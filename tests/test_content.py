from __future__ import annotations

import pytest

from townsim.config.content import (
    AGENTS, SCHEDULE_TEMPLATES, merge_traits, sociability_for, validate_content,
)
from townsim.config.models import SimConfig
from townsim.world.grid import TownMap


class TestContentValidation:
    def test_repo_content_is_consistent(self):
        town = TownMap.load(SimConfig().paths.map_file)
        warnings = validate_content(set(town.places.keys()))
        assert warnings == [], f"dead config (F39): {warnings}"

    def test_unknown_trait_raises(self):
        with pytest.raises(KeyError):
            merge_traits(["extrovert", "definitely_not_a_trait"])

    def test_trait_collision_takes_mean_not_overwrite(self):
        merged = merge_traits(["conscientious", "spontaneous"])
        # F38: V1 silently kept the later value (0.3); mean keeps both voices.
        assert merged["routine_adherence"] == pytest.approx((0.8 + 0.3) / 2)

    def test_every_agent_has_sociability(self):
        for spec in AGENTS:
            assert 0.0 < spec.sociability <= 1.0

    def test_introvert_less_sociable_than_extrovert(self):
        assert sociability_for(["introvert"]) < sociability_for(["extrovert"])

    def test_overnight_windows_exist_and_valid(self):
        """The (22,1) party windows V1 silently never triggered (F17)."""
        wrap_windows = [
            window
            for template in SCHEDULE_TEMPLATES.values()
            for windows in template.values()
            for window in windows
            if window[0] > window[1]
        ]
        assert wrap_windows, "expected at least one overnight window in content"
