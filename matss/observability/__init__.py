"""Observability: structured logging, in-process metrics, and tracing spans.

Stdlib-only and dependency-free. The metrics registry and tracer expose the same
shape a Prometheus/OpenTelemetry exporter would consume, so wiring a real
exporter later is an adapter swap, not a rewrite.
"""

from .logging import get_logger, configure_logging
from .metrics import Metrics, METRICS
from .tracing import Tracer, TRACER, Span

__all__ = [
    "get_logger", "configure_logging",
    "Metrics", "METRICS",
    "Tracer", "TRACER", "Span",
]
