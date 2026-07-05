"""Bounded feedback channel tests: reflection can nudge, never command."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from townsim.agents.agent import UTILITY_AXES, AgentState
from townsim.cognition.reflection import GoalAdjustment, ReflectionResult, ScheduleProposal
from townsim.config.content import AGENTS


def make_agent() -> AgentState:
    spec = AGENTS[0]
    return AgentState(spec=spec, x=spec.home_pos[0], y=spec.home_pos[1])


class TestSchemaBounds:
    def test_delta_out_of_bounds_rejected(self):
        with pytest.raises(ValidationError):
            GoalAdjustment(goal="social", delta=0.5)

    def test_too_many_adjustments_rejected(self):
        with pytest.raises(ValidationError):
            ReflectionResult(mood="fine", goal_adjustments=[
                GoalAdjustment(goal="social", delta=0.1)] * 4)


class TestSanitization:
    def test_unknown_axis_dropped(self):
        result = ReflectionResult(mood="fine", goal_adjustments=[
            GoalAdjustment(goal="become_mayor", delta=0.2),
            GoalAdjustment(goal="social", delta=0.1),
        ]).sanitized(UTILITY_AXES)
        assert [a.goal for a in result.goal_adjustments] == ["social"]

    def test_unknown_activity_dropped(self):
        result = ReflectionResult(mood="fine", schedule_proposals=[
            ScheduleProposal(start_hour=20, end_hour=22, activity="rob_the_bank"),
            ScheduleProposal(start_hour=20, end_hour=22, activity="socialize_at_park"),
        ]).sanitized(UTILITY_AXES)
        assert [p.activity for p in result.schedule_proposals] == ["socialize_at_park"]

    def test_degenerate_window_dropped(self):
        result = ReflectionResult(mood="fine", schedule_proposals=[
            ScheduleProposal(start_hour=9, end_hour=9, activity="socialize_at_park"),
        ]).sanitized(UTILITY_AXES)
        assert result.schedule_proposals == []


class TestWeightClamping:
    def test_weights_stay_in_bounds(self):
        agent = make_agent()
        for _ in range(50):
            agent.apply_goal_adjustment("social", 0.2)
        assert agent.utility_weights["social"] == 2.0
        for _ in range(50):
            agent.apply_goal_adjustment("social", -0.2)
        assert agent.utility_weights["social"] == 0.4

    def test_oversized_delta_clamped(self):
        agent = make_agent()
        agent.apply_goal_adjustment("social", 5.0)
        assert agent.utility_weights["social"] == 1.2

    def test_unknown_axis_returns_false(self):
        agent = make_agent()
        assert agent.apply_goal_adjustment("nonsense", 0.1) is False
