"""Event log: the append-only canonical source of truth + CQRS read models.

This package implements MATSS v2's event-sourcing substrate:

* the live :class:`InProcessEventBus` (publish/subscribe fan-out),
* durable append-only logs — :class:`InMemoryEventLog` (with an integrity hash
  chain) and the Kafka-shaped :class:`JsonlEventLog`,
* and the read side: pure replay helpers (:func:`replay_state_hashes`,
  :func:`reconstruct_world_canonical`) plus incremental projections
  (:class:`LiveWorldReadModel`, :class:`NarrativeReadModel`).

Write once to the log; project many views from it.
"""

from .bus import InProcessEventBus
from .jsonl_log import JsonlEventLog
from .memory_log import InMemoryEventLog
from .projections import (
    LiveWorldReadModel,
    NarrativeReadModel,
    reconstruct_world_canonical,
    replay_state_hashes,
)

__all__ = [
    "InProcessEventBus",
    "InMemoryEventLog",
    "JsonlEventLog",
    "replay_state_hashes",
    "reconstruct_world_canonical",
    "LiveWorldReadModel",
    "NarrativeReadModel",
]
