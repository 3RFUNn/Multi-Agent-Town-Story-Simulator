"""LLM-as-judge evaluation of generated narrative (report recommendation #10).

:class:`LLMJudge` scores a piece of generated text along a set of qualitative
dimensions (coherence, character consistency, ...) on a 1-10 scale, using a
:data:`~matss.ports.ModelTier.FRONTIER` structured-output call. The scoring
contract is expressed as a JSON ``response_schema`` so a conforming provider
returns a parseable :attr:`~matss.ports.LLMResponse.structured` dict; the judge
then clamps each score into ``[1, 10]`` defensively.

Given a deterministic provider, the judge is itself fully deterministic.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Sequence, Tuple

from ..ports import LLMProvider, LLMRequest, ModelTier

DEFAULT_DIMENSIONS: Tuple[str, ...] = (
    "coherence",
    "character_consistency",
    "interestingness",
    "faithfulness",
)

# The valid score range for every dimension.
_MIN_SCORE = 1.0
_MAX_SCORE = 10.0


class LLMJudge:
    """Scores generated text along named quality dimensions on a 1-10 scale.

    Attributes:
        provider: The LLM provider used to produce structured scores.
    """

    def __init__(self, provider: LLMProvider) -> None:
        """Initialise the judge.

        Args:
            provider: A :class:`~matss.ports.LLMProvider` implementation.
        """
        self.provider = provider

    def _schema(self, dimensions: Sequence[str]) -> Dict[str, Any]:
        """Build the JSON response schema requiring each dimension as a number."""
        properties = {
            dim: {
                "type": "number",
                "minimum": _MIN_SCORE,
                "maximum": _MAX_SCORE,
                "description": f"Score for {dim} from 1 (poor) to 10 (excellent).",
            }
            for dim in dimensions
        }
        return {
            "type": "object",
            "properties": properties,
            "required": list(dimensions),
        }

    def score(
        self,
        text: str,
        dimensions: Sequence[str] = DEFAULT_DIMENSIONS,
    ) -> Dict[str, float]:
        """Score ``text`` along each dimension on a 1-10 scale.

        Args:
            text: The narrative text to evaluate.
            dimensions: The quality dimensions to score. Defaults to
                :data:`DEFAULT_DIMENSIONS`.

        Returns:
            A mapping of ``dimension -> float`` where every value lies within
            ``[1.0, 10.0]``. Every requested dimension is always present.
        """
        dims: Tuple[str, ...] = tuple(dimensions)
        schema = self._schema(dims)

        dim_list = ", ".join(dims)
        prompt = (
            "You are an impartial literary judge. Evaluate the following text on "
            f"each of these dimensions: {dim_list}. Score every dimension as a "
            "number from 1 (poor) to 10 (excellent). Respond with the structured "
            "JSON object only.\n\n"
            "=== TEXT TO EVALUATE ===\n"
            f"{text}\n"
            "=== END TEXT ==="
        )

        request = LLMRequest(
            prompt=prompt,
            tier=ModelTier.FRONTIER,
            max_tokens=512,
            temperature=0.0,
            response_schema=schema,
            metadata={"kind": "judge", "dimensions": list(dims)},
        )
        response = self.provider.complete(request)
        raw = self._extract(response.structured, response.text)

        scores: Dict[str, float] = {}
        for dim in dims:
            scores[dim] = self._clamp(raw.get(dim))
        return scores

    @staticmethod
    def _extract(
        structured: Optional[Dict[str, Any]], text: str
    ) -> Dict[str, Any]:
        """Return the structured dict, falling back to parsing ``text`` as JSON."""
        if isinstance(structured, dict):
            return structured
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _clamp(value: Any) -> float:
        """Coerce ``value`` to a float clamped into ``[1, 10]``.

        Non-numeric or missing values default to the midpoint, keeping the
        result within range so downstream aggregation never sees an out-of-band
        score.
        """
        try:
            num = float(value)
        except (TypeError, ValueError):
            num = (_MIN_SCORE + _MAX_SCORE) / 2.0
        if num < _MIN_SCORE:
            return _MIN_SCORE
        if num > _MAX_SCORE:
            return _MAX_SCORE
        return num
