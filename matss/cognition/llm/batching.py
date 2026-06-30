"""A batching facade over any :class:`~matss.ports.LLMProvider`.

Real frontier APIs offer a *Batch* endpoint (submit many prompts, collect later)
that is markedly cheaper than per-request calls. Because the foundation's
provider port is synchronous, this adapter models that submit/collect ergonomics
without async machinery: callers :meth:`submit` requests, then :meth:`flush` to
run them all through the inner provider's :meth:`batch` in one shot.

It also satisfies the full :class:`~matss.ports.LLMProvider` port (delegating
:meth:`complete`/:meth:`batch`), so it can stand in anywhere a provider is
expected.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

from ...ports import LLMProvider, LLMRequest, LLMResponse


class BatchingLLMProvider:
    """Collects requests and dispatches them as one batch to ``inner``.

    Usage::

        bp = BatchingLLMProvider(inner)
        h0 = bp.submit(req0)
        h1 = bp.submit(req1)
        responses = bp.flush()        # runs inner.batch([req0, req1])
        responses[h0], responses[h1]  # index by the handle returned by submit

    Attributes:
        name: The wrapped provider's name (delegated).
    """

    def __init__(self, inner: LLMProvider) -> None:
        """Initialise the batcher.

        Args:
            inner: The provider that performs the actual completions.
        """
        self._inner = inner
        self._pending: List[LLMRequest] = []

    @property
    def name(self) -> str:
        return getattr(self._inner, "name", "batching")

    @property
    def pending(self) -> int:
        """Number of requests queued but not yet flushed."""
        return len(self._pending)

    def submit(self, request: LLMRequest) -> int:
        """Queue ``request`` for the next :meth:`flush`.

        Args:
            request: The request to enqueue.

        Returns:
            A handle (the request's index within the pending batch) used to index
            the list returned by :meth:`flush`.
        """
        self._pending.append(request)
        return len(self._pending) - 1

    def flush(self) -> List[LLMResponse]:
        """Dispatch all queued requests in one batch and clear the queue.

        Returns:
            Responses in submission order (the handle from :meth:`submit` indexes
            this list). Empty when nothing was queued.
        """
        if not self._pending:
            return []
        batch = self._pending
        self._pending = []
        return list(self._inner.batch(batch))

    def submit_all(self, requests: Sequence[LLMRequest]) -> Tuple[int, ...]:
        """Queue several requests at once, returning their handles."""
        return tuple(self.submit(r) for r in requests)

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Complete a single request immediately (delegates to ``inner``)."""
        return self._inner.complete(request)

    def batch(self, requests: Sequence[LLMRequest]) -> List[LLMResponse]:
        """Complete a batch immediately (delegates to ``inner``)."""
        return list(self._inner.batch(requests))
