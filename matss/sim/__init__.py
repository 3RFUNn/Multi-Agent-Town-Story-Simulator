"""The simulation engine: the deterministic, event-sourced tick loop.

``SimulationEngine`` composes every subsystem (behavior trees, pathfinding,
memory, the LLM narrative stack, the event log/bus) into one reproducible Tier-1
loop. ``build_engine`` is the composition root that wires sensible offline
defaults (mock LLM, in-memory log) so a full run works with zero external
dependencies, while any port can be swapped for a production adapter.
"""

from .engine import SimulationEngine, EngineConfig
from .builder import build_engine

__all__ = ["SimulationEngine", "EngineConfig", "build_engine"]
