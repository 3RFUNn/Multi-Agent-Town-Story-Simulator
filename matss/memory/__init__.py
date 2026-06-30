"""Park-style memory stream for MATSS v2.

This package implements a *Generative Agents*-style memory architecture over a
pluggable vector store: observations and reflections are embedded and retrieved
by a deterministic blend of **recency**, **importance**, and **relevance**,
replacing the prototype's ``startswith(day)`` lookup.

Public surface:

* :class:`MockEmbeddingProvider` / :class:`OpenAIEmbeddingProvider` — embedders.
* :class:`InMemoryVectorStore` — brute-force cosine vector store.
* :class:`MemoryStream` — the retriever (:class:`~matss.ports.MemoryRetriever`).
* :class:`Reflector` — synthesises high-level insights from observations.
* :func:`default_importance` — the stdlib poignancy heuristic.
"""

from .embeddings import MockEmbeddingProvider, OpenAIEmbeddingProvider
from .vector_store import InMemoryVectorStore
from .stream import MemoryStream, default_importance
from .reflection import Reflector

__all__ = [
    "MockEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "InMemoryVectorStore",
    "MemoryStream",
    "default_importance",
    "Reflector",
]
