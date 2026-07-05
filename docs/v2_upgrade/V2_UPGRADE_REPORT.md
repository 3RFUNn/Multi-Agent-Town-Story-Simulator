# Multi-Agent Town Story Simulator — V2.0 Audit & Upgrade Report

**Date:** 2026-07-03 · **Scope:** full codebase (~3,900 lines) · **Method:** line-by-line lead review + 5 parallel dimension-focused audit agents, findings deduplicated and every finding adversarially verified against the code (46 CONFIRMED, 7 CONFIRMED-with-corrections, 0 refuted), plus a web-research pass verifying every citation, venue, metric, and library recommendation.

---

## 1. Executive Summary

The project's core architectural thesis — deterministic Behavior-Tree control generating a factual event log, with an LLM confined to post-hoc narrative cognition — is sound, genuinely differentiated from the Generative-Agents lineage, and worth building V2.0 around. The prototype demonstrably runs and produces 14 days of coherent narrative output. However, the audit confirmed **53 defects (6 Critical, 20 Major, 27 Minor)**, and they cluster exactly where the project's claims are strongest. The flagship "BT/planner hybrid" selection mechanism is behaviorally dead code: the heuristic maps every non-negative outcome to exactly 1.0, the lookahead never calls the per-node `simulate()` methods, and the `StatefulSelector` never falls back on failure — so agent decision-making today is plain fixed-priority selection, not the hybrid the README describes. The narrative pipeline — the system's *raison d'être* — is its most fragile subsystem: daily stories are silently lost to a cross-process SocketIO emit and have never reached the browser; a single transient LLM error at the nightly 03:00 generation burst permanently kills the simulation; LLM calls have no timeout; restarts silently overwrite all previous runs' diaries; and a log-flooding bug drowns real events out of the memory stream that feeds the diaries. A confirmed economy bug re-charges the full activity cost every ~8 ticks, bankrupting every agent within the first simulated day.

The V2.0 design keeps the thesis and repairs the machinery. Architecturally: collapse the two-process split into a single asyncio process (FastAPI + WebSocket) so an entire class of cross-process bugs disappears; introduce a fixed-timestep, seeded, journaled simulation kernel whose runs are bit-for-bit replayable; rebuild the behavior layer on py_trees with a real `UtilitySelector` (making the README's existing py_trees claim true); replace ad-hoc shared-dict mutation with a three-scope blackboard; and upgrade agent cognition to a Generative-Agents-grade memory stream (episodic entries keyed by absolute day, retrieval scored by recency × importance × relevance, nightly reflection, hierarchical summarization) with one crucial addition — reflection feeds back into behavior **only through a typed, bounded, validated channel** (clamped goal-weight adjustments and grammar-checked schedule proposals). The LLM layer becomes production-grade: async gateway with retries/timeouts/rate-limit handling, versioned prompt templates, Pydantic-validated structured outputs, semantic caching, and provider abstraction.

Academically, the defensible contribution is the **inverted control-flow hybrid**: every surveyed system (Generative Agents, AI Town, Project Sid, AgentSociety) keeps LLM inference in the per-decision loop; this system removes it entirely and gains three things none of them have — bit-identical reproducibility, orders-of-magnitude lower cost per agent-day, and a symbolic ground-truth log against which every generated narrative sentence can be audited (a hallucination-rate metric for emergent narrative that pure-LLM systems *cannot compute*, because their "ground truth" is itself LLM output). With the Phase A–C roadmap below (~10–14 person-weeks total), the system becomes simultaneously showcase-ready, commercially credible, and publishable at AIIDE/CoG/FDG-class venues.

---

## 2. Audit Report

Every finding below was adversarially verified against the code by an independent agent instructed to refute it. Severities reflect post-verification corrections (three findings were downgraded Major→Minor). Full mechanism descriptions and verification justifications: `docs/v2_upgrade/findings_verified.json`.

### Critical (6)

| ID | Location | Issue | Recommended Fix |
|----|----------|-------|-----------------|
| F01 | `command.py:66-78` | Catch-all `except Exception: break` in the tick loop permanently kills the simulation on the first error. Exposure is guaranteed: every sim day (~4.8 real minutes) the 03:00 tick makes 7 unguarded LLM calls; any 429/5xx/connection error rides `raise_for_status()` straight into the `break`. All in-memory state (clock, needs, money, memories) is lost and runs restart at Monday day 1. | Log-and-continue per tick; wrap each diary/story call in its own try/except; put retries around LLM calls so they never propagate into the loop. |
| F02 | `simulation/llm_handler.py:33,51` | LLM requests have **no timeout** (while `check_llm_api` passes `timeout=10`, the real calls omit it), no retry/backoff, no 429 handling. A stalled connection freezes the single-threaded simulation forever — silently. | `timeout=(10, 120)` on generation; tenacity exponential backoff honoring `Retry-After` on 429/5xx; structured error returns. |
| F03 | `simulation/manager.py:356-366` | Seven synchronous `max_tokens=2048` LLM calls (6 diaries + 1 story) inside `tick()` at 03:00 stall the 0.4 s loop for minutes every sim day; the frontend and sim clock freeze. | Move narrative generation to a background worker fed by a day-end event; never call the LLM from the tick path. |
| F04 | `simulation/manager.py:366` + `app.py:39-41` | Daily stories never reach the browser: `emit_daily_story` fires on a **second, never-started SocketIO server object** imported into the command.py process (zero clients). The frontend's `new_daily_story` listener has never received an event. State updates only work because they go through the socketio *client*. | Emit stories through the same client channel with a server rebroadcast handler; or configure a message queue; or (V2) collapse to a single process. |
| F05 | `behavior/agent_behaviors.py:625-629` | Food-emergency branch teleport-eats: `Sequence[IsNeedCritical, PlanPathToEatLocation, ExecuteEat]` runs in one tick — `ExecuteEat` overwrites `state='moving'` with `'doing_action'`, hunger −70 wherever the agent stands, and the $10 cost is never deducted. The agent never travels. | Use the location-guard idiom (as the rest branch structurally does): `Selector[Sequence[IsAtEatLocation, ExecuteEat], GoToEatLocation]`; deduct cost in `ExecuteEat`. |
| F06 | `README.md:87-92` + repo root | Fresh install per README cannot run: `requests` (imported by `llm_handler`) and the `python-socketio` client (imported by `command.py`) are not in the install instructions, and **no `requirements.txt`/`pyproject.toml`/lockfile exists anywhere**. | Add pinned `requirements.txt` (or `pyproject.toml` with `sim`/`analysis` extras) covering all runtime + analysis deps. |

### Major (20)

| ID | Location | Issue | Recommended Fix |
|----|----------|-------|-----------------|
| F07 | `behavior/behavior_tree.py:129-145` | `StatefulSelector` never falls back to a sibling when the selected child FAILs — combined with F08's universal tie, the free-time `Idle` branch is unreachable and agents can dead-tick doing nothing. | Proper utility-selector semantics: try children in descending utility, fall through on FAILURE. |
| F08 | `behavior/behavior_tree.py:14-29` | `heuristic_function` returns `1/(1+max(0,-score))` — exactly **1.0 for every non-negative outcome**. With strict `>` comparison, selection degenerates to fixed first-child priority. The "utility" layer decides nothing. | Order-preserving scoring for positive outcomes (raw score or sigmoid); add tests asserting selection varies with state. |
| F09 | `behavior/behavior_tree.py:113-127` | `simulate_child` never calls `child.simulate()`; it substring-matches child *names* for "socialize/work/eat" — and the real children are named "Follow My Schedule"/"Free Time Activities", which match nothing. The entire lookahead subsystem (all per-node `simulate()` methods) is behaviorally dead. | Call `child.simulate(agent, world_state, initial_summary)`; delete or exercise the dead per-node implementations. |
| F11 | `behavior/agent_behaviors.py:615-623` | Rest branch checks the location of `current_activity` (scheduler-owned), not the chosen rest spot: agents at work "nap" instantly at the office (energy −70, silently cancelling their work activity); otherwise they can pace without ever resting. | Dedicated `IsAtRestLocation` reading the agent's own `rest_location`; don't clear `current_activity` as a side effect. |
| F13 | `behavior/agent_behaviors.py:244-247` + `manager.py:225-235` | Full activity cost re-charged every ~8 ticks within the same schedule slot: a 2-hour $20 dinner is charged 6–7× ($120–140) against $100–150 starting money — **agents go broke on day 1**, then `HasEnoughMoney` blocks their schedules; arrival logs spam all night. | Charge once per schedule slot (track last-paid slot), or set `action_duration` to span the remaining window; suppress repeat arrival logs. |
| F15 | `simulation/manager.py:87-91` | The 22:00 force-idle for `socialize_at_park` runs before the state guard and clears state/activity but **not** the mutual `interacting_with` or `path` — later, any completed walk triggers a spurious cross-town interaction that hijacks sleeping/walking partners. | A single `break_interaction()` helper that symmetrically clears state, `interacting_with`, durations, and paths on both agents; call it from all teardown paths. |
| F16 | `simulation/manager.py:327-340` | Arrival-triggered interaction never re-checks that the target is still nearby; the target keeps moving during the walk. If idle again on arrival, both agents are frozen "chatting" from arbitrary distances — visibly broken in the UI. | Verify adjacency (Chebyshev ≤ 2) on arrival; else replan toward the new position or abandon cleanly. |
| F17 | `simulation/manager.py:104-108` | Overnight windows like `(22,1)` can never satisfy `start <= hour < end` — `party_at_bar` and all wrap-around schedule entries are silently dead config. | `start<=h<end if start<end else h>=start or h<end`; property-test all templates. |
| F18 | `simulation/memory/memory.py:36-40` | Memory streams grow unbounded (`reset_daily_memories` never called; `reset_agent_diaries` is a no-op) and timestamps are bare weekday names — on day 8, `get_memories_for_day('Monday')` returns day-1 **and** day-8 memories: diaries mix weeks and prompt tokens grow without bound. | Key memories by absolute `day_index`; prune/summarize after diary generation. |
| F19 | `behavior/behavior_tree.py:109` | `_select_best_child` logs "I've decided to…" on essentially **every idle tick** (the BT is re-ticked and fully re-selected after every action/movement reset). Hundreds of identical entries push real events out of the 50-entry log and flood the memory stream that feeds the LLM diaries. | Log only on selection *change*; rate-limit/dedupe consecutive identical entries in `add_log`. |
| F20 | `behavior/agent_behaviors.py:460-463,510-513` | Per-agent rest/eat targets are written into the **shared global** `ACTIVITY_DATA` dict via `world_state` — concurrent resters clobber each other, so agent A is validated against agent B's rest spot. | Per-agent transient state on the agent/blackboard, never in shared world config. |
| F21 | `behavior/agent_behaviors.py:114-126` | `ShouldSocialize` only fires for `'extrovert'` or `'introvert'` trait names — Diana (agreeable/conscientious/fitness_enthusiast) can never voluntarily socialize; her free-time branch is dead. | Drive the check from numeric social need × talkativeness, with trait modifiers, not trait-name string matching. |
| F22 | `simulation/manager.py:288-322` | Blocked-path replanning handles home/place destinations but not `agent_<id>` targets: two agents walking toward each other stall indefinitely, spamming logs/memories every tick. | Handle `agent_` targets in replanning (recompute adjacent spot) + a give-up counter. |
| F23 | `simulation/entities.py:39` et al. | No RNG seeding anywhere (money init, tick-order shuffles, partner/target choices, durations) — **no run is reproducible**, contradicting the project's determinism/research-artifact positioning. | Injected `random.Random(seed)` instances per subsystem; log the seed in every run header. |
| F24 | `simulation/narrative/narrative_system.py:38-42,67-69` | Outputs keyed only by day number and opened `'w'`; the sim always restarts at day 1 → **every restart silently overwrites the previous run's diaries and stories** — the system's only durable artifact. | Namespace outputs per run (`daily_stories/run_<timestamp>/day_<n>/`), or persist and resume `day_index`. |
| F25 | `static/script.js:39-44,317` + `app.py:53-56` | Pause/Resume is permanently disabled in the README's documented startup order: `command_client_ready` is broadcast exactly once when command.py connects; a browser opened afterward never receives it. | Track engine-ready state server-side and send it to each newly connected client; also treat the first state update as proof-of-readiness. |
| F26 | `static/script.js:137-139` | `updateAgentAvatar` dereferences null on every agent's *first* state update (`createAgentAvatar` returns nothing; `agentDiv` never reassigned) — N uncaught TypeErrors per page load, aborting that tick's roster/inspector rendering. | `if (!agentDiv) agentDiv = createAgentAvatar(agent);` (return the created element). |
| F27 | `static/script.js:64,240-252` | Full roster/inspector DOM rebuild every 0.4 s tick: buttons destroyed between mousedown and mouseup swallow clicks; needs-bar CSS transitions never animate; log re-joined 2.5×/s. | Rebuild only when the agent set changes; targeted mutations (`style.width`, `textContent`, append-only log). |
| F28 | `README.md:150-156` | README describes a py_trees architecture with `QueryRAG`/`FollowPath`/`PickUpItem` nodes that **do not exist anywhere in the code** — a documentation-integrity risk fatal in academic review. | Rewrite to match the actual implementation (or make it true — V2 adopts py_trees). |
| F29 | repo root | No dependency manifest, no lockfile, no tests, no CI — nothing between the code and silent regression. | `pyproject.toml` + pytest suite + GitHub Actions (lint, typecheck, tests, smoke run). |

### Minor (27)

| ID | Location | Issue | Recommended Fix |
|----|----------|-------|-----------------|
| F10 | `behavior/behavior_tree.py:49-81` | `simulate()`/`is_running` machinery is inconsistent dead code (`Selector.simulate` returns after child[0]; leaves never set `is_running`); one unreset path (post-force-idle) lets a stale RUNNING branch resume and skip condition re-checks. | Set `is_running` on every RUNNING return; define real selector-simulation semantics or delete the dead machinery. |
| F12 | `behavior/agent_behaviors.py:610-613` | Latent exhaustion livelock: the energy≥95 emergency branch has no sleep action — outside the personality sleep window the agent paces between home cells indefinitely. Currently mostly shadowed by the rest-at-70 branch, but trivially triggerable by tuning. | Add a terminal at-home sleep action, or let critical exhaustion override the schedule gate. |
| F14 | `behavior/agent_behaviors.py:219-239` | Park-socialize mutates the partner mid-tick: shuffle-order gives a one-tick countdown asymmetry; both agents' social need is hard-reset to 0 instead of the calibrated −60. | Mediate interactions at a single manager/event point; start countdowns next tick; reuse `_update_needs_for_activity`. |
| F30 | `simulation/manager.py:12-39` | BFS uses `list.pop(0)` and full path copies; the returned path begins with the agent's own cell → one wasted movement tick per trip. | `collections.deque`, parent-pointer path reconstruction, skip index 0; consider A*. |
| F31 | `behavior/agent_behaviors.py:608-632` | Priority inversion: "Urgent: Rest" (energy≥70) outranks "Critical: Find Food" (hunger≥85) — tired-and-starving agents never eat while hunger pins at 100. | Put the starvation branch above rest, or gate rest on `hunger < 85`. |
| F32 | `simulation/manager.py:218-223` | Wage rates applied per tick but commented per hour (30× discrepancy); wage/cost tuning constants scattered as magic numbers. | Centralize economy constants in config with explicit units; document sim-time scaling. |
| F33 | `simulation/entities.py:103-120` + `app.py:58-61` | Full 50-entry logs for all agents shipped 2.5×/s; the server also echoes the whole payload back to the sender. | Delta updates; `include_self=False`; send logs on change only. |
| F34 | `simulation/llm_handler.py:39` | No LLM output validation: truncated diaries, null `content`, or missing `choices` are silently accepted or crash downstream (`KeyError` rides F01's kill path). | Validate response shape; check `finish_reason`; retry-or-flag empty/truncated generations. |
| F35 | `simulation/narrative/narrative_system.py:27-36,56-65` | Prompts are raw f-string concatenation of agent logs and *prior LLM output* — injectable, unversioned, and untestable. | Template files (Jinja2) with version headers; sanitize/delimit embedded content; log template hash per generation. |
| F36 | `simulation/llm_handler.py:16` | `get_embedding` is dead code; API key read from generic `API_KEY` env var; no fail-fast when missing; duplicate handler instances (command.py and manager each build one). | Wire embeddings into V2 retrieval or delete; rename `OPENAI_API_KEY`; fail fast at startup; single shared instance. |
| F37 | `simulation/manager.py:182-183` etc. | Dead/vestigial code: `_pending_narrative*` flags set but never read; no-op `reset_agent_diaries`; `tick()` returns an always-empty `commands` list; brittle `hour==3 and minute==0` exact match. | Remove dead members; event-driven day-end trigger. |
| F38 | `simulation/entities.py:23` + `config.py:13-24` | Trait merge silently overwrites colliding keys (conscientious vs spontaneous `planning_focus`); unknown traits silently dropped; **16 of 19 trait keys are never read** — advertised personality richness is unused. | Validate trait sets at load; combine collisions explicitly; wire traits into utilities or trim them. |
| F39 | `simulation/config.py:201-292` | 15+ `ACTIVITY_DATA` entries are unreachable dead config (no schedule references them and several schedule activities have no data entry) — the behavioral repertoire is materially overstated. | Cross-validate schedules ↔ activity data at startup; delete or wire dead entries. |
| F40 | `behavior/agent_behaviors.py:89-104` ↔ `manager.py:138-161` | Home-coordinate mapping duplicated with magic ranges in two modules, both hard-coupled to `map_data.json`. | Config gives each agent a home *place*; one function derives coords. |
| F41 | `command.py:64-72` | Fixed 0.4 s sleep with variable tick cost — sim-time/wall-clock ratio drifts, badly during any blocking call. | Fixed-timestep accumulator loop or deadline scheduling. |
| F42 | throughout | `print()` diagnostics only; no levels, no structure, no replayable event log; type hints inconsistent (analyzer typed, sim untyped). | structlog JSON logging + append-only journal; mypy across the sim package. |
| F43 | `app.py:11-19,74` | Hardcoded `SECRET_KEY`, CORS `*`, `debug=True` + `allow_unsafe_werkzeug=True`, import-time file I/O. | Env-based config; restrict CORS; production server settings; lazy map loading. |
| F44 | `static/script.js:89,154,204` | LLM and simulation text injected via `innerHTML` — stored XSS the moment any generated/log text contains markup. | `textContent` everywhere text is text; escape at render boundaries. |
| F45 | `static/index.html:14-18` | UI depends entirely on CDNs: Tailwind **Play CDN** (explicitly non-production), Google Fonts, socket.io client pinned to 4.0.1 (early-2021) from cdnjs — offline or blocked network kills the whole UI (`io()` → ReferenceError). | Vendor socket.io client; pre-built Tailwind CSS (CLI) or plain CSS; self-host fonts. |
| F46 | `static/script.js:38` | No disconnect/error states — the UI silently freezes when command.py or the server dies. | Handle `disconnect`/`connect_error`; staleness indicator when updates stop. |
| F47 | `static/script.js:272-284` + `app.py:63-71` | Pause state desyncs across browser clients: the server broadcasts pause/resume but the frontend never subscribes; each tab keeps only local state. | Subscribe to the broadcast; render authoritative shared pause state. |
| F48 | `static/script.js:254-269` | Dead UI code: the static daily-story panel is replaced at runtime; unreachable/broken render paths; orphaned CSS; advertised-but-missing elements. | Prune after F04's fix makes the story path live. |
| F49 | `README.md:166` | README claims a "model-agnostic" LLMHandler; the handler hardcodes OpenAI endpoints and models. | Make it true via the V2 provider abstraction; fix the README. |
| F50 | `narrative_analyzer.py:103-106` | Analyzer duplicates the agent roster and weekday mapping instead of importing simulation config — silent divergence when agents change. | Import from `simulation.config`. |
| F51 | `narrative_analyzer.py:330,360,524` | Heatmap rows sort lexicographically: `day_10` renders before `day_2`; weekdays sort alphabetically (Friday first). The committed `results/*.png` figures are affected — a reviewer-visible flaw. | Numeric day column + explicit weekday reindex. |
| F52 | `narrative_analyzer.py:723+` | Keyword metrics use raw substring counting: "work" matches "workout", agent names match inside words — the README's quantitative claims are inflated by construction. | Tokenized/word-boundary matching; recompute README stats. |
| F53 | `narrative_analyzer.py:189+` | CWD-relative paths, per-run NLTK downloads, global warning suppression — environment-fragile analyzer runtime. | Path anchoring via `__file__`; cached corpora check; scoped warnings. |

---

## 3. V2.0 Architecture Design

### Design thesis

V1's insight — deterministic BT control + post-hoc LLM narration — is the publishable core. V2 (a) repairs the behavior layer so the "hybrid" claim is *true* (today the utility machinery decides nothing — F07/F08/F09), (b) makes the LLM layer production-grade and asynchronous, and (c) adds a **bounded feedback channel** from LLM reflection into behavior — precisely the "mixed-initiative" upgrade the README's own future-work section calls for, done safely.

### Process model: one process, not two

The Flask server / sim-client split across two processes is the direct cause of F04 (lost stories), F25 (dead pause button), and F41 (clock drift). V2 collapses to a single asyncio process:

```
┌────────────────────────────── townsim (single process, asyncio) ─────────────────────────────┐
│                                                                                               │
│  ┌───────────────┐   tick events   ┌──────────────┐   validated intents    ┌──────────────┐  │
│  │ SIMULATION    │ ──────────────▶ │ EVENT BUS /  │ ◀───────────────────── │ COGNITION    │  │
│  │ KERNEL        │                 │ JOURNAL      │                        │ WORKERS      │  │
│  │ fixed timestep│ ◀────────────── │ (append-only │ ──────────────────────▶│ (async LLM:  │  │
│  │ seeded RNG    │  apply at tick  │  JSONL)      │  day-end, encounters   │  diaries,    │  │
│  │ systems:      │  boundaries     └──────┬───────┘                        │  reflection, │  │
│  │  Schedule     │                        │                                │  dialogue,   │  │
│  │  Needs        │                        ▼                                │  story)      │  │
│  │  Behavior(BT) │                 ┌──────────────┐                        └──────┬───────┘  │
│  │  Movement     │                 │ WORLD STATE  │                               │          │
│  │  Interaction  │                 │ single source│                        ┌──────▼───────┐  │
│  │  Economy      │                 │ of truth +   │                        │ LLM GATEWAY  │  │
│  └───────┬───────┘                 │ snapshots    │                        │ providers,   │  │
│          │                         └──────────────┘                        │ retry, cache,│  │
│          ▼                                                                 │ rate limits  │  │
│  ┌───────────────┐    WebSocket (delta updates)    ┌────────────────┐      └──────────────┘  │
│  │ FastAPI +     │ ─────────────────────────────▶  │ Browser        │                        │
│  │ WS broadcast  │ ◀─────────────────────────────  │ dashboard      │                        │
│  └───────────────┘    pause/resume/inspect         └────────────────┘                        │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

Key properties:

- **The kernel never awaits an LLM call.** Cognition workers consume events from the bus and post results back as *typed intents* applied only at tick boundaries (fixes F01–F03 by construction).
- **Every state change is a journal event** → any run is replayable bit-for-bit (seeded RNG + journal), fixing F23/F42 and enabling a golden-replay CI test.
- **The browser is a pure view** — it can disconnect/reconnect freely (fixes F25/F46/F47 structurally).

### Module layout

```
townsim/
  kernel/        # clock, scheduler, event bus, journal, snapshots, seeded RNG
  world/         # WorldState, places, grid, spatial hash, pathfinding (A*)
  agents/        # components: Needs, Wallet, Personality, ScheduleState, SocialGraph
  behavior/      # BT runtime (py_trees), UtilitySelector, node library, blackboards
  cognition/     # memory stream, retrieval, reflection, dialogue, narrative
  llm/           # gateway: providers, prompt templates, schemas, semantic cache
  server/        # FastAPI app, WS hub, REST inspection/replay API
  config/        # pydantic-settings models + YAML defaults
  cli.py         # run / replay / analyze entrypoints
tests/           # unit, property, integration (FakeLLM), golden-replay
prompts/         # versioned Jinja2 templates (diary_v2.j2, reflect_v1.j2, ...)
```

### Behavior layer: BT + Utility hybrid, actually working

- **py_trees** as the composite/decorator substrate (correct RUNNING semantics, blackboards, tree introspection for the dashboard). The README already claims py_trees (F28) — V2 makes the claim true.
- **`UtilitySelector`** replaces `StatefulSelector`: children scored by real utility functions (need pressure × personality weights × schedule pressure × opportunity), tried in descending order **with fallback on failure**, committed while RUNNING with a small hysteresis bonus against oscillation. One component fixes F07, F08, F09, F19, and F21.
- **Three-scope blackboard** (agent / group / world) replaces ad-hoc attributes and shared-dict mutation (fixes F20 and the F15-class of stale-state bugs; conversation state lives in a group scope with symmetric teardown).
- **Location-guard idiom** applied uniformly: `Selector[Sequence[IsAt(target), Do(action)], GoTo(target)]` (fixes F05, F11 structurally).
- Root priorities re-ordered with explicit rationale (fixes F31); a real at-home sleep action ends the F12 latent livelock.

### Cognition layer: memory, reflection, bounded feedback

Generative-Agents-inspired (Park et al., 2023), BT-grounded:

- **Episodic memory** keyed by absolute `day_index` + tick, with location/participants/importance (fixes F18). Importance from cheap heuristics (relationship delta, novelty, rarity), optional LLM scoring for candidates.
- **Retrieval**: `score = α·recency + β·importance + γ·relevance` with embedding cosine relevance — finally exercising the currently-dead embedding path (F36).
- **Nightly reflection**: the LLM reads retrieved highlights and returns a **typed, validated `ReflectionResult`** (Pydantic): mood, ≤3 insights, ≤3 *clamped* goal-weight adjustments, ≤2 schedule proposals validated against the schedule grammar. This is the bounded feedback channel: open-ended cognition, guaranteed-safe behavior. It is the architectural novelty (§6).
- **Hierarchical summarization**: day → daily summary → weekly summary; prompts reference summaries + retrieved episodes, never the raw stream. Token cost per agent-day becomes O(1).

### Social & narrative layer

- **Relationship model** per dyad (familiarity, affinity, valence) updated by interaction events with decay; feeds both utility scores (whom to approach) and prompt context (how to talk about them).
- **Conversations**: salient encounters (first meeting, large affinity delta, story-beat candidates) get budget-capped multi-turn LLM dialogues; mundane encounters get templated exchanges. Transcripts summarize into both agents' memories.
- **Emergent event detection**: rule triggers (conflict, milestone, streak, first-X) nominate story beats; a nightly LLM pass over the journal selects the day's beats; the town-story prompt is built around beats + diary excerpts — directly attacking the weak diary↔story cohesion V1 measured (mean TF-IDF similarity 0.149).

### Simulation kernel

- **Fixed-timestep loop** (sim-minutes per tick from config), wall-clock independent, with a headless fast-forward mode for experiments (fixes F41).
- **Seeded `random.Random` per subsystem**; seed in the journal header (fixes F23).
- **WorldState + snapshots + journal → replay CLI**; golden-replay test in CI (same seed ⇒ identical journal hash).
- **Spatial hash** for proximity queries (V1's `FindAgentToTalkTo` is O(n) per agent per tick → O(n²) overall); **A\*** with `heapq` (fixes F30); per-run output directories (fixes F24).
- **esper ECS** adoption in Phase C for the 100+ agent scalability chapter; dataclass components from day one make that migration mechanical.

---

## 4. Upgrade Roadmap

### Phase A — Correctness & survivability (~2 person-weeks)
*Goal: the current feature set, but true — runs indefinitely, reproducibly, end-to-end.*

| # | Work item | Fixes |
|---|-----------|-------|
| A1 | `requirements.txt`/`pyproject.toml`, pinned | F06, F29 |
| A2 | Story delivery via client channel + rebroadcast; per-run output dirs | F04, F24, F48 |
| A3 | LLM timeout + tenacity retries + output-shape validation; never kill the loop | F01, F02, F34 |
| A4 | Narrative generation on a background thread fed by a day-end event | F03, F37 |
| A5 | BT structural fixes: food-branch guard, rest-location check, per-agent transient state, priority order, at-home sleep | F05, F11, F20, F31, F12 |
| A6 | UtilitySelector semantics: order-preserving scores, call `simulate()`, fallback on failure, decision-change-only logging | F07, F08, F09, F19, F10 |
| A7 | Schedule wrap-around windows; schedule↔activity cross-validation | F17, F39 |
| A8 | Memory keyed by `day_index` + post-diary pruning | F18 |
| A9 | Charge activities once per slot; economy constants centralized with units | F13, F32 |
| A10 | Interaction hygiene: `break_interaction()` helper, arrival adjacency check, `agent_` replanning | F15, F16, F22 |
| A11 | `ShouldSocialize` numeric default | F21 |
| A12 | Seeded RNG + seed logging | F23 |
| A13 | Frontend: null-avatar fix, engine-ready state, delta-aware rendering, `textContent`, vendored assets, disconnect states | F25, F26, F27, F44, F45, F46, F47 |
| A14 | pytest suite (BT contracts, schedule property tests, BFS, memory filters) + FakeLLM smoke run + GitHub Actions | F29 |
| A15 | structlog everywhere; README rewritten to match reality | F42, F28, F49 |

### Phase B — Core V2 architecture (~4–6 person-weeks)
*Goal: the architecture in §3, minus the showcase extras.*

| # | Work item |
|---|-----------|
| B1 | Single-process FastAPI + asyncio port (server/, kernel/ skeleton) |
| B2 | WorldState + event journal + snapshots + replay CLI + golden-replay test |
| B3 | Config system: pydantic-settings + YAML + env overrides (all magic numbers migrate) |
| B4 | Three-scope blackboard |
| B5 | BT rebuild on py_trees + `UtilitySelector` composite + node library with location-guard idiom |
| B6 | Memory stream + embedding retrieval + nightly reflection with the bounded feedback channel |
| B7 | Prompt template system (versioned Jinja2) + Pydantic structured outputs |
| B8 | Provider abstraction (OpenAI/Anthropic/Ollama) + semantic cache |
| B9 | Relationship dynamics (familiarity/affinity/valence with decay) |
| B10 | Dashboard v2: delta WS updates, live BT-path inspector, relationship graph, diary panel |

### Phase C — Showcase & research (~4–6 person-weeks)
*Goal: the demo that impresses and the evaluation that publishes.*

| # | Work item |
|---|-----------|
| C1 | Multi-turn conversation system with saliency budgeting |
| C2 | Emergent event detection → story beats → beat-driven town story |
| C3 | Dynamic schedule generation from reflections (invitations, plan changes) |
| C4 | Scalability: spatial hash, esper ECS migration, 100–500 agent benchmark |
| C5 | (Optional) grammar-based procedural town-block generation |
| C6 | Evaluation harness: metrics battery + 4-way ablation (BT-only / LLM-only / hybrid-no-feedback / full) |
| C7 | Packaging, demo video, docs site, artifact release |

**Total: ~10–14 person-weeks** for a single senior developer; Phase A alone yields a demonstrably correct, unkillable, reproducible system.

---

## 5. Technology Stack Recommendations

All maintenance statuses verified against current releases (July 2026).

| Library | Role | Justification / status |
|---------|------|------------------------|
| **FastAPI + uvicorn** | Async server, WebSocket hub, inspection API | Async-native; kills the two-process split. v0.139.0 (Jul 2026), very active. |
| **pydantic v2 + pydantic-settings + PyYAML** | Config with env overrides **and** LLM output schemas | One library, two critical jobs. v2.13.4, Rust-core, industry standard. |
| **openai SDK (AsyncOpenAI) behind a small Protocol; LiteLLM when a 2nd provider lands** | Provider abstraction | Protocol-first keeps moving parts minimal; LiteLLM (v1.90.2, very active) buys OpenAI/Anthropic/Ollama breadth when actually needed. |
| **instructor** (optional alternative) | Pydantic-validated LLM outputs | v1.15.4, active; use it *or* the hand-rolled `complete_structured` in §7 — not both. |
| **tenacity** | LLM retry/backoff | v9.1.4, stable, declarative. |
| **jinja2** | Versioned prompt templates | Template hash logged per generation → prompt provenance. |
| **py_trees** | BT runtime | v2.4.0 (Nov 2025), maintained; correct RUNNING semantics, blackboards, introspection — and makes the README's claim true. |
| **esper** | ECS for Phase C scaling | v3.7 (Jan 2026), lightweight, pure Python. |
| **numpy** | Embedding math (retrieval, semantic cache) | — |
| **structlog** | JSON structured logging | v26.1.0 (Jun 2026). |
| **pytest + pytest-asyncio + hypothesis** | Tests; property tests are ideal for wrap-around schedule windows and BT invariants | pytest 9.1.1, hypothesis 6.156.x — both very active. |
| **ruff + mypy** | Lint/format/typecheck in CI | — |
| **sqlite (stdlib)** | Semantic-cache persistence, journal index | No server DB needed at this scale. |

**Explicitly not recommended:** Celery/Redis (asyncio queues suffice; a broker adds ops burden for zero benefit in a single-process sim), LangChain (the LLM surface is ~5 templates + embeddings; a framework adds indirection, not capability), and MCTS planning (the per-slot decision space is small; utility + reflection covers it — revisit only if multi-step social planning becomes a research goal in Phase C).

---

## 6. Academic Contribution Framework

### Research claim

> We present a hybrid agent architecture for narrative simulation in which behavior is governed entirely by deterministic, utility-arbitrated behavior trees, while an LLM performs asynchronous post-hoc narrative cognition — per-agent diaries, reflection, and town-level story synthesis — over the simulation's factual event log. Cognition feeds back into behavior exclusively through a typed, bounded, validated channel (clamped goal-weight adjustments and grammar-checked schedule proposals), yielding agents that are simultaneously (a) reliable, reproducible, and cheap enough for games — O(1) LLM calls per agent-day rather than per decision — and (b) capable of open-ended, memory-grounded character development.

### Novelty differentiators (verified against the literature)

1. **Inverted control-flow hybrid.** Generative Agents (Park et al., UIST 2023), AI Town (a16z, 2023), Project Sid (Altera, arXiv:2411.00114) and AgentSociety (arXiv:2502.08691) all keep LLM inference inside the per-decision loop; PIANO (Sid) merely parallelizes it. This system removes it entirely: behavior is symbolic, seeded, and re-runnable; language cognition is asynchronous and off the critical path.
2. **Verifiable narrative grounding as a first-class metric.** Because the BT substrate emits symbolic ground truth, every generated diary/story sentence can be audited as supported/unsupported/contradicted — a hallucination-rate score for emergent narrative that pure-LLM systems *cannot compute* (their "ground truth" memory stream is itself LLM output).
3. **Reflection-to-utility coupling.** Park-style retrieval/reflection outputs parameterize a classical utility arbiter over BTs (Mark 2009; Merrill, *Game AI Pro* 2013) rather than being spliced into prompts — a bridge between the Generative-Agents cognitive loop and the Game AI Pro control tradition that neither literature has built.
4. **Cost and reproducibility economics.** Seeded reruns are bit-identical and near-free; LLM cost is amortized asynchronously — a direct answer to the cost/latency limitations Park et al. themselves acknowledge, enabling controlled A/B ablations impossible in stochastic in-loop systems.
5. **Two-level focalized narration from one ground truth.** The same event log renders as first-person diaries *and* an omniscient town chronicle — making narrative focalization over shared emergent events an object of study; surveyed systems either hand-author narrative (Façade) or produce none.
6. **Honest non-novelty disclosure** (state this in the paper): BT/planner hybrids (Hilburn, *Game AI Pro* 2013), utility-driven BT selection (Merrill 2013), the memory-stream design (Park et al. 2023), and LLM diary generation are each established. The contribution is the specific composition, the grounding-auditable pipeline, and its cost/believability evaluation.

### Key related work (citations verified)

- Park, J.S., O'Brien, J.C., Cai, C.J., Morris, M.R., Liang, P., Bernstein, M.S. (2023). *Generative Agents: Interactive Simulacra of Human Behavior.* UIST '23. DOI: 10.1145/3586183.3606763.
- Wang, G. et al. (2024). *Voyager: An Open-Ended Embodied Agent with Large Language Models.* TMLR, March 2024 (arXiv:2305.16291) — single-agent skill acquisition; no social sim, no narrative.
- a16z-infra (2023). *AI Town* (github.com/a16z-infra/ai-town) — engineering artifact, no evaluation, no hybrid control layer.
- Altera.AL (2024). *Project Sid: Many-agent simulations toward AI civilization.* arXiv:2411.00114 — PIANO parallelizes in-loop LLM cognition; measures civilizational progress, not narrative.
- Piao, J. et al. (2025). *AgentSociety.* arXiv:2502.08691 — macro-social realism at 10k agents; no per-agent narrative artifacts.
- Orkin, J. (2006). *Three States and a Plan: The A.I. of F.E.A.R.* GDC 2006 — symbolic planning, no language cognition.
- Mateas, M., Stern, A. (2004/2005). ABL / *Façade* (AIIDE 2005) — hand-authored believability; nothing generated.
- Mark, D. (2009). *Behavioral Mathematics for Game AI*; Merrill, B. (2013) and Hilburn, D. (2013) in *Game AI Pro*, CRC Press.

### Evaluation plan

| Metric | Method | Precedent |
|--------|--------|-----------|
| Behavioral reliability | % invalid/impossible actions (ours: 0 by construction vs measured LLM-only baseline); schedule adherence; needs homeostasis (time-in-critical-band) | novel to this architecture |
| Believability | Interview-probe rankings by human raters, TrueSkill-aggregated, across ablations | Park et al. 2023 (100 raters, 5 conditions) |
| Narrative grounding | Decompose diaries/stories into atomic claims; label supported/unsupported/contradicted against the journal → faithfulness score | novel — enabled by symbolic ground truth |
| Narrative coherence | Diary↔story embedding similarity (upgrading V1's TF-IDF 0.149 baseline); cross-day continuity probes; human Likert/pairwise ratings | extends V1's own analyzer |
| Behavioral diversity | Entropy of activity distributions per agent-day; distinct interaction patterns; personality separability (classifier recovering traits from behavior logs alone) | adapted from Voyager's diversity metrics |
| Cost & scalability | Tokens + $ per agent-day vs Generative-Agents-style baseline (orders of magnitude); tick latency vs agent count (target 100+ real-time on a laptop); narrative latency showing the async pipeline never blocks | Park et al. flag cost as a limitation; Sid scales 10–1000+ |
| Ablations | (i) BT-only, (ii) LLM-only decisions, (iii) hybrid without feedback channel, (iv) full system | Park et al.'s component ablations |

### Suggested venues (status verified July 2026)

1. **AIIDE 2027** — primary target; the home of believable agents and interactive narrative (AIIDE 2026's June deadline has just passed; 2027 gives time for the Phase C evaluation). Artifact/demo track fits the system itself.
2. **IEEE CoG 2026 (Madrid, Sept 1–4)** — full-paper cycle closed, but **demo/auxiliary tracks remain viable near-term targets** for the showcase.
3. **FDG 2027** — systems + games-research fit (FDG 2026 deadlines passed).
4. **ICLR/NeurIPS workshops on agent memory & multi-agent systems** (ICLR 2026 ran MemAgents and MALGAI; NeurIPS 2025 ran MTI-LLM) — fast-turnaround workshop paper on the memory/reflection/bounded-feedback slice.
5. **CHI 2027** (papers deadline ~Sept 2026) — only with a human-subjects believability/comprehension study front and center (precedent: Generative Agents at UIST).

### Paper outline

1. Introduction — the control-vs-autonomy tension in game NPCs; cost/reproducibility failures of in-loop LLM agents
2. Related Work — LLM agent simulacra; classical game AI (BT/GOAP/utility); interactive emergent narrative
3. Architecture — kernel; BT+utility substrate; memory/retrieval/reflection; the bounded feedback channel; two-level narrative pipeline
4. Implementation — open-source, seeded/replayable, provider-agnostic; journal as ground truth
5. Evaluation — metrics + 4-way ablation (§ above)
6. Results
7. Discussion — limitations (small authored town, template schedules); ethics (parasocial NPC risks, narrative hallucination even when grounded)
8. Conclusion

---

## 7. Code Samples

### 7.1 Async LLM gateway (provider abstraction, retries, bounded concurrency, semantic cache, structured output)

```python
# townsim/llm/gateway.py
"""Provider-agnostic async LLM gateway: retries, timeouts, bounded concurrency,
semantic caching, and schema-validated structured output.
Replaces simulation/llm_handler.py (fixes F01, F02, F34, F49)."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

import numpy as np
from pydantic import BaseModel, ValidationError
from tenacity import (
    retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter,
)

T = TypeVar("T", bound=BaseModel)


class TransientLLMError(Exception):
    """Rate limits, 5xx, timeouts — safe to retry."""


class LLMProvider(Protocol):
    async def complete(self, prompt: str, *, max_tokens: int, temperature: float) -> str: ...
    async def embed(self, text: str) -> list[float]: ...


class OpenAIProvider:
    def __init__(self, api_key: str, model: str = "gpt-4.1-mini",
                 embed_model: str = "text-embedding-3-small") -> None:
        from openai import AsyncOpenAI, APIStatusError, APITimeoutError, RateLimitError
        self._client = AsyncOpenAI(api_key=api_key, timeout=30.0)
        self._model, self._embed_model = model, embed_model
        self._transient = (RateLimitError, APITimeoutError, APIStatusError)

    async def complete(self, prompt: str, *, max_tokens: int, temperature: float) -> str:
        try:
            rsp = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens, temperature=temperature,
            )
        except self._transient as exc:          # normalize for tenacity
            raise TransientLLMError(str(exc)) from exc
        return rsp.choices[0].message.content or ""

    async def embed(self, text: str) -> list[float]:
        try:
            rsp = await self._client.embeddings.create(model=self._embed_model, input=text)
        except self._transient as exc:
            raise TransientLLMError(str(exc)) from exc
        return rsp.data[0].embedding


@dataclass
class SemanticCache:
    """Reuses responses for near-duplicate prompts (cosine >= threshold)."""
    threshold: float = 0.97
    _keys: list[np.ndarray] = field(default_factory=list)
    _values: list[str] = field(default_factory=list)

    def get(self, embedding: list[float]) -> str | None:
        if not self._keys:
            return None
        q = np.asarray(embedding)
        q = q / np.linalg.norm(q)
        matrix = np.stack(self._keys)                       # (n, d), rows unit-norm
        best = int(np.argmax(matrix @ q))
        return self._values[best] if float(matrix[best] @ q) >= self.threshold else None

    def put(self, embedding: list[float], value: str) -> None:
        v = np.asarray(embedding)
        self._keys.append(v / np.linalg.norm(v))
        self._values.append(value)


class LLMGateway:
    def __init__(self, provider: LLMProvider, *, max_concurrency: int = 4,
                 cache: SemanticCache | None = None) -> None:
        self._provider = provider
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._cache = cache

    @retry(retry=retry_if_exception_type(TransientLLMError),
           wait=wait_exponential_jitter(initial=1, max=30), stop=stop_after_attempt(5),
           reraise=True)
    async def _complete_raw(self, prompt: str, max_tokens: int, temperature: float) -> str:
        async with self._semaphore:
            return await self._provider.complete(
                prompt, max_tokens=max_tokens, temperature=temperature)

    async def complete(self, prompt: str, *, max_tokens: int = 1024,
                       temperature: float = 0.8, cacheable: bool = False) -> str:
        embedding: list[float] | None = None
        if cacheable and self._cache is not None:
            embedding = await self._provider.embed(prompt)
            if (hit := self._cache.get(embedding)) is not None:
                return hit
        text = await self._complete_raw(prompt, max_tokens, temperature)
        if embedding is not None:
            self._cache.put(embedding, text)
        return text

    async def complete_structured(self, prompt: str, schema: type[T], *,
                                  max_tokens: int = 1024, attempts: int = 3) -> T:
        """LLM output -> validated Pydantic model, re-prompting on invalid JSON."""
        suffix = ("\nRespond with ONLY a JSON object matching this schema:\n"
                  f"{json.dumps(schema.model_json_schema(), indent=2)}")
        last_error = ""
        for _ in range(attempts):
            raw = await self.complete(prompt + suffix + last_error,
                                      max_tokens=max_tokens, temperature=0.2)
            try:
                start, end = raw.find("{"), raw.rfind("}") + 1
                return schema.model_validate_json(raw[start:end])
            except (ValidationError, ValueError) as exc:
                last_error = f"\nYour previous answer failed validation: {exc}. Fix it."
        raise ValueError(f"LLM output failed {schema.__name__} validation {attempts}x")
```

Cognition never blocks the kernel — the worker pattern replacing the 03:00 block (F03):

```python
# townsim/cognition/narrative_worker.py
async def narrative_worker(queue: asyncio.Queue, gateway: LLMGateway, journal: Journal):
    while True:
        job = await queue.get()                      # e.g. ("diary", agent_id, day_index)
        try:
            text = await gateway.complete(job.prompt, max_tokens=2048)
            journal.append("narrative_ready", kind=job.kind, agent=job.agent_id, text=text)
        except Exception:
            log.exception("narrative job failed", job=job)   # sim keeps running (F01)
        finally:
            queue.task_done()
```

### 7.2 BT core with a real UtilitySelector (fixes F07/F08/F09/F19)

```python
# townsim/behavior/core.py
"""Minimal, correct BT runtime with a utility-driven selector.
(With py_trees, UtilitySelector becomes a custom composite; these are the
semantics that matter.)"""
from __future__ import annotations

import enum
from abc import ABC, abstractmethod


class Status(enum.Enum):
    SUCCESS = enum.auto()
    FAILURE = enum.auto()
    RUNNING = enum.auto()


class Node(ABC):
    def __init__(self, name: str) -> None:
        self.name = name
        self.status: Status | None = None

    @abstractmethod
    def tick(self, ctx: "TickContext") -> Status: ...

    def utility(self, ctx: "TickContext") -> float:
        """Predicted desirability of running this subtree now. Override in
        branch roots; composites default to max over children."""
        return 0.0

    def reset(self) -> None:
        self.status = None
        for child in getattr(self, "children", []):
            child.reset()


class UtilitySelector(Node):
    """Scores children, tries them in descending utility, FALLS BACK on
    failure, and stays committed to a RUNNING child until it resolves."""

    def __init__(self, name: str, children: list[Node],
                 commitment_bonus: float = 0.15) -> None:
        super().__init__(name)
        self.children = children
        self._running_child: Node | None = None
        # Hysteresis: a running branch keeps a small bonus so agents don't
        # oscillate between near-equal utilities every tick.
        self._commitment_bonus = commitment_bonus

    def tick(self, ctx: "TickContext") -> Status:
        scored = sorted(
            self.children,
            key=lambda c: c.utility(ctx)
            + (self._commitment_bonus if c is self._running_child else 0.0),
            reverse=True,
        )
        for child in scored:
            if child is not self._running_child:
                child.reset()
            status = child.tick(ctx)
            if status == Status.RUNNING:
                self._running_child = child
                self.status = Status.RUNNING
                return Status.RUNNING
            if status == Status.SUCCESS:
                self._running_child = None
                self.status = Status.SUCCESS
                return Status.SUCCESS
            # FAILURE -> try the next-best child. (V1 returned FAILURE here,
            # which is why the Idle branch never ran.)
        self._running_child = None
        self.status = Status.FAILURE
        return Status.FAILURE

    def reset(self) -> None:
        super().reset()
        self._running_child = None
```

Utilities computed from real state, not name matching (fixes F08/F09/F21):

```python
# townsim/behavior/utilities.py
def free_time_socialize_utility(ctx: TickContext) -> float:
    agent = ctx.agent
    pressure = agent.needs.social / 100.0                       # 0..1
    talkativeness = agent.personality.talkativeness             # 0..1
    nearby = ctx.world.spatial.count_neighbors(agent.pos, radius=6)
    opportunity = min(nearby, 3) / 3.0
    return pressure * (0.5 + 0.5 * talkativeness) * (0.3 + 0.7 * opportunity)
```

The location-guard idiom every "do X somewhere" branch must use (fixes F05/F11):

```python
def eat_out_branch() -> Node:
    return Selector("eat out", [
        Sequence("eat here", [IsAtLocation("at cafe", key="eat_target"),
                              ExecuteEat("eat")]),
        GoTo("walk to cafe", key="eat_target"),      # returns RUNNING while walking
    ])
```

### 7.3 Scoped blackboard (fixes F20 and the F15-class of stale shared state)

```python
# townsim/behavior/blackboard.py
"""Three-scope blackboard: AGENT (private), GROUP (shared by an interaction
group), WORLD (global). Replaces ad-hoc attributes stuck onto Agent
(rest_location, eat_ticks, ...) and shared-dict mutation
(world_state['activity_data'] being overwritten per agent)."""
from __future__ import annotations

import enum
from typing import Any


class Scope(enum.Enum):
    AGENT = "agent"
    GROUP = "group"
    WORLD = "world"


class Blackboard:
    def __init__(self) -> None:
        self._data: dict[tuple[Scope, str, str], Any] = {}
        self._group_of: dict[str, str] = {}          # agent_id -> group_id

    def _key(self, scope: Scope, owner: str, name: str) -> tuple[Scope, str, str]:
        if scope is Scope.WORLD:
            return (scope, "*", name)
        if scope is Scope.GROUP:
            return (scope, self._group_of.get(owner, owner), name)
        return (scope, owner, name)

    def get(self, scope: Scope, owner: str, name: str, default: Any = None) -> Any:
        return self._data.get(self._key(scope, owner, name), default)

    def set(self, scope: Scope, owner: str, name: str, value: Any) -> None:
        self._data[self._key(scope, owner, name)] = value

    def clear_agent(self, agent_id: str) -> None:
        self._data = {k: v for k, v in self._data.items()
                      if not (k[0] is Scope.AGENT and k[1] == agent_id)}

    def join_group(self, agent_id: str, group_id: str) -> None:
        self._group_of[agent_id] = group_id

    def leave_group(self, agent_id: str) -> None:
        self._group_of.pop(agent_id, None)
```

### 7.4 Memory stream with scored retrieval + typed, bounded reflection (fixes F18/F19; implements the feedback channel)

```python
# townsim/cognition/memory.py
"""Generative-Agents-style episodic memory keyed by absolute day index
(V1 keyed by weekday name, so week 2 re-ingested week 1 — F18)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from pydantic import BaseModel, Field


@dataclass
class MemoryEntry:
    text: str
    day_index: int                    # absolute day, not weekday name
    tick: int
    importance: float                 # 0..1
    location: str | None = None
    participants: tuple[str, ...] = ()
    embedding: np.ndarray | None = None


@dataclass
class MemoryStream:
    alpha_recency: float = 1.0
    beta_importance: float = 1.0
    gamma_relevance: float = 1.0
    decay_per_tick: float = 0.995
    entries: list[MemoryEntry] = field(default_factory=list)

    def add(self, entry: MemoryEntry) -> None:
        self.entries.append(entry)

    def for_day(self, day_index: int) -> list[MemoryEntry]:
        return [e for e in self.entries if e.day_index == day_index]

    def retrieve(self, query_embedding: np.ndarray, now_tick: int, k: int = 12
                 ) -> list[MemoryEntry]:
        """score = a*recency + b*importance + c*relevance (Park et al., 2023)."""
        if not self.entries:
            return []
        q = query_embedding / np.linalg.norm(query_embedding)
        scored = []
        for e in self.entries:
            recency = self.decay_per_tick ** max(0, now_tick - e.tick)
            relevance = 0.0 if e.embedding is None else float(
                np.dot(e.embedding / np.linalg.norm(e.embedding), q))
            score = (self.alpha_recency * recency
                     + self.beta_importance * e.importance
                     + self.gamma_relevance * relevance)
            scored.append((score, e))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [e for _, e in scored[:k]]

    def compact(self, before_day: int, summary: MemoryEntry) -> None:
        """Hierarchical summarization: old episodics -> one summary entry."""
        self.entries = [e for e in self.entries if e.day_index >= before_day]
        self.entries.append(summary)


class GoalAdjustment(BaseModel):
    goal: str                                   # must name a known utility axis
    delta: float = Field(ge=-0.2, le=0.2)       # clamped: bounded feedback


class ScheduleProposal(BaseModel):
    day: str
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=0, le=23)
    activity: str                               # validated against ACTIVITY_DATA
    invitee: str | None = None


class ReflectionResult(BaseModel):
    """The ONLY channel through which LLM cognition may influence behavior.
    Everything is typed, bounded, and validated before the kernel applies it."""
    mood: str
    insights: list[str] = Field(max_length=3)
    goal_adjustments: list[GoalAdjustment] = Field(max_length=3)
    schedule_proposals: list[ScheduleProposal] = Field(max_length=2)


async def reflect(agent, gateway: "LLMGateway", day_index: int) -> ReflectionResult:
    highlights = agent.memory.for_day(day_index)
    prompt = render_template(
        "reflect_v1.j2", agent=agent,
        memories=[e.text for e in sorted(highlights,
                                         key=lambda e: e.importance, reverse=True)[:20]],
    )
    result = await gateway.complete_structured(prompt, ReflectionResult)
    # Kernel-side guards — never trust even validated output blindly:
    result.goal_adjustments = [a for a in result.goal_adjustments
                               if a.goal in agent.utility_axes]
    result.schedule_proposals = [p for p in result.schedule_proposals
                                 if p.activity in ACTIVITY_DATA]
    return result
```

### 7.5 Fixed-timestep kernel with journal (fixes F41/F42/F23; excerpt)

```python
# townsim/kernel/loop.py
async def run(kernel: Kernel, cfg: SimConfig) -> None:
    tick_budget = 1.0 / cfg.ticks_per_second     # 0 => headless, run flat out
    while kernel.running:
        started = time.perf_counter()
        events = kernel.step()                   # pure, deterministic, seeded RNG
        kernel.journal.extend(events)            # append-only JSONL ground truth
        await kernel.hub.broadcast_delta(events) # WS delta, not full state (F33)
        while not kernel.intents.empty():        # apply async cognition results
            kernel.apply(kernel.intents.get_nowait())   # only at tick boundaries
        if tick_budget:
            await asyncio.sleep(max(0.0, tick_budget - (time.perf_counter() - started)))
```

### 7.6 Overnight schedule windows — drop-in V1 micro-fix (F17)

```python
def is_in_window(hour: int, start: int, end: int) -> bool:
    """(22, 1) means 22:00-01:00 across midnight."""
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end
```

---

*Supporting artifacts in this directory: `findings_verified.json` (all 53 findings with full mechanisms and verification justifications), `research_verified.json` (citations, venues, metrics, novelty angles, library statuses), `audit_results_raw.json` (complete workflow output), `audit_workflow.js` (the orchestration script), `drafts/` (working drafts).*
