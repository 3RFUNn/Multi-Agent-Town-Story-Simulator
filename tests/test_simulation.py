"""Integration tests: multi-day headless runs on the fake provider.

These are the tests that would have caught most of V1's audited defects:
economy double-charging (F13), starvation deadlock (F31), memory growth
(F18), lost stories (F04), sim-killing narrative errors (F01).
"""
from __future__ import annotations

from collections import Counter

from townsim.cognition.narrative import NarrativeCoordinator
from townsim.kernel.kernel import Kernel
from townsim.kernel.loop import run_kernel
from townsim.llm.gateway import LLMGateway
from townsim.llm.providers import FakeProvider
from townsim.llm.templates import PromptLibrary


def make_kernel(cfg, with_narrative=True) -> Kernel:
    narrative = None
    if with_narrative:
        gateway = LLMGateway(FakeProvider())
        narrative = NarrativeCoordinator(gateway, PromptLibrary(cfg.paths.prompts_dir), cfg)
    return Kernel(cfg, narrative=narrative)


def step_days(kernel: Kernel, days: int) -> list:
    events = []
    while kernel.now().day_index < days:
        events.extend(kernel.step())
    return events


class TestDeterminism:
    def test_same_seed_same_hash(self, cfg):
        k1 = make_kernel(cfg, with_narrative=False)
        k2 = make_kernel(cfg, with_narrative=False)
        try:  # R26: close journals even on assertion failure (Windows tmp cleanup)
            step_days(k1, 1)
            step_days(k2, 1)
            assert k1.journal.determinism_hash() == k2.journal.determinism_hash()
        finally:
            k1.close()
            k2.close()

    def test_different_seed_different_hash(self, cfg):
        k1 = make_kernel(cfg, with_narrative=False)
        cfg.kernel.seed = cfg.kernel.seed + 1
        k2 = make_kernel(cfg, with_narrative=False)
        try:
            step_days(k1, 1)
            step_days(k2, 1)
            assert k1.journal.determinism_hash() != k2.journal.determinism_hash()
        finally:
            k1.close()
            k2.close()

    async def test_strict_mode_full_loop_reproducible(self, cfg):
        hashes = []
        for _ in range(2):
            kernel = make_kernel(cfg, with_narrative=True)
            kernel.narrative.start()
            try:
                await run_kernel(kernel, max_days=1)
                await kernel.narrative.stop()
            finally:
                kernel.close()   # R26: close journals on ANY exit path
            hashes.append(kernel.journal.determinism_hash())
        assert hashes[0] == hashes[1]


class TestTwoDayRun:
    async def test_full_pipeline(self, cfg):
        kernel = make_kernel(cfg, with_narrative=True)
        kernel.narrative.start()
        try:
            await run_kernel(kernel, max_days=2)
            await kernel.narrative.stop()
        finally:
            kernel.close()   # R26: close journals on ANY exit path

        world = kernel.world
        # Stories: one per completed day (V1 lost every one of these — F04).
        assert len(world.stories) == 2
        # Diaries on disk, namespaced per run (F24).
        diaries = sorted((kernel.run_dir / "diaries").rglob("*.txt"))
        assert len(diaries) == 2 * len(world.agents)
        # Every agent reflected: mood set and weights still within bounds.
        for agent in world.agents_sorted():
            assert agent.mood
            for weight in agent.utility_weights.values():
                assert 0.4 <= weight <= 2.0
        # Nobody is bankrupted by double-charging (F13) or pinned at
        # max hunger by priority inversion (F31).
        for agent in world.agents_sorted():
            assert agent.wallet.money > -1e-6, f"{agent.id} went broke"
            assert agent.needs.hunger < 95, f"{agent.id} is starving"
        # Memory stays bounded (F18): compaction keeps only recent days.
        for agent in world.agents_sorted():
            event_days = {e.day_index for e in agent.memory.entries if e.kind == "event"}
            assert all(d >= 2 - cfg.memory.compact_after_days for d in event_days)

    async def test_charges_once_per_slot(self, cfg):
        from townsim.kernel.journal import read_journal

        kernel = make_kernel(cfg, with_narrative=True)
        kernel.narrative.start()
        try:
            await run_kernel(kernel, max_days=2)
            await kernel.narrative.stop()
        finally:
            kernel.close()   # R26: close journals on ANY exit path
        _, events = read_journal(kernel.run_dir / "journal.jsonl")
        charges = Counter()
        for event in events:
            if event["type"] == "cost_paid" and event["data"]["activity"] != "eat_at_cafe":
                charges[(event["agent"], event["day"], event["data"]["activity"])] += 1
        assert charges, "expected at least one paid activity"
        multi = {k: v for k, v in charges.items() if v > 1}
        assert not multi, f"double-charged slots (F13 regression): {multi}"

    async def test_conversations_are_adjacent_and_symmetric(self, cfg):
        from townsim.kernel.journal import read_journal

        kernel = make_kernel(cfg, with_narrative=True)
        kernel.narrative.start()
        try:
            await run_kernel(kernel, max_days=2)
            await kernel.narrative.stop()
        finally:
            kernel.close()   # R26: close journals on ANY exit path
        _, events = read_journal(kernel.run_dir / "journal.jsonl")
        started = [e for e in events if e["type"] == "conversation_started"]
        ended = [e for e in events if e["type"] == "conversation_ended"]
        assert len(started) == len(ended), "every conversation must tear down (F15)"
        # After the run, nobody is left frozen in an interaction.
        for agent in kernel.world.agents_sorted():
            assert agent.state != "interacting"
            assert agent.interacting_with is None
