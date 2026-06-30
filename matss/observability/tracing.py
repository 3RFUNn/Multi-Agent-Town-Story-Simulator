"""Minimal tracing: nestable spans with durations, OTel-shaped.

The default tracer records spans in-process (inspectable in tests). A real
OpenTelemetry exporter is a drop-in adapter implementing ``record(span)``.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional


@dataclass
class Span:
    name: str
    start_ms: float
    end_ms: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)
    parent: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        return max(0.0, self.end_ms - self.start_ms)


class Tracer:
    def __init__(self, sink: Optional[Callable[[Span], None]] = None,
                 clock: Callable[[], float] = lambda: time.perf_counter() * 1000.0) -> None:
        self._sink = sink
        self._clock = clock
        self._stack: List[str] = []
        self.spans: List[Span] = []

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[Span]:
        s = Span(name=name, start_ms=self._clock(), attributes=dict(attributes),
                 parent=self._stack[-1] if self._stack else None)
        self._stack.append(name)
        try:
            yield s
        finally:
            s.end_ms = self._clock()
            self._stack.pop()
            self.spans.append(s)
            if self._sink:
                self._sink(s)

    def reset(self) -> None:
        self.spans.clear()
        self._stack.clear()


TRACER = Tracer()
