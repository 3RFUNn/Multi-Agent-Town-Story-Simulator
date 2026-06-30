"""A retrying decorator over any :class:`~matss.ports.LLMProvider`.

Network LLM calls fail transiently (rate limits, 5xx, timeouts). This wrapper
retries :meth:`complete` with exponential backoff. The ``sleep`` callable is
injected so tests run instantly and deterministically (``sleep=lambda _: None``)
while production passes ``time.sleep``.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Tuple, Type

from ...ports import LLMProvider, LLMRequest, LLMResponse


class RetryingProvider:
    """Wraps a provider and retries :meth:`complete` on failure.

    The retry schedule is purely deterministic: ``delay = base_delay * 2**n``
    for the ``n``-th (zero-based) failed attempt, handed to the injected
    ``sleep`` callable. No randomness (no jitter) is introduced, preserving
    reproducibility.

    Attributes:
        name: The wrapped provider's name (delegated).
        attempts: Total number of inner :meth:`complete` calls in the most
            recent :meth:`complete` invocation.
    """

    def __init__(
        self,
        inner: LLMProvider,
        max_attempts: int = 4,
        base_delay: float = 0.0,
        sleep: Optional[Callable[[float], None]] = None,
        retry_on: Tuple[Type[BaseException], ...] = (Exception,),
    ) -> None:
        """Initialise the retrying wrapper.

        Args:
            inner: The provider to delegate to.
            max_attempts: Maximum total attempts (must be >= 1). After this many
                failures the last exception is re-raised.
            base_delay: Base backoff delay in seconds; ``0.0`` disables waiting.
            sleep: Callable invoked with each computed delay. Defaults to a
                no-op (so wrapping is non-blocking unless a real sleeper is
                injected).
            retry_on: Exception types that trigger a retry. Other exceptions
                propagate immediately.

        Raises:
            ValueError: If ``max_attempts`` is less than 1.
        """
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self._inner = inner
        self._max_attempts = int(max_attempts)
        self._base_delay = float(base_delay)
        self._sleep: Callable[[float], None] = sleep or (lambda _d: None)
        self._retry_on = retry_on
        self.attempts = 0

    @property
    def name(self) -> str:
        return getattr(self._inner, "name", "retrying")

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Call ``inner.complete`` with retries.

        Args:
            request: The request to complete.

        Returns:
            The first successful :class:`LLMResponse`.

        Raises:
            BaseException: The last exception raised by the inner provider once
                ``max_attempts`` is exhausted.
        """
        self.attempts = 0
        last_exc: Optional[BaseException] = None
        for attempt in range(self._max_attempts):
            self.attempts += 1
            try:
                return self._inner.complete(request)
            except self._retry_on as exc:  # noqa: PERF203 - retry loop
                last_exc = exc
                is_last = attempt == self._max_attempts - 1
                if is_last:
                    break
                delay = self._base_delay * (2 ** attempt)
                self._sleep(delay)
        assert last_exc is not None  # loop ran at least once
        raise last_exc

    def batch(self, requests: Sequence[LLMRequest]) -> List[LLMResponse]:
        """Retry each request independently via :meth:`complete`."""
        return [self.complete(r) for r in requests]
