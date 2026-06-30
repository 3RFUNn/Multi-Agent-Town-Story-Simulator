"""Tiny, dependency-free ``.env`` loader + API-key resolution.

The prototype read its key from a ``.env`` file via ``python-dotenv``. To keep
the core stdlib-only, this re-implements just enough: parse ``KEY=VALUE`` lines
(supporting ``export``, ``#`` comments, and quoted values) and populate
``os.environ`` without overriding values already set.

``resolve_api_key`` is the helper the LLM adapters use: it loads ``.env`` (once)
and returns the first non-empty value among a list of candidate variable names,
so a single generic ``API_KEY`` works for whichever provider is selected, while a
provider-specific name (``OPENROUTER_API_KEY`` …) takes precedence.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence

# Paths whose .env has already been applied, so repeated construction is cheap.
_LOADED: set = set()


def find_dotenv(start: Optional[str] = None) -> Optional[str]:
    """Return the path to the nearest ``.env`` searching ``start`` and parents.

    The walk stops at the first ``.env`` found, or at the project root (the first
    directory containing ``pyproject.toml``), whichever comes first.
    """
    cur = Path(start or os.getcwd()).resolve()
    for d in (cur, *cur.parents):
        candidate = d / ".env"
        if candidate.is_file():
            return str(candidate)
        if (d / "pyproject.toml").is_file():
            return None
    return None


def parse_dotenv(text: str) -> Dict[str, str]:
    """Parse ``.env`` text into a dict (no I/O)."""
    out: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip matching surrounding quotes.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def load_dotenv(path: Optional[str] = None, override: bool = False) -> Dict[str, str]:
    """Load a ``.env`` into ``os.environ`` (without overriding existing vars).

    Args:
        path: Explicit ``.env`` path; auto-discovered via :func:`find_dotenv`
            when omitted.
        override: When ``True``, ``.env`` values replace existing env vars and the
            file is re-read even if loaded before.

    Returns:
        The parsed mapping from the file (empty if no file was found).
    """
    p = path or find_dotenv()
    if not p or not os.path.isfile(p):
        return {}
    if p in _LOADED and not override:
        return {}
    with open(p, "r", encoding="utf-8") as fh:
        data = parse_dotenv(fh.read())
    for key, value in data.items():
        if override or key not in os.environ:
            os.environ[key] = value
    _LOADED.add(p)
    return data


def resolve_api_key(
    explicit: Optional[str],
    names: Sequence[str],
    *,
    load: bool = True,
) -> Optional[str]:
    """Resolve an API key from an explicit value, ``.env``, then the environment.

    Args:
        explicit: A key passed directly (wins if truthy).
        names: Candidate env-var names in priority order (e.g.
            ``["OPENROUTER_API_KEY", "API_KEY"]``).
        load: Whether to load ``.env`` first (default ``True``).

    Returns:
        The first non-empty key found, or ``None``.
    """
    if explicit:
        return explicit
    if load:
        load_dotenv()
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None
