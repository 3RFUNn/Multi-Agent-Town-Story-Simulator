"""Agent domain: immutable definitions + mutable runtime aggregate.

``AgentDef`` is the data-driven *definition* loaded from content (replacing the
hardcoded ``AGENT_CONFIG``/``PERSONALITY_TRAITS``/``RELATIONSHIPS`` dicts).
``Agent`` is the mutable runtime aggregate whose observable fields contribute to
the per-tick ``state_hash``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .enums import AgentState, Need


@dataclass(frozen=True)
class Relationship:
    """A directed social tie (``affinity`` 0-100)."""

    type: str
    affinity: int

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "affinity": self.affinity}


@dataclass(frozen=True)
class AgentDef:
    """Immutable, data-driven definition of an agent (from content)."""

    id: str
    name: str
    icon: str
    color: str
    home_pos: Tuple[int, int]
    personality: Tuple[str, ...]
    traits: Dict[str, float]
    schedule_template: str
    work_location: Optional[str]
    background: str = ""
    starting_money_range: Tuple[int, int] = (100, 150)

    def trait(self, name: str, default: float = 1.0) -> float:
        return float(self.traits.get(name, default))

    def has_personality(self, name: str) -> bool:
        return name in self.personality


class Agent:
    """Mutable runtime state for one agent.

    The constructor takes an :class:`AgentDef` and the resolved initial
    relationships/money so that construction itself is deterministic (money is
    drawn by the caller from a seeded RNG, never from the global generator).
    """

    __slots__ = (
        "defn", "x", "y", "money", "needs", "state", "current_activity",
        "current_goal", "current_action", "destination_name", "path",
        "path_index", "action_duration", "interacting_with", "relationships",
        "rest_ticks", "eat_ticks", "rest_location",
    )

    def __init__(
        self,
        defn: AgentDef,
        money: float,
        relationships: Optional[Dict[str, Relationship]] = None,
    ) -> None:
        self.defn = defn
        self.x, self.y = defn.home_pos
        self.money = float(money)
        self.needs: Dict[str, float] = {Need.HUNGER: 0.0, Need.SOCIAL: 0.0, Need.ENERGY: 0.0}
        self.state = AgentState.IDLE
        self.current_activity: Optional[str] = None
        self.current_goal = "Initializing..."
        self.current_action = "Thinking..."
        self.destination_name: Optional[str] = None
        self.path: List[Tuple[int, int]] = []
        self.path_index = 0
        self.action_duration = 0
        self.interacting_with: Optional[str] = None
        self.relationships: Dict[str, Relationship] = dict(relationships or {})
        self.rest_ticks = 0
        self.eat_ticks = 0
        self.rest_location: Optional[str] = None

    # --- Convenience accessors ------------------------------------------------

    @property
    def id(self) -> str:
        return self.defn.id

    @property
    def name(self) -> str:
        return self.defn.name

    @property
    def pos(self) -> Tuple[int, int]:
        return (self.x, self.y)

    def has_personality(self, name: str) -> bool:
        return self.defn.has_personality(name)

    def trait(self, name: str, default: float = 1.0) -> float:
        return self.defn.trait(name, default)

    def get_relationship(self, other_id: str) -> Optional[Relationship]:
        return self.relationships.get(other_id)

    def set_affinity(self, other_id: str, affinity: int) -> None:
        rel = self.relationships.get(other_id)
        affinity = max(0, min(100, int(affinity)))
        if rel is None:
            self.relationships[other_id] = Relationship("acquaintance", affinity)
        else:
            self.relationships[other_id] = Relationship(rel.type, affinity)

    # --- Serialisation --------------------------------------------------------

    def to_canonical(self) -> Dict[str, Any]:
        """The hash-relevant observable state of the agent."""
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "money": self.money,
            "needs": self.needs,
            "state": self.state,
            "current_activity": self.current_activity,
            "destination_name": self.destination_name,
            "path": self.path,
            "path_index": self.path_index,
            "action_duration": self.action_duration,
            "interacting_with": self.interacting_with,
            "relationships": {k: v.to_dict() for k, v in self.relationships.items()},
        }

    def to_view(self) -> Dict[str, Any]:
        """A richer dict for the client/wire (includes display + log fields)."""
        d = self.to_canonical()
        d.update(
            {
                "name": self.name,
                "icon": self.defn.icon,
                "color": self.defn.color,
                "current_goal": self.current_goal,
                "current_action": self.current_action,
                "personality": list(self.defn.personality),
            }
        )
        return d

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Agent {self.id} @({self.x},{self.y}) {self.state} ${self.money:.1f}>"
