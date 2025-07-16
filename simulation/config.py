# simulation/config.py

# --- Agent Personalities and Schedules ---
AGENT_CONFIG = [
    {
        'id': 'emily', 'name': 'Emily Carter', 'icon': 'EC', 'color': '#FF69B4',
        'home_pos': (3, 14), 'personality': 'extrovert',
        'schedule': { (9, 12): "work_at_cafe", (12, 13): "eat_at_cafe", (13, 17): "socialize_at_park", (17, 22): "relax_at_home" }
    },
    {
        'id': 'sophia', 'name': 'Sophia Reyes', 'icon': 'SR', 'color': '#8A2BE2',
        'home_pos': (3, 6), 'personality': 'introvert',
        'schedule': { (8, 16): "study_at_college", (16, 17): "get_groceries", (17, 23): "relax_at_home" }
    },
    {
        'id': 'mia', 'name': 'Mia Bennett', 'icon': 'MB', 'color': '#DAA520',
        'home_pos': (4, 15), 'personality': 'extrovert',
        'schedule': { (10, 18): "work_at_college", (18, 20): "socialize_at_bar", (20, 23): "relax_at_home" }
    },
    {
        'id': 'ryan', 'name': 'Ryan Cooper', 'icon': 'RC', 'color': '#00CED1',
        'home_pos': (2, 2), 'personality': 'introvert', # Moved to co-living
        'schedule': { (9, 17): "work_at_supply_store", (17, 18): "shop_at_supply_store", (18, 23): "relax_at_co_living" }
    },
    {
        'id': 'daniel', 'name': 'Daniel Park', 'icon': 'DP', 'color': '#FF4500',
        'home_pos': (3, 18), 'personality': 'extrovert', # In the college dorm
        'schedule': { (9, 12): "study_at_college_dorm", (12, 17): "hang_out_at_park", (17, 19): "eat_at_cafe", (19, 23): "socialize_at_bar" }
    },
    {
        'id': 'lucas', 'name': 'Lucas Brooks', 'icon': 'LB', 'color': '#32CD32',
        'home_pos': (18, 2), 'personality': 'introvert', # Near the college
        'schedule': { (8, 12): "read_at_park", (12, 13): "eat_at_home", (13, 18): "work_at_college", (18, 23): "relax_at_home" }
    }
]

# --- World Locations ---
# *** FIX: Each location now has a list of valid coordinates for agents to target. ***
PLACES = {
    'co_living_space': {'type': 'Co-Living Space', 'coords': [(1,1), (2,1), (3,1), (4,1), (1,2), (2,2), (3,2), (4,2)]},
    'bar_hobbs': {'type': 'Bar', 'coords': [(7,3), (8,3), (7,4), (8,4)]},
    'cafe_hobbs': {'type': 'Cafe', 'coords': [(3,6), (4,6), (3,7), (4,7)]},
    'supply_store_harvey': {'type': 'Supply Store', 'coords': [(6,1), (7,1), (6,2), (7,2)]},
    'college_oak_hill': {'type': 'College', 'coords': [(18,1), (19,1), (20,1), (18,2), (19,2), (20,2), (18,3), (19,3), (20,3)]},
    'grocery_pharmacy_willow': {'type': 'Grocery & Pharmacy', 'coords': [(7,8), (8,8), (9,8), (10,8), (11,8), (7,9), (8,9), (9,9)]},
    'johnson_park': {'type': 'Park', 'coords': [(3,10), (4,10), (5,10), (3,11), (4,11), (5,11), (3,12), (4,12), (5,12)]},
    'main_house_area': {'type': 'House', 'coords': [(3,13), (4,13), (5,13), (3,14), (4,14), (5,14), (3,15), (4,15), (5,15)]},
    'college_dorm_main': {'type': 'College Dorm', 'coords': [(3,18), (4,18), (5,18), (3,19), (4,19), (5,19)]},
}

# Mapping activities from schedules to locations
ACTIVITY_LOCATIONS = {
    "work_at_cafe": "cafe_hobbs", "eat_at_cafe": "cafe_hobbs",
    "socialize_at_park": "johnson_park", "relax_at_home": "main_house_area",
    "study_at_college": "college_oak_hill", "get_groceries": "grocery_pharmacy_willow",
    "work_at_college": "college_oak_hill", "socialize_at_bar": "bar_hobbs",
    "work_at_supply_store": "supply_store_harvey", "shop_at_supply_store": "supply_store_harvey",
    "relax_at_co_living": "co_living_space", "study_at_college_dorm": "college_dorm_main",
    "hang_out_at_park": "johnson_park", "read_at_park": "johnson_park",
    "eat_at_home": "main_house_area",
}
