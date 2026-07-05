"""Agent behavior tree construction.

Root priority order (fixing V1's F31 priority inversion):
  1. exhaustion emergency (fatigue >= exhausted) — with a REAL sleep action (F12)
  2. hunger emergency (hunger >= critical) — guarded travel + paid meal (F05)
  3. tiredness (fatigue >= tired) — rest at an agent-chosen spot (F11/F20)
  4. utility arbitration between the schedule and free-time behaviors, where
     free time is itself utility-arbitrated (socialize / leisure / idle) and
     reflection-adjusted weights can shift priorities within bounds.
"""
from __future__ import annotations

from townsim.behavior.core import (
    Branch,
    Condition,
    Node,
    Selector,
    Sequence,
    TickContext,
    UtilitySelector,
    guarded_move,
)
from townsim.behavior.nodes import (
    ApproachAndChat,
    EatEmergencyMeal,
    EmergencySleep,
    GoTo,
    IdleFlavor,
    StartScheduledActivity,
    TakeRest,
    rest_spot_for,
)
from townsim.config.content import ACTIVITY_DATA


def _activity_place(ctx: TickContext) -> str:
    activity = ctx.agent.current_activity
    if activity is None:
        return "home"
    return ACTIVITY_DATA[activity]["location"]


def build_agent_tree(agent_id: str) -> Node:
    needs = lambda ctx: ctx.cfg.needs  # noqa: E731

    exhaustion_branch = Sequence("Emergency: sleep when exhausted", [
        Condition("exhausted?", lambda ctx: ctx.agent.needs.fatigue >= needs(ctx).fatigue_exhausted),
        guarded_move(
            "sleep at home",
            is_there=lambda ctx: ctx.world.is_at_place(ctx.agent, "home"),
            do_there=EmergencySleep("collapse into bed"),
            go_there=GoTo("walk home exhausted", lambda ctx: "home", reason="exhausted"),
        ),
    ])

    hunger_branch = Sequence("Emergency: eat when starving", [
        Condition("starving?", lambda ctx: ctx.agent.needs.hunger >= needs(ctx).hunger_critical),
        guarded_move(
            "eat at cafe",
            is_there=lambda ctx: ctx.world.is_at_place(ctx.agent, "downtown_cafe"),
            do_there=EatEmergencyMeal("buy a meal"),
            go_there=GoTo("walk to cafe hungry", lambda ctx: "downtown_cafe", reason="starving"),
        ),
    ])

    rest_branch = Sequence("Urgent: rest when tired", [
        Condition("tired?", lambda ctx: ctx.agent.needs.fatigue >= needs(ctx).fatigue_tired),
        guarded_move(
            "rest at chosen spot",
            is_there=lambda ctx: ctx.world.is_at_place(ctx.agent, rest_spot_for(ctx)),
            do_there=TakeRest("take a short rest"),
            go_there=GoTo("walk to rest spot", rest_spot_for, reason="tired"),
        ),
    ])

    schedule_branch = Branch(
        "Follow my schedule",
        Sequence("scheduled activity", [
            Condition("has activity?", lambda ctx: ctx.agent.current_activity is not None),
            guarded_move(
                "do scheduled activity",
                is_there=lambda ctx: ctx.world.is_at_place(ctx.agent, _activity_place(ctx)),
                do_there=StartScheduledActivity("start activity"),
                go_there=GoTo("walk to activity", _activity_place, reason="schedule"),
            ),
        ]),
        utility_fn=None,  # set in build below to avoid circular import noise
    )

    free_time = UtilitySelector("Free time", [
        Branch("Socialize", ApproachAndChat("find someone to chat with"), utility_fn=None),
        Branch("Leisure",
               guarded_move(
                   "hang out at park",
                   is_there=lambda ctx: ctx.world.is_at_place(ctx.agent, "central_park"),
                   do_there=IdleFlavor("enjoy the park"),
                   go_there=GoTo("stroll to park", lambda ctx: "central_park", reason="leisure"),
               ),
               utility_fn=None),
        Branch("Idle", IdleFlavor("idle"), utility_fn=None),
    ])

    core = UtilitySelector("Core routine", [schedule_branch, free_time])

    root = Selector(f"Root ({agent_id})", [
        exhaustion_branch,
        hunger_branch,
        rest_branch,
        core,
    ])

    _wire_utilities(schedule_branch, free_time)
    return root


def _wire_utilities(schedule_branch: Branch, free_time: UtilitySelector) -> None:
    from townsim.behavior import utilities as u

    schedule_branch._utility_fn = u.schedule_utility
    socialize, leisure, idle = free_time.children
    socialize._utility_fn = u.socialize_utility
    leisure._utility_fn = u.leisure_utility
    idle._utility_fn = u.idle_utility
    # Free time's own utility: best of its children (so the core arbiter
    # compares schedule pressure against the strongest free-time pull).
    free_time.utility = lambda ctx: max(  # type: ignore[method-assign]
        u.socialize_utility(ctx), u.leisure_utility(ctx), u.idle_utility(ctx))
