# simulation/config.py
import random

AGENT_CONFIG = [
    {
        'id': 'emily', 'name': 'Emily Carter', 'icon': 'EC', 'color': '#FF69B4',
        'home_pos': (3, 14), 'personality': 'extrovert',
        'schedule': {
            (9, 12): "work_at_cafe", (12, 13): "eat_at_cafe",
            (13, 17): "socialize_at_park", (17, 22): "relax_at_home", (22, 7): "sleep_at_home"
        }
    },
    {
        'id': 'sophia', 'name': 'Sophia Reyes', 'icon': 'SR', 'color': '#8A2BE2',
        'home_pos': (4, 14), 'personality': 'introvert',
        'schedule': {
            (8, 16): "study_at_college", (16, 17): "get_groceries",
            (17, 22): "relax_at_home", (22, 7): "sleep_at_home"
        }
    },
    {
        'id': 'mia', 'name': 'Mia Bennett', 'icon': 'MB', 'color': '#DAA520',
        'home_pos': (5, 14), 'personality': 'extrovert',
        'schedule': {
            (10, 18): "work_at_college", (18, 20): "socialize_at_bar",
            (20, 22): "relax_at_home", (22, 7): "sleep_at_home"
        }
    },
    {
        'id': 'ryan', 'name': 'Ryan Cooper', 'icon': 'RC', 'color': '#00CED1',
        'home_pos': (2, 2), 'personality': 'introvert',
        'schedule': {
            (9, 17): "work_at_supply_store", (17, 18): "shop_at_supply_store",
            (18, 22): "relax_at_co_living", (22, 7): "sleep_at_home"
        }
    },
    {
        'id': 'daniel', 'name': 'Daniel Park', 'icon': 'DP', 'color': '#FF4500',
        'home_pos': (21, 1), 'personality': 'extrovert', # Moved to dorm
        'schedule': {
            (9, 12): "study_at_college_dorm", (12, 17): "hang_out_at_park",
            (17, 19): "eat_at_cafe", (19, 22): "socialize_at_bar", (22, 7): "sleep_at_home"
        }
    },
    {
        'id': 'lucas', 'name': 'Lucas Brooks', 'icon': 'LB', 'color': '#32CD32',
        'home_pos': (22, 1), 'personality': 'introvert', # Moved to dorm
        'schedule': {
            (8, 12): "read_at_park", (12, 13): "eat_at_home",
            (13, 18): "work_at_college", (18, 22): "relax_at_home", (22, 7): "sleep_at_home"
        }
    }
]

# *** FIX: The PLACES dictionary has been removed from this file. ***
# It is now loaded from map_data.json in app.py.

# This dictionary maps activities to their required location and cost.
ACTIVITY_DATA = {
    "work_at_cafe": {"location": "cafe_hobbs", "cost": 0},
    "eat_at_cafe": {"location": "cafe_hobbs", "cost": 15},
    "socialize_at_park": {"location": "johnson_park", "cost": 0},
    "relax_at_home": {"location": "main_house_area", "cost": 0},
    "sleep_at_home": {"location": "main_house_area", "cost": 0},
    "study_at_college": {"location": "college_oak_hill", "cost": 0},
    "get_groceries": {"location": "grocery_pharmacy_willow", "cost": 30},
    "work_at_college": {"location": "college_oak_hill", "cost": 0},
    "socialize_at_bar": {"location": "bar_hobbs", "cost": 25},
    "work_at_supply_store": {"location": "supply_store_harvey", "cost": 0},
    "shop_at_supply_store": {"location": "supply_store_harvey", "cost": 20},
    "relax_at_co_living": {"location": "co_living_space", "cost": 0},
    "study_at_college_dorm": {"location": "college_dorm_main", "cost": 0},
    "hang_out_at_park": {"location": "johnson_park", "cost": 0},
    "read_at_park": {"location": "johnson_park", "cost": 0},
    "eat_at_home": {"location": "main_house_area", "cost": 0},
}
