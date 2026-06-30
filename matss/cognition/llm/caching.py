"""A caching decorator over any :class:`~matss.ports.LLMProvider`.

Generative-agent simulations re-issue near-identical prompts constantly (the same
persona + world preamble, the same reflexive question). Caching deduplicates
them, which is both a cost lever and — because the mock provider is deterministic
— a way to make repeated runs cheaper without changing results.

The cache key is the tuple ``(cache_prefix, system, prompt, schema-json)``: two
requests that would produce the same completion share an entry. On a hit the
stored response is returned with ``cached=True`` and the inner provider is *not*
called.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Sequence, Tuple

from dataclasses import replace

from ...ports import LLMProvider, LLMRequest, LLMResponse

_CacheKey = Tuple[str, str, str, str]


def _key_for(request: LLMRequest) -> _CacheKey:
    """Build the canonical cache key for ``request``."""
    schema_json = ""
    if request.response_schema is not None:
        schema_json = json.dumps(request.response_schema, sort_keys=True)
    return (
        request.cache_prefix or "",
        request.system or "",
        request.prompt,
        schema_json,
    )


class CachingLLMProvider:
    """Wraps a provider with an in-memory, exact-match response cache.

    Attributes:
        name: The wrapped provider's name (delegated).
        hits: Number of cache hits observed.
        misses: Number of cache misses (i.e. inner calls) observed.
    """

    def __init__(self, inner: LLMProvider, max_entries: Optional[int] = None) -> None:
        """Initialise the cache.

        Args:
            inner: The provider to delegate misses to.
            max_entries: Optional soft cap on stored entries; when exceeded the
                oldest insertion is evicted (FIFO). ``None`` means unbounded.
        """
        self._inner = inner
        self._cache: Dict[_CacheKey, LLMResponse] = {}
        self._max_entries = max_entries
        self.hits = 0
        self.misses = 0

    @property
    def name(self) -> str:
        return getattr(self._inner, "name", "caching")

    @property
    def hit_rate(self) -> float:
        """Fraction of :meth:`complete` calls served from cache (``0.0`` if none)."""
        total = self.hits + self.misses
        return self.hits / total if total else 0.0

    def __len__(self) -> int:
        """Number of cached entries currently held."""
        return len(self._cache)

    def clear(self) -> None:
        """Drop all cached entries and reset hit/miss counters."""
        self._cache.clear()
        self.hits = 0
        self.misses = 0

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Return a cached response if present, otherwise delegate and store it.

        Args:
            request: The request to complete.

        Returns:
            On a cache hit, the stored :class:`LLMResponse` with ``cached=True``.
            On a miss, the inner provider's response (stored for next time).
        """
        key = _key_for(request)
        cached = self._cache.get(key)
        if cached is not None:
            self.hits += 1
            return replace(cached, cached=True)

        self.misses += 1
        response = self._inner.complete(request)
        self._store(key, response)
        return response

    def _store(self, key: _CacheKey, response: LLMResponse) -> None:
        """Insert ``response`` under ``key``, honouring the FIFO cap."""
        if (
            self._max_entries is not None
            and key not in self._cache
            and len(self._cache) >= self._max_entries
        ):
            # Evict the oldest entry (insertion-ordered dict).
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = response

    def batch(self, requests: Sequence[LLMRequest]) -> List[LLMResponse]:
        """Complete each request through the cache via :meth:`complete`."""
        return [self.complete(r) for r in requests]
