"""Async LLM gateway: retries, bounded concurrency, semantic cache, and
schema-validated structured output (fixes F01/F02/F03/F34 by construction —
the kernel never awaits this; only cognition workers do)."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import TypeVar

import numpy as np
import structlog
from pydantic import BaseModel, ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from townsim.llm.providers import LLMProvider, TransientLLMError

log = structlog.get_logger(__name__)
T = TypeVar("T", bound=BaseModel)


@dataclass
class SemanticCache:
    """Reuses responses for near-duplicate prompts (cosine >= threshold)."""
    threshold: float = 0.97
    max_entries: int = 512
    _keys: list[np.ndarray] = field(default_factory=list)
    _values: list[str] = field(default_factory=list)

    def get(self, embedding: list[float]) -> str | None:
        if not self._keys:
            return None
        q = np.asarray(embedding, dtype=float)
        norm = np.linalg.norm(q)
        if norm == 0:
            return None
        q = q / norm
        matrix = np.stack(self._keys)
        scores = matrix @ q
        best = int(np.argmax(scores))
        return self._values[best] if float(scores[best]) >= self.threshold else None

    def put(self, embedding: list[float], value: str) -> None:
        v = np.asarray(embedding, dtype=float)
        norm = np.linalg.norm(v)
        if norm == 0:
            return
        if len(self._keys) >= self.max_entries:
            self._keys.pop(0)
            self._values.pop(0)
        self._keys.append(v / norm)
        self._values.append(value)


class LLMGateway:
    def __init__(self, provider: LLMProvider, *, max_concurrency: int = 4,
                 max_attempts: int = 4, retry_max_wait_s: float = 30.0,
                 requests_per_minute: float = 0,
                 cache: SemanticCache | None = None) -> None:
        self.provider = provider
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._max_attempts = max_attempts
        self._retry_max_wait_s = retry_max_wait_s
        # Client-side pacing for strict provider quotas (e.g. OpenRouter's
        # :free tier at 16 req/min): space requests evenly instead of
        # bursting into 429s.
        self._min_interval = 60.0 / requests_per_minute if requests_per_minute > 0 else 0.0
        self._pace_lock = asyncio.Lock()
        self._next_slot = 0.0
        self._cache = cache
        self.stats = {"calls": 0, "retries": 0, "cache_hits": 0, "failures": 0}

    async def _pace(self) -> None:
        if not self._min_interval:
            return
        loop = asyncio.get_running_loop()
        async with self._pace_lock:
            now = loop.time()
            wait = self._next_slot - now
            self._next_slot = max(now, self._next_slot) + self._min_interval
        if wait > 0:
            await asyncio.sleep(wait)

    async def _complete_raw(self, prompt: str, max_tokens: int, temperature: float) -> str:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(TransientLLMError),
            wait=wait_exponential_jitter(initial=2, max=self._retry_max_wait_s),
            stop=stop_after_attempt(self._max_attempts),
            reraise=True,
        ):
            with attempt:
                if attempt.retry_state.attempt_number > 1:
                    self.stats["retries"] += 1
                async with self._semaphore:
                    await self._pace()
                    self.stats["calls"] += 1
                    return await self.provider.complete(
                        prompt, max_tokens=max_tokens, temperature=temperature)
        raise RuntimeError("unreachable")  # pragma: no cover

    async def complete(self, prompt: str, *, max_tokens: int = 1024,
                       temperature: float = 0.8, cacheable: bool = False) -> str:
        embedding: list[float] | None = None
        if cacheable and self._cache is not None:
            try:
                embedding = await self.provider.embed(prompt)
            except TransientLLMError:
                embedding = None
            if embedding is not None:
                hit = self._cache.get(embedding)
                if hit is not None:
                    self.stats["cache_hits"] += 1
                    return hit
        try:
            text = await self._complete_raw(prompt, max_tokens, temperature)
        except Exception:
            self.stats["failures"] += 1
            raise
        if embedding is not None:
            self._cache.put(embedding, text)
        return text

    async def embed(self, text: str) -> list[float] | None:
        try:
            return await self.provider.embed(text)
        except TransientLLMError:
            log.warning("embedding failed", provider=self.provider.name)
            return None

    async def complete_structured(self, prompt: str, schema: type[T], *,
                                  max_tokens: int = 800, attempts: int = 3) -> T:
        """LLM output -> validated Pydantic model, re-prompting on invalid JSON."""
        suffix = ("\nRespond with ONLY a JSON object matching this schema "
                  "(no prose, no markdown):\n"
                  + json.dumps(schema.model_json_schema(), indent=2))
        feedback = ""
        last_error: Exception | None = None
        for _ in range(attempts):
            raw = await self.complete(prompt + suffix + feedback,
                                      max_tokens=max_tokens, temperature=0.2)
            try:
                start, end = raw.find("{"), raw.rfind("}") + 1
                if start < 0 or end <= start:
                    raise ValueError("no JSON object in response")
                return schema.model_validate_json(raw[start:end])
            except (ValidationError, ValueError) as exc:
                last_error = exc
                feedback = f"\nYour previous answer failed validation: {exc}. Return corrected JSON only."
        raise ValueError(
            f"LLM output failed {schema.__name__} validation after {attempts} attempts"
        ) from last_error
