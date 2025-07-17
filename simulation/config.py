# simulation/config.py
import random

AGENT_CONFIG = [
    {
        'id': 'emily', 'name': 'Emily Carter', 'icon': 'EC', 'color': '#FF69B4',
        'home_pos': (3, 14), 'personality': 'extrovert',
        'schedule': {
            (9, 12): "work_at_cafe", (12, 13): "eat_at_cafe",
            (13, 17): "socialize_at_park", (17, 22): "relax_at_home"
        }
    },
    {
        'id': 'sophia', 'name': 'Sophia Reyes', 'icon': 'SR', 'color': '#8A2BE2',
        'home_pos': (4, 14), 'personality': 'introvert',
        'schedule': {
            (8, 16): "study_at_college", (16, 17): "get_groceries",
            (17, 23): "relax_at_home"
        }
    },
    {
        'id': 'mia', 'name': 'Mia Bennett', 'icon': 'MB', 'color': '#DAA520',
        'home_pos': (5, 14), 'personality': 'extrovert',
        'schedule': {
            (10, 18): "work_at_college", (18, 20): "socialize_at_bar",
            (20, 23): "relax_at_home"
        }
    },
    {
        'id': 'ryan', 'name': 'Ryan Cooper', 'icon': 'RC', 'color': '#00CED1',
        'home_pos': (2, 2), 'personality': 'introvert',
        'schedule': {
            (9, 17): "work_at_supply_store", (17, 18): "shop_at_supply_store",
            (18, 23): "relax_at_co_living"
        }
    },
    {
        'id': 'daniel', 'name': 'Daniel Park', 'icon': 'DP', 'color': '#FF4500',
        'home_pos': (3, 18), 'personality': 'extrovert',
        'schedule': {
            (9, 12): "study_at_college_dorm", (12, 17): "hang_out_at_park",
            (17, 19): "eat_at_cafe", (19, 23): "socialize_at_bar"
        }
    },
    {
        'id': 'lucas', 'name': 'Lucas Brooks', 'icon': 'LB', 'color': '#32CD32',
        'home_pos': (18, 2), 'personality': 'introvert',
        'schedule': {
            (8, 12): "read_at_park", (12, 13): "eat_at_home",
            (13, 18): "work_at_college", (18, 23): "relax_at_home"
        }
    }
]

PLACES = {
    'co_living_space': {'type': 'Co-Living Space', 'coords': [(1,1), (2,1), (3,1), (4,1), (1,2), (2,2), (3,2), (4,2), (1,3), (2,3), (3,3), (4,3)]},
    'bar_hobbs': {'type': 'Bar', 'coords': [(7,3), (8,3), (7,4), (8,4)]},
    'cafe_hobbs': {'type': 'Cafe', 'coords': [(3,6), (4,6), (3,7), (4,7)]},
    'supply_store_harvey': {'type': 'Supply Store', 'coords': [(6,1), (7,1), (6,2), (7,2)]},
    'college_oak_hill': {'type': 'College', 'coords': [(18,1), (19,1), (20,1), (18,2), (19,2), (20,2), (18,3), (19,3), (20,3)]},
    'grocery_pharmacy_willow': {'type': 'Grocery & Pharmacy', 'coords': [(7,8), (8,8), (9,8), (10,8), (11,8), (7,9), (8,9), (9,9)]},
    'johnson_park': {'type': 'Park', 'coords': [(3,10), (4,10), (5,10), (3,11), (4,11), (5,11), (3,12), (4,12), (5,12)]},
    'main_house_area': {'type': 'House', 'coords': [(3,13), (4,13), (5,13), (3,14), (4,14), (5,14), (3,15), (4,15), (5,15)]},
    'college_dorm_main': {'type': 'College Dorm', 'coords': [(3,18), (4,18), (5,18), (3,19), (4,19), (5,19)]},
}

# *** FIX: Added a cost to certain activities. ***
ACTIVITY_DATA = {
    "work_at_cafe": {"location": "cafe_hobbs", "cost": 0},
    "eat_at_cafe": {"location": "cafe_hobbs", "cost": 15},
    "socialize_at_park": {"location": "johnson_park", "cost": 0},
    "relax_at_home": {"location": "main_house_area", "cost": 0},
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
