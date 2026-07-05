"""Regression tests for the adversarial-review findings (R01-R26).

Each test pins the FIX for a confirmed finding from the multi-agent review
of the V2 package (docs/v2_upgrade/review_findings.json).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx
import pytest

from townsim.agents.agent import AgentState
from townsim.agents.schedule import slot_for
from townsim.behavior.core import Leaf, Status, guarded_move
from townsim.cognition.memory import MemoryEntry, MemoryStream
from townsim.config.content import AGENTS
from townsim.config.models import SimConfig, load_config
from townsim.kernel.clock import SimClock
from townsim.llm.providers import OpenAIProvider, TransientLLMError


@dataclass
class FakeCtx:
    trace: list = field(default_factory=list)


class Always(Leaf):
    def __init__(self, name, status):
        super().__init__(name)
        self.status = status
        self.ticks = 0

    def run(self, ctx):
        self.ticks += 1
        return self.status


class TestR01GuardedMoveFallback:
    def test_do_there_failure_propagates_when_at_location(self):
        """R01: at the location + do_there FAILS -> the whole branch must
        FAIL (previously go_there returned SUCCESS and swallowed it)."""
        go = Always("go", Status.SUCCESS)
        branch = guarded_move("eat", is_there=lambda ctx: True,
                              do_there=Always("eat", Status.FAILURE), go_there=go)
        assert branch.tick(FakeCtx()) == Status.FAILURE
        assert go.ticks == 0   # travel arm is guarded off when already there

    def test_travel_still_happens_when_away(self):
        branch = guarded_move("eat", is_there=lambda ctx: False,
                              do_there=Always("eat", Status.SUCCESS),
                              go_there=Always("go", Status.RUNNING))
        assert branch.tick(FakeCtx()) == Status.RUNNING

    def test_do_there_runs_at_location(self):
        do = Always("do", Status.RUNNING)
        branch = guarded_move("work", is_there=lambda ctx: True,
                              do_there=do, go_there=Always("go", Status.SUCCESS))
        assert branch.tick(FakeCtx()) == Status.RUNNING
        assert do.ticks == 1


class TestR09OverrideNapSlot:
    def test_sleep_override_uses_its_own_window(self):
        spec = AGENTS[0]  # alex, sleep_window (23, 7)
        agent = AgentState(spec=spec, x=0, y=0)
        clock = SimClock(tick_minutes=2, day_start_hour=8)
        now = clock.at(180)  # Monday 14:00
        agent.schedule_overrides[(now.day_index, 14, 15)] = "sleep_at_home"
        assert slot_for(agent, now, "sleep_at_home") == (14, 15)  # not (23, 7)

    def test_nightly_sleep_still_uses_sleep_window(self):
        spec = AGENTS[0]
        agent = AgentState(spec=spec, x=0, y=0)
        clock = SimClock(tick_minutes=2, day_start_hour=8)
        now = clock.at(480)  # Tuesday 00:00 — inside (23, 7)
        assert slot_for(agent, now, "sleep_at_home") == (23, 7)


class TestR12ErrorClassification:
    def _provider(self):
        return OpenAIProvider(api_key="sk-test", model="m")

    def _status_error(self, code):
        import openai
        request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        response = httpx.Response(status_code=code, request=request)
        return openai.APIStatusError("boom", response=response, body=None)

    def test_5xx_is_transient(self):
        provider = self._provider()
        assert isinstance(provider._classify(self._status_error(503)), TransientLLMError)

    def test_401_is_permanent(self):
        provider = self._provider()
        classified = provider._classify(self._status_error(401))
        assert not isinstance(classified, TransientLLMError)

    def test_rate_limit_is_transient(self):
        import openai
        provider = self._provider()
        request = httpx.Request("POST", "https://x")
        response = httpx.Response(status_code=429, request=request,
                                  headers={"x-request-id": "1"})
        err = openai.RateLimitError("rl", response=response, body=None)
        assert isinstance(provider._classify(err), TransientLLMError)


class TestR15EnvOverridesYaml:
    def test_env_beats_yaml_init_kwargs(self, monkeypatch):
        monkeypatch.setenv("TOWNSIM_KERNEL__SEED", "99")
        cfg = SimConfig(kernel={"seed": 1})   # simulates YAML-provided value
        assert cfg.kernel.seed == 99

    def test_yaml_beats_defaults_without_env(self):
        cfg = SimConfig(kernel={"seed": 7})
        assert cfg.kernel.seed == 7


class TestR20LongtermMemoryCap:
    def test_summaries_capped(self):
        stream = MemoryStream()
        for i in range(40):
            stream.add(MemoryEntry(text=f"s{i}", day_index=i, tick=i,
                                   importance=0.5, kind="summary"))
        stream.compact_before(100, None)
        summaries = stream.summaries()
        assert len(summaries) == MemoryStream.MAX_LONGTERM
        assert summaries[-1].text == "s39"   # newest kept


class TestR24ExplicitConfigPath:
    def test_missing_explicit_config_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nope.yaml")
