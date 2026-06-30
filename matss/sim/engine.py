"""The deterministic, event-sourced simulation engine (Tier-1).

This is the integration centerpiece. Each :meth:`SimulationEngine.tick`:

1. advances the deterministic clock (+``minutes_per_tick`` simulated minutes);
2. updates each agent's scheduled activity (data-driven, sleep-aware);
3. ticks idle agents' behavior trees (which set movement/action *intent*);
4. resolves movement with the :class:`~matss.pathfinding.PathPlanner`
   (A* + flow-field), handling contention and conversations;
5. advances in-progress actions/interactions and pays wages;
6. emits granular domain events to the bus + log, then one ``TICK_COMPLETED``
   event carrying the canonical world snapshot and its ``state_hash``.

At the configured narrative hour it generates the previous day's diaries and
town story strictly post-hoc (Tier-2), via the bounded cognition queue.

**Determinism contract.** Every stochastic draw flows through the run's seeded
:class:`~matss.determinism.RandomSource` via stable, named sub-streams; agents
are processed in a seeded-shuffled but reproducible order; nothing reads the wall
clock. Two runs with the same ``seed`` + content therefore emit an identical
per-tick ``state_hash`` chain — the property the prototype could not offer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from ..behavior.builder import create_agent_bt
from ..behavior.tree import Node
from ..config.loader import Content
from ..determinism import RandomSource, state_hash
from ..domain.agent import Agent
from ..domain.enums import AgentState, EventType, Need
from ..domain.events import Event
from ..domain.world import DAYS, WorldState
from ..observability import METRICS, TRACER, get_logger
from ..ports import EventBus, EventLog, LLMProvider
from ..runtime import DecisionContext

_log = get_logger("engine")

Coord = Tuple[int, int]
_WORK_TOKENS = ("work", "shift", "classes")


@dataclass
class EngineConfig:
    """Composition config for :class:`SimulationEngine` (built by ``build_engine``)."""

    seed: int
    content: Content
    event_log: EventLog
    event_bus: EventBus
    planner: Any                 # matss.pathfinding.PathPlanner
    memory: Any                  # matss.memory.MemoryStream
    narrative: Any               # matss.cognition.NarrativeSystem
    cognition_queue: Any         # matss.cognition.CognitionQueue
    llm_provider: LLMProvider
    enable_narrative: bool = True
    hierarchical_narrative: bool = False
    record_observations_in_memory: bool = True


class SimulationEngine:
    """The authoritative, deterministic Tier-1 simulation."""

    def __init__(self, config: EngineConfig) -> None:
        self.cfg = config
        self.content = config.content
        self.rng = RandomSource(config.seed)
        self.log = config.event_log
        self.bus = config.event_bus
        self.planner = config.planner
        self.memory = config.memory
        self.narrative = config.narrative
        self.queue = config.cognition_queue

        self.params: Dict[str, Any] = config.content.sim_params
        start_time = tuple(self.params.get("start_time", [8, 0]))
        self.minutes_per_tick = int(self.params.get("minutes_per_tick", 2))
        self.narrative_hour = int(self.params.get("narrative_hour", 3))

        self.world = self._init_world(start_time)
        self._trees: Dict[str, Node] = {
            a.id: create_agent_bt(a, self.params) for a in self.world.agents.values()
        }
        # Tick at which each simulated day began; index == day_index.
        self._day_start_ticks: List[int] = [0]
        self.state_hashes: List[str] = []
        self._started = False

    # -- construction ----------------------------------------------------------

    def _init_world(self, start_time: Tuple[int, int]) -> WorldState:
        agents: Dict[str, Agent] = {}
        for d in self.content.agent_defs:
            lo, hi = d.starting_money_range
            money = self.rng.stream(f"spawn:{d.id}").randint(int(lo), int(hi))
            agents[d.id] = Agent(d, money=money, relationships=self.content.relationships_for(d.id))
        return WorldState(
            nav=self.content.nav,
            places=self.content.places,
            # Copy so ad-hoc activities (take_a_short_rest/eat_at_cafe) registered
            # at runtime never mutate the shared content catalog.
            activity_data=dict(self.content.activity_data),
            agents=agents,
            time=(int(start_time[0]), int(start_time[1])),
            day_index=0,
            tick=0,
            sim_minute=0,
        )

    # -- public driving API ----------------------------------------------------

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        for a in self.world.agent_list():
            self._record(self._mk_event(EventType.AGENT_SPAWNED, agent_id=a.id,
                                        payload={"pos": list(a.pos), "money": a.money}))
        self._record(self._mk_event(EventType.SIM_STARTED,
                                    payload={"seed": self.cfg.seed,
                                             "agents": [a.id for a in self.world.agent_list()],
                                             "content": self.content.meta.get("name", "")}))
        # Emit an initial frame so subscribers have a baseline snapshot.
        self._emit_tick_completed()

    def run(self, ticks: int) -> List[str]:
        """Run ``ticks`` ticks; return the list of per-tick state hashes."""
        if not self._started:
            self.start()
        for _ in range(ticks):
            self.tick()
        return self.state_hashes

    def run_until_day(self, day_index: int, max_ticks: int = 2_000_000) -> List[str]:
        """Run until ``world.day_index`` reaches ``day_index`` (safety-bounded)."""
        if not self._started:
            self.start()
        guard = 0
        while self.world.day_index < day_index and guard < max_ticks:
            self.tick()
            guard += 1
        return self.state_hashes

    # -- the tick --------------------------------------------------------------

    def tick(self) -> str:
        if not self._started:
            self.start()
        with TRACER.span("tick", tick=self.world.tick + 1):
            day_rolled = self._advance_time()
            self._update_schedules()

            order = self.world.agent_list()
            self.rng.shuffle("tick_order", order)

            claimed: set = {a.pos for a in self.world.agents.values()}

            for agent in order:
                self._update_needs(agent)
                if agent.state in (AgentState.DOING_ACTION, AgentState.INTERACTING):
                    self._advance_action(agent)
                    continue
                if agent.state == AgentState.IDLE:
                    self._run_bt(agent)
                if agent.state == AgentState.MOVING:
                    self._resolve_movement(agent, claimed)

            if day_rolled and self.cfg.enable_narrative:
                self._maybe_generate_narrative()

            METRICS.incr("ticks_total")
            h = self._emit_tick_completed()
            return h

    def _advance_time(self) -> bool:
        hour, minute = self.world.time
        minute += self.minutes_per_tick
        rolled = False
        if minute >= 60:
            minute %= 60
            hour += 1
            if hour >= 24:
                hour %= 24
                self.world.day_index += 1
                self._day_start_ticks.append(self.world.tick + 1)
                for tree in self._trees.values():
                    tree.reset()
                rolled = True
                self._record(self._mk_event(
                    EventType.DAY_ROLLOVER,
                    payload={"day_index": self.world.day_index,
                             "day_of_week": DAYS[self.world.day_index % 7]}))
        self.world.time = (hour, int(minute))
        self.world.tick += 1
        self.world.sim_minute += self.minutes_per_tick
        return rolled

    # -- schedules + needs (ported, deterministic) -----------------------------

    def _is_sleep_time(self, agent: Agent, hour: int) -> bool:
        if agent.has_personality("lazy"):
            return hour >= 22 or hour < 10
        if agent.has_personality("workaholic"):
            return 1 <= hour < 6
        if agent.has_personality("fitness_enthusiast"):
            return hour >= 22 or hour < 6
        return hour >= 23 or hour < 8

    def _update_schedules(self) -> None:
        hour = self.world.hour
        day = self.world.day_of_week
        for agent in self.world.agent_list():
            if agent.current_activity == "socialize_at_park" and hour >= 22:
                agent.state = AgentState.IDLE
                agent.current_activity = None
            if agent.state in (AgentState.INTERACTING, AgentState.MOVING):
                continue
            if self._is_sleep_time(agent, hour):
                agent.current_activity = "sleep_at_home"
                continue
            activity = self.content.schedule_activity(agent.defn.schedule_template, day, hour)
            agent.current_activity = activity

    def _update_needs(self, agent: Agent) -> None:
        p = self.params.get("needs", {})
        hunger_inc = p.get("hunger_increase", 0.25)
        social_inc = p.get("social_increase", 0.15)
        energy_inc = p.get("energy_increase", 0.1)
        work_energy_inc = p.get("work_energy_increase", 0.2)
        sleep_energy_dec = p.get("sleep_energy_decrease", 0.8)
        needs = agent.needs

        if agent.current_activity != "sleep_at_home":
            needs[Need.HUNGER] = min(100.0, needs[Need.HUNGER] + hunger_inc)
            social_motivation = agent.trait("social_motivation", 1.0)
            needs[Need.SOCIAL] = min(100.0, needs[Need.SOCIAL] + social_inc * social_motivation)

        is_working = "work" in (agent.current_activity or "")
        if agent.current_activity == "sleep_at_home":
            needs[Need.ENERGY] = max(0.0, needs[Need.ENERGY] - sleep_energy_dec)
        elif not is_working:
            needs[Need.ENERGY] = min(100.0, needs[Need.ENERGY] + energy_inc)
        else:
            work_ethic = agent.trait("work_ethic", 1.0) or 1.0
            needs[Need.ENERGY] = min(100.0, needs[Need.ENERGY] + work_energy_inc / work_ethic)

    # -- action / interaction progression --------------------------------------

    def _advance_action(self, agent: Agent) -> None:
        agent.action_duration -= 1
        self._maybe_earn_wage(agent)
        if agent.action_duration > 0:
            return
        if agent.state == AgentState.INTERACTING and agent.interacting_with:
            other = self.world.agents.get(agent.interacting_with)
            if other is not None:
                other.state = AgentState.IDLE
                other.interacting_with = None
                self._trees[other.id].reset()
            self._observe(agent, "Finished my conversation.")
            self._record(self._mk_event(EventType.INTERACTION_FINISHED, agent_id=agent.id,
                                        payload={"with": agent.interacting_with}))
        else:
            self._record(self._mk_event(EventType.ACTIVITY_FINISHED, agent_id=agent.id,
                                        payload={"activity": agent.current_activity}))
        agent.state = AgentState.IDLE
        agent.interacting_with = None
        self._trees[agent.id].reset()

    def _maybe_earn_wage(self, agent: Agent) -> None:
        if agent.state != AgentState.DOING_ACTION:
            return
        activity = agent.current_activity or ""
        if not any(tok in activity for tok in _WORK_TOKENS):
            return
        data = self.world.activity_data.get(activity) or self.content.activity_data.get(activity, {})
        required = data.get("location") or agent.defn.work_location
        place = self.world.places.get(required) if required else None
        if place is None or not place.contains(agent.x, agent.y):
            return
        wages = self.params.get("work_wage", {"shift": 0.8, "classes": 0.3, "default": 0.5})
        if "shift" in activity:
            wage = wages.get("shift", 0.8)
        elif "classes" in activity:
            wage = wages.get("classes", 0.3)
        else:
            wage = wages.get("default", 0.5)
        agent.money += wage
        self._record(self._mk_event(EventType.WORKED, agent_id=agent.id,
                                    payload={"wage": wage, "balance": agent.money}))

    # -- behavior tree ---------------------------------------------------------

    def _run_bt(self, agent: Agent) -> None:
        ctx = DecisionContext(
            agent=agent,
            world=self.world,
            content=self.content,
            rng=self.rng,
            emit=lambda event_type, **payload: self._emit_agent_event(agent, event_type, payload),
            observe=lambda text: self._observe(agent, text),
        )
        self._trees[agent.id].tick(ctx)

    # -- movement (ported, planner-backed) -------------------------------------

    def _resolve_target(self, agent: Agent, claimed: set) -> Optional[Coord]:
        dest = agent.destination_name
        if not dest:
            return None
        others = self.world.occupied_positions(exclude=agent.id)
        avoid = claimed | others
        if dest.startswith("agent_"):
            target = self.world.agents.get(dest.split("_", 1)[1])
            if target is None:
                return None
            return self.planner.nearest_free(target.pos, avoid)
        if dest.endswith("_home") or "home" in dest:
            return self.planner.nearest_free(agent.defn.home_pos, avoid)
        place = self.world.places.get(dest)
        if place is None:
            return None
        available = sorted(c for c in place.coords
                           if c not in claimed and self.world.nav.is_traversable(*c))
        if not available:
            return None
        return self.rng.stream(f"move:{agent.id}").choice(available)

    def _resolve_movement(self, agent: Agent, claimed: set) -> None:
        if not agent.path or agent.path_index >= len(agent.path):
            target = self._resolve_target(agent, claimed)
            if target is None:
                agent.state = AgentState.IDLE
                self._trees[agent.id].reset()
                if agent.destination_name:
                    self._observe(agent, f"I can't go to {agent.destination_name}, there's no space.")
                return
            claimed.add(target)
            others = frozenset(self.world.occupied_positions(exclude=agent.id))
            path = self.planner.plan(agent.pos, target, blocked=others)
            if not path:
                agent.state = AgentState.IDLE
                self._trees[agent.id].reset()
                self._observe(agent, f"I can't find a path to {agent.destination_name}.")
                claimed.discard(target)
                return
            agent.path = path
            agent.path_index = 1  # path[0] is the current cell

        if agent.path and agent.path_index < len(agent.path):
            next_pos = tuple(agent.path[agent.path_index])
            occ_now = self.world.occupied_positions(exclude=agent.id)
            if next_pos in occ_now:
                # Transient block: replan once around current occupants.
                goal = tuple(agent.path[-1])
                replanned = self.planner.plan(agent.pos, goal, blocked=frozenset(occ_now))
                if replanned and len(replanned) > 1 and tuple(replanned[1]) not in occ_now:
                    agent.path = replanned
                    agent.x, agent.y = tuple(replanned[1])
                    agent.path_index = 2
                    self._record(self._mk_event(EventType.AGENT_MOVED, agent_id=agent.id,
                                                payload={"to": [agent.x, agent.y]}))
                # else: wait this tick.
            else:
                agent.x, agent.y = next_pos
                agent.path_index += 1
                self._record(self._mk_event(EventType.AGENT_MOVED, agent_id=agent.id,
                                            payload={"to": [agent.x, agent.y]}))

            if agent.path_index >= len(agent.path):
                agent.path = []
                self._on_arrival(agent)

    def _on_arrival(self, agent: Agent) -> None:
        if agent.interacting_with:
            other = self.world.agents.get(agent.interacting_with)
            if other is not None and (other.state == AgentState.IDLE
                                      or other.interacting_with == agent.id):
                lo, hi = self.params.get("interaction_duration_range", [15, 25])
                dur = self.rng.stream(f"interaction:{agent.id}").randint(int(lo), int(hi))
                agent.state = AgentState.INTERACTING
                other.state = AgentState.INTERACTING
                other.interacting_with = agent.id
                agent.action_duration = dur
                other.action_duration = dur
                agent.current_goal = f"Chatting with {other.name}"
                other.current_goal = f"Chatting with {agent.name}"
                self._record(self._mk_event(EventType.INTERACTION_STARTED, agent_id=agent.id,
                                            payload={"with": other.id, "duration": dur}))
            else:
                agent.state = AgentState.IDLE
                agent.interacting_with = None
                self._observe(agent, "They seemed busy, so I decided not to interrupt.")
        else:
            agent.state = AgentState.IDLE
        self._trees[agent.id].reset()

    # -- Tier-2 narrative (post-hoc, via the bounded cognition queue) ----------

    def _maybe_generate_narrative(self) -> None:
        d = self.world.day_index
        prev_index = d - 1
        if prev_index < 0:
            return
        prev_day = DAYS[prev_index % 7]
        day_number = prev_index + 1
        start = self._day_start_ticks[prev_index] if prev_index < len(self._day_start_ticks) else 0
        end = self._day_start_ticks[d] if d < len(self._day_start_ticks) else self.world.tick

        from ..cognition.queue import CognitionJob

        # Enqueue one diary job per agent (bounded queue models backpressure).
        for agent in self.world.agent_list():
            mems = [m for m in self.memory.all(agent.id) if start <= m.tick < end]
            self.queue.submit(CognitionJob(
                id=f"diary:{day_number}:{agent.id}",
                importance=float(len(mems)),
                kind="diary",
                payload={"agent_id": agent.id, "memories": mems},
            ))

        diaries: Dict[str, str] = {}

        def worker(job: CognitionJob) -> Tuple[str, str]:
            aid = job.payload["agent_id"]
            agent_def = self.content.agent_def(aid)
            text = self.narrative.write_diary(agent_def, prev_day, day_number, job.payload["memories"])
            return aid, text

        for aid, text in self.queue.process_all(worker):
            diaries[aid] = text
            self._record(self._mk_event(EventType.DIARY_WRITTEN, agent_id=aid,
                                        payload={"day": prev_day, "day_number": day_number,
                                                 "text": text}))

        if diaries:
            groups = self._narrative_groups() if self.cfg.hierarchical_narrative else None
            story = self.narrative.compile_town_story(
                diaries, prev_day, day_number,
                groups=groups, hierarchical=self.cfg.hierarchical_narrative)
            self._record(self._mk_event(EventType.STORY_COMPILED,
                                        payload={"day": prev_day, "day_number": day_number,
                                                 "text": story}))
            METRICS.incr("stories_compiled")

    def _narrative_groups(self) -> List[List[str]]:
        ids = sorted(self.world.agents)
        size = 4
        return [ids[i:i + size] for i in range(0, len(ids), size)] or [ids]

    # -- event plumbing --------------------------------------------------------

    def _mk_event(self, event_type: str, agent_id: Optional[str] = None,
                  payload: Optional[Dict[str, Any]] = None) -> Event:
        return Event(
            type=event_type,
            tick=self.world.tick,
            sim_minute=self.world.sim_minute,
            day_index=self.world.day_index,
            day_of_week=self.world.day_of_week,
            agent_id=agent_id,
            payload=payload or {},
        )

    def _emit_agent_event(self, agent: Agent, event_type: str, payload: Dict[str, Any]) -> None:
        self._record(self._mk_event(event_type, agent_id=agent.id, payload=dict(payload)))

    def _observe(self, agent: Agent, text: str) -> None:
        if self.cfg.record_observations_in_memory:
            self.memory.add_observation(agent.id, text, self.world.tick, self.world.day_of_week)

    def _record(self, event: Event) -> None:
        stamped = self.log.append(event)
        self.bus.publish(stamped)

    def _emit_tick_completed(self) -> str:
        snapshot = self.world.to_canonical()
        h = state_hash(self.world)
        self.state_hashes.append(h)
        self._record(self._mk_event(
            EventType.TICK_COMPLETED,
            payload={"tick": self.world.tick, "state_hash": h, "snapshot": snapshot}))
        return h
