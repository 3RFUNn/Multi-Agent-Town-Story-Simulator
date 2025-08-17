# behavior/behavior_tree.py
# Defines the core behavior tree node types and logic for agent decision-making.
# Includes Selector, Sequence, and StatefulSelector nodes, as well as simulation utilities.

from enum import Enum
import random

class SimulationSummary:
    """Encapsulates the predicted outcome of an action for planning and heuristics."""
    def __init__(self, final_needs, final_money):
        self.final_needs = final_needs
        self.final_money = final_money

def heuristic_function(agent, initial_summary, final_summary):
    """
    Scores the desirability of a simulated outcome based on changes in needs and money.
    Higher scores indicate more desirable outcomes.
    """
    score = 0
    for need, initial_value in initial_summary.final_needs.items():
        final_value = final_summary.final_needs.get(need, initial_value)
        change = initial_value - final_value
        weight = 1.5 if need in ['hunger', 'energy'] else 1.0
        score += change * weight

    money_change = final_summary.final_money - initial_summary.final_money
    score += money_change * 0.5
    normalized_score = 1 / (1 + max(0, -score))
    return normalized_score

class NodeStatus(Enum):
    """Represents the possible return statuses of a Behavior Tree node."""
    SUCCESS = 1
    FAILURE = 2
    RUNNING = 3

class Node:
    """Base class for all nodes in a Behavior Tree."""
    def __init__(self, name):
        self.name = name
        self.is_running = False

    def tick(self, agent, world_state):
        """
        Called every simulation tick. Must be implemented by subclasses.
        """
        raise NotImplementedError

    def simulate(self, agent, world_state, prev_summary):
        """
        Used for lookahead simulation. Must be implemented by subclasses.
        """
        raise NotImplementedError

    def reset(self):
        """Resets the state of the node."""
        self.is_running = False
        if hasattr(self, 'children'):
            for child in self.children:
                child.reset()

class Selector(Node):
    """
    Executes children in order until one succeeds. Used for high-priority, reactive checks.
    Stateless: re-evaluates from the first child every tick.
    """
    def __init__(self, name, children=None):
        super().__init__(name)
        self.children = children if children else []

    def tick(self, agent, world_state):
        for child in self.children:
            status = child.tick(agent, world_state)
            if status != NodeStatus.FAILURE:
                return status
        return NodeStatus.FAILURE

    def simulate(self, agent, world_state, prev_summary):
        for child in self.children:
            return child.simulate(agent, world_state, prev_summary)
        return prev_summary

class StatefulSelector(Node):
    """
    Commits to a chosen child branch and continues to tick it until it succeeds or fails.
    Uses a heuristic to select the best child branch for the agent.
    """
    def __init__(self, name, children=None):
        super().__init__(name)
        self.children = children if children else []
        self.selected_child = None

    def _select_best_child(self, agent, world_state):
        """Uses a heuristic to decide the best action to take."""
        best_child = None
        best_score = -1
        
        initial_summary = SimulationSummary(agent.needs.copy(), agent.money)

        for child in self.children:
            sim_summary = self.simulate_child(child, agent, world_state, initial_summary)
            score = heuristic_function(agent, initial_summary, sim_summary)

            if score > best_score:
                best_score = score
                best_child = child
        
        if best_child:
            agent.add_log(f"I've decided to: {best_child.name.replace('_', ' ')}. (Score: {best_score:.2f})", world_state['time'], world_state['day_of_week'])

        return best_child

    def simulate_child(self, child, agent, world_state, initial_summary):
        """Simulates a child node's execution to predict the outcome."""
        sim_agent = agent 
        
        final_needs = sim_agent.needs.copy()
        final_money = sim_agent.money

        if "socialize" in child.name.lower():
            final_needs['social'] = max(0, final_needs['social'] - 20)
        if "work" in child.name.lower():
            final_money += 10
        if "eat" in child.name.lower():
            final_needs['hunger'] = max(0, final_needs['hunger'] - 30)

        return SimulationSummary(final_needs, final_money)

    def tick(self, agent, world_state):
        if self.selected_child and self.selected_child.is_running:
            status = self.selected_child.tick(agent, world_state)
        else:
            self.selected_child = self._select_best_child(agent, world_state)
            if not self.selected_child:
                return NodeStatus.FAILURE
            status = self.selected_child.tick(agent, world_state)

        if status != NodeStatus.RUNNING:
            self.selected_child.reset()
            self.selected_child = None
            self.is_running = False
        else:
            self.is_running = True
            
        return status

    def simulate(self, agent, world_state, prev_summary):
        best_child = self._select_best_child(agent, world_state)
        if best_child:
            return best_child.simulate(agent, world_state, prev_summary)
        return prev_summary

    def reset(self):
        super().reset()
        self.selected_child = None

class Sequence(Node):
    """
    Executes children in order. Returns FAILURE as soon as a child fails.
    Returns SUCCESS if all children succeed. Handles RUNNING state.
    """
    def __init__(self, name, children=None):
        super().__init__(name)
        self.children = children if children else []
        self.current_child_index = 0

    def tick(self, agent, world_state):
        while self.current_child_index < len(self.children):
            child = self.children[self.current_child_index]
            status = child.tick(agent, world_state)

            if status == NodeStatus.SUCCESS:
                child.reset()
                self.current_child_index += 1
                continue
            
            if status == NodeStatus.FAILURE:
                self.reset()
                return NodeStatus.FAILURE
            
            if status == NodeStatus.RUNNING:
                self.is_running = True
                return NodeStatus.RUNNING
        
        self.reset()
        return NodeStatus.SUCCESS

    def simulate(self, agent, world_state, prev_summary):
        current_sim_summary = prev_summary
        for child in self.children:
            current_sim_summary = child.simulate(agent, world_state, current_sim_summary)
        return current_sim_summary

    def reset(self):
        super().reset()
        self.current_child_index = 0