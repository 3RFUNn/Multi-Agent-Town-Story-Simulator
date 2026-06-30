# MATSS v2 — Architecture

This document describes the **v2 engine** (`matss/`), the industry-scale rebuild
of the prototype, implemented directly from
[`PROJECT_SCALING_AND_RESEARCH_STRATEGY.md`](./PROJECT_SCALING_AND_RESEARCH_STRATEGY.md).
The original prototype (`app.py`, `command.py`, `simulation/`, `behavior/`,
`narrative_analyzer.py`) is preserved for reference.

## The one idea

> **Tier-1 control is deterministic and is the source of truth. Tier-2 narration
> is generative, strictly post-hoc, and never feeds back.**

v2 turns that thesis — which the prototype only *asserted* — into an enforced,
tested property: a run is **bit-reproducible** from `seed + content`, and the
**append-only event log is the canonical source of truth** that the LLM merely
sifts into prose.

## Hexagonal (ports & adapters) layout

The core depends only on **ports** (`matss/ports.py`), never on concrete
adapters. The default wiring is in-memory/offline (no API key, no network, no
infra) so the whole system runs and tests deterministically; each port has a
documented production adapter.

```
                       ┌───────────────────────────── matss.sim.SimulationEngine ─────────────────────────────┐
                       │  deterministic tick loop · composes every port · emits events + per-tick state_hash   │
                       └───────┬───────────────┬───────────────┬───────────────┬───────────────┬──────────────┘
            DecisionContext    │               │               │               │               │
        ┌──────────────────────▼──┐   ┌────────▼─────────┐  ┌──▼───────────┐  ┌─▼───────────┐  ┌▼──────────────┐
        │ matss.behavior          │   │ matss.pathfinding│  │ matss.memory │  │ matss.event │  │ matss.cognition│
        │ BT engine (Tier-1)      │   │ A* + flow-field  │  │ Park stream  │  │ log + bus   │  │ narrative+queue│
        │ real lookahead (C2)     │   │ cached planner   │  │ recency·imp· │  │ +projections│  │ +judge (C4)    │
        └─────────────────────────┘   └──────────────────┘  │ relevance    │  └──────┬──────┘  └───────┬────────┘
                                                             └──────┬───────┘         │                 │
                       ports.EmbeddingProvider / VectorStore ───────┘        ports.EventLog/Bus   ports.LLMProvider
                              │ mock (default) · OpenAI                  in-memory · JSONL          mock (default)
                              │ pgvector/Qdrant (prod)                   Kafka/Redpanda (prod)      Anthropic · OpenAI
                              ▼                                                                     router·cache·batch·retry
                       matss.app.gateway  (Console / Flask+SocketIO)  ── pure EventBus subscriber ──► clients
```

### Packages

| Package | Responsibility | Default adapter | Production adapter |
|---|---|---|---|
| `determinism` | seeded named RNG sub-streams + canonical `state_hash` | — | — |
| `domain` | pure model: `Event`, `Agent`, `WorldState`, `NavGrid`, `MemoryRecord` | — | — |
| `config` | data-driven, **validated** world content (`content/world.json`) | file | DB-backed content service |
| `behavior` | deterministic Behavior-Tree engine; real `simulate()` lookahead | — | — |
| `pathfinding` | A* + cached flow-fields on the static nav-grid | — | — |
| `memory` | Park-style recency+importance+relevance stream + reflection | mock embeddings + in-memory cosine store | OpenAI embeddings + pgvector/Qdrant |
| `cognition.llm` | provider-agnostic LLM stack: router, cache, batch, retry, structured | `MockLLMProvider` | `AnthropicProvider` / `OpenAIProvider` |
| `cognition` | post-hoc hierarchical narrative + cost model, bounded queue, LLM-judge | — | — |
| `eventlog` | append-only log (source of truth), bus, replay + CQRS projections | in-memory + JSONL | Kafka/Redpanda + projections |
| `observability` | structured logging, metrics, tracing | in-process | OTel/Prometheus exporters |
| `sim` | the engine + composition root (`build_engine`) | — | — |
| `app` | entrypoints (`runner`, `replay`) + transport gateway | console / Flask | — |

## The tick (Tier-1, deterministic)

`SimulationEngine.tick()`:

1. **advance the clock** (+`minutes_per_tick` simulated minutes; day rollover
   resets behavior trees);
2. **update schedules** (data-driven, sleep-aware, per personality);
3. **process agents** in a *seeded-shuffled but reproducible* order:
   - update needs; advance in-progress actions/interactions; pay wages at work;
   - tick idle agents' **behavior trees** (which set movement/action *intent*);
   - **resolve movement** with the planner (A*/flow-field), with claimed-cell
     contention handling and conversation initiation;
4. **emit** granular domain events to the bus + log, then one `TICK_COMPLETED`
   event carrying `{state_hash, snapshot}`.

Every stochastic draw flows through a named `RandomSource` sub-stream
(`agent:<id>:socialize`, `move:<id>`, `tick_order`, …), so reordering subsystems
can't perturb results. **No wall-clock, no global `random`, no reliance on dict
order.**

## Tier-2 (narration, post-hoc)

At the narrative hour the engine selects the **previous day's** memories by tick
range (avoiding weekday-name collisions), enqueues one diary job per agent on the
**bounded cognition queue** (drop-by-importance backpressure), writes diaries,
then compiles the town story (flat, or hierarchical agent→group→town). All output
is appended to the log as `DIARY_WRITTEN` / `STORY_COMPILED` events. **It never
mutates Tier-1 state**, which is exactly why a cognition backlog degrades
narrative richness without ever stalling — or perturbing the determinism of — the
simulation.

## Reproducibility certificate

```bash
# Run, persisting the event log:
python -m matss.app.runner --seed 123 --ticks 500 --jsonl run.jsonl

# Prove a fresh same-seed run reproduces the identical state-hash chain:
python -m matss.app.replay --jsonl run.jsonl --verify-seed 123
# -> "re-run seed=123 ticks=500: chain MATCHES the logged run"  (exit 0)
```

CI enforces this in `tests/test_integration_determinism.py` (the reproducibility
gate), alongside event-log replay equality and snapshot reconstruction.

## Mapping to the strategy report

| Report recommendation | Where it lives |
|---|---|
| #1 Provider-agnostic LLM: cache/batch/route/retry/structured | `cognition/llm/` |
| #2 Genuinely deterministic kernel (seed + state_hash chain + CI gate) | `determinism/`, `sim/engine.py`, CI |
| #3 Event-sourced log = source of truth + replay/CQRS | `eventlog/` |
| #4 Break `manager→app` cycle; tests/CI/observability | `app/gateway.py` (bus subscriber), `observability/`, `.github/` |
| #5 Park-style vector memory + reflection | `memory/` |
| #6 Cognition off the tick path (bounded queue, backpressure) | `cognition/queue.py`, `sim/engine.py` |
| #7 A*/flow-field pathfinding replacing per-move BFS | `pathfinding/` |
| #9 Data-driven, validated content (no hardcoded dicts) | `config/`, `content/world.json` |
| #10 LLM-as-judge + keep the analyzer | `cognition/judge.py`, legacy `narrative_analyzer.py` |
| Contribution **C2** real BT lookahead (no stub) | `behavior/tree.py` `StatefulSelector` |
| Contribution **C4** hierarchical narration + cost model | `cognition/narrative.py` |

## Deliberately out of scope (future work)

The report's later phases need infrastructure that cannot be stood up and tested
in a single offline session, and are therefore **not** implemented here (only the
seams for them exist): distributed sharding / Ray actors / out-of-order execution
(P2 #8); multi-tenant SaaS, OIDC/RBAC, secrets management, multi-AZ HA/DR (P3);
and the Godot/Unity game client (P4). The ports & adapters boundaries are drawn so
these slot in without touching the core.
