"""Gateway tests: retries, structured output, semantic cache, fake provider."""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from townsim.cognition.reflection import ReflectionResult
from townsim.llm.gateway import LLMGateway, SemanticCache
from townsim.llm.providers import FakeProvider, TransientLLMError


class FlakyProvider:
    name = "flaky"

    def __init__(self, fail_times: int, text: str = "ok") -> None:
        self.fail_times = fail_times
        self.calls = 0
        self.text = text

    async def complete(self, prompt, *, max_tokens, temperature):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise TransientLLMError("simulated 429")
        return self.text

    async def embed(self, text):
        return [1.0, 0.0]


class TestRetries:
    async def test_retries_transient_then_succeeds(self):
        provider = FlakyProvider(fail_times=2)
        gateway = LLMGateway(provider, max_attempts=4)
        assert await gateway.complete("hi") == "ok"
        assert provider.calls == 3
        assert gateway.stats["retries"] == 2

    async def test_gives_up_after_max_attempts(self):
        provider = FlakyProvider(fail_times=10)
        gateway = LLMGateway(provider, max_attempts=3)
        with pytest.raises(TransientLLMError):
            await gateway.complete("hi")
        assert provider.calls == 3
        assert gateway.stats["failures"] == 1


class TestStructuredOutput:
    async def test_fake_provider_reflection_roundtrip(self):
        gateway = LLMGateway(FakeProvider())
        result = await gateway.complete_structured("Reflect please", ReflectionResult)
        assert isinstance(result, ReflectionResult)
        assert result.mood
        for adj in result.goal_adjustments:
            assert -0.2 <= adj.delta <= 0.2

    async def test_invalid_json_retries_then_raises(self):
        class Rigid(BaseModel):
            must_exist: int

        class BadJsonProvider:
            name = "bad"

            def __init__(self):
                self.calls = 0

            async def complete(self, prompt, *, max_tokens, temperature):
                self.calls += 1
                return "ONLY a JSON object {\"wrong\": true}"

            async def embed(self, text):
                return [1.0]

        provider = BadJsonProvider()
        gateway = LLMGateway(provider)
        with pytest.raises(ValueError):
            await gateway.complete_structured("x", Rigid, attempts=2)
        assert provider.calls == 2


class TestSemanticCache:
    def test_hit_above_threshold(self):
        cache = SemanticCache(threshold=0.9)
        cache.put([1.0, 0.0], "answer")
        assert cache.get([1.0, 0.01]) == "answer"
        assert cache.get([0.0, 1.0]) is None

    async def test_gateway_uses_cache(self):
        provider = FakeProvider()
        gateway = LLMGateway(provider, cache=SemanticCache(threshold=0.99))
        first = await gateway.complete("same prompt", cacheable=True)
        second = await gateway.complete("same prompt", cacheable=True)
        assert first == second
        assert gateway.stats["cache_hits"] == 1


class TestFakeProvider:
    async def test_deterministic(self):
        provider = FakeProvider()
        a = await provider.complete("You are Alex,\n- did a thing\nWrite a diary",
                                    max_tokens=100, temperature=0.8)
        b = await provider.complete("You are Alex,\n- did a thing\nWrite a diary",
                                    max_tokens=100, temperature=0.8)
        assert a == b
        assert "did a thing" in a

    async def test_embeddings_stable_and_normalizable(self):
        provider = FakeProvider()
        e1 = await provider.embed("hello")
        e2 = await provider.embed("hello")
        assert e1 == e2
        assert any(abs(v) > 0 for v in e1)
