"""Bounded reflection: the ONLY channel through which LLM cognition may
influence behavior. Everything is typed, clamped, and validated twice —
once by Pydantic at parse time, once by the kernel before application."""
from __future__ import annotations

from pydantic import BaseModel, Field

from townsim.config.content import ACTIVITY_DATA


class GoalAdjustment(BaseModel):
    goal: str
    delta: float = Field(ge=-0.2, le=0.2)


class ScheduleProposal(BaseModel):
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=0, le=23)
    activity: str


class ReflectionResult(BaseModel):
    mood: str = Field(min_length=1, max_length=40)
    insights: list[str] = Field(default_factory=list, max_length=3)
    goal_adjustments: list[GoalAdjustment] = Field(default_factory=list, max_length=3)
    schedule_proposals: list[ScheduleProposal] = Field(default_factory=list, max_length=2)

    def sanitized(self, valid_axes: tuple[str, ...]) -> ReflectionResult:
        """Kernel-side guard: never trust even validated output blindly."""
        return ReflectionResult(
            mood=self.mood.strip()[:40] or "settled",
            insights=[i.strip()[:200] for i in self.insights if i.strip()][:3],
            goal_adjustments=[a for a in self.goal_adjustments if a.goal in valid_axes][:3],
            schedule_proposals=[
                p for p in self.schedule_proposals
                if p.activity in ACTIVITY_DATA and p.start_hour != p.end_hour
            ][:2],
        )
