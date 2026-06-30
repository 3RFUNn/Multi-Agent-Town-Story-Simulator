"""Ports (interfaces) for the hexagonal architecture.

Every adapter — in-memory or production (Anthropic/OpenAI, Kafka, pgvector,
Flask) — implements one of these ``Protocol`` contracts. The engine depends only
on these abstractions, never on concrete adapters, which is what lets the whole
core run and test offline with mock/in-memory implementations while staying
ready for real infrastructure.

This module is the frozen contract that all engine modules are built against.
It imports only from :mod:`matss.domain` and the standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any, Callable, Dict, Iterator, List, Optional, Protocol, Sequence,
    runtime_checkable,
)

from .domain.events import Event
from .domain.memory import MemoryRecord


# ===========================================================================
# LLM provider stack
# ===========================================================================

class ModelTier:
    """Capability tiers for cost/quality routing (mapped to concrete models)."""

    CHEAP = "cheap"        # high-volume reflex calls (e.g. Haiku / local model)
    BALANCED = "balanced"  # per-agent diaries (e.g. Sonnet)
    FRONTIER = "frontier"  # director / town-story synthesis (e.g. Opus)

    ALL = (CHEAP, BALANCED, FRONTIER)


@dataclass(frozen=True)
class LLMRequest:
    """A provider-agnostic LLM request.

    ``cache_prefix`` is the stable, reusable portion of the prompt (persona +
    world description) that a caching adapter can deduplicate across calls.
    ``response_schema`` (a JSON-schema dict) requests structured output.
    """

    prompt: str
    system: Optional[str] = None
    tier: str = ModelTier.BALANCED
    max_tokens: int = 1024
    temperature: float = 0.8
    cache_prefix: Optional[str] = None
    response_schema: Optional[Dict[str, Any]] = None
    stop: Optional[Sequence[str]] = None
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    """A provider-agnostic LLM response."""

    text: str
    model: str
    tier: str = ModelTier.BALANCED
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cached: bool = False
    structured: Optional[Dict[str, Any]] = None
    latency_ms: float = 0.0
    finish_reason: str = "stop"


@runtime_checkable
class LLMProvider(Protocol):
    """Generates text/structured completions. Implemented by mock + real adapters."""

    name: str

    def complete(self, request: LLMRequest) -> LLMResponse: ...

    def batch(self, requests: Sequence[LLMRequest]) -> List[LLMResponse]: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Maps text to a fixed-dimension vector."""

    dim: int

    def embed(self, text: str) -> List[float]: ...

    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]: ...


# ===========================================================================
# Vector store (agent memory retrieval)
# ===========================================================================

@dataclass(frozen=True)
class VectorHit:
    key: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class VectorStore(Protocol):
    """An approximate-nearest-neighbour store (in-memory cosine or pgvector/Qdrant)."""

    def add(self, key: str, vector: Sequence[float], metadata: Optional[Dict[str, Any]] = None) -> None: ...

    def query(self, vector: Sequence[float], k: int) -> List[VectorHit]: ...

    def remove(self, key: str) -> None: ...

    def __len__(self) -> int: ...


@runtime_checkable
class MemoryRetriever(Protocol):
    """Retrieval surface the narrative layer depends on (implemented by the
    memory stream). Kept here so cognition need not import the memory module."""

    def retrieve(self, agent_id: str, query: str, k: int, now_tick: int) -> List[MemoryRecord]: ...

    def memories_for_day(self, agent_id: str, day: str) -> List[MemoryRecord]: ...


# ===========================================================================
# Event sourcing: bus (live) + log (durable, canonical)
# ===========================================================================

EventHandler = Callable[[Event], None]


@runtime_checkable
class EventBus(Protocol):
    """Live publish/subscribe used to decouple the sim core from transports.

    Publishing to the bus is how the simulation notifies the persistence log,
    the web gateway, metrics, etc. — WITHOUT the sim importing any of them
    (this is what breaks the prototype's ``manager -> app`` import cycle).
    """

    def publish(self, event: Event) -> None: ...

    def subscribe(self, handler: EventHandler) -> None: ...


@runtime_checkable
class EventLog(Protocol):
    """Append-only, ordered, replayable log — the canonical source of truth.

    The in-memory and JSONL adapters are stdlib-only; a Kafka/Redpanda adapter
    implements the same contract for production.
    """

    def append(self, event: Event) -> Event: ...

    def append_many(self, events: Sequence[Event]) -> List[Event]: ...

    def read(self, from_seq: int = 0) -> Iterator[Event]: ...

    def __len__(self) -> int: ...


# ===========================================================================
# Clock (deterministic; no wall-clock in the domain)
# ===========================================================================

@runtime_checkable
class Clock(Protocol):
    """Supplies timestamps. The deterministic sim clock derives time from ticks."""

    def now_ms(self) -> float: ...
