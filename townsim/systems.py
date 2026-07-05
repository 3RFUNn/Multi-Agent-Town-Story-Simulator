"""Simulation systems: pure, ordered, deterministic per-tick logic.

Order per tick (see kernel.Kernel.step):
  Schedule -> Needs -> ActionExpiry -> Behavior -> Movement -> Interaction -> Economy

All cross-agent effects (conversations) are mediated here, at a single point,
fixing V1's mid-tick partner mutation (F14) and stale-interaction bugs (F15).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from townsim.agents.agent import AgentState
from townsim.agents.schedule import scheduled_activity
from townsim.behavior.blackboard import Blackboard, Scope
from townsim.behavior.core import Status, TickContext
from townsim.cognition.memory import MemoryEntry
from townsim.config.content import ACTIVITY_DATA
from townsim.config.models import SimConfig
from townsim.kernel.clock import SimTime
from townsim.kernel.events import Event
from townsim.kernel.rng import RngRegistry
from townsim.world.pathfinding import astar
from townsim.world.state import Conversation, WorldState

WORK_KINDS = ("work", "shift", "classes", "study")


@dataclass
class SysContext:
    world: WorldState
    cfg: SimConfig
    bb: Blackboard
    rng: RngRegistry
    now: SimTime
    events: list[Event] = field(default_factory=list)

    def emit(self, event_type: str, agent_id: str | None = None, **data) -> None:
        self.events.append(Event(tick=self.now.tick, day_index=self.now.day_index,
                                 type=event_type, agent_id=agent_id, data=data))

    def log(self, agent: AgentState, text: str, importance: float = 0.3,
            participants: tuple[str, ...] = (), location: str | None = None) -> None:
        """Agent-visible log + episodic memory + journal event. Consecutive
        duplicates are dropped (F19 — no more log floods)."""
        if text == agent._last_log_text:
            return
        agent._last_log_text = text
        agent.recent_log.appendleft({"t": self.now.label(), "text": text})
        agent.memory.add(MemoryEntry(
            text=text, day_index=self.now.day_index, tick=self.now.tick,
            importance=importance, location=location or self.world.town.place_at(agent.pos),
            participants=participants))
        self.emit("log", agent_id=agent.id, text=text)

    def tick_context(self, agent: AgentState) -> TickContext:
        return TickContext(
            agent=agent, world=self.world, cfg=self.cfg, now=self.now,
            rng=self.rng.stream("behavior"), bb=self.bb,
            emit=lambda event_type, **data: self.emit(event_type, agent_id=agent.id, **data),
            log=lambda text, importance=0.3, participants=(), location=None:
                self.log(agent, text, importance, tuple(participants), location),
        )


class ScheduleSystem:
    """What does each agent's schedule say right now? (wrap-aware — F17)"""

    def update(self, ctx: SysContext) -> None:
        for agent in ctx.world.agents_sorted():
            activity = scheduled_activity(agent, ctx.now)
            if activity != agent.current_activity:
                agent.current_activity = activity


class NeedsSystem:
    def update(self, ctx: SysContext) -> None:
        n = ctx.cfg.needs
        minutes = ctx.cfg.kernel.tick_minutes
        for agent in ctx.world.agents_sorted():
            needs = agent.needs
            sleeping = agent.action is not None and agent.action.kind == "sleep"
            working = agent.action is not None and agent.action.kind in WORK_KINDS
            if sleeping:
                needs.fatigue -= n.fatigue_recovery_sleeping * minutes
            else:
                needs.hunger += n.hunger_rate * minutes
                social_motivation = agent.spec.traits.get("social_motivation", 1.0)
                needs.social += n.social_rate * social_motivation * minutes
                if working:
                    work_ethic = max(0.5, agent.spec.traits.get("work_ethic", 1.0))
                    needs.fatigue += (n.fatigue_rate_working / work_ethic) * minutes
                else:
                    needs.fatigue += n.fatigue_rate * minutes
            needs.clamp()


class ActionExpirySystem:
    """End timed actions whose time is up; emit totals; reset trees."""

    def update(self, ctx: SysContext) -> None:
        for agent in ctx.world.agents_sorted():
            action = agent.action
            if agent.state != "doing_action" or action is None:
                continue
            if ctx.now.tick < action.until_tick:
                continue
            if action.earned:
                ctx.emit("wage_paid", agent_id=agent.id,
                         activity=action.activity, amount=round(action.earned, 2))
            ctx.emit("activity_ended", agent_id=agent.id, activity=action.activity,
                     kind=action.kind, duration_ticks=ctx.now.tick - action.started_tick)
            if action.kind == "sleep":
                ctx.log(agent, "Woke up feeling rested.", importance=0.25)
            agent.action = None
            agent.state = "idle"
            if agent.behavior_tree is not None:
                agent.behavior_tree.reset()


class BehaviorSystem:
    """Tick behavior trees for autonomous agents (idle or moving — moving
    agents stay reactive, so emergencies can redirect a walk)."""

    def update(self, ctx: SysContext) -> None:
        for agent in ctx.world.agents_sorted():
            if agent.state not in ("idle", "moving") or agent.behavior_tree is None:
                continue
            tick_ctx = ctx.tick_context(agent)
            status = agent.behavior_tree.tick(tick_ctx)
            agent.bt_path = list(tick_ctx.trace)
            if status == Status.FAILURE and agent.state == "idle":
                agent.current_goal = "At a loose end"
                agent.current_action = "Standing around"


class MovementSystem:
    """Resolve move intents to targets/paths and step agents one cell per
    tick. Dynamic collisions are handled with bounded retries + replanning
    for EVERY destination kind (V1 skipped agent-targets — F22)."""

    MAX_WAIT_RETRIES = 2
    MAX_TOTAL_RETRIES = 8

    def update(self, ctx: SysContext) -> None:
        rng = ctx.rng.stream("movement")
        for agent in ctx.world.agents_sorted():
            if agent.state != "moving":
                # A walk abandoned for ANY reason (arrival, preemption into an
                # action, interaction start) must not hold stale paths or cell
                # reservations for hours (R05).
                if agent.path or agent.path_target is not None:
                    agent.path = []
                    agent.path_target = None
                    agent.path_goal_key = None
                    agent.path_retries = 0
                ctx.world.release_reservations(agent.id)
                continue
            intent = agent.move_intent
            if intent is None:
                agent.state = "idle"
                continue

            goal_key = f"{intent.kind}:{intent.key}"
            if agent.path_goal_key != goal_key:
                self._clear_path(ctx, agent)
                agent.path_goal_key = goal_key

            if intent.kind == "agent":
                target_agent = ctx.world.agents.get(intent.key)
                if target_agent is None:
                    self._fail(ctx, agent)
                    continue
                # Replan if the target wandered far from where we were heading.
                if (agent.path_target is not None
                        and ctx.world.chebyshev(agent.path_target, target_agent.pos) > 3):
                    self._clear_path(ctx, agent)

            if not agent.path:
                if not self._plan(ctx, agent, rng):
                    continue

            self._step(ctx, agent)

    # -- helpers ----------------------------------------------------------
    def _clear_path(self, ctx: SysContext, agent: AgentState) -> None:
        ctx.world.release_reservations(agent.id)
        agent.path = []
        agent.path_target = None
        agent.path_retries = 0

    def _fail(self, ctx: SysContext, agent: AgentState) -> None:
        self._clear_path(ctx, agent)
        agent.path_failed = True
        agent.path_goal_key = None
        agent.move_intent = None   # R06: leave no half-armed intent behind
        agent.state = "idle"
        ctx.emit("path_failed", agent_id=agent.id)

    def _plan(self, ctx: SysContext, agent: AgentState, rng) -> bool:
        intent = agent.move_intent
        assert intent is not None
        target: tuple[int, int] | None = None

        if intent.kind == "place":
            coords = ctx.world.resolve_place_coords(intent.key, agent)
            if agent.pos in coords:
                self._arrive(ctx, agent)
                return False
            free = ctx.world.free_cells_in(coords, for_agent=agent.id)
            if free:
                target = rng.choice(sorted(free))
        elif intent.kind == "agent":
            other = ctx.world.agents.get(intent.key)
            if other is not None:
                target = self._adjacent_free_cell(ctx, other.pos, agent)

        if target is None:
            agent.path_retries += 1
            if agent.path_retries > self.MAX_TOTAL_RETRIES:
                self._fail(ctx, agent)
            return False

        blocked = frozenset(ctx.world.occupied_cells(exclude=agent.id))
        path = astar(ctx.world.town, agent.pos, target, blocked)
        if path is None:
            path = astar(ctx.world.town, agent.pos, target)  # ignore agents, sort it out en route
        if path is None:
            self._fail(ctx, agent)
            return False
        ctx.world.reserve(target, agent.id)
        agent.path = path
        agent.path_target = target
        return True

    def _adjacent_free_cell(self, ctx: SysContext, around: tuple[int, int],
                            agent: AgentState) -> tuple[int, int] | None:
        occupied = ctx.world.occupied_cells(exclude=agent.id)
        candidates = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == dy == 0:
                    continue
                cell = (around[0] + dx, around[1] + dy)
                if (ctx.world.town.walkable(*cell) and cell not in occupied
                        and ctx.world.reservations.get(cell, agent.id) == agent.id):
                    candidates.append(cell)
        if agent.pos in candidates or ctx.world.chebyshev(agent.pos, around) == 1:
            return agent.pos  # already adjacent
        return min(candidates) if candidates else None

    def _step(self, ctx: SysContext, agent: AgentState) -> None:
        if not agent.path:
            self._arrive(ctx, agent)
            return
        next_cell = agent.path[0]
        if next_cell == agent.pos:
            agent.path.pop(0)
            self._step(ctx, agent)
            return
        occupied = ctx.world.occupied_cells(exclude=agent.id)
        if next_cell in occupied:
            agent.path_retries += 1
            if agent.path_retries > self.MAX_TOTAL_RETRIES:
                self._fail(ctx, agent)
            elif agent.path_retries > self.MAX_WAIT_RETRIES:
                # Stop waiting: replan around the blocker next tick (F22).
                ctx.world.release_reservations(agent.id)
                agent.path = []
                agent.path_target = None
            return
        ctx.world.move_agent(agent, next_cell)
        agent.path.pop(0)
        agent.path_retries = 0
        if not agent.path:
            self._arrive(ctx, agent)

    def _arrive(self, ctx: SysContext, agent: AgentState) -> None:
        intent = agent.move_intent
        ctx.world.release_reservations(agent.id)
        agent.path = []
        agent.path_target = None
        agent.path_retries = 0
        if intent is not None and intent.kind == "place":
            coords = ctx.world.resolve_place_coords(intent.key, agent)
            if agent.pos in coords:
                agent.state = "idle"   # BT's location guard takes over next tick
                agent.move_intent = None
                agent.path_goal_key = None
                ctx.emit("agent_moved_to", agent_id=agent.id, place=intent.key,
                         x=agent.x, y=agent.y)
        # kind == "agent": ApproachAndChat checks adjacency and requests the
        # conversation; the interaction system validates it (F16).


class InteractionSystem:
    """Single mediation point for conversations (F14/F15/F16)."""

    def update(self, ctx: SysContext) -> None:
        self._process_requests(ctx)
        self._tick_conversations(ctx)

    def _process_requests(self, ctx: SysContext) -> None:
        rng = ctx.rng.stream("interaction")
        requests, ctx.world.conversation_requests = ctx.world.conversation_requests, []
        handled: set[frozenset] = set()
        for initiator_id, partner_id in requests:
            pair = frozenset((initiator_id, partner_id))
            if pair in handled:      # symmetric same-tick request already served
                continue
            initiator = ctx.world.agents.get(initiator_id)
            partner = ctx.world.agents.get(partner_id)
            if initiator is None or partner is None:
                continue
            # R07: an initiator who just entered a conversation this tick was
            # not rebuffed — drop the request silently.
            if initiator.state == "interacting":
                continue
            adjacency = ctx.cfg.interaction.adjacency_max_chebyshev
            # R17: a partner still WALKING toward the initiator counts as
            # available — mutual approaches must not rebuff each other.
            partner_available = (partner.state == "idle"
                                 or (partner.state == "moving"
                                     and partner.social_target == initiator_id))
            valid = (initiator.state == "idle" and partner_available
                     and ctx.world.chebyshev(initiator.pos, partner.pos) <= adjacency)
            if not valid:
                ctx.bb.set(Scope.AGENT, initiator_id, "social_rebuffed", True)
                ctx.log(initiator, f"{partner.spec.name} seemed busy, so I let it go.",
                        importance=0.2, participants=(partner_id,))
                continue
            handled.add(pair)
            if partner.state == "moving":
                ctx.world.release_reservations(partner.id)
                partner.path = []
                partner.path_target = None
                partner.path_goal_key = None
                partner.path_retries = 0
                partner.move_intent = None
                partner.state = "idle"
            duration = rng.randint(ctx.cfg.interaction.conversation_min_ticks,
                                   ctx.cfg.interaction.conversation_max_ticks)
            location = ctx.world.town.place_at(initiator.pos)
            # R03/R19: salient = the pair's first conversation today, within
            # BOTH participants' daily dialogue budgets.
            budget = ctx.cfg.interaction.daily_dialogue_budget
            salient = (pair not in ctx.world.today_pairs
                       and initiator.daily_dialogues_used < budget
                       and partner.daily_dialogues_used < budget)
            ctx.world.today_pairs.add(pair)
            conv = ctx.world.new_conversation(initiator_id, partner_id, duration,
                                              ctx.now.tick, location, salient)
            for me, other in ((initiator, partner), (partner, initiator)):
                me.state = "interacting"
                me.conversation_id = conv.id
                me.interacting_with = other.id
                me.social_target = None
                me.move_intent = None
                me.current_goal = f"Chatting with {other.spec.name}"
                me.current_action = "Deep in conversation"
                ctx.bb.join_group(me.id, conv.id)
            ctx.emit("conversation_started", agent_id=initiator_id,
                     partner=partner_id, duration=duration, location=location,
                     salient=salient)
            ctx.log(initiator, f"Started chatting with {partner.spec.name}.",
                    importance=0.5, participants=(partner_id,), location=location)
            ctx.log(partner, f"{initiator.spec.name} came over for a chat.",
                    importance=0.5, participants=(initiator_id,), location=location)

    def _tick_conversations(self, ctx: SysContext) -> None:
        rng = ctx.rng.stream("interaction")
        finished: list[Conversation] = []
        for conv in list(ctx.world.conversations.values()):
            a = ctx.world.agents.get(conv.a)
            b = ctx.world.agents.get(conv.b)
            if a is None or b is None or a.state != "interacting" or b.state != "interacting":
                finished.append(conv)
                continue
            conv.remaining_ticks -= 1
            if conv.remaining_ticks <= 0:
                finished.append(conv)
        for conv in finished:
            self._end_conversation(ctx, conv, rng)

    def _end_conversation(self, ctx: SysContext, conv: Conversation, rng) -> None:
        ctx.world.conversations.pop(conv.id, None)
        a = ctx.world.agents.get(conv.a)
        b = ctx.world.agents.get(conv.b)
        quality = rng.uniform(0.3, 1.0)
        for me, other_id in ((a, conv.b), (b, conv.a)):
            if me is None:
                continue
            other = ctx.world.agents.get(other_id)
            me.needs.social -= ctx.cfg.needs.conversation_social_relief * quality
            me.needs.clamp()
            rel = me.relationship_with(other_id)
            rel.affinity = min(100.0, rel.affinity + 3.0 * quality)
            rel.familiarity = min(100.0, rel.familiarity + 5.0)
            rel.valence = quality * 2 - 1
            if conv.salient:   # R19: budget charged to BOTH, and only when
                me.daily_dialogues_used += 1   # an LLM dialogue is rendered
            other_name = other.spec.name if other else other_id
            ctx.log(me, f"Had a nice talk with {other_name}.",
                    importance=0.45 + 0.2 * quality, participants=(other_id,),
                    location=conv.location)
            self._release(ctx, me)
        ctx.emit("relationship_changed", agent_id=conv.a, partner=conv.b,
                 quality=round(quality, 2))
        ctx.emit("conversation_ended", agent_id=conv.a, partner=conv.b,
                 duration=ctx.now.tick - conv.started_tick, quality=round(quality, 2),
                 location=conv.location, salient=conv.salient)

    def _release(self, ctx: SysContext, agent: AgentState) -> None:
        """Symmetric teardown (F15): clear ALL interaction state and reset."""
        ctx.bb.leave_group(agent.id)
        agent.clear_transient()
        agent.state = "idle"
        if agent.behavior_tree is not None:
            agent.behavior_tree.reset()


class EconomySystem:
    """Wages accrue per tick while actually working at the right place, at
    per-HOUR rates from config (F32 unit fix); paid out at action end."""

    def update(self, ctx: SysContext) -> None:
        econ = ctx.cfg.economy
        hours_per_tick = ctx.cfg.kernel.tick_minutes / 60.0
        for agent in ctx.world.agents_sorted():
            action = agent.action
            if agent.state != "doing_action" or action is None:
                continue
            if action.kind not in ("work", "shift", "classes"):
                continue
            location = ACTIVITY_DATA[action.activity]["location"]
            if not ctx.world.is_at_place(agent, location):
                continue
            rate = {"work": econ.wage_office_per_hour,
                    "shift": econ.wage_shift_per_hour,
                    "classes": econ.wage_classes_per_hour}[action.kind]
            pay = rate * hours_per_tick
            agent.wallet.money += pay
            action.earned += pay


def default_systems() -> list:
    return [ScheduleSystem(), NeedsSystem(), ActionExpirySystem(), BehaviorSystem(),
            MovementSystem(), InteractionSystem(), EconomySystem()]
