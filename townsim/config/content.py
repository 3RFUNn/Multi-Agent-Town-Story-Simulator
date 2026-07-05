"""Simulation content: agents, personalities, schedules, activities, relationships.

Ported from V1 ``simulation/config.py`` with the audited defects repaired:
- every agent has an explicit ``home_place`` (F40 — no coordinate-range guessing),
- every agent has numeric ``sociability`` so anyone can socialize (F21),
- overnight schedule windows like (22, 1) are legal and handled wrap-aware (F17),
- schedules and activities are cross-validated at load time (F39),
- sleep windows are explicit per-agent data, not personality string-matching.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --- Personality traits (numeric modifiers; consumed by utilities & needs) ---
PERSONALITY_TRAITS: dict[str, dict[str, float]] = {
    "extrovert": {"social_motivation": 1.5, "talkativeness": 0.8},
    "introvert": {"social_motivation": 0.5, "talkativeness": 0.3},
    "agreeable": {"cooperativeness": 0.9},
    "conscientious": {"work_ethic": 1.4, "routine_adherence": 0.8},
    "curious": {"exploration_tendency": 0.8},
    "spontaneous": {"routine_adherence": 0.3},
    "fitness_enthusiast": {"gym_motivation": 0.9},
    "workaholic": {"work_ethic": 1.6, "overtime_tendency": 0.8},
    "lazy": {"work_ethic": 0.7, "rest_preference": 0.8},
    "social_butterfly": {"social_motivation": 1.3, "talkativeness": 0.9},
}


def merge_traits(names: list[str]) -> dict[str, float]:
    """Combine trait dicts; on key collision take the mean (V1 silently
    overwrote — F38). Unknown trait names raise instead of vanishing."""
    merged: dict[str, list[float]] = {}
    for name in names:
        if name not in PERSONALITY_TRAITS:
            raise KeyError(f"unknown personality trait: {name!r}")
        for key, value in PERSONALITY_TRAITS[name].items():
            merged.setdefault(key, []).append(value)
    return {k: sum(v) / len(v) for k, v in merged.items()}


def sociability_for(names: list[str]) -> float:
    """0..1 baseline used by socialize utility — defined for EVERY agent (F21)."""
    score = 0.5
    if "extrovert" in names:
        score = 0.8
    if "introvert" in names:
        score = 0.3
    if "social_butterfly" in names:
        score = min(1.0, score + 0.15)
    return score


# --- Schedules -----------------------------------------------------------------
# Windows are (start_hour, end_hour); start > end means the window wraps midnight.
SCHEDULE_TEMPLATES: dict[str, dict[str, dict[tuple[int, int], str]]] = {
    "office_worker_extrovert": {
        "weekdays": {
            (8, 9): "morning_coffee_at_cafe",
            (9, 12): "work_at_office",
            (12, 13): "lunch_break_at_cafe",
            (13, 17): "work_at_office",
            (17, 18): "evening_workout_at_gym",
            (18, 20): "dinner_at_cafe",
            (20, 22): "socialize_at_park",
        },
        "weekends": {
            (9, 11): "lazy_morning_at_home",
            (11, 13): "workout_at_gym",
            (13, 15): "grocery_shopping",
            (15, 18): "leisure_time_at_park",
            (18, 20): "dinner_at_cafe",
            (20, 22): "socialize_at_park",
            (22, 1): "party_at_bar",
        },
    },
    "student_conscientious": {
        "weekdays": {
            (8, 9): "breakfast_at_accommodation",
            (9, 12): "morning_classes_at_college",
            (12, 13): "lunch_at_cafe",
            (13, 16): "afternoon_classes_at_college",
            (16, 18): "study_at_college",
            (18, 20): "dinner_at_accommodation",
            (20, 22): "socialize_at_park",
        },
        "weekends": {
            (11, 13): "brunch_at_cafe",
            (13, 16): "study_session_at_college",
            (16, 18): "exercise_at_gym",
            (18, 20): "grocery_shopping",
            (20, 22): "socialize_at_park",
        },
    },
    "cafe_worker_social": {
        "weekdays": {
            (8, 12): "morning_shift_at_cafe",
            (12, 13): "lunch_break_at_park",
            (13, 17): "afternoon_shift_at_cafe",
            (17, 18): "grocery_shopping",
            (18, 20): "dinner_at_home",
            (20, 22): "socialize_at_park",
        },
        "weekends": {
            (10, 12): "lazy_morning_at_home",
            (12, 14): "brunch_shift_at_cafe",
            (14, 16): "personal_time_at_park",
            (16, 18): "workout_at_gym",
            (18, 20): "dinner_at_cafe",
            (20, 22): "socialize_at_park",
            (22, 1): "nightlife_at_bar",
        },
    },
    "fitness_enthusiast": {
        "weekdays": {
            (6, 8): "morning_workout_at_gym",
            (8, 9): "breakfast_at_cafe",
            (9, 12): "work_at_office",
            (12, 13): "lunch_at_cafe",
            (13, 17): "work_at_office",
            (17, 19): "evening_workout_at_gym",
            (19, 20): "dinner_at_home",
            (20, 22): "socialize_at_park",
        },
        "weekends": {
            (7, 9): "morning_workout_at_gym",
            (9, 10): "breakfast_at_cafe",
            (10, 12): "grocery_shopping",
            (12, 14): "lunch_at_home",
            (14, 18): "leisure_time_at_park",
            (18, 20): "dinner_at_home",
            (20, 22): "socialize_at_park",
        },
    },
    "lazy_sleeper": {
        "weekdays": {
            (10, 11): "lazy_morning_at_home",
            (11, 12): "brunch_at_cafe",
            (12, 16): "work_at_office",
            (16, 17): "coffee_break_at_cafe",
            (17, 20): "work_at_office",
            (20, 22): "socialize_at_park",
        },
        "weekends": {
            (11, 13): "lazy_morning_at_home",
            (13, 15): "brunch_at_cafe",
            (15, 18): "leisure_time_at_park",
            (18, 20): "dinner_at_home",
            (20, 22): "socialize_at_park",
        },
    },
    "workaholic_ambitious": {
        "weekdays": {
            (7, 8): "morning_coffee_at_cafe",
            (8, 12): "work_at_office",
            (12, 13): "lunch_break_at_cafe",
            (13, 18): "work_at_office",
            (18, 20): "dinner_at_cafe",
            (20, 22): "socialize_at_park",
            (22, 1): "party_at_bar",
        },
        "weekends": {
            (9, 11): "work_at_office",
            (11, 12): "coffee_break_at_cafe",
            (12, 15): "work_at_office",
            (15, 17): "networking_at_cafe",
            (17, 20): "dinner_at_cafe",
            (20, 22): "socialize_at_park",
        },
    },
}

# --- Activities ------------------------------------------------------------------
# location "home" resolves to the agent's own home_place.
# Cost is charged ONCE per schedule slot (F13). Effects apply once at activity start.
ACTIVITY_DATA: dict[str, dict] = {
    # Work
    "work_at_office": {"location": "business_office", "cost": 0, "kind": "work"},
    "morning_shift_at_cafe": {"location": "downtown_cafe", "cost": 0, "kind": "shift"},
    "afternoon_shift_at_cafe": {"location": "downtown_cafe", "cost": 0, "kind": "shift"},
    "brunch_shift_at_cafe": {"location": "downtown_cafe", "cost": 0, "kind": "shift"},
    # Education
    "morning_classes_at_college": {"location": "college_campus", "cost": 0, "kind": "classes"},
    "afternoon_classes_at_college": {"location": "college_campus", "cost": 0, "kind": "classes"},
    "study_at_college": {"location": "college_campus", "cost": 0, "kind": "study"},
    "study_session_at_college": {"location": "college_campus", "cost": 0, "kind": "study"},
    # Food & drink
    "morning_coffee_at_cafe": {"location": "downtown_cafe", "cost": 8, "kind": "meal"},
    "coffee_break_at_cafe": {"location": "downtown_cafe", "cost": 5, "kind": "meal"},
    "breakfast_at_cafe": {"location": "downtown_cafe", "cost": 12, "kind": "meal"},
    "brunch_at_cafe": {"location": "downtown_cafe", "cost": 18, "kind": "meal"},
    "lunch_at_cafe": {"location": "downtown_cafe", "cost": 15, "kind": "meal"},
    "lunch_break_at_cafe": {"location": "downtown_cafe", "cost": 15, "kind": "meal"},
    "dinner_at_cafe": {"location": "downtown_cafe", "cost": 20, "kind": "meal"},
    "networking_at_cafe": {"location": "downtown_cafe", "cost": 25, "kind": "meal"},
    "breakfast_at_accommodation": {"location": "student_accommodation", "cost": 0, "kind": "meal"},
    "dinner_at_accommodation": {"location": "student_accommodation", "cost": 0, "kind": "meal"},
    "lunch_at_home": {"location": "home", "cost": 0, "kind": "meal"},
    "dinner_at_home": {"location": "home", "cost": 0, "kind": "meal"},
    "eat_at_cafe": {"location": "downtown_cafe", "cost": 10, "kind": "meal"},  # hunger emergency
    # Home / rest
    "lazy_morning_at_home": {"location": "home", "cost": 0, "kind": "rest"},
    "sleep_at_home": {"location": "home", "cost": 0, "kind": "sleep"},
    "take_a_short_rest": {"location": "central_park", "cost": 0, "kind": "rest"},  # fatigue relief
    # Fitness
    "morning_workout_at_gym": {"location": "fitness_gym", "cost": 10, "kind": "workout"},
    "evening_workout_at_gym": {"location": "fitness_gym", "cost": 10, "kind": "workout"},
    "workout_at_gym": {"location": "fitness_gym", "cost": 10, "kind": "workout"},
    "exercise_at_gym": {"location": "fitness_gym", "cost": 10, "kind": "workout"},
    # Social & leisure
    "socialize_at_park": {"location": "central_park", "cost": 0, "kind": "social"},
    "lunch_break_at_park": {"location": "central_park", "cost": 0, "kind": "leisure"},
    "personal_time_at_park": {"location": "central_park", "cost": 0, "kind": "leisure"},
    "leisure_time_at_park": {"location": "central_park", "cost": 0, "kind": "leisure"},
    "party_at_bar": {"location": "nightlife_bar", "cost": 50, "kind": "social"},
    "nightlife_at_bar": {"location": "nightlife_bar", "cost": 60, "kind": "social"},
    # Errands
    "grocery_shopping": {"location": "grocery_store", "cost": 20, "kind": "errand"},
}


@dataclass(frozen=True)
class AgentSpec:
    id: str
    name: str
    icon: str
    color: str
    home_place: str                     # explicit place key (F40)
    home_pos: tuple[int, int]
    personality: list[str]
    schedule_template: str
    work_location: str | None
    sleep_window: tuple[int, int]       # (start_hour, end_hour), wrap-aware
    background: str = ""
    traits: dict[str, float] = field(default_factory=dict)
    sociability: float = 0.5


def _spec(**kw) -> AgentSpec:
    kw["traits"] = merge_traits(kw["personality"])
    kw["sociability"] = sociability_for(kw["personality"])
    return AgentSpec(**kw)


AGENTS: list[AgentSpec] = [
    _spec(id="alex", name="Alex Rodriguez", icon="AR", color="#FF6B6B",
          home_place="north_houses", home_pos=(3, 3),
          personality=["extrovert", "workaholic", "social_butterfly"],
          schedule_template="office_worker_extrovert", work_location="business_office",
          sleep_window=(23, 7),
          background="Alex is an ambitious office worker who thrives on people and deadlines."),
    _spec(id="bella", name="Bella Chen", icon="BC", color="#4ECDC4",
          home_place="student_accommodation", home_pos=(19, 3),
          personality=["introvert", "conscientious", "curious"],
          schedule_template="student_conscientious", work_location="college_campus",
          sleep_window=(23, 8),
          background="Bella is a diligent, quietly curious student who keeps a small circle close."),
    _spec(id="charlie", name="Charlie Davis", icon="CD", color="#45B7D1",
          home_place="central_houses", home_pos=(3, 15),
          personality=["extrovert", "social_butterfly", "spontaneous"],
          schedule_template="cafe_worker_social", work_location="downtown_cafe",
          sleep_window=(0, 8),
          background="Charlie works the cafe counter and knows everyone in town by name."),
    _spec(id="diana", name="Diana Kim", icon="DK", color="#96CEB4",
          home_place="student_accommodation", home_pos=(19, 4),
          personality=["agreeable", "conscientious", "fitness_enthusiast"],
          schedule_template="student_conscientious", work_location="college_campus",
          sleep_window=(22, 6),
          background="Diana balances coursework with early-morning training and easy friendships."),
    _spec(id="ethan", name="Ethan Brooks", icon="EB", color="#FECA57",
          home_place="south_houses", home_pos=(3, 19),
          personality=["fitness_enthusiast", "conscientious", "extrovert"],
          schedule_template="fitness_enthusiast", work_location="business_office",
          sleep_window=(22, 6),
          background="Ethan structures his days around the gym and steady office work."),
    _spec(id="fiona", name="Fiona Walsh", icon="FW", color="#FF9FF3",
          home_place="south_houses", home_pos=(4, 20),
          personality=["lazy", "introvert", "spontaneous"],
          schedule_template="lazy_sleeper", work_location="business_office",
          sleep_window=(22, 10),
          background="Fiona drifts through late mornings and works just as much as she must."),
]

RELATIONSHIPS: dict[str, dict[str, dict]] = {
    "alex": {"bella": {"type": "colleague", "affinity": 70}, "charlie": {"type": "friend", "affinity": 85},
             "diana": {"type": "acquaintance", "affinity": 50}, "ethan": {"type": "gym_buddy", "affinity": 75},
             "fiona": {"type": "neighbor", "affinity": 60}},
    "bella": {"alex": {"type": "colleague", "affinity": 70}, "charlie": {"type": "study_partner", "affinity": 80},
              "diana": {"type": "friend", "affinity": 90}, "ethan": {"type": "acquaintance", "affinity": 45},
              "fiona": {"type": "roommate", "affinity": 85}},
    "charlie": {"alex": {"type": "friend", "affinity": 85}, "bella": {"type": "study_partner", "affinity": 80},
                "diana": {"type": "classmate", "affinity": 65}, "ethan": {"type": "friend", "affinity": 75},
                "fiona": {"type": "acquaintance", "affinity": 55}},
    "diana": {"alex": {"type": "acquaintance", "affinity": 50}, "bella": {"type": "friend", "affinity": 90},
              "charlie": {"type": "classmate", "affinity": 65}, "ethan": {"type": "colleague", "affinity": 70},
              "fiona": {"type": "friend", "affinity": 80}},
    "ethan": {"alex": {"type": "gym_buddy", "affinity": 75}, "bella": {"type": "acquaintance", "affinity": 45},
              "charlie": {"type": "friend", "affinity": 75}, "diana": {"type": "colleague", "affinity": 70},
              "fiona": {"type": "neighbor", "affinity": 60}},
    "fiona": {"alex": {"type": "neighbor", "affinity": 60}, "bella": {"type": "roommate", "affinity": 85},
              "charlie": {"type": "acquaintance", "affinity": 55}, "diana": {"type": "friend", "affinity": 80},
              "ethan": {"type": "neighbor", "affinity": 60}},
}

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def validate_content(place_names: set[str]) -> list[str]:
    """Cross-validate schedules <-> activities <-> places (F39). Raises on
    missing references; returns warnings for unused activities."""
    problems: list[str] = []
    referenced: set[str] = set()
    for template_name, template in SCHEDULE_TEMPLATES.items():
        for day_kind, windows in template.items():
            for (start, end), activity in windows.items():
                if not (0 <= start <= 23 and 0 <= end <= 24):
                    raise ValueError(f"{template_name}/{day_kind}: bad window {(start, end)}")
                if activity not in ACTIVITY_DATA:
                    raise ValueError(f"{template_name}/{day_kind}: unknown activity {activity!r}")
                referenced.add(activity)
    for name, data in ACTIVITY_DATA.items():
        loc = data["location"]
        if loc != "home" and loc not in place_names:
            raise ValueError(f"activity {name!r}: unknown place {loc!r}")
    always_used = {"sleep_at_home", "eat_at_cafe", "take_a_short_rest"}
    unused = set(ACTIVITY_DATA) - referenced - always_used
    problems.extend(f"activity {name!r} defined but never scheduled" for name in sorted(unused))
    for spec in AGENTS:
        if spec.schedule_template not in SCHEDULE_TEMPLATES:
            raise ValueError(f"agent {spec.id}: unknown schedule template {spec.schedule_template!r}")
        if spec.home_place not in place_names:
            raise ValueError(f"agent {spec.id}: unknown home place {spec.home_place!r}")
    return problems
