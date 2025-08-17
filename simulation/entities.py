# simulation/entities.py
# Defines the Agent class and related logic for agent state, needs, relationships, and memory.

import random
from simulation.config import PERSONALITY_TRAITS, RELATIONSHIPS

class Agent:
    """
    Represents an agent in the simulation, holding all its state and attributes.
    Supports personality, relationships, dynamic memory, and simulation needs.
    """
    def __init__(self, agent_id, name, icon, color, home_pos, personality, schedule_template, work_location, background=None):
        self.id = agent_id
        self.name = name
        self.icon = icon
        self.color = color
        self.x = home_pos[0]
        self.y = home_pos[1]
        self.home = {'x': home_pos[0], 'y': home_pos[1]}

        # --- Cognitive and Behavioral State ---
        self.personality_names = personality # e.g., ['extrovert', 'conscientious']
        self.personality = {k: v for p in personality for k, v in PERSONALITY_TRAITS.get(p, {}).items()}
        self.schedule_template = schedule_template
        self.work_location = work_location
        self.relationships = RELATIONSHIPS.get(self.id, {})

        # --- Dynamic State ---
        self.current_goal = "Initializing..."
        self.current_action = "Thinking..."
        self.current_activity = None
        self.state = 'idle' # States: idle, moving, doing_action, interacting
        self.destination_name = None
        self.path = []
        self.path_index = 0
        self.action_duration = 0
        self.interacting_with = None # ID of agent they are talking to

        self.money = random.randint(100, 150)
        self.needs = {
            'hunger': 0,
            'social': 0,
            'energy': 0,
        }

        self.rest_ticks = 0  # Track rest cycles for ExecuteRest
        self.eat_ticks = 0   # Track eat cycles for ExecuteEat

        self.background = background or f"{name} grew up in this town and has a unique story."
        from simulation.memory.memory import AgentMemoryStream
        self.memory_stream = AgentMemoryStream()

        self.log = []

    def add_log(self, entry, world_time, day_of_week):
        """Adds a new entry to the agent's personal log with a timestamp."""
        hour, minute = world_time
        ampm = "AM" if hour < 12 else "PM"
        display_hour = hour % 12 if hour % 12 != 0 else 12
        timestamp = f"[{day_of_week} {display_hour:02d}:{minute:02d} {ampm}]"
        log_entry = f"{timestamp} {entry}"
        self.log.insert(0, log_entry)
        # Keep the log from getting too long
        if len(self.log) > 50:
            self.log.pop()
        # Add to memory stream as well
        from simulation.memory.memory import Memory
        mem = Memory(event=entry, timestamp=f"{day_of_week}", details={'time': world_time})
        self.memory_stream.add_memory(mem)

    def update_needs(self, world_time):
        """Periodically updates the agent's needs over time, influenced by personality."""
        # Base increase rates (higher value = more urgent need)
        hunger_increase = 0.25
        social_increase = 0.15
        energy_increase = 0.1 # Tiredness increases over time
        work_energy_increase = 0.2 # Tiredness increases faster when working
        sleep_energy_decrease = 0.8 # Tiredness decreases when sleeping

        # Only update needs if not sleeping
        if self.current_activity != "sleep_at_home":
            self.needs['hunger'] = min(100, self.needs['hunger'] + hunger_increase)
            
            # Social need increases faster for extroverts
            social_motivation = self.personality.get('social_motivation', 1.0)
            self.needs['social'] = min(100, self.needs['social'] + (social_increase * social_motivation))
        
        is_working = "work" in (self.current_activity or "")
        
        if self.current_activity == "sleep_at_home":
             self.needs['energy'] = max(0, self.needs['energy'] - sleep_energy_decrease)
        elif not is_working:
            self.needs['energy'] = min(100, self.needs['energy'] + energy_increase)
        else: # Is working
             # Conscientious agents get tired slower while working
            work_ethic_modifier = self.personality.get('work_ethic', 1.0)
            self.needs['energy'] = min(100, self.needs['energy'] + (work_energy_increase / work_ethic_modifier))

    def get_relationship(self, other_agent_id):
        """Retrieves the relationship status with another agent."""
        return self.relationships.get(other_agent_id)

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
            'log': self.log,
            'interacting_with': self.interacting_with,
            'personality': self.personality_names, # Send personality names to frontend
        }