"""Simulation clock: pure function of the tick counter (fixed timestep).

V1 mutated (hour, minute) in place with drift-prone bookkeeping (F41); here
sim time is derived arithmetically from the tick, so replay and fast-forward
are exact.
"""
from __future__ import annotations

from dataclasses import dataclass

from townsim.config.content import WEEKDAYS

MINUTES_PER_DAY = 24 * 60


@dataclass(frozen=True)
class SimTime:
    tick: int
    day_index: int
    weekday: str
    hour: int
    minute: int

    @property
    def minutes_of_day(self) -> int:
        return self.hour * 60 + self.minute

    def label(self) -> str:
        ampm = "AM" if self.hour < 12 else "PM"
        display_hour = self.hour % 12 or 12
        return f"{self.weekday} {display_hour:02d}:{self.minute:02d} {ampm}"

    def to_dict(self) -> dict:
        return {
            "tick": self.tick, "day_index": self.day_index, "weekday": self.weekday,
            "hour": self.hour, "minute": self.minute, "label": self.label(),
        }


class SimClock:
    def __init__(self, tick_minutes: int = 2, day_start_hour: int = 8,
                 start_weekday: str = "Monday") -> None:
        if MINUTES_PER_DAY % tick_minutes != 0:
            raise ValueError("tick_minutes must divide a day evenly")
        if start_weekday not in WEEKDAYS:
            raise ValueError(f"unknown weekday: {start_weekday!r}")
        self.tick_minutes = tick_minutes
        self.day_start_hour = day_start_hour
        self.start_weekday = start_weekday
        self._weekday_offset = WEEKDAYS.index(start_weekday)
        self.ticks_per_day = MINUTES_PER_DAY // tick_minutes

    def at(self, tick: int) -> SimTime:
        total_minutes = tick * self.tick_minutes + self.day_start_hour * 60
        day_index = total_minutes // MINUTES_PER_DAY
        minutes_of_day = total_minutes % MINUTES_PER_DAY
        return SimTime(
            tick=tick,
            day_index=day_index,
            weekday=WEEKDAYS[(day_index + self._weekday_offset) % 7],
            hour=minutes_of_day // 60,
            minute=minutes_of_day % 60,
        )

    def is_day_rollover(self, tick: int) -> bool:
        """True when `tick` is the first tick of a new day (tick > 0)."""
        return tick > 0 and self.at(tick).day_index != self.at(tick - 1).day_index
