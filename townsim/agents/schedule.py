"""Schedule resolution — wrap-aware windows (F17), sleep windows, overrides.

The scheduler answers one question per agent per tick: "what does your
schedule say you should be doing right now?" Sleep windows take precedence,
then reflection-accepted overrides, then the agent's materialized schedule
(a seeded per-run variation of the weekday/weekend template).
"""
from __future__ import annotations

import random

from townsim.agents.agent import AgentState
from townsim.config.content import SCHEDULE_TEMPLATES, AgentSpec
from townsim.kernel.clock import SimTime

# Per-run schedule variation knobs (consumed by materialize_schedule).
JITTER_SHIFTS = (-1, 0, 1)      # whole-schedule phase shift, hours
SHRINK_CHANCE = 0.35            # per-window chance to lose one hour
MIN_SHRINK_DURATION = 2         # never shrink a window below 1 hour


def is_in_window(hour: int, start: int, end: int) -> bool:
    """(22, 1) means 22:00-01:00 across midnight (F17)."""
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def materialize_schedule(
    spec: AgentSpec, rng: random.Random,
) -> tuple[dict[str, dict[tuple[int, int], str]], tuple[int, int]]:
    """A seeded per-run variation of the agent's schedule template, so no
    two runs play out identical days: the whole schedule (sleep included)
    phase-shifts by -1/0/+1 hour, and individual windows occasionally
    shrink by one hour from either edge.

    Shifting everything rigidly preserves the template's non-overlap
    invariant, and shrinking a window inside its own original span can
    never create an overlap either — gaps just fall through to the
    behavior tree's free-time layer. Same seed -> identical schedules.
    """
    shift = rng.choice(JITTER_SHIFTS)
    template = SCHEDULE_TEMPLATES[spec.schedule_template]
    schedule: dict[str, dict[tuple[int, int], str]] = {}
    for day_kind, windows in template.items():
        materialized: dict[tuple[int, int], str] = {}
        for (start, end), activity in windows.items():
            duration = (end - start) % 24
            new_start = (start + shift) % 24
            if duration >= MIN_SHRINK_DURATION and rng.random() < SHRINK_CHANCE:
                if rng.random() < 0.5:
                    new_start = (new_start + 1) % 24   # start an hour later
                duration -= 1                          # or end an hour earlier
            materialized[(new_start, (new_start + duration) % 24)] = activity
        schedule[day_kind] = materialized
    sleep_start, sleep_end = spec.sleep_window
    sleep_window = ((sleep_start + shift) % 24, (sleep_end + shift) % 24)
    return schedule, sleep_window


def _windows(agent: AgentState) -> dict[str, dict[tuple[int, int], str]]:
    """The agent's materialized per-run schedule; bare AgentStates (tests,
    tools) fall back to the pristine template."""
    return agent.schedule or SCHEDULE_TEMPLATES[agent.spec.schedule_template]


def is_sleep_time(agent: AgentState, hour: int) -> bool:
    start, end = agent.sleep_window
    return is_in_window(hour, start, end)


def scheduled_activity(agent: AgentState, now: SimTime) -> str | None:
    if is_sleep_time(agent, now.hour):
        return "sleep_at_home"

    # Reflection-accepted overrides win over the template (bounded feedback).
    for (day_index, start, end), activity in agent.schedule_overrides.items():
        if day_index == now.day_index and is_in_window(now.hour, start, end):
            return activity

    day_kind = "weekends" if now.weekday in ("Saturday", "Sunday") else "weekdays"
    windows = _windows(agent).get(day_kind, {})
    for (start, end), activity in windows.items():
        if is_in_window(now.hour, start, end):
            return activity
    return None


def slot_for(agent: AgentState, now: SimTime, activity: str) -> tuple[int, int]:
    """The (start_hour, end_hour) window that produced `activity` right now.
    Used for charge-once-per-slot accounting (F13) and action end times.

    Overrides are checked BEFORE the sleep special-case (R09): a
    reflection-proposed afternoon nap must end at the override's end hour,
    not stretch to the agent's whole nightly sleep window."""
    for (day_index, start, end), a in agent.schedule_overrides.items():
        if day_index == now.day_index and a == activity and is_in_window(now.hour, start, end):
            return (start, end)
    if activity == "sleep_at_home":
        return agent.sleep_window
    day_kind = "weekends" if now.weekday in ("Saturday", "Sunday") else "weekdays"
    for (start, end), a in _windows(agent).get(day_kind, {}).items():
        if a == activity and is_in_window(now.hour, start, end):
            return (start, end)
    return (now.hour, (now.hour + 1) % 24)


def ticks_until_hour(now: SimTime, end_hour: int, tick_minutes: int) -> int:
    """Ticks from `now` until the next occurrence of end_hour:00 (wrap-aware)."""
    now_minutes = now.hour * 60 + now.minute
    end_minutes = end_hour * 60
    delta = end_minutes - now_minutes
    if delta <= 0:
        delta += 24 * 60
    return max(1, delta // tick_minutes)
