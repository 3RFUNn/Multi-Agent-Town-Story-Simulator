"""Episodic memory stream with scored retrieval and compaction.

Generative-Agents-style scoring (Park et al., 2023): retrieval score is a
weighted sum of recency, importance, and embedding relevance. Fixes V1's F18:
entries are keyed by absolute day_index (never weekday names), and old
episodic entries are compacted into summaries so prompts stay bounded.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class MemoryEntry:
    text: str
    day_index: int
    tick: int
    importance: float                      # 0..1
    location: str | None = None
    participants: tuple[str, ...] = ()
    kind: str = "event"                    # event | summary | reflection
    embedding: np.ndarray | None = None

    def to_dict(self) -> dict:
        return {"text": self.text, "day": self.day_index, "tick": self.tick,
                "importance": round(self.importance, 2), "location": self.location,
                "participants": list(self.participants), "kind": self.kind}


@dataclass
class MemoryStream:
    alpha_recency: float = 1.0
    beta_importance: float = 1.0
    gamma_relevance: float = 1.0
    decay_per_tick: float = 0.9985
    entries: list[MemoryEntry] = field(default_factory=list)

    def add(self, entry: MemoryEntry) -> None:
        self.entries.append(entry)

    def for_day(self, day_index: int) -> list[MemoryEntry]:
        return [e for e in self.entries if e.day_index == day_index and e.kind == "event"]

    def summaries(self) -> list[MemoryEntry]:
        return [e for e in self.entries if e.kind in ("summary", "reflection")]

    def retrieve(self, query_embedding: np.ndarray | None, now_tick: int, k: int = 12
                 ) -> list[MemoryEntry]:
        if not self.entries:
            return []
        q = None
        if query_embedding is not None:
            norm = np.linalg.norm(query_embedding)
            q = query_embedding / norm if norm > 0 else None
        scored: list[tuple[float, int, MemoryEntry]] = []
        for i, e in enumerate(self.entries):
            recency = self.decay_per_tick ** max(0, now_tick - e.tick)
            relevance = 0.0
            if q is not None and e.embedding is not None:
                norm = np.linalg.norm(e.embedding)
                if norm > 0:
                    relevance = float(np.dot(e.embedding / norm, q))
            score = (self.alpha_recency * recency
                     + self.beta_importance * e.importance
                     + self.gamma_relevance * relevance)
            scored.append((score, -i, e))  # -i: stable tie-break, newest first
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [e for _, _, e in scored[:k]]

    def compact_before(self, day_index: int, summary: MemoryEntry | None) -> int:
        """Drop episodic entries older than day_index; keep summaries/reflections.
        Returns the number of entries removed."""
        keep = [e for e in self.entries
                if e.day_index >= day_index or e.kind in ("summary", "reflection")]
        removed = len(self.entries) - len(keep)
        self.entries = keep
        if summary is not None:
            self.entries.append(summary)
        return removed
