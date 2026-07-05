"""Typed runtime configuration.

All tuning constants that were magic numbers scattered across V1
(wages, need rates, thresholds, durations, tick scale) live here, loadable
from YAML with environment-variable overrides (prefix TOWNSIM_, nested keys
joined by '__', e.g. TOWNSIM_LLM__PROVIDER=fake).
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class LLMConfig(BaseModel):
    provider: str = "auto"  # auto | openai | fake
    model: str = "gpt-4.1-mini"
    embed_model: str = "text-embedding-3-small"
    api_key_env: str = "OPENAI_API_KEY"
    legacy_api_key_env: str = "API_KEY"  # V1 used this name; honored with a warning
    request_timeout_s: float = 60.0
    max_concurrency: int = 4
    max_attempts: int = 4
    diary_max_tokens: int = 1024
    story_max_tokens: int = 1536
    semantic_cache_threshold: float = 0.97

    def resolve_api_key(self) -> str | None:
        return os.getenv(self.api_key_env) or os.getenv(self.legacy_api_key_env)

    def resolve_provider(self) -> str:
        if self.provider != "auto":
            return self.provider
        return "openai" if self.resolve_api_key() else "fake"


class NeedsConfig(BaseModel):
    """Rates are per sim-minute; thresholds on a 0-100 scale (higher = more urgent)."""
    hunger_rate: float = 0.125          # V1: 0.25 per 2-minute tick
    social_rate: float = 0.075
    fatigue_rate: float = 0.05
    fatigue_rate_working: float = 0.10
    fatigue_recovery_sleeping: float = 0.40
    hunger_critical: float = 85.0
    fatigue_tired: float = 70.0
    fatigue_exhausted: float = 95.0
    social_pressure_min: float = 30.0   # below this, socialize utility is 0
    meal_hunger_relief: float = 60.0
    rest_fatigue_relief: float = 45.0
    conversation_social_relief: float = 60.0


class EconomyConfig(BaseModel):
    """Wages are per sim-HOUR (V1 mixed per-tick and per-hour units — F32)."""
    starting_money_min: int = 100
    starting_money_max: int = 150
    wage_office_per_hour: float = 15.0
    wage_shift_per_hour: float = 24.0
    wage_classes_per_hour: float = 9.0


class InteractionConfig(BaseModel):
    conversation_min_ticks: int = 8
    conversation_max_ticks: int = 15
    adjacency_max_chebyshev: int = 2    # F16: partners must actually be near each other
    approach_radius: int = 6
    daily_dialogue_budget: int = 4      # LLM-rendered dialogues per day (salient encounters)


class KernelConfig(BaseModel):
    seed: int = 42
    tick_minutes: int = 2
    ticks_per_second: float = 2.5       # wall-clock pacing; 0 = headless flat-out
    day_start_hour: int = 8             # hour of day at tick 0 of day 0 (V1 parity)
    snapshot_every_ticks: int = 360
    # Strict mode: at each day rollover, wait for cognition (diaries,
    # reflections, story) and apply the results at that exact tick. Makes
    # runs bit-for-bit reproducible even WITH the narrative layer enabled
    # (free with the fake provider; adds a nightly pause with a real LLM).
    strict_narrative_sync: bool = False


class PathsConfig(BaseModel):
    map_file: Path = PROJECT_ROOT / "static" / "map_data.json"
    runs_dir: Path = PROJECT_ROOT / "runs"
    prompts_dir: Path = PROJECT_ROOT / "prompts"


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000


class MemoryConfig(BaseModel):
    alpha_recency: float = 1.0
    beta_importance: float = 1.0
    gamma_relevance: float = 1.0
    recency_decay_per_tick: float = 0.9985
    retrieve_k: int = 12
    compact_after_days: int = 2         # episodic memories older than this get summarized away


class SimConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TOWNSIM_", env_nested_delimiter="__")

    kernel: KernelConfig = Field(default_factory=KernelConfig)
    needs: NeedsConfig = Field(default_factory=NeedsConfig)
    economy: EconomyConfig = Field(default_factory=EconomyConfig)
    interaction: InteractionConfig = Field(default_factory=InteractionConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings,
                                   dotenv_settings, file_secret_settings):
        # R15: YAML values arrive as init kwargs; environment variables must
        # still override them (env > yaml > defaults).
        return (env_settings, init_settings, dotenv_settings, file_secret_settings)


def load_config(yaml_path: str | Path | None = None) -> SimConfig:
    """Precedence: env vars > YAML file > built-in defaults. An explicitly
    given yaml_path that does not exist is an error (R24), never silently
    ignored."""
    if yaml_path is not None:
        explicit = Path(yaml_path)
        if not explicit.exists():
            raise FileNotFoundError(f"config file not found: {explicit}")
        candidates = [explicit]
    else:
        candidates = [PROJECT_ROOT / "townsim.yaml",
                      Path(__file__).with_name("default.yaml")]
    data: dict = {}
    for candidate in candidates:
        if candidate.exists():
            with open(candidate, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            break
    return SimConfig(**data)
