"""Park-style memory stream: recency + importance + relevance retrieval.

This module implements :class:`~matss.ports.MemoryRetriever`. It stores each
agent's observations and reflections as :class:`~matss.domain.memory.MemoryRecord`
objects, embeds their text into a :class:`~matss.ports.VectorStore`, and scores
retrieval candidates by the three signals from Park et al.'s *Generative Agents*:

* **recency** — exponential decay of how long ago a memory was last accessed;
* **importance** — the memory's poignancy score (1-10);
* **relevance** — cosine similarity between the query and the memory embedding.

It replaces the prototype's ``startswith(day)`` retrieval with a principled,
deterministic blend of all three.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from ..domain.memory import MemoryRecord
from ..ports import EmbeddingProvider, VectorStore
from .vector_store import InMemoryVectorStore

ImportanceScorer = Callable[[str], float]

# Tokens that hint at emotionally/socially poignant events, used by the stdlib
# importance heuristic when no explicit score or scorer is supplied.
_SALIENT_TOKENS = frozenset(
    {
        "love", "hate", "fight", "fired", "hired", "died", "death", "born",
        "married", "wedding", "breakup", "broke", "argued", "argument",
        "promotion", "promoted", "accident", "kissed", "confessed", "secret",
        "betrayed", "afraid", "scared", "cried", "angry", "furious", "joy",
        "heartbroken", "proposed", "won", "lost", "emergency", "crash",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9']+")


def default_importance(text: str) -> float:
    """A deterministic, stdlib-only poignancy heuristic in ``[1, 10]``.

    Mundane observations score near the floor; longer texts and those containing
    emotionally salient keywords score higher. The result is clamped to Park
    et al.'s 1-10 range.

    Args:
        text: The observation text to score.

    Returns:
        A float importance in ``[1.0, 10.0]``.
    """
    tokens = _TOKEN_RE.findall(text.lower())
    score = 1.0
    # Mild length signal: more detail tends to mean a more notable event.
    score += min(len(tokens) / 8.0, 3.0)
    salient = sum(1 for token in tokens if token in _SALIENT_TOKENS)
    score += 3.0 * salient
    if "!" in text or "?" in text:
        score += 1.0
    return max(1.0, min(10.0, score))


class MemoryStream:
    """Per-agent Park-style memory store with blended retrieval.

    Memories live in a single :class:`~matss.ports.VectorStore` namespaced by a
    ``f"{agent_id}:{mem_id}"`` key scheme, giving strict per-agent isolation
    while sharing one backing store. Retrieval scores each candidate by a
    weighted sum of recency, importance, and relevance and (per Park et al.)
    refreshes the ``last_accessed_tick`` of every returned memory so that
    repeatedly recalled memories stay "fresh".
    """

    def __init__(
        self,
        embedder: EmbeddingProvider,
        store: Optional[VectorStore] = None,
        decay: float = 0.995,
        weights: Tuple[float, float, float] = (1.0, 1.0, 1.0),
        importance_scorer: Optional[ImportanceScorer] = None,
    ) -> None:
        """Initialise the memory stream.

        Args:
            embedder: Provider used to embed memory text and queries.
            store: Backing vector store. A fresh :class:`InMemoryVectorStore` is
                created when omitted.
            decay: Per-tick recency decay base in ``(0, 1]``; higher means slower
                forgetting.
            weights: ``(w_recency, w_importance, w_relevance)`` retrieval weights.
            importance_scorer: Optional callable mapping text to a 1-10 score,
                used when an observation is added without an explicit importance.
        """
        self._embedder = embedder
        self._store: VectorStore = store if store is not None else InMemoryVectorStore()
        self._decay = float(decay)
        w_recency, w_importance, w_relevance = weights
        self._w_recency = float(w_recency)
        self._w_importance = float(w_importance)
        self._w_relevance = float(w_relevance)
        self._importance_scorer = importance_scorer
        # All records, keyed by agent then by record id, preserving insertion order.
        self._records: Dict[str, Dict[str, MemoryRecord]] = {}
        # Monotonic per-agent counter for stable, unique record ids + ordering.
        self._counters: Dict[str, int] = {}

    # --- internal helpers -----------------------------------------------------

    @staticmethod
    def _store_key(agent_id: str, mem_id: str) -> str:
        """Return the namespaced backing-store key for a memory."""
        return f"{agent_id}:{mem_id}"

    def _score_importance(self, text: str) -> float:
        scorer = self._importance_scorer or default_importance
        return max(1.0, min(10.0, float(scorer(text))))

    def _add_record(
        self,
        agent_id: str,
        text: str,
        tick: int,
        day: str,
        importance: float,
        kind: str,
        related_agents: Optional[Sequence[str]],
    ) -> MemoryRecord:
        seq = self._counters.get(agent_id, 0)
        self._counters[agent_id] = seq + 1
        mem_id = f"{agent_id}-{seq:08d}"
        embedding = self._embedder.embed(text)
        record = MemoryRecord(
            id=mem_id,
            agent_id=agent_id,
            text=text,
            tick=tick,
            day=day,
            importance=float(importance),
            created_seq=seq,
            last_accessed_tick=tick,
            kind=kind,
            related_agents=list(related_agents) if related_agents else [],
            embedding=list(embedding),
        )
        self._records.setdefault(agent_id, {})[mem_id] = record
        self._store.add(
            self._store_key(agent_id, mem_id),
            embedding,
            metadata={"agent_id": agent_id, "mem_id": mem_id, "kind": kind},
        )
        return record

    # --- public API -----------------------------------------------------------

    def add_observation(
        self,
        agent_id: str,
        text: str,
        tick: int,
        day: str,
        importance: Optional[float] = None,
        related_agents: Optional[Sequence[str]] = None,
    ) -> MemoryRecord:
        """Record an observation, embedding it and storing it for retrieval.

        Args:
            agent_id: Owning agent.
            text: The observation text.
            tick: Simulation tick the observation occurred at.
            day: Day label (e.g. weekday name) for day-scoped lookups.
            importance: Explicit 1-10 poignancy; derived deterministically from
                the configured scorer / stdlib heuristic when ``None``.
            related_agents: Other agents referenced by the observation.

        Returns:
            The created :class:`~matss.domain.memory.MemoryRecord`.
        """
        score = importance if importance is not None else self._score_importance(text)
        score = max(1.0, min(10.0, float(score)))
        return self._add_record(
            agent_id, text, tick, day, score, "observation", related_agents
        )

    def add_reflection(
        self,
        agent_id: str,
        text: str,
        tick: int,
        day: str,
        importance: Optional[float] = None,
        related_agents: Optional[Sequence[str]] = None,
    ) -> MemoryRecord:
        """Record a higher-level reflection (``kind="reflection"``).

        Reflections default to a high importance floor since they summarise many
        observations. See :meth:`add_observation` for argument semantics.

        Returns:
            The created reflection :class:`~matss.domain.memory.MemoryRecord`.
        """
        if importance is None:
            score = max(self._score_importance(text), 6.0)
        else:
            score = float(importance)
        score = max(1.0, min(10.0, score))
        return self._add_record(
            agent_id, text, tick, day, score, "reflection", related_agents
        )

    def retrieve(
        self, agent_id: str, query: str, k: int, now_tick: int
    ) -> List[MemoryRecord]:
        """Retrieve the top ``k`` memories for ``agent_id`` matching ``query``.

        Each candidate is scored by::

            w_recency   * decay ** (now_tick - last_accessed_tick)
          + w_importance* (importance / 10)
          + w_relevance * relevance        # cosine normalised to [0, 1]

        Ties are broken deterministically by ascending memory id. As a side
        effect (per Park et al.), the ``last_accessed_tick`` of every returned
        record is refreshed to ``now_tick``.

        Args:
            agent_id: Agent whose memories to search.
            query: Natural-language retrieval query.
            k: Maximum number of memories to return.
            now_tick: Current simulation tick (drives recency decay).

        Returns:
            Up to ``k`` records sorted by descending blended score.
        """
        agent_records = self._records.get(agent_id)
        if not agent_records or k <= 0:
            return []

        query_vector = self._embedder.embed(query)
        # Map store keys -> cosine score for this agent's memories only.
        hits = self._store.query(query_vector, k=len(self._store))
        relevance_by_id: Dict[str, float] = {}
        prefix = f"{agent_id}:"
        for hit in hits:
            if hit.key.startswith(prefix):
                mem_id = hit.key[len(prefix):]
                # Normalise cosine [-1, 1] -> [0, 1].
                relevance_by_id[mem_id] = (hit.score + 1.0) / 2.0

        scored: List[Tuple[float, str, MemoryRecord]] = []
        for mem_id, record in agent_records.items():
            age = now_tick - record.last_accessed_tick
            recency = self._decay ** age if age >= 0 else 1.0
            importance = record.importance / 10.0
            relevance = relevance_by_id.get(mem_id, 0.0)
            score = (
                self._w_recency * recency
                + self._w_importance * importance
                + self._w_relevance * relevance
            )
            scored.append((score, mem_id, record))

        scored.sort(key=lambda item: (-item[0], item[1]))
        top = [record for _, _, record in scored[:k]]

        # Refresh recency for everything we just surfaced.
        for record in top:
            record.last_accessed_tick = now_tick
        return top

    def memories_for_day(self, agent_id: str, day: str) -> List[MemoryRecord]:
        """Return all of ``agent_id``'s memories tagged with ``day``.

        Args:
            agent_id: Agent whose memories to filter.
            day: Day label to match exactly.

        Returns:
            Matching records in creation order.
        """
        agent_records = self._records.get(agent_id)
        if not agent_records:
            return []
        return [r for r in agent_records.values() if r.day == day]

    def all(self, agent_id: str) -> List[MemoryRecord]:
        """Return all of ``agent_id``'s memories in creation order.

        Args:
            agent_id: Agent whose memories to return.

        Returns:
            Every record owned by the agent, oldest first.
        """
        agent_records = self._records.get(agent_id)
        if not agent_records:
            return []
        return list(agent_records.values())
