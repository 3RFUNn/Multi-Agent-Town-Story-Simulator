# behavior/behavior_tree.py

from enum import Enum

class NodeStatus(Enum):
    """Represents the possible return statuses of a Behavior Tree node."""
    SUCCESS = 1
    FAILURE = 2
    RUNNING = 3

class Node:
    """Base class for all nodes in a Behavior Tree."""
    def __init__(self, name):
        self.name = name

    def tick(self, agent, world_state):
        """
        This method is called every simulation tick.
        It must be implemented by all subclasses.
        """
        raise NotImplementedError

class Selector(Node):
    """
    A Selector node ('?') executes its children in order until one succeeds.
    It returns SUCCESS as soon as a child succeeds.
    If all children fail, it returns FAILURE.
    It's used for decision-making and prioritization.
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

class Sequence(Node):
    """
    A Sequence node ('->') executes its children in order.
    It returns FAILURE as soon as a child fails.
    If all children succeed, it returns SUCCESS.
    It's used for executing a series of tasks.
    """
    def __init__(self, name, children=None):
        super().__init__(name)
        self.children = children if children else []

    def tick(self, agent, world_state):
        for child in self.children:
            status = child.tick(agent, world_state)
            if status != NodeStatus.SUCCESS:
                # If a child is RUNNING or FAILS, the sequence returns that status
                return status
        # All children succeeded
        return NodeStatus.SUCCESS