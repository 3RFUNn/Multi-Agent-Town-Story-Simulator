"""Tier 2 — generative cognition: the LLM provider stack + narrative synthesis.

Populated by:
* ``matss.cognition.llm`` — provider-agnostic LLM stack (mock + real adapters,
  router, caching, batching, structured outputs).
* ``matss.cognition.narrative`` / ``queue`` / ``judge`` — post-hoc narrative
  generation, the bounded cognition queue, and LLM-as-judge evaluation.

This subsystem is strictly post-hoc: it observes the Tier-1 event stream and
appends narrative events, but never mutates Tier-1 state.
"""

__all__ = []
