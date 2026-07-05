"""Per-run randomness: random seed resolution, seeded start weekday, and
seeded schedule variation — while a pinned seed stays perfectly reproducible."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from townsim.agents.schedule import is_in_window, materialize_schedule
from townsim.config.content import ACTIVITY_DATA, AGENTS, SCHEDULE_TEMPLATES, WEEKDAYS
from townsim.config.models import SimConfig
from townsim.kernel.clock import SimClock
from townsim.kernel.journal import read_journal
from townsim.kernel.kernel import Kernel
from townsim.kernel.rng import RngRegistry


def all_schedules(seed: int):
    rng = RngRegistry(seed).stream("schedule")
    return [materialize_schedule(spec, rng) for spec in AGENTS]


def covered_hours(start: int, end: int) -> set[int]:
    return {(start + i) % 24 for i in range((end - start) % 24)}


class TestScheduleJitter:
    def test_windows_stay_valid_across_many_seeds(self):
        for seed in range(50):
            for (schedule, sleep), spec in zip(all_schedules(seed), AGENTS, strict=True):
                assert 0 <= sleep[0] <= 23 and 0 <= sleep[1] <= 23
                assert sleep[0] != sleep[1]
                for day_kind, windows in schedule.items():
                    template = SCHEDULE_TEMPLATES[spec.schedule_template][day_kind]
                    # same activities, same count — jitter moves, never drops
                    assert sorted(windows.values()) == sorted(template.values())
                    occupied: set[int] = set()
                    for (start, end), activity in windows.items():
                        assert activity in ACTIVITY_DATA
                        hours = covered_hours(start, end)
                        assert hours, f"empty window {(start, end)} seed={seed}"
                        assert not occupied & hours, f"overlap at seed={seed}"
                        occupied |= hours

    def test_same_seed_identical_different_seeds_vary(self):
        assert all_schedules(42) == all_schedules(42)
        baseline = all_schedules(0)
        assert any(all_schedules(seed) != baseline for seed in range(1, 8))

    def test_bare_agentstate_falls_back_to_template(self):
        from townsim.agents.agent import AgentState
        agent = AgentState(spec=AGENTS[0], x=0, y=0)
        assert agent.schedule == {}
        assert agent.sleep_window == AGENTS[0].sleep_window
        clock = SimClock(tick_minutes=2, day_start_hour=8)
        from townsim.agents.schedule import scheduled_activity
        now = clock.at(60)  # Monday 10:00 — office block in the pristine template
        assert scheduled_activity(agent, now) == "work_at_office"


class TestStartWeekday:
    def test_clock_offset(self):
        clock = SimClock(tick_minutes=2, day_start_hour=8, start_weekday="Friday")
        assert clock.at(0).weekday == "Friday"
        next_day = clock.at(clock.ticks_per_day)
        assert next_day.weekday == "Saturday"

    def test_default_stays_monday(self):
        assert SimClock().at(0).weekday == "Monday"

    def test_seed_derives_weekday_deterministically(self, cfg, tmp_path):
        days = set()
        for seed in range(12):
            cfg.kernel.seed = seed
            cfg.paths.runs_dir = tmp_path / f"s{seed}"
            kernel = Kernel(cfg)
            repeat = Kernel(cfg, run_dir=tmp_path / f"s{seed}-b")
            assert kernel.clock.start_weekday == repeat.clock.start_weekday
            days.add(kernel.clock.start_weekday)
            kernel.close(), repeat.close()
        assert len(days) >= 2, "12 seeds all landed on the same weekday"

    def test_config_pin_wins_over_seed(self, cfg):
        cfg.kernel.start_weekday = "Sunday"
        kernel = Kernel(cfg)
        assert kernel.clock.at(0).weekday == "Sunday"
        kernel.close()


class TestStartWeekdayValidation:
    def test_casing_is_forgiven_at_load_time(self):
        cfg = SimConfig(kernel={"start_weekday": "friday"})
        assert cfg.kernel.start_weekday == "Friday"

    def test_bogus_name_fails_at_load_time_with_valid_values(self):
        with pytest.raises(ValidationError, match="start_weekday"):
            SimConfig(kernel={"start_weekday": "Funday"})

    def test_empty_string_means_seed_derived(self):
        cfg = SimConfig(kernel={"start_weekday": "  "})
        assert cfg.kernel.start_weekday is None


class TestRandomSeedResolution:
    def test_none_seed_resolves_and_is_journaled(self, cfg):
        cfg.kernel.seed = None
        kernel = Kernel(cfg)
        assert isinstance(cfg.kernel.seed, int)
        kernel.journal.close()
        header, _ = read_journal(kernel.run_dir / "journal.jsonl")
        assert header["seed"] == cfg.kernel.seed
        assert header["config"]["start_weekday"] in WEEKDAYS

    def test_fresh_runs_get_fresh_seeds(self, cfg, tmp_path):
        seeds = set()
        for i in range(5):
            cfg.kernel.seed = None
            cfg.paths.runs_dir = tmp_path / f"r{i}"
            kernel = Kernel(cfg)
            seeds.add(cfg.kernel.seed)
            kernel.close()
        assert len(seeds) > 1, "5 'random' runs drew the same seed"

    def test_pinned_seed_reproduces_world_exactly(self, cfg, tmp_path):
        cfg.kernel.seed = 777
        a = Kernel(cfg, run_dir=tmp_path / "a")
        b = Kernel(cfg, run_dir=tmp_path / "b")
        assert a.clock.start_weekday == b.clock.start_weekday
        for agent_a, agent_b in zip(a.world.agents_sorted(), b.world.agents_sorted(), strict=True):
            assert agent_a.schedule == agent_b.schedule
            assert agent_a.sleep_window == agent_b.sleep_window
            assert agent_a.needs.to_dict() == agent_b.needs.to_dict()
            assert agent_a.wallet.money == agent_b.wallet.money
        a.close(), b.close()

    def test_different_seeds_differ_somewhere(self, cfg, tmp_path):
        cfg.kernel.seed = 1
        a = Kernel(cfg, run_dir=tmp_path / "a")
        cfg.kernel.seed = 2
        b = Kernel(cfg, run_dir=tmp_path / "b")
        differs = (
            a.clock.start_weekday != b.clock.start_weekday
            or any(x.schedule != y.schedule or x.needs.to_dict() != y.needs.to_dict()
                   for x, y in zip(a.world.agents_sorted(), b.world.agents_sorted(), strict=True))
        )
        assert differs
        a.close(), b.close()


class TestSleepWindowJitterConsistency:
    def test_sleep_shifts_with_schedule(self):
        for seed in range(20):
            for (_schedule, sleep), spec in zip(all_schedules(seed), AGENTS, strict=True):
                duration = (sleep[1] - sleep[0]) % 24
                spec_duration = (spec.sleep_window[1] - spec.sleep_window[0]) % 24
                assert duration == spec_duration, "sleep length must never change"
                # shifted by at most 1 hour in either direction
                shift = (sleep[0] - spec.sleep_window[0]) % 24
                assert shift in (0, 1, 23)

    def test_is_in_window_wraps(self):
        assert is_in_window(23, 22, 10)
        assert is_in_window(3, 22, 10)
        assert not is_in_window(12, 22, 10)
