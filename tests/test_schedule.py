"""Schedule window tests — wrap-around windows were dead config in V1 (F17)."""
from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from townsim.agents.schedule import is_in_window, ticks_until_hour
from townsim.kernel.clock import SimClock


class TestIsInWindow:
    def test_normal_window(self):
        assert is_in_window(9, 8, 17)
        assert not is_in_window(7, 8, 17)
        assert not is_in_window(17, 8, 17)

    def test_overnight_window_f17(self):
        """(22, 1) = 22:00-01:00: V1's start<=h<end could never match it."""
        assert is_in_window(22, 22, 1)
        assert is_in_window(23, 22, 1)
        assert is_in_window(0, 22, 1)
        assert not is_in_window(1, 22, 1)
        assert not is_in_window(12, 22, 1)

    def test_degenerate_window(self):
        assert not is_in_window(5, 5, 5)

    @given(st.integers(0, 23), st.integers(0, 23), st.integers(0, 23))
    def test_every_hour_classified_consistently(self, hour, start, end):
        """A wrap window matches exactly the union of [start,24) and [0,end)."""
        result = is_in_window(hour, start, end)
        if start < end:
            assert result == (start <= hour < end)
        elif start == end:
            assert result is False
        else:
            assert result == (hour >= start or hour < end)


class TestTicksUntilHour:
    def test_same_day(self):
        clock = SimClock(tick_minutes=2, day_start_hour=8)
        now = clock.at(0)  # Monday 08:00
        assert ticks_until_hour(now, 9, 2) == 30

    def test_wraps_midnight(self):
        clock = SimClock(tick_minutes=2, day_start_hour=8)
        now = clock.at(0)  # 08:00
        assert ticks_until_hour(now, 7, 2) == (23 * 60) // 2

    def test_never_zero(self):
        clock = SimClock(tick_minutes=2, day_start_hour=8)
        now = clock.at(0)
        assert ticks_until_hour(now, 8, 2) == (24 * 60) // 2  # next 08:00 is tomorrow


class TestClock:
    def test_day_rollover(self):
        clock = SimClock(tick_minutes=2, day_start_hour=8)
        # day 0 spans 08:00 -> 24:00 = 16h = 480 ticks
        assert clock.at(479).day_index == 0
        assert clock.at(480).day_index == 1
        assert clock.is_day_rollover(480)
        assert not clock.is_day_rollover(481)
        assert clock.at(480).hour == 0 and clock.at(480).minute == 0

    def test_weekday_cycles(self):
        clock = SimClock(tick_minutes=2, day_start_hour=8)
        assert clock.at(0).weekday == "Monday"
        assert clock.at(480).weekday == "Tuesday"
