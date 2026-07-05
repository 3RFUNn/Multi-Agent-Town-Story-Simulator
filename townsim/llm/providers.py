"""LLM providers behind one Protocol (F49: real provider abstraction).

- OpenAIProvider: official AsyncOpenAI SDK with explicit timeout.
- FakeProvider: deterministic, offline, zero-cost. Used for tests, demos
  without an API key, and the golden-replay determinism guarantee.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from typing import Protocol

import structlog

log = structlog.get_logger(__name__)


class TransientLLMError(Exception):
    """Rate limits, 5xx, timeouts — safe to retry."""


class LLMProvider(Protocol):
    name: str

    async def complete(self, prompt: str, *, max_tokens: int, temperature: float) -> str: ...
    async def embed(self, text: str) -> list[float]: ...


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini",
                 embed_model: str = "text-embedding-3-small", timeout: float = 60.0) -> None:
        from openai import (
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            AsyncOpenAI,
            RateLimitError,
        )
        # max_retries=0: the gateway owns retry policy (paced, backoff-capped);
        # the SDK's hidden internal retries would multiply the real request
        # rate and defeat rate-limit pacing.
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout, max_retries=0)
        self._model = model
        self._embed_model = embed_model
        self._transient = (RateLimitError, APITimeoutError, APIConnectionError)
        self._status_error = APIStatusError

    def _classify(self, exc: Exception) -> Exception:
        """R12: only rate limits, timeouts, connection errors, and 5xx are
        retryable; 4xx client errors (bad key, bad model, ...) must surface
        immediately instead of burning retries."""
        if isinstance(exc, self._transient):
            return TransientLLMError(str(exc))
        if isinstance(exc, self._status_error) and getattr(exc, "status_code", 0) >= 500:
            return TransientLLMError(str(exc))
        return exc

    async def complete(self, prompt: str, *, max_tokens: int, temperature: float) -> str:
        try:
            rsp = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            raise self._classify(exc) from exc
        content = rsp.choices[0].message.content
        if not content or not content.strip():
            raise TransientLLMError("empty completion")  # F34: validate output shape
        return content

    async def embed(self, text: str) -> list[float]:
        try:
            rsp = await self._client.embeddings.create(model=self._embed_model, input=text)
        except Exception as exc:
            raise self._classify(exc) from exc
        return rsp.data[0].embedding


class OpenRouterProvider:
    """OpenRouter (openrouter.ai) — OpenAI-compatible chat completions with
    any hosted model (e.g. google/gemma-4-31b-it:free).

    Fallback strategy: the full pool of ``:free`` models is discovered from
    GET /models at first use (configured primary + fallbacks stay at the
    head of the list). Every request sends a window of 3 candidates via the
    OpenRouter ``models`` routing array (the API caps it at 3), so a
    saturated model falls through to a backup INSIDE the same request; when
    the whole window fails transiently, the window rotates so the gateway's
    retry immediately targets 3 fresh models. A window that succeeds stays
    put, so traffic sticks with whatever pool is currently healthy.

    Notes:
    - `reasoning={"enabled": true}` is passed via extra_body per the
      OpenRouter API; models that don't support it simply ignore it.
      townsim's calls are single-turn, so the multi-turn reasoning_details
      pass-back from the OpenRouter docs does not apply here.
    - OpenRouter has no embeddings endpoint, so embed() returns local
      deterministic hash vectors (same scheme as FakeProvider) — enough for
      the semantic cache and retrieval to keep functioning.
    """

    name = "openrouter"
    EMBED_DIM = 32
    ROUTE_WINDOW = 3          # hard OpenRouter cap on the `models` array
    MIN_CONTEXT = 8000        # skip free models too small for diary/story prompts
    DISCOVERY_TIMEOUT = 10.0  # a hung /models GET must not eat a completion slot
    DISCOVERY_COOLDOWN = 60.0  # after a failed discovery, don't re-fetch for this long
    # Specialty models that emit labels/scores instead of prose — never
    # acceptable as narrative fallbacks even when technically "text out".
    SPECIALTY_PATTERN = re.compile(r"guard|safety|moderat|rerank|embed|classif", re.IGNORECASE)

    def __init__(self, api_key: str, model: str = "google/gemma-4-31b-it:free",
                 base_url: str = "https://openrouter.ai/api/v1",
                 timeout: float = 60.0, reasoning: bool = True,
                 fallback_models: list[str] | None = None,
                 auto_free_models: bool = True) -> None:
        from openai import (
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            AsyncOpenAI,
            RateLimitError,
        )
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout,
                                   max_retries=0,  # gateway owns retries (see OpenAIProvider)
                                   default_headers={
                                       "HTTP-Referer": "https://github.com/3RFUNn/Multi-Agent-Town-Story-Simulator",
                                       "X-Title": "Multi-Agent Town Story Simulator",
                                   })
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._model = model
        self._fallback_models = list(fallback_models or [])
        self._auto_free_models = auto_free_models
        self._reasoning = reasoning
        self._transient = (RateLimitError, APITimeoutError, APIConnectionError)
        self._status_error = APIStatusError
        self._candidates: list[str] | None = None   # resolved lazily (None until discovery)
        self._rotation = 0
        self._discovery_lock = asyncio.Lock()
        self._discovery_warned = False
        self._next_discovery_at = 0.0   # loop-time gate after a failed discovery

    def _classify(self, exc: Exception) -> Exception:
        if isinstance(exc, self._transient):
            return TransientLLMError(str(exc))
        if isinstance(exc, self._status_error) and getattr(exc, "status_code", 0) >= 500:
            return TransientLLMError(str(exc))
        return exc

    # ---------------------------------------------------------- free-model pool
    def _configured_models(self) -> list[str]:
        seen: dict[str, None] = {}
        for model_id in (self._model, *self._fallback_models):
            seen.setdefault(model_id)
        return list(seen)

    @classmethod
    def _free_model_ids(cls, payload: dict) -> list[str]:
        """Filter a GET /models payload down to usable :free chat models,
        preserving the API's order."""
        ids: list[str] = []
        for item in payload.get("data") or []:
            model_id = item.get("id") or ""
            if not model_id.endswith(":free"):
                continue
            if cls.SPECIALTY_PATTERN.search(model_id):
                continue
            arch = item.get("architecture") or {}
            out_modalities = arch.get("output_modalities") or []
            if out_modalities and "text" not in out_modalities:
                continue
            context = item.get("context_length")
            if isinstance(context, (int, float)) and context < cls.MIN_CONTEXT:
                continue
            ids.append(model_id)
        return ids

    async def _fetch_models_payload(self) -> dict:
        import httpx
        timeout = min(self._timeout, self.DISCOVERY_TIMEOUT)
        async with httpx.AsyncClient(timeout=timeout) as client:
            rsp = await client.get(f"{self._base_url}/models")
            rsp.raise_for_status()
            return rsp.json()

    async def _resolve_candidates(self) -> list[str]:
        """Configured models first, then every other discovered :free model.
        Discovery failure degrades to the configured list and is retried
        after a cooldown — never per-call, or a hung /models endpoint would
        serialize every completion behind its timeout."""
        configured = self._configured_models()
        if not self._auto_free_models:
            return configured
        if self._candidates is not None:
            return self._candidates
        async with self._discovery_lock:
            if self._candidates is not None:    # raced with another worker
                return self._candidates
            now = asyncio.get_running_loop().time()
            if now < self._next_discovery_at:   # cooling down after a failure
                return configured
            try:
                discovered = self._free_model_ids(await self._fetch_models_payload())
            except Exception as exc:
                self._next_discovery_at = now + self.DISCOVERY_COOLDOWN
                if not self._discovery_warned:
                    self._discovery_warned = True
                    log.warning("free-model discovery failed; using configured models",
                                error=str(exc), retry_in_s=self.DISCOVERY_COOLDOWN)
                return configured
            pool = configured + [m for m in discovered if m not in set(configured)]
            self._candidates = pool
            log.info("openrouter free-model pool", models=len(pool), primary=self._model)
            return pool

    def _window(self, candidates: list[str]) -> list[str]:
        if len(candidates) <= self.ROUTE_WINDOW:
            return list(candidates)
        start = self._rotation % len(candidates)
        return [candidates[(start + i) % len(candidates)]
                for i in range(self.ROUTE_WINDOW)]

    # -------------------------------------------------------------- completion
    async def complete(self, prompt: str, *, max_tokens: int, temperature: float) -> str:
        candidates = await self._resolve_candidates()
        rotation_at_dispatch = self._rotation
        window = self._window(candidates)
        extra_body: dict = {}
        if self._reasoning:
            extra_body["reasoning"] = {"enabled": True}
        if len(window) > 1:
            # OpenRouter natively falls through this list within one request.
            extra_body["models"] = window
        try:
            rsp = await self._client.chat.completions.create(
                model=window[0],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                extra_body=extra_body,
            )
            if not rsp.choices:
                raise TransientLLMError("no choices in response")
            content = rsp.choices[0].message.content
            if not content or not content.strip():
                raise TransientLLMError("empty completion")
            return content
        except Exception as exc:
            classified = exc if isinstance(exc, TransientLLMError) else self._classify(exc)
            if isinstance(classified, TransientLLMError) and self._rotation == rotation_at_dispatch:
                # The whole window struck out — the gateway's retry should
                # instantly land on the next 3 backup models, not re-hit
                # the same saturated pools. Compare-and-set: concurrent
                # callers that dispatched the SAME window advance it once,
                # not once each (which would skip never-tried windows).
                self._rotation = rotation_at_dispatch + len(window)
            if classified is exc:
                raise
            raise classified from exc

    async def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [(b - 127.5) / 127.5 for b in digest[: self.EMBED_DIM]]


class FakeProvider:
    """Deterministic offline provider. Diary/story output is synthesized from
    the prompt's own bullet lines, so narratives remain grounded in the
    journal even without a real model. Embeddings are stable hash vectors."""

    name = "fake"
    EMBED_DIM = 32

    async def complete(self, prompt: str, *, max_tokens: int, temperature: float) -> str:
        if "ONLY a JSON object" in prompt:
            return self._fake_json(prompt)
        # Only mine fact bullets from the prompt body, not instruction lists.
        body_lines: list[str] = []
        for line in prompt.splitlines():
            if line.startswith("Write ") or line.strip() == "Requirements:":
                break
            body_lines.append(line)
        bullets = [line.strip("- ").strip() for line in body_lines
                   if line.strip().startswith("- ") and "(" not in line[:4]]
        who = self._extract(prompt, r"You are ([^,\n]+),") or "someone in town"
        day = self._extract(prompt, r"(?:Today is|for) (\w+day)") or "today"
        if bullets:
            body = " ".join(bullets[:14])
            return (f"[offline narrative] {who} — {day}. {body} "
                    f"All in all, a full day; tomorrow will bring more.")
        return f"[offline narrative] {who} passed {day} quietly, and the town carried on."

    async def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [(b - 127.5) / 127.5 for b in digest[: self.EMBED_DIM]]

    @staticmethod
    def _extract(text: str, pattern: str) -> str | None:
        match = re.search(pattern, text)
        return match.group(1) if match else None

    @staticmethod
    def _fake_json(prompt: str) -> str:
        """Minimal schema-shaped reflection output (deterministic)."""
        seed = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16)
        moods = ["settled", "upbeat", "wistful", "focused", "restless"]
        return json.dumps({
            "mood": moods[seed % len(moods)],
            "insights": ["The days have a steady rhythm lately."],
            "goal_adjustments": [{"goal": "social", "delta": round(((seed % 5) - 2) * 0.05, 2)}],
            "schedule_proposals": [],
        })


def build_provider(cfg) -> LLMProvider:
    """cfg: townsim.config.models.LLMConfig"""
    provider = cfg.resolve_provider()
    if provider == "openai":
        api_key = cfg.resolve_api_key("openai")
        if not api_key:
            raise RuntimeError(
                f"LLM provider 'openai' selected but neither {cfg.api_key_env} nor "
                f"{cfg.legacy_api_key_env} is set")
        return OpenAIProvider(api_key=api_key, model=cfg.model,
                              embed_model=cfg.embed_model, timeout=cfg.request_timeout_s)
    if provider == "openrouter":
        api_key = cfg.resolve_api_key("openrouter")
        if not api_key:
            raise RuntimeError(
                f"LLM provider 'openrouter' selected but {cfg.openrouter_api_key_env} is not set")
        return OpenRouterProvider(api_key=api_key, model=cfg.openrouter_model,
                                  base_url=cfg.openrouter_base_url,
                                  timeout=cfg.request_timeout_s, reasoning=cfg.reasoning,
                                  fallback_models=cfg.openrouter_fallback_models,
                                  auto_free_models=cfg.openrouter_auto_free_models)
    if provider == "fake":
        return FakeProvider()
    raise ValueError(f"unknown LLM provider: {provider!r}")
