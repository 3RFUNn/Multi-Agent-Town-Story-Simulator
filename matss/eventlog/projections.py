"""CQRS read-side projections over the canonical event stream.

In the event-sourced design the log is the only source of truth; every "current
state" view is a *projection* derived by folding events. This module holds those
projections, kept deliberately separate from the write path (the log/bus) so the
query models can evolve, be rebuilt, or be added without touching the core.

Two flavours live here:

* **Pure replay helpers** — :func:`replay_state_hashes` and
  :func:`reconstruct_world_canonical` reduce a finished (or partial) stream into
  the reproducibility hash chain or a point-in-time world snapshot. They rely
  only on the ``TICK_COMPLETED`` contract: the integrator emits one such event
  per tick with payload ``{"state_hash", "snapshot", "tick"}``.
* **Incremental read models** — :class:`LiveWorldReadModel` and
  :class:`NarrativeReadModel` consume events one at a time (``apply``) to
  maintain a cheap current view of, respectively, the live world and the
  post-hoc narrative artefacts.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from ..domain.enums import EventType
from ..domain.events import Event


def replay_state_hashes(events: Iterable[Event]) -> List[str]:
    """Collect the per-tick reproducibility hashes from a stream.

    Walks ``events`` and gathers ``payload["state_hash"]`` from every
    :data:`~matss.domain.enums.EventType.TICK_COMPLETED` event, in the order
    they appear (which is sequence order for a log read). Chaining or diffing
    these lists across runs is the reproducibility certificate.

    Args:
        events: An iterable of events, expected in sequence order.

    Returns:
        The list of state hashes, one per completed tick, in order. Events
        lacking a ``state_hash`` payload entry are skipped.
    """
    hashes: List[str] = []
    for event in events:
        if event.type == EventType.TICK_COMPLETED:
            value = event.payload.get("state_hash")
            if value is not None:
                hashes.append(value)
    return hashes


def reconstruct_world_canonical(
    events: Iterable[Event], at_tick: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """Return the canonical world snapshot at (or before) a given tick.

    Scans the ``TICK_COMPLETED`` events and returns the ``payload["snapshot"]``
    of the latest one whose ``payload["tick"]`` is ``<= at_tick``. With
    ``at_tick=None`` the snapshot of the last completed tick is returned.

    Args:
        events: An iterable of events, expected in sequence order.
        at_tick: Inclusive upper bound on tick. ``None`` selects the final
            completed tick.

    Returns:
        The selected world snapshot dict, or ``None`` if no matching
        ``TICK_COMPLETED`` event exists.
    """
    best: Optional[Dict[str, Any]] = None
    best_tick: Optional[int] = None
    for event in events:
        if event.type != EventType.TICK_COMPLETED:
            continue
        # The integrator contract guarantees payload["tick"]; fall back to the
        # always-present domain ``event.tick`` if a malformed payload omits it,
        # so the selection arithmetic never has to reason about ``None``.
        tick = event.payload.get("tick")
        if tick is None:
            tick = event.tick
        if at_tick is not None and tick > at_tick:
            continue
        # Among eligible ticks keep the highest tick; ties resolve to the later
        # event since iteration follows sequence order.
        if best_tick is None or tick >= best_tick:
            best = event.payload.get("snapshot")
            best_tick = tick
    return best


class LiveWorldReadModel:
    """Incremental projection of the live, per-agent world view.

    Folds granular domain events into a compact ``{agent_id: {...}}`` view
    suitable for a dashboard or the web gateway: latest position, current
    activity, money, and current interaction partner. Unknown event types are
    ignored, so the model is forward-compatible with new vocabulary.
    """

    def __init__(self) -> None:
        self._agents: Dict[str, Dict[str, Any]] = {}

    def _agent(self, agent_id: str) -> Dict[str, Any]:
        return self._agents.setdefault(
            agent_id,
            {
                "position": None,
                "current_activity": None,
                "money": None,
                "interacting_with": None,
            },
        )

    def apply(self, event: Event) -> None:
        """Update the view from a single event.

        Args:
            event: The event to fold in. Events without an ``agent_id`` (for
                the agent-keyed transitions) or of unhandled types are ignored.
        """
        etype = event.type
        payload = event.payload

        if etype == EventType.AGENT_MOVED:
            if event.agent_id is not None:
                to = payload.get("to")
                if to is not None:
                    self._agent(event.agent_id)["position"] = list(to)
        elif etype == EventType.ACTIVITY_STARTED:
            if event.agent_id is not None:
                self._agent(event.agent_id)["current_activity"] = payload.get(
                    "activity"
                )
        elif etype == EventType.MONEY_CHANGED:
            if event.agent_id is not None:
                self._agent(event.agent_id)["money"] = payload.get("money")
        elif etype == EventType.INTERACTION_STARTED:
            if event.agent_id is not None:
                self._agent(event.agent_id)["interacting_with"] = payload.get(
                    "with"
                )
        elif etype == EventType.INTERACTION_FINISHED:
            if event.agent_id is not None:
                self._agent(event.agent_id)["interacting_with"] = None

    def state(self) -> Dict[str, Dict[str, Any]]:
        """Return a deep-ish copy of the current per-agent view.

        Returns:
            A mapping ``agent_id -> {position, current_activity, money,
            interacting_with}``. The outer and inner dicts are fresh copies so
            callers cannot mutate the model's internals.
        """
        return {aid: dict(view) for aid, view in self._agents.items()}


class NarrativeReadModel:
    """Incremental projection of the Tier-2 narrative artefacts.

    Collects per-agent diaries and per-day compiled town stories from the
    post-hoc narrative events. Queries are by ``day_number`` (the integer day
    index supplied in the event payloads).
    """

    def __init__(self) -> None:
        # day_number -> {agent_id -> diary text}
        self._diaries: Dict[int, Dict[str, str]] = {}
        # day_number -> story text
        self._stories: Dict[int, str] = {}

    def apply(self, event: Event) -> None:
        """Update the narrative view from a single event.

        Args:
            event: A :data:`~matss.domain.enums.EventType.DIARY_WRITTEN` or
                :data:`~matss.domain.enums.EventType.STORY_COMPILED` event.
                Other event types are ignored.
        """
        payload = event.payload
        if event.type == EventType.DIARY_WRITTEN:
            day_number = payload.get("day_number")
            agent_id = payload.get("agent_id")
            text = payload.get("text", "")
            if day_number is not None and agent_id is not None:
                self._diaries.setdefault(day_number, {})[agent_id] = text
        elif event.type == EventType.STORY_COMPILED:
            day_number = payload.get("day_number")
            if day_number is not None:
                self._stories[day_number] = payload.get("text", "")

    def diaries_for_day(self, day_number: int) -> Dict[str, str]:
        """Return the agent diaries written for a given day.

        Args:
            day_number: The integer day index to look up.

        Returns:
            A fresh ``{agent_id: text}`` mapping (empty if none recorded).
        """
        return dict(self._diaries.get(day_number, {}))

    def story_for_day(self, day_number: int) -> Optional[str]:
        """Return the compiled town story for a given day, if any.

        Args:
            day_number: The integer day index to look up.

        Returns:
            The compiled story text, or ``None`` if no story was compiled for
            that day.
        """
        return self._stories.get(day_number)
