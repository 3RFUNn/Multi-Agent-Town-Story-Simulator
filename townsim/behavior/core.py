"""Behavior-tree runtime with utility arbitration.

Semantics (fixing V1's F07/F08/F09/F10):
- Reactive composites: conditions are re-evaluated every tick; RUNNING leaf
  actions are idempotent, so re-reaching them is safe.
- UtilitySelector orders children by utility computed from REAL agent/world
  state, falls back to the next-best child on FAILURE, and commits to a
  RUNNING child with a hysteresis bonus so agents don't oscillate.
- Composites record the active path into ctx.trace for dashboard introspection.
"""
from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from random import Random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from townsim.agents.agent import AgentState
    from townsim.behavior.blackboard import Blackboard
    from townsim.config.models import SimConfig
    from townsim.kernel.clock import SimTime
    from townsim.world.state import WorldState


class Status(enum.Enum):
    SUCCESS = enum.auto()
    FAILURE = enum.auto()
    RUNNING = enum.auto()


@dataclass
class TickContext:
    agent: AgentState
    world: WorldState
    cfg: SimConfig
    now: SimTime
    rng: Random
    bb: Blackboard
    emit: Callable[..., None]          # emit(event_type, **data)
    log: Callable[..., None]           # log(text, importance=0.3, participants=())
    trace: list[str] = field(default_factory=list)


class Node(ABC):
    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def tick(self, ctx: TickContext) -> Status: ...

    def utility(self, ctx: TickContext) -> float:
        return 0.0

    def reset(self) -> None:
        for child in getattr(self, "children", []):
            child.reset()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{type(self).__name__} {self.name!r}>"


class Leaf(Node):
    """Base for leaves: traces itself when it participates in the tick."""

    def tick(self, ctx: TickContext) -> Status:
        status = self.run(ctx)
        if status != Status.FAILURE:
            ctx.trace.append(self.name)
        return status

    @abstractmethod
    def run(self, ctx: TickContext) -> Status: ...


class Condition(Leaf):
    def __init__(self, name: str, predicate: Callable[[TickContext], bool]) -> None:
        super().__init__(name)
        self._predicate = predicate

    def run(self, ctx: TickContext) -> Status:
        return Status.SUCCESS if self._predicate(ctx) else Status.FAILURE


class Sequence(Node):
    """Reactive sequence: re-evaluates children from the start each tick.
    Returns at the first non-SUCCESS child."""

    def __init__(self, name: str, children: list[Node]) -> None:
        super().__init__(name)
        self.children = children

    def tick(self, ctx: TickContext) -> Status:
        mark = len(ctx.trace)
        ctx.trace.append(self.name)
        for child in self.children:
            status = child.tick(ctx)
            if status != Status.SUCCESS:
                if status == Status.FAILURE:
                    del ctx.trace[mark:]  # branch didn't actually run
                return status
        return Status.SUCCESS


class Selector(Node):
    """Reactive priority selector: first child not FAILING wins."""

    def __init__(self, name: str, children: list[Node]) -> None:
        super().__init__(name)
        self.children = children

    def tick(self, ctx: TickContext) -> Status:
        mark = len(ctx.trace)
        ctx.trace.append(self.name)
        for child in self.children:
            status = child.tick(ctx)
            if status != Status.FAILURE:
                return status
        del ctx.trace[mark:]
        return Status.FAILURE


class UtilitySelector(Node):
    """Children tried in descending utility; falls back on FAILURE; commits
    to a RUNNING child (with hysteresis) until it resolves."""

    def __init__(self, name: str, children: list[Node], commitment_bonus: float = 0.15) -> None:
        super().__init__(name)
        self.children = children
        self._running_child: Node | None = None
        self._commitment_bonus = commitment_bonus

    def tick(self, ctx: TickContext) -> Status:
        mark = len(ctx.trace)
        ctx.trace.append(self.name)
        scored = sorted(
            self.children,
            key=lambda c: (
                c.utility(ctx) + (self._commitment_bonus if c is self._running_child else 0.0),
                # deterministic tie-break: earlier child wins
                -self.children.index(c),
            ),
            reverse=True,
        )
        for child in scored:
            if child is not self._running_child:
                child.reset()
            status = child.tick(ctx)
            if status == Status.RUNNING:
                self._running_child = child
                return Status.RUNNING
            if status == Status.SUCCESS:
                self._running_child = None
                return Status.SUCCESS
            # FAILURE: try the next-best child (V1 gave up here — F07).
        self._running_child = None
        del ctx.trace[mark:]
        return Status.FAILURE

    def reset(self) -> None:
        super().reset()
        self._running_child = None


class Branch(Node):
    """Wraps a subtree with an externally supplied utility function, so
    utilities live in one inspectable module instead of inside node classes."""

    def __init__(self, name: str, child: Node,
                 utility_fn: Callable[[TickContext], float] | None = None) -> None:
        super().__init__(name)
        self.children = [child]
        self._utility_fn = utility_fn

    def tick(self, ctx: TickContext) -> Status:
        return self.children[0].tick(ctx)

    def utility(self, ctx: TickContext) -> float:
        if self._utility_fn is not None:
            return self._utility_fn(ctx)
        return self.children[0].utility(ctx)


def guarded_move(name: str, is_there: Callable[[TickContext], bool],
                 do_there: Node, go_there: Node) -> Selector:
    """The location-guard idiom (fixes V1's F05/F11): act only when actually
    at the target, otherwise travel there.

    The travel arm is guarded on NOT being there (R01): if the agent is at
    the location and do_there FAILS (e.g. can't afford it), the whole branch
    must FAIL so the tree can fall back to lower-priority behaviors — without
    the guard, GoTo would return SUCCESS on arrival-already and silently
    swallow the failure."""
    return Selector(name, [
        Sequence(f"{name}: here", [Condition(f"{name}: at location?", is_there), do_there]),
        Sequence(f"{name}: travel", [
            Condition(f"{name}: not there yet?", lambda ctx: not is_there(ctx)),
            go_there,
        ]),
    ])
