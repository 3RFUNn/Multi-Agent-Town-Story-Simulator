"""A tiny in-process metrics registry (counters, gauges, histograms).

Deterministic and dependency-free. ``snapshot()`` yields a plain dict suitable
for assertions in tests or for shipping to a real exporter via an adapter.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Tuple


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._hist: Dict[str, List[float]] = {}

    @staticmethod
    def _key(name: str, labels: Dict[str, str] | None) -> str:
        if not labels:
            return name
        tags = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{tags}}}"

    def incr(self, name: str, value: float = 1.0, **labels: str) -> None:
        k = self._key(name, labels)
        with self._lock:
            self._counters[k] = self._counters.get(k, 0.0) + value

    def gauge(self, name: str, value: float, **labels: str) -> None:
        with self._lock:
            self._gauges[self._key(name, labels)] = value

    def observe(self, name: str, value: float, **labels: str) -> None:
        k = self._key(name, labels)
        with self._lock:
            self._hist.setdefault(k, []).append(value)

    def get_counter(self, name: str, **labels: str) -> float:
        return self._counters.get(self._key(name, labels), 0.0)

    def histogram_stats(self, name: str, **labels: str) -> Dict[str, float]:
        vals = sorted(self._hist.get(self._key(name, labels), []))
        if not vals:
            return {"count": 0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0, "mean": 0.0}

        def pct(p: float) -> float:
            idx = min(len(vals) - 1, int(p * (len(vals) - 1) + 0.5))
            return vals[idx]

        return {
            "count": len(vals),
            "p50": pct(0.50),
            "p95": pct(0.95),
            "p99": pct(0.99),
            "max": vals[-1],
            "mean": sum(vals) / len(vals),
        }

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {k: self.histogram_stats(*self._split(k)) for k in self._hist},
            }

    @staticmethod
    def _split(key: str) -> Tuple[str, ...]:
        # histogram_stats re-keys; for snapshot we just pass the raw key as name.
        return (key,)

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._hist.clear()


# Process-wide default registry (callers may also construct their own).
METRICS = Metrics()
