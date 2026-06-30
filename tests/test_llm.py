"""Tests for the provider-agnostic LLM stack (``matss.cognition.llm``)."""

from __future__ import annotations

import json
from typing import List, Sequence

import pytest

from matss import ports
from matss.ports import LLMRequest, LLMResponse, ModelTier
from matss.cognition.llm import (
    AnthropicProvider,
    BatchingLLMProvider,
    CachingLLMProvider,
    MockLLMProvider,
    OpenAIProvider,
    RetryingProvider,
    TieredRouter,
)
from matss.cognition.llm import structured


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class _FlakyProvider:
    """Fails ``fail_times`` times, then returns a fixed response.

    Implements the :class:`ports.LLMProvider` contract.
    """

    name = "flaky"

    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError(f"transient failure #{self.calls}")
        return LLMResponse(text="ok", model="flaky", tier=request.tier)

    def batch(self, requests: Sequence[LLMRequest]) -> List[LLMResponse]:
        return [self.complete(r) for r in requests]


class _TaggedProvider:
    """Returns a response whose text identifies which provider answered."""

    def __init__(self, tag: str) -> None:
        self.name = tag
        self.calls = 0

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        return LLMResponse(text=self.name, model=self.name, tier=request.tier)

    def batch(self, requests: Sequence[LLMRequest]) -> List[LLMResponse]:
        return [self.complete(r) for r in requests]


# ---------------------------------------------------------------------------
# (a) MockLLMProvider determinism
# ---------------------------------------------------------------------------

def test_mock_is_a_provider():
    assert isinstance(MockLLMProvider(), ports.LLMProvider)
    assert MockLLMProvider().name == "mock"


def test_mock_determinism_same_request_same_text():
    p1 = MockLLMProvider()
    p2 = MockLLMProvider()
    req = LLMRequest(prompt="hello world", system="be terse", tier=ModelTier.CHEAP)
    r1 = p1.complete(req)
    r2 = p2.complete(req)
    assert r1.text == r2.text
    assert r1.model == r2.model == "mock-cheap"
    # Repeated calls on the same instance are also stable.
    assert p1.complete(req).text == r1.text


def test_mock_different_prompts_and_tiers_differ():
    p = MockLLMProvider()
    base = LLMRequest(prompt="alpha")
    other_prompt = LLMRequest(prompt="beta")
    other_tier = LLMRequest(prompt="alpha", tier=ModelTier.FRONTIER)
    assert p.complete(base).text != p.complete(other_prompt).text
    assert p.complete(base).text != p.complete(other_tier).text
    # Tier is reflected in the model name.
    assert p.complete(other_tier).model == "mock-frontier"


def test_mock_token_counts_and_call_tracking():
    p = MockLLMProvider()
    req = LLMRequest(prompt="one two three four")
    resp = p.complete(req)
    assert resp.input_tokens == 4
    assert resp.output_tokens >= 1
    assert p.call_count == 1
    assert p.calls[0] is req
    p.batch([req, req])
    assert p.call_count == 3


def test_mock_empty_prompt_is_safe_and_deterministic():
    # Degenerate input must not crash and must stay deterministic.
    a = MockLLMProvider().complete(LLMRequest(prompt=""))
    b = MockLLMProvider().complete(LLMRequest(prompt=""))
    assert a.text == b.text
    assert a.input_tokens >= 1  # floored at 1, never 0
    assert a.output_tokens >= 1


def test_mock_large_word_count_is_deterministic():
    # Exercises the digest re-hash branch used for long free-text outputs.
    req = LLMRequest(prompt="a longer prompt here", tier=ModelTier.FRONTIER)
    a = MockLLMProvider(words=100).complete(req)
    b = MockLLMProvider(words=100).complete(req)
    assert a.text == b.text
    assert len(a.text.split()) == 100


def test_mock_batch_matches_complete_elementwise():
    p = MockLLMProvider()
    reqs = [LLMRequest(prompt="r0"), LLMRequest(prompt="r1", tier=ModelTier.CHEAP)]
    batched = p.batch(reqs)
    fresh = MockLLMProvider()
    assert [r.text for r in batched] == [fresh.complete(r).text for r in reqs]
    assert [r.model for r in batched] == [fresh.complete(r).model for r in reqs]


# ---------------------------------------------------------------------------
# (b) Structured output
# ---------------------------------------------------------------------------

def test_mock_structured_output_satisfies_schema():
    schema = {
        "type": "object",
        "required": ["mood", "intensity", "active"],
        "properties": {
            "mood": {"type": "string"},
            "intensity": {"type": "integer"},
            "active": {"type": "boolean"},
        },
    }
    p = MockLLMProvider()
    req = LLMRequest(prompt="how do you feel", response_schema=schema)
    resp = p.complete(req)
    assert resp.structured is not None
    # All required keys present and correctly typed.
    assert set(resp.structured) >= {"mood", "intensity", "active"}
    assert structured.satisfies(resp.structured, schema)
    # text is the JSON of the structured dict.
    assert json.loads(resp.text) == resp.structured


def test_mock_structured_is_deterministic_and_prompt_sensitive():
    schema = {"type": "object", "required": ["x"], "properties": {"x": {"type": "string"}}}
    p = MockLLMProvider()
    a = p.complete(LLMRequest(prompt="p1", response_schema=schema))
    b = p.complete(LLMRequest(prompt="p1", response_schema=schema))
    c = p.complete(LLMRequest(prompt="p2", response_schema=schema))
    assert a.structured == b.structured
    assert a.structured != c.structured


def test_structured_validate_and_coerce():
    schema = {
        "type": "object",
        "required": ["n", "flag"],
        "properties": {"n": {"type": "integer"}, "flag": {"type": "boolean"}},
    }
    ok, reason = structured.validate({"n": 5, "flag": True}, schema)
    assert ok and reason is None
    bad_ok, bad_reason = structured.validate({"n": 5}, schema)
    assert not bad_ok and "flag" in bad_reason
    coerced = structured.coerce({"n": "7", "flag": "true"}, schema)
    assert coerced == {"n": 7, "flag": True}
    # bool must not satisfy integer.
    assert not structured.satisfies({"n": True, "flag": True}, schema)


def test_structured_nested_object_and_array():
    schema = {
        "type": "object",
        "required": ["meta", "tags"],
        "properties": {
            "meta": {
                "type": "object",
                "required": ["score"],
                "properties": {"score": {"type": "number"}},
            },
            "tags": {"type": "array", "items": {"type": "string"}},
        },
    }
    stub = structured.build_stub(schema, seed=3)
    assert structured.satisfies(stub, schema)
    assert isinstance(stub["meta"], dict) and "score" in stub["meta"]
    assert isinstance(stub["tags"], list)
    # A wrong-typed nested element is reported with a path, not silently passed.
    ok, reason = structured.validate({"meta": {"score": "bad"}, "tags": ["t"]}, schema)
    assert not ok and "meta" in reason and "score" in reason
    # Array item type mismatch is caught.
    ok2, reason2 = structured.validate({"meta": {"score": 1.0}, "tags": [123]}, schema)
    assert not ok2 and "tags" in reason2


def test_structured_coerce_missing_keys_filled_with_stubs():
    schema = {
        "type": "object",
        "required": ["a", "b"],
        "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
    }
    coerced = structured.coerce({"a": "given"}, schema)
    assert coerced["a"] == "given"
    assert isinstance(coerced["b"], int)
    assert structured.satisfies(coerced, schema)


# ---------------------------------------------------------------------------
# (c) RetryingProvider
# ---------------------------------------------------------------------------

def test_retry_succeeds_after_failures():
    slept: List[float] = []
    inner = _FlakyProvider(fail_times=2)  # fails twice, succeeds on 3rd
    p = RetryingProvider(inner, max_attempts=4, base_delay=0.0, sleep=slept.append)
    resp = p.complete(LLMRequest(prompt="x"))
    assert resp.text == "ok"
    assert inner.calls == 3
    assert p.attempts == 3
    # Two sleeps (before retry 2 and retry 3), none after the success.
    assert len(slept) == 2


def test_retry_raises_after_max_attempts():
    inner = _FlakyProvider(fail_times=99)
    p = RetryingProvider(inner, max_attempts=3, base_delay=0.0, sleep=lambda _d: None)
    with pytest.raises(RuntimeError):
        p.complete(LLMRequest(prompt="x"))
    assert inner.calls == 3
    assert p.attempts == 3


def test_retry_backoff_schedule_is_deterministic():
    slept: List[float] = []
    inner = _FlakyProvider(fail_times=2)
    p = RetryingProvider(inner, max_attempts=4, base_delay=1.0, sleep=slept.append)
    p.complete(LLMRequest(prompt="x"))
    # base_delay * 2**attempt for attempts 0 and 1.
    assert slept == [1.0, 2.0]


def test_retry_only_retries_configured_exceptions():
    # An exception type outside retry_on must propagate on the first attempt.
    class _KeyErrorProvider:
        name = "ke"

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, request: LLMRequest) -> LLMResponse:
            self.calls += 1
            raise KeyError("boom")

        def batch(self, requests: Sequence[LLMRequest]) -> List[LLMResponse]:
            return [self.complete(r) for r in requests]

    inner = _KeyErrorProvider()
    p = RetryingProvider(inner, max_attempts=5, retry_on=(RuntimeError,), sleep=lambda _d: None)
    with pytest.raises(KeyError):
        p.complete(LLMRequest(prompt="x"))
    assert inner.calls == 1
    assert p.attempts == 1


def test_retry_rejects_bad_max_attempts():
    with pytest.raises(ValueError):
        RetryingProvider(MockLLMProvider(), max_attempts=0)


def test_retry_is_a_provider():
    assert isinstance(RetryingProvider(MockLLMProvider()), ports.LLMProvider)


# ---------------------------------------------------------------------------
# (d) CachingLLMProvider
# ---------------------------------------------------------------------------

def test_caching_calls_inner_once():
    inner = MockLLMProvider()
    p = CachingLLMProvider(inner)
    req = LLMRequest(prompt="cache me", system="sys")
    r1 = p.complete(req)
    r2 = p.complete(req)
    assert inner.call_count == 1
    assert r1.cached is False
    assert r2.cached is True
    assert r2.text == r1.text
    assert p.hits == 1 and p.misses == 1
    assert p.hit_rate == 0.5
    assert len(p) == 1


def test_caching_distinguishes_requests():
    inner = MockLLMProvider()
    p = CachingLLMProvider(inner)
    p.complete(LLMRequest(prompt="a"))
    p.complete(LLMRequest(prompt="b"))
    p.complete(LLMRequest(prompt="a", cache_prefix="other"))
    assert inner.call_count == 3
    assert p.misses == 3 and p.hits == 0


def test_caching_preserves_payload_only_flips_cached_flag():
    inner = MockLLMProvider()
    p = CachingLLMProvider(inner)
    req = LLMRequest(prompt="payload", response_schema={
        "type": "object", "required": ["x"], "properties": {"x": {"type": "string"}},
    })
    first = p.complete(req)
    second = p.complete(req)
    # Everything but the cached flag is identical (structured + tokens preserved).
    assert second.cached is True and first.cached is False
    assert second.text == first.text
    assert second.structured == first.structured
    assert second.input_tokens == first.input_tokens
    assert second.output_tokens == first.output_tokens


def test_caching_fifo_eviction_under_cap():
    inner = MockLLMProvider()
    p = CachingLLMProvider(inner, max_entries=2)
    p.complete(LLMRequest(prompt="a"))
    p.complete(LLMRequest(prompt="b"))
    p.complete(LLMRequest(prompt="c"))  # cache now {b, c}; "a" evicted (oldest)
    assert len(p) == 2
    # "c" is the most recent insertion and is still cached (a hit, no inner call).
    before = inner.call_count
    hit = p.complete(LLMRequest(prompt="c"))
    assert hit.cached is True and inner.call_count == before
    # "a" was evicted -> recomputed (miss), inner called again.
    p.complete(LLMRequest(prompt="a"))
    assert inner.call_count == before + 1


def test_caching_clear_resets_state():
    inner = MockLLMProvider()
    p = CachingLLMProvider(inner)
    req = LLMRequest(prompt="z")
    p.complete(req)
    p.complete(req)
    assert p.hits == 1 and len(p) == 1
    p.clear()
    assert p.hits == 0 and p.misses == 0 and len(p) == 0
    assert p.hit_rate == 0.0
    p.complete(req)  # recomputed after clear
    assert inner.call_count == 2


def test_caching_is_a_provider():
    assert isinstance(CachingLLMProvider(MockLLMProvider()), ports.LLMProvider)


# ---------------------------------------------------------------------------
# (e) TieredRouter
# ---------------------------------------------------------------------------

def test_router_dispatches_by_tier():
    cheap = _TaggedProvider("cheap-p")
    balanced = _TaggedProvider("balanced-p")
    frontier = _TaggedProvider("frontier-p")
    router = TieredRouter(
        {
            ModelTier.CHEAP: cheap,
            ModelTier.BALANCED: balanced,
            ModelTier.FRONTIER: frontier,
        }
    )
    assert router.complete(LLMRequest(prompt="x", tier=ModelTier.CHEAP)).text == "cheap-p"
    assert router.complete(LLMRequest(prompt="x", tier=ModelTier.FRONTIER)).text == "frontier-p"
    assert cheap.calls == 1 and frontier.calls == 1 and balanced.calls == 0


def test_router_default_fallback():
    default = _TaggedProvider("default-p")
    router = TieredRouter({ModelTier.FRONTIER: _TaggedProvider("f")}, default=default)
    assert router.complete(LLMRequest(prompt="x", tier=ModelTier.CHEAP)).text == "default-p"


def test_router_cascade_escalates_on_failure():
    cheap = _FlakyProvider(fail_times=99)   # always fails
    balanced = _TaggedProvider("balanced-p")
    router = TieredRouter({ModelTier.CHEAP: cheap, ModelTier.BALANCED: balanced})
    resp = router.cascade(
        LLMRequest(prompt="x"),
        order=(ModelTier.CHEAP, ModelTier.BALANCED),
    )
    assert resp.text == "balanced-p"
    assert resp.tier == ModelTier.BALANCED
    assert cheap.calls == 1 and balanced.calls == 1


def test_router_cascade_raises_when_all_fail():
    router = TieredRouter(
        {ModelTier.CHEAP: _FlakyProvider(99), ModelTier.BALANCED: _FlakyProvider(99)}
    )
    with pytest.raises(RuntimeError):
        router.cascade(LLMRequest(prompt="x"), order=(ModelTier.CHEAP, ModelTier.BALANCED))


def test_router_batch_routes_each_request_by_tier():
    cheap = _TaggedProvider("cheap-p")
    frontier = _TaggedProvider("frontier-p")
    router = TieredRouter({ModelTier.CHEAP: cheap, ModelTier.FRONTIER: frontier})
    out = router.batch([
        LLMRequest(prompt="x", tier=ModelTier.CHEAP),
        LLMRequest(prompt="y", tier=ModelTier.FRONTIER),
        LLMRequest(prompt="z", tier=ModelTier.CHEAP),
    ])
    assert [r.text for r in out] == ["cheap-p", "frontier-p", "cheap-p"]
    assert cheap.calls == 2 and frontier.calls == 1


def test_router_cascade_dispatches_to_each_tier_provider():
    # Verifies the request is re-tiered AND sent to that tier's provider in order.
    cheap = _FlakyProvider(fail_times=99)
    frontier = _TaggedProvider("frontier-p")
    router = TieredRouter({ModelTier.CHEAP: cheap, ModelTier.FRONTIER: frontier})
    resp = router.cascade(
        LLMRequest(prompt="x", tier=ModelTier.BALANCED),
        order=(ModelTier.CHEAP, ModelTier.FRONTIER),
    )
    assert resp.text == "frontier-p"
    assert resp.tier == ModelTier.FRONTIER  # re-tiered away from BALANCED
    assert cheap.calls == 1 and frontier.calls == 1


def test_router_cascade_empty_order_raises():
    router = TieredRouter(default=MockLLMProvider())
    with pytest.raises(ValueError):
        router.cascade(LLMRequest(prompt="x"), order=())


def test_router_is_a_provider():
    assert isinstance(TieredRouter(default=MockLLMProvider()), ports.LLMProvider)


def test_router_requires_a_provider():
    with pytest.raises(ValueError):
        TieredRouter()


# ---------------------------------------------------------------------------
# Batching
# ---------------------------------------------------------------------------

def test_batching_submit_flush():
    inner = MockLLMProvider()
    bp = BatchingLLMProvider(inner)
    h0 = bp.submit(LLMRequest(prompt="first"))
    h1 = bp.submit(LLMRequest(prompt="second"))
    assert bp.pending == 2
    responses = bp.flush()
    assert bp.pending == 0
    assert len(responses) == 2
    # Handles index into the result list; matches direct completion.
    assert responses[h0].text == MockLLMProvider().complete(LLMRequest(prompt="first")).text
    assert responses[h1].text == MockLLMProvider().complete(LLMRequest(prompt="second")).text
    # Flushing again with nothing pending yields an empty list.
    assert bp.flush() == []


def test_batching_is_a_provider():
    assert isinstance(BatchingLLMProvider(MockLLMProvider()), ports.LLMProvider)


# ---------------------------------------------------------------------------
# (f) Real adapters: tier->model mapping, no network at construction
# ---------------------------------------------------------------------------

def test_openai_tier_model_mapping_no_network():
    p = OpenAIProvider(api_key="sk-test")
    assert isinstance(p, ports.LLMProvider)
    assert p.model_for(ModelTier.CHEAP) == "gpt-4.1-mini"
    assert p.model_for(ModelTier.BALANCED) == "gpt-4.1"
    assert p.model_for(ModelTier.FRONTIER) == "o4-mini"
    # Payload construction is offline and reflects the model + schema mapping.
    schema = {"type": "object", "required": ["a"], "properties": {"a": {"type": "string"}}}
    payload = p._build_payload(
        LLMRequest(prompt="hi", system="sys", tier=ModelTier.CHEAP, response_schema=schema)
    )
    assert payload["model"] == "gpt-4.1-mini"
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["messages"][0]["role"] == "system"


def test_openai_model_override():
    p = OpenAIProvider(api_key="k", models={ModelTier.CHEAP: "custom-mini"})
    assert p.model_for(ModelTier.CHEAP) == "custom-mini"
    # Unspecified tiers keep defaults.
    assert p.model_for(ModelTier.FRONTIER) == "o4-mini"


def test_anthropic_tier_model_mapping_no_network():
    p = AnthropicProvider(api_key="sk-ant")
    assert isinstance(p, ports.LLMProvider)
    assert p.model_for(ModelTier.CHEAP) == "claude-haiku-4-5"
    assert p.model_for(ModelTier.BALANCED) == "claude-sonnet-4-6"
    assert p.model_for(ModelTier.FRONTIER) == "claude-opus-4-8"


def test_anthropic_cache_prefix_and_structured_payload():
    p = AnthropicProvider(api_key="k")
    schema = {"type": "object", "required": ["a"], "properties": {"a": {"type": "string"}}}
    payload = p._build_payload(
        LLMRequest(
            prompt="body",
            system="persona and world",
            cache_prefix="persona and world",
            response_schema=schema,
        )
    )
    # cache_control breakpoint present on the stable prefix block.
    assert payload["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert payload["system"][0]["text"] == "persona and world"
    # structured output emulated as a forced tool call.
    assert payload["tools"][0]["input_schema"] == schema
    assert payload["tool_choice"]["name"] == payload["tools"][0]["name"]


def test_openai_payload_without_schema_has_no_response_format():
    p = OpenAIProvider(api_key="k")
    payload = p._build_payload(LLMRequest(prompt="hi", stop=["END"]))
    assert "response_format" not in payload
    assert payload["stop"] == ["END"]
    # No system -> only the user message is present.
    assert [m["role"] for m in payload["messages"]] == ["user"]


def test_anthropic_payload_without_cache_prefix_uses_plain_system():
    p = AnthropicProvider(api_key="k")
    payload = p._build_payload(LLMRequest(prompt="body", system="plain system"))
    # Plain string system block, no cache_control machinery.
    assert payload["system"] == "plain system"
    assert "tools" not in payload


def test_llm_package_imports_without_requests():
    # The whole stack must import with zero third-party deps at module load.
    import importlib
    import sys

    blocked = {"requests"}
    saved = {name: sys.modules.pop(name, None) for name in list(sys.modules)
             if name == "requests" or name.startswith("requests.")}

    class _Blocker:
        def find_module(self, name, path=None):
            return self if name in blocked else None

        def load_module(self, name):
            raise ImportError(f"{name} is blocked for this test")

    sys.meta_path.insert(0, _Blocker())
    try:
        for mod in [
            "matss.cognition.llm",
            "matss.cognition.llm.openai_provider",
            "matss.cognition.llm.anthropic_provider",
            "matss.cognition.llm.mock",
        ]:
            sys.modules.pop(mod, None)
            importlib.import_module(mod)  # must not raise
    finally:
        sys.meta_path.pop(0)
        for name, mod in saved.items():
            if mod is not None:
                sys.modules[name] = mod


def test_real_adapters_require_key_to_call():
    # No key -> calling complete raises before any network access. Clear every
    # candidate var (incl. the generic API_KEY fallback) so the test is hermetic.
    import os

    cleared = {name: os.environ.pop(name, None)
               for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                            "OPENROUTER_API_KEY", "API_KEY")}
    try:
        with pytest.raises(RuntimeError):
            OpenAIProvider().complete(LLMRequest(prompt="x"))
        with pytest.raises(RuntimeError):
            AnthropicProvider().complete(LLMRequest(prompt="x"))
    finally:
        for name, value in cleared.items():
            if value is not None:
                os.environ[name] = value


# ---------------------------------------------------------------------------
# Composition smoke test
# ---------------------------------------------------------------------------

def test_composed_stack_caching_over_retry_over_router():
    cheap = MockLLMProvider()
    stack = CachingLLMProvider(
        RetryingProvider(
            TieredRouter(default=cheap), base_delay=0.0, sleep=lambda _d: None
        )
    )
    req = LLMRequest(prompt="compose", tier=ModelTier.CHEAP)
    r1 = stack.complete(req)
    r2 = stack.complete(req)
    assert r1.text == r2.text
    assert r2.cached is True
    assert cheap.call_count == 1  # second served from cache
