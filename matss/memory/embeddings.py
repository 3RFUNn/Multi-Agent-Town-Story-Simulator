"""Embedding providers for the Park-style memory stream.

Two adapters implement :class:`~matss.ports.EmbeddingProvider`:

* :class:`MockEmbeddingProvider` — a fully deterministic, stdlib-only embedder
  that hashes text tokens into a fixed-dimension, L2-normalised vector. It needs
  no network and is what the entire test/offline kernel runs against.
* :class:`OpenAIEmbeddingProvider` — a thin production adapter over OpenAI's
  embeddings HTTP API. It lazy-imports :mod:`requests` *inside* its methods so
  that importing this module never touches the network or requires the package.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import List, Optional, Sequence

# Tokenisation splits on any run of non-alphanumeric characters and lowercases,
# so embeddings are case/punctuation insensitive and stable across machines.
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _l2_normalize(vector: List[float]) -> List[float]:
    """Return ``vector`` scaled to unit L2 norm (zero vectors are returned as-is)."""
    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0.0:
        return vector
    return [component / norm for component in vector]


class MockEmbeddingProvider:
    """Deterministic, offline embedding provider for tests and local runs.

    The embedding of a piece of text is built by hashing each of its tokens into
    the fixed-dimension vector: every token contributes a signed unit of weight
    to one bucket (chosen by a hash of the token), and the accumulated vector is
    then L2-normalised. Identical text therefore always yields an identical
    unit-norm vector, and texts sharing tokens land closer together in cosine
    space — enough structure to exercise relevance-based retrieval deterministically.

    Attributes:
        dim: The fixed dimensionality of produced vectors.
    """

    def __init__(self, dim: int = 64) -> None:
        """Initialise the provider.

        Args:
            dim: Dimensionality of the produced embeddings. Must be positive.

        Raises:
            ValueError: If ``dim`` is not a positive integer.
        """
        if dim <= 0:
            raise ValueError(f"dim must be a positive integer, got {dim!r}")
        self.dim = int(dim)

    def embed(self, text: str) -> List[float]:
        """Embed a single string into a unit-norm vector of length :attr:`dim`.

        Args:
            text: The text to embed.

        Returns:
            An L2-normalised list of ``dim`` floats.
        """
        vector = [0.0] * self.dim
        tokens = _TOKEN_RE.findall(text.lower())
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            bucket = value % self.dim
            # Use a second bit of the hash for a deterministic sign so that
            # unrelated tokens do not all push in the same direction.
            sign = 1.0 if (value >> 63) & 1 else -1.0
            vector[bucket] += sign
        return _l2_normalize(vector)

    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        """Embed a batch of strings.

        Args:
            texts: The texts to embed.

        Returns:
            One unit-norm vector per input text, in input order.
        """
        return [self.embed(text) for text in texts]


class OpenAIEmbeddingProvider:
    """Production embedding adapter over the OpenAI embeddings HTTP API.

    The :mod:`requests` dependency is imported lazily inside the request methods
    so that importing this module never performs network I/O nor requires the
    package to be installed (mirroring the rest of the engine's adapter policy).

    Attributes:
        dim: The dimensionality requested from / returned by the model.
        model: The OpenAI embedding model name.
    """

    _ENDPOINT = "https://api.openai.com/v1/embeddings"

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        dim: int = 1536,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialise the adapter.

        Args:
            model: OpenAI embedding model identifier.
            dim: Requested embedding dimensionality (passed as ``dimensions``).
            api_key: API key; falls back to the ``OPENAI_API_KEY`` env var at
                request time when omitted.
            base_url: Optional override of the embeddings endpoint base.
            timeout: Per-request timeout in seconds.
        """
        self.model = model
        self.dim = int(dim)
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout

    def _resolve_key(self) -> str:
        key = self._api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError(
                "OpenAIEmbeddingProvider requires an api_key or the "
                "OPENAI_API_KEY environment variable to be set."
            )
        return key

    def _endpoint(self) -> str:
        if self._base_url:
            return self._base_url.rstrip("/") + "/embeddings"
        return self._ENDPOINT

    def _post(self, inputs: List[str]) -> List[List[float]]:
        import requests  # lazy import: no network/dependency at module import

        response = requests.post(
            self._endpoint(),
            headers={
                "Authorization": f"Bearer {self._resolve_key()}",
                "Content-Type": "application/json",
            },
            json={"model": self.model, "input": inputs, "dimensions": self.dim},
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        # Preserve request order via the ``index`` field returned by the API.
        rows = sorted(payload["data"], key=lambda row: row["index"])
        return [list(row["embedding"]) for row in rows]

    def embed(self, text: str) -> List[float]:
        """Embed a single string via the OpenAI API.

        Args:
            text: The text to embed.

        Returns:
            The embedding vector of length :attr:`dim`.
        """
        return self._post([text])[0]

    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        """Embed a batch of strings via the OpenAI API.

        Args:
            texts: The texts to embed.

        Returns:
            One embedding vector per input text, in input order.
        """
        if not texts:
            return []
        return self._post(list(texts))
