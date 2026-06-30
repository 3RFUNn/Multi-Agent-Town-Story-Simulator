"""Offline tests for the OpenRouter (Google Gemma + reasoning) adapter.

All network calls are monkeypatched; these never touch OpenRouter.
"""

import importlib
import sys

import pytest

from matss import ports
from matss.cognition.llm import OpenRouterProvider, build_provider
from matss.cognition.llm.openrouter_provider import DEFAULT_MODEL
from matss.ports import LLMRequest, ModelTier


# A canned OpenRouter-shaped response with reasoning_details.
def _fake_response(content="3 r's.", reasoning="The word strawberry has r-r-r."):
    return {
        "model": "google/gemma-4-26b-a4b-it:free",
        "choices": [{
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": content,
                "reasoning_details": [{"type": "reasoning.text", "text": reasoning}],
            },
        }],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7},
    }


def test_construction_is_inert_and_protocol_conformant():
    p = OpenRouterProvider(api_key="test-key")
    assert isinstance(p, ports.LLMProvider)
    assert p.name == "openrouter"
    assert p.default_model == DEFAULT_MODEL
    assert p.model_for(ModelTier.CHEAP) == DEFAULT_MODEL
    assert p.model_for(ModelTier.FRONTIER) == DEFAULT_MODEL


def test_module_import_does_not_require_requests():
    sys.modules.pop("requests", None)
    mod = importlib.import_module("matss.cognition.llm.openrouter_provider")
    importlib.reload(mod)
    assert "requests" not in sys.modules


def test_missing_key_raises_runtime_error_before_network():
    p = OpenRouterProvider(api_key=None)
    p.api_key = None  # ensure no env leak in the test environment
    with pytest.raises(RuntimeError):
        p.complete(LLMRequest(prompt="hi"))
    with pytest.raises(RuntimeError):
        p.chat([{"role": "user", "content": "hi"}])


def test_build_payload_matches_gemma_reasoning_format():
    p = OpenRouterProvider(api_key="k")
    payload = p._build_payload(
        LLMRequest(prompt="How many r's in strawberry?", system="You are precise.",
                   tier=ModelTier.BALANCED, max_tokens=256, temperature=0.3, stop=["END"])
    )
    assert payload["model"] == DEFAULT_MODEL
    assert payload["reasoning"] == {"enabled": True}
    assert payload["max_tokens"] == 256
    assert payload["temperature"] == 0.3
    assert payload["stop"] == ["END"]
    assert payload["messages"][0] == {"role": "system", "content": "You are precise."}
    assert payload["messages"][1] == {"role": "user", "content": "How many r's in strawberry?"}


def test_reasoning_can_be_disabled():
    p = OpenRouterProvider(api_key="k", reasoning=False)
    payload = p._build_payload(LLMRequest(prompt="hi"))
    assert "reasoning" not in payload


def test_per_tier_model_override():
    p = OpenRouterProvider(api_key="k", model="google/gemma-4-26b-a4b-it:free",
                           models={ModelTier.FRONTIER: "google/gemma-3-27b-it"})
    assert p.model_for(ModelTier.BALANCED) == "google/gemma-4-26b-a4b-it:free"
    assert p.model_for(ModelTier.FRONTIER) == "google/gemma-3-27b-it"


def test_complete_parses_response_and_captures_reasoning(monkeypatch):
    p = OpenRouterProvider(api_key="k")
    monkeypatch.setattr(p, "_post", lambda payload: _fake_response())
    resp = p.complete(LLMRequest(prompt="How many r's in strawberry?", tier=ModelTier.BALANCED))
    assert resp.text == "3 r's."
    assert resp.model == "google/gemma-4-26b-a4b-it:free"
    assert resp.input_tokens == 11 and resp.output_tokens == 7
    assert resp.tier == ModelTier.BALANCED
    # reasoning_details captured for continuation.
    assert p.last_reasoning_details == [{"type": "reasoning.text", "text": "The word strawberry has r-r-r."}]


def test_chat_preserves_reasoning_details_for_multi_turn(monkeypatch):
    p = OpenRouterProvider(api_key="k")
    calls = []

    def fake_post(payload):
        calls.append(payload)
        return _fake_response(content="There are 3.", reasoning="s-t-r-a-w-b-e-r-r-y -> 3 r")

    monkeypatch.setattr(p, "_post", fake_post)

    messages = [{"role": "user", "content": "How many r's are in 'strawberry'?"}]
    assistant = p.chat(messages)
    assert assistant["role"] == "assistant"
    assert assistant["content"] == "There are 3."
    assert assistant["reasoning_details"]  # present, to be passed back unmodified

    # Append the assistant turn WITH reasoning_details, then continue.
    messages.append(assistant)
    messages.append({"role": "user", "content": "Are you sure? Think carefully."})
    p.chat(messages)

    # The second request carried the preserved reasoning_details + reasoning enabled.
    assert calls[1]["reasoning"] == {"enabled": True}
    sent = calls[1]["messages"]
    assert sent[1]["role"] == "assistant"
    assert sent[1]["reasoning_details"] == assistant["reasoning_details"]
    assert sent[2]["content"] == "Are you sure? Think carefully."


def test_structured_output_parsed_when_schema_present(monkeypatch):
    p = OpenRouterProvider(api_key="k")
    schema = {"type": "object", "required": ["count"], "properties": {"count": {"type": "integer"}}}
    monkeypatch.setattr(p, "_post", lambda payload: {
        "model": DEFAULT_MODEL,
        "choices": [{"finish_reason": "stop", "message": {"content": '{"count": 3}'}}],
        "usage": {},
    })
    resp = p.complete(LLMRequest(prompt="count r's", response_schema=schema))
    assert resp.structured == {"count": 3}


def test_build_provider_openrouter_is_wrapped_and_conformant():
    p = build_provider("openrouter", api_key="k")
    assert isinstance(p, ports.LLMProvider)
    # build_provider wraps real adapters in caching for cost reuse.
    assert p.name == "openrouter"


def test_build_provider_rejects_unknown():
    with pytest.raises(ValueError):
        build_provider("not-a-provider")


def test_full_engine_narrative_through_openrouter(monkeypatch):
    """End-to-end: the engine drives Tier-2 narrative through the OpenRouter
    (Gemma) provider. The HTTP call is simulated so this stays offline, proving
    every link works except the actual network egress."""
    from matss.sim import build_engine
    from matss.domain.enums import EventType

    provider = OpenRouterProvider(api_key="test-key")

    def fake_post(payload):
        # Echo the model + a deterministic "Gemma" narration of the prompt.
        kind = "story" if payload["messages"][-1]["content"].startswith("Day") else "diary"
        return {
            "model": payload["model"],
            "choices": [{
                "finish_reason": "stop",
                "message": {
                    "content": f"[gemma {kind}] " + payload["messages"][-1]["content"][:40],
                    "reasoning_details": [{"type": "reasoning.text", "text": "thinking..."}],
                },
            }],
            "usage": {"prompt_tokens": 50, "completion_tokens": 60},
        }

    monkeypatch.setattr(provider, "_post", fake_post)

    engine = build_engine(seed=42, llm_provider=provider)
    engine.run_until_day(1)

    diaries = [e for e in engine.log.read() if e.type == EventType.DIARY_WRITTEN]
    stories = [e for e in engine.log.read() if e.type == EventType.STORY_COMPILED]
    assert len(diaries) == 6
    assert len(stories) == 1
    # The narrative text came from the (simulated) Gemma provider.
    assert all(d.payload["text"].startswith("[gemma diary]") for d in diaries)
    assert stories[0].payload["text"].startswith("[gemma story]")


def test_tier1_determinism_is_independent_of_llm_provider(monkeypatch):
    """Swapping the narrative provider must NOT change the Tier-1 state_hash chain."""
    from matss.sim import build_engine

    provider = OpenRouterProvider(api_key="test-key")
    monkeypatch.setattr(provider, "_post", lambda payload: {
        "model": payload["model"],
        "choices": [{"finish_reason": "stop", "message": {"content": "x"}}],
        "usage": {},
    })
    with_openrouter = build_engine(seed=42, llm_provider=provider).run_until_day(1)
    with_mock = build_engine(seed=42).run_until_day(1)
    assert with_openrouter == with_mock  # narrative provider is decoupled from Tier-1
