# behavior/agent_behaviors.py

from .behavior_tree import Node, NodeStatus, Selector, Sequence, StatefulSelector, SimulationSummary
import random

# --- Condition Nodes ---

class IsNeedCritical(Node):
    """Checks if a specific need has crossed a critical threshold."""
    def __init__(self, name, need, threshold):
        super().__init__(name)
        self.need = need
        self.threshold = threshold

    def tick(self, agent, world_state):
        if agent.needs.get(self.need, 0) >= self.threshold:
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE
    
    def simulate(self, agent, world_state, prev_summary):
        return prev_summary

class IsAgentTired(Node):
    """Specific and common check for the agent's energy level."""
    def __init__(self, name, threshold=75):
        super().__init__(name)
        self.threshold = threshold

    def tick(self, agent, world_state):
        if agent.needs['energy'] >= self.threshold:
            agent.add_log(f"I'm feeling quite tired (Energy Need: {agent.needs['energy']:.1f}). I should find a place to rest.", world_state['time'], world_state['day_of_week'])
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE

    def simulate(self, agent, world_state, prev_summary):
        return prev_summary

class IsScheduledActivity(Node):
    """Checks if the agent has a scheduled activity right now."""
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        return NodeStatus.SUCCESS if agent.current_activity else NodeStatus.FAILURE
        
    def simulate(self, agent, world_state, prev_summary):
        return prev_summary

class HasEnoughMoney(Node):
    """Checks if the agent can afford their current activity."""
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        activity_data = world_state['activity_data'].get(agent.current_activity)
        if not activity_data or agent.money >= activity_data['cost']:
            return NodeStatus.SUCCESS
        agent.add_log(f"I can't afford to {agent.current_activity.replace('_', ' ')}, I only have ${agent.money:.2f}.", world_state['time'], world_state['day_of_week'])
        return NodeStatus.FAILURE

    def simulate(self, agent, world_state, prev_summary):
        return prev_summary

class IsAtActivityLocation(Node):
    """Checks if the agent is at the correct location for their current activity."""
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        if not agent.current_activity:
            return NodeStatus.FAILURE
        
        if "home" in agent.current_activity:
            # Check if agent is at their specific home location
            home_locations = self._get_agent_home_locations(agent, world_state)
            is_at_home = (agent.x, agent.y) in home_locations
            return NodeStatus.SUCCESS if is_at_home else NodeStatus.FAILURE

        location_name = world_state['activity_data'][agent.current_activity]['location']
        target_location = world_state['places'].get(location_name)
        if not target_location:
            return NodeStatus.FAILURE
        
        is_at_location = (agent.x, agent.y) in target_location['coords']
        return NodeStatus.SUCCESS if is_at_location else NodeStatus.FAILURE

    def _get_agent_home_locations(self, agent, world_state):
        """Get the appropriate home location coords for the agent"""
        home_x, home_y = agent.home['x'], agent.home['y']
        
        # Map agent home positions to the correct place
        if home_x <= 5 and home_y <= 5:  # North houses
            return world_state['places']['north_houses']['coords']
        elif home_x <= 5 and 13 <= home_y <= 17:  # Central houses  
            return world_state['places']['central_houses']['coords']
        elif home_x <= 5 and home_y >= 18:  # South houses
            return world_state['places']['south_houses']['coords']
        elif home_x >= 18 and home_y <= 5:  # Student accommodation
            return world_state['places']['student_accommodation']['coords']
        else:
            # Fallback to exact position
            return [(home_x, home_y)]

    def simulate(self, agent, world_state, prev_summary):
        return prev_summary

class ShouldSocialize(Node):
    """Determines if an agent should seek social interaction based on personality and needs."""
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        social_need = agent.needs['social']
        talkativeness = agent.personality.get('talkativeness', 0.5)
        
        # Extroverts are more likely to socialize even with moderate need
        if 'extrovert' in agent.personality_names and social_need > 30 and random.random() < (0.4 * talkativeness):
            agent.add_log(f"I'm feeling social (Social need: {social_need:.1f}). Let me find someone to talk to.", world_state['time'], world_state['day_of_week'])
            return NodeStatus.SUCCESS
        # Introverts only socialize when their need is quite high
        if 'introvert' in agent.personality_names and social_need > 70 and random.random() < (0.3 * talkativeness):
            agent.add_log(f"I really need some social interaction (Social need: {social_need:.1f}). Maybe I should find someone to chat with.", world_state['time'], world_state['day_of_week'])
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE

    def simulate(self, agent, world_state, prev_summary):
        return prev_summary


# --- Action Nodes ---

class FindAgentToTalkTo(Node):
    """Finds a nearby agent and initiates movement to talk to them."""
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        # Find potential targets: nearby and idle.
        potential_targets = [
            other for other in world_state['agents'].values()
            if other.id != agent.id and
               abs(other.x - agent.x) < 6 and
               abs(other.y - agent.y) < 6 and
               other.state == 'idle'
        ]
        
        if not potential_targets:
            agent.add_log("I looked around but didn't see anyone available to chat with.", world_state['time'], world_state['day_of_week'])
            return NodeStatus.FAILURE

        # Prioritize talking to friends and people with good relationships
        friends = [t for t in potential_targets if agent.get_relationship(t.id) and agent.get_relationship(t.id)['affinity'] > 70]
        target_agent = random.choice(friends) if friends else random.choice(potential_targets)

        # Set the intent to interact and the destination for pathfinding
        agent.interacting_with = target_agent.id
        agent.destination_name = f"agent_{target_agent.id}"
        
        # Change state to moving
        agent.state = 'moving'
        agent.current_goal = f"Going to have a conversation with {target_agent.name}"
        
        relationship = agent.get_relationship(target_agent.id)
        relationship_type = relationship['type'] if relationship else "someone"
        agent.add_log(f"I spotted {target_agent.name} nearby. They're my {relationship_type}, so I'll go say hello.", world_state['time'], world_state['day_of_week'])

        return NodeStatus.SUCCESS
            
    def simulate(self, agent, world_state, prev_summary):
        # Simulating this action would decrease social need and a bit of energy
        final_needs = prev_summary.final_needs.copy()
        final_needs['social'] = max(0, final_needs['social'] - 40)
        final_needs['energy'] = max(0, final_needs['energy'] - 3)
        return SimulationSummary(final_needs, prev_summary.final_money)

class ExecuteActivity(Node):
    def __init__(self, name, duration=8):
        super().__init__(name)
        self.duration = duration

    def tick(self, agent, world_state):
        activity = agent.current_activity
        if not activity: 
            return NodeStatus.FAILURE

        activity_data = world_state['activity_data'].get(activity, {})
        cost = activity_data.get('cost', 0)

        if agent.money >= cost:
            agent.money -= cost
            agent.state = 'doing_action'
            agent.action_duration = self.duration
            
            # Create more descriptive and varied action text
            action_descriptions = self._get_action_description(activity)
            agent.current_action = action_descriptions['action']
            agent.current_goal = action_descriptions['goal']
            
            location = activity_data.get('location', 'my destination')
            agent.add_log(f"I've arrived at the {location.replace('_', ' ')}. {action_descriptions['log']}", world_state['time'], world_state['day_of_week'])
            
            # Update needs based on activity type with more realistic values
            self._update_needs_for_activity(agent, activity)
            
            return NodeStatus.RUNNING # Action takes time
        return NodeStatus.FAILURE

    def _get_action_description(self, activity):
        """Generate descriptive text for different activities"""
        descriptions = {
            # Work activities
            "work_at_office": {
                "action": "Working on projects and attending meetings",
                "goal": "Being productive and advancing my career",
                "log": "Time to focus on my work tasks and be productive."
            },
            "morning_shift_at_cafe": {
                "action": "Serving customers and preparing drinks",
                "goal": "Providing excellent customer service",
                "log": "Starting my morning shift, ready to serve customers with a smile."
            },
            "overtime_work_at_office": {
                "action": "Working late on important projects",
                "goal": "Finishing urgent tasks and deadlines",
                "log": "Staying late to finish these important projects."
            },
            
            # Gym activities
            "morning_workout_at_gym": {
                "action": "Doing cardio and strength training",
                "goal": "Building strength and staying healthy",
                "log": "Time for my morning workout routine to start the day right."
            },
            "evening_workout_at_gym": {
                "action": "Weight training and fitness exercises",
                "goal": "Maintaining my fitness and relieving stress",
                "log": "Perfect time for my evening workout to unwind."
            },
            
            # Social activities
            "socialize_at_park": {
                "action": "Enjoying time outdoors and meeting people",
                "goal": "Relaxing and connecting with others",
                "log": "What a nice day to spend some time in the park."
            },
            "drinks_at_bar": {
                "action": "Having drinks and socializing",
                "goal": "Unwinding and enjoying nightlife",
                "log": "Time to relax and enjoy some drinks with friends."
            },
            
            # Food activities
            "lunch_break_at_cafe": {
                "action": "Having lunch and taking a break",
                "goal": "Refueling and taking a mental break",
                "log": "Perfect time for a lunch break to recharge."
            },
            "dinner_at_cafe": {
                "action": "Enjoying a nice dinner",
                "goal": "Having a satisfying meal",
                "log": "Looking forward to a delicious dinner."
            },
            
            # Study activities
            "morning_classes_at_college": {
                "action": "Attending lectures and taking notes",
                "goal": "Learning and advancing my education",
                "log": "Time for my morning classes, ready to learn."
            },
            "study_at_college": {
                "action": "Studying and doing homework",
                "goal": "Mastering my coursework",
                "log": "Need to focus on my studies and get caught up."
            },
        }
        
        # Default description for activities not specifically defined
        default = {
            "action": activity.replace('_', ' ').title(),
            "goal": f"Completing my {activity.replace('_', ' ')} activity",
            "log": f"Time to {activity.replace('_', ' ')}."
        }
        
        return descriptions.get(activity, default)

    def _update_needs_for_activity(self, agent, activity):
        """Update agent needs based on the specific activity"""
        if "eat" in activity or "lunch" in activity or "dinner" in activity or "breakfast" in activity:
            agent.needs['hunger'] = max(0, agent.needs['hunger'] - 50)
        elif "coffee" in activity:
            agent.needs['hunger'] = max(0, agent.needs['hunger'] - 15)
            agent.needs['energy'] = max(0, agent.needs['energy'] - 15) # Coffee reduces tiredness
        
        if "socialize" in activity or "drinks" in activity or "party" in activity:
            agent.needs['social'] = max(0, agent.needs['social'] - 60)
        
        if "workout" in activity or "gym" in activity or "training" in activity:
            agent.needs['energy'] = min(100, agent.needs['energy'] + 5) # Workout increases tiredness significantly
            # Fitness enthusiasts get a mood boost from exercise
            if 'fitness_enthusiast' in agent.personality_names:
                agent.needs['social'] = max(0, agent.needs['social'] - 10)
        
        if "relax" in activity or "leisure" in activity or "park" in activity:
            agent.needs['energy'] = max(0, agent.needs['energy'] - 25) # Relaxing reduces tiredness
        
        if "sleep" in activity:
            agent.needs['energy'] = max(0, agent.needs['energy'] - 90) # Sleeping greatly reduces tiredness

    def simulate(self, agent, world_state, prev_summary):
        final_needs = prev_summary.final_needs.copy()
        final_money = prev_summary.final_money
        
        activity = agent.current_activity
        activity_data = world_state['activity_data'].get(activity, {})
        final_money -= activity_data.get('cost', 0)

        # Simulate need changes
        if "eat" in activity or "lunch" in activity or "dinner" in activity:
            final_needs['hunger'] = max(0, final_needs['hunger'] - 50)
        if "socialize" in activity or "drinks" in activity:
            final_needs['social'] = max(0, final_needs['social'] - 60)
        if "workout" in activity or "gym" in activity:
            final_needs['energy'] = min(100, final_needs['energy'] + 5)
        if "relax" in activity or "park" in activity:
            final_needs['energy'] = max(0, final_needs['energy'] - 25)
        if "sleep" in activity:
            final_needs['energy'] = max(0, final_needs['energy'] - 90)

        return SimulationSummary(final_needs, final_money)

class PlanPathToActivityLocation(Node):
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        activity = agent.current_activity
        if not activity: 
            return NodeStatus.FAILURE
        
        if "home" in activity or "sleep" in activity:
            agent.destination_name = f"{agent.id}_home"
            agent.current_goal = "Heading home to rest and recharge"
            agent.add_log(f"Time to head home. I need to {activity.replace('_', ' ')}.", world_state['time'], world_state['day_of_week'])
        else:
            location_name = world_state['activity_data'][activity]['location']
            agent.destination_name = location_name
            
            # Create more descriptive goals based on activity
            activity_goals = {
                "work_at_office": "Going to work to be productive",
                "morning_classes_at_college": "Heading to college for my morning classes",
                "workout_at_gym": "Going to the gym for my workout session",
                "lunch_break_at_cafe": "Going to the cafe for lunch",
                "socialize_at_park": "Going to the park to relax and socialize",
                "drinks_at_bar": "Heading to the bar for drinks",
                "grocery_shopping": "Going shopping for groceries"
            }
            
            agent.current_goal = activity_goals.get(activity, f"Going to {location_name.replace('_', ' ')} to {activity.replace('_', ' ')}")
            agent.add_log(f"According to my schedule, it's time to {activity.replace('_', ' ')}. Let me head over to {location_name.replace('_', ' ')}.", world_state['time'], world_state['day_of_week'])
        
        agent.state = 'moving'
        return NodeStatus.SUCCESS

    def simulate(self, agent, world_state, prev_summary):
        final_needs = prev_summary.final_needs.copy()
        final_needs['energy'] = min(100, final_needs['energy'] + 2) # Pathfinding increases tiredness
        return SimulationSummary(final_needs, prev_summary.final_money)

class PlanPathToHome(Node):
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        agent.destination_name = f"{agent.id}_home"
        agent.state = 'moving'
        agent.current_goal = "Going home to get some sleep"
        agent.add_log("I'm completely drained. I need to get home immediately and get some rest.", world_state['time'], world_state['day_of_week'])
        return NodeStatus.SUCCESS

    def simulate(self, agent, world_state, prev_summary):
        final_needs = prev_summary.final_needs.copy()
        final_needs['energy'] = min(100, final_needs['energy'] + 2) # Pathfinding increases tiredness
        return SimulationSummary(final_needs, prev_summary.final_money)

class PlanPathToRestLocation(Node):
    """Plans a path to a location to rest, like a park or cafe."""
    def __init__(self, name):
        super().__init__(name)
        self.rest_locations = ['central_park', 'downtown_cafe']

    def tick(self, agent, world_state):
        # Find a nearby rest location
        chosen_location = random.choice(self.rest_locations)
        agent.destination_name = chosen_location
        agent.state = 'moving'
        agent.current_goal = f"Going to the {chosen_location.replace('_', ' ')} to rest for a bit"
        
        # Set a temporary activity that will be executed upon arrival
        agent.current_activity = "take_a_short_rest"
        world_state['activity_data']['take_a_short_rest'] = {
            "location": chosen_location,
            "cost": 0
        }

        agent.add_log(f"I'm feeling tired, so I'll head to the {chosen_location.replace('_', ' ')} to recharge.", world_state['time'], world_state['day_of_week'])
        return NodeStatus.SUCCESS

    def simulate(self, agent, world_state, prev_summary):
        final_needs = prev_summary.final_needs.copy()
        final_needs['energy'] = min(100, final_needs['energy'] + 2) # Pathfinding cost
        return SimulationSummary(final_needs, prev_summary.final_money)

class ExecuteRest(Node):
    """A specific action for the agent to rest and recover energy."""
    def __init__(self, name, duration=10):
        super().__init__(name)
        self.duration = duration

    def tick(self, agent, world_state):
        agent.state = 'doing_action'
        agent.action_duration = self.duration
        agent.current_action = "Taking a short break to recharge"
        agent.current_goal = "Resting to regain some energy"
        agent.add_log("Ah, much better. Taking a moment to rest here.", world_state['time'], world_state['day_of_week'])
        
        # Significantly decrease energy need
        agent.needs['energy'] = max(0, agent.needs['energy'] - 70)
        
        # Clear the temporary activity
        agent.current_activity = None

        return NodeStatus.RUNNING

    def simulate(self, agent, world_state, prev_summary):
        final_needs = prev_summary.final_needs.copy()
        final_needs['energy'] = max(0, final_needs['energy'] - 70)
        return SimulationSummary(final_needs, prev_summary.final_money)

class Idle(Node):
    """The default state if no other action is taken."""
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        # Create more varied idle behaviors based on personality
        if 'lazy' in agent.personality_names:
            agent.current_goal = "Taking it easy and enjoying some downtime"
            agent.current_action = "Lounging around and relaxing"
        elif 'curious' in agent.personality_names:
            agent.current_goal = "Looking around and observing my surroundings"
            agent.current_action = "Exploring and being curious"
        elif 'social_butterfly' in agent.personality_names:
            agent.current_goal = "Looking for interesting people to meet"
            agent.current_action = "Scanning for social opportunities"
        else:
            agent.current_goal = "Taking a moment to think and plan"
            agent.current_action = "Contemplating my next move"
        
        return NodeStatus.SUCCESS

    def simulate(self, agent, world_state, prev_summary):
        return prev_summary

# --- Behavior Tree Construction ---
def create_agent_bt(agent, world_state):
    """
    Creates the complete, hierarchical Behavior Tree for an agent.
    Enhanced structure with better reactivity and personality-driven decisions.
    """

    # --- Level 4: Default & Social Behaviors (Lowest Priority) ---
    free_time_branch = StatefulSelector("Free Time Activities", children=[
        Sequence("Try to socialize", children=[
            ShouldSocialize("Should I socialize?"),
            FindAgentToTalkTo("Find someone to talk to")
        ]),
        Idle("Default idle behavior")
    ])

    # --- Level 3: Scheduled Activities ---
    scheduled_activity_branch = Sequence("Follow My Schedule", children=[
        IsScheduledActivity("Do I have a scheduled activity?"),
        HasEnoughMoney("Can I afford this activity?"),
        Selector("Execute or Move to Activity", children=[
            Sequence("I'm already here, so do the activity", children=[
                IsAtActivityLocation("Am I at the right location?"),
                ExecuteActivity("Execute the scheduled activity")
            ]),
            # If not at the location, plan path there
            PlanPathToActivityLocation("Go to the activity location")
        ])
    ])
    
    # --- Level 2: Core Behavior (Stateful Selector) ---
    core_behavior_branch = StatefulSelector(f"Core Daily Routine for {agent.name}", children=[
        scheduled_activity_branch,
        free_time_branch,
    ])

    # --- Level 1: Critical Needs & Reactions (Highest Priority Selector) ---
    root = Selector(f"Behavior Tree Root for {agent.name}", children=[
        # --- Emergency Reactions First ---
        Sequence("Emergency: Go Home When Exhausted", children=[
            IsAgentTired("Am I completely exhausted?", threshold=95),
            PlanPathToHome("Emergency path home")
        ]),
        # --- Urgent, but not critical reactions ---
        Sequence("Urgent: Rest when tired", children=[
            IsAgentTired("Am I tired?", threshold=70),
            Selector("Rest Behavior", children=[
                Sequence("I am at a rest location", children=[
                    IsAtActivityLocation("Am I at the rest spot?"),
                    ExecuteRest("Take a short rest")
                ]),
                PlanPathToRestLocation("Find a place to rest")
            ])
        ]),
        Sequence("Critical: Find Food When Starving", children=[
            IsNeedCritical("Am I starving?", 'hunger', threshold=85),
            # This could trigger an emergency food-finding behavior
        ]),
        
        # --- Then, execute normal behavior ---
        core_behavior_branch
    ])

    return root