# Code samples for section 7

## S1 — Async LLM gateway

```python
# townsim/llm/gateway.py
"""Provider-agnostic async LLM gateway: retries, timeouts, bounded concurrency,
semantic caching, and schema-validated structured output."""
from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

import numpy as np
from pydantic import BaseModel, ValidationError
from tenacity import (
    retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter,
)

T = TypeVar("T", bound=BaseModel)


class TransientLLMError(Exception):
    """Rate limits, 5xx, timeouts — safe to retry."""


class LLMProvider(Protocol):
    async def complete(self, prompt: str, *, max_tokens: int, temperature: float) -> str: ...
    async def embed(self, text: str) -> list[float]: ...


class OpenAIProvider:
    def __init__(self, api_key: str, model: str = "gpt-4.1-mini",
                 embed_model: str = "text-embedding-3-small") -> None:
        from openai import AsyncOpenAI, APIStatusError, APITimeoutError, RateLimitError
        self._client = AsyncOpenAI(api_key=api_key, timeout=30.0)
        self._model, self._embed_model = model, embed_model
        self._transient = (RateLimitError, APITimeoutError, APIStatusError)

    async def complete(self, prompt: str, *, max_tokens: int, temperature: float) -> str:
        try:
            rsp = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens, temperature=temperature,
            )
        except self._transient as exc:          # normalize for tenacity
            raise TransientLLMError(str(exc)) from exc
        return rsp.choices[0].message.content or ""

    async def embed(self, text: str) -> list[float]:
        try:
            rsp = await self._client.embeddings.create(model=self._embed_model, input=text)
        except self._transient as exc:
            raise TransientLLMError(str(exc)) from exc
        return rsp.data[0].embedding


@dataclass
class SemanticCache:
    """Reuses responses for near-duplicate prompts (cosine >= threshold)."""
    threshold: float = 0.97
    _keys: list[np.ndarray] = field(default_factory=list)
    _values: list[str] = field(default_factory=list)

    def get(self, embedding: list[float]) -> str | None:
        if not self._keys:
            return None
        q = np.asarray(embedding)
        q = q / np.linalg.norm(q)
        matrix = np.stack(self._keys)                       # (n, d), rows unit-norm
        best = int(np.argmax(matrix @ q))
        return self._values[best] if float(matrix[best] @ q) >= self.threshold else None

    def put(self, embedding: list[float], value: str) -> None:
        v = np.asarray(embedding)
        self._keys.append(v / np.linalg.norm(v))
        self._values.append(value)


class LLMGateway:
    def __init__(self, provider: LLMProvider, *, max_concurrency: int = 4,
                 cache: SemanticCache | None = None) -> None:
        self._provider = provider
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._cache = cache

    @retry(retry=retry_if_exception_type(TransientLLMError),
           wait=wait_exponential_jitter(initial=1, max=30), stop=stop_after_attempt(5),
           reraise=True)
    async def _complete_raw(self, prompt: str, max_tokens: int, temperature: float) -> str:
        async with self._semaphore:
            return await self._provider.complete(
                prompt, max_tokens=max_tokens, temperature=temperature)

    async def complete(self, prompt: str, *, max_tokens: int = 1024,
                       temperature: float = 0.8, cacheable: bool = False) -> str:
        embedding: list[float] | None = None
        if cacheable and self._cache is not None:
            embedding = await self._provider.embed(prompt)
            if (hit := self._cache.get(embedding)) is not None:
                return hit
        text = await self._complete_raw(prompt, max_tokens, temperature)
        if embedding is not None:
            self._cache.put(embedding, text)
        return text

    async def complete_structured(self, prompt: str, schema: type[T], *,
                                  max_tokens: int = 1024, attempts: int = 3) -> T:
        """LLM output -> validated Pydantic model, re-prompting on invalid JSON."""
        suffix = ("\nRespond with ONLY a JSON object matching this schema:\n"
                  f"{json.dumps(schema.model_json_schema(), indent=2)}")
        last_error = ""
        for _ in range(attempts):
            raw = await self.complete(prompt + suffix + last_error,
                                      max_tokens=max_tokens, temperature=0.2)
            try:
                start, end = raw.find("{"), raw.rfind("}") + 1
                return schema.model_validate_json(raw[start:end])
            except (ValidationError, ValueError) as exc:
                last_error = f"\nYour previous answer failed validation: {exc}. Fix it."
        raise ValueError(f"LLM output failed {schema.__name__} validation {attempts}x")
```

Usage in the sim — cognition never blocks the kernel:

```python
# townsim/cognition/narrative_worker.py
async def narrative_worker(queue: asyncio.Queue, gateway: LLMGateway, journal: Journal):
    while True:
        job = await queue.get()                      # e.g. ("diary", agent_id, day_index)
        try:
            text = await gateway.complete(job.prompt, max_tokens=2048)
            journal.append("narrative_ready", kind=job.kind, agent=job.agent_id, text=text)
        except Exception:
            log.exception("narrative job failed", job=job)   # sim keeps running
        finally:
            queue.task_done()
```

## S2 — BT core with a real UtilitySelector

```python
# townsim/behavior/core.py
"""Minimal, correct BT runtime with a utility-driven selector.
(If adopting py_trees, UtilitySelector becomes a custom composite; the
semantics below are what matter.)"""
from __future__ import annotations

import enum
from abc import ABC, abstractmethod


class Status(enum.Enum):
    SUCCESS = enum.auto()
    FAILURE = enum.auto()
    RUNNING = enum.auto()


class Node(ABC):
    def __init__(self, name: str) -> None:
        self.name = name
        self.status: Status | None = None

    @abstractmethod
    def tick(self, ctx: "TickContext") -> Status: ...

    def utility(self, ctx: "TickContext") -> float:
        """Predicted desirability of running this subtree now. Override in
        branch roots; composites default to max over children."""
        return 0.0

    def reset(self) -> None:
        self.status = None
        for child in getattr(self, "children", []):
            child.reset()


class UtilitySelector(Node):
    """Scores children, tries them in descending utility, FALLS BACK on
    failure, and stays committed to a RUNNING child until it resolves."""

    def __init__(self, name: str, children: list[Node],
                 commitment_bonus: float = 0.15) -> None:
        super().__init__(name)
        self.children = children
        self._running_child: Node | None = None
        # Hysteresis: a running branch keeps a small bonus so agents don't
        # oscillate between near-equal utilities every tick.
        self._commitment_bonus = commitment_bonus

    def tick(self, ctx: "TickContext") -> Status:
        scored = sorted(
            self.children,
            key=lambda c: c.utility(ctx)
            + (self._commitment_bonus if c is self._running_child else 0.0),
            reverse=True,
        )
        for child in scored:
            if child is not self._running_child:
                child.reset()
            status = child.tick(ctx)
            if status == Status.RUNNING:
                self._running_child = child
                self.status = Status.RUNNING
                return Status.RUNNING
            if status == Status.SUCCESS:
                self._running_child = None
                self.status = Status.SUCCESS
                return Status.SUCCESS
            # FAILURE -> try the next-best child (V1 returned FAILURE here,
            # which is why the Idle branch never ran).
        self._running_child = None
        self.status = Status.FAILURE
        return Status.FAILURE

    def reset(self) -> None:
        super().reset()
        self._running_child = None
```

```python
# townsim/behavior/utilities.py — utilities computed from real state, not name matching
def free_time_socialize_utility(ctx: TickContext) -> float:
    agent = ctx.agent
    pressure = agent.needs.social / 100.0                       # 0..1
    talkativeness = agent.personality.talkativeness             # 0..1
    nearby = ctx.world.spatial.count_neighbors(agent.pos, radius=6)
    opportunity = min(nearby, 3) / 3.0
    return pressure * (0.5 + 0.5 * talkativeness) * (0.3 + 0.7 * opportunity)
```

The standard location-guard idiom every "do X somewhere" branch must use
(V1's emergency-food branch omits it and eats in place):

```python
def eat_out_branch() -> Node:
    return Selector("eat out", [
        Sequence("eat here", [IsAtLocation("at cafe", key="eat_target"),
                              ExecuteEat("eat")]),
        GoTo("walk to cafe", key="eat_target"),      # returns RUNNING while walking
    ])
```

## S3 — Scoped blackboard

```python
# townsim/behavior/blackboard.py
"""Three-scope blackboard: AGENT (private), GROUP (shared by an interaction
group), WORLD (global). Replaces both the ad-hoc attributes stuck onto Agent
(rest_location, eat_ticks, ...) and the shared-dict mutation bugs
(world_state['activity_data'] being overwritten per agent)."""
from __future__ import annotations

import enum
from collections import defaultdict
from typing import Any


class Scope(enum.Enum):
    AGENT = "agent"
    GROUP = "group"
    WORLD = "world"


class Blackboard:
    def __init__(self) -> None:
        self._data: dict[tuple[Scope, str, str], Any] = {}
        self._group_of: dict[str, str] = {}          # agent_id -> group_id

    def _key(self, scope: Scope, owner: str, name: str) -> tuple[Scope, str, str]:
        if scope is Scope.WORLD:
            return (scope, "*", name)
        if scope is Scope.GROUP:
            return (scope, self._group_of.get(owner, owner), name)
        return (scope, owner, name)

    def get(self, scope: Scope, owner: str, name: str, default: Any = None) -> Any:
        return self._data.get(self._key(scope, owner, name), default)

    def set(self, scope: Scope, owner: str, name: str, value: Any) -> None:
        self._data[self._key(scope, owner, name)] = value

    def clear_agent(self, agent_id: str) -> None:
        self._data = {k: v for k, v in self._data.items()
                      if not (k[0] is Scope.AGENT and k[1] == agent_id)}

    def join_group(self, agent_id: str, group_id: str) -> None:
        self._group_of[agent_id] = group_id

    def leave_group(self, agent_id: str) -> None:
        self._group_of.pop(agent_id, None)
```

## S4 — Memory stream with scored retrieval + typed reflection

```python
# townsim/cognition/memory.py
"""Generative-Agents-style episodic memory keyed by absolute day index
(fixes V1, which keyed by weekday name so week 2 re-ingested week 1)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from pydantic import BaseModel, Field


@dataclass
class MemoryEntry:
    text: str
    day_index: int                    # absolute day, not weekday name
    tick: int
    importance: float                 # 0..1
    location: str | None = None
    participants: tuple[str, ...] = ()
    embedding: np.ndarray | None = None


@dataclass
class MemoryStream:
    alpha_recency: float = 1.0
    beta_importance: float = 1.0
    gamma_relevance: float = 1.0
    decay_per_tick: float = 0.995
    entries: list[MemoryEntry] = field(default_factory=list)

    def add(self, entry: MemoryEntry) -> None:
        self.entries.append(entry)

    def for_day(self, day_index: int) -> list[MemoryEntry]:
        return [e for e in self.entries if e.day_index == day_index]

    def retrieve(self, query_embedding: np.ndarray, now_tick: int, k: int = 12
                 ) -> list[MemoryEntry]:
        """score = a*recency + b*importance + c*relevance (Park et al., 2023)."""
        if not self.entries:
            return []
        q = query_embedding / np.linalg.norm(query_embedding)
        scored = []
        for e in self.entries:
            recency = self.decay_per_tick ** max(0, now_tick - e.tick)
            relevance = 0.0 if e.embedding is None else float(
                np.dot(e.embedding / np.linalg.norm(e.embedding), q))
            score = (self.alpha_recency * recency
                     + self.beta_importance * e.importance
                     + self.gamma_relevance * relevance)
            scored.append((score, e))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [e for _, e in scored[:k]]

    def compact(self, before_day: int, summary: MemoryEntry) -> None:
        """Hierarchical summarization: old episodics -> one summary entry."""
        self.entries = [e for e in self.entries if e.day_index >= before_day]
        self.entries.append(summary)


class GoalAdjustment(BaseModel):
    goal: str                                   # must name a known utility axis
    delta: float = Field(ge=-0.2, le=0.2)       # clamped: bounded feedback


class ScheduleProposal(BaseModel):
    day: str
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=0, le=23)
    activity: str                               # validated against ACTIVITY_DATA
    invitee: str | None = None


class ReflectionResult(BaseModel):
    """The ONLY channel through which LLM cognition may influence behavior.
    Everything is typed, bounded, and validated before the kernel applies it."""
    mood: str
    insights: list[str] = Field(max_length=3)
    goal_adjustments: list[GoalAdjustment] = Field(max_length=3)
    schedule_proposals: list[ScheduleProposal] = Field(max_length=2)


async def reflect(agent, gateway: "LLMGateway", day_index: int) -> ReflectionResult:
    highlights = agent.memory.for_day(day_index)
    prompt = render_template(
        "reflect_v1.j2", agent=agent,
        memories=[e.text for e in sorted(highlights,
                                         key=lambda e: e.importance, reverse=True)[:20]],
    )
    result = await gateway.complete_structured(prompt, ReflectionResult)
    # Kernel-side guards, never trust even validated output blindly:
    result.goal_adjustments = [a for a in result.goal_adjustments
                               if a.goal in agent.utility_axes]
    result.schedule_proposals = [p for p in result.schedule_proposals
                                 if p.activity in ACTIVITY_DATA]
    return result
```

## S5 — Fixed-timestep kernel with journal (excerpt)

```python
# townsim/kernel/loop.py
async def run(kernel: Kernel, cfg: SimConfig) -> None:
    tick_budget = 1.0 / cfg.ticks_per_second     # 0 => headless, run flat out
    while kernel.running:
        started = time.perf_counter()
        events = kernel.step()                   # pure, deterministic, seeded RNG
        kernel.journal.extend(events)            # append-only JSONL
        await kernel.hub.broadcast_delta(events) # WS delta, not full state
        while not kernel.intents.empty():        # apply async cognition results
            kernel.apply(kernel.intents.get_nowait())   # only at tick boundaries
        if tick_budget:
            await asyncio.sleep(max(0.0, tick_budget - (time.perf_counter() - started)))
```

## S6 — Overnight schedule windows (micro-fix, drop-in for V1)

```python
def is_in_window(hour: int, start: int, end: int) -> bool:
    """(22, 1) means 22:00-01:00 across midnight."""
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end
```
