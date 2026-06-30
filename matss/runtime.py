"""Shared runtime types that cross module boundaries.

``DecisionContext`` is the sandbox a Behavior-Tree node executes inside. The
simulation engine constructs it per agent per tick, binding the event-emit and
observation callbacks to the current tick/time so nodes never touch wall-clock,
global state, or the transport layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict

from .determinism.rng import RandomSource
from .domain.agent import Agent
from .domain.world import WorldState

if TYPE_CHECKING:  # avoid importing the config package at runtime here
    from .config.loader import Content

# emit(event_type, **payload) -> records a domain Event for ctx.agent.
EmitFn = Callable[..., None]
# observe(text) -> records an agent observation (becomes a memory + log line).
ObserveFn = Callable[[str], None]


@dataclass
class DecisionContext:
    """Everything a behavior node may legitimately touch — and nothing else."""

    agent: Agent
    world: "WorldState"
    content: "Content"
    rng: RandomSource
    emit: EmitFn
    observe: ObserveFn

    @property
    def params(self) -> Dict[str, Any]:
        """Tunable simulation parameters (from content ``sim_params``)."""
        return self.content.sim_params

    def rng_stream(self, name: str):
        """A per-agent, per-purpose deterministic RNG sub-stream."""
        return self.rng.stream(f"agent:{self.agent.id}:{name}")
