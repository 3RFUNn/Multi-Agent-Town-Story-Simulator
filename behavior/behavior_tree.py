# behavior/behavior_tree.py

from enum import Enum
import random

# A data structure to encapsulate the predicted outcome of an action.
# This will be used by the heuristic planning system later, but we define it here.
class SimulationSummary:
    def __init__(self, final_needs, final_money):
        self.final_needs = final_needs
        self.final_money = final_money

# Function to score the desirability of a simulated outcome.
# We define this here to be used by the StatefulSelector.
def heuristic_function(agent, initial_summary, final_summary):
    score = 0
    # Higher score for fulfilling needs
    for need, initial_value in initial_summary.final_needs.items():
        final_value = final_summary.final_needs.get(need, initial_value)
        change = initial_value - final_value  # Positive change is good (need decreased)
        
        # Weight needs differently, e.g., hunger and energy are more critical
        weight = 1.5 if need in ['hunger', 'energy'] else 1.0
        score += change * weight

    # Higher score for gaining money
    money_change = final_summary.final_money - initial_summary.final_money
    score += money_change * 0.5 # Weight money gain

    # Normalize score to be between 0 and 1 for simplicity
    normalized_score = 1 / (1 + max(0, -score)) # Simple sigmoid-like normalization
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
        This method is called every simulation tick.
        It must be implemented by all subclasses.
        """
        raise NotImplementedError

    def simulate(self, agent, world_state, prev_summary):
        """
        This method is used for the lookahead simulation.
        It must be implemented by all subclasses.
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
    A Selector node ('?') executes its children in order until one succeeds.
    It is 'stateless' and re-evaluates from the first child on every tick.
    Ideal for high-priority, reactive checks.
    """
    def __init__(self, name, children=None):
        super().__init__(name)
        self.children = children if children else []

    def tick(self, agent, world_state):
        for child in self.children:
            status = child.tick(agent, world_state)
            if status != NodeStatus.FAILURE:
                # If a child is RUNNING or SUCCEEDS, the selector returns that status
                return status
        # All children failed
        return NodeStatus.FAILURE

    def simulate(self, agent, world_state, prev_summary):
        # This is a stateless selector, so simulation is tricky.
        # For now, we assume the first successful simulation path is taken.
        for child in self.children:
            # In a real scenario, we might check if a simulated path is viable
            return child.simulate(agent, world_state, prev_summary)
        return prev_summary

class StatefulSelector(Node):
    """
    A stateful selector commits to a chosen child branch and continues to tick it
    until it succeeds or fails. It only re-evaluates its choice when it is not
    already running a child. This prevents the agent from "changing its mind" every tick.
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
        # This is a simplified simulation for the heuristic.
        # A full implementation would involve deeper state cloning.
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
        # The selector itself doesn't change the state, its children do.
        best_child = self._select_best_child(agent, world_state)
        if best_child:
            return best_child.simulate(agent, world_state, prev_summary)
        return prev_summary

    def reset(self):
        super().reset()
        self.selected_child = None

class Sequence(Node):
    """
    A Sequence node ('->') executes its children in order.
    It returns FAILURE as soon as a child fails.
    If all children succeed, it returns SUCCESS.
    It is now stateful and correctly handles the RUNNING state.
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
                child.reset() # Reset successful child before moving to the next
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
            # Pass the result of the previous simulation to the next
            current_sim_summary = child.simulate(agent, world_state, current_sim_summary)
        return current_sim_summary

    def reset(self):
        super().reset()
        self.current_child_index = 0