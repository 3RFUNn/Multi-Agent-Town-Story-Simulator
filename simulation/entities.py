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
        self.current_goal = "Initializing..."
        self.current_action = "Thinking..."
        self.current_activity = None
        self.state = 'idle'
        self.destination_name = None
        self.path = []
        self.path_index = 0
        self.action_duration = 0
        self.interacting_with = None # ID of agent they are talking to

        self.money = random.randint(50, 200)
        self.needs = {
            'hunger': random.randint(0, 40),
            'social': random.randint(30, 70),
            'energy': random.randint(80, 100),
        }

        # *** FIX: Each agent now has their own personal log. ***
        self.log = []

    def add_log(self, entry, world_time):
        """Adds a new entry to the agent's personal log with a timestamp."""
        hour, minute = world_time
        ampm = "AM" if hour < 12 else "PM"
        display_hour = hour % 12 if hour % 12 != 0 else 12
        timestamp = f"{display_hour:02d}:{minute:02d} {ampm}"
        self.log.insert(0, f"[{timestamp}] {entry}")
        # Keep the log from getting too long
        if len(self.log) > 50:
            self.log.pop()

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
            'needs': self.needs,
            'money': self.money,
            'log': self.log, # Include the log in the data sent to the frontend
            'interacting_with': self.interacting_with
        }

    def update_needs(self, world_time):
        """Periodically updates the agent's needs over time."""
        # Only update needs if not sleeping
        if self.current_activity != "sleep_at_home":
            self.needs['hunger'] = min(100, self.needs['hunger'] + 0.25)
            self.needs['social'] = min(100, self.needs['social'] + 0.15)
        
        is_working = "work" in (self.current_activity or "")
        
        if self.current_activity == "sleep_at_home":
             self.needs['energy'] = min(100, self.needs['energy'] + 0.8)
        elif not is_working:
            self.needs['energy'] = max(0, self.needs['energy'] - 0.1)
        else: # Is working
            self.needs['energy'] = max(0, self.needs['energy'] - 0.2)