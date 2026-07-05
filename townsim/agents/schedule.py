"""Schedule resolution — wrap-aware windows (F17), sleep windows, overrides.

The scheduler answers one question per agent per tick: "what does your
schedule say you should be doing right now?" Sleep windows take precedence,
then reflection-accepted overrides, then the weekday/weekend template.
"""
from __future__ import annotations

from townsim.agents.agent import AgentState
from townsim.config.content import SCHEDULE_TEMPLATES
from townsim.kernel.clock import SimTime


def is_in_window(hour: int, start: int, end: int) -> bool:
    """(22, 1) means 22:00-01:00 across midnight (F17)."""
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def is_sleep_time(agent: AgentState, hour: int) -> bool:
    start, end = agent.spec.sleep_window
    return is_in_window(hour, start, end)


def scheduled_activity(agent: AgentState, now: SimTime) -> str | None:
    if is_sleep_time(agent, now.hour):
        return "sleep_at_home"

    # Reflection-accepted overrides win over the template (bounded feedback).
    for (day_index, start, end), activity in agent.schedule_overrides.items():
        if day_index == now.day_index and is_in_window(now.hour, start, end):
            return activity

    template = SCHEDULE_TEMPLATES[agent.spec.schedule_template]
    day_kind = "weekends" if now.weekday in ("Saturday", "Sunday") else "weekdays"
    windows = template.get(day_kind, {})
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
        return agent.spec.sleep_window
    template = SCHEDULE_TEMPLATES[agent.spec.schedule_template]
    day_kind = "weekends" if now.weekday in ("Saturday", "Sunday") else "weekdays"
    for (start, end), a in template.get(day_kind, {}).items():
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
