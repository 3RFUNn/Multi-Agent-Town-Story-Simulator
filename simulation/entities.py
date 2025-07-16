# simulation/entities.py

import random

class Agent:
    """
    Represents an agent in the simulation, holding all its state and attributes.
    """
    def __init__(self, agent_id, name, icon, color, home_x, home_y, personality, schedule):
        self.id = agent_id
        self.name = name
        self.icon = icon
        self.color = color
        self.x = home_x
        self.y = home_y
        self.home = {'x': home_x, 'y': home_y}

        # --- Cognitive and Behavioral State ---
        self.personality = personality
        self.schedule = schedule
        self.current_goal = "Idle"
        self.current_action = "Wandering"
        self.state = 'idle' # 'idle', 'moving', 'doing_action'
        
        # *** FIX: Added the missing destination attribute ***
        self.destination = None 
        
        self.path = []
        self.path_index = 0
        self.action_duration = 0 # How many ticks an action will last

        # --- Agent Needs (scale of 0-100) ---
        self.needs = {
            'hunger': random.randint(20, 60),
            'social': random.randint(40, 80),
            'energy': 100
        }

        # --- Relationships and Memory ---
        self.relationships = {}
        self.memory = []

    def to_dict(self):
        """Converts the agent object to a dictionary for JSON serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'x': self.x,
            'y': self.y,
            'icon': self.icon,
            'color': self.color,
            'current_goal': self.current_goal,
            'current_action': self.current_action,
            'state': self.state,
            'needs': self.needs
        }

    def update_needs(self):
        """Periodically updates the agent's needs over time."""
        self.needs['hunger'] = min(100, self.needs['hunger'] + 0.2) # Increased rate for testing
        self.needs['social'] = min(100, self.needs['social'] + 0.1)
        self.needs['energy'] = max(0, self.needs['energy'] - 0.05)
