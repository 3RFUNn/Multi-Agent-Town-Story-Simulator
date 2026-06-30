"""OpenAI chat-completions adapter implementing :class:`~matss.ports.LLMProvider`.

The HTTP client (``requests``) is imported lazily *inside* the calling methods so
that importing this module never requires the dependency or touches the network —
a hard rule of the engine, which must import and run fully offline with mock
providers. Constructing an :class:`OpenAIProvider` is likewise inert: it only
records configuration.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Sequence

from ...config.env import resolve_api_key
from ...ports import LLMRequest, LLMResponse, ModelTier
from . import structured

# Default tier -> concrete OpenAI model mapping.
DEFAULT_MODELS: Dict[str, str] = {
    ModelTier.CHEAP: "gpt-4.1-mini",
    ModelTier.BALANCED: "gpt-4.1",
    ModelTier.FRONTIER: "o4-mini",
}

_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider:
    """Calls the OpenAI Chat Completions API.

    Attributes:
        name: Provider name (``"openai"``).
        models: Effective tier -> model-name mapping.
    """

    name: str = "openai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        models: Optional[Dict[str, str]] = None,
        base_url: str = _API_URL,
        timeout: float = 60.0,
    ) -> None:
        """Initialise the adapter (no network, no import of ``requests``).

        Args:
            api_key: API key; falls back to the ``OPENAI_API_KEY`` env var. May be
                ``None`` at construction time (only needed when a call is made).
            models: Optional override of the tier -> model mapping. Missing tiers
                inherit :data:`DEFAULT_MODELS`.
            base_url: Chat-completions endpoint URL.
            timeout: Per-request timeout in seconds.
        """
        self.api_key = resolve_api_key(api_key, ["OPENAI_API_KEY", "API_KEY"])
        self.models: Dict[str, str] = {**DEFAULT_MODELS, **(models or {})}
        self.base_url = base_url
        self.timeout = float(timeout)

    def model_for(self, tier: str) -> str:
        """Return the concrete model name for ``tier`` (defaults to balanced)."""
        return self.models.get(tier, self.models[ModelTier.BALANCED])

    def _build_payload(self, request: LLMRequest) -> Dict[str, Any]:
        """Construct the chat-completions JSON payload for ``request``."""
        messages: List[Dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})

        payload: Dict[str, Any] = {
            "model": self.model_for(request.tier),
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.stop:
            payload["stop"] = list(request.stop)
        if request.response_schema is not None:
            # Map to OpenAI Structured Outputs (json_schema response format).
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_output",
                    "schema": request.response_schema,
                    "strict": True,
                },
            }
        return payload

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Execute one chat completion against the OpenAI API.

        Args:
            request: The provider-agnostic request.

        Returns:
            The parsed :class:`LLMResponse`, including structured output when a
            ``response_schema`` was supplied.

        Raises:
            RuntimeError: If no API key is configured.
        """
        if not self.api_key:
            raise RuntimeError("OpenAIProvider requires an API key")
        import requests  # lazy: never imported at module load

        payload = self._build_payload(request)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        started = time.monotonic()
        resp = requests.post(
            self.base_url, headers=headers, json=payload, timeout=self.timeout
        )
        resp.raise_for_status()
        latency_ms = (time.monotonic() - started) * 1000.0
        data = resp.json()
        return self._parse(data, request, latency_ms)

    def _parse(
        self, data: Dict[str, Any], request: LLMRequest, latency_ms: float
    ) -> LLMResponse:
        """Translate a raw OpenAI response body into an :class:`LLMResponse`."""
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message", {})
        text = message.get("content", "") or ""
        usage = data.get("usage", {})

        structured_out: Optional[Dict[str, Any]] = None
        if request.response_schema is not None and text:
            try:
                parsed = json.loads(text)
                structured_out = structured.coerce(parsed, request.response_schema)
            except (ValueError, TypeError):
                structured_out = None

        return LLMResponse(
            text=text,
            model=data.get("model", self.model_for(request.tier)),
            tier=request.tier,
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
            cached_input_tokens=int(
                usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
            ),
            cached=False,
            structured=structured_out,
            latency_ms=latency_ms,
            finish_reason=choice.get("finish_reason", "stop") or "stop",
        )

    def batch(self, requests: Sequence[LLMRequest]) -> List[LLMResponse]:
        """Complete each request sequentially (synchronous API)."""
        return [self.complete(r) for r in requests]
