"""Behavior-tree leaf node library.

Every "do X somewhere" behavior uses the location-guard idiom from core
(guarded_move), fixing V1's teleport-eat (F05) and nap-anywhere (F11) bugs.
All timed effects are applied exactly once when the action starts; costs are
charged once per schedule slot (F13).
"""
from __future__ import annotations

from collections.abc import Callable

from townsim.agents.components import ActionState, MoveIntent
from townsim.agents.schedule import slot_for, ticks_until_hour
from townsim.behavior.blackboard import Scope
from townsim.behavior.core import Leaf, Status, TickContext
from townsim.config.content import ACTIVITY_DATA


def pretty(key: str) -> str:
    return key.replace("_", " ")


ACTIVITY_FLAVOR: dict[str, tuple[str, str]] = {
    # kind -> (current_action, current_goal)
    "work": ("Working through tasks and meetings", "Getting my work done"),
    "shift": ("Serving customers behind the counter", "Keeping the cafe running"),
    "classes": ("Attending lectures and taking notes", "Keeping up with my classes"),
    "study": ("Studying and working through problems", "Staying on top of coursework"),
    "meal": ("Eating and taking a breather", "Refueling"),
    "workout": ("Training hard at the gym", "Staying strong and healthy"),
    "social": ("Hanging out and chatting", "Enjoying time with people"),
    "leisure": ("Relaxing and people-watching", "Unwinding for a while"),
    "rest": ("Taking a short break", "Recovering some energy"),
    "sleep": ("Sleeping soundly", "Getting a good night's rest"),
    "errand": ("Running errands", "Ticking things off the list"),
}


def _apply_start_effects(ctx: TickContext, kind: str) -> None:
    needs_cfg = ctx.cfg.needs
    needs = ctx.agent.needs
    if kind == "meal":
        needs.hunger -= needs_cfg.meal_hunger_relief
        ctx.emit("meal_eaten", relief=needs_cfg.meal_hunger_relief)
    elif kind == "rest":
        needs.fatigue -= needs_cfg.rest_fatigue_relief
        ctx.emit("rest_taken", relief=needs_cfg.rest_fatigue_relief)
    elif kind == "workout":
        needs.fatigue += 5.0
        if "fitness_enthusiast" in ctx.agent.spec.personality:
            needs.social -= 10.0
    needs.clamp()


def _begin_action(ctx: TickContext, activity: str, kind: str, until_tick: int,
                  emergency: bool = False) -> None:
    agent = ctx.agent
    agent.action = ActionState(activity=activity, kind=kind,
                               until_tick=until_tick, started_tick=ctx.now.tick)
    agent.state = "doing_action"
    action_text, goal_text = ACTIVITY_FLAVOR.get(kind, (pretty(activity).capitalize(), ""))
    agent.current_action = action_text
    agent.current_goal = goal_text or f"Finishing {pretty(activity)}"
    if kind == "sleep":
        ctx.emit("sleep_started", activity=activity, until=until_tick, emergency=emergency)
    else:
        ctx.emit("activity_started", activity=activity, kind=kind, until=until_tick)
    _apply_start_effects(ctx, kind)


class GoTo(Leaf):
    """Travel to a place (the key may be 'home'). RUNNING while moving,
    SUCCESS on arrival, FAILURE if no path could be found."""

    def __init__(self, name: str, place_fn: Callable[[TickContext], str], reason: str) -> None:
        super().__init__(name)
        self._place_fn = place_fn
        self._reason = reason

    def run(self, ctx: TickContext) -> Status:
        agent = ctx.agent
        place = self._place_fn(ctx)
        if ctx.world.is_at_place(agent, place):
            if agent.state == "moving":
                agent.state = "idle"
            agent.move_intent = None
            return Status.SUCCESS
        if agent.path_failed:
            agent.path_failed = False
            agent.move_intent = None
            if agent.state == "moving":
                agent.state = "idle"
            ctx.log(f"I couldn't find a way to the {pretty(place)}.", importance=0.3)
            return Status.FAILURE
        intent = agent.move_intent
        if not (intent and intent.kind == "place" and intent.key == place):
            agent.move_intent = MoveIntent(kind="place", key=place, reason=self._reason)
            agent.current_goal = f"Heading to the {pretty(place)}" if place != "home" \
                else "Heading home"
            agent.current_action = "Walking"
        agent.state = "moving"
        return Status.RUNNING


class StartScheduledActivity(Leaf):
    """Begin the scheduled activity (agent is already at its location).
    Charges the slot cost exactly once (F13); FAILURE if unaffordable so the
    tree can fall back to free-time behavior."""

    def run(self, ctx: TickContext) -> Status:
        agent, now = ctx.agent, ctx.now
        activity = agent.current_activity
        if activity is None:
            return Status.FAILURE
        data = ACTIVITY_DATA[activity]
        start_hour, end_hour = slot_for(agent, now, activity)
        slot_key = (now.day_index, activity, start_hour)
        cost = data["cost"]
        already_paid = slot_key in agent.wallet.paid_slots
        if cost > 0 and not already_paid and agent.wallet.money < cost:
            ctx.log(f"I can't afford to {pretty(activity)} right now "
                    f"(${agent.wallet.money:.0f} on hand).", importance=0.5)
            return Status.FAILURE
        if cost > 0 and not already_paid:
            agent.wallet.money -= cost
            agent.wallet.paid_slots.add(slot_key)
            ctx.emit("cost_paid", activity=activity, amount=cost)
        until = now.tick + ticks_until_hour(now, end_hour, ctx.cfg.kernel.tick_minutes)
        _begin_action(ctx, activity, data["kind"], until)
        location = data["location"]
        place_label = "home" if location == "home" else f"the {pretty(location)}"
        ctx.log(f"Started {pretty(activity)} at {place_label}.",
                importance=0.35 if data["kind"] in ("work", "shift", "classes") else 0.4,
                location=location)
        return Status.RUNNING


class EatEmergencyMeal(Leaf):
    """Hunger emergency: buy and eat a meal at the cafe (F05: only ever runs
    behind an at-location guard, and it actually pays)."""

    DURATION_MINUTES = 30

    def run(self, ctx: TickContext) -> Status:
        agent = ctx.agent
        data = ACTIVITY_DATA["eat_at_cafe"]
        cost = data["cost"]
        if agent.wallet.money < cost:
            ctx.log("I'm starving but I can't even afford a cafe meal.", importance=0.7)
            return Status.FAILURE
        agent.wallet.money -= cost
        ctx.emit("cost_paid", activity="eat_at_cafe", amount=cost)
        until = ctx.now.tick + max(1, self.DURATION_MINUTES // ctx.cfg.kernel.tick_minutes)
        _begin_action(ctx, "eat_at_cafe", "meal", until)
        ctx.log("Grabbed a proper meal at the cafe — I was starving.",
                importance=0.5, location="downtown_cafe")
        return Status.RUNNING


class TakeRest(Leaf):
    """Short break at the agent's chosen rest spot (agent-scoped blackboard,
    fixing V1's shared-dict clobbering — F20)."""

    DURATION_MINUTES = 30

    def run(self, ctx: TickContext) -> Status:
        agent = ctx.agent
        until = ctx.now.tick + max(1, self.DURATION_MINUTES // ctx.cfg.kernel.tick_minutes)
        _begin_action(ctx, "take_a_short_rest", "rest", until)
        spot = ctx.bb.get(Scope.AGENT, agent.id, "rest_spot", "central_park")
        ctx.bb.delete(Scope.AGENT, agent.id, "rest_spot")
        ctx.log(f"Taking a breather at the {pretty(spot)}.", importance=0.3, location=spot)
        return Status.RUNNING


class EmergencySleep(Leaf):
    """Exhaustion emergency: actually sleep at home even outside the
    scheduled window (fixes V1's pacing livelock — F12)."""

    DURATION_HOURS = 3

    def run(self, ctx: TickContext) -> Status:
        agent = ctx.agent
        until = ctx.now.tick + (self.DURATION_HOURS * 60) // ctx.cfg.kernel.tick_minutes
        _begin_action(ctx, "sleep_at_home", "sleep", until, emergency=True)
        ctx.log("Completely drained — collapsing into bed for a few hours.",
                importance=0.55, location=agent.spec.home_place)
        return Status.RUNNING


def rest_spot_for(ctx: TickContext) -> str:
    """Choose (once) and remember this agent's rest spot."""
    agent_id = ctx.agent.id
    spot = ctx.bb.get(Scope.AGENT, agent_id, "rest_spot")
    if spot is None:
        spot = ctx.rng.choice(["central_park", "downtown_cafe"])
        ctx.bb.set(Scope.AGENT, agent_id, "rest_spot", spot)
    return spot


class ApproachAndChat(Leaf):
    """Free-time socializing: find a nearby idle agent (friends preferred),
    walk over, and request a conversation. The interaction system validates
    adjacency and availability before starting anything (F16)."""

    def run(self, ctx: TickContext) -> Status:
        agent, world = ctx.agent, ctx.world
        icfg = ctx.cfg.interaction

        if ctx.bb.get(Scope.AGENT, agent.id, "social_rebuffed"):
            ctx.bb.delete(Scope.AGENT, agent.id, "social_rebuffed")
            agent.social_target = None
            return Status.FAILURE

        target_id = agent.social_target
        if target_id is not None:
            target = world.agents.get(target_id)
            if target is None or target.state not in ("idle", "moving"):
                agent.social_target = None
                agent.move_intent = None
                if agent.state == "moving":
                    agent.state = "idle"
                return Status.FAILURE
            if world.chebyshev(agent.pos, target.pos) <= icfg.adjacency_max_chebyshev:
                if agent.state == "moving":
                    agent.state = "idle"
                agent.move_intent = None
                world.conversation_requests.append((agent.id, target_id))
                return Status.RUNNING
            intent = agent.move_intent
            if not (intent and intent.kind == "agent" and intent.key == target_id):
                agent.move_intent = MoveIntent(kind="agent", key=target_id, reason="chat")
            agent.state = "moving"
            return Status.RUNNING

        nearby = world.spatial.neighbors_within(
            agent.pos, icfg.approach_radius, exclude=agent.id)
        candidates = [world.agents[a] for a in nearby if world.agents[a].state == "idle"]
        if not candidates:
            return Status.FAILURE
        friends = [c for c in candidates if agent.relationship_with(c.id).affinity >= 70]
        target = ctx.rng.choice(friends if friends else candidates)
        rel = agent.relationship_with(target.id)
        agent.social_target = target.id
        agent.move_intent = MoveIntent(kind="agent", key=target.id, reason="chat")
        agent.state = "moving"
        agent.current_goal = f"Going to chat with {target.spec.name}"
        agent.current_action = "Walking over to say hello"
        ctx.log(f"Spotted {target.spec.name} nearby — my {rel.kind}. Going to say hello.",
                importance=0.4, participants=(target.id,))
        return Status.RUNNING


class IdleFlavor(Leaf):
    """Personality-flavored idling (V1's F09/F07 made this unreachable)."""

    def run(self, ctx: TickContext) -> Status:
        traits = ctx.agent.spec.personality
        if "lazy" in traits:
            goal, action = "Taking it easy", "Lounging around"
        elif "curious" in traits:
            goal, action = "Seeing what's happening around town", "People-watching"
        elif "social_butterfly" in traits:
            goal, action = "Looking for someone to talk to", "Scanning for familiar faces"
        else:
            goal, action = "Enjoying a quiet moment", "Thinking things over"
        ctx.agent.current_goal = goal
        ctx.agent.current_action = action
        return Status.SUCCESS
