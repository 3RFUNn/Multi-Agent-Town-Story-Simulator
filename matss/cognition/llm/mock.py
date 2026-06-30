"""A deterministic, offline mock :class:`~matss.ports.LLMProvider`.

The mock derives its output entirely from a stable hash of the request, so the
same request always yields the same response on any machine — the property the
whole engine's reproducibility rests on. It performs no I/O and is the default
provider used throughout the test suite and offline simulation runs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Sequence

from ... import ports
from ...ports import LLMRequest, LLMResponse, ModelTier
from . import structured

# A small bank of readable words used to render hash bytes into pseudo-prose.
_WORDBANK = (
    "the", "town", "agent", "thinks", "about", "morning", "coffee", "quiet",
    "street", "remembers", "yesterday", "plans", "to", "visit", "friend",
    "garden", "feels", "calm", "tired", "curious", "walks", "slowly", "past",
    "the", "market", "and", "wonders", "what", "comes", "next", "in", "story",
    "light", "rain", "begins", "while", "people", "gather", "near", "square",
)

# Maps a tier to a concrete pseudo-model name returned in the response.
_TIER_MODEL: Dict[str, str] = {
    ModelTier.CHEAP: "mock-cheap",
    ModelTier.BALANCED: "mock-balanced",
    ModelTier.FRONTIER: "mock-frontier",
}


def _digest_bytes(request: LLMRequest) -> bytes:
    """Return a stable digest of the salient request fields."""
    h = hashlib.blake2b(digest_size=32)
    parts = (
        request.system or "",
        request.prompt,
        request.tier,
        str(request.max_tokens),
    )
    h.update("\x00".join(parts).encode("utf-8"))
    return h.digest()


def _prose_from(digest: bytes, word_count: int) -> str:
    """Render ``digest`` bytes into a fixed number of readable pseudo-words."""
    words: List[str] = []
    n = len(_WORDBANK)
    for i in range(word_count):
        words.append(_WORDBANK[digest[i % len(digest)] % n])
        # Rotate the byte index a second way to avoid short cycles.
        if i and i % len(digest) == 0:
            digest = hashlib.blake2b(digest, digest_size=32).digest()
    sentence = " ".join(words)
    return sentence[:1].upper() + sentence[1:] + "."


class MockLLMProvider:
    """Deterministic, network-free LLM provider for tests and offline runs.

    Attributes:
        name: Provider name (``"mock"``), satisfying the port contract.
        calls: An append-only list of every :class:`LLMRequest` seen, for test
            assertions.
    """

    name: str = "mock"

    def __init__(self, words: int = 12) -> None:
        """Initialise the mock.

        Args:
            words: The number of pseudo-prose words to emit for free-text
                responses.
        """
        self._words = int(words)
        self.calls: List[LLMRequest] = []

    @property
    def call_count(self) -> int:
        """Number of :meth:`complete` invocations recorded so far."""
        return len(self.calls)

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Return a deterministic completion derived from ``request``.

        Args:
            request: The provider-agnostic request.

        Returns:
            A deterministic :class:`LLMResponse`. When ``request.response_schema``
            is set, ``structured`` holds a stub dict satisfying the schema's
            required keys and ``text`` is its canonical JSON.
        """
        self.calls.append(request)
        digest = _digest_bytes(request)
        model = _TIER_MODEL.get(request.tier, f"mock-{request.tier}")
        input_tokens = max(1, len(request.prompt.split()))

        structured_out: Optional[Dict[str, Any]] = None
        if request.response_schema is not None:
            # Deterministic seed from the digest so distinct requests differ.
            seed = digest[0] + 1
            structured_out = structured.build_stub(request.response_schema, seed)
            text = json.dumps(structured_out, sort_keys=True)
        else:
            text = _prose_from(digest, self._words)

        output_tokens = max(1, len(text.split()))
        return LLMResponse(
            text=text,
            model=model,
            tier=request.tier,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached=False,
            structured=structured_out,
            latency_ms=0.0,
            finish_reason="stop",
        )

    def batch(self, requests: Sequence[LLMRequest]) -> List[LLMResponse]:
        """Map :meth:`complete` over ``requests`` deterministically."""
        return [self.complete(r) for r in requests]


# Static contract conformance check (cheap, import-time).
assert isinstance(MockLLMProvider(), ports.LLMProvider)
