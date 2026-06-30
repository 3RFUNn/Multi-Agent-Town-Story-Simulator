"""OpenRouter chat-completions adapter (Google Gemma + reasoning).

Implements :class:`~matss.ports.LLMProvider` against the OpenRouter API, using the
reasoning-enabled request format and preserving ``reasoning_details`` so a
conversation can continue the model's reasoning across turns:

    POST https://openrouter.ai/api/v1/chat/completions
    {
      "model": "google/gemma-4-26b-a4b-it:free",
      "messages": [...],
      "reasoning": {"enabled": true}
    }

As with the other adapters, ``requests`` is imported lazily inside the calling
methods (never at module import), the API key is validated *before* that import,
and the key is read from the ``OPENROUTER_API_KEY`` environment variable when not
passed explicitly. Constructing the provider is inert (no network, no key needed).

Two entry points:

* :meth:`complete` — the provider-agnostic single-shot call used by the engine's
  Tier-2 narrative (returns an :class:`~matss.ports.LLMResponse`).
* :meth:`chat` — a lower-level multi-turn call that returns the assistant message
  dict including ``reasoning_details``, so callers can append it back unmodified
  and continue the reasoning (the exact OpenRouter pattern).
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Sequence

from ...config.env import resolve_api_key
from ...ports import LLMRequest, LLMResponse, ModelTier
from . import structured

#: Default model. Gemma is a single model used for every capability tier unless a
#: per-tier override is supplied via ``models=``.
DEFAULT_MODEL = "google/gemma-4-26b-a4b-it:free"

_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider:
    """Calls the OpenRouter Chat Completions API (default model: Google Gemma).

    Attributes:
        name: Provider name (``"openrouter"``).
        default_model: Model used when a tier has no explicit override.
        models: Optional tier -> model overrides.
        reasoning: Whether to send ``reasoning: {"enabled": true}``.
        last_reasoning_details: ``reasoning_details`` from the most recent call
            (``None`` until a call is made), for callers that want to continue
            the reasoning without using :meth:`chat`.
    """

    name: str = "openrouter"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        models: Optional[Dict[str, str]] = None,
        *,
        reasoning: bool = True,
        base_url: str = _API_URL,
        timeout: float = 60.0,
        referer: Optional[str] = None,
        title: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """Initialise the adapter (no network, no import of ``requests``).

        Args:
            api_key: OpenRouter key; falls back to ``OPENROUTER_API_KEY``. May be
                ``None`` at construction (only needed when a call is made).
            model: Default model id (e.g. ``"google/gemma-4-26b-a4b-it:free"``).
            models: Optional tier -> model override mapping.
            reasoning: Send ``reasoning: {"enabled": true}`` on every request.
            base_url: Chat-completions endpoint URL.
            timeout: Per-request timeout in seconds.
            referer: Optional ``HTTP-Referer`` header (OpenRouter app ranking).
            title: Optional ``X-Title`` header (OpenRouter app ranking).
            extra_headers: Any additional headers to send.
        """
        # Reads OPENROUTER_API_KEY (preferred) or the generic API_KEY from the
        # environment or a .env file, so credentials live in .env, never in code.
        self.api_key = resolve_api_key(api_key, ["OPENROUTER_API_KEY", "API_KEY"])
        self.default_model = model
        self.models: Dict[str, str] = dict(models or {})
        self.reasoning = bool(reasoning)
        self.base_url = base_url
        self.timeout = float(timeout)
        self.referer = referer
        self.title = title
        self.extra_headers = dict(extra_headers or {})
        self.last_reasoning_details: Optional[Any] = None

    def model_for(self, tier: str) -> str:
        """Return the concrete model id for ``tier`` (defaults to ``default_model``)."""
        return self.models.get(tier, self.default_model)

    # -- payload / headers -----------------------------------------------------

    def _require_key(self) -> str:
        if not self.api_key:
            raise RuntimeError(
                "OpenRouterProvider requires an api_key or the OPENROUTER_API_KEY "
                "environment variable to be set."
            )
        return self.api_key

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._require_key()}",
            "Content-Type": "application/json",
        }
        if self.referer:
            headers["HTTP-Referer"] = self.referer
        if self.title:
            headers["X-Title"] = self.title
        headers.update(self.extra_headers)
        return headers

    def _messages_from_request(self, request: LLMRequest) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        return messages

    def _build_payload(
        self,
        request: LLMRequest,
        messages: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Construct the OpenRouter request payload for ``request``."""
        payload: Dict[str, Any] = {
            "model": model or self.model_for(request.tier),
            "messages": messages if messages is not None else self._messages_from_request(request),
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if self.reasoning:
            payload["reasoning"] = {"enabled": True}
        if request.stop:
            payload["stop"] = list(request.stop)
        if request.response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_output",
                    "schema": request.response_schema,
                },
            }
        return payload

    # -- HTTP ------------------------------------------------------------------

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = self._headers()  # validates the key before importing requests
        import requests  # lazy: never imported at module load

        resp = requests.post(
            self.base_url, headers=headers, data=json.dumps(payload), timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.json()

    # -- public API ------------------------------------------------------------

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Execute one reasoning-enabled completion against OpenRouter.

        Args:
            request: The provider-agnostic request.

        Returns:
            The parsed :class:`~matss.ports.LLMResponse`. ``reasoning_details``
            from the response is stashed on :attr:`last_reasoning_details`.

        Raises:
            RuntimeError: If no API key is configured.
        """
        self._require_key()
        payload = self._build_payload(request)
        started = time.monotonic()
        data = self._post(payload)
        latency_ms = (time.monotonic() - started) * 1000.0
        return self._parse(data, request, latency_ms, payload["model"])

    def chat(
        self,
        messages: Sequence[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        tier: str = ModelTier.BALANCED,
        max_tokens: int = 1024,
        temperature: float = 0.8,
        reasoning: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Multi-turn call that preserves ``reasoning_details``.

        Returns the assistant message as a dict with ``role``, ``content`` and
        ``reasoning_details``. Append it back to ``messages`` *unmodified* and call
        again to continue the model's reasoning from where it left off — the
        canonical OpenRouter reasoning pattern.

        Args:
            messages: The running conversation (each a ``{"role", "content", ...}``
                dict; assistant turns should carry their ``reasoning_details``).
            model: Model id override (defaults to :attr:`default_model`).
            tier: Tier used only to resolve the model when ``model`` is omitted.
            max_tokens: Max completion tokens.
            temperature: Sampling temperature.
            reasoning: Override the instance ``reasoning`` flag for this call.

        Returns:
            ``{"role": "assistant", "content": ..., "reasoning_details": ...}``.
        """
        self._require_key()
        use_reasoning = self.reasoning if reasoning is None else bool(reasoning)
        payload: Dict[str, Any] = {
            "model": model or self.model_for(tier),
            "messages": list(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if use_reasoning:
            payload["reasoning"] = {"enabled": True}
        data = self._post(payload)
        message = (data.get("choices") or [{}])[0].get("message", {})
        self.last_reasoning_details = message.get("reasoning_details")
        return {
            "role": "assistant",
            "content": message.get("content"),
            "reasoning_details": message.get("reasoning_details"),
        }

    def _parse(
        self, data: Dict[str, Any], request: LLMRequest, latency_ms: float, model: str
    ) -> LLMResponse:
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message", {})
        # Gemma may return content=null when only reasoning is present; coerce to "".
        text = message.get("content") or ""
        self.last_reasoning_details = message.get("reasoning_details")
        usage = data.get("usage", {}) or {}

        structured_out: Optional[Dict[str, Any]] = None
        if request.response_schema is not None and text:
            try:
                structured_out = structured.coerce(json.loads(text), request.response_schema)
            except (ValueError, TypeError):
                structured_out = None

        return LLMResponse(
            text=text,
            model=data.get("model", model),
            tier=request.tier,
            input_tokens=int(usage.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage.get("completion_tokens", 0) or 0),
            cached=False,
            structured=structured_out,
            latency_ms=latency_ms,
            finish_reason=choice.get("finish_reason", "stop") or "stop",
        )

    def batch(self, requests: Sequence[LLMRequest]) -> List[LLMResponse]:
        """Complete each request sequentially (synchronous API)."""
        return [self.complete(r) for r in requests]
