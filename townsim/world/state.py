"""WorldState: the single source of truth for the simulation.

Owns the map, all agents, the spatial index, conversations, and target-cell
reservations. Everything the systems and behavior trees read or mutate goes
through here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from townsim.agents.agent import AgentState
from townsim.world.grid import TownMap
from townsim.world.spatial import SpatialHash

Coord = tuple[int, int]


@dataclass
class Conversation:
    id: str
    a: str
    b: str
    remaining_ticks: int
    started_tick: int
    location: str | None = None
    salient: bool = False


@dataclass
class WorldState:
    town: TownMap
    agents: dict[str, AgentState] = field(default_factory=dict)
    spatial: SpatialHash = field(default_factory=SpatialHash)
    conversations: dict[str, Conversation] = field(default_factory=dict)
    reservations: dict[Coord, str] = field(default_factory=dict)   # target cell -> agent id
    conversation_requests: list[tuple[str, str]] = field(default_factory=list)
    stories: list[dict] = field(default_factory=list)
    _conversation_seq: int = 0

    # ---- agents ----------------------------------------------------------
    def add_agent(self, agent: AgentState) -> None:
        self.agents[agent.id] = agent
        self.spatial.upsert(agent.id, agent.pos)

    def move_agent(self, agent: AgentState, pos: Coord) -> None:
        agent.x, agent.y = pos
        self.spatial.upsert(agent.id, pos)

    def agents_sorted(self) -> list[AgentState]:
        return [self.agents[k] for k in sorted(self.agents)]

    # ---- geometry --------------------------------------------------------
    def resolve_place_coords(self, place_key: str, agent: AgentState) -> tuple[Coord, ...]:
        """Resolve 'home' to the agent's own home place (F40)."""
        key = agent.spec.home_place if place_key == "home" else place_key
        return self.town.place_coords(key)

    def occupied_cells(self, *, exclude: str | None = None) -> set[Coord]:
        cells = set()
        for a in self.agents.values():
            if a.id != exclude:
                cells.add(a.pos)
        return cells

    def free_cells_in(self, coords: tuple[Coord, ...], *, for_agent: str) -> list[Coord]:
        """Cells in a place not occupied and not reserved by someone else."""
        occupied = self.occupied_cells(exclude=for_agent)
        return [c for c in coords
                if c not in occupied
                and self.reservations.get(c, for_agent) == for_agent]

    def reserve(self, cell: Coord, agent_id: str) -> None:
        self.reservations[cell] = agent_id

    def release_reservations(self, agent_id: str) -> None:
        stale = [c for c, owner in self.reservations.items() if owner == agent_id]
        for c in stale:
            del self.reservations[c]

    def is_at_place(self, agent: AgentState, place_key: str) -> bool:
        return agent.pos in self.resolve_place_coords(place_key, agent)

    def chebyshev(self, a: Coord, b: Coord) -> int:
        return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

    # ---- conversations -----------------------------------------------------
    def new_conversation(self, a: str, b: str, duration: int, tick: int,
                         location: str | None, salient: bool) -> Conversation:
        self._conversation_seq += 1
        conv = Conversation(id=f"c{self._conversation_seq}", a=a, b=b,
                            remaining_ticks=duration, started_tick=tick,
                            location=location, salient=salient)
        self.conversations[conv.id] = conv
        return conv

    # ---- snapshots ---------------------------------------------------------
    def snapshot(self, time_dict: dict) -> dict:
        return {
            "time": time_dict,
            "agents": [a.to_public_dict() for a in self.agents_sorted()],
            "conversations": [
                {"id": c.id, "a": c.a, "b": c.b, "remaining": c.remaining_ticks}
                for c in self.conversations.values()
            ],
        }
