"""Determinism primitives: seeded RNG sub-streams and canonical state hashing.

This package is the technical heart of MATSS v2's headline property:
**bit-reproducible simulation**. The original prototype seeded nothing
(``random.*`` was called with the global, unseeded generator), so identical
configs produced divergent runs. Here, every stochastic draw flows through a
:class:`~matss.determinism.rng.RandomSource` seeded from the run seed, and every
tick's world state is reduced to a canonical :func:`~matss.determinism.hashing.state_hash`.
"""

from .rng import RandomSource
from .hashing import state_hash, hash_events, canonical_json

__all__ = ["RandomSource", "state_hash", "hash_events", "canonical_json"]
