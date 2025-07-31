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
    def __init__(self, name, threshold=20):
        super().__init__(name)
        self.threshold = threshold

    def tick(self, agent, world_state):
        if agent.needs['energy'] <= self.threshold:
            agent.add_log(f"I'm exhausted (Energy: {agent.needs['energy']:.1f}). I must go home to rest.", world_state['time'], world_state['day_of_week'])
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
        # In simulation, assume they can afford it for now
        return prev_summary

class IsAtActivityLocation(Node):
    """Checks if the agent is at the correct location for their current activity."""
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        if not agent.current_activity:
            return NodeStatus.FAILURE
        
        if "home" in agent.current_activity:
            is_at_home = (agent.x, agent.y) == (agent.home['x'], agent.home['y'])
            return NodeStatus.SUCCESS if is_at_home else NodeStatus.FAILURE

        location_name = world_state['activity_data'][agent.current_activity]['location']
        target_location = world_state['places'].get(location_name)
        if not target_location:
            return NodeStatus.FAILURE
        
        is_at_location = (agent.x, agent.y) in target_location['coords']
        return NodeStatus.SUCCESS if is_at_location else NodeStatus.FAILURE

    def simulate(self, agent, world_state, prev_summary):
        return prev_summary

class ShouldSocialize(Node):
    """Determines if an agent should seek social interaction based on personality and needs."""
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        social_need = agent.needs['social']
        talkativeness = agent.personality.get('talkativeness', 0.5)
        
        # Extroverts are more likely to socialize even with low need
        if 'extrovert' in agent.personality_names and social_need > 40 and random.random() < (0.3 * talkativeness):
            return NodeStatus.SUCCESS
        # Introverts only socialize when their need is high
        if 'introvert' in agent.personality_names and social_need > 80 and random.random() < (0.5 * talkativeness):
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
               abs(other.x - agent.x) < 5 and
               abs(other.y - agent.y) < 5 and
               other.state == 'idle'
        ]
        
        if not potential_targets:
            return NodeStatus.FAILURE

        # Prioritize talking to friends
        friends = [t for t in potential_targets if agent.get_relationship(t.id) and agent.get_relationship(t.id)['type'] == 'friend']
        target_agent = random.choice(friends) if friends else random.choice(potential_targets)

        # Set the intent to interact and the destination for pathfinding
        agent.interacting_with = target_agent.id
        agent.destination_name = f"agent_{target_agent.id}"
        
        # Change state to moving
        agent.state = 'moving'
        agent.current_goal = f"Going to talk to {target_agent.name}"
        agent.add_log(f"I see {target_agent.name} nearby, I'll go say hello. Reason: Social need is {agent.needs['social']:.1f}", world_state['time'], world_state['day_of_week'])

        return NodeStatus.SUCCESS
            
    def simulate(self, agent, world_state, prev_summary):
        # Simulating this action would decrease social need and maybe energy
        final_needs = prev_summary.final_needs.copy()
        final_needs['social'] = max(0, final_needs['social'] - 50)
        final_needs['energy'] = max(0, final_needs['energy'] - 5)
        return SimulationSummary(final_needs, prev_summary.final_money)


class ExecuteActivity(Node):
    def __init__(self, name, duration=5):
        super().__init__(name)
        self.duration = duration

    def tick(self, agent, world_state):
        activity = agent.current_activity
        if not activity: return NodeStatus.FAILURE

        activity_data = world_state['activity_data'].get(activity, {})
        cost = activity_data.get('cost', 0)

        if agent.money >= cost:
            agent.money -= cost
            agent.state = 'doing_action'
            agent.action_duration = self.duration
            agent.current_action = activity.replace("_", " ").title()
            
            agent.add_log(f"I've arrived at {activity_data.get('location', 'my destination')}. Now I'm starting to {activity.replace('_', ' ')}.", world_state['time'], world_state['day_of_week'])
            
            # Update needs based on activity
            if "eat" in activity: agent.needs['hunger'] = max(0, agent.needs['hunger'] - 60)
            if "socialize" in activity or "hang_out" in activity: agent.needs['social'] = max(0, agent.needs['social'] - 70)
            if "relax" in activity or "read" in activity: agent.needs['energy'] = min(100, agent.needs['energy'] + 10)
            if "sleep" in activity: agent.needs['energy'] = min(100, agent.needs['energy'] + 80)
            
            return NodeStatus.RUNNING # Action takes time
        return NodeStatus.FAILURE

    def simulate(self, agent, world_state, prev_summary):
        # This action is complex; a full simulation would be needed.
        # For now, we'll estimate the effects.
        final_needs = prev_summary.final_needs.copy()
        final_money = prev_summary.final_money
        
        activity = agent.current_activity
        activity_data = world_state['activity_data'].get(activity, {})
        final_money -= activity_data.get('cost', 0)

        if "eat" in activity: final_needs['hunger'] = max(0, final_needs['hunger'] - 60)
        if "socialize" in activity: final_needs['social'] = max(0, final_needs['social'] - 70)
        if "sleep" in activity: final_needs['energy'] = min(100, final_needs['energy'] + 80)

        return SimulationSummary(final_needs, final_money)

class PlanPathToActivityLocation(Node):
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        activity = agent.current_activity
        if not activity: return NodeStatus.FAILURE
        
        if "home" in activity or "sleep" in activity:
            agent.destination_name = f"{agent.id}_home"
            agent.current_goal = "Heading home"
        else:
            location_name = world_state['activity_data'][activity]['location']
            agent.destination_name = location_name
            agent.current_goal = f"Heading to the {location_name.replace('_', ' ').title()} to {activity.replace('_', ' ')}"
        
        agent.add_log(f"My schedule says it's time to {activity.replace('_', ' ')}. I should head over.", world_state['time'], world_state['day_of_week'])
        agent.state = 'moving'
        return NodeStatus.SUCCESS

    def simulate(self, agent, world_state, prev_summary):
        # Pathfinding itself consumes a bit of energy
        final_needs = prev_summary.final_needs.copy()
        final_needs['energy'] = max(0, final_needs['energy'] - 2)
        return SimulationSummary(final_needs, prev_summary.final_money)

class PlanPathToHome(Node):
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        agent.destination_name = f"{agent.id}_home"
        agent.state = 'moving'
        agent.current_goal = "Going home to rest"
        agent.add_log("I'm exhausted. I need to go home and get some sleep.", world_state['time'], world_state['day_of_week'])
        return NodeStatus.SUCCESS

    def simulate(self, agent, world_state, prev_summary):
        final_needs = prev_summary.final_needs.copy()
        final_needs['energy'] = max(0, final_needs['energy'] - 2)
        return SimulationSummary(final_needs, prev_summary.final_money)

class Idle(Node):
    """The default state if no other action is taken."""
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        agent.current_goal = "Wandering and thinking"
        agent.current_action = "Looking around"
        return NodeStatus.SUCCESS

    def simulate(self, agent, world_state, prev_summary):
        return prev_summary

# --- Behavior Tree Construction ---
def create_agent_bt(agent, world_state):
    """
    Creates the complete, hierarchical Behavior Tree for an agent.
    This new structure prioritizes reactivity, then critical needs, then scheduled activities,
    and finally falls back to idle or social behavior.
    """

    # --- Level 4: Default & Social Behaviors (Lowest Priority) ---
    free_time_branch = StatefulSelector("Free Time Activities", children=[
        FindAgentToTalkTo("Find someone to talk to"),
        Idle("Idle")
    ])

    # --- Level 3: Scheduled Activities ---
    # This is the agent's main "day job".
    scheduled_activity_branch = Sequence("Follow Schedule", children=[
        IsScheduledActivity("Is it time for an activity?"),
        HasEnoughMoney("Can I afford it?"),
        Selector("Perform or Move to Activity", children=[
            Sequence("Already at location, so perform action", children=[
                IsAtActivityLocation("Am I at the right place?"),
                ExecuteActivity("Do the activity")
            ]),
            # If not at the location, this will run
            PlanPathToActivityLocation("Plan path to activity location")
        ])
    ])
    
    # --- Level 2: Core Behavior (Stateful Selector) ---
    # The agent commits to a high-level goal (schedule or free time).
    core_behavior_branch = StatefulSelector(f"Core Behavior for {agent.name}", children=[
        scheduled_activity_branch,
        free_time_branch,
    ])

    # --- Level 1: Critical Needs & Reactions (Highest Priority Selector) ---
    # This branch uses a stateless Selector to allow for immediate reactions.
    # It will interrupt any other behavior if a need is critical.
    root = Selector(f"BT Root for {agent.name}", children=[
        # --- Reactivity First ---
        Sequence("Go Home When Exhausted", children=[
            IsAgentTired("Am I exhausted?", threshold=10),
            PlanPathToHome("Plan path home")
        ]),
        Sequence("Go Eat When Starving", children=[
            IsNeedCritical("Am I starving?", 'hunger', threshold=90),
            # This would ideally have a "find food" action, but for now, we log it.
            # In the future, this could trigger a dynamic replan to go to a cafe.
        ]),
        
        # --- Then, execute the core behavior ---
        core_behavior_branch
    ])

    return root