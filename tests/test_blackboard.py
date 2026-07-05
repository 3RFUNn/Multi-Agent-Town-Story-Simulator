from __future__ import annotations

from townsim.behavior.blackboard import Blackboard, Scope


class TestScopes:
    def test_agent_scope_is_private(self):
        bb = Blackboard()
        bb.set(Scope.AGENT, "alex", "rest_spot", "central_park")
        bb.set(Scope.AGENT, "bella", "rest_spot", "downtown_cafe")
        assert bb.get(Scope.AGENT, "alex", "rest_spot") == "central_park"
        assert bb.get(Scope.AGENT, "bella", "rest_spot") == "downtown_cafe"

    def test_world_scope_is_shared(self):
        bb = Blackboard()
        bb.set(Scope.WORLD, "anyone", "weather", "rain")
        assert bb.get(Scope.WORLD, "someone_else", "weather") == "rain"

    def test_group_scope_shared_within_group_only(self):
        bb = Blackboard()
        bb.join_group("alex", "c1")
        bb.join_group("bella", "c1")
        bb.set(Scope.GROUP, "alex", "topic", "the weather")
        assert bb.get(Scope.GROUP, "bella", "topic") == "the weather"
        assert bb.get(Scope.GROUP, "charlie", "topic") is None
        bb.leave_group("bella")
        assert bb.get(Scope.GROUP, "bella", "topic") is None

    def test_clear_agent(self):
        bb = Blackboard()
        bb.set(Scope.AGENT, "alex", "a", 1)
        bb.set(Scope.WORLD, "alex", "b", 2)
        bb.clear_agent("alex")
        assert bb.get(Scope.AGENT, "alex", "a") is None
        assert bb.get(Scope.WORLD, "alex", "b") == 2
