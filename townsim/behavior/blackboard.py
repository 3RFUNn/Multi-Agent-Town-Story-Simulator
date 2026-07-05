"""Three-scope blackboard: AGENT (private), GROUP (interaction group), WORLD.

Replaces V1's ad-hoc attributes stuck onto Agent (rest_location, eat_ticks)
and the shared-dict mutation bugs (per-agent data written into the global
ACTIVITY_DATA — F20).
"""
from __future__ import annotations

import enum
from typing import Any


class Scope(enum.Enum):
    AGENT = "agent"
    GROUP = "group"
    WORLD = "world"


class Blackboard:
    def __init__(self) -> None:
        self._data: dict[tuple[Scope, str, str], Any] = {}
        self._group_of: dict[str, str] = {}

    def _key(self, scope: Scope, owner: str, name: str) -> tuple[Scope, str, str]:
        if scope is Scope.WORLD:
            return (scope, "*", name)
        if scope is Scope.GROUP:
            return (scope, self._group_of.get(owner, owner), name)
        return (scope, owner, name)

    def get(self, scope: Scope, owner: str, name: str, default: Any = None) -> Any:
        return self._data.get(self._key(scope, owner, name), default)

    def set(self, scope: Scope, owner: str, name: str, value: Any) -> None:
        self._data[self._key(scope, owner, name)] = value

    def delete(self, scope: Scope, owner: str, name: str) -> None:
        self._data.pop(self._key(scope, owner, name), None)

    def clear_agent(self, agent_id: str) -> None:
        self._data = {k: v for k, v in self._data.items()
                      if not (k[0] is Scope.AGENT and k[1] == agent_id)}

    def join_group(self, agent_id: str, group_id: str) -> None:
        self._group_of[agent_id] = group_id

    def leave_group(self, agent_id: str) -> None:
        self._group_of.pop(agent_id, None)
