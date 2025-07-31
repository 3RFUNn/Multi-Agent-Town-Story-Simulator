# simulation/config.py
import random

# ==================================================================================================
# AGENT PERSONALITY AND RELATIONSHIP CONFIGURATION
# ==================================================================================================

# Define more nuanced personality traits. These can be used to influence BT decisions.
PERSONALITY_TRAITS = {
    'extrovert': {'social_motivation': 1.5, 'talkativeness': 0.8, 'prefers_group': True},
    'introvert': {'social_motivation': 0.5, 'talkativeness': 0.3, 'prefers_group': False},
    'agreeable': {'cooperativeness': 0.9, 'conflict_aversion': 0.7},
    'conscientious': {'planning_focus': 0.8, 'work_ethic': 0.9},
    'curious': {'exploration_tendency': 0.8, 'learning_focus': 0.7},
    'spontaneous': {'planning_focus': 0.2, 'routine_adherence': 0.3},
}

# Define initial relationships between agents
# Affinity is on a scale of 0-100
RELATIONSHIPS = {
    'emily': {
        'sophia': {'type': 'friend', 'affinity': 80},
        'ryan': {'type': 'acquaintance', 'affinity': 50},
        'mia': {'type': 'friend', 'affinity': 85},
    },
    'sophia': {
        'emily': {'type': 'friend', 'affinity': 80},
        'lucas': {'type': 'friend', 'affinity': 75},
    },
    'mia': {
        'emily': {'type': 'friend', 'affinity': 85},
        'daniel': {'type': 'friend', 'affinity': 70},
    },
    'ryan': {
        'emily': {'type': 'acquaintance', 'affinity': 50},
        'daniel': {'type': 'colleague', 'affinity': 60},
    },
    'daniel': {
        'mia': {'type': 'friend', 'affinity': 70},
        'ryan': {'type': 'colleague', 'affinity': 60},
        'lucas': {'type': 'roommate', 'affinity': 65},
    },
    'lucas': {
        'sophia': {'type': 'friend', 'affinity': 75},
        'daniel': {'type': 'roommate', 'affinity': 65},
    }
}


# ==================================================================================================
# AGENT SCHEDULE AND ACTIVITY CONFIGURATION
# ==================================================================================================

# Templates for schedules to reduce redundancy. Agents can be assigned these templates.
SCHEDULE_TEMPLATES = {
    'student_extrovert': {
        'weekdays': {
            (8, 11): "study_at_college",
            (11, 12): "socialize_at_college",
            (12, 13): "eat_at_cafe",
            (13, 16): "group_study_at_college",
            (16, 18): "hang_out_at_park",
            (18, 20): "relax_at_home",
            (20, 22): "socialize_at_bar",
        },
        'weekends': {
            (10, 13): "relax_at_home",
            (13, 15): "hang_out_at_park",
            (15, 17): "shop_at_supply_store",
            (17, 19): "eat_at_cafe",
            (19, 22): "go_to_bar_with_friends",
        }
    },
    'student_introvert': {
        'weekdays': {
            (9, 12): "study_at_college_dorm",
            (12, 13): "eat_at_home",
            (13, 17): "read_at_park",
            (17, 22): "relax_at_home",
        },
        'weekends': {
            (11, 14): "read_at_park",
            (14, 16): "get_groceries",
            (16, 22): "relax_at_home",
        }
    },
    'worker_extrovert': {
        'weekdays': {
            (9, 12): "work_at_cafe",
            (12, 13): "eat_at_cafe",
            (13, 17): "work_at_cafe",
            (17, 19): "socialize_at_park",
            (19, 22): "go_to_bar_with_friends",
        },
        'weekends': {
            (10, 12): "relax_at_co_living",
            (12, 14): "hang_out_at_park",
            (14, 17): "eat_at_cafe",
            (17, 22): "socialize_at_bar",
        }
    },
    'worker_introvert': {
        'weekdays': {
            (9, 17): "work_at_supply_store",
            (17, 18): "shop_at_supply_store",
            (18, 22): "relax_at_co_living",
        },
        'weekends': {
            (12, 14): "get_groceries",
            (14, 18): "relax_at_co_living",
            (18, 22): "read_at_park",
        }
    }
}

# This dictionary maps activities to their required location and cost.
# It's expanded with more activities to support the new schedules.
ACTIVITY_DATA = {
    # Work & Study
    "work_at_cafe": {"location": "cafe_hobbs", "cost": 0},
    "work_at_supply_store": {"location": "supply_store_harvey", "cost": 0},
    "work_at_college": {"location": "college_oak_hill", "cost": 0},
    "study_at_college": {"location": "college_oak_hill", "cost": 0},
    "study_at_college_dorm": {"location": "college_dorm_main", "cost": 0},
    "group_study_at_college": {"location": "college_oak_hill", "cost": 0},

    # Food & Shopping
    "eat_at_cafe": {"location": "cafe_hobbs", "cost": 15},
    "eat_at_home": {"location": "main_house_area", "cost": 0},
    "get_groceries": {"location": "grocery_pharmacy_willow", "cost": 30},
    "shop_at_supply_store": {"location": "supply_store_harvey", "cost": 20},

    # Social & Leisure
    "socialize_at_park": {"location": "johnson_park", "cost": 0},
    "socialize_at_bar": {"location": "bar_hobbs", "cost": 25},
    "go_to_bar_with_friends": {"location": "bar_hobbs", "cost": 25},
    "socialize_at_college": {"location": "college_oak_hill", "cost": 0},
    "hang_out_at_park": {"location": "johnson_park", "cost": 0},
    "read_at_park": {"location": "johnson_park", "cost": 0},

    # Home & Relaxation
    "relax_at_home": {"location": "main_house_area", "cost": 0},
    "relax_at_co_living": {"location": "co_living_space", "cost": 0},
    "sleep_at_home": {"location": "main_house_area", "cost": 0},
}


# ==================================================================================================
# AGENT CONFIGURATION
# ==================================================================================================

AGENT_CONFIG = [
    {
        'id': 'emily', 'name': 'Emily Carter', 'icon': 'EC', 'color': '#FF69B4',
        'home_pos': (3, 14),
        'personality': ['extrovert', 'spontaneous'],
        'schedule_template': 'worker_extrovert',
        'work_location': 'cafe_hobbs'
    },
    {
        'id': 'sophia', 'name': 'Sophia Reyes', 'icon': 'SR', 'color': '#8A2BE2',
        'home_pos': (4, 14),
        'personality': ['introvert', 'conscientious', 'curious'],
        'schedule_template': 'student_introvert',
        'work_location': 'college_oak_hill'
    },
    {
        'id': 'mia', 'name': 'Mia Bennett', 'icon': 'MB', 'color': '#DAA520',
        'home_pos': (5, 14),
        'personality': ['extrovert', 'agreeable'],
        'schedule_template': 'student_extrovert',
        'work_location': 'college_oak_hill'
    },
    {
        'id': 'ryan', 'name': 'Ryan Cooper', 'icon': 'RC', 'color': '#00CED1',
        'home_pos': (2, 2),
        'personality': ['introvert', 'conscientious'],
        'schedule_template': 'worker_introvert',
        'work_location': 'supply_store_harvey'
    },
    {
        'id': 'daniel', 'name': 'Daniel Park', 'icon': 'DP', 'color': '#FF4500',
        'home_pos': (21, 1), # Dorm
        'personality': ['extrovert', 'spontaneous', 'agreeable'],
        'schedule_template': 'student_extrovert',
        'work_location': 'college_dorm_main'
    },
    {
        'id': 'lucas', 'name': 'Lucas Brooks', 'icon': 'LB', 'color': '#32CD32',
        'home_pos': (22, 1), # Dorm
        'personality': ['introvert', 'curious'],
        'schedule_template': 'student_introvert',
        'work_location': 'college_dorm_main'
    }
]