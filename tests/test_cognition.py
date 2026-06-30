"""Tests for the cognition subsystem: narrative, queue, and judge.

These tests use a local, self-contained deterministic ``FakeLLMProvider`` that
records every request and returns canned output derived from a hash of the
request (so it is reproducible). It honours ``response_schema`` by returning a
structured stub. The cognition module's own LLM stack is deliberately *not*
imported here — the fake stands in for any conforming provider.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Sequence

import pytest

from matss import ports
from matss.cognition.judge import LLMJudge
from matss.cognition.narrative import NarrativeSystem
from matss.cognition.queue import CognitionJob, CognitionQueue
from matss.domain.agent import AgentDef
from matss.domain.memory import MemoryRecord
from matss.ports import LLMRequest, LLMResponse, ModelTier


# ---------------------------------------------------------------------------
# Local deterministic fake provider
# ---------------------------------------------------------------------------

class FakeLLMProvider:
    """A deterministic, network-free :class:`~matss.ports.LLMProvider` for tests.

    Records every request in ``calls`` and returns text/structured output that is
    a stable function of the request, so the same request always yields the same
    response.
    """

    name: str = "fake"

    def __init__(self) -> None:
        self.calls: List[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        # The fake's output is a stable function of the *whole* request: system,
        # prompt, and tier all participate (parenthesised so ``or`` does not
        # swallow the prompt when ``system`` is truthy).
        seed = (request.system or "") + "\x00" + request.prompt + "\x00" + request.tier
        digest = hashlib.blake2b(seed.encode("utf-8"), digest_size=16).digest()

        structured: Optional[Dict[str, Any]] = None
        if request.response_schema is not None:
            structured = {}
            props = request.response_schema.get("properties", {})
            for i, key in enumerate(request.response_schema.get("required", [])):
                ptype = props.get(key, {}).get("type", "string")
                if ptype in ("number", "integer"):
                    # Deterministic value spread across 1..10.
                    structured[key] = 1 + (digest[i % len(digest)] % 10)
                else:
                    structured[key] = f"val_{digest[i % len(digest)]}"
            text = repr(structured)
        else:
            text = f"FAKE[{request.tier}]:{digest.hex()[:12]}"

        return LLMResponse(
            text=text,
            model=f"fake-{request.tier}",
            tier=request.tier,
            input_tokens=max(1, len(request.prompt.split())),
            output_tokens=max(1, len(text.split())),
            structured=structured,
        )

    def batch(self, requests: Sequence[LLMRequest]) -> List[LLMResponse]:
        return [self.complete(r) for r in requests]


def _agent_def(agent_id: str = "alice") -> AgentDef:
    return AgentDef(
        id=agent_id,
        name="Alice",
        icon="A",
        color="#abcabc",
        home_pos=(1, 2),
        personality=("curious", "kind"),
        traits={"sociability": 1.2},
        schedule_template="default",
        work_location="market",
        background="A long-time resident who runs the town garden.",
    )


def _memory(agent_id: str, text: str, tick: int = 0) -> MemoryRecord:
    return MemoryRecord(
        id=f"{agent_id}-{tick}-{text[:4]}",
        agent_id=agent_id,
        text=text,
        tick=tick,
        day="Monday",
        importance=5.0,
    )


# ---------------------------------------------------------------------------
# Contract conformance
# ---------------------------------------------------------------------------

def test_fake_provider_is_llmprovider():
    assert isinstance(FakeLLMProvider(), ports.LLMProvider)


# ---------------------------------------------------------------------------
# (a) write_diary
# ---------------------------------------------------------------------------

def test_write_diary_uses_persona_cache_prefix_and_memories():
    provider = FakeLLMProvider()
    system = NarrativeSystem(provider)
    adef = _agent_def()
    memories = [
        _memory("alice", "Watered the tomatoes at dawn.", 1),
        _memory("alice", "Argued with Bob about the fence.", 2),
    ]

    result = system.write_diary(adef, "Monday", 3, memories)

    assert isinstance(result, str) and result
    assert len(provider.calls) == 1
    req = provider.calls[0]

    # Persona must be the cacheable prefix and include identifying persona info.
    assert req.cache_prefix is not None
    assert "Alice" in req.cache_prefix
    assert "curious" in req.cache_prefix
    assert req.cache_prefix == req.system

    # The day's memories must appear in the variable prompt, not the prefix.
    assert "Watered the tomatoes at dawn." in req.prompt
    assert "Argued with Bob about the fence." in req.prompt
    assert "day 3" in req.prompt

    # Diary calls go to the BALANCED tier with a generous budget.
    assert req.tier == ModelTier.BALANCED
    assert req.max_tokens >= 1024


def test_write_diary_handles_no_memories():
    provider = FakeLLMProvider()
    system = NarrativeSystem(provider)
    result = system.write_diary(_agent_def(), "Tuesday", 4, [])
    assert isinstance(result, str) and result
    assert len(provider.calls) == 1


def test_write_diary_deterministic():
    adef = _agent_def()
    mems = [_memory("alice", "Saw a comet.", 1)]
    r1 = NarrativeSystem(FakeLLMProvider()).write_diary(adef, "Monday", 1, mems)
    r2 = NarrativeSystem(FakeLLMProvider()).write_diary(adef, "Monday", 1, mems)
    assert r1 == r2


# ---------------------------------------------------------------------------
# (b) compile_town_story flat vs hierarchical
# ---------------------------------------------------------------------------

def test_compile_town_story_flat_makes_one_frontier_call():
    provider = FakeLLMProvider()
    system = NarrativeSystem(provider)
    diaries = {"alice": "A diary.", "bob": "B diary.", "carol": "C diary."}

    story = system.compile_town_story(diaries, "Monday", 1)

    assert isinstance(story, str) and story
    assert len(provider.calls) == 1
    assert provider.calls[0].tier == ModelTier.FRONTIER
    # All diaries are present in the single flat call.
    for text in diaries.values():
        assert text in provider.calls[0].prompt


def test_compile_town_story_hierarchical_call_counts_and_tiers():
    provider = FakeLLMProvider()
    system = NarrativeSystem(provider)
    diaries = {f"a{i}": f"diary {i}" for i in range(6)}
    groups = [["a0", "a1", "a2"], ["a3", "a4", "a5"]]

    story = system.compile_town_story(
        diaries, "Monday", 1, groups=groups, hierarchical=True
    )

    assert isinstance(story, str) and story

    # num_groups BALANCED summary calls + 1 FRONTIER fusion call.
    tiers = [c.tier for c in provider.calls]
    assert tiers.count(ModelTier.BALANCED) == len(groups)
    assert tiers.count(ModelTier.FRONTIER) == 1
    assert len(provider.calls) == len(groups) + 1

    # The final call is the frontier fusion and its input is the group summaries,
    # not the raw diaries.
    final = provider.calls[-1]
    assert final.tier == ModelTier.FRONTIER
    assert "group 0" in final.prompt and "group 1" in final.prompt


def test_compile_town_story_hierarchical_default_single_group():
    provider = FakeLLMProvider()
    system = NarrativeSystem(provider)
    diaries = {"alice": "A", "bob": "B"}
    system.compile_town_story(diaries, "Monday", 1, hierarchical=True)
    # One BALANCED group call (default single group) + one FRONTIER call.
    tiers = [c.tier for c in provider.calls]
    assert tiers.count(ModelTier.BALANCED) == 1
    assert tiers.count(ModelTier.FRONTIER) == 1


# ---------------------------------------------------------------------------
# (c) estimate_cost
# ---------------------------------------------------------------------------

def test_estimate_cost_structure_flat_and_hierarchical():
    system = NarrativeSystem(FakeLLMProvider())

    flat = system.estimate_cost(n_agents=8, hierarchical=False)
    hier = system.estimate_cost(n_agents=8, hierarchical=True, group_size=4)

    for est in (flat, hier):
        assert set(("calls", "input_tokens_est", "tiers")).issubset(est.keys())

    assert flat["scheme"] == "flat"
    assert flat["calls"] == 1
    assert ModelTier.FRONTIER in flat["tiers"]

    assert hier["scheme"] == "hierarchical"
    # ceil(8/4) = 2 group calls + 1 town call.
    assert hier["num_groups"] == 2
    assert hier["calls"] == 3
    assert hier["tiers"][ModelTier.BALANCED]["calls"] == 2
    assert hier["tiers"][ModelTier.FRONTIER]["calls"] == 1


def test_estimate_cost_hierarchical_bounds_frontier_input():
    system = NarrativeSystem(FakeLLMProvider())
    avg = 600
    gs = 4

    # Flat frontier input grows ~linearly with n; hierarchical town-call input is
    # bounded by the (much smaller) number of groups.
    prev_flat_frontier = -1
    for n in (4, 40, 400):
        flat = system.estimate_cost(n, hierarchical=False, avg_diary_tokens=avg)
        hier = system.estimate_cost(
            n, hierarchical=True, avg_diary_tokens=avg, group_size=gs
        )

        flat_frontier = flat["tiers"][ModelTier.FRONTIER]["input_tokens"]
        hier_frontier = hier["tiers"][ModelTier.FRONTIER]["input_tokens"]

        # Flat frontier input is exactly n * avg and strictly increasing.
        assert flat_frontier == n * avg
        assert flat_frontier > prev_flat_frontier
        prev_flat_frontier = flat_frontier

        # Hierarchical frontier input is bounded by num_groups, far below flat.
        num_groups = hier["num_groups"]
        assert hier_frontier == num_groups * avg
        assert hier_frontier <= flat_frontier

    # At large n the hierarchical frontier input is smaller by ~group_size: the
    # frontier call only reads one summary per group, so it scales with
    # n/group_size rather than n.
    big_flat = system.estimate_cost(400, hierarchical=False, avg_diary_tokens=avg)
    big_hier = system.estimate_cost(
        400, hierarchical=True, avg_diary_tokens=avg, group_size=gs
    )
    flat_fr = big_flat["tiers"][ModelTier.FRONTIER]["input_tokens"]
    hier_fr = big_hier["tiers"][ModelTier.FRONTIER]["input_tokens"]
    assert hier_fr * gs == flat_fr           # exact: n*avg vs (n/gs)*avg
    assert hier_fr < flat_fr / 2             # materially cheaper at the frontier


def test_estimate_cost_zero_agents_makes_no_calls():
    system = NarrativeSystem(FakeLLMProvider())
    flat = system.estimate_cost(0, hierarchical=False)
    hier = system.estimate_cost(0, hierarchical=True)
    assert flat["calls"] == 0
    assert flat["input_tokens_est"] == 0
    assert hier["calls"] == 0
    assert hier["num_groups"] == 0
    assert hier["input_tokens_est"] == 0
    # No FRONTIER call is modelled when there is nothing to compile.
    assert hier["tiers"][ModelTier.FRONTIER]["calls"] == 0


def test_estimate_cost_partial_group_rounds_up():
    system = NarrativeSystem(FakeLLMProvider())
    # 9 agents / group_size 4 -> ceil = 3 groups (not 2).
    hier = system.estimate_cost(9, hierarchical=True, group_size=4)
    assert hier["num_groups"] == 3
    assert hier["tiers"][ModelTier.BALANCED]["calls"] == 3
    assert hier["calls"] == 4


# ---------------------------------------------------------------------------
# Edge cases: empty diaries still produce a single coherent call per scheme.
# ---------------------------------------------------------------------------

def test_compile_town_story_flat_empty_diaries():
    provider = FakeLLMProvider()
    story = NarrativeSystem(provider).compile_town_story({}, "Monday", 1)
    assert isinstance(story, str) and story
    assert len(provider.calls) == 1
    assert provider.calls[0].tier == ModelTier.FRONTIER


def test_compile_town_story_deterministic_across_schemes():
    diaries = {"a0": "d0", "a1": "d1", "a2": "d2", "a3": "d3"}
    groups = [["a0", "a1"], ["a2", "a3"]]
    flat1 = NarrativeSystem(FakeLLMProvider()).compile_town_story(diaries, "Mon", 1)
    flat2 = NarrativeSystem(FakeLLMProvider()).compile_town_story(diaries, "Mon", 1)
    assert flat1 == flat2
    h1 = NarrativeSystem(FakeLLMProvider()).compile_town_story(
        diaries, "Mon", 1, groups=groups, hierarchical=True
    )
    h2 = NarrativeSystem(FakeLLMProvider()).compile_town_story(
        diaries, "Mon", 1, groups=groups, hierarchical=True
    )
    assert h1 == h2


def test_fake_provider_output_depends_on_prompt_with_system_set():
    """Guards against the ``or``-precedence regression: with the same persona,
    different memories must yield different diary text (the prompt is hashed)."""
    provider = FakeLLMProvider()
    system = NarrativeSystem(provider)
    adef = _agent_def()
    r1 = system.write_diary(adef, "Monday", 1, [_memory("alice", "Event one.", 1)])
    r2 = system.write_diary(adef, "Monday", 1, [_memory("alice", "Event two.", 2)])
    # Same persona/system, different memories -> the prompt differs, so output must.
    assert provider.calls[0].system == provider.calls[1].system
    assert provider.calls[0].prompt != provider.calls[1].prompt
    assert r1 != r2


# ---------------------------------------------------------------------------
# (d) CognitionQueue
# ---------------------------------------------------------------------------

def _job(jid: str, importance: float) -> CognitionJob:
    return CognitionJob(id=jid, importance=importance, kind="diary", payload={"n": jid})


def test_queue_drops_lowest_importance_when_full():
    q = CognitionQueue(maxlen=3)
    assert q.submit(_job("a", 5.0)) is True
    assert q.submit(_job("b", 1.0)) is True   # lowest so far
    assert q.submit(_job("c", 9.0)) is True
    assert len(q) == 3

    # Queue full; submit a higher-importance job -> drops "b" (importance 1.0).
    assert q.submit(_job("d", 7.0)) is False
    kept_ids = {j.id for j in q.pending()}
    assert kept_ids == {"a", "c", "d"}

    stats = q.stats()
    assert stats["submitted"] == 4
    assert stats["dropped"] == 1
    assert stats["dropped_importance_sum"] == pytest.approx(1.0)


def test_queue_rejects_new_job_if_it_is_lowest():
    q = CognitionQueue(maxlen=2)
    q.submit(_job("a", 5.0))
    q.submit(_job("b", 6.0))
    # New job is the lowest-importance candidate -> rejected, queue unchanged.
    assert q.submit(_job("c", 1.0)) is False
    assert {j.id for j in q.pending()} == {"a", "b"}
    assert q.stats()["dropped"] == 1
    assert q.stats()["dropped_importance_sum"] == pytest.approx(1.0)


def test_queue_process_all_fifo_and_stats():
    q = CognitionQueue(maxlen=5)
    for jid, imp in (("a", 5), ("b", 6), ("c", 7)):
        q.submit(_job(jid, imp))

    seen: List[str] = []
    results = q.process_all(lambda job: seen.append(job.id) or job.id.upper())

    assert seen == ["a", "b", "c"]          # FIFO order preserved
    assert results == ["A", "B", "C"]
    assert len(q) == 0                       # drained
    assert q.stats()["processed"] == 3


def test_queue_maxlen_validation():
    with pytest.raises(ValueError):
        CognitionQueue(maxlen=0)


def test_queue_deterministic_drop():
    def run() -> Dict[str, Any]:
        q = CognitionQueue(maxlen=2)
        for jid, imp in (("a", 3), ("b", 8), ("c", 1), ("d", 5)):
            q.submit(_job(jid, imp))
        return {"kept": sorted(j.id for j in q.pending()), "stats": q.stats()}

    assert run() == run()


def test_queue_process_all_empty_is_noop():
    q = CognitionQueue(maxlen=3)
    calls: List[str] = []
    results = q.process_all(lambda job: calls.append(job.id))
    assert results == []
    assert calls == []
    assert q.stats()["processed"] == 0


def test_queue_maxlen_one_keeps_highest_importance():
    q = CognitionQueue(maxlen=1)
    assert q.submit(_job("low", 1.0)) is True
    # Higher-importance arrival evicts the held lower one.
    assert q.submit(_job("high", 9.0)) is False
    assert [j.id for j in q.pending()] == ["high"]
    # A subsequent lower-importance arrival is itself rejected; "high" stays.
    assert q.submit(_job("mid", 5.0)) is False
    assert [j.id for j in q.pending()] == ["high"]
    s = q.stats()
    assert s["submitted"] == 3
    assert s["dropped"] == 2
    assert s["dropped_importance_sum"] == pytest.approx(1.0 + 5.0)


def test_queue_can_resubmit_after_draining():
    q = CognitionQueue(maxlen=2)
    q.submit(_job("a", 5.0))
    q.process_all(lambda job: job.id)
    assert len(q) == 0
    # Draining frees capacity; new submissions are retained again.
    assert q.submit(_job("b", 1.0)) is True
    assert [j.id for j in q.pending()] == ["b"]


# ---------------------------------------------------------------------------
# Module hygiene: the cognition core must not import the in-progress LLM engine.
# ---------------------------------------------------------------------------

def test_core_modules_do_not_import_cognition_llm():
    import sys
    import matss.cognition.judge  # noqa: F401
    import matss.cognition.narrative  # noqa: F401
    import matss.cognition.queue  # noqa: F401

    for name in ("narrative", "queue", "judge"):
        mod = sys.modules[f"matss.cognition.{name}"]
        src = mod.__file__
        with open(src, "r", encoding="utf-8") as fh:
            text = fh.read()
        assert "cognition.llm" not in text
        assert "import llm" not in text


# ---------------------------------------------------------------------------
# (e) LLMJudge
# ---------------------------------------------------------------------------

def test_judge_scores_all_dimensions_in_range():
    provider = FakeLLMProvider()
    judge = LLMJudge(provider)
    scores = judge.score("The town awoke to gentle rain and quiet resolve.")

    expected = ("coherence", "character_consistency", "interestingness", "faithfulness")
    assert set(scores.keys()) == set(expected)
    for dim, val in scores.items():
        assert isinstance(val, float)
        assert 1.0 <= val <= 10.0

    # Frontier tier with a structured response schema requiring each dimension.
    req = provider.calls[0]
    assert req.tier == ModelTier.FRONTIER
    assert req.response_schema is not None
    assert set(req.response_schema["required"]) == set(expected)


def test_judge_custom_dimensions_and_determinism():
    dims = ("pacing", "tone")
    s1 = LLMJudge(FakeLLMProvider()).score("A short tale.", dimensions=dims)
    s2 = LLMJudge(FakeLLMProvider()).score("A short tale.", dimensions=dims)
    assert set(s1.keys()) == set(dims)
    assert s1 == s2  # deterministic given a deterministic provider
    for v in s1.values():
        assert 1.0 <= v <= 10.0


def test_judge_clamps_out_of_range_provider_values():
    class OutOfRangeProvider(FakeLLMProvider):
        def complete(self, request: LLMRequest) -> LLMResponse:
            self.calls.append(request)
            structured = {k: 999.0 for k in request.response_schema["required"]}
            return LLMResponse(
                text=repr(structured),
                model="oor",
                tier=request.tier,
                structured=structured,
            )

    scores = LLMJudge(OutOfRangeProvider()).score("text")
    for v in scores.values():
        assert v == 10.0  # clamped to the max


def test_judge_falls_back_to_text_json_when_unstructured():
    class TextOnlyProvider(FakeLLMProvider):
        def complete(self, request: LLMRequest) -> LLMResponse:
            self.calls.append(request)
            import json
            payload = {k: 7 for k in request.response_schema["required"]}
            return LLMResponse(
                text=json.dumps(payload),
                model="textonly",
                tier=request.tier,
                structured=None,  # force the text-parsing fallback
            )

    scores = LLMJudge(TextOnlyProvider()).score("text")
    assert all(v == 7.0 for v in scores.values())
