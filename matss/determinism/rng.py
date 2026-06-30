"""Seeded, named RNG sub-streams for reproducible simulation.

Design rationale
----------------
A single shared ``random.Random`` makes reproducibility fragile: the order in
which *unrelated* subsystems happen to draw numbers becomes load-bearing, so any
refactor (or a change in iteration order) silently changes every downstream
result. Instead we derive an **independent named sub-stream** per concern
(movement, social, spawn, ...) from one root seed. Each sub-stream is a fully
independent ``random.Random`` whose seed is ``H(root_seed, name)``, so:

* the same ``(root_seed, name)`` always yields the same sequence, on any machine
  (CPython's Mersenne-Twister is platform-independent for a given seed);
* reordering subsystem calls cannot perturb another subsystem's stream;
* adding a new subsystem does not shift the numbers drawn by existing ones.

This is the single change that turns the project's "reproducible kernel" thesis
from aspiration into a tested property (see ``tests/test_determinism.py``).
"""

from __future__ import annotations

import hashlib
import random
from typing import Dict, Sequence, TypeVar

T = TypeVar("T")

# Mask to fold a BLAKE2b digest into the range accepted by ``random.seed`` while
# staying comfortably within an unsigned 64-bit integer.
_SEED_MASK = (1 << 63) - 1


def _derive_seed(root_seed: int, name: str) -> int:
    """Deterministically derive a 63-bit sub-stream seed from ``(root, name)``."""
    h = hashlib.blake2b(digest_size=8)
    h.update(int(root_seed).to_bytes(8, "big", signed=False))
    h.update(b"\x00")
    h.update(name.encode("utf-8"))
    return int.from_bytes(h.digest(), "big") & _SEED_MASK


class RandomSource:
    """A factory of independent, reproducible ``random.Random`` sub-streams.

    Example
    -------
    >>> rs = RandomSource(seed=42)
    >>> a = rs.stream("movement")
    >>> b = rs.stream("movement")
    >>> a is b                      # same name -> same (memoised) stream
    True
    >>> RandomSource(42).stream("movement").random() == \
    ...     RandomSource(42).stream("movement").random()
    True
    """

    __slots__ = ("_root_seed", "_streams")

    def __init__(self, seed: int) -> None:
        self._root_seed = int(seed)
        self._streams: Dict[str, random.Random] = {}

    @property
    def seed(self) -> int:
        return self._root_seed

    def stream(self, name: str) -> random.Random:
        """Return the memoised sub-stream for ``name`` (creating it on first use)."""
        rng = self._streams.get(name)
        if rng is None:
            rng = random.Random(_derive_seed(self._root_seed, name))
            self._streams[name] = rng
        return rng

    # --- Convenience helpers (all routed through a named sub-stream) ----------

    def randint(self, name: str, a: int, b: int) -> int:
        return self.stream(name).randint(a, b)

    def random(self, name: str) -> float:
        return self.stream(name).random()

    def choice(self, name: str, seq: Sequence[T]) -> T:
        return self.stream(name).choice(seq)

    def shuffle(self, name: str, seq: list) -> None:
        """In-place deterministic shuffle using the named sub-stream."""
        self.stream(name).shuffle(seq)

    def sample(self, name: str, population: Sequence[T], k: int) -> list:
        return self.stream(name).sample(list(population), k)

    def fork(self, name: str) -> "RandomSource":
        """Create a child :class:`RandomSource` deterministically tied to ``name``.

        Useful for giving a per-agent or per-region scope its own independent,
        reproducible universe of sub-streams.
        """
        return RandomSource(_derive_seed(self._root_seed, "fork:" + name))

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"RandomSource(seed={self._root_seed}, streams={sorted(self._streams)})"
