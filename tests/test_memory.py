"""Memory stream tests — V1 keyed memories by weekday name, so week-2 diaries
re-ingested week-1 events and the stream grew forever (F18)."""
from __future__ import annotations

import numpy as np

from townsim.cognition.memory import MemoryEntry, MemoryStream


def entry(text, day, tick, importance=0.5, kind="event", embedding=None):
    return MemoryEntry(text=text, day_index=day, tick=tick, importance=importance,
                       kind=kind, embedding=embedding)


class TestDayKeying:
    def test_same_weekday_different_weeks_are_distinct(self):
        stream = MemoryStream()
        stream.add(entry("monday week 1", day=0, tick=10))
        stream.add(entry("monday week 2", day=7, tick=5000))
        assert [e.text for e in stream.for_day(0)] == ["monday week 1"]
        assert [e.text for e in stream.for_day(7)] == ["monday week 2"]

    def test_summaries_excluded_from_day_view(self):
        stream = MemoryStream()
        stream.add(entry("event", day=0, tick=1))
        stream.add(entry("summary", day=0, tick=2, kind="summary"))
        assert len(stream.for_day(0)) == 1
        assert len(stream.summaries()) == 1


class TestRetrieval:
    def test_recency_prefers_newer(self):
        stream = MemoryStream()
        stream.add(entry("old", day=0, tick=0, importance=0.5))
        stream.add(entry("new", day=0, tick=900, importance=0.5))
        top = stream.retrieve(None, now_tick=1000, k=1)
        assert top[0].text == "new"

    def test_importance_can_beat_recency(self):
        stream = MemoryStream(decay_per_tick=0.999)
        stream.add(entry("vital old", day=0, tick=0, importance=1.0))
        stream.add(entry("trivial new", day=0, tick=990, importance=0.0))
        top = stream.retrieve(None, now_tick=1000, k=1)
        assert top[0].text == "vital old"

    def test_relevance_with_embeddings(self):
        stream = MemoryStream(alpha_recency=0.0, beta_importance=0.0)
        stream.add(entry("about cats", 0, 10, embedding=np.array([1.0, 0.0])))
        stream.add(entry("about dogs", 0, 10, embedding=np.array([0.0, 1.0])))
        top = stream.retrieve(np.array([1.0, 0.05]), now_tick=20, k=1)
        assert top[0].text == "about cats"

    def test_k_limits(self):
        stream = MemoryStream()
        for i in range(30):
            stream.add(entry(f"e{i}", 0, i))
        assert len(stream.retrieve(None, now_tick=100, k=12)) == 12


class TestCompaction:
    def test_compact_drops_old_events_keeps_summaries(self):
        stream = MemoryStream()
        for day in range(4):
            for i in range(10):
                stream.add(entry(f"d{day}e{i}", day, day * 100 + i))
        summary = entry("early days summary", 1, 400, kind="summary")
        removed = stream.compact_before(2, summary)
        assert removed == 20
        assert stream.for_day(0) == [] and stream.for_day(1) == []
        assert len(stream.for_day(2)) == 10
        assert [s.text for s in stream.summaries()] == ["early days summary"]
