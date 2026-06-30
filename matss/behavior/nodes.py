"""Condition and action nodes for the agent Behavior Tree.

Each node is a deterministic port of the legacy ``agent_behaviors.py`` adapted
to the frozen :class:`~matss.runtime.DecisionContext` contract:

* Reads come from ``ctx.agent`` / ``ctx.world`` / ``ctx.content``.
* Randomness goes through ``ctx.rng_stream(name)`` — never the global RNG.
* Side effects are limited to mutating the agent aggregate, recording an
  agent-facing line via ``ctx.observe(text)``, and recording domain events via
  ``ctx.emit(event_type, **payload)``.

Nodes never run pathfinding: a movement intent is expressed by setting
``agent.destination_name`` and ``agent.state = AgentState.MOVING``; the engine
resolves the actual path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from ..domain.enums import AgentState, EventType, Need
from .tree import Node, SimulationSummary, Status

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..runtime import DecisionContext
    from ..domain.agent import Agent


# Locations the legacy prototype used for ad-hoc rest/eat fallbacks.
_REST_LOCATIONS = ("central_park", "downtown_cafe")
_EAT_LOCATION = "downtown_cafe"
_EAT_COST = 10.0
_SOCIAL_RANGE = 6  # Manhattan-ish proximity window for spotting a chat partner.


def _activity_data(ctx: "DecisionContext", activity: Optional[str]) -> Optional[dict]:
    """Resolve an activity's data, preferring the live world view.

    Action nodes register ad-hoc activities (``take_a_short_rest``,
    ``eat_at_cafe``) on ``ctx.world.activity_data``; the static content catalog
    only holds the authored activities. Reading the world first (then falling
    back to content) is what lets the rest/eat round-trip resolve its own
    location and cost — without it the agent never reaches ``ExecuteRest`` /
    ``ExecuteEat``.
    """
    if not activity:
        return None
    data = ctx.world.activity_data.get(activity)
    if data is None:
        data = ctx.content.activity_data.get(activity)
    return data


def _activity_location(ctx: "DecisionContext", activity: str) -> Optional[str]:
    """Return the configured location name for an activity, if any."""
    data = _activity_data(ctx, activity)
    if not data:
        return None
    return data.get("location")


def _is_at_place(ctx: "DecisionContext", place_name: str) -> bool:
    """Whether the agent currently stands on a tile of ``place_name``."""
    place = ctx.world.places.get(place_name)
    if place is None:
        return False
    return place.contains(ctx.agent.x, ctx.agent.y)


# ===========================================================================
# Condition nodes
# ===========================================================================

class IsNeedCritical(Node):
    """Succeeds when a named need has reached a critical threshold."""

    def __init__(self, name: str, need: str, threshold: float) -> None:
        super().__init__(name)
        self.need = need
        self.threshold = float(threshold)

    def tick(self, ctx: "DecisionContext") -> Status:
        if ctx.agent.needs.get(self.need, 0.0) >= self.threshold:
            ctx.emit(
                EventType.NEED_CRITICAL,
                need=self.need,
                value=ctx.agent.needs.get(self.need, 0.0),
                threshold=self.threshold,
            )
            return Status.SUCCESS
        return Status.FAILURE


class IsAgentTired(Node):
    """Succeeds when the agent's energy need is at or above ``threshold``."""

    def __init__(self, name: str, threshold: float = 75.0) -> None:
        super().__init__(name)
        self.threshold = float(threshold)

    def tick(self, ctx: "DecisionContext") -> Status:
        energy = ctx.agent.needs.get(Need.ENERGY, 0.0)
        if energy >= self.threshold:
            ctx.observe(
                f"I'm feeling quite tired (Energy Need: {energy:.1f}). "
                "I should find a place to rest."
            )
            return Status.SUCCESS
        return Status.FAILURE


class IsScheduledActivity(Node):
    """Succeeds when the agent currently has a scheduled activity assigned."""

    def tick(self, ctx: "DecisionContext") -> Status:
        return Status.SUCCESS if ctx.agent.current_activity else Status.FAILURE


class HasEnoughMoney(Node):
    """Succeeds when the agent can afford its current activity."""

    def tick(self, ctx: "DecisionContext") -> Status:
        activity = ctx.agent.current_activity
        data = _activity_data(ctx, activity)
        cost = float(data["cost"]) if data and "cost" in data else 0.0
        if data is None or ctx.agent.money >= cost:
            return Status.SUCCESS
        ctx.observe(
            f"I can't afford to {str(activity).replace('_', ' ')}, "
            f"I only have ${ctx.agent.money:.2f}."
        )
        return Status.FAILURE


class IsAtActivityLocation(Node):
    """Succeeds when the agent is at the location for its current activity."""

    def tick(self, ctx: "DecisionContext") -> Status:
        activity = ctx.agent.current_activity
        if not activity:
            return Status.FAILURE

        if "home" in activity or "sleep" in activity:
            home = ctx.agent.defn.home_pos
            return Status.SUCCESS if ctx.agent.pos == home else Status.FAILURE

        location_name = _activity_location(ctx, activity)
        if not location_name:
            return Status.FAILURE
        return Status.SUCCESS if _is_at_place(ctx, location_name) else Status.FAILURE


class ShouldSocialize(Node):
    """Succeeds when personality + social need + a seeded roll favour socialising."""

    def tick(self, ctx: "DecisionContext") -> Status:
        agent = ctx.agent
        social = agent.needs.get(Need.SOCIAL, 0.0)
        talkativeness = agent.trait("talkativeness", 0.5)
        roll = ctx.rng_stream("socialize").random()

        if agent.has_personality("extrovert") and social > 30 and roll < (0.4 * talkativeness):
            ctx.observe(
                f"I'm feeling social (Social need: {social:.1f}). "
                "Let me find someone to talk to."
            )
            return Status.SUCCESS
        if agent.has_personality("introvert") and social > 70 and roll < (0.3 * talkativeness):
            ctx.observe(
                f"I really need some social interaction (Social need: {social:.1f}). "
                "Maybe I should find someone to chat with."
            )
            return Status.SUCCESS
        return Status.FAILURE


# ===========================================================================
# Action nodes
# ===========================================================================

class FindAgentToTalkTo(Node):
    """Selects a nearby idle agent and sets a movement intent to greet them."""

    def _candidates(self, ctx: "DecisionContext") -> List["Agent"]:
        agent = ctx.agent
        out: List["Agent"] = []
        for other in ctx.world.agent_list():  # id-sorted for determinism
            if other.id == agent.id:
                continue
            if other.state != AgentState.IDLE:
                continue
            if abs(other.x - agent.x) < _SOCIAL_RANGE and abs(other.y - agent.y) < _SOCIAL_RANGE:
                out.append(other)
        return out

    def tick(self, ctx: "DecisionContext") -> Status:
        agent = ctx.agent
        candidates = self._candidates(ctx)
        if not candidates:
            ctx.observe("I looked around but didn't see anyone available to chat with.")
            return Status.FAILURE

        friends = [
            t for t in candidates
            if (rel := agent.get_relationship(t.id)) is not None and rel.affinity > 70
        ]
        pool = friends if friends else candidates
        target = ctx.rng_stream("talk_target").choice(pool)

        agent.interacting_with = target.id
        agent.destination_name = f"agent_{target.id}"
        agent.state = AgentState.MOVING
        agent.current_goal = f"Going to have a conversation with {target.name}"

        rel = agent.get_relationship(target.id)
        rel_type = rel.type if rel else "someone"
        ctx.observe(
            f"I spotted {target.name} nearby. They're my {rel_type}, so I'll go say hello."
        )
        ctx.emit(EventType.DECISION_MADE, decision="seek_conversation", target=target.id)
        return Status.SUCCESS

    def simulate(self, ctx: "DecisionContext", summary: SimulationSummary) -> SimulationSummary:
        # A conversation is predicted to substantially drop the social need at a
        # small energy cost — this is the real prediction the planner scores.
        out = summary.copy()
        out.final_needs[Need.SOCIAL] = max(0.0, out.final_needs.get(Need.SOCIAL, 0.0) - 40.0)
        out.final_needs[Need.ENERGY] = max(0.0, out.final_needs.get(Need.ENERGY, 0.0) - 3.0)
        return out


class ExecuteActivity(Node):
    """Performs the agent's current scheduled activity (paying its cost)."""

    def __init__(self, name: str, duration: int = 8) -> None:
        super().__init__(name)
        self.duration = duration

    def _apply_need_effects(self, agent: "Agent", activity: str) -> None:
        needs = agent.needs
        if any(tok in activity for tok in ("eat", "lunch", "dinner", "breakfast", "brunch")):
            needs[Need.HUNGER] = max(0.0, needs[Need.HUNGER] - 50.0)
            needs[Need.ENERGY] = max(0.0, needs[Need.ENERGY] - 20.0)
        elif "coffee" in activity:
            needs[Need.HUNGER] = max(0.0, needs[Need.HUNGER] - 15.0)
            needs[Need.ENERGY] = max(0.0, needs[Need.ENERGY] - 15.0)

        if any(tok in activity for tok in ("socialize", "drinks", "party")):
            needs[Need.SOCIAL] = max(0.0, needs[Need.SOCIAL] - 60.0)

        if any(tok in activity for tok in ("workout", "gym", "training", "exercise")):
            needs[Need.ENERGY] = min(100.0, needs[Need.ENERGY] + 5.0)
            if agent.has_personality("fitness_enthusiast"):
                needs[Need.SOCIAL] = max(0.0, needs[Need.SOCIAL] - 10.0)

        if any(tok in activity for tok in ("relax", "leisure", "park")):
            needs[Need.ENERGY] = max(0.0, needs[Need.ENERGY] - 25.0)

        if "sleep" in activity:
            needs[Need.ENERGY] = max(0.0, needs[Need.ENERGY] - 90.0)

    def tick(self, ctx: "DecisionContext") -> Status:
        agent = ctx.agent
        activity = agent.current_activity
        if not activity:
            return Status.FAILURE

        data = _activity_data(ctx, activity) or {}
        cost = float(data.get("cost", 0.0))
        if agent.money < cost:
            return Status.FAILURE

        if cost:
            agent.money -= cost
            ctx.emit(EventType.MONEY_CHANGED, delta=-cost, balance=agent.money, reason=activity)

        agent.state = AgentState.DOING_ACTION
        agent.action_duration = self.duration
        pretty = activity.replace("_", " ")
        agent.current_action = pretty.title()
        agent.current_goal = f"Completing my {pretty} activity"

        location = data.get("location", "my destination")
        ctx.observe(
            f"I've arrived at the {str(location).replace('_', ' ')}. Time to {pretty}."
        )
        self._apply_need_effects(agent, activity)
        ctx.emit(EventType.ACTIVITY_STARTED, activity=activity, location=location, cost=cost)
        return Status.RUNNING

    def simulate(self, ctx: "DecisionContext", summary: SimulationSummary) -> SimulationSummary:
        agent = ctx.agent
        activity = agent.current_activity
        if not activity:
            return summary
        out = summary.copy()
        data = _activity_data(ctx, activity) or {}
        out.final_money -= float(data.get("cost", 0.0))

        needs = out.final_needs
        if any(tok in activity for tok in ("eat", "lunch", "dinner", "breakfast", "brunch")):
            needs[Need.HUNGER] = max(0.0, needs.get(Need.HUNGER, 0.0) - 50.0)
            needs[Need.ENERGY] = max(0.0, needs.get(Need.ENERGY, 0.0) - 20.0)
        if any(tok in activity for tok in ("socialize", "drinks", "party")):
            needs[Need.SOCIAL] = max(0.0, needs.get(Need.SOCIAL, 0.0) - 60.0)
        if any(tok in activity for tok in ("workout", "gym", "training", "exercise")):
            needs[Need.ENERGY] = min(100.0, needs.get(Need.ENERGY, 0.0) + 5.0)
        if any(tok in activity for tok in ("relax", "park")):
            needs[Need.ENERGY] = max(0.0, needs.get(Need.ENERGY, 0.0) - 25.0)
        if "sleep" in activity:
            needs[Need.ENERGY] = max(0.0, needs.get(Need.ENERGY, 0.0) - 90.0)
        return out


class PlanPathToActivityLocation(Node):
    """Sets a movement intent toward the current activity's location."""

    def tick(self, ctx: "DecisionContext") -> Status:
        agent = ctx.agent
        activity = agent.current_activity
        if not activity:
            return Status.FAILURE

        if "home" in activity or "sleep" in activity:
            agent.destination_name = f"{agent.id}_home"
            agent.current_goal = "Heading home to rest and recharge"
            ctx.observe(f"Time to head home. I need to {activity.replace('_', ' ')}.")
        else:
            location_name = _activity_location(ctx, activity)
            if not location_name:
                return Status.FAILURE
            agent.destination_name = location_name
            pretty_loc = location_name.replace("_", " ")
            agent.current_goal = f"Going to {pretty_loc} to {activity.replace('_', ' ')}"
            ctx.observe(
                f"According to my schedule, it's time to {activity.replace('_', ' ')}. "
                f"Let me head over to {pretty_loc}."
            )

        agent.state = AgentState.MOVING
        ctx.emit(EventType.DECISION_MADE, decision="go_to_activity", activity=activity)
        return Status.SUCCESS

    def simulate(self, ctx: "DecisionContext", summary: SimulationSummary) -> SimulationSummary:
        out = summary.copy()
        out.final_needs[Need.ENERGY] = min(100.0, out.final_needs.get(Need.ENERGY, 0.0) + 2.0)
        return out


class PlanPathToHome(Node):
    """Sets an emergency movement intent toward the agent's home."""

    def tick(self, ctx: "DecisionContext") -> Status:
        agent = ctx.agent
        agent.destination_name = f"{agent.id}_home"
        agent.state = AgentState.MOVING
        agent.current_goal = "Going home to get some sleep"
        ctx.observe(
            "I'm completely drained. I need to get home immediately and get some rest."
        )
        ctx.emit(EventType.DECISION_MADE, decision="emergency_go_home")
        return Status.SUCCESS

    def simulate(self, ctx: "DecisionContext", summary: SimulationSummary) -> SimulationSummary:
        out = summary.copy()
        out.final_needs[Need.ENERGY] = min(100.0, out.final_needs.get(Need.ENERGY, 0.0) + 2.0)
        return out


class PlanPathToRestLocation(Node):
    """Picks a rest spot (once per rest event) and heads there."""

    def __init__(self, name: str, rest_locations=_REST_LOCATIONS) -> None:
        super().__init__(name)
        self.rest_locations = tuple(rest_locations)

    def tick(self, ctx: "DecisionContext") -> Status:
        agent = ctx.agent
        if agent.rest_location is None:
            agent.rest_location = ctx.rng_stream("rest_location").choice(list(self.rest_locations))
            agent.rest_ticks = 0
        agent.destination_name = agent.rest_location
        agent.state = AgentState.MOVING
        agent.current_activity = "take_a_short_rest"
        agent.current_goal = (
            f"Going to the {agent.rest_location.replace('_', ' ')} to rest for a bit"
        )
        # Register the ad-hoc activity so location/cost lookups resolve.
        ctx.world.activity_data["take_a_short_rest"] = {
            "location": agent.rest_location,
            "cost": 0,
        }
        ctx.observe(
            f"I'm feeling tired, so I'll head to the "
            f"{agent.rest_location.replace('_', ' ')} to recharge."
        )
        ctx.emit(EventType.DECISION_MADE, decision="go_rest", location=agent.rest_location)
        return Status.SUCCESS

    def simulate(self, ctx: "DecisionContext", summary: SimulationSummary) -> SimulationSummary:
        out = summary.copy()
        out.final_needs[Need.ENERGY] = min(100.0, out.final_needs.get(Need.ENERGY, 0.0) + 2.0)
        return out


class ExecuteRest(Node):
    """Recovers energy by resting in place."""

    def __init__(self, name: str, duration: int = 10) -> None:
        super().__init__(name)
        self.duration = duration

    def tick(self, ctx: "DecisionContext") -> Status:
        agent = ctx.agent
        agent.state = AgentState.DOING_ACTION
        agent.action_duration = self.duration
        agent.current_action = "Taking a short break to recharge"
        agent.current_goal = "Resting to regain some energy"
        agent.rest_ticks += 1
        if agent.rest_ticks >= 1:
            agent.needs[Need.ENERGY] = max(0.0, agent.needs[Need.ENERGY] - 70.0)
            agent.rest_location = None
            agent.rest_ticks = 0
            agent.current_activity = None
        ctx.observe("Ah, much better. Taking a moment to rest here.")
        ctx.emit(EventType.RESTED, energy=agent.needs[Need.ENERGY])
        return Status.RUNNING

    def simulate(self, ctx: "DecisionContext", summary: SimulationSummary) -> SimulationSummary:
        out = summary.copy()
        out.final_needs[Need.ENERGY] = max(0.0, out.final_needs.get(Need.ENERGY, 0.0) - 70.0)
        return out


class PlanPathToEatLocation(Node):
    """Heads to a cafe to eat when hungry."""

    def __init__(self, name: str, eat_location: str = _EAT_LOCATION) -> None:
        super().__init__(name)
        self.eat_location = eat_location

    def tick(self, ctx: "DecisionContext") -> Status:
        agent = ctx.agent
        agent.destination_name = self.eat_location
        agent.state = AgentState.MOVING
        agent.current_goal = "Going to the cafe to eat and refuel"
        agent.current_activity = "eat_at_cafe"
        ctx.world.activity_data["eat_at_cafe"] = {
            "location": self.eat_location,
            "cost": _EAT_COST,
        }
        ctx.observe("I'm really hungry, so I'll head to the cafe to eat.")
        ctx.emit(EventType.DECISION_MADE, decision="go_eat", location=self.eat_location)
        return Status.SUCCESS

    def simulate(self, ctx: "DecisionContext", summary: SimulationSummary) -> SimulationSummary:
        out = summary.copy()
        out.final_needs[Need.ENERGY] = min(100.0, out.final_needs.get(Need.ENERGY, 0.0) + 2.0)
        return out


class ExecuteEat(Node):
    """Recovers hunger by eating in place."""

    def __init__(self, name: str, duration: int = 10) -> None:
        super().__init__(name)
        self.duration = duration

    def tick(self, ctx: "DecisionContext") -> Status:
        agent = ctx.agent
        agent.state = AgentState.DOING_ACTION
        agent.action_duration = self.duration
        agent.current_action = "Eating at the cafe"
        agent.current_goal = "Refueling and satisfying hunger"
        agent.eat_ticks += 1
        if agent.eat_ticks >= 1:
            agent.needs[Need.HUNGER] = max(0.0, agent.needs[Need.HUNGER] - 70.0)
            agent.eat_ticks = 0
            agent.current_activity = None
        ctx.observe("That meal hit the spot. Feeling much better now.")
        ctx.emit(EventType.ATE, hunger=agent.needs[Need.HUNGER])
        return Status.RUNNING

    def simulate(self, ctx: "DecisionContext", summary: SimulationSummary) -> SimulationSummary:
        out = summary.copy()
        out.final_needs[Need.HUNGER] = max(0.0, out.final_needs.get(Need.HUNGER, 0.0) - 70.0)
        return out


class Idle(Node):
    """Default fallback behaviour when nothing else applies."""

    def tick(self, ctx: "DecisionContext") -> Status:
        agent = ctx.agent
        if agent.has_personality("lazy"):
            agent.current_goal = "Taking it easy and enjoying some downtime"
            agent.current_action = "Lounging around and relaxing"
        elif agent.has_personality("curious"):
            agent.current_goal = "Looking around and observing my surroundings"
            agent.current_action = "Exploring and being curious"
        elif agent.has_personality("social_butterfly"):
            agent.current_goal = "Looking for interesting people to meet"
            agent.current_action = "Scanning for social opportunities"
        else:
            agent.current_goal = "Taking a moment to think and plan"
            agent.current_action = "Contemplating my next move"
        agent.state = AgentState.IDLE
        return Status.SUCCESS
