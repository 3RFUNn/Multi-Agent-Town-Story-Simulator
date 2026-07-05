"""AgentState: the full runtime state of one agent (composition of components)."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from townsim.agents.components import ActionState, MoveIntent, Needs, Relationship, Wallet
from townsim.config.content import AgentSpec
from townsim.cognition.memory import MemoryStream

if TYPE_CHECKING:
    from townsim.behavior.core import Node

# Utility axes reflection is allowed to adjust (bounded feedback channel).
UTILITY_AXES = ("schedule", "social", "rest", "leisure")
UTILITY_WEIGHT_MIN, UTILITY_WEIGHT_MAX = 0.4, 2.0


@dataclass
class AgentState:
    spec: AgentSpec
    x: int
    y: int
    needs: Needs = field(default_factory=Needs)
    wallet: Wallet = field(default_factory=Wallet)
    relationships: dict[str, Relationship] = field(default_factory=dict)

    # --- FSM ---
    state: str = "idle"                      # idle | moving | doing_action | interacting
    current_activity: str | None = None      # what the schedule says right now
    action: ActionState | None = None        # in-progress timed action
    move_intent: MoveIntent | None = None
    path: list[tuple[int, int]] = field(default_factory=list)
    path_target: tuple[int, int] | None = None
    path_goal_key: str | None = None
    path_retries: int = 0
    path_failed: bool = False
    conversation_id: str | None = None
    interacting_with: str | None = None
    social_target: str | None = None

    # --- cognition ---
    memory: MemoryStream = field(default_factory=MemoryStream)
    mood: str = "settled"
    utility_weights: dict[str, float] = field(
        default_factory=lambda: {axis: 1.0 for axis in UTILITY_AXES})
    schedule_overrides: dict[tuple[int, int, int], str] = field(default_factory=dict)
    daily_dialogues_used: int = 0
    last_diary: dict | None = None           # {"day": int, "text": str}

    # --- presentation ---
    current_goal: str = "Waking up"
    current_action: str = "Starting the day"
    recent_log: deque = field(default_factory=lambda: deque(maxlen=50))
    bt_path: list[str] = field(default_factory=list)
    behavior_tree: "Node | None" = None
    _last_log_text: str = ""

    @property
    def id(self) -> str:
        return self.spec.id

    @property
    def pos(self) -> tuple[int, int]:
        return (self.x, self.y)

    def relationship_with(self, other_id: str) -> Relationship:
        if other_id not in self.relationships:
            self.relationships[other_id] = Relationship()
        return self.relationships[other_id]

    def apply_goal_adjustment(self, axis: str, delta: float) -> bool:
        """Bounded feedback: clamp both the delta and the resulting weight."""
        if axis not in self.utility_weights:
            return False
        delta = max(-0.2, min(0.2, delta))
        new = self.utility_weights[axis] + delta
        self.utility_weights[axis] = max(UTILITY_WEIGHT_MIN, min(UTILITY_WEIGHT_MAX, new))
        return True

    def clear_transient(self) -> None:
        """Reset movement/interaction transients (used by teardown paths)."""
        self.move_intent = None
        self.path = []
        self.path_target = None
        self.path_goal_key = None
        self.path_retries = 0
        self.path_failed = False
        self.conversation_id = None
        self.interacting_with = None
        self.social_target = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.spec.name, "icon": self.spec.icon,
            "color": self.spec.color, "x": self.x, "y": self.y,
            "state": self.state, "activity": self.current_activity,
            "goal": self.current_goal, "action": self.current_action,
            "needs": self.needs.to_dict(), "money": round(self.wallet.money, 2),
            "interacting_with": self.interacting_with, "mood": self.mood,
            "bt_path": self.bt_path,
            "personality": list(self.spec.personality),
        }
