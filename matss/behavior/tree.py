"""The deterministic Behavior-Tree engine (Tier-1 control).

This is the reproducible port of the legacy prototype ``behavior_tree.py``.
The node graph is the agent's reactive decision policy: a priority
:class:`Selector` of emergency reactions over a :class:`StatefulSelector` of
deliberative routines.

Two properties distinguish this port from the prototype:

* **Determinism** — nodes never touch the global ``random`` module or the wall
  clock. All randomness flows through :class:`~matss.runtime.DecisionContext`
  RNG sub-streams, and all side effects flow through ``ctx.emit`` / ``ctx.observe``.
* **Real lookahead (report contribution C2)** — the prototype's
  ``StatefulSelector`` scored children with a hardcoded substring stub
  (``simulate_child``). Here the selector scores each child by calling the
  child's *own* :meth:`Node.simulate`, so the planning heuristic reflects each
  branch's genuine predicted outcome instead of a fiction.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..runtime import DecisionContext
    from ..domain.agent import Agent


class Status(enum.Enum):
    """The result of ticking a behavior-tree node."""

    SUCCESS = 1
    FAILURE = 2
    RUNNING = 3


class SimulationSummary:
    """A predicted post-action world snapshot used by the planning heuristic.

    Attributes:
        final_needs: Predicted need levels keyed by need name (0 satisfied,
            100 critical).
        final_money: Predicted agent money after the action.
    """

    __slots__ = ("final_needs", "final_money")

    def __init__(self, final_needs: Dict[str, float], final_money: float) -> None:
        self.final_needs: Dict[str, float] = dict(final_needs)
        self.final_money: float = float(final_money)

    def copy(self) -> "SimulationSummary":
        """Return a deep-enough copy (needs dict is duplicated)."""
        return SimulationSummary(dict(self.final_needs), self.final_money)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"SimulationSummary(needs={self.final_needs}, money={self.final_money})"


def heuristic_function(
    agent: "Agent",
    initial: SimulationSummary,
    final: SimulationSummary,
) -> float:
    """Score the desirability of a predicted outcome.

    Ported faithfully from the prototype: each *reduction* in a need is rewarded
    (hunger/energy weighted 1.5, everything else 1.0), money gain is rewarded at
    0.5, and the raw score is squashed to ``(0, 1]`` so larger is always better.

    Args:
        agent: The deciding agent (unused by the formula but kept for parity and
            future trait-aware scoring).
        initial: The summary before the action.
        final: The summary the action is predicted to produce.

    Returns:
        A normalized desirability in ``(0, 1]``; higher is more desirable.
    """
    score = 0.0
    for need, initial_value in initial.final_needs.items():
        final_value = final.final_needs.get(need, initial_value)
        change = initial_value - final_value
        weight = 1.5 if need in ("hunger", "energy") else 1.0
        score += change * weight

    money_change = final.final_money - initial.final_money
    score += money_change * 0.5

    return 1.0 / (1.0 + max(0.0, -score))


class Node:
    """Base class for every behavior-tree node.

    Subclasses override :meth:`tick` (and optionally :meth:`simulate`). The base
    :meth:`simulate` is the identity, which is the correct default for condition
    nodes and any action whose outcome the planner need not predict.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.is_running = False

    def tick(self, ctx: "DecisionContext") -> Status:
        """Advance the node by one simulation tick.

        Args:
            ctx: The decision sandbox bound to the current agent/world/tick.

        Returns:
            The node's status for this tick.
        """
        raise NotImplementedError

    def simulate(self, ctx: "DecisionContext", summary: SimulationSummary) -> SimulationSummary:
        """Predict this node's outcome for planning lookahead.

        The default is the identity (no predicted change), which condition nodes
        rely on. Action nodes override this to provide a real prediction.

        Args:
            ctx: The decision sandbox.
            summary: The predicted state before this node runs.

        Returns:
            The predicted state after this node runs.
        """
        return summary

    def reset(self) -> None:
        """Clear transient running state, recursing into children if any."""
        self.is_running = False
        children = getattr(self, "children", None)
        if children:
            for child in children:
                child.reset()


class Selector(Node):
    """Stateless priority fallback.

    Ticks children in order and returns the first non-``FAILURE`` result,
    re-evaluating from the first child every tick. This is what makes the root
    reactive: a higher-priority emergency always pre-empts lower branches.
    """

    def __init__(self, name: str, children: Optional[List[Node]] = None) -> None:
        super().__init__(name)
        self.children: List[Node] = list(children) if children else []

    def tick(self, ctx: "DecisionContext") -> Status:
        for child in self.children:
            status = child.tick(ctx)
            if status != Status.FAILURE:
                return status
        return Status.FAILURE

    def simulate(self, ctx: "DecisionContext", summary: SimulationSummary) -> SimulationSummary:
        # Mirror tick semantics: the first child is the predicted branch.
        for child in self.children:
            return child.simulate(ctx, summary)
        return summary


class Sequence(Node):
    """Ordered conjunction.

    Ticks children left to right. Fails as soon as a child fails, stays
    ``RUNNING`` while a child is running, and succeeds only when every child has
    succeeded. Tracks the current child across ticks so a running child resumes.
    """

    def __init__(self, name: str, children: Optional[List[Node]] = None) -> None:
        super().__init__(name)
        self.children: List[Node] = list(children) if children else []
        self.current_child_index = 0

    def tick(self, ctx: "DecisionContext") -> Status:
        while self.current_child_index < len(self.children):
            child = self.children[self.current_child_index]
            status = child.tick(ctx)

            if status == Status.SUCCESS:
                child.reset()
                self.current_child_index += 1
                continue
            if status == Status.FAILURE:
                self.reset()
                return Status.FAILURE
            # RUNNING: hold position for the next tick.
            self.is_running = True
            return Status.RUNNING

        self.reset()
        return Status.SUCCESS

    def simulate(self, ctx: "DecisionContext", summary: SimulationSummary) -> SimulationSummary:
        current = summary
        for child in self.children:
            current = child.simulate(ctx, current)
        return current

    def reset(self) -> None:
        super().reset()
        self.current_child_index = 0


class StatefulSelector(Node):
    """Deliberative selector with real, heuristic-driven lookahead.

    Unlike :class:`Selector`, this node *plans*: on each fresh decision it asks
    every child to predict its own outcome via :meth:`Node.simulate`, scores the
    predictions with :func:`heuristic_function`, commits to the highest-scoring
    child, and ticks it until it returns a non-``RUNNING`` status.

    This fixes the prototype's stubbed ``simulate_child`` (report contribution
    C2): the score now comes from each branch's genuine predicted effect, not a
    hardcoded substring table.
    """

    def __init__(self, name: str, children: Optional[List[Node]] = None) -> None:
        super().__init__(name)
        self.children: List[Node] = list(children) if children else []
        self.selected_child: Optional[Node] = None

    def _initial_summary(self, ctx: "DecisionContext") -> SimulationSummary:
        return SimulationSummary(dict(ctx.agent.needs), ctx.agent.money)

    def select_best_child(self, ctx: "DecisionContext") -> Optional[Node]:
        """Pick the child whose real :meth:`Node.simulate` scores highest.

        Ties resolve to the earlier child (stable priority order), keeping
        selection fully deterministic.

        Args:
            ctx: The decision sandbox.

        Returns:
            The best child, or ``None`` when this selector has no children.
        """
        initial = self._initial_summary(ctx)
        best_child: Optional[Node] = None
        best_score = -1.0
        for child in self.children:
            predicted = child.simulate(ctx, initial.copy())
            score = heuristic_function(ctx.agent, initial, predicted)
            if score > best_score:
                best_score = score
                best_child = child
        return best_child

    def tick(self, ctx: "DecisionContext") -> Status:
        if self.selected_child is not None and self.selected_child.is_running:
            status = self.selected_child.tick(ctx)
        else:
            self.selected_child = self.select_best_child(ctx)
            if self.selected_child is None:
                return Status.FAILURE
            status = self.selected_child.tick(ctx)

        if status != Status.RUNNING:
            self.selected_child.reset()
            self.selected_child = None
            self.is_running = False
        else:
            self.is_running = True
        return status

    def simulate(self, ctx: "DecisionContext", summary: SimulationSummary) -> SimulationSummary:
        best_child = self.select_best_child(ctx)
        if best_child is not None:
            return best_child.simulate(ctx, summary)
        return summary

    def reset(self) -> None:
        super().reset()
        self.selected_child = None
