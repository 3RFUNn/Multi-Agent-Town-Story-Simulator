"""Tier-aware routing across multiple :class:`~matss.ports.LLMProvider` backends.

Cost/quality routing is the report's headline LLM recommendation: send
high-volume reflex calls to a cheap model, per-agent diaries to a balanced one,
and director/town-story synthesis to a frontier model. :class:`TieredRouter`
dispatches each request to the provider registered for its
:class:`~matss.ports.ModelTier`, and offers a :meth:`cascade` helper that tries
cheaper tiers first and escalates on failure.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from ...ports import LLMProvider, LLMRequest, LLMResponse, ModelTier

from dataclasses import replace


class TieredRouter:
    """Routes requests to per-tier providers (with an optional default).

    Attributes:
        name: Static name ``"router"`` satisfying the port contract.
    """

    name: str = "router"

    def __init__(
        self,
        providers: Optional[Dict[str, LLMProvider]] = None,
        default: Optional[LLMProvider] = None,
    ) -> None:
        """Initialise the router.

        Args:
            providers: Mapping of :class:`ModelTier` value -> provider. May be
                partial; unmapped tiers fall back to ``default``.
            default: Provider used when a request's tier has no explicit
                mapping. Required if ``providers`` does not cover every tier that
                will be requested.

        Raises:
            ValueError: If neither ``providers`` nor ``default`` is given.
        """
        self._providers: Dict[str, LLMProvider] = dict(providers or {})
        self._default = default
        if not self._providers and self._default is None:
            raise ValueError("TieredRouter needs at least one provider or a default")

    def provider_for(self, tier: str) -> LLMProvider:
        """Return the provider responsible for ``tier``.

        Args:
            tier: A :class:`ModelTier` value.

        Returns:
            The mapped provider, or the default.

        Raises:
            KeyError: If ``tier`` is unmapped and no default exists.
        """
        provider = self._providers.get(tier, self._default)
        if provider is None:
            raise KeyError(f"no provider registered for tier {tier!r} and no default")
        return provider

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Dispatch ``request`` to the provider for ``request.tier``."""
        return self.provider_for(request.tier).complete(request)

    def batch(self, requests: Sequence[LLMRequest]) -> List[LLMResponse]:
        """Route each request to its tier's provider, preserving order."""
        return [self.complete(r) for r in requests]

    def cascade(
        self,
        request: LLMRequest,
        order: Sequence[str] = (ModelTier.CHEAP, ModelTier.BALANCED, ModelTier.FRONTIER),
    ) -> LLMResponse:
        """Try tiers in ``order``, escalating on failure.

        The request is re-tiered to each tier in turn (cheapest first by default)
        and dispatched; the first success is returned. If every tier fails, the
        last exception propagates.

        Args:
            request: The base request (its ``tier`` is overridden per attempt).
            order: The tiers to try, cheapest/most-preferred first.

        Returns:
            The first successful :class:`LLMResponse`.

        Raises:
            BaseException: The last provider exception if all tiers fail.
            ValueError: If ``order`` is empty.
        """
        if not order:
            raise ValueError("cascade order must be non-empty")
        last_exc: Optional[BaseException] = None
        for tier in order:
            attempt = replace(request, tier=tier)
            try:
                return self.provider_for(tier).complete(attempt)
            except Exception as exc:  # noqa: BLE001 - escalate to next tier
                last_exc = exc
        assert last_exc is not None
        raise last_exc
