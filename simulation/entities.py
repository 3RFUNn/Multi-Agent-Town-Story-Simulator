# simulation/entities.py

import random
from simulation.config import PERSONALITY_TRAITS, RELATIONSHIPS

class Agent:
    """
    Represents an agent in the simulation, holding all its state and attributes.
    This class has been refactored to support more complex states like personality,
    relationships, and a dynamic memory stream.
    """
    def __init__(self, agent_id, name, icon, color, home_pos, personality, schedule_template, work_location):
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

        self.money = random.randint(50, 200)
        self.needs = {
            'hunger': random.randint(0, 40),
            'social': random.randint(30, 70),
            'energy': random.randint(80, 100),
        }

        # The memory stream will store Memory objects (to be implemented)
        self.memory_stream = []
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

    def update_needs(self, world_time):
        """Periodically updates the agent's needs over time, influenced by personality."""
        
        # Personality-based modifiers
        is_lazy = 'lazy' in self.personality_names
        is_workaholic = 'workaholic' in self.personality_names
        is_fitness_enthusiast = 'fitness_enthusiast' in self.personality_names
        is_extrovert = 'extrovert' in self.personality_names
        is_introvert = 'introvert' in self.personality_names
        is_social_butterfly = 'social_butterfly' in self.personality_names
        
        # Base decay rates with personality adjustments
        if is_lazy:
            hunger_increase = 0.3  # Lazy people eat less frequently
            social_increase = 0.2  # Less social interaction
            energy_decrease = 0.25  # Tire out faster
        elif is_workaholic:
            hunger_increase = 0.5  # Skip meals for work
            social_increase = 0.15  # Neglect social needs
            energy_decrease = 0.35  # Work drains energy
        elif is_fitness_enthusiast:
            hunger_increase = 0.6  # Higher metabolism
            social_increase = 0.2   # Moderate social needs
            energy_decrease = 0.1   # Better stamina
        else:
            hunger_increase = 0.4
            social_increase = 0.25
            energy_decrease = 0.15

        # Social need adjustments based on personality
        if is_extrovert or is_social_butterfly:
            social_increase *= 1.8  # Extroverts need more social interaction
        elif is_introvert:
            social_increase *= 0.6  # Introverts need less social interaction

        # Update needs based on current activity
        if self.current_activity == "sleep_at_home":
            # While sleeping: restore energy, minimal hunger/social changes
            if is_lazy:
                self.needs['energy'] = min(100, self.needs['energy'] + 1.5)  # Lazy people love sleep
            elif is_fitness_enthusiast:
                self.needs['energy'] = min(100, self.needs['energy'] + 1.8)  # Better recovery
            else:
                self.needs['energy'] = min(100, self.needs['energy'] + 1.2)
            
            self.needs['hunger'] = min(100, self.needs['hunger'] + (hunger_increase * 0.2))
            # Social needs don't change much while sleeping
        else:
            # Normal waking activities
            self.needs['hunger'] = min(100, self.needs['hunger'] + hunger_increase)
            self.needs['social'] = min(100, self.needs['social'] + social_increase)
            
            # Energy decreases based on activity type and personality
            is_working = ("work" in (self.current_activity or "") or 
                         "shift" in (self.current_activity or "") or
                         "classes" in (self.current_activity or ""))
            
            if is_working:
                if is_workaholic:
                    # Workaholics lose less energy from work (they thrive on it)
                    self.needs['energy'] = max(0, self.needs['energy'] - 0.2)
                elif is_lazy:
                    # Lazy people hate work and lose more energy
                    self.needs['energy'] = max(0, self.needs['energy'] - 0.5)
                else:
                    self.needs['energy'] = max(0, self.needs['energy'] - 0.3)
                    
            elif "workout" in (self.current_activity or "") or "gym" in (self.current_activity or ""):
                if is_fitness_enthusiast:
                    # Fitness enthusiasts gain energy from working out (endorphins)
                    self.needs['energy'] = max(0, self.needs['energy'] - 0.2)
                    self.needs['social'] = max(0, self.needs['social'] - 0.3)  # Social aspect of gym
                elif is_lazy:
                    # Lazy people hate exercise
                    self.needs['energy'] = max(0, self.needs['energy'] - 0.8)
                else:
                    self.needs['energy'] = max(0, self.needs['energy'] - 0.5)
                    
            elif "relax" in (self.current_activity or "") or "park" in (self.current_activity or ""):
                if is_lazy:
                    # Lazy people love relaxing
                    self.needs['energy'] = min(100, self.needs['energy'] + 0.4)
                else:
                    self.needs['energy'] = min(100, self.needs['energy'] + 0.2)
                # Park activities also reduce stress/improve mood
                self.needs['social'] = max(0, self.needs['social'] - 0.1)
                    
            elif "socialize" in (self.current_activity or "") or "drinks" in (self.current_activity or "") or "party" in (self.current_activity or ""):
                if is_extrovert or is_social_butterfly:
                    # Extroverts gain energy from socializing
                    self.needs['energy'] = min(100, self.needs['energy'] + 0.15)
                    self.needs['social'] = max(0, self.needs['social'] - 0.8)  # Major social satisfaction
                elif is_introvert:
                    # Introverts lose energy from socializing but still get some social benefit
                    self.needs['energy'] = max(0, self.needs['energy'] - 0.25)
                    self.needs['social'] = max(0, self.needs['social'] - 0.4)  # Less social benefit
                else:
                    # Normal people get moderate benefits
                    self.needs['social'] = max(0, self.needs['social'] - 0.6)
                    
            elif "eat" in (self.current_activity or "") or "lunch" in (self.current_activity or "") or "dinner" in (self.current_activity or "") or "breakfast" in (self.current_activity or ""):
                # Eating activities continuously satisfy hunger
                self.needs['hunger'] = max(0, self.needs['hunger'] - 0.5)
                
            elif "coffee" in (self.current_activity or ""):
                # Coffee provides energy and reduces hunger slightly
                self.needs['energy'] = min(100, self.needs['energy'] + 0.2)
                self.needs['hunger'] = max(0, self.needs['hunger'] - 0.2)
            else:
                # Normal activities with personality adjustments
                if is_lazy:
                    self.needs['energy'] = max(0, self.needs['energy'] - (energy_decrease * 1.3))
                elif is_fitness_enthusiast:
                    self.needs['energy'] = max(0, self.needs['energy'] - (energy_decrease * 0.7))
                else:
                    self.needs['energy'] = max(0, self.needs['energy'] - energy_decrease)

        # Additional personality-based adjustments
        hour, _ = world_time
        
        # Lazy people get tired easier during the day
        if is_lazy and 14 <= hour <= 18:  # Afternoon fatigue
            self.needs['energy'] = max(0, self.needs['energy'] - 0.1)
            
        # Workaholics get energized during work hours
        if is_workaholic and 9 <= hour <= 17 and is_working:
            self.needs['energy'] = min(100, self.needs['energy'] + 0.05)
            
        # Social butterflies need more social interaction in the evening
        if is_social_butterfly and 18 <= hour <= 22:
            self.needs['social'] = min(100, self.needs['social'] + 0.2)
            
        # Fitness enthusiasts have better overall energy management
        if is_fitness_enthusiast:
            # Cap energy loss and maintain higher baseline
            self.needs['energy'] = max(20, self.needs['energy'])  # Never completely exhausted

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