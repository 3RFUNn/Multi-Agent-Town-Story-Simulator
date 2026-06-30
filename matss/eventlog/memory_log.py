"""In-memory append-only event log with an integrity hash chain.

This is the stdlib reference implementation of :class:`~matss.ports.EventLog`:
the canonical, ordered source of truth from which world state is projected. Every
appended event is stamped with a monotonically increasing sequence number and
folded into a rolling :func:`~matss.determinism.hashing.hash_events` chain, so
:attr:`InMemoryEventLog.head_hash` is a tamper-evident fingerprint of the entire
ordered history. Two logs holding the same events in the same order share a head
hash; any reorder or mutation changes it.
"""

from __future__ import annotations

from typing import Iterator, List, Sequence

from ..determinism.hashing import hash_events
from ..domain.events import Event


class InMemoryEventLog:
    """An ordered, append-only :class:`~matss.ports.EventLog` kept in memory.

    Sequence numbers start at ``0`` and increase by one per appended event. The
    log never mutates or drops events; ``read`` returns them in append order.

    Attributes:
        head_hash: Rolling integrity hash of the full ordered event history,
            updated on every append. Empty string for an empty log.
    """

    def __init__(self) -> None:
        self._events: List[Event] = []
        self.head_hash: str = ""

    def append(self, event: Event) -> Event:
        """Stamp ``event`` with the next sequence number and append it.

        Args:
            event: The event to append. Its existing ``seq`` is ignored and
                replaced with the log's next monotonic sequence number.

        Returns:
            The stamped event that was stored (a new instance with ``seq`` set).
        """
        stamped = event.with_seq(len(self._events))
        self._events.append(stamped)
        self.head_hash = hash_events([stamped], previous=self.head_hash)
        return stamped

    def append_many(self, events: Sequence[Event]) -> List[Event]:
        """Append a batch of events in order, returning the stamped events.

        Args:
            events: The events to append, in the desired order.

        Returns:
            The list of stamped events, parallel to ``events``.
        """
        return [self.append(event) for event in events]

    def read(self, from_seq: int = 0) -> Iterator[Event]:
        """Iterate over stored events with ``seq >= from_seq``, in order.

        Args:
            from_seq: Inclusive lower bound on sequence number. Defaults to 0
                (the whole log).

        Yields:
            Stored events in append order whose sequence number is at least
            ``from_seq``.
        """
        for event in self._events:
            if event.seq >= from_seq:
                yield event

    def __len__(self) -> int:
        """Number of events currently in the log."""
        return len(self._events)
