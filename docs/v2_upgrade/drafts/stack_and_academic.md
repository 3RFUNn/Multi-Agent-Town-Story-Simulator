# Draft — sections 5 & 6

## 5. Technology stack (to finalize with research agent's status notes)

Runtime core:
- FastAPI + uvicorn — async-native server; WebSocket support; replaces the two-process Flask/SocketIO split that causes the lost-story bug. OpenAPI docs free for the inspection API.
- python-socketio (AsyncServer) OPTIONAL — only if keeping the existing frontend socket code verbatim; otherwise native WebSockets and drop two deps.
- pydantic v2 + pydantic-settings + PyYAML — typed config with YAML defaults + env overrides; also the schema layer for LLM structured output. One library, two critical jobs.
- openai (official SDK, AsyncOpenAI) behind a small Protocol; litellm as the multi-provider adapter (OpenAI/Anthropic/Ollama) if provider breadth is wanted immediately. Recommendation: Protocol + official SDKs first (fewer moving parts), litellm when a second provider is actually needed.
- tenacity — declarative retry with exponential backoff + jitter for LLM calls.
- jinja2 — versioned prompt templates as files (prompts/diary_v2.j2), variables injected explicitly, template hash logged per generation for prompt provenance.

Behavior & simulation:
- py_trees — mature BT library (blackboards, decorators, visualization, correct RUNNING semantics). The README already cites it; V2 makes that true. Custom UtilitySelector implemented as a py_trees composite.
- esper — tiny, pure-python ECS for the Phase C scalability push (hundreds of agents); until then, dataclass components keep migration mechanical.
- numpy — embedding math for retrieval + semantic cache.
- heapq/A* + uniform spatial hash — stdlib; no dependency needed at this grid size.

Observability & quality:
- structlog — JSON structured logging with levels; pairs with the append-only journal for replay.
- pytest + pytest-asyncio + hypothesis — unit (BT contract, schedule windows — hypothesis property tests are perfect for wrap-around windows), integration (FakeLLM smoke runs), golden replay test.
- ruff + mypy — lint/format/typecheck; CI via GitHub Actions.
- sqlite (stdlib) — semantic cache persistence + journal index; no server DB needed.

Explicitly NOT recommended:
- Celery/Redis — asyncio queues suffice at this scale; a broker adds ops burden with zero benefit for a single-process sim.
- LangChain — the LLM surface here is 5 prompt templates + embeddings; a framework would add indirection, not capability.
- Full MCTS planner — the decision space (which scheduled/free-time branch) is small; utility scoring + reflection covers it. Revisit only if multi-step social planning becomes a research goal (Phase C option).

## 6. Academic contribution framework (citations to verify vs research agent)

### Research claim (draft)
"We present [SystemName], a hybrid agent architecture for narrative simulation in which
behavior is governed by deterministic behavior trees with utility-based arbitration, while
an LLM provides post-hoc narrative cognition (diaries, reflection, town-level story
synthesis) over the simulation's factual event log. Cognition feeds back into behavior
exclusively through a typed, bounded channel (goal-weight adjustments and schedule
proposals validated against a behavioral grammar), yielding agents that are simultaneously
(a) reliable and cheap enough for games — O(1) LLM calls per agent-day rather than per
decision — and (b) capable of open-ended, memory-grounded character development."

### Novelty differentiators (draft, honesty-checked)
1. vs Generative Agents (Park et al., UIST 2023): they put the LLM in the decision loop (plan/react/reflect all LLM) — believable but expensive and unconstrained (thousands of LLM calls/agent/day; no behavioral guarantees). Ours: BT substrate guarantees action validity and slashes cost by orders of magnitude; LLM influence is bounded and typed. The cost/believability trade-off curve is the paper's core figure.
2. vs AI Town / Concordia-style platforms: those are LLM-decision platforms; none provide a hybrid BT substrate with typed feedback.
3. vs Voyager (Wang et al., 2023): single-agent skill acquisition (code as policy) in Minecraft; no social simulation, no narrative layer.
4. vs classical game AI (GOAP/Orkin's F.E.A.R., utility AI, BT hybrids like Hilburn's): behaviorally rich but language-blind: no episodic memory grounded in natural language, no character development, no narrative artifact.
5. The diary→story pipeline as an *evaluable narrative artifact* with quantitative cohesion metrics (V1 already measures diary↔story similarity — a rare, concrete narrative metric) extended in V2 with beat-based story compilation.
NOT novel (say so in the paper): memory stream scoring (recency/importance/relevance) is Park et al.'s; BTs and utility AI are standard; the novelty is the *architecture of the coupling* + its evaluation.

### Evaluation plan (draft)
- Behavioral reliability: % invalid/impossible actions (ours: 0 by construction; LLM-only baseline measured); schedule adherence; needs homeostasis (time-in-critical-band).
- Cost/scalability: LLM tokens + $ per agent-day vs Generative-Agents-style baseline; tick latency vs #agents (target: 100+ agents real-time on a laptop).
- Narrative coherence: diary↔story embedding similarity + NLI-based factual consistency (does the diary contradict the event log?); cross-day continuity probes.
- Believability: Park-style human evaluation (interview probes rated by humans / pairwise TrueSkill ranking) across ablations.
- Ablations: (i) BT-only (no LLM), (ii) LLM-only decisions (no BT), (iii) hybrid w/o feedback channel, (iv) full system. This 4-way ablation directly evidences the claim.
- Behavioral diversity: entropy over activity distributions per agent; personality separability (can a classifier recover personality from behavior logs alone?).

### Paper outline (draft)
1 Introduction (control vs autonomy tension in game NPCs)
2 Related Work (LLM agent simulacra; BT/GOAP/utility game AI; interactive emergent narrative)
3 System: kernel/BT+utility/memory+reflection/bounded feedback/narrative pipeline
4 Implementation (open-source, replayable, provider-agnostic)
5 Evaluation (metrics + ablations above)
6 Results
7 Discussion (limitations: small town, template schedules; ethics: parasocial NPC risks)
8 Conclusion
Venues (verify): AIIDE (AI + interactive digital entertainment; artifact/demo track), IEEE CoG, FDG, NeurIPS workshop on (open-world) agents, CHI (if human-eval-centric).
