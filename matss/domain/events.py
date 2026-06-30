"""The :class:`Event` — the atomic unit of the event-sourced narrative substrate.

Every meaningful thing that happens in Tier-1 is recorded as an immutable
``Event`` appended to the log. The log (not any in-memory dict) is the canonical
source of truth: world state is a *projection* of the event stream, and the
Tier-2 narrator sifts the same stream. Events are JSON-serialisable end to end.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, Optional

# Bumped when the on-the-wire payload shape changes; consumers may upcast.
PAYLOAD_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Event:
    """An immutable domain event.

    Attributes
    ----------
    type:
        One of :data:`matss.domain.enums.KNOWN_EVENT_TYPES`.
    tick:
        Monotonic simulation tick index at which the event occurred.
    sim_minute:
        Minutes of simulated time elapsed since the run started (deterministic
        clock; independent of wall-clock time).
    day_index:
        0-based simulated day.
    day_of_week:
        e.g. ``"Monday"`` (derived from ``day_index``).
    agent_id:
        The agent the event concerns, or ``None`` for world-level events.
    payload:
        Arbitrary JSON-serialisable detail.
    seq:
        Global append sequence number, assigned by the event log. ``-1`` means
        "not yet appended".
    schema_version:
        Payload schema version for forward-compatible replay.
    """

    type: str
    tick: int
    sim_minute: int
    day_index: int
    day_of_week: str
    agent_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    seq: int = -1
    schema_version: int = PAYLOAD_SCHEMA_VERSION

    def with_seq(self, seq: int) -> "Event":
        """Return a copy stamped with its global sequence number."""
        return replace(self, seq=seq)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "type": self.type,
            "tick": self.tick,
            "sim_minute": self.sim_minute,
            "day_index": self.day_index,
            "day_of_week": self.day_of_week,
            "agent_id": self.agent_id,
            "payload": self.payload,
            "schema_version": self.schema_version,
        }

    # The hash/canonical form deliberately EXCLUDES ``seq`` so that the content
    # identity of an event is independent of its position, while the log's
    # integrity chain (which includes order) is handled separately.
    def to_canonical(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "tick": self.tick,
            "sim_minute": self.sim_minute,
            "day_index": self.day_index,
            "day_of_week": self.day_of_week,
            "agent_id": self.agent_id,
            "payload": self.payload,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Event":
        return cls(
            type=d["type"],
            tick=d["tick"],
            sim_minute=d["sim_minute"],
            day_index=d["day_index"],
            day_of_week=d["day_of_week"],
            agent_id=d.get("agent_id"),
            payload=d.get("payload", {}) or {},
            seq=d.get("seq", -1),
            schema_version=d.get("schema_version", PAYLOAD_SCHEMA_VERSION),
        )
