"""Narrative coordinator: the async cognition side of the architecture.

At each day rollover the kernel calls on_day_end(), which SNAPSHOTS all
prompt inputs synchronously (no shared mutable state crosses into workers)
and enqueues jobs. Async workers call the LLM gateway and push results back
as typed Intents that the kernel applies at tick boundaries.

A failed job is logged and skipped — narrative failures can never stall or
kill the simulation (V1's F01/F03).
"""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import structlog

from townsim.cognition.reflection import ReflectionResult
from townsim.config.models import SimConfig
from townsim.kernel.events import Event, Intent
from townsim.llm.gateway import LLMGateway
from townsim.llm.templates import PromptLibrary

log = structlog.get_logger(__name__)


@dataclass
class Job:
    kind: str                  # diary | reflect | story | dialogue
    day_index: int
    agent_id: str | None
    prompt: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class _PendingStory:
    weekday: str
    day_number: int
    expected: int
    beats: list[str]
    diaries: dict[str, tuple[str, str]] = field(default_factory=dict)  # id -> (name, text)
    dispatched: bool = False


class NarrativeCoordinator:
    def __init__(self, gateway: LLMGateway, prompts: PromptLibrary, cfg: SimConfig,
                 num_workers: int = 3) -> None:
        self.gateway = gateway
        self.prompts = prompts
        self.cfg = cfg
        self.queue: asyncio.Queue[Job] = asyncio.Queue()
        self.intents: deque[Intent] = deque()
        self._pending_stories: dict[int, _PendingStory] = {}
        self._num_workers = num_workers
        self._tasks: list[asyncio.Task] = []

    # ---- lifecycle --------------------------------------------------------
    def start(self) -> None:
        for i in range(self._num_workers):
            self._tasks.append(asyncio.create_task(self._worker(i)))

    async def stop(self) -> None:
        await self.drain()
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

    async def drain(self, timeout: float | None = None) -> None:
        """Wait for queued narrative work to finish (used at shutdown /
        end of a headless run so the last day's story is not lost). The
        default timeout is configurable — slow rate-limited providers
        (free tiers) need minutes, not seconds."""
        if timeout is None:
            timeout = self.cfg.llm.narrative_drain_timeout_s
        try:
            await asyncio.wait_for(self.queue.join(), timeout=timeout)
        except asyncio.TimeoutError:
            log.warning("narrative drain timed out", pending=self.queue.qsize())

    # ---- kernel-facing (synchronous; called at day rollover) --------------
    def on_day_end(self, world, prev_day_index: int, weekday: str,
                   day_events: list[Event], now_tick: int = 0) -> None:
        day_number = prev_day_index + 1
        beats = detect_beats(world, day_events)
        agents = world.agents_sorted()
        self._pending_stories[prev_day_index] = _PendingStory(
            weekday=weekday, day_number=day_number, expected=len(agents), beats=beats)

        for agent in agents:
            memories = [e.text for e in agent.memory.for_day(prev_day_index)]
            summaries = [e.text for e in agent.memory.summaries()][-6:]
            diary_prompt = self.prompts.render(
                "diary_v2.j2",
                name=agent.spec.name, background=agent.spec.background,
                personality=", ".join(agent.spec.personality), mood=agent.mood,
                weekday=weekday, day_number=day_number,
                summaries=summaries, memories=memories or ["A quiet, uneventful day."],
            )
            self.queue.put_nowait(Job("diary", prev_day_index, agent.id, diary_prompt,
                                      meta={"name": agent.spec.name}))

            # Scored retrieval (recency x importance; relevance when
            # embeddings are present) picks what the agent reflects on (R21).
            top = agent.memory.retrieve(None, now_tick, k=self.cfg.memory.retrieve_k)
            reflect_prompt = self.prompts.render(
                "reflect_v1.j2",
                name=agent.spec.name, personality=", ".join(agent.spec.personality),
                mood=agent.mood, weekday=weekday, day_number=day_number,
                memories=[e.text for e in top] or ["A quiet, uneventful day."],
                weights=dict(agent.utility_weights),
            )
            self.queue.put_nowait(Job("reflect", prev_day_index, agent.id, reflect_prompt))

    def on_salient_conversation(self, world, event: Event, weekday: str,
                                time_label: str) -> None:
        """Render a short dialogue for a salient encounter (budgeted)."""
        a = world.agents.get(event.agent_id)
        b = world.agents.get(event.data.get("partner"))
        if a is None or b is None:
            return
        rel = a.relationship_with(b.id)
        quality = event.data.get("quality", 0.5)
        tone = "warm and lively" if quality > 0.7 else \
               "friendly but a little flat" if quality > 0.4 else "awkward and short"
        recent = [e.text for e in a.memory.for_day(event.day_index)][-5:]
        prompt = self.prompts.render(
            "dialogue_v1.j2",
            a_name=a.spec.name, a_personality=", ".join(a.spec.personality), a_mood=a.mood,
            b_name=b.spec.name, b_personality=", ".join(b.spec.personality), b_mood=b.mood,
            relationship=rel.kind, affinity=int(rel.affinity),
            location=(event.data.get("location") or "the street").replace("_", " "),
            weekday=weekday, time_label=time_label, tone=tone, a_context=recent,
        )
        self.queue.put_nowait(Job("dialogue", event.day_index, a.id, prompt,
                                  meta={"partner": b.id}))

    # ---- workers ------------------------------------------------------------
    async def _worker(self, worker_id: int) -> None:
        while True:
            job = await self.queue.get()
            try:
                await self._run_job(job)
            except Exception:
                log.exception("narrative job failed", kind=job.kind, agent=job.agent_id,
                              day=job.day_index)
                if job.kind == "diary":
                    self._diary_done(job.day_index, job.agent_id, job.meta.get("name", ""),
                                     text=None)
            finally:
                self.queue.task_done()

    async def _run_job(self, job: Job) -> None:
        llm_cfg = self.cfg.llm
        if job.kind == "diary":
            text = await self.gateway.complete(job.prompt, max_tokens=llm_cfg.diary_max_tokens)
            self.intents.append(Intent("diary_ready", job.agent_id,
                                       {"day_index": job.day_index, "text": text}))
            self._diary_done(job.day_index, job.agent_id, job.meta.get("name", ""), text)
        elif job.kind == "reflect":
            result = await self.gateway.complete_structured(job.prompt, ReflectionResult)
            self.intents.append(Intent("reflection_ready", job.agent_id,
                                       {"day_index": job.day_index,
                                        "result": result.model_dump()}))
        elif job.kind == "story":
            text = await self.gateway.complete(job.prompt, max_tokens=llm_cfg.story_max_tokens)
            self.intents.append(Intent("story_ready", None,
                                       {"day_index": job.day_index,
                                        "weekday": job.meta["weekday"],
                                        "day_number": job.meta["day_number"], "text": text}))
        elif job.kind == "dialogue":
            # Never semantically cached (R11): a near-duplicate prompt for a
            # DIFFERENT pair would replay the wrong names into their memories.
            text = await self.gateway.complete(job.prompt, max_tokens=400)
            self.intents.append(Intent("dialogue_ready", job.agent_id,
                                       {"day_index": job.day_index,
                                        "partner": job.meta["partner"], "text": text}))

    def _diary_done(self, day_index: int, agent_id: str | None, name: str,
                    text: str | None) -> None:
        pending = self._pending_stories.get(day_index)
        if pending is None:
            return
        if text is not None and agent_id is not None:
            pending.diaries[agent_id] = (name, text)
        else:
            pending.expected -= 1  # failed diary: don't wait for it
        if not pending.dispatched and len(pending.diaries) >= pending.expected:
            pending.dispatched = True
            diaries = [{"name": n, "excerpt": t[:800]} for n, t in
                       [pending.diaries[k] for k in sorted(pending.diaries)]]
            prompt = self.prompts.render(
                "story_v2.j2", weekday=pending.weekday, day_number=pending.day_number,
                beats=pending.beats, diaries=diaries,
            )
            self.queue.put_nowait(Job("story", day_index, None, prompt,
                                      meta={"weekday": pending.weekday,
                                            "day_number": pending.day_number}))
            del self._pending_stories[day_index]


# ---- emergent event detection (rule triggers -> story beats) ----------------
def detect_beats(world, day_events: list[Event]) -> list[str]:
    """Deterministic rule triggers nominate the day's story beats (C2)."""
    scored: list[tuple[float, str]] = []

    def name(agent_id: str | None) -> str:
        agent = world.agents.get(agent_id) if agent_id else None
        return agent.spec.name if agent else str(agent_id)

    seen_pairs: set[frozenset] = set()
    for event in day_events:
        data = event.data
        if event.type == "conversation_ended":
            pair = frozenset((event.agent_id, data.get("partner")))
            quality = data.get("quality", 0)
            place = (data.get("location") or "town").replace("_", " ")
            if data.get("salient") and pair not in seen_pairs:
                seen_pairs.add(pair)
                scored.append((0.9, f"{name(event.agent_id)} and {name(data.get('partner'))} "
                                    f"had a memorable conversation at the {place}"))
            elif quality > 0.85:
                scored.append((0.7, f"{name(event.agent_id)} and {name(data.get('partner'))} "
                                    f"really hit it off at the {place}"))
        elif event.type == "relationship_changed" and data.get("quality", 0) > 0.9:
            scored.append((0.6, f"{name(event.agent_id)} and {name(data.get('partner'))} "
                                f"grew noticeably closer today"))
        elif event.type == "cost_paid" and data.get("activity") == "eat_at_cafe":
            scored.append((0.5, f"{name(event.agent_id)} got caught out starving and had to "
                                f"grab an emergency meal at the cafe"))
        elif event.type == "sleep_started" and data.get("emergency"):
            scored.append((0.5, f"{name(event.agent_id)} ran themselves ragged and crashed "
                                f"into bed early"))
        elif event.type == "path_failed":
            scored.append((0.3, f"{name(event.agent_id)} couldn't get where they were going "
                                f"and had to change plans"))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    beats = []
    for _, text in scored:
        if text not in beats:
            beats.append(text)
    return beats[:8]
