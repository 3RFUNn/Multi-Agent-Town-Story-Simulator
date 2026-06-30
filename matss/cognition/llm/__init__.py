"""Provider-agnostic LLM stack for MATSS v2 cognition.

This package replaces the prototype's raw ``requests.post`` (no retries, no
timeout, no caching, no routing) with a composable set of adapters, each
implementing the frozen :class:`matss.ports.LLMProvider` contract:

* :class:`MockLLMProvider` — deterministic, offline provider for tests/sim.
* :class:`RetryingProvider` — exponential-backoff retries around any provider.
* :class:`CachingLLMProvider` — exact-match response cache with hit-rate stats.
* :class:`BatchingLLMProvider` — submit/flush batch ergonomics over a provider.
* :class:`TieredRouter` — cost/quality routing by :class:`matss.ports.ModelTier`.
* :class:`OpenAIProvider` / :class:`AnthropicProvider` / :class:`OpenRouterProvider`
  — real HTTP adapters that lazy-import ``requests`` and never touch the network
  at import time. :class:`OpenRouterProvider` defaults to Google Gemma with the
  reasoning format (``reasoning: {"enabled": true}`` + ``reasoning_details``).

The :mod:`matss.cognition.llm.structured` helpers validate/coerce structured
output against a minimal JSON-schema subset.

These adapters are composable wrappers: e.g.
``CachingLLMProvider(RetryingProvider(TieredRouter({...})))``. :func:`build_provider`
is a convenience factory that wires a named provider with retries + caching.
"""

from __future__ import annotations

from typing import Optional

from .mock import MockLLMProvider
from .retry import RetryingProvider
from .caching import CachingLLMProvider
from .batching import BatchingLLMProvider
from .router import TieredRouter
from .openai_provider import OpenAIProvider, DEFAULT_MODELS as OPENAI_DEFAULT_MODELS
from .anthropic_provider import (
    AnthropicProvider,
    DEFAULT_MODELS as ANTHROPIC_DEFAULT_MODELS,
)
from .openrouter_provider import OpenRouterProvider, DEFAULT_MODEL as OPENROUTER_DEFAULT_MODEL
from .structured import (
    build_stub,
    coerce,
    required_keys,
    satisfies,
    stub_value,
    validate,
    SchemaError,
)


def build_provider(name: str = "mock", *, model: Optional[str] = None, **kwargs):
    """Build a ready-to-use LLM provider by name, with retries + caching.

    Args:
        name: One of ``"mock"``, ``"openrouter"``, ``"openai"``, ``"anthropic"``.
        model: Optional default model id override (for the real adapters).
        **kwargs: Passed through to the underlying provider constructor.

    Returns:
        A :class:`matss.ports.LLMProvider`. Real adapters are wrapped in
        ``CachingLLMProvider(RetryingProvider(...))`` for cost + resilience; the
        mock is returned bare (it is already deterministic and free).

    Raises:
        ValueError: If ``name`` is not a known provider.
    """
    key = name.lower()
    if key == "mock":
        return MockLLMProvider(**kwargs)
    if key == "openrouter":
        base = OpenRouterProvider(model=model or OPENROUTER_DEFAULT_MODEL, **kwargs)
    elif key == "openai":
        base = OpenAIProvider(**kwargs)
    elif key == "anthropic":
        base = AnthropicProvider(**kwargs)
    else:
        raise ValueError(
            f"unknown LLM provider {name!r}; choose mock/openrouter/openai/anthropic"
        )
    return CachingLLMProvider(RetryingProvider(base))


__all__ = [
    "MockLLMProvider",
    "RetryingProvider",
    "CachingLLMProvider",
    "BatchingLLMProvider",
    "TieredRouter",
    "OpenAIProvider",
    "AnthropicProvider",
    "OpenRouterProvider",
    "OPENAI_DEFAULT_MODELS",
    "ANTHROPIC_DEFAULT_MODELS",
    "OPENROUTER_DEFAULT_MODEL",
    "build_provider",
    # structured helpers
    "build_stub",
    "coerce",
    "required_keys",
    "satisfies",
    "stub_value",
    "validate",
    "SchemaError",
]
