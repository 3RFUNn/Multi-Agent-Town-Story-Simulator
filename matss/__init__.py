"""MATSS v2 — Multi-Agent Town Story Simulator.

A deterministic, event-sourced generative-agent engine with a strictly
decoupled, post-hoc LLM narrative layer.

Architecture (ports & adapters / hexagonal):

    matss.domain        Pure domain model (agents, events, world) — no I/O.
    matss.determinism   Seeded RNG + canonical state hashing (reproducibility).
    matss.behavior      Deterministic Behavior-Tree engine (Tier 1 control).
    matss.pathfinding   A* + flow-field pathing on the static nav-grid.
    matss.memory        Park-style recency+importance+relevance memory stream.
    matss.eventlog      Append-only event log = canonical source of truth.
    matss.cognition     Tier 2: async narrative generation + LLM provider stack.
    matss.config        Data-driven, validated content (no hardcoded dicts).
    matss.observability Structured logging, metrics, tracing.
    matss.sim           The engine: deterministic tick loop composing the ports.
    matss.app           Entrypoints + the web gateway adapter.

The CORE (everything except matss.app's web gateway and the real LLM/embedding
provider adapters) is stdlib-only and runs fully offline.
"""

__version__ = "2.0.0"

__all__ = ["__version__"]
