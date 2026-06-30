"""Durable JSON-Lines append-only event log.

A file-backed :class:`~matss.ports.EventLog` where each event is one JSON object
on its own line (:meth:`Event.to_dict` / :meth:`Event.from_dict`). The format is
the deliberately Kafka/Redpanda-shaped wire form: append-only, one record per
line, parseable incrementally. Swapping this adapter for a real streaming log is
a transport change, not a model change.

Append is the only write operation; existing lines are never rewritten. The
sequence number is assigned from the current line count so that, like the
in-memory log, sequence numbers are dense and monotonic from ``0``.
"""

from __future__ import annotations

import json
import os
from typing import Iterator, List, Sequence, Union

from ..domain.events import Event


class JsonlEventLog:
    """An append-only :class:`~matss.ports.EventLog` persisted as JSON Lines.

    Each :meth:`append` writes exactly one ``\\n``-terminated JSON line and
    flushes it. The next sequence number is derived from the number of lines
    already present, so opening an existing file resumes its sequence.
    """

    def __init__(self, path: Union[str, "os.PathLike[str]"]) -> None:
        """Open (creating if absent) the JSONL log at ``path``.

        Args:
            path: Filesystem path to the log file.
        """
        self._path = os.fspath(path)
        # Touch the file so reads on a fresh log succeed and the count is well
        # defined from the outset.
        if not os.path.exists(self._path):
            open(self._path, "a", encoding="utf-8").close()

    def _line_count(self) -> int:
        # Count only lines that parse as complete JSON objects, so a partial or
        # corrupt trailing record never inflates the next assigned sequence
        # number (which would violate the dense/monotonic seq invariant).
        count = 0
        with open(self._path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    json.loads(line)
                except (ValueError, TypeError):
                    continue
                count += 1
        return count

    def append(self, event: Event) -> Event:
        """Stamp ``event`` with the next sequence number and write one line.

        Args:
            event: The event to persist. Its existing ``seq`` is replaced with
                the next monotonic sequence number.

        Returns:
            The stamped event that was written.
        """
        stamped = event.with_seq(self._line_count())
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(stamped.to_dict(), sort_keys=True))
            fh.write("\n")
            fh.flush()
        return stamped

    def append_many(self, events: Sequence[Event]) -> List[Event]:
        """Append a batch of events in order, returning the stamped events.

        Args:
            events: The events to persist, in the desired order.

        Returns:
            The list of stamped events, parallel to ``events``.
        """
        stamped: List[Event] = []
        seq = self._line_count()
        with open(self._path, "a", encoding="utf-8") as fh:
            for event in events:
                ev = event.with_seq(seq)
                fh.write(json.dumps(ev.to_dict(), sort_keys=True))
                fh.write("\n")
                stamped.append(ev)
                seq += 1
            fh.flush()
        return stamped

    def read(self, from_seq: int = 0, *, strict: bool = False) -> Iterator[Event]:
        """Parse stored lines into events with ``seq >= from_seq``, in order.

        Malformed or incomplete lines (e.g. a truncated trailing record from a
        crash mid-write) are **skipped** by default so that one bad line cannot
        make an otherwise-valid log unreplayable. Pass ``strict=True`` to raise a
        :class:`ValueError` naming the offending line instead.

        Args:
            from_seq: Inclusive lower bound on sequence number. Defaults to 0.
            strict: When ``True``, raise on the first malformed line rather than
                skipping it.

        Yields:
            Reconstructed :class:`Event` objects in file order whose sequence
            number is at least ``from_seq``.
        """
        with open(self._path, "r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = Event.from_dict(json.loads(line))
                except (ValueError, TypeError, KeyError) as exc:
                    if strict:
                        raise ValueError(
                            f"{self._path}:{lineno}: malformed event line: {exc}"
                        ) from exc
                    continue
                if event.seq >= from_seq:
                    yield event

    def __len__(self) -> int:
        """Number of events currently persisted in the log."""
        return self._line_count()
