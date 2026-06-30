"""Application layer: entrypoints + transport adapters (the only non-core code).

* ``matss.app.gateway``  — transport adapters that SUBSCRIBE to the event bus
  (console sink + optional Flask/SocketIO web gateway). The simulation core
  publishes events to the bus; gateways consume them. This one-way flow is what
  breaks the prototype's ``manager -> app`` import cycle.
* ``matss.app.runner``   — headless deterministic run entrypoint (offline).
* ``matss.app.replay``   — replay a persisted event log and verify determinism.
"""

__all__ = []
