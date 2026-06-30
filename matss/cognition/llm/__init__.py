"""Provider-agnostic LLM stack for MATSS v2 cognition.

This package replaces the prototype's raw ``requests.post`` (no retries, no
timeout, no caching, no routing) with a composable set of adapters, each
implementing the frozen :class:`matss.ports.LLMProvider` contract:

* :class:`MockLLMProvider` — deterministic, offline provider for tests/sim.
* :class:`RetryingProvider` — exponential-backoff retries around any provider.
* :class:`CachingLLMProvider` — exact-match response cache with hit-rate stats.
* :class:`BatchingLLMProvider` — submit/flush batch ergonomics over a provider.
* :class:`TieredRouter` — cost/quality routing by :class:`matss.ports.ModelTier`.
* :class:`OpenAIProvider` / :class:`AnthropicProvider` — real HTTP adapters that
  lazy-import ``requests`` and never touch the network at import time.

The :mod:`matss.cognition.llm.structured` helpers validate/coerce structured
output against a minimal JSON-schema subset.

These adapters are composable wrappers: e.g.
``CachingLLMProvider(RetryingProvider(TieredRouter({...})))``.
"""

from __future__ import annotations

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
from .structured import (
    build_stub,
    coerce,
    required_keys,
    satisfies,
    stub_value,
    validate,
    SchemaError,
)

__all__ = [
    "MockLLMProvider",
    "RetryingProvider",
    "CachingLLMProvider",
    "BatchingLLMProvider",
    "TieredRouter",
    "OpenAIProvider",
    "AnthropicProvider",
    "OPENAI_DEFAULT_MODELS",
    "ANTHROPIC_DEFAULT_MODELS",
    # structured helpers
    "build_stub",
    "coerce",
    "required_keys",
    "satisfies",
    "stub_value",
    "validate",
    "SchemaError",
]
