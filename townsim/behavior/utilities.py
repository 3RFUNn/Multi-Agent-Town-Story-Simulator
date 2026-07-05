"""Utility functions: desirability of each behavior branch from REAL state.

This is the arbitration layer V1 advertised but never had (F08/F09 made its
heuristic constant). Reflection adjusts agent.utility_weights within clamped
bounds, so LLM cognition can shift priorities without ever inventing actions.
"""
from __future__ import annotations

from townsim.behavior.core import TickContext


def _w(ctx: TickContext, axis: str) -> float:
    return ctx.agent.utility_weights.get(axis, 1.0)


def schedule_utility(ctx: TickContext) -> float:
    """Following the schedule is the default winner when a slot is active."""
    if ctx.agent.current_activity is None:
        return 0.0
    base = 1.2
    adherence = ctx.agent.spec.traits.get("routine_adherence", 0.6)
    return base * (0.7 + 0.5 * adherence) * _w(ctx, "schedule")


def socialize_utility(ctx: TickContext) -> float:
    agent = ctx.agent
    pressure = agent.needs.social / 100.0
    if agent.needs.social < ctx.cfg.needs.social_pressure_min:
        return 0.0
    nearby = ctx.world.spatial.neighbors_within(
        agent.pos, ctx.cfg.interaction.approach_radius, exclude=agent.id)
    idle_nearby = [aid for aid in nearby if ctx.world.agents[aid].state == "idle"]
    opportunity = min(len(idle_nearby), 3) / 3.0
    sociability = agent.spec.sociability
    return pressure * (0.4 + 0.6 * sociability) * (0.2 + 0.8 * opportunity) * _w(ctx, "social")


def leisure_utility(ctx: TickContext) -> float:
    """Head to the park when free and not already somewhere interesting."""
    agent = ctx.agent
    if agent.current_activity is not None:
        return 0.0
    at_park = ctx.world.is_at_place(agent, "central_park")
    curiosity = agent.spec.traits.get("exploration_tendency", 0.3)
    base = 0.10 + 0.25 * curiosity
    return (base if not at_park else base * 0.3) * _w(ctx, "leisure")


def idle_utility(ctx: TickContext) -> float:
    return 0.05
