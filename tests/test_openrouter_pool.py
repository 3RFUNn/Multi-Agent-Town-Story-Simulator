"""OpenRouter free-model pool: discovery filtering, 3-model routing windows,
and rotation-on-failure so every gateway retry instantly targets backups."""
from __future__ import annotations

import asyncio

import httpx
import openai
import pytest

from townsim.llm.providers import OpenRouterProvider, TransientLLMError

PRIMARY = "google/gemma-4-31b-it:free"
FALLBACKS = ["meta-llama/llama-3.3-70b-instruct:free"]


def make_provider(**kw) -> OpenRouterProvider:
    return OpenRouterProvider(api_key="sk-or-test", model=PRIMARY,
                              fallback_models=list(FALLBACKS), **kw)


def models_payload() -> dict:
    return {"data": [
        {"id": "vendor/paid-model", "context_length": 128000},
        {"id": "vendor/free-a:free", "context_length": 32000,
         "architecture": {"output_modalities": ["text"]}},
        {"id": "vendor/free-tiny:free", "context_length": 4000},          # too small
        {"id": "vendor/free-image:free", "context_length": 32000,
         "architecture": {"output_modalities": ["image"]}},               # not text
        {"id": PRIMARY, "context_length": 96000},                          # dup of primary
        {"id": "vendor/free-b:free"},                                      # no metadata: keep
        {"id": "vendor/llama-guard-4:free", "context_length": 32000},      # specialty: drop
        {"id": "nvidia/nemotron-content-safety:free", "context_length": 32000},
    ]}


class TestDiscoveryFiltering:
    def test_free_model_ids_filters_and_preserves_order(self):
        ids = OpenRouterProvider._free_model_ids(models_payload())
        assert ids == ["vendor/free-a:free", PRIMARY, "vendor/free-b:free"]

    def test_empty_payload(self):
        assert OpenRouterProvider._free_model_ids({}) == []
        assert OpenRouterProvider._free_model_ids({"data": None}) == []

    def test_specialty_models_excluded(self):
        ids = OpenRouterProvider._free_model_ids(models_payload())
        assert not [m for m in ids if "guard" in m or "safety" in m]

    def test_configured_models_deduped(self):
        provider = OpenRouterProvider(api_key="k", model="a:free",
                                      fallback_models=["b:free", "a:free"])
        assert provider._configured_models() == ["a:free", "b:free"]


class TestCandidateResolution:
    async def test_configured_head_then_discovered(self, monkeypatch):
        provider = make_provider()

        async def fake_fetch():
            return models_payload()
        monkeypatch.setattr(provider, "_fetch_models_payload", fake_fetch)
        pool = await provider._resolve_candidates()
        assert pool[:2] == [PRIMARY, *FALLBACKS]
        assert "vendor/free-a:free" in pool and "vendor/free-b:free" in pool
        assert pool.count(PRIMARY) == 1                     # deduped
        assert provider._candidates == pool                 # cached

    async def test_discovery_failure_cools_down_then_retries(self, monkeypatch):
        provider = make_provider()
        calls = {"n": 0}

        async def failing_fetch():
            calls["n"] += 1
            raise httpx.ConnectError("offline")
        monkeypatch.setattr(provider, "_fetch_models_payload", failing_fetch)
        assert await provider._resolve_candidates() == [PRIMARY, *FALLBACKS]
        assert provider._candidates is None                 # not cached permanently
        # Inside the cooldown, completions must NOT pay for another fetch —
        # a hung /models endpoint would otherwise serialize all throughput.
        assert await provider._resolve_candidates() == [PRIMARY, *FALLBACKS]
        assert calls["n"] == 1
        provider._next_discovery_at = 0.0                   # cooldown elapsed
        await provider._resolve_candidates()
        assert calls["n"] == 2

    async def test_auto_disabled_uses_configured_only(self, monkeypatch):
        provider = make_provider(auto_free_models=False)

        async def boom():                                    # must never be called
            raise AssertionError("discovery ran with auto_free_models=False")
        monkeypatch.setattr(provider, "_fetch_models_payload", boom)
        assert await provider._resolve_candidates() == [PRIMARY, *FALLBACKS]


class TestRoutingWindow:
    def test_small_pool_used_whole(self):
        provider = make_provider()
        assert provider._window(["a", "b"]) == ["a", "b"]

    def test_window_caps_at_three_and_rotates_with_wraparound(self):
        provider = make_provider()
        pool = ["a", "b", "c", "d", "e"]
        assert provider._window(pool) == ["a", "b", "c"]
        provider._rotation += 3
        assert provider._window(pool) == ["d", "e", "a"]
        provider._rotation += 3
        assert provider._window(pool) == ["b", "c", "d"]


def _rate_limit_error() -> openai.RateLimitError:
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx.Response(status_code=429, request=request)
    return openai.RateLimitError("rate limited", response=response, body=None)


def _bad_request_error() -> openai.APIStatusError:
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx.Response(status_code=400, request=request)
    return openai.APIStatusError("bad request", response=response, body=None)


class _FakeCompletions:
    """Records each create() call; behavior driven by a script of
    exceptions/strings."""

    def __init__(self, script):
        self.script = list(script)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        await asyncio.sleep(0)   # let concurrent callers dispatch first
        action = self.script.pop(0)
        if isinstance(action, Exception):
            raise action

        class Msg:
            content = action

        class Choice:
            message = Msg()

        class Rsp:
            choices = [Choice()]
        return Rsp()


def wire(provider: OpenRouterProvider, script, candidates) -> _FakeCompletions:
    fake = _FakeCompletions(script)
    provider._client.chat.completions = fake
    provider._candidates = list(candidates)
    return fake


class TestRotationOnFailure:
    POOL = ["m1:free", "m2:free", "m3:free", "m4:free", "m5:free", "m6:free"]

    async def test_success_sends_window_and_keeps_rotation(self):
        provider = make_provider()
        fake = wire(provider, ["hello town"], self.POOL)
        out = await provider.complete("p", max_tokens=10, temperature=0.1)
        assert out == "hello town"
        call = fake.calls[0]
        assert call["model"] == "m1:free"
        assert call["extra_body"]["models"] == ["m1:free", "m2:free", "m3:free"]
        assert call["extra_body"]["reasoning"] == {"enabled": True}
        assert provider._rotation == 0

    async def test_transient_failure_rotates_next_call_to_backups(self):
        provider = make_provider()
        fake = wire(provider, [_rate_limit_error(), "recovered"], self.POOL)
        with pytest.raises(TransientLLMError):
            await provider.complete("p", max_tokens=10, temperature=0.1)
        out = await provider.complete("p", max_tokens=10, temperature=0.1)  # gateway retry
        assert out == "recovered"
        assert fake.calls[1]["extra_body"]["models"] == ["m4:free", "m5:free", "m6:free"]

    async def test_empty_completion_is_transient_and_rotates(self):
        provider = make_provider()
        wire(provider, ["   "], self.POOL)
        with pytest.raises(TransientLLMError):
            await provider.complete("p", max_tokens=10, temperature=0.1)
        assert provider._rotation == 3

    async def test_permanent_error_surfaces_without_rotation(self):
        provider = make_provider()
        wire(provider, [_bad_request_error()], self.POOL)
        with pytest.raises(openai.APIStatusError):
            await provider.complete("p", max_tokens=10, temperature=0.1)
        assert provider._rotation == 0                       # R12: don't burn backups on 4xx

    async def test_sticky_window_after_recovery(self):
        provider = make_provider()
        fake = wire(provider, [_rate_limit_error(), "ok", "ok again"], self.POOL)
        with pytest.raises(TransientLLMError):
            await provider.complete("p", max_tokens=10, temperature=0.1)
        await provider.complete("p", max_tokens=10, temperature=0.1)
        await provider.complete("p", max_tokens=10, temperature=0.1)
        # the healthy window stays put instead of snapping back to a saturated primary
        assert fake.calls[2]["extra_body"]["models"] == ["m4:free", "m5:free", "m6:free"]

    async def test_two_model_pool_omits_nothing(self):
        provider = make_provider()
        fake = wire(provider, ["hi"], ["only:free", "other:free"])
        await provider.complete("p", max_tokens=10, temperature=0.1)
        assert fake.calls[0]["extra_body"]["models"] == ["only:free", "other:free"]

    async def test_concurrent_failures_of_same_window_advance_once(self):
        """Compare-and-set on the rotation counter: N workers failing on the
        SAME dispatched window must advance it once, not N times — otherwise
        retries skip windows that were never tried."""
        provider = make_provider()
        wire(provider, [_rate_limit_error(), _rate_limit_error(), _rate_limit_error()],
             self.POOL)
        results = await asyncio.gather(
            *(provider.complete("p", max_tokens=10, temperature=0.1) for _ in range(3)),
            return_exceptions=True)
        assert all(isinstance(r, TransientLLMError) for r in results)
        assert provider._rotation == 3   # one advance for the shared window
