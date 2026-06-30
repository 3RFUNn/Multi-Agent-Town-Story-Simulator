"""A bounded, drop-by-importance cognition queue (report: backpressure).

Generative cognition (diaries, reflections, judging) is expensive and bursty. To
keep cost and latency bounded under load, work is funnelled through a
:class:`CognitionQueue` with a fixed capacity. When the queue is full, submitting
a new job evicts the *lowest-importance* job currently held — so scarce LLM
budget is always spent on the most important cognition, and the system sheds load
gracefully instead of blocking or growing without bound.

The queue is fully deterministic and synchronous: no threads, no locks, no
wall-clock. :meth:`CognitionQueue.process_all` drains the kept jobs in FIFO order
through a caller-supplied worker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List


@dataclass
class CognitionJob:
    """A unit of deferred cognition.

    Attributes:
        id: A stable, unique identifier for the job.
        importance: Priority used for drop decisions; higher is kept first.
        kind: A free-form job category (e.g. ``"diary"``, ``"reflection"``).
        payload: Arbitrary job inputs passed through to the worker.
    """

    id: str
    importance: float
    kind: str
    payload: Dict[str, Any] = field(default_factory=dict)


class CognitionQueue:
    """A fixed-capacity queue that drops the lowest-importance job when full.

    Submitting never blocks. While the queue holds fewer than ``maxlen`` jobs a
    submission is simply enqueued. Once full, the newly arriving set (the held
    jobs plus the new one) is reduced back to ``maxlen`` by evicting the single
    lowest-importance job; that eviction is recorded in :meth:`stats`.

    Attributes:
        maxlen: The maximum number of jobs retained at once.
    """

    def __init__(self, maxlen: int) -> None:
        """Initialise the queue.

        Args:
            maxlen: Maximum retained jobs. Must be at least 1.

        Raises:
            ValueError: If ``maxlen`` is less than 1.
        """
        if int(maxlen) < 1:
            raise ValueError("maxlen must be >= 1")
        self.maxlen = int(maxlen)
        self._jobs: List[CognitionJob] = []
        self._submitted = 0
        self._dropped = 0
        self._processed = 0
        self._dropped_importance_sum = 0.0

    def submit(self, job: CognitionJob) -> bool:
        """Submit a job, dropping the lowest-importance job if the queue is full.

        Args:
            job: The job to enqueue.

        Returns:
            ``True`` if ``job`` was retained, ``False`` if a job was dropped to
            make room (the dropped job may be ``job`` itself if it is the
            lowest-importance of the candidates).
        """
        self._submitted += 1

        if len(self._jobs) < self.maxlen:
            self._jobs.append(job)
            return True

        # Queue is full: choose the lowest-importance job among current + new to
        # evict. Ties are broken by FIFO order — the new job is "newest", so an
        # equal-importance existing job is kept and the new one would lose only
        # if it is strictly lowest. To keep "oldest dropped first" semantics for
        # existing jobs we scan held jobs in order and track the minimum.
        candidates = self._jobs + [job]
        victim_index = 0
        victim_importance = candidates[0].importance
        for i in range(1, len(candidates)):
            if candidates[i].importance < victim_importance:
                victim_importance = candidates[i].importance
                victim_index = i

        victim = candidates[victim_index]
        self._dropped += 1
        self._dropped_importance_sum += float(victim.importance)

        if victim is job:
            # The new job itself is the lowest-importance; reject it.
            return False

        # Replace the evicted held job with the new job, preserving FIFO order
        # of the survivors by removing the victim and appending the new job.
        self._jobs.pop(victim_index)
        self._jobs.append(job)
        return False

    def process_all(self, worker: Callable[[CognitionJob], Any]) -> List[Any]:
        """Process all retained jobs in FIFO order through ``worker``.

        Processed jobs are removed from the queue. The processed count in
        :meth:`stats` is incremented per job.

        Args:
            worker: A callable applied to each retained job; its return value is
                collected into the result list.

        Returns:
            The list of worker results, in FIFO order.
        """
        results: List[Any] = []
        for job in self._jobs:
            results.append(worker(job))
            self._processed += 1
        self._jobs = []
        return results

    def pending(self) -> List[CognitionJob]:
        """Return a copy of the currently retained jobs in FIFO order."""
        return list(self._jobs)

    def __len__(self) -> int:
        return len(self._jobs)

    def stats(self) -> Dict[str, Any]:
        """Return cumulative queue statistics.

        Returns:
            A dict with keys ``"submitted"``, ``"dropped"``, ``"processed"`` and
            ``"dropped_importance_sum"``.
        """
        return {
            "submitted": self._submitted,
            "dropped": self._dropped,
            "processed": self._processed,
            "dropped_importance_sum": self._dropped_importance_sum,
        }
