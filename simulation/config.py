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
    'fitness_enthusiast': {'gym_motivation': 0.9, 'health_focus': 0.8},
    'workaholic': {'work_motivation': 0.9, 'overtime_tendency': 0.8},
    'lazy': {'sleep_motivation': 0.8, 'procrastination': 0.7},
    'social_butterfly': {'party_motivation': 0.9, 'networking': 0.8},
}

# Define initial relationships between agents
# Affinity is on a scale of 0-100
RELATIONSHIPS = {
    'alex': {
        'bella': {'type': 'colleague', 'affinity': 70},
        'charlie': {'type': 'friend', 'affinity': 85},
        'diana': {'type': 'acquaintance', 'affinity': 50},
        'ethan': {'type': 'gym_buddy', 'affinity': 75},
        'fiona': {'type': 'neighbor', 'affinity': 60},
    },
    'bella': {
        'alex': {'type': 'colleague', 'affinity': 70},
        'charlie': {'type': 'study_partner', 'affinity': 80},
        'diana': {'type': 'friend', 'affinity': 90},
        'ethan': {'type': 'acquaintance', 'affinity': 45},
        'fiona': {'type': 'roommate', 'affinity': 85},
    },
    'charlie': {
        'alex': {'type': 'friend', 'affinity': 85},
        'bella': {'type': 'study_partner', 'affinity': 80},
        'diana': {'type': 'classmate', 'affinity': 65},
        'ethan': {'type': 'friend', 'affinity': 75},
        'fiona': {'type': 'acquaintance', 'affinity': 55},
    },
    'diana': {
        'alex': {'type': 'acquaintance', 'affinity': 50},
        'bella': {'type': 'friend', 'affinity': 90},
        'charlie': {'type': 'classmate', 'affinity': 65},
        'ethan': {'type': 'colleague', 'affinity': 70},
        'fiona': {'type': 'friend', 'affinity': 80},
    },
    'ethan': {
        'alex': {'type': 'gym_buddy', 'affinity': 75},
        'bella': {'type': 'acquaintance', 'affinity': 45},
        'charlie': {'type': 'friend', 'affinity': 75},
        'diana': {'type': 'colleague', 'affinity': 70},
        'fiona': {'type': 'neighbor', 'affinity': 60},
    },
    'fiona': {
        'alex': {'type': 'neighbor', 'affinity': 60},
        'bella': {'type': 'roommate', 'affinity': 85},
        'charlie': {'type': 'acquaintance', 'affinity': 55},
        'diana': {'type': 'friend', 'affinity': 80},
        'ethan': {'type': 'neighbor', 'affinity': 60},
    }
}


# ==================================================================================================
# AGENT SCHEDULE AND ACTIVITY CONFIGURATION
# ==================================================================================================

# Templates for schedules to reduce redundancy. Agents can be assigned these templates.
SCHEDULE_TEMPLATES = {
    'office_worker_extrovert': {
        'weekdays': {
            (8, 9): "morning_coffee_at_cafe",
            (9, 12): "work_at_office",
            (12, 13): "lunch_break_at_cafe",
            (13, 17): "work_at_office",
            (17, 18): "evening_workout_at_gym",
            (18, 19): "dinner_at_cafe",
            (19, 21): "socialize_at_park",
            (21, 23): "drinks_at_bar",
        },
        'weekends': {
            (9, 11): "lazy_morning_at_home",
            (11, 13): "workout_at_gym",
            (13, 15): "lunch_and_shopping_grocery",
            (15, 17): "socialize_at_park",
            (17, 19): "dinner_at_cafe",
            (19, 1): "party_at_bar",
        }
    },
    'student_conscientious': {
        'weekdays': {
            (8, 9): "breakfast_at_accommodation",
            (9, 12): "morning_classes_at_college",
            (12, 13): "lunch_at_cafe",
            (13, 16): "afternoon_classes_at_college",
            (16, 18): "study_at_college",
            (18, 19): "dinner_at_accommodation",
            (19, 21): "evening_study_at_accommodation",
            (21, 22): "relax_at_park",
        },
        'weekends': {
            (9, 11): "sleep_in_at_accommodation",
            (11, 13): "brunch_at_cafe",
            (13, 16): "study_session_at_college",
            (16, 18): "exercise_at_gym",
            (18, 20): "dinner_and_groceries",
            (20, 22): "social_time_at_park",
        }
    },
    'cafe_worker_social': {
        'weekdays': {
            (8, 12): "morning_shift_at_cafe",
            (12, 13): "lunch_break_at_park",
            (13, 17): "afternoon_shift_at_cafe",
            (17, 18): "grocery_shopping",
            (18, 20): "dinner_at_home",
            (20, 22): "socialize_at_park",
            (22, 24): "evening_drinks_at_bar",
        },
        'weekends': {
            (10, 12): "lazy_morning_at_home",
            (12, 14): "brunch_shift_at_cafe",
            (14, 16): "personal_time_at_park",
            (16, 18): "workout_at_gym",
            (18, 20): "dinner_with_friends_at_cafe",
            (20, 1): "nightlife_at_bar",
        }
    },
    'fitness_enthusiast': {
        'weekdays': {
            (6, 8): "morning_workout_at_gym",
            (8, 9): "protein_breakfast_at_cafe",
            (9, 12): "work_at_office",
            (12, 13): "healthy_lunch_at_cafe",
            (13, 17): "work_at_office",
            (17, 19): "evening_training_at_gym",
            (19, 20): "dinner_at_home",
            (20, 22): "recovery_walk_at_park",
        },
        'weekends': {
            (7, 9): "intensive_workout_at_gym",
            (9, 10): "post_workout_meal_at_cafe",
            (10, 12): "grocery_shopping_healthy",
            (12, 14): "meal_prep_at_home",
            (14, 16): "outdoor_activities_at_park",
            (16, 18): "social_workout_at_gym",
            (18, 20): "healthy_dinner_at_home",
            (20, 22): "relaxation_at_park",
        }
    },
    'lazy_sleeper': {
        'weekdays': {
            (10, 11): "slow_morning_at_home",
            (11, 12): "late_breakfast_at_cafe",
            (12, 16): "minimal_work_at_office",
            (16, 17): "coffee_break_at_cafe",
            (17, 19): "finish_work_at_office",
            (19, 21): "easy_dinner_at_home",
            (21, 23): "leisure_time_at_park",
        },
        'weekends': {
            (11, 13): "sleep_in_at_home",
            (13, 15): "brunch_at_cafe",
            (15, 17): "lazy_afternoon_at_park",
            (17, 19): "minimal_shopping_grocery",
            (19, 21): "takeout_dinner_at_home",
            (21, 23): "casual_socializing_at_bar",
        }
    },
    'workaholic_ambitious': {
        'weekdays': {
            (7, 8): "early_coffee_at_cafe",
            (8, 12): "focused_work_at_office",
            (12, 13): "working_lunch_at_office",
            (13, 18): "intensive_work_at_office",
            (18, 19): "dinner_at_cafe",
            (19, 22): "overtime_work_at_office",
            (22, 23): "late_evening_at_home",
        },
        'weekends': {
            (9, 11): "weekend_work_at_office",
            (11, 12): "coffee_break_at_cafe",
            (12, 15): "personal_projects_at_office",
            (15, 17): "networking_at_cafe",
            (17, 19): "dinner_meeting_at_cafe",
            (19, 21): "business_drinks_at_bar",
            (21, 23): "planning_at_home",
        }
    },
}

# This dictionary maps activities to their required location and cost.
# It's expanded with more activities to support the new schedules.
ACTIVITY_DATA = {
    # Work Activities
    "work_at_office": {"location": "business_office", "cost": 0},
    "work_at_cafe": {"location": "downtown_cafe", "cost": 0},
    "morning_shift_at_cafe": {"location": "downtown_cafe", "cost": 0},
    "afternoon_shift_at_cafe": {"location": "downtown_cafe", "cost": 0},
    "brunch_shift_at_cafe": {"location": "downtown_cafe", "cost": 0},
    "overtime_work_at_office": {"location": "business_office", "cost": 0},
    "focused_work_at_office": {"location": "business_office", "cost": 0},
    "minimal_work_at_office": {"location": "business_office", "cost": 0},
    "intensive_work_at_office": {"location": "business_office", "cost": 0},
    "working_lunch_at_office": {"location": "business_office", "cost": 0},
    "weekend_work_at_office": {"location": "business_office", "cost": 0},
    "personal_projects_at_office": {"location": "business_office", "cost": 0},
    "finish_work_at_office": {"location": "business_office", "cost": 0},

    # Education Activities
    "morning_classes_at_college": {"location": "college_campus", "cost": 0},
    "afternoon_classes_at_college": {"location": "college_campus", "cost": 0},
    "study_at_college": {"location": "college_campus", "cost": 0},
    "study_session_at_college": {"location": "college_campus", "cost": 0},
    "evening_study_at_accommodation": {"location": "student_accommodation", "cost": 0},

    # Food & Dining
    "morning_coffee_at_cafe": {"location": "downtown_cafe", "cost": 8},
    "lunch_break_at_cafe": {"location": "downtown_cafe", "cost": 15},
    "dinner_at_cafe": {"location": "downtown_cafe", "cost": 20},
    "late_breakfast_at_cafe": {"location": "downtown_cafe", "cost": 12},
    "brunch_at_cafe": {"location": "downtown_cafe", "cost": 18},
    "lunch_at_cafe": {"location": "downtown_cafe", "cost": 15},
    "early_coffee_at_cafe": {"location": "downtown_cafe", "cost": 6},
    "coffee_break_at_cafe": {"location": "downtown_cafe", "cost": 5},
    "protein_breakfast_at_cafe": {"location": "downtown_cafe", "cost": 15},
    "healthy_lunch_at_cafe": {"location": "downtown_cafe", "cost": 18},
    "post_workout_meal_at_cafe": {"location": "downtown_cafe", "cost": 20},
    "networking_at_cafe": {"location": "downtown_cafe", "cost": 25},
    "dinner_meeting_at_cafe": {"location": "downtown_cafe", "cost": 35},
    "dinner_with_friends_at_cafe": {"location": "downtown_cafe", "cost": 25},
    "breakfast_at_accommodation": {"location": "student_accommodation", "cost": 0},
    "dinner_at_accommodation": {"location": "student_accommodation", "cost": 0},

    # Home Activities
    "lazy_morning_at_home": {"location": "home", "cost": 0},
    "dinner_at_home": {"location": "home", "cost": 0},
    "relax_at_home": {"location": "home", "cost": 0},
    "slow_morning_at_home": {"location": "home", "cost": 0},
    "easy_dinner_at_home": {"location": "home", "cost": 0},
    "takeout_dinner_at_home": {"location": "home", "cost": 25},
    "late_evening_at_home": {"location": "home", "cost": 0},
    "sleep_in_at_home": {"location": "home", "cost": 0},
    "sleep_in_at_accommodation": {"location": "student_accommodation", "cost": 0},
    "meal_prep_at_home": {"location": "home", "cost": 0},
    "healthy_dinner_at_home": {"location": "home", "cost": 0},
    "planning_at_home": {"location": "home", "cost": 0},

    # Fitness & Health
    "evening_workout_at_gym": {"location": "fitness_gym", "cost": 10},
    "workout_at_gym": {"location": "fitness_gym", "cost": 10},
    "exercise_at_gym": {"location": "fitness_gym", "cost": 10},
    "morning_workout_at_gym": {"location": "fitness_gym", "cost": 10},
    "evening_training_at_gym": {"location": "fitness_gym", "cost": 10},
    "intensive_workout_at_gym": {"location": "fitness_gym", "cost": 15},
    "social_workout_at_gym": {"location": "fitness_gym", "cost": 10},

    # Social Activities
    "socialize_at_park": {"location": "central_park", "cost": 0},
    "drinks_at_bar": {"location": "nightlife_bar", "cost": 30},
    "party_at_bar": {"location": "nightlife_bar", "cost": 50},
    "evening_drinks_at_bar": {"location": "nightlife_bar", "cost": 25},
    "nightlife_at_bar": {"location": "nightlife_bar", "cost": 60},
    "casual_socializing_at_bar": {"location": "nightlife_bar", "cost": 20},
    "business_drinks_at_bar": {"location": "nightlife_bar", "cost": 40},
    "lunch_break_at_park": {"location": "central_park", "cost": 0},
    "relax_at_park": {"location": "central_park", "cost": 0},
    "social_time_at_park": {"location": "central_park", "cost": 0},
    "personal_time_at_park": {"location": "central_park", "cost": 0},
    "recovery_walk_at_park": {"location": "central_park", "cost": 0},
    "outdoor_activities_at_park": {"location": "central_park", "cost": 0},
    "leisure_time_at_park": {"location": "central_park", "cost": 0},
    "lazy_afternoon_at_park": {"location": "central_park", "cost": 0},
    "relaxation_at_park": {"location": "central_park", "cost": 0},

    # Shopping & Errands
    "grocery_shopping": {"location": "grocery_store", "cost": 40},
    "lunch_and_shopping_grocery": {"location": "grocery_store", "cost": 45},
    "dinner_and_groceries": {"location": "grocery_store", "cost": 35},
    "grocery_shopping_healthy": {"location": "grocery_store", "cost": 50},
    "minimal_shopping_grocery": {"location": "grocery_store", "cost": 20},

    # Sleep
    "sleep_at_home": {"location": "home", "cost": 0},
}


# ==================================================================================================
# AGENT CONFIGURATION
# ==================================================================================================

AGENT_CONFIG = [
    {
        'id': 'alex', 'name': 'Alex Rodriguez', 'icon': 'AR', 'color': '#FF6B6B',
        'home_pos': (3, 3),  # North houses
        'personality': ['extrovert', 'workaholic', 'social_butterfly'],
        'schedule_template': 'office_worker_extrovert',
        'work_location': 'business_office'
    },
    {
        'id': 'bella', 'name': 'Bella Chen', 'icon': 'BC', 'color': '#4ECDC4',
        'home_pos': (19, 3),  # Student accommodation
        'personality': ['introvert', 'conscientious', 'curious'],
        'schedule_template': 'student_conscientious',
        'work_location': 'college_campus'
    },
    {
        'id': 'charlie', 'name': 'Charlie Davis', 'icon': 'CD', 'color': '#45B7D1',
        'home_pos': (3, 15),  # Central houses
        'personality': ['extrovert', 'social_butterfly', 'spontaneous'],
        'schedule_template': 'cafe_worker_social',
        'work_location': 'downtown_cafe'
    },
    {
        'id': 'diana', 'name': 'Diana Kim', 'icon': 'DK', 'color': '#96CEB4',
        'home_pos': (19, 4),  # Student accommodation
        'personality': ['agreeable', 'conscientious', 'fitness_enthusiast'],
        'schedule_template': 'student_conscientious',
        'work_location': 'college_campus'
    },
    {
        'id': 'ethan', 'name': 'Ethan Brooks', 'icon': 'EB', 'color': '#FECA57',
        'home_pos': (3, 19),  # South houses
        'personality': ['fitness_enthusiast', 'conscientious', 'extrovert'],
        'schedule_template': 'fitness_enthusiast',
        'work_location': 'business_office'
    },
    {
        'id': 'fiona', 'name': 'Fiona Walsh', 'icon': 'FW', 'color': '#FF9FF3',
        'home_pos': (4, 20),  # South houses
        'personality': ['lazy', 'introvert', 'spontaneous'],
        'schedule_template': 'lazy_sleeper',
        'work_location': 'business_office'
    }
]