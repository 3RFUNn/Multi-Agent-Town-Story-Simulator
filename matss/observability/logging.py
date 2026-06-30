"""Structured JSON logging (stdlib ``logging`` under the hood)."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, Dict

_CONFIGURED = False


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, sort_keys=True, default=str)


class _StructuredAdapter(logging.LoggerAdapter):
    """Lets callers do ``log.info("msg", agent="alex", tick=3)``."""

    def process(self, msg, kwargs):
        fields = {k: kwargs.pop(k) for k in list(kwargs) if k not in ("exc_info", "stack_info", "stacklevel", "extra")}
        extra = kwargs.get("extra", {})
        extra = {**extra, "extra_fields": fields}
        kwargs["extra"] = extra
        return msg, kwargs


def configure_logging(level: int = logging.INFO, stream=None) -> None:
    global _CONFIGURED
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger("matss")
    root.handlers[:] = [handler]
    root.setLevel(level)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> _StructuredAdapter:
    if not _CONFIGURED:
        configure_logging()
    return _StructuredAdapter(logging.getLogger(f"matss.{name}"), {})
