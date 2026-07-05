# DRAFT — sections 3-7 (audit table + research inserted later)

## 3. V2.0 Architecture Design

### Design thesis
V1's core insight — deterministic BT control + post-hoc LLM narration — is sound and is the thing worth publishing. V2 does not abandon it; it (a) repairs the BT layer so the "hybrid" claim is actually true (the utility machinery is currently dead code), (b) makes the LLM layer production-grade and asynchronous, and (c) adds a *bounded feedback channel* from LLM reflection back into behavior — the "mixed-initiative" upgrade the README's own future-work section calls for. That bounded feedback loop is the publishable novelty.

### Process model: one process, not two
V1 splits Flask server (app.py) and sim client (command.py) across two processes connected by SocketIO — which is the direct cause of the lost daily stories. V2 collapses to a single asyncio process:

```
┌────────────────────────────── townsim (single process, asyncio) ──────────────────────────────┐
│                                                                                                │
│  ┌───────────────┐   tick events   ┌──────────────┐    validated feedback    ┌──────────────┐  │
│  │ SIMULATION    │ ──────────────▶ │ EVENT BUS /  │ ◀──────────────────────  │ COGNITION    │  │
│  │ KERNEL        │                 │ JOURNAL      │                          │ WORKERS      │  │
│  │ fixed timestep│ ◀────────────── │ (append-only │ ───────────────────────▶ │ (async LLM:  │  │
│  │ seeded RNG    │  intents        │  JSONL)      │   day-end, encounters    │  diaries,    │  │
│  │ systems:      │                 └──────┬───────┘                          │  reflection, │  │
│  │  Schedule     │                        │                                  │  dialogue,   │  │
│  │  Needs        │                        ▼                                  │  story)      │  │
│  │  Behavior(BT) │                 ┌──────────────┐                          └──────┬───────┘  │
│  │  Movement     │                 │ WORLD STATE  │                                 │          │
│  │  Interaction  │                 │ single source│                          ┌──────▼───────┐  │
│  │  Economy      │                 │ of truth +   │                          │ LLM GATEWAY  │  │
│  └───────────────┘                 │ snapshots    │                          │ provider-    │  │
│         │                          └──────────────┘                          │ agnostic,    │  │
│         ▼                                                                    │ retry, cache,│  │
│  ┌───────────────┐   WebSocket (delta updates)   ┌────────────────┐          │ rate-limit   │  │
│  │ FastAPI       │ ────────────────────────────▶ │ Browser        │          └──────────────┘  │
│  │ + WS broadcast│ ◀──────────────────────────── │ dashboard      │                             │
│  └───────────────┘    pause/resume/inspect       └────────────────┘                             │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Key properties:
- The kernel never awaits an LLM call. Cognition workers consume events from the bus and post results back as *typed intents* that the kernel applies at tick boundaries.
- Every state change is an event in the journal → any run is replayable bit-for-bit (seeded RNG + journal = deterministic reproduction).
- The browser is a pure view; it can disconnect/reconnect without touching sim state.

### Layered module layout

```
townsim/
  kernel/        # clock, scheduler, event bus, journal, snapshots, RNG
  world/         # WorldState, places, grid, spatial hash, pathfinding (A*)
  agents/        # components: Needs, Wallet, Personality, ScheduleState, SocialGraph
  behavior/      # BT runtime (py_trees), UtilitySelector, node library, blackboards
  cognition/     # memory stream, retrieval, reflection, dialogue, narrative
  llm/           # gateway: providers, prompt templates, schemas, semantic cache
  server/        # FastAPI app, WS hub, REST for replay/inspection
  config/        # pydantic-settings models + YAML defaults
  cli.py         # run / replay / analyze entrypoints
tests/
prompts/         # versioned Jinja2 templates (diary_v2.j2, reflect_v1.j2, ...)
```

### Behavior layer: BT + Utility hybrid (fixed)
- Adopt py_trees for the composite/decorator machinery (correct RUNNING semantics, tree visualization/introspection for the dashboard). The README already claims py_trees — V2 makes that claim true.
- Replace `StatefulSelector` with a real `UtilitySelector`: scores each child with a proper utility function (need pressure × personality weights × schedule pressure), sorts, tries children in descending utility WITH fallback on failure, commits while RUNNING. This fixes the three dead-selection bugs (flat heuristic, name-keyword simulate, no fallback) in one move.
- Blackboards with three scopes: agent-local (rest_location, path, current intent), group (conversation state shared by participants), world (time, weather, occupancy). Kills the `world_state['activity_data']` mutation class of bugs and the ad-hoc attributes sprinkled on Agent.
- All action nodes get a location-guard idiom: `Selector[Sequence[IsAt(target), Do(action)], GoTo(target)]` — applied uniformly (V1's food branch skips it; the rest branch checks the wrong target).

### Cognition layer: memory, reflection, bounded feedback
Generative-Agents-inspired but BT-grounded:
- **Episodic memory**: every event with (sim_day_index, tick, location, participants, importance). Importance scored by cheap heuristics first (relationship delta, novelty, rarity) with optional LLM scoring for candidates. Keyed by day_index (fixes the week-2 diary-pollution bug).
- **Retrieval**: score = α·recency + β·importance + γ·relevance (embedding cosine — finally using the currently-dead get_embedding path). Used to build diary prompts and dialogue context.
- **Reflection (nightly)**: LLM reads the day's retrieved highlights → produces a *typed, validated* ReflectionResult (Pydantic): mood, 1-3 goal-weight adjustments, 0-2 schedule proposals ("invite Bella to the cafe on Saturday"). The kernel applies only what validates and only within bounds (weights clamped, proposals checked against the schedule grammar). This is the bounded feedback channel: open-ended cognition, guaranteed-safe behavior.
- **Hierarchical summarization**: day memories → daily summary → weekly summary; prompts always reference summaries + retrieved episodes, never the raw unbounded stream. Token cost per agent-day becomes O(1), not O(t).

### Social & narrative layer
- Relationship model per dyad: familiarity, affinity, valence(last-interaction), updated by interaction events with decay; feeds both utility scores (whom to approach) and prompt context (how to talk about them).
- Conversations: salient encounters (first meeting, big affinity delta, story-beat candidates) get a real multi-turn LLM dialogue (budget-capped per day); mundane encounters get templated exchanges. Transcripts summarize into both agents' memories.
- Emergent event detection: rule triggers (conflict, milestone, streak, first-X) nominate story beats; a nightly LLM pass over the journal picks the day's beats; the town-story prompt is built around beats + diary excerpts. Directly attacks the weak diary↔story cohesion the README measured (mean TF-IDF similarity 0.149).

### Simulation kernel
- Fixed-timestep loop with accumulator (sim minutes per tick from config), wall-clock-independent; headless fast-forward mode for experiments (no sleep).
- Seeded `random.Random` instances per subsystem (kernel, behavior, narrative sampling) — reproducible runs; seed logged in the journal header.
- WorldState as the single source of truth; periodic snapshots + journal events → replay CLI reconstructs any run; golden-replay test in CI.
- Spatial hash (uniform grid buckets) for proximity queries; A* with heapq; both O(1)-ish per query at hundreds of agents.
- ECS-lite via esper in Phase C if agent count is scaled for the paper's scalability section; component dataclasses from day one so migration is mechanical.

## 4. Upgrade Roadmap (draft — final effort numbers after audit merge)

### Phase A — Correctness & survivability (goal: the current feature set, but true) ~1.5-2 wks
A1 requirements.txt + pinned deps; A2 fix daily-story delivery (route via client channel);
A3 LLM timeout+retry (tenacity)+never-kill-loop; A4 narrative generation to background thread;
A5 fix food branch structure + rest-location check + shared activity_data; A6 overnight schedule windows;
A7 memory day_index keying + pruning; A8 utility heuristic + UtilitySelector fallback; A9 ShouldSocialize default case;
A10 seeded RNG; A11 escape LLM text in frontend (textContent) ; A12 pytest suite + FakeLLM + CI; A13 logging→structlog.

### Phase B — Core V2 architecture ~3-5 wks
B1 single-process FastAPI+asyncio port; B2 WorldState+journal+replay; B3 config system (pydantic-settings+YAML);
B4 blackboard scopes; B5 BT on py_trees + UtilitySelector; B6 memory stream + retrieval + reflection (bounded feedback);
B7 prompt template system (Jinja2, versioned) + Pydantic structured outputs; B8 provider abstraction + semantic cache;
B9 relationship dynamics; B10 delta WS updates + dashboard v2 (BT introspection, relationship graph, diary panel).

### Phase C — Showcase & research ~4-6 wks
C1 conversation system; C2 emergent event detection/story beats; C3 dynamic schedule generation from reflections;
C4 scalability: spatial hash + esper + 100-500 agent benchmark; C5 (optional) procedural town blocks;
C6 evaluation harness (metrics battery + ablations BT-only/LLM-only/hybrid); C7 packaging, demo video, docs site.

## 5. Technology Stack (justifications in final)
fastapi+uvicorn; python-socketio (async server) OR native WS; pydantic v2 + pydantic-settings + PyYAML; openai SDK behind a thin Protocol + litellm option; tenacity; jinja2; py_trees; esper (Phase C); numpy; structlog; pytest+pytest-asyncio+hypothesis; ruff+mypy; sqlite (semantic cache + journal index).

## 7. Code samples to write
S1 async LLM gateway (protocol, adapter, retries, semaphore, semantic cache, structured output)
S2 BT core: Node contract + UtilitySelector (fallback + real utilities)
S3 scoped Blackboard
S4 memory stream + retrieval + reflection schema
S5 fixed-timestep kernel + journal (short)
S6 wrap-around schedule window fix (micro-diff)
