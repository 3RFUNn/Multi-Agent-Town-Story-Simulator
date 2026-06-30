"""Composition root: wire a :class:`SimulationEngine` from ports.

``build_engine`` assembles the engine with offline-by-default adapters (mock LLM,
in-memory event log/bus, in-memory vector store) so a full simulation runs with
zero external dependencies. Any port can be overridden to plug in a production
adapter (Anthropic/OpenAI, JSONL/Kafka log, pgvector store) without touching the
engine.
"""

from __future__ import annotations

from typing import Any, Optional

from ..cognition.llm import MockLLMProvider
from ..cognition.narrative import NarrativeSystem
from ..cognition.queue import CognitionQueue
from ..config.loader import Content, load_content
from ..eventlog import InMemoryEventLog, InProcessEventBus
from ..memory import MemoryStream, MockEmbeddingProvider
from ..pathfinding import PathPlanner
from ..ports import EventBus, EventLog, LLMProvider
from .engine import EngineConfig, SimulationEngine


def build_engine(
    seed: int = 42,
    content: Optional[Content] = None,
    *,
    llm_provider: Optional[LLMProvider] = None,
    event_log: Optional[EventLog] = None,
    event_bus: Optional[EventBus] = None,
    memory: Optional[Any] = None,
    enable_narrative: bool = True,
    hierarchical_narrative: bool = False,
    cognition_queue_maxlen: int = 256,
) -> SimulationEngine:
    """Build a fully-wired :class:`SimulationEngine`.

    Args:
        seed: Run seed. Determines the entire (reproducible) trajectory.
        content: World content; the default town is loaded when omitted.
        llm_provider: LLM provider; a deterministic :class:`MockLLMProvider` by
            default (so runs are reproducible and need no API key/network).
        event_log: Canonical log; in-memory by default.
        event_bus: Live event bus; in-process by default.
        memory: Memory stream; a mock-embedding stream by default.
        enable_narrative: Whether to run Tier-2 narrative at the narrative hour.
        hierarchical_narrative: Use the agent->group->town narration scheme.
        cognition_queue_maxlen: Bounded cognition-queue capacity (backpressure).

    Returns:
        An unstarted :class:`SimulationEngine` (call ``.run(n)`` / ``.tick()``).
    """
    # NOTE: use explicit ``is not None`` checks, never ``X or default()``. Several
    # of these ports implement ``__len__`` (e.g. an empty event log has len 0),
    # so a freshly-constructed, still-empty adapter is *falsy* and ``or`` would
    # silently discard the caller's instance.
    content = content if content is not None else load_content()
    provider = llm_provider if llm_provider is not None else MockLLMProvider()
    log = event_log if event_log is not None else InMemoryEventLog()
    bus = event_bus if event_bus is not None else InProcessEventBus()
    mem = memory if memory is not None else MemoryStream(MockEmbeddingProvider())
    narrative = NarrativeSystem(provider, content=content)
    queue = CognitionQueue(maxlen=cognition_queue_maxlen)
    planner = PathPlanner(content.nav)

    cfg = EngineConfig(
        seed=seed,
        content=content,
        event_log=log,
        event_bus=bus,
        planner=planner,
        memory=mem,
        narrative=narrative,
        cognition_queue=queue,
        llm_provider=provider,
        enable_narrative=enable_narrative,
        hierarchical_narrative=hierarchical_narrative,
    )
    return SimulationEngine(cfg)
