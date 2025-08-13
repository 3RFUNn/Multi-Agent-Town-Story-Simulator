# simulation/memory/memory.py

import datetime

class Memory:
    """
    Represents a single memory entry for an agent.
    """
    def __init__(self, event, timestamp=None, related_agents=None, details=None):
        self.event = event
        self.timestamp = timestamp or datetime.datetime.now().isoformat()
        self.related_agents = related_agents or []
        self.details = details or {}

    def to_dict(self):
        return {
            'event': self.event,
            'timestamp': self.timestamp,
            'related_agents': self.related_agents,
            'details': self.details
        }

class AgentMemoryStream:
    """
    Stores all memories for an agent, including relationships, daily activities, and notable events.
    """
    def __init__(self):
        self.memories = []

    def add_memory(self, memory):
        self.memories.append(memory)

    def get_memories_for_day(self, day):
        return [m for m in self.memories if m.timestamp.startswith(day)]

    def reset_daily_memories(self, day):
        self.memories = [m for m in self.memories if not m.timestamp.startswith(day)]

    def to_dict(self):
        return [m.to_dict() for m in self.memories]
