"""Canonical, cross-machine-stable hashing of world state and events.

The ``state_hash`` of a tick is the cryptographic fingerprint of the simulation's
observable state at that tick. Chaining these hashes across a run produces a
*reproducibility certificate*: two runs with the same ``(seed, content, engine
version)`` MUST yield an identical hash chain, on any machine. This is what makes
controlled-perturbation experiments (flip one config field, diff the chain)
rigorous, and is the property the prototype lacked.

Canonicalisation rules
----------------------
* dicts are serialised with sorted keys;
* floats are rounded to a fixed precision then formatted with ``repr`` so that
  ``0.1 + 0.2`` hashes identically everywhere (IEEE-754 is deterministic, but we
  also round to neutralise benign last-bit accumulation differences);
* tuples and lists are distinguished (``["t", ...]`` vs ``["l", ...]`` tags);
* sets are sorted by their canonical form;
* unknown objects must expose ``to_canonical()`` or ``to_dict()``.
"""

from __future__ import annotations

import hashlib
from typing import Any, Iterable

# Fixed float precision for hashing. 6 decimals is far finer than any gameplay
# quantity (needs are 0-100, money is dollars) yet coarse enough to absorb
# last-bit float noise. Determinism does not depend on this value, only on it
# being fixed.
_FLOAT_PRECISION = 6


def _canonical(obj: Any) -> Any:
    """Recursively convert ``obj`` into a canonical, JSON-ish structure."""
    if obj is None or isinstance(obj, (bool, int, str)):
        return obj
    if isinstance(obj, float):
        # Normalise -0.0 to 0.0 and round to fixed precision.
        r = round(obj, _FLOAT_PRECISION)
        if r == 0.0:
            r = 0.0
        return f"f:{r!r}"
    if isinstance(obj, dict):
        return {str(k): _canonical(obj[k]) for k in sorted(obj, key=str)}
    if isinstance(obj, (list, tuple)):
        tag = "t" if isinstance(obj, tuple) else "l"
        return [tag, [_canonical(v) for v in obj]]
    if isinstance(obj, (set, frozenset)):
        items = [_canonical(v) for v in obj]
        items.sort(key=lambda x: repr(x))
        return ["s", items]
    if hasattr(obj, "to_canonical"):
        return _canonical(obj.to_canonical())
    if hasattr(obj, "to_dict"):
        return _canonical(obj.to_dict())
    raise TypeError(
        f"Cannot canonicalise object of type {type(obj).__name__!r} "
        f"(add a to_canonical()/to_dict() method)"
    )


def canonical_json(obj: Any) -> str:
    """Serialise ``obj`` to a canonical, stable string (not standard JSON).

    The format is intentionally compact and unambiguous rather than pretty; it
    exists only to be hashed, never parsed back.
    """
    return _encode(_canonical(obj))


def _encode(node: Any) -> str:
    if isinstance(node, dict):
        inner = ",".join(f"{k!r}:{_encode(v)}" for k, v in node.items())
        return "{" + inner + "}"
    if isinstance(node, list):
        return "[" + ",".join(_encode(v) for v in node) + "]"
    return repr(node)


def _digest(payload: str) -> str:
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=16).hexdigest()


def state_hash(obj: Any) -> str:
    """Return the canonical 32-hex-char state hash of ``obj``."""
    return _digest(canonical_json(obj))


def hash_events(events: Iterable[Any], previous: str = "") -> str:
    """Fold a sequence of events into a single rolling hash.

    ``previous`` lets callers chain across batches/ticks so the final value
    depends on the full ordered history, not just the last batch.
    """
    acc = previous
    for ev in events:
        payload = ev.to_dict() if hasattr(ev, "to_dict") else ev
        acc = _digest(acc + "|" + canonical_json(payload))
    return acc
