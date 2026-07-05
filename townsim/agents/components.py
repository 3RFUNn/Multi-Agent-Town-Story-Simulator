"""Agent component dataclasses (data only — systems own the logic).

Naming fix vs V1: the need formerly called 'energy' actually measured
tiredness; it is now 'fatigue' (0 = fresh, 100 = exhausted).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Needs:
    hunger: float = 20.0
    social: float = 20.0
    fatigue: float = 20.0

    def clamp(self) -> None:
        self.hunger = min(100.0, max(0.0, self.hunger))
        self.social = min(100.0, max(0.0, self.social))
        self.fatigue = min(100.0, max(0.0, self.fatigue))

    def to_dict(self) -> dict:
        return {"hunger": round(self.hunger, 1), "social": round(self.social, 1),
                "fatigue": round(self.fatigue, 1)}


@dataclass
class Wallet:
    money: float = 0.0
    # (day_index, activity, start_hour) slots already paid for — F13: charge once.
    paid_slots: set[tuple[int, str, int]] = field(default_factory=set)


@dataclass
class ActionState:
    """An in-progress timed action (work, meal, sleep, rest, ...)."""
    activity: str
    kind: str
    until_tick: int
    started_tick: int
    earned: float = 0.0        # wages accrued during this action


@dataclass
class MoveIntent:
    """Where the behavior tree wants the agent to go; the movement system
    resolves it to a concrete cell and path."""
    kind: str                  # "place" | "agent" | "home"
    key: str                   # place key / agent id / agent's own id for home
    reason: str = ""


@dataclass
class Relationship:
    kind: str = "acquaintance"
    affinity: float = 50.0     # 0..100 long-term liking
    familiarity: float = 0.0   # 0..100 grows with interactions
    valence: float = 0.0       # -1..1 tone of the last interaction

    def to_dict(self) -> dict:
        return {"type": self.kind, "affinity": round(self.affinity, 1),
                "familiarity": round(self.familiarity, 1), "valence": round(self.valence, 2)}
