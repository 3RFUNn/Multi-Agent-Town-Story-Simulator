"""Memory records — the unit of the Park-style memory stream.

Defined in the domain (not the memory adapter) so that the narrative subsystem
can depend on the *record* + a retriever Protocol without importing the concrete
memory implementation. This keeps modules decoupled and independently testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryRecord:
    """A single memory: an observation or a higher-level reflection.

    ``importance`` is Park et al.'s poignancy score (1-10). ``last_accessed_tick``
    drives recency decay. ``embedding`` is filled lazily by the memory stream.
    """

    id: str
    agent_id: str
    text: str
    tick: int
    day: str
    importance: float = 1.0
    created_seq: int = 0
    last_accessed_tick: int = 0
    kind: str = "observation"  # "observation" | "reflection"
    related_agents: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "text": self.text,
            "tick": self.tick,
            "day": self.day,
            "importance": self.importance,
            "created_seq": self.created_seq,
            "last_accessed_tick": self.last_accessed_tick,
            "kind": self.kind,
            "related_agents": list(self.related_agents),
            "metadata": dict(self.metadata),
        }
