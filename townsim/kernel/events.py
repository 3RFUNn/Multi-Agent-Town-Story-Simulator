"""Events (facts that happened) and intents (requests to change state).

Events are the simulation's ground truth: appended to the journal, broadcast
to the dashboard, and consumed by the narrative layer. Intents are how the
async cognition side feeds back into the kernel — applied only at tick
boundaries, never mid-tick.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Event types with deterministic content (participate in the replay hash).
BEHAVIORAL = {
    "sim_started", "day_started", "activity_started", "activity_ended",
    "agent_moved_to", "path_failed", "conversation_started", "conversation_ended",
    "meal_eaten", "rest_taken", "sleep_started", "wage_paid", "cost_paid",
    "log", "relationship_changed", "schedule_override_applied",
}
# Narrative/LLM event types (excluded from the determinism hash — their text
# depends on the provider).
NARRATIVE = {"diary_written", "story_written", "reflection_applied", "dialogue_rendered"}


@dataclass(frozen=True)
class Event:
    tick: int
    day_index: int
    type: str
    agent_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "tick": self.tick, "day": self.day_index, "type": self.type,
            "agent": self.agent_id, "data": self.data,
        }


@dataclass(frozen=True)
class Intent:
    """Typed, validated feedback from async cognition into the kernel."""
    kind: str          # "reflection" | "story_ready" | "diary_ready" | "dialogue_ready"
    agent_id: str | None
    payload: dict[str, Any]
