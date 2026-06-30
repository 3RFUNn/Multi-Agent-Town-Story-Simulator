"""Domain enumerations and the canonical event-type vocabulary.

Event types are plain ``str`` constants (not ``enum.Enum``) so that event
payloads stay trivially JSON-serialisable for the append-only log and the wire
protocol, while ``KNOWN_EVENT_TYPES`` still allows validation.
"""

from __future__ import annotations

from typing import FrozenSet


class AgentState:
    """The agent's coarse FSM state (mirrors the prototype's states)."""

    IDLE = "idle"
    MOVING = "moving"
    DOING_ACTION = "doing_action"
    INTERACTING = "interacting"

    ALL: FrozenSet[str] = frozenset({IDLE, MOVING, DOING_ACTION, INTERACTING})


class Need:
    """The agent need axes (0 = satisfied, 100 = critical)."""

    HUNGER = "hunger"
    SOCIAL = "social"
    ENERGY = "energy"

    ALL = (HUNGER, SOCIAL, ENERGY)


class EventType:
    """Canonical domain event vocabulary (the narrative substrate)."""

    SIM_STARTED = "sim_started"
    TICK_COMPLETED = "tick_completed"
    DAY_ROLLOVER = "day_rollover"

    AGENT_SPAWNED = "agent_spawned"
    DECISION_MADE = "decision_made"
    AGENT_MOVED = "agent_moved"
    ACTIVITY_STARTED = "activity_started"
    ACTIVITY_FINISHED = "activity_finished"
    ATE = "ate"
    RESTED = "rested"
    WORKED = "worked"
    NEED_CRITICAL = "need_critical"
    INTERACTION_STARTED = "interaction_started"
    INTERACTION_FINISHED = "interaction_finished"
    MONEY_CHANGED = "money_changed"

    # Authoring / mixed-initiative (the game's "Nudge API" + drama director).
    NUDGE_APPLIED = "nudge_applied"
    REFLECTION_CREATED = "reflection_created"

    # Tier-2 narrative (post-hoc; never feeds back into Tier-1).
    DIARY_WRITTEN = "diary_written"
    STORY_COMPILED = "story_compiled"


KNOWN_EVENT_TYPES: FrozenSet[str] = frozenset(
    v for k, v in vars(EventType).items() if not k.startswith("_") and isinstance(v, str)
)
