# Multi-Agent Town Story Simulator

**Author:** Erfan Rafieioskouei

A hybrid agent architecture for emergent narrative generation: deterministic **behavior trees with utility arbitration** drive autonomous town residents, while an **LLM performs asynchronous post-hoc narrative cognition** — per-agent diaries, nightly reflection, and a town-wide story — over the simulation's factual event journal. Cognition feeds back into behavior only through a **typed, bounded, validated channel**, so agents gain open-ended character development without ever losing behavioral reliability.

> **V2.0 (this branch)** is a ground-up re-architecture in the `townsim/` package, built from the findings of a full audit of the V1 prototype (53 verified defects — see [`docs/v2_upgrade/V2_UPGRADE_REPORT.md`](docs/v2_upgrade/V2_UPGRADE_REPORT.md)). The V1 code is preserved at the repo root (`app.py`, `command.py`, `behavior/`, `simulation/`) for reference.

![V2 dashboard](docs/v2_upgrade/dashboard_screenshot.png)

---

## V2.0 Quickstart

Requires Python 3.10+.

```bash
git clone <this repo> && cd Multi-Agent-Town-Story-Simulator
python -m venv .venv
.venv\Scripts\activate            # Windows   (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt

# Run with the live dashboard at http://127.0.0.1:8000
python -m townsim serve

# Headless research run: 3 simulated days, no wall-clock pacing
python -m townsim run --days 3 --fast

# Summarize any recorded run
python -m townsim replay runs/run_<stamp>_seed42/journal.jsonl
```

**No API key needed to try it.** Without a key, the system uses a deterministic offline provider (`fake`) that grounds its text in the real event journal. For real narratives, set an OpenAI key and the provider resolves automatically:

```bash
# .env or environment
OPENAI_API_KEY=sk-...             # (the V1 name API_KEY also still works)
```

Configuration lives in [`townsim/config/default.yaml`](townsim/config/default.yaml) — copy to `townsim.yaml` at the repo root to customize, or override any key via environment (`TOWNSIM_KERNEL__SEED=7`, `TOWNSIM_LLM__PROVIDER=fake`, …). All tuning constants (needs rates, wages, thresholds, tick scale) are config, not magic numbers.

### Reproducibility

Every run writes to its own directory under `runs/` (journal, diaries, stories — nothing is ever overwritten). The journal carries a **determinism hash** over all behavioral events:

```bash
python -m townsim run --days 2 --fast --provider fake --seed 42
# -> Determinism hash: 2b0540f0...   (bit-identical on every machine, every rerun)
```

Same seed → identical behavior, byte for byte, even with the narrative layer enabled (`--strict`, the default for `run`, settles cognition at day rollovers so LLM results land at reproducible sim times).

### Tests

```bash
pip install -r requirements-dev.txt
pytest              # 65 tests: BT contracts, wrap-around schedules, pathfinding,
                    # memory, bounded reflection, 2-day integration runs, determinism
```

---

## V2.0 Architecture

One process, one source of truth, cognition off the critical path:

```
┌────────────────────────── townsim (single process, asyncio) ──────────────────────────┐
│  ┌───────────────┐   events    ┌──────────────┐   typed intents   ┌──────────────┐    │
│  │ KERNEL        │ ──────────▶ │ JOURNAL      │ ◀──────────────── │ COGNITION    │    │
│  │ fixed timestep│             │ (JSONL, per- │                   │ (async LLM:  │    │
│  │ seeded RNG    │             │  run dirs,   │ ────────────────▶ │ diaries,     │    │
│  │ Schedule      │             │  determinism │   day-end jobs    │ reflection,  │    │
│  │ Needs         │             │  hash)       │                   │ story,       │    │
│  │ Behavior (BT+ │             └──────────────┘                   │ dialogue)    │    │
│  │  UtilitySel.) │                                                └──────┬───────┘    │
│  │ Movement      │   WebSocket deltas   ┌────────────────┐        ┌──────▼───────┐    │
│  │ Interaction   │ ───────────────────▶ │ Dashboard      │        │ LLM GATEWAY  │    │
│  │ Economy       │ ◀─────────────────── │ (self-contained│        │ retry, cache,│    │
│  └───────────────┘   pause / inspect    │  vanilla JS)   │        │ providers    │    │
└─────────────────────────────────────────└────────────────┘────────└──────────────┘────┘
```

| Layer | Module | What it does |
|-------|--------|--------------|
| Kernel | `townsim/kernel/` | Fixed-timestep clock (sim time is a pure function of the tick), per-subsystem seeded RNG streams, append-only event journal with per-run directories, async run loop |
| World | `townsim/world/` | Map + places, spatial-hash proximity queries, A* pathfinding, `WorldState` as single source of truth |
| Behavior | `townsim/behavior/` | Reactive BT runtime; **`UtilitySelector`** scores branches from real state (needs × personality × opportunity), falls back on failure, commits with hysteresis; three-scope blackboard (agent / group / world); location-guard idiom on every "do X somewhere" branch |
| Systems | `townsim/systems.py` | Ordered per-tick logic: wrap-aware schedules, needs, action expiry, movement with universal replanning, single-point conversation mediation with symmetric teardown, charge-once-per-slot economy |
| Cognition | `townsim/cognition/` | Day-indexed episodic memory with recency/importance/relevance retrieval and compaction; nightly **bounded reflection** (mood, clamped utility-weight deltas, grammar-checked schedule proposals); diary → story pipeline with rule-triggered story beats; salient-encounter dialogue rendering |
| LLM | `townsim/llm/` | Provider Protocol (OpenAI / deterministic offline fake), async gateway with timeouts + exponential-backoff retries + bounded concurrency, embedding-based semantic cache, versioned Jinja2 prompt templates, Pydantic-validated structured output |
| Server | `townsim/server/` | FastAPI + WebSocket hub (delta updates), REST inspection API, dependency-free dashboard with live BT-path introspection, needs bars, relationships, diaries, stories |

### The bounded feedback channel

The LLM never chooses actions. Each night it reads the day's retrieved memories and returns a `ReflectionResult` — validated by Pydantic, then sanitized again by the kernel: mood, up to 3 insights, up to 3 utility-weight adjustments (clamped to ±0.2, weights bounded to [0.4, 2.0]), up to 2 schedule proposals (checked against the activity grammar). Open-ended cognition, guaranteed-safe behavior — the property that makes this architecture publishable (see the [upgrade report](docs/v2_upgrade/V2_UPGRADE_REPORT.md), §6).

### Why not LLM-in-the-loop?

Compared to Generative-Agents-style systems (Park et al., UIST 2023), where the LLM plans every action:

- **O(1) LLM calls per agent-day** (diary + reflection + shared story) instead of per decision — orders of magnitude cheaper;
- **bit-exact reproducibility** from a seed — impossible with in-loop sampling;
- **auditable narratives**: every generated sentence can be checked against the symbolic ground-truth journal (a hallucination-rate metric pure-LLM simulacra cannot compute, because their "ground truth" is itself LLM output).

---

## Project structure

```
townsim/                 # V2.0 package (see table above)
tests/                   # pytest suite (65 tests)
prompts/                 # versioned Jinja2 prompt templates (diary, story, reflect, dialogue)
runs/                    # per-run output: journal.jsonl, diaries/, stories/   (gitignored)
docs/v2_upgrade/         # V1 audit report (53 verified findings), V2 design docs, artifacts
app.py, command.py,      # V1 prototype (two-process Flask/SocketIO version) — kept for
behavior/, simulation/,  #   reference; see the audit report for its known defects
static/                  #   V1 frontend + map_data.json (the map is shared with V2)
narrative_analyzer.py    # offline NLP analysis toolkit over generated narratives
results/                 # analysis outputs from the V1 14-day study
```

## V1 prototype (legacy)

The original two-process prototype (Flask-SocketIO server + simulation client) remains runnable:

```bash
pip install -r requirements.txt
python app.py          # terminal 1 — web server on :5000
python command.py      # terminal 2 — simulation client (requires an OpenAI key)
```

Known limitations are documented exhaustively in the [V2 upgrade report](docs/v2_upgrade/V2_UPGRADE_REPORT.md) — among them: daily stories never reach the V1 browser UI (cross-process emit), a single LLM error terminates the run, the custom `StatefulSelector`'s heuristic degenerates to fixed priority, and runs are not reproducible. V2 fixes all of these by construction. Two claims in earlier versions of this README have been corrected: V1 uses a **custom** behavior-tree implementation (not `py_trees`), and the V1 `LLMHandler` is **OpenAI-only** (provider abstraction arrived in V2).

## Narrative analysis toolkit

`narrative_analyzer.py` evaluates generated narratives (TF-IDF diary↔story similarity, day-of-week behavioral consistency, sentiment and behavioral keyword patterns, agent interaction networks) and writes CSVs + figures to `results/`:

```bash
pip install -r requirements-dev.txt pandas matplotlib seaborn scikit-learn textblob networkx
python narrative_analyzer.py
```

Headline numbers from the V1 14-day, 6-agent study (84 diaries): mean diary↔story similarity 0.149; stable positive sentiment across agents; clear per-agent behavioral differentiation (Charlie the social hub, Alex work-oriented, Fiona/Bella reserved). V2's story-beat pipeline is designed to raise the diary↔story cohesion number; the analyzer runs unchanged over `runs/<run>/diaries` output.

## Research framing

The system is positioned as a **hybrid agentic architecture** contribution: BT/utility behavioral substrate + LLM narrative cognition + bounded feedback, evaluated on behavioral reliability, believability (Park-style interview probes), narrative grounding (claim-level faithfulness against the journal), behavioral diversity, and cost/scalability, with a 4-way ablation (BT-only / LLM-only / hybrid-without-feedback / full). Full academic framing — verified related work, metrics, venues (AIIDE, IEEE CoG, FDG, agent-memory workshops), and paper outline — in [`docs/v2_upgrade/V2_UPGRADE_REPORT.md`](docs/v2_upgrade/V2_UPGRADE_REPORT.md) §6.

**Key references**

- Park et al., *Generative Agents: Interactive Simulacra of Human Behavior*, UIST '23 ([arXiv:2304.03442](https://arxiv.org/abs/2304.03442))
- Orkin, *Three States and a Plan: The A.I. of F.E.A.R.*, GDC 2006
- Mark, *Behavioral Mathematics for Game AI*, 2009; Merrill & Hilburn chapters in *Game AI Pro*, CRC Press 2013
- Wang et al., *Voyager: An Open-Ended Embodied Agent with LLMs*, TMLR 2024 ([arXiv:2305.16291](https://arxiv.org/abs/2305.16291))
- Altera.AL, *Project Sid: Many-agent simulations toward AI civilization*, 2024 ([arXiv:2411.00114](https://arxiv.org/abs/2411.00114))

## License

MIT — see `LICENSE`.

## Acknowledgments

OpenAI (LLM API), FastAPI/Starlette, pydantic, Jinja2, structlog, tenacity, NumPy, pytest & Hypothesis, Flask & Socket.IO (V1), TextBlob/NLTK/NetworkX/pandas/matplotlib/seaborn (analysis), and Park et al. for the foundational generative-agents work.
