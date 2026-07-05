"""BT runtime contract tests — the semantics V1 got wrong (F07/F08/F09)."""
from __future__ import annotations

from dataclasses import dataclass, field

from townsim.behavior.core import (
    Branch, Condition, Leaf, Selector, Sequence, Status, UtilitySelector,
)


@dataclass
class FakeCtx:
    trace: list = field(default_factory=list)


class Stub(Leaf):
    def __init__(self, name, statuses):
        super().__init__(name)
        self.statuses = list(statuses)
        self.ticks = 0
        self.resets = 0

    def run(self, ctx):
        self.ticks += 1
        return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]

    def reset(self):
        self.resets += 1


def branch(name, statuses, utility):
    return Branch(name, Stub(name + "-leaf", statuses), utility_fn=lambda ctx: utility)


class TestUtilitySelector:
    def test_orders_children_by_utility(self):
        low = branch("low", [Status.SUCCESS], 0.1)
        high = branch("high", [Status.SUCCESS], 0.9)
        sel = UtilitySelector("sel", [low, high])
        assert sel.tick(FakeCtx()) == Status.SUCCESS
        assert high.children[0].ticks == 1
        assert low.children[0].ticks == 0

    def test_falls_back_on_failure(self):
        """V1's StatefulSelector returned FAILURE outright here (F07)."""
        first = branch("first", [Status.FAILURE], 0.9)
        second = branch("second", [Status.SUCCESS], 0.1)
        sel = UtilitySelector("sel", [first, second])
        assert sel.tick(FakeCtx()) == Status.SUCCESS
        assert second.children[0].ticks == 1

    def test_all_fail_returns_failure(self):
        sel = UtilitySelector("sel", [branch("a", [Status.FAILURE], 0.5),
                                      branch("b", [Status.FAILURE], 0.4)])
        assert sel.tick(FakeCtx()) == Status.FAILURE

    def test_commits_to_running_child(self):
        """Hysteresis: a RUNNING child keeps winning against slightly-higher
        utility competitors."""
        stable = branch("stable", [Status.RUNNING, Status.RUNNING, Status.SUCCESS], 0.5)
        rival = branch("rival", [Status.SUCCESS], 0.55)  # within the 0.15 bonus
        sel = UtilitySelector("sel", [rival, stable])
        # force selection of `stable` by making rival fail once
        rival.children[0].statuses = [Status.FAILURE, Status.SUCCESS]
        assert sel.tick(FakeCtx()) == Status.RUNNING     # rival fails, stable runs
        assert sel.tick(FakeCtx()) == Status.RUNNING     # stable keeps winning (bonus)
        assert sel.tick(FakeCtx()) == Status.SUCCESS
        assert sel._running_child is None

    def test_ties_break_deterministically_by_child_order(self):
        a = branch("a", [Status.SUCCESS], 0.5)
        b = branch("b", [Status.SUCCESS], 0.5)
        sel = UtilitySelector("sel", [a, b])
        sel.tick(FakeCtx())
        assert a.children[0].ticks == 1 and b.children[0].ticks == 0


class TestComposites:
    def test_sequence_stops_at_failure(self):
        first = Stub("a", [Status.SUCCESS])
        second = Stub("b", [Status.FAILURE])
        third = Stub("c", [Status.SUCCESS])
        seq = Sequence("seq", [first, second, third])
        assert seq.tick(FakeCtx()) == Status.FAILURE
        assert third.ticks == 0

    def test_sequence_running_propagates(self):
        seq = Sequence("seq", [Stub("a", [Status.SUCCESS]), Stub("b", [Status.RUNNING])])
        assert seq.tick(FakeCtx()) == Status.RUNNING

    def test_selector_first_non_failure_wins(self):
        sel = Selector("sel", [Stub("a", [Status.FAILURE]), Stub("b", [Status.RUNNING]),
                               Stub("c", [Status.SUCCESS])])
        assert sel.tick(FakeCtx()) == Status.RUNNING

    def test_condition(self):
        ctx = FakeCtx()
        assert Condition("yes", lambda c: True).tick(ctx) == Status.SUCCESS
        assert Condition("no", lambda c: False).tick(ctx) == Status.FAILURE

    def test_failed_branch_leaves_no_trace(self):
        ctx = FakeCtx()
        seq = Sequence("seq", [Stub("a", [Status.SUCCESS]), Stub("b", [Status.FAILURE])])
        seq.tick(ctx)
        assert ctx.trace == []
