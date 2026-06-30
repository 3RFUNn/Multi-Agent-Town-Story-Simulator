"""Anthropic Messages API adapter implementing :class:`~matss.ports.LLMProvider`.

As with the OpenAI adapter, ``requests`` is imported lazily inside methods so the
module imports with no dependencies and no network access, and construction is
inert.

Two Anthropic-specific features are wired in:

* **Prompt caching** — when ``request.cache_prefix`` is set, the system prompt is
  split so the stable prefix carries a ``cache_control`` breakpoint, letting
  Anthropic reuse it across calls and bill it at the cached rate.
* **Structured output** — emulated via a single forced tool call whose
  ``input_schema`` is the requested ``response_schema``; the tool input is
  returned as the structured result.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence

from ...ports import LLMRequest, LLMResponse, ModelTier
from . import structured

# Default tier -> concrete Anthropic model mapping.
DEFAULT_MODELS: Dict[str, str] = {
    ModelTier.CHEAP: "claude-haiku-4-5",
    ModelTier.BALANCED: "claude-sonnet-4-6",
    ModelTier.FRONTIER: "claude-opus-4-8",
}

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
_STRUCTURED_TOOL_NAME = "emit_structured_output"


class AnthropicProvider:
    """Calls the Anthropic Messages API.

    Attributes:
        name: Provider name (``"anthropic"``).
        models: Effective tier -> model-name mapping.
    """

    name: str = "anthropic"

    def __init__(
        self,
        api_key: Optional[str] = None,
        models: Optional[Dict[str, str]] = None,
        base_url: str = _API_URL,
        timeout: float = 60.0,
    ) -> None:
        """Initialise the adapter (no network, no import of ``requests``).

        Args:
            api_key: API key; falls back to the ``ANTHROPIC_API_KEY`` env var.
            models: Optional override of the tier -> model mapping. Missing tiers
                inherit :data:`DEFAULT_MODELS`.
            base_url: Messages endpoint URL.
            timeout: Per-request timeout in seconds.
        """
        import os

        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.models: Dict[str, str] = {**DEFAULT_MODELS, **(models or {})}
        self.base_url = base_url
        self.timeout = float(timeout)

    def model_for(self, tier: str) -> str:
        """Return the concrete model name for ``tier`` (defaults to balanced)."""
        return self.models.get(tier, self.models[ModelTier.BALANCED])

    def _build_payload(self, request: LLMRequest) -> Dict[str, Any]:
        """Construct the Messages API JSON payload for ``request``."""
        payload: Dict[str, Any] = {
            "model": self.model_for(request.tier),
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [{"role": "user", "content": request.prompt}],
        }

        if request.system:
            if request.cache_prefix:
                # Split system into a cacheable prefix block + the remainder.
                blocks: List[Dict[str, Any]] = [
                    {
                        "type": "text",
                        "text": request.cache_prefix,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
                if request.system != request.cache_prefix:
                    blocks.append({"type": "text", "text": request.system})
                payload["system"] = blocks
            else:
                payload["system"] = request.system
        elif request.cache_prefix:
            payload["system"] = [
                {
                    "type": "text",
                    "text": request.cache_prefix,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        if request.stop:
            payload["stop_sequences"] = list(request.stop)

        if request.response_schema is not None:
            # Force a single tool call whose input schema is the response schema.
            payload["tools"] = [
                {
                    "name": _STRUCTURED_TOOL_NAME,
                    "description": "Return the structured result.",
                    "input_schema": request.response_schema,
                }
            ]
            payload["tool_choice"] = {"type": "tool", "name": _STRUCTURED_TOOL_NAME}

        return payload

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Execute one message completion against the Anthropic API.

        Args:
            request: The provider-agnostic request.

        Returns:
            The parsed :class:`LLMResponse`, including structured output when a
            ``response_schema`` was supplied.

        Raises:
            RuntimeError: If no API key is configured.
        """
        if not self.api_key:
            raise RuntimeError("AnthropicProvider requires an API key")
        import requests  # lazy: never imported at module load

        payload = self._build_payload(request)
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": _API_VERSION,
            "content-type": "application/json",
        }
        started = time.monotonic()
        resp = requests.post(
            self.base_url, headers=headers, json=payload, timeout=self.timeout
        )
        resp.raise_for_status()
        latency_ms = (time.monotonic() - started) * 1000.0
        return self._parse(resp.json(), request, latency_ms)

    def _parse(
        self, data: Dict[str, Any], request: LLMRequest, latency_ms: float
    ) -> LLMResponse:
        """Translate a raw Anthropic response body into an :class:`LLMResponse`."""
        text_parts: List[str] = []
        structured_out: Optional[Dict[str, Any]] = None
        for block in data.get("content", []):
            btype = block.get("type")
            if btype == "text":
                text_parts.append(block.get("text", ""))
            elif btype == "tool_use" and block.get("name") == _STRUCTURED_TOOL_NAME:
                raw = block.get("input", {})
                if request.response_schema is not None:
                    structured_out = structured.coerce(raw, request.response_schema)
                else:
                    structured_out = raw

        text = "".join(text_parts)
        if structured_out is not None and not text:
            import json

            text = json.dumps(structured_out, sort_keys=True)

        usage = data.get("usage", {})
        return LLMResponse(
            text=text,
            model=data.get("model", self.model_for(request.tier)),
            tier=request.tier,
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
            cached_input_tokens=int(usage.get("cache_read_input_tokens", 0)),
            cached=False,
            structured=structured_out,
            latency_ms=latency_ms,
            finish_reason=data.get("stop_reason", "stop") or "stop",
        )

    def batch(self, requests: Sequence[LLMRequest]) -> List[LLMResponse]:
        """Complete each request sequentially (synchronous API)."""
        return [self.complete(r) for r in requests]
