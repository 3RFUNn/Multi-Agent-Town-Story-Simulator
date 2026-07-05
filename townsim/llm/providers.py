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
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout)
        self._model = model
        self._embed_model = embed_model
        self._transient = (RateLimitError, APITimeoutError, APIConnectionError, APIStatusError)

    async def complete(self, prompt: str, *, max_tokens: int, temperature: float) -> str:
        try:
            rsp = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except self._transient as exc:
            raise TransientLLMError(str(exc)) from exc
        content = rsp.choices[0].message.content
        if not content or not content.strip():
            raise TransientLLMError("empty completion")  # F34: validate output shape
        return content

    async def embed(self, text: str) -> list[float]:
        try:
            rsp = await self._client.embeddings.create(model=self._embed_model, input=text)
        except self._transient as exc:
            raise TransientLLMError(str(exc)) from exc
        return rsp.data[0].embedding


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
        api_key = cfg.resolve_api_key()
        if not api_key:
            raise RuntimeError(
                f"LLM provider 'openai' selected but neither {cfg.api_key_env} nor "
                f"{cfg.legacy_api_key_env} is set")
        return OpenAIProvider(api_key=api_key, model=cfg.model,
                              embed_model=cfg.embed_model, timeout=cfg.request_timeout_s)
    if provider == "fake":
        return FakeProvider()
    raise ValueError(f"unknown LLM provider: {provider!r}")
