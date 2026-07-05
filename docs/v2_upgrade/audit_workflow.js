export const meta = {
  name: 'town-sim-v2-audit',
  description: 'Exhaustive multi-dimension audit of the Multi-Agent Town Story Simulator with adversarial verification, plus academic-framing research',
  phases: [
    { title: 'Audit', detail: '5 parallel dimension-focused code auditors' },
    { title: 'Research', detail: 'verify related work, venues, metrics, libraries via web' },
    { title: 'Merge', detail: 'dedupe finder + lead findings into canonical list' },
    { title: 'Verify', detail: 'adversarial per-finding verification against the code' },
  ],
}

const ROOT = 'D:/Github/Multi-Agent-Town-Story-Simulator'

const FINDINGS_SCHEMA = {
  type: 'object', required: ['findings'],
  properties: { findings: { type: 'array', items: { type: 'object',
    required: ['severity', 'file', 'title', 'description', 'fix'],
    properties: {
      severity: { type: 'string', enum: ['Critical', 'Major', 'Minor'] },
      file: { type: 'string' },
      line: { type: 'integer' },
      title: { type: 'string' },
      description: { type: 'string' },
      fix: { type: 'string' },
    } } } } }

const VERDICT_SCHEMA = {
  type: 'object', required: ['verdict', 'justification'],
  properties: {
    verdict: { type: 'string', enum: ['CONFIRMED', 'REFUTED', 'PARTIAL'] },
    justification: { type: 'string' },
    corrected_title: { type: 'string' },
    corrected_description: { type: 'string' },
    corrected_severity: { type: 'string', enum: ['Critical', 'Major', 'Minor'] },
  } }

const BATCH_SCHEMA = {
  type: 'object', required: ['verdicts'],
  properties: { verdicts: { type: 'array', items: { type: 'object',
    required: ['id', 'verdict', 'justification'],
    properties: {
      id: { type: 'string' },
      verdict: { type: 'string', enum: ['CONFIRMED', 'REFUTED', 'PARTIAL'] },
      justification: { type: 'string' },
    } } } } }

const RESEARCH_SCHEMA = {
  type: 'object', required: ['related_work', 'venues', 'metrics', 'novelty_angles', 'libraries'],
  properties: {
    related_work: { type: 'array', items: { type: 'object',
      required: ['name', 'citation', 'summary', 'difference_hook'],
      properties: { name: { type: 'string' }, citation: { type: 'string' }, summary: { type: 'string' }, difference_hook: { type: 'string' } } } },
    venues: { type: 'array', items: { type: 'object', required: ['venue', 'fit_rationale'],
      properties: { venue: { type: 'string' }, fit_rationale: { type: 'string' } } } },
    metrics: { type: 'array', items: { type: 'object', required: ['metric', 'how_to_measure', 'used_by'],
      properties: { metric: { type: 'string' }, how_to_measure: { type: 'string' }, used_by: { type: 'string' } } } },
    novelty_angles: { type: 'array', items: { type: 'string' } },
    libraries: { type: 'array', items: { type: 'object', required: ['name', 'purpose', 'status_note'],
      properties: { name: { type: 'string' }, purpose: { type: 'string' }, status_note: { type: 'string' } } } },
  } }

const COMMON = `You are auditing a Python multi-agent town simulator at ${ROOT}. ` +
  `It runs as two processes: app.py (Flask+Flask-SocketIO server serving static/ and rebroadcasting events) and command.py (a python-socketio CLIENT that runs AgentManager.tick() in a 0.4s loop and emits state to the server). ` +
  `Agents are driven by a custom behavior tree (behavior/), needs/schedules (simulation/config.py), BFS pathfinding on a 30x23 grid (static/map_data.json), and an LLM writes per-agent diaries plus a town story at 03:00 sim time (simulation/narrative/narrative_system.py via simulation/llm_handler.py, synchronous OpenAI REST calls). ` +
  `READ the actual files with the Read tool before claiming anything; cite file and line numbers. Report only defects you can verify in the code — trace the execution path that triggers each one. Do NOT read or print the .env file. ` +
  `Severity: Critical = breaks runnability/loses data/kills the sim; Major = wrong behavior, unbounded growth, dead subsystem, non-reproducibility; Minor = quality/perf/hygiene. ` +
  `Return findings via the structured output schema. Be exhaustive within your dimension; do not pad with generic style advice.`

const FINDERS = [
  { key: 'bt-logic', prompt: COMMON + ` YOUR DIMENSION: behavior tree correctness. Files: ${ROOT}/behavior/behavior_tree.py, ${ROOT}/behavior/agent_behaviors.py, and ${ROOT}/simulation/manager.py (only for how the BT is ticked/reset). Hunt: SUCCESS/FAILURE/RUNNING propagation errors; is_running bookkeeping; Selector/Sequence/StatefulSelector semantics (fallback on failure? memory?); the simulate()/heuristic_function scoring math (check what values it can actually produce for the real tree and whether selection ever differs from first-child); sequences whose action nodes execute before the agent has physically traveled (state overwrites within one tick); nodes that mutate other agents or shared world_state; unreachable branches/dead nodes; emergency branches that can livelock (e.g. what happens at home when exhausted outside sleep hours); condition nodes that misfire for agents whose personalities match neither case.` },
  { key: 'sim-state', prompt: COMMON + ` YOUR DIMENSION: simulation loop, state management, scheduling, pathfinding, and the two-process architecture. Files: ${ROOT}/simulation/manager.py, ${ROOT}/simulation/entities.py, ${ROOT}/command.py, ${ROOT}/app.py, ${ROOT}/simulation/config.py (schedules/activities), ${ROOT}/static/map_data.json. Hunt: whether emit_daily_story can ever reach browser clients given which process calls it and where the SocketIO SERVER actually runs; the catch-all exception handling in command.py's loop and what one LLM failure at 03:00 does to the sim; overnight schedule windows like (22,1) vs the 'start<=hour<end' check; schedule/sleep-time interactions; order-dependent cross-agent mutation during a tick; claimed_spots/replanning gaps (including destinations of the form agent_<id>); BFS efficiency and correctness; time-step drift; random seeding/reproducibility; payload bloat in to_dict; money/wage magic numbers; import-time coupling (manager importing app).` },
  { key: 'llm-narrative', prompt: COMMON + ` YOUR DIMENSION: LLM integration, memory, and narrative generation. Files: ${ROOT}/simulation/llm_handler.py, ${ROOT}/simulation/narrative/narrative_system.py, ${ROOT}/simulation/memory/memory.py, ${ROOT}/simulation/entities.py (add_log/memory usage), ${ROOT}/simulation/manager.py (the 03:00 block), ${ROOT}/command.py. Hunt: missing timeouts/retries/rate-limit handling on requests.post; synchronous LLM calls blocking the tick loop (count calls per day, estimate stall); prompt construction brittleness and injection of raw logs; no output validation/schema; no caching; memory growth: is reset_daily_memories ever called, is reset_agent_diaries a no-op, and what does get_memories_for_day('Monday') return in week 2 (timestamps are bare day names); dead methods (is get_embedding called anywhere in the repo? grep it); API key handling and env var naming; token-budget growth of the compile_daily_story prompt over long runs.` },
  { key: 'quality-packaging', prompt: COMMON + ` YOUR DIMENSION: code quality, configuration, packaging, reproducibility, and the analyzer. Files: ${ROOT}/simulation/config.py, ${ROOT}/README.md, ${ROOT}/.gitignore, ${ROOT}/narrative_analyzer.py (all 1382 lines — skim systematically), repo root (what packaging/test/CI files are MISSING: requirements.txt, pyproject.toml, tests/, lockfiles). Hunt: README install instructions vs actual imports across the codebase (is 'requests' listed? 'python-socketio' client? 'openai'?); README claims that do not match the code (e.g. does the README describe py_trees nodes like QueryRAG/FollowPath/PickUpItem that do not exist in the repo? does it claim model-agnostic LLMHandler?); duplicated config (agent lists duplicated in narrative_analyzer vs config.py); duplicated coordinate-mapping logic between behavior/agent_behaviors.py (_get_agent_home_locations) and simulation/manager.py (_get_agent_home_target); magic numbers; personality trait dict merge overwrites; missing type hints/docstrings inconsistency; dead code and unused imports anywhere; zero tests; print-vs-logging; hardcoded SECRET_KEY/debug=True/CORS '*' in app.py.` },
  { key: 'frontend-runnability', prompt: COMMON + ` YOUR DIMENSION: frontend and end-to-end runnability. Files: ${ROOT}/static/script.js, ${ROOT}/static/index.html, ${ROOT}/static/style.css, ${ROOT}/app.py, ${ROOT}/command.py, ${ROOT}/README.md (usage section). Hunt: does the frontend listen for 'new_daily_story' and can that event ever arrive given emit_daily_story runs in the command.py process (trace which SocketIO object emits it and where the server actually runs); pause/resume event flow correctness end-to-end (browser -> server -> command client); full-log retransmission every 0.4s tick and DOM-rebuild cost in script.js; XSS risk if LLM/agent text is injected via innerHTML; CDN dependencies (Tailwind CDN in production); dead UI elements; missing error states when the sim client disconnects; anything that would make a fresh 'pip install' per README fail to run 'python command.py' or 'python app.py'.` },
]

const parsedArgs = typeof args === 'string' ? JSON.parse(args) : args
const LEAD_FINDINGS = (parsedArgs && parsedArgs.seeded) || []

phase('Audit')
log('Fanning out 5 dimension auditors + 1 research agent')

const researchP = agent(
  `You are preparing the academic-framing section for a research paper about a hybrid agent architecture: behavior-tree-driven autonomous agents in a simulated town whose factual event logs are turned into per-agent diaries and a town-wide story by an LLM (post-hoc narrative cognition), being upgraded to add episodic memory retrieval, reflection loops, utility-based BT selection, and async LLM integration. Use WebSearch/WebFetch to VERIFY every claim — accurate citations only (authors, year, venue). Collect: (1) related_work: Generative Agents (Park et al., UIST 2023), Voyager (Wang et al., 2023), AI Town (a16z), Project Sid / Altera (2024), AgentSociety or other 2024-2025 LLM-agent-simulation systems, classic game-AI hybrids (GOAP/Orkin FEAR, utility AI, ABL/Facade), Hilburn's BT/planner hybrid if verifiable — for each give a precise citation string, 2-sentence summary, and a 'difference_hook': what it does NOT do that a BT+LLM narrative hybrid does. (2) venues: check that AIIDE, IEEE CoG (Conference on Games), FDG, CHI, and relevant NeurIPS/ICLR workshops on LLM agents actually fit and are active in 2025-2026; note paper formats (AIIDE artifact/demo tracks). (3) metrics: evaluation metrics used by these papers for agent believability/coherence (e.g. Park et al.'s interview-based believability ranking, TrueSkill), narrative quality metrics, behavioral diversity metrics, scalability benchmarks. (4) novelty_angles: 3-6 crisp, defensible novelty claims for this system relative to the related work (be honest about what is NOT novel). (5) libraries: verify current maintenance status (2025-2026) of py_trees, esper (ECS), LiteLLM, instructor, pydantic v2, FastAPI, structlog, pytest, hypothesis, tenacity — one status_note each with the latest known version or activity level. Return via the structured schema only.`,
  { label: 'research:academic-framing', phase: 'Research', schema: RESEARCH_SCHEMA })

const finderResults = await parallel(FINDERS.map(f => () =>
  agent(f.prompt, { label: `audit:${f.key}`, phase: 'Audit', schema: FINDINGS_SCHEMA })
    .then(r => (r && r.findings ? r.findings.map(x => ({ ...x, source: f.key })) : []))))

const allFound = finderResults.filter(Boolean).flat()
log(`Auditors returned ${allFound.length} findings; merging with ${LEAD_FINDINGS.length} lead findings`)

phase('Merge')
const mergeInput = JSON.stringify({ lead: LEAD_FINDINGS, auditors: allFound })
const MERGE_SCHEMA = {
  type: 'object', required: ['findings'],
  properties: { findings: { type: 'array', items: { type: 'object',
    required: ['id', 'severity', 'file', 'title', 'description', 'fix'],
    properties: {
      id: { type: 'string' },
      severity: { type: 'string', enum: ['Critical', 'Major', 'Minor'] },
      file: { type: 'string' },
      line: { type: 'integer' },
      title: { type: 'string' },
      description: { type: 'string' },
      fix: { type: 'string' },
      sources: { type: 'array', items: { type: 'string' } },
    } } } } }

const merged = await agent(
  `Merge and dedupe these code-audit findings for the project at ${ROOT}. Two findings are duplicates if they describe the same root defect (same file + same mechanism), even if worded differently — merge them, keeping the clearest description, the union of insight, the most specific file/line, and the WORST severity claimed. Assign ids F01, F02, ... ordered by severity (Critical first). Keep every distinct defect — do not drop findings just because only one source reported them. Do not add new findings of your own. Findings JSON follows:\n${mergeInput}`,
  { label: 'merge:dedupe', phase: 'Merge', schema: MERGE_SCHEMA })

const canonical = merged.findings
log(`Canonical list: ${canonical.length} findings (${canonical.filter(f => f.severity === 'Critical').length} critical, ${canonical.filter(f => f.severity === 'Major').length} major)`)

phase('Verify')
const heavy = canonical.filter(f => f.severity !== 'Minor')
const minors = canonical.filter(f => f.severity === 'Minor')

const verifyPrompt = f =>
  `Adversarially verify this claimed defect in the codebase at ${ROOT}. Your job is to REFUTE it if you can: Read the cited file(s) and every file needed to trace the actual execution path, then decide. CONFIRMED = the code demonstrably behaves as described (name the exact lines proving it). PARTIAL = real defect but the description overstates/misstates mechanism or severity (supply corrected_title/corrected_description/corrected_severity). REFUTED = the claim is wrong (explain the code path that disproves it). Default to REFUTED if you cannot positively confirm. Architecture reminder: app.py is the SocketIO SERVER process; command.py is a socketio CLIENT process that imports the app module (so it holds an un-run Flask-SocketIO server object) and runs the manager loop. Do NOT read .env. The finding:\n${JSON.stringify(f)}`

const heavyVerified = await parallel(heavy.map(f => () =>
  agent(verifyPrompt(f), { label: `verify:${f.id}`, phase: 'Verify', schema: VERDICT_SCHEMA })
    .then(v => ({ ...f, verdict: v }))))

const chunks = []
for (let i = 0; i < minors.length; i += 8) chunks.push(minors.slice(i, i + 8))
const minorVerified = await parallel(chunks.map((chunk, ci) => () =>
  agent(
    `Adversarially verify EACH of these ${chunk.length} claimed Minor defects in the codebase at ${ROOT}. For each: Read the cited file(s), trace the code, and return a verdict keyed by the finding's id. CONFIRMED only if the code provably matches the claim; REFUTED if wrong; PARTIAL if real but misdescribed. Default to REFUTED when unsure. Do NOT read .env. Findings:\n${JSON.stringify(chunk)}`,
    { label: `verify:minors-${ci + 1}`, phase: 'Verify', schema: BATCH_SCHEMA })
    .then(r => chunk.map(f => {
      const v = r && r.verdicts ? r.verdicts.find(x => x.id === f.id) : null
      return { ...f, verdict: v ? { verdict: v.verdict, justification: v.justification } : { verdict: 'UNVERIFIED', justification: 'no verdict returned' } }
    }))))

const research = await researchP
const verified = [...heavyVerified.filter(Boolean), ...minorVerified.filter(Boolean).flat()]
const kept = verified.filter(f => f.verdict && f.verdict.verdict !== 'REFUTED')
log(`Verification done: ${kept.length}/${verified.length} findings survived`)

return { findings: verified, research }