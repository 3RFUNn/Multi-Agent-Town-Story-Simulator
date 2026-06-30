"""In-process event bus: synchronous, ordered, fault-isolating publish/subscribe.

The bus is the *live* fan-out surface of the event-sourced core. The simulation
publishes every :class:`~matss.domain.events.Event` exactly once; subscribers
(the durable log, the web gateway, metrics, read models) react without the sim
ever importing them. Delivery is synchronous and in subscriber-registration
order so that, given the same event stream, every run observes the same handler
ordering — a prerequisite for the engine's bit-reproducibility guarantee.

A throwing subscriber must never break the publish path or the other
subscribers: handler exceptions are caught, counted, and logged, then delivery
continues.
"""

from __future__ import annotations

from typing import List

from ..domain.events import Event
from ..observability import get_logger
from ..ports import EventHandler

_log = get_logger("eventlog.bus")


class InProcessEventBus:
    """A synchronous, deterministic, fault-isolating :class:`~matss.ports.EventBus`.

    Handlers are invoked in the order they were registered. Each ``publish``
    call delivers a single event to every current subscriber; if a handler
    raises, the exception is recorded and logged but neither propagated nor
    allowed to skip the remaining handlers.

    Attributes:
        error_count: Total number of handler exceptions swallowed since
            construction. Useful for tests and health checks.
    """

    def __init__(self) -> None:
        self._handlers: List[EventHandler] = []
        self.error_count: int = 0

    def subscribe(self, handler: EventHandler) -> None:
        """Register ``handler`` to receive every subsequently published event.

        Args:
            handler: A callable taking a single :class:`Event`. Registration
                order is preserved and defines delivery order.
        """
        self._handlers.append(handler)

    def publish(self, event: Event) -> None:
        """Deliver ``event`` to every subscriber in registration order.

        A handler that raises does not abort the publish: the error is counted
        on :attr:`error_count`, logged, and delivery proceeds to the next
        handler.

        Args:
            event: The event to broadcast.
        """
        for handler in self._handlers:
            try:
                handler(event)
            except Exception:  # noqa: BLE001 - fault isolation is the contract.
                self.error_count += 1
                _log.error(
                    "event handler raised; continuing",
                    event_type=event.type,
                    seq=event.seq,
                    exc_info=True,
                )

    @property
    def subscriber_count(self) -> int:
        """Number of currently registered handlers."""
        return len(self._handlers)
