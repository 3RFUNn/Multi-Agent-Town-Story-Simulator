"""Tests for the Park-style memory stream (matss/memory).

Covers: deterministic embeddings (dim, unit norm, identical-vs-different text),
cosine ranking in the vector store, the three-signal retrieval blend (recency /
importance / relevance each made to dominate), last-accessed-tick refresh,
day-scoped lookup, and reflection triggering against a local deterministic fake
LLM provider. All randomness is hashed-derived so the suite is reproducible.
"""

from __future__ import annotations

import hashlib
import importlib
import math
import sys
from typing import List, Sequence

import pytest

from matss import ports
from matss.domain.memory import MemoryRecord
from matss.memory import (
    InMemoryVectorStore,
    MemoryStream,
    MockEmbeddingProvider,
    OpenAIEmbeddingProvider,
    Reflector,
    default_importance,
)
from matss.ports import LLMRequest, LLMResponse, ModelTier, VectorHit


# ---------------------------------------------------------------------------
# Local deterministic fake LLM provider (satisfies ports.LLMProvider).
# ---------------------------------------------------------------------------

class FakeLLMProvider:
    """Deterministic in-test LLM provider deriving output from input hashes."""

    def __init__(self, name: str = "fake-llm") -> None:
        self.name = name
        self.calls: List[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        # Deterministically emit two insight lines derived from the prompt hash.
        digest = hashlib.blake2b(request.prompt.encode("utf-8"), digest_size=4).hexdigest()
        text = f"Insight about {digest} one\nInsight about {digest} two"
        return LLMResponse(text=text, model=self.name, tier=request.tier)

    def batch(self, requests: Sequence[LLMRequest]) -> List[LLMResponse]:
        return [self.complete(r) for r in requests]


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

def test_embedding_dim_and_unit_norm():
    embedder = MockEmbeddingProvider(dim=64)
    assert embedder.dim == 64
    vec = embedder.embed("the cat sat on the mat")
    assert len(vec) == 64
    norm = math.sqrt(sum(c * c for c in vec))
    assert norm == pytest.approx(1.0, abs=1e-9)


def test_embedding_deterministic_identical_and_different():
    embedder = MockEmbeddingProvider(dim=64)
    a1 = embedder.embed("Alice talked to Bob at the cafe")
    a2 = embedder.embed("Alice talked to Bob at the cafe")
    b = embedder.embed("a completely unrelated weather forecast")
    assert a1 == a2  # identical text -> identical vector
    assert a1 != b  # different text -> different vector


def test_embedding_batch_matches_single():
    embedder = MockEmbeddingProvider(dim=32)
    texts = ["hello world", "goodbye world", "hello there"]
    batch = embedder.embed_batch(texts)
    assert len(batch) == 3
    assert all(len(v) == 32 for v in batch)
    for text, vec in zip(texts, batch):
        assert vec == embedder.embed(text)


def test_embedding_contract_conformance():
    embedder = MockEmbeddingProvider(dim=16)
    assert isinstance(embedder, ports.EmbeddingProvider)


def test_embedding_rejects_nonpositive_dim():
    with pytest.raises(ValueError):
        MockEmbeddingProvider(dim=0)


def test_empty_text_is_zero_vector_not_crash():
    embedder = MockEmbeddingProvider(dim=8)
    vec = embedder.embed("!!!???   ")  # no alphanumeric tokens
    assert vec == [0.0] * 8


# ---------------------------------------------------------------------------
# Vector store
# ---------------------------------------------------------------------------

def test_vector_store_ranks_most_similar_first():
    store = InMemoryVectorStore()
    store.add("a", [1.0, 0.0, 0.0])
    store.add("b", [0.0, 1.0, 0.0])
    store.add("c", [0.9, 0.1, 0.0])
    hits = store.query([1.0, 0.0, 0.0], k=3)
    assert [h.key for h in hits] == ["a", "c", "b"]
    assert hits[0].score == pytest.approx(1.0)


def test_vector_store_contract_and_len_remove():
    store = InMemoryVectorStore()
    assert isinstance(store, ports.VectorStore)
    store.add("x", [1.0, 0.0], metadata={"foo": 1})
    store.add("y", [0.0, 1.0])
    assert len(store) == 2
    hits = store.query([1.0, 0.0], k=1)
    assert hits[0].key == "x"
    assert isinstance(hits[0], VectorHit)
    assert hits[0].metadata == {"foo": 1}
    store.remove("x")
    assert len(store) == 1
    store.remove("missing")  # no-op
    assert len(store) == 1


def test_vector_store_tie_break_by_key():
    store = InMemoryVectorStore()
    # Identical vectors -> identical scores -> ascending-key tie-break.
    store.add("zeta", [1.0, 1.0])
    store.add("alpha", [1.0, 1.0])
    hits = store.query([1.0, 1.0], k=2)
    assert [h.key for h in hits] == ["alpha", "zeta"]


def test_vector_store_empty_query():
    store = InMemoryVectorStore()
    assert store.query([1.0, 0.0], k=3) == []
    store.add("a", [1.0, 0.0])
    assert store.query([1.0, 0.0], k=0) == []


# ---------------------------------------------------------------------------
# Importance heuristic
# ---------------------------------------------------------------------------

def test_default_importance_in_range_and_salient_higher():
    mundane = default_importance("walked to the kitchen")
    salient = default_importance("Alice confessed her love and then they cried")
    assert 1.0 <= mundane <= 10.0
    assert 1.0 <= salient <= 10.0
    assert salient > mundane


# ---------------------------------------------------------------------------
# MemoryStream: basic add / retrieve / isolation
# ---------------------------------------------------------------------------

def make_stream(**kwargs) -> MemoryStream:
    return MemoryStream(embedder=MockEmbeddingProvider(dim=64), **kwargs)


def test_stream_contract_conformance():
    stream = make_stream()
    assert isinstance(stream, ports.MemoryRetriever)


def test_add_observation_returns_record_and_derives_importance():
    stream = make_stream()
    rec = stream.add_observation("alice", "had a quiet breakfast", tick=5, day="Monday")
    assert isinstance(rec, MemoryRecord)
    assert rec.agent_id == "alice"
    assert rec.kind == "observation"
    assert rec.last_accessed_tick == 5
    assert 1.0 <= rec.importance <= 10.0
    # Explicit importance is respected.
    rec2 = stream.add_observation("alice", "x", tick=6, day="Monday", importance=9.0)
    assert rec2.importance == 9.0


def test_per_agent_isolation():
    stream = make_stream()
    stream.add_observation("alice", "alice memory", tick=1, day="Monday")
    stream.add_observation("bob", "bob memory", tick=1, day="Monday")
    assert len(stream.all("alice")) == 1
    assert len(stream.all("bob")) == 1
    got = stream.retrieve("alice", "memory", k=10, now_tick=1)
    assert all(r.agent_id == "alice" for r in got)


# ---------------------------------------------------------------------------
# MemoryStream: three-signal blend — each signal made to dominate
# ---------------------------------------------------------------------------

def test_relevance_dominates():
    # Only relevance weighted; importance + recency neutralised.
    stream = make_stream(weights=(0.0, 0.0, 1.0))
    stream.add_observation("a", "the cat sat on the mat", tick=1, day="D", importance=1.0)
    stream.add_observation("a", "fiscal quarterly revenue report", tick=1, day="D", importance=10.0)
    got = stream.retrieve("a", "the cat sat on the mat", k=1, now_tick=1)
    assert got[0].text == "the cat sat on the mat"


def test_importance_dominates():
    # Only importance weighted; both texts equally (ir)relevant to the query.
    stream = make_stream(weights=(0.0, 1.0, 0.0))
    stream.add_observation("a", "low stakes note", tick=1, day="D", importance=2.0)
    stream.add_observation("a", "huge dramatic event", tick=1, day="D", importance=10.0)
    got = stream.retrieve("a", "unrelated query string", k=1, now_tick=1)
    assert got[0].importance == 10.0


def test_recency_dominates():
    # Only recency weighted; the more recently created memory wins.
    stream = make_stream(weights=(1.0, 0.0, 0.0), decay=0.9)
    stream.add_observation("a", "old memory", tick=0, day="D", importance=10.0)
    stream.add_observation("a", "new memory", tick=50, day="D", importance=1.0)
    got = stream.retrieve("a", "anything", k=1, now_tick=50)
    assert got[0].text == "new memory"


# ---------------------------------------------------------------------------
# MemoryStream: last_accessed_tick refresh changes recency on re-retrieve
# ---------------------------------------------------------------------------

def test_retrieve_updates_last_accessed_tick():
    stream = make_stream(weights=(1.0, 0.0, 0.0), decay=0.9)
    rec = stream.add_observation("a", "memory one", tick=0, day="D", importance=5.0)
    assert rec.last_accessed_tick == 0
    got = stream.retrieve("a", "memory", k=1, now_tick=10)
    assert got[0].id == rec.id
    # The returned record's recency clock has been refreshed to now_tick.
    assert rec.last_accessed_tick == 10


def test_recency_refresh_changes_future_ordering():
    # Two memories; we refresh one by retrieving it, which should later make it
    # rank above an un-refreshed, older-accessed memory under recency weighting.
    stream = make_stream(weights=(1.0, 0.0, 0.0), decay=0.5)
    old = stream.add_observation("a", "alpha apple", tick=0, day="D", importance=5.0)
    new = stream.add_observation("a", "beta banana", tick=0, day="D", importance=5.0)

    # Refresh only `old` to tick 100 by querying for its tokens.
    refreshed = stream.retrieve("a", "alpha apple", k=1, now_tick=100)
    assert refreshed[0].id == old.id
    assert old.last_accessed_tick == 100
    assert new.last_accessed_tick == 0

    # Now retrieve both under pure recency: `old` (accessed at 100) must outrank
    # `new` (accessed at 0) at a later tick.
    got = stream.retrieve("a", "fruit", k=2, now_tick=101)
    assert got[0].id == old.id


# ---------------------------------------------------------------------------
# MemoryStream: day filtering and determinism
# ---------------------------------------------------------------------------

def test_memories_for_day_filters():
    stream = make_stream()
    stream.add_observation("a", "mon1", tick=1, day="Monday")
    stream.add_observation("a", "tue1", tick=2, day="Tuesday")
    stream.add_observation("a", "mon2", tick=3, day="Monday")
    monday = stream.memories_for_day("a", "Monday")
    assert {r.text for r in monday} == {"mon1", "mon2"}
    assert stream.memories_for_day("a", "Sunday") == []
    assert stream.memories_for_day("ghost", "Monday") == []


def test_retrieve_is_deterministic():
    def build():
        s = make_stream(weights=(1.0, 1.0, 1.0), decay=0.99)
        s.add_observation("a", "Alice met Bob at the cafe", tick=1, day="D", importance=4.0)
        s.add_observation("a", "Bob ordered a coffee", tick=2, day="D", importance=3.0)
        s.add_observation("a", "it rained heavily all afternoon", tick=3, day="D", importance=7.0)
        return s

    r1 = build().retrieve("a", "Bob at the cafe", k=3, now_tick=10)
    r2 = build().retrieve("a", "Bob at the cafe", k=3, now_tick=10)
    assert [r.id for r in r1] == [r.id for r in r2]


def test_retrieve_empty_and_k_zero():
    stream = make_stream()
    assert stream.retrieve("nobody", "q", k=5, now_tick=1) == []
    stream.add_observation("a", "x", tick=1, day="D")
    assert stream.retrieve("a", "x", k=0, now_tick=1) == []


# ---------------------------------------------------------------------------
# Reflector
# ---------------------------------------------------------------------------

def test_reflector_triggers_when_threshold_exceeded():
    provider = FakeLLMProvider()
    stream = make_stream()
    reflector = Reflector(provider, stream)

    # Three high-importance observations -> total 30 > threshold 15.
    for i in range(3):
        stream.add_observation("a", f"dramatic event number {i}", tick=i, day="D", importance=10.0)

    reflections = reflector.maybe_reflect("a", now_tick=10, day="D", threshold=15.0)
    assert len(reflections) >= 1
    assert all(r.kind == "reflection" for r in reflections)
    assert all(r in stream.all("a") for r in reflections)
    # The provider was asked exactly once, at the balanced tier.
    assert len(provider.calls) == 1
    assert provider.calls[0].tier == ModelTier.BALANCED


def test_reflector_no_trigger_below_threshold():
    provider = FakeLLMProvider()
    stream = make_stream()
    reflector = Reflector(provider, stream)
    stream.add_observation("a", "minor thing", tick=0, day="D", importance=2.0)
    reflections = reflector.maybe_reflect("a", now_tick=1, day="D", threshold=15.0)
    assert reflections == []
    assert provider.calls == []


def test_reflector_does_not_double_count_after_reflecting():
    provider = FakeLLMProvider()
    stream = make_stream()
    reflector = Reflector(provider, stream)
    for i in range(2):
        stream.add_observation("a", f"big event {i}", tick=i, day="D", importance=10.0)

    first = reflector.maybe_reflect("a", now_tick=5, day="D", threshold=15.0)
    assert first  # triggered

    # Immediately re-calling with no new observations must not re-trigger.
    second = reflector.maybe_reflect("a", now_tick=6, day="D", threshold=15.0)
    assert second == []
    assert len(provider.calls) == 1


def test_reflector_isolated_per_agent():
    provider = FakeLLMProvider()
    stream = make_stream()
    reflector = Reflector(provider, stream)
    stream.add_observation("a", "big a event", tick=0, day="D", importance=10.0)
    stream.add_observation("b", "tiny b note", tick=0, day="D", importance=1.0)
    a_refl = reflector.maybe_reflect("a", now_tick=1, day="D", threshold=8.0)
    b_refl = reflector.maybe_reflect("b", now_tick=1, day="D", threshold=8.0)
    assert a_refl
    assert b_refl == []


def test_reflector_retriggers_on_new_observations():
    # After a successful reflection consumes the backlog, fresh high-importance
    # observations must be able to trigger a second reflection.
    provider = FakeLLMProvider()
    stream = make_stream()
    reflector = Reflector(provider, stream)
    for i in range(2):
        stream.add_observation("a", f"first wave {i}", tick=i, day="D", importance=10.0)
    assert reflector.maybe_reflect("a", now_tick=5, day="D", threshold=15.0)
    assert len(provider.calls) == 1

    # A new wave of importance should trigger again (cursor advanced, not frozen).
    for i in range(2):
        stream.add_observation("a", f"second wave {i}", tick=10 + i, day="D", importance=10.0)
    second = reflector.maybe_reflect("a", now_tick=20, day="D", threshold=15.0)
    assert second
    assert len(provider.calls) == 2


def test_reflector_records_are_retrievable_as_reflections():
    provider = FakeLLMProvider()
    stream = make_stream()
    reflector = Reflector(provider, stream)
    for i in range(3):
        stream.add_observation("a", f"dramatic {i}", tick=i, day="D", importance=10.0)
    reflections = reflector.maybe_reflect("a", now_tick=10, day="Tuesday", threshold=15.0)
    assert reflections
    # Reflections are day-tagged and present in the stream.
    tuesday = stream.memories_for_day("a", "Tuesday")
    assert all(r.kind == "reflection" for r in tuesday)
    assert {r.id for r in reflections} <= {r.id for r in stream.all("a")}


# ---------------------------------------------------------------------------
# Embedding semantic properties + OpenAI adapter (no network)
# ---------------------------------------------------------------------------

def test_embedding_case_and_punctuation_insensitive():
    embedder = MockEmbeddingProvider(dim=64)
    assert embedder.embed("Hello, World!") == embedder.embed("hello world")


def test_embedding_shared_tokens_are_more_similar():
    from matss.memory.vector_store import _cosine

    embedder = MockEmbeddingProvider(dim=128)
    base = embedder.embed("alice visited the cafe with bob")
    similar = embedder.embed("alice visited the cafe alone")
    different = embedder.embed("quarterly fiscal revenue projections")
    assert _cosine(base, similar) > _cosine(base, different)


def test_openai_provider_constructs_and_is_lazy():
    # Constructing the real adapter must not require/import `requests` and must
    # expose the Protocol surface with the documented defaults.
    sys.modules.pop("requests", None)
    embeddings = importlib.import_module("matss.memory.embeddings")
    importlib.reload(embeddings)
    assert "requests" not in sys.modules  # not imported at module import time

    provider = embeddings.OpenAIEmbeddingProvider()
    assert provider.model == "text-embedding-3-small"
    assert provider.dim == 1536
    assert isinstance(provider, ports.EmbeddingProvider)


def test_openai_provider_missing_key_raises_without_network(monkeypatch):
    # Clear the specific var AND the generic API_KEY fallback so resolution finds
    # nothing and fails fast with RuntimeError (before any import/network).
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    provider = OpenAIEmbeddingProvider(api_key=None)
    with pytest.raises(RuntimeError):
        provider.embed("hello")


# ---------------------------------------------------------------------------
# Determinism: byte-for-byte reproducibility of an end-to-end build
# ---------------------------------------------------------------------------

def test_end_to_end_pipeline_is_byte_for_byte_deterministic():
    def run():
        stream = MemoryStream(
            embedder=MockEmbeddingProvider(dim=64),
            decay=0.97,
            weights=(0.7, 1.3, 1.0),
        )
        events = [
            ("Alice met Bob at the cafe", 5.0),
            ("Bob confessed a secret to Alice", None),
            ("it rained heavily all afternoon", None),
            ("Alice walked home alone", 2.0),
        ]
        for tick, (text, imp) in enumerate(events):
            stream.add_observation("a", text, tick=tick, day="Monday", importance=imp)
        got = stream.retrieve("a", "Bob and the cafe", k=4, now_tick=20)
        return [(r.id, round(r.importance, 6), r.last_accessed_tick) for r in got]

    assert run() == run()


def test_retrieve_k_larger_than_population():
    stream = make_stream()
    stream.add_observation("a", "only memory", tick=1, day="D")
    got = stream.retrieve("a", "memory", k=99, now_tick=2)
    assert len(got) == 1


def test_default_importance_clamped_to_ceiling():
    # A pathologically long, salient-heavy string must still clamp to <= 10.
    text = " ".join(["love hate fight died married won lost emergency"] * 20)
    assert default_importance(text) <= 10.0


def test_importance_clamped_on_explicit_out_of_range():
    stream = make_stream()
    hi = stream.add_observation("a", "x", tick=1, day="D", importance=999.0)
    lo = stream.add_observation("a", "y", tick=1, day="D", importance=-5.0)
    assert hi.importance == 10.0
    assert lo.importance == 1.0
