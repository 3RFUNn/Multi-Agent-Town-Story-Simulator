"""In-memory cosine-similarity vector store.

A stdlib-only, brute-force implementation of :class:`~matss.ports.VectorStore`
suitable for the offline kernel and tests. Production deployments swap in a
pgvector/Qdrant adapter behind the same Protocol; this one keeps the engine
fully deterministic and dependency-free.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..ports import VectorHit


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Return the cosine similarity of two equal-length vectors.

    A zero-magnitude vector yields a similarity of ``0.0`` rather than raising,
    which keeps retrieval robust to empty/degenerate embeddings.
    """
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


class InMemoryVectorStore:
    """A deterministic, brute-force cosine-similarity vector store.

    Vectors are stored verbatim and queried by exhaustively scoring every entry.
    Ties in similarity are broken by ascending key so that results are fully
    reproducible regardless of insertion order.
    """

    def __init__(self) -> None:
        """Create an empty store."""
        self._vectors: Dict[str, List[float]] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

    def add(
        self,
        key: str,
        vector: Sequence[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Insert or replace the vector (and metadata) stored under ``key``.

        Args:
            key: Unique identifier for the vector.
            vector: The embedding to store.
            metadata: Optional metadata associated with the vector.
        """
        self._vectors[key] = list(vector)
        self._metadata[key] = dict(metadata) if metadata else {}

    def query(self, vector: Sequence[float], k: int) -> List[VectorHit]:
        """Return the ``k`` most cosine-similar entries to ``vector``.

        Args:
            vector: The query embedding.
            k: Maximum number of hits to return.

        Returns:
            Up to ``k`` :class:`~matss.ports.VectorHit` objects sorted by
            descending similarity, breaking ties by ascending key.
        """
        if k <= 0 or not self._vectors:
            return []
        scored: List[Tuple[float, str]] = [
            (_cosine(vector, stored), key) for key, stored in self._vectors.items()
        ]
        # Sort by descending score, then ascending key for a stable tie-break.
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [
            VectorHit(key=key, score=score, metadata=dict(self._metadata[key]))
            for score, key in scored[:k]
        ]

    def remove(self, key: str) -> None:
        """Remove the entry stored under ``key`` if present.

        Args:
            key: Identifier of the entry to remove. A missing key is a no-op.
        """
        self._vectors.pop(key, None)
        self._metadata.pop(key, None)

    def __len__(self) -> int:
        """Return the number of stored vectors."""
        return len(self._vectors)
