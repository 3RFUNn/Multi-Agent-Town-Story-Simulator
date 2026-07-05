"""The simulation kernel: deterministic, synchronous, journaled.

step() is a pure function of (state, tick) given the seed — it never awaits,
never blocks on I/O other than the append-only journal, and applies async
cognition results (Intents) only at tick boundaries.
"""
from __future__ import annotations

import structlog

from townsim.agents.agent import UTILITY_AXES, AgentState
from townsim.agents.components import Needs, Relationship, Wallet
from townsim.agents.schedule import is_in_window
from townsim.behavior.blackboard import Blackboard, Scope
from townsim.behavior.trees import build_agent_tree
from townsim.cognition.memory import MemoryEntry, MemoryStream
from townsim.cognition.narrative import NarrativeCoordinator
from townsim.cognition.reflection import ReflectionResult
from townsim.config.content import AGENTS, RELATIONSHIPS, validate_content
from townsim.config.models import SimConfig
from townsim.kernel.clock import SimClock
from townsim.kernel.events import BEHAVIORAL, Event, Intent
from townsim.kernel.journal import Journal, new_run_dir
from townsim.kernel.rng import RngRegistry
from townsim.systems import SysContext, default_systems
from townsim.world.grid import TownMap
from townsim.world.state import WorldState

log = structlog.get_logger(__name__)


def build_world(cfg: SimConfig, rng: RngRegistry) -> WorldState:
    town = TownMap.load(cfg.paths.map_file)
    warnings = validate_content(set(town.places.keys()))
    for warning in warnings:
        log.warning("content", note=warning)
    world = WorldState(town=town)
    init_rng = rng.stream("init")
    for spec in AGENTS:
        agent = AgentState(
            spec=spec, x=spec.home_pos[0], y=spec.home_pos[1],
            needs=Needs(hunger=init_rng.uniform(10, 30), social=init_rng.uniform(10, 30),
                        fatigue=init_rng.uniform(5, 20)),
            wallet=Wallet(money=float(init_rng.randint(cfg.economy.starting_money_min,
                                                       cfg.economy.starting_money_max))),
            memory=MemoryStream(                      # R21: scoring knobs wired
                alpha_recency=cfg.memory.alpha_recency,
                beta_importance=cfg.memory.beta_importance,
                gamma_relevance=cfg.memory.gamma_relevance,
                decay_per_tick=cfg.memory.recency_decay_per_tick,
            ),
        )
        for other_id, rel in RELATIONSHIPS.get(spec.id, {}).items():
            agent.relationships[other_id] = Relationship(
                kind=rel["type"], affinity=float(rel["affinity"]),
                familiarity=30.0, valence=0.0)
        agent.behavior_tree = build_agent_tree(spec.id)
        world.add_agent(agent)
    return world


class Kernel:
    def __init__(self, cfg: SimConfig, *, narrative: NarrativeCoordinator | None = None,
                 run_dir=None) -> None:
        self.cfg = cfg
        self.clock = SimClock(cfg.kernel.tick_minutes, cfg.kernel.day_start_hour)
        self.rng = RngRegistry(cfg.kernel.seed)
        self.world = build_world(cfg, self.rng)
        self.bb = Blackboard()
        self.systems = default_systems()
        self.narrative = narrative
        self.run_dir = run_dir or new_run_dir(cfg.paths.runs_dir, cfg.kernel.seed)
        self.journal = Journal(self.run_dir, cfg.kernel.seed,
                               config_summary={"tick_minutes": cfg.kernel.tick_minutes,
                                               "agents": len(self.world.agents),
                                               "provider": cfg.llm.resolve_provider()})
        self.tick = 0
        self.paused = False
        self._day_events: list[Event] = []

    # ------------------------------------------------------------------ step
    def step(self) -> list[Event]:
        now = self.clock.at(self.tick)
        ctx = SysContext(world=self.world, cfg=self.cfg, bb=self.bb,
                         rng=self.rng, now=now)

        if self.tick == 0:
            ctx.emit("sim_started", seed=self.cfg.kernel.seed,
                     agents=[a.id for a in self.world.agents_sorted()])
            ctx.emit("day_started", weekday=now.weekday, day_number=now.day_index + 1)

        if self.clock.is_day_rollover(self.tick):
            self._on_day_rollover(ctx)

        for system in self.systems:
            system.update(ctx)

        self._apply_intents(ctx)

        # Salient conversations get an async dialogue rendering (C1).
        if self.narrative is not None:
            for event in ctx.events:
                if event.type == "conversation_ended" and event.data.get("salient"):
                    self.narrative.on_salient_conversation(
                        self.world, event, now.weekday, now.label())

        self.journal.extend(ctx.events)
        self._day_events.extend(e for e in ctx.events if e.type in BEHAVIORAL)
        self.tick += 1
        return ctx.events

    # ------------------------------------------------------------- rollover
    def _on_day_rollover(self, ctx: SysContext) -> None:
        now = ctx.now
        prev = self.clock.at(self.tick - 1)
        ctx.emit("day_started", weekday=now.weekday, day_number=now.day_index + 1)
        log.info("new day", day=now.day_index + 1, weekday=now.weekday)

        # 1) snapshot prompts & enqueue narrative jobs BEFORE any pruning
        if self.narrative is not None:
            self.narrative.on_day_end(self.world, prev.day_index, prev.weekday,
                                      list(self._day_events), now_tick=self.tick)
        self._day_events = []

        # 2) per-agent daily housekeeping
        self.world.today_pairs.clear()
        for agent in self.world.agents_sorted():
            agent.daily_dialogues_used = 0
            self.bb.delete(Scope.AGENT, agent.id, "rest_spot")   # R18: no sticky choices
            agent.wallet.paid_slots = {
                s for s in agent.wallet.paid_slots if s[0] >= now.day_index - 1}
            agent.schedule_overrides = {
                k: v for k, v in agent.schedule_overrides.items() if k[0] >= now.day_index}
            cutoff = now.day_index - self.cfg.memory.compact_after_days
            if cutoff > 0:
                old = [e for e in agent.memory.entries
                       if e.kind == "event" and e.day_index < cutoff]
                summary = None
                if old:
                    top = sorted(old, key=lambda e: e.importance, reverse=True)[:3]
                    summary = MemoryEntry(
                        text="Earlier days: " + " / ".join(e.text for e in top),
                        day_index=cutoff - 1, tick=now.tick, importance=0.5, kind="summary")
                agent.memory.compact_before(cutoff, summary)

    # -------------------------------------------------------------- intents
    def _apply_intents(self, ctx: SysContext) -> None:
        if self.narrative is None:
            return
        while self.narrative.intents:
            intent = self.narrative.intents.popleft()
            try:
                self._apply_intent(ctx, intent)
            except Exception:
                log.exception("intent application failed", kind=intent.kind)

    def _apply_intent(self, ctx: SysContext, intent: Intent) -> None:
        payload = intent.payload
        if intent.kind == "diary_ready":
            agent = self.world.agents.get(intent.agent_id)
            if agent is None:
                return
            day_number = payload["day_index"] + 1
            diary_dir = self.run_dir / "diaries" / f"day_{day_number}"
            diary_dir.mkdir(parents=True, exist_ok=True)
            (diary_dir / f"{agent.id}.txt").write_text(payload["text"], encoding="utf-8")
            agent.last_diary = {"day": day_number, "text": payload["text"]}
            ctx.emit("diary_written", agent_id=agent.id, day_number=day_number,
                     text=payload["text"])
        elif intent.kind == "story_ready":
            day_number = payload["day_number"]
            label = f"Day {day_number} ({payload['weekday']})"
            story = {"day": label, "day_index": payload["day_index"], "text": payload["text"]}
            self.world.stories.append(story)
            stories_dir = self.run_dir / "stories"
            stories_dir.mkdir(parents=True, exist_ok=True)
            (stories_dir / f"day_{day_number}.txt").write_text(payload["text"], encoding="utf-8")
            ctx.emit("story_written", day_number=day_number, weekday=payload["weekday"],
                     text=payload["text"])
        elif intent.kind == "reflection_ready":
            agent = self.world.agents.get(intent.agent_id)
            if agent is None:
                return
            result = ReflectionResult.model_validate(payload["result"]).sanitized(UTILITY_AXES)
            agent.mood = result.mood
            applied = []
            for adjustment in result.goal_adjustments:
                if agent.apply_goal_adjustment(adjustment.goal, adjustment.delta):
                    applied.append({"goal": adjustment.goal, "delta": adjustment.delta})
            next_day = payload["day_index"] + 1
            for proposal in result.schedule_proposals:
                key = (next_day, proposal.start_hour, proposal.end_hour)
                agent.schedule_overrides[key] = proposal.activity
                ctx.emit("schedule_override_applied", agent_id=agent.id,
                         day_index=next_day, start=proposal.start_hour,
                         end=proposal.end_hour, activity=proposal.activity)
            for insight in result.insights:
                agent.memory.add(MemoryEntry(
                    text=f"(reflection) {insight}", day_index=ctx.now.day_index,
                    tick=ctx.now.tick, importance=0.6, kind="reflection"))
            ctx.emit("reflection_applied", agent_id=agent.id, mood=result.mood,
                     adjustments=applied, proposals=len(result.schedule_proposals))
        elif intent.kind == "dialogue_ready":
            agent = self.world.agents.get(intent.agent_id)
            partner = self.world.agents.get(payload.get("partner"))
            if agent is None or partner is None:
                return
            snippet = payload["text"][:400]
            for me, other in ((agent, partner), (partner, agent)):
                me.memory.add(MemoryEntry(
                    text=f"Conversation with {other.spec.name}: {snippet}",
                    day_index=payload["day_index"], tick=ctx.now.tick,
                    importance=0.6, participants=(other.id,), kind="event"))
            ctx.emit("dialogue_rendered", agent_id=agent.id,
                     partner=partner.id, text=payload["text"])

    def flush_intents(self) -> list[Event]:
        """Apply pending cognition intents outside of step() (end of run),
        journaling the resulting events. Events are stamped with the LAST
        STEPPED tick (R22), not a tick that never ran."""
        last = max(0, self.tick - 1)
        ctx = SysContext(world=self.world, cfg=self.cfg, bb=self.bb,
                         rng=self.rng, now=self.clock.at(last))
        self._apply_intents(ctx)
        self.journal.extend(ctx.events)
        return ctx.events

    # ------------------------------------------------------------- helpers
    def now(self):
        return self.clock.at(self.tick)

    def is_sleep_window(self, agent: AgentState) -> bool:
        start, end = agent.spec.sleep_window
        return is_in_window(self.now().hour, start, end)

    def close(self) -> None:
        self.journal.close()
