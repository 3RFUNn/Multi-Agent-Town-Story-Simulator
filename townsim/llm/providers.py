"""LLM providers behind one Protocol (F49: real provider abstraction).

- OpenAIProvider: official AsyncOpenAI SDK with explicit timeout.
- FakeProvider: deterministic, offline, zero-cost. Used for tests, demos
  without an API key, and the golden-replay determinism guarantee.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Protocol


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

    def __init__(self, api_key: str, model: str = "google/gemma-4-31b-it:free",
                 base_url: str = "https://openrouter.ai/api/v1",
                 timeout: float = 60.0, reasoning: bool = True,
                 fallback_models: list[str] | None = None) -> None:
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
        self._model = model
        self._fallback_models = list(fallback_models or [])
        self._reasoning = reasoning
        self._transient = (RateLimitError, APITimeoutError, APIConnectionError)
        self._status_error = APIStatusError

    def _classify(self, exc: Exception) -> Exception:
        if isinstance(exc, self._transient):
            return TransientLLMError(str(exc))
        if isinstance(exc, self._status_error) and getattr(exc, "status_code", 0) >= 500:
            return TransientLLMError(str(exc))
        return exc

    async def complete(self, prompt: str, *, max_tokens: int, temperature: float) -> str:
        extra_body: dict = {}
        if self._reasoning:
            extra_body["reasoning"] = {"enabled": True}
        if self._fallback_models:
            # OpenRouter routes to the first available model in this list
            # when earlier ones are saturated/erroring. The API caps the
            # array at 3 items total.
            extra_body["models"] = [self._model, *self._fallback_models][:3]
        try:
            rsp = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                extra_body=extra_body,
            )
        except Exception as exc:
            raise self._classify(exc) from exc
        if not rsp.choices:
            raise TransientLLMError("no choices in response")
        content = rsp.choices[0].message.content
        if not content or not content.strip():
            raise TransientLLMError("empty completion")
        return content

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
                                  fallback_models=cfg.openrouter_fallback_models)
    if provider == "fake":
        return FakeProvider()
    raise ValueError(f"unknown LLM provider: {provider!r}")
