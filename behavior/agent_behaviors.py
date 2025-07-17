# behavior/agent_behaviors.py

from .behavior_tree import Node, NodeStatus, Selector, Sequence
import random

# --- Condition Nodes ---

class IsNeedCritical(Node):
    def __init__(self, name, need, threshold):
        super().__init__(name)
        self.need = need
        self.threshold = threshold

    def tick(self, agent, world_state):
        if agent.needs.get(self.need, 0) >= self.threshold:
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE

class IsAgentTired(Node):
    def __init__(self, name, threshold=20):
        super().__init__(name)
        self.threshold = threshold

    def tick(self, agent, world_state):
        if agent.needs['energy'] < self.threshold:
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE

class IsScheduledActivity(Node):
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        if agent.current_activity:
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE

class HasEnoughMoney(Node):
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        activity_data = world_state['activity_data'].get(agent.current_activity)
        if not activity_data or agent.money >= activity_data['cost']:
            return NodeStatus.SUCCESS
        agent.add_log(f"I can't afford to {agent.current_activity.replace('_', ' ')}, I only have ${agent.money}.", world_state['time'])
        return NodeStatus.FAILURE

class IsAtActivityLocation(Node):
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        if not agent.current_activity:
            return NodeStatus.FAILURE
        
        if "home" in agent.current_activity:
            return NodeStatus.SUCCESS if (agent.x, agent.y) == (agent.home['x'], agent.home['y']) else NodeStatus.FAILURE

        location_name = world_state['activity_data'][agent.current_activity]['location']
        target_location = world_state['places'].get(location_name)
        if not target_location:
            return NodeStatus.FAILURE
        
        return NodeStatus.SUCCESS if (agent.x, agent.y) in target_location['coords'] else NodeStatus.FAILURE

class ShouldSocialize(Node):
    """Determines if an agent should seek social interaction based on personality and needs."""
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        social_need = agent.needs['social']
        # Extroverts are more likely to socialize even with low need
        if agent.personality == 'extrovert' and social_need > 40 and random.random() < 0.3:
            return NodeStatus.SUCCESS
        # Introverts only socialize when their need is high
        if agent.personality == 'introvert' and social_need > 80 and random.random() < 0.5:
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE

# --- Action Nodes ---

class FindAgentToTalkTo(Node):
    """Finds a nearby agent and initiates an interaction."""
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        nearby_agents = [other for other in world_state['agents'].values() if other.id != agent.id and abs(other.x - agent.x) < 5 and abs(other.y - agent.y) < 5 and not other.interacting_with]
        
        if nearby_agents:
            target_agent = random.choice(nearby_agents)
            agent.interacting_with = target_agent.id
            target_agent.interacting_with = agent.id # Both agents are now busy
            
            agent.state = 'interacting'
            target_agent.state = 'interacting'

            agent.add_log(f"I see {target_agent.name} nearby, I'll go say hello.", world_state['time'])
            target_agent.add_log(f"{agent.name} is coming over to talk to me.", world_state['time'])
            
            agent.current_goal = f"Chatting with {target_agent.name}"
            target_agent.current_goal = f"Chatting with {agent.name}"
            
            agent.action_duration = 10 # Interaction lasts for 10 ticks
            target_agent.action_duration = 10
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE

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
            
            agent.add_log(f"I've arrived. Now I'm starting to {activity.replace('_', ' ')}.", world_state['time'])
            
            if "eat" in activity: agent.needs['hunger'] = max(0, agent.needs['hunger'] - 60)
            if "socialize" in activity or "hang_out" in activity: agent.needs['social'] = max(0, agent.needs['social'] - 70)
            if "relax" in activity or "sleep" in activity: agent.needs['energy'] = min(100, agent.needs['energy'] + 80)
            
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE

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
        
        agent.add_log(f"My schedule says it's time to {activity.replace('_', ' ')}. I should head over.", world_state['time'])
        agent.state = 'moving'
        return NodeStatus.SUCCESS

class PlanPathToHome(Node):
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        agent.destination_name = f"{agent.id}_home"
        agent.state = 'moving'
        agent.current_goal = "Going home to rest"
        agent.add_log("I'm exhausted. I need to go home and get some sleep.", world_state['time'])
        return NodeStatus.SUCCESS

class Idle(Node):
    """The default state if no other action is taken."""
    def __init__(self, name):
        super().__init__(name)

    def tick(self, agent, world_state):
        agent.current_goal = "Wandering and thinking"
        agent.current_action = "Looking around"
        return NodeStatus.SUCCESS

# --- Behavior Tree Construction ---
def create_agent_bt(agent, world_state):
    """Creates the complete, hierarchical Behavior Tree for an agent."""

    # --- Level 4: Default Behavior ---
    idle_behavior = Idle("Idle")

    # --- Level 3: Proactive Socializing ---
    proactive_social_behavior = Sequence("Proactive Socializing", children=[
        ShouldSocialize("Do I feel like talking to someone?"),
        FindAgentToTalkTo("Find someone to talk to")
    ])

    # --- Level 2: Scheduled Activities ---
    # This is the agent's main "day job".
    scheduled_activity_branch = Sequence("Scheduled Activity Branch", children=[
        IsScheduledActivity("Is it time for an activity?"),
        HasEnoughMoney("Can I afford this?"),
        Selector("Perform or Move to Activity", children=[
            Sequence("Already at location, so perform action", children=[
                IsAtActivityLocation("Am I at the right place?"),
                ExecuteActivity("Do the activity")
            ]),
            # If not at the location, this will run
            PlanPathToActivityLocation("Plan path to activity location")
        ])
    ])
    
    # --- Level 1: Critical Needs ---
    # This branch will interrupt any other behavior if a need is critical.
    critical_needs_branch = Selector("Critical Needs Branch", children=[
        Sequence("Go Home When Exhausted", children=[
            IsAgentTired("Am I exhausted?", threshold=10),
            PlanPathToHome("Plan path home")
        ]),
        # Add more critical needs here, like finding food when starving.
    ])

    # --- Level 0: Root Selector ---
    # The root tries each branch in order of priority.
    root = Selector(f"BT Root for {agent.name}", children=[
        critical_needs_branch,
        proactive_social_behavior,
        scheduled_activity_branch,
        idle_behavior
    ])

    return root
