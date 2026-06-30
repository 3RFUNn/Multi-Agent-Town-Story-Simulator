"""Park-style reflection: synthesising high-level insights from observations.

When the accumulated importance of an agent's recent observations crosses a
threshold, the :class:`Reflector` asks an :class:`~matss.ports.LLMProvider` to
distil 1-3 higher-level insights and writes them back into the
:class:`~matss.memory.stream.MemoryStream` as ``kind="reflection"`` memories.
This mirrors Park et al.'s reflection loop and keeps provider usage minimal:
one balanced-tier call per reflection trigger.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..domain.memory import MemoryRecord
from ..ports import LLMProvider, LLMRequest, ModelTier
from .stream import MemoryStream

_DEFAULT_THRESHOLD = 15.0
_MAX_INSIGHTS = 3
_RECENT_WINDOW = 25


class Reflector:
    """Triggers and persists reflections over an agent's memory stream.

    Attributes:
        provider: The LLM provider used to synthesise insights.
        stream: The memory stream reflections are read from and written to.
    """

    def __init__(self, provider: LLMProvider, stream: MemoryStream) -> None:
        """Initialise the reflector.

        Args:
            provider: LLM provider used to synthesise insights.
            stream: Memory stream to read observations from and add reflections to.
        """
        self.provider = provider
        self.stream = stream
        # Per-agent index of the next observation to consider for reflection,
        # so importance is only counted once across calls.
        self._cursor: Dict[str, int] = {}

    def _pending_observations(self, agent_id: str) -> List[MemoryRecord]:
        """Return observations not yet consumed by a prior reflection trigger."""
        seen = self._cursor.get(agent_id, 0)
        observations = [
            r for r in self.stream.all(agent_id) if r.kind == "observation"
        ]
        return observations[seen:]

    def _build_request(
        self, agent_id: str, observations: List[MemoryRecord]
    ) -> LLMRequest:
        recent = observations[-_RECENT_WINDOW:]
        lines = "\n".join(f"- {r.text}" for r in recent)
        prompt = (
            f"You are reflecting on agent {agent_id}'s recent experiences.\n"
            f"Recent observations:\n{lines}\n\n"
            f"Synthesize {_MAX_INSIGHTS} or fewer high-level insights about "
            f"this agent. Write one insight per line, no numbering or bullets."
        )
        return LLMRequest(
            prompt=prompt,
            system="You distil concise, high-level insights from observations.",
            tier=ModelTier.BALANCED,
            max_tokens=256,
            metadata={"purpose": "reflection", "agent_id": agent_id},
        )

    @staticmethod
    def _parse_insights(text: str) -> List[str]:
        """Parse provider output into at most :data:`_MAX_INSIGHTS` insight lines."""
        insights: List[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            # Strip common leading list markers/numbering.
            line = line.lstrip("-*•0123456789.) ").strip()
            if line:
                insights.append(line)
            if len(insights) >= _MAX_INSIGHTS:
                break
        return insights

    def maybe_reflect(
        self,
        agent_id: str,
        now_tick: int,
        day: str,
        threshold: float = _DEFAULT_THRESHOLD,
    ) -> List[MemoryRecord]:
        """Reflect if recent observation importance has exceeded ``threshold``.

        The accumulated importance of observations not yet consumed by a prior
        successful reflection is summed; once it exceeds ``threshold`` a single
        balanced-tier provider call synthesises insights, which are added as
        reflection memories and the consumed-cursor is advanced.

        Args:
            agent_id: Agent to (possibly) reflect for.
            now_tick: Current simulation tick (used as the reflection's tick).
            day: Day label for the created reflection memories.
            threshold: Cumulative importance required to trigger a reflection.

        Returns:
            The reflection records created (empty if the threshold was not met
            or the provider produced no parseable insights).
        """
        pending = self._pending_observations(agent_id)
        if not pending:
            return []

        total_importance = sum(r.importance for r in pending)
        if total_importance < threshold:
            return []

        request = self._build_request(agent_id, pending)
        response = self.provider.complete(request)
        insights = self._parse_insights(response.text)

        # Mark these observations consumed regardless of parse outcome so we do
        # not re-trigger on the same backlog every tick.
        self._cursor[agent_id] = self._cursor.get(agent_id, 0) + len(pending)

        related: List[str] = []
        for r in pending:
            for other in r.related_agents:
                if other not in related:
                    related.append(other)

        reflections: List[MemoryRecord] = []
        for insight in insights:
            reflections.append(
                self.stream.add_reflection(
                    agent_id,
                    insight,
                    tick=now_tick,
                    day=day,
                    related_agents=related,
                )
            )
        return reflections
