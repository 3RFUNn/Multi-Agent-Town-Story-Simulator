# behavior/agent_behaviors.py

from .behavior_tree import Node, NodeStatus, Selector, Sequence

# --- Condition Nodes ---
class IsNeedAbove(Node):
    def __init__(self, name, need_name, threshold):
        super().__init__(name)
        self.need_name = need_name
        self.threshold = threshold

    def tick(self, agent, world_state):
        return NodeStatus.SUCCESS if agent.needs.get(self.need_name, 0) > self.threshold else NodeStatus.FAILURE

class IsAtLocation(Node):
    # *** FIX: Checks if the agent is at ANY of the coordinates for the location. ***
    def __init__(self, name, location_name):
        super().__init__(name)
        self.location_name = location_name

    def tick(self, agent, world_state):
        target_location = world_state['places'].get(self.location_name)
        if not target_location:
            return NodeStatus.FAILURE
        
        agent_pos = (agent.x, agent.y)
        if agent_pos in target_location['coords']:
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE

# --- Action Nodes ---
class SetGoal(Node):
    def __init__(self, name, goal_text):
        super().__init__(name)
        self.goal_text = goal_text

    def tick(self, agent, world_state):
        agent.current_goal = self.goal_text
        return NodeStatus.SUCCESS

class PlanPathToLocation(Node):
    def __init__(self, name, location_name):
        super().__init__(name)
        self.location_name = location_name

    def tick(self, agent, world_state):
        # This action now simply sets the name of the destination.
        # The manager will handle picking a specific, unoccupied coordinate.
        agent.destination_name = self.location_name
        agent.state = 'moving'
        agent.current_action = f"Walking to {self.location_name.replace('_', ' ').title()}"
        return NodeStatus.SUCCESS

class DoAction(Node):
    def __init__(self, name, action_text, duration):
        super().__init__(name)
        self.action_text = action_text
        self.duration = duration

    def tick(self, agent, world_state):
        agent.current_action = self.action_text
        agent.state = 'doing_action'
        agent.action_duration = self.duration
        agent.needs['hunger'] -= 20 # Eating reduces hunger
        agent.needs['hunger'] = max(0, agent.needs['hunger'])
        return NodeStatus.SUCCESS

# --- Behavior Tree Construction ---
def create_agent_bt(agent, world_state):
    """Creates and returns the root node of an agent's Behavior Tree."""

    hunger_plan = Sequence(name="Satisfy Hunger Plan", children=[
        SetGoal(name="Set Goal to Eat", goal_text="Getting something to eat"),
        PlanPathToLocation(name="Path to Cafe", location_name="cafe_hobbs"),
    ])
    
    at_cafe_plan = Sequence(name="At Cafe Plan", children=[
        IsAtLocation(name="Is at Cafe?", location_name="cafe_hobbs"),
        DoAction(name="Eat Food", action_text="Eating at the cafe", duration=3)
    ])

    root = Selector(name=f"BT Root for {agent.name}", children=[
        at_cafe_plan,
        Sequence(name="Hunger Check", children=[
            IsNeedAbove(name="Is Hungry?", need_name="hunger", threshold=80),
            hunger_plan
        ]),
        Sequence(name="Default Wander", children=[
            SetGoal(name="Set Goal to Wander", goal_text="Wandering to the park"),
            PlanPathToLocation(name="Path to Park", location_name="johnson_park"),
        ])
    ])
    return root
