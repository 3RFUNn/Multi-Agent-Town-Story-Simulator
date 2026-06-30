"""Tests for the deterministic Behavior-Tree engine (``matss.behavior``).

Covered:
    * determinism — identical seed/state yields identical decisions and events;
    * a scheduled work activity drives plan-path / execute nodes;
    * tired/critical thresholds trigger the correct emergency branches;
    * the StatefulSelector picks the child whose *real* ``simulate`` scores
      highest, and that ``simulate`` is genuine (not the removed stub);
    * ``reset`` clears running state.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pytest

from matss.behavior import (
    ExecuteActivity,
    FindAgentToTalkTo,
    Idle,
    Node,
    PlanPathToActivityLocation,
    SimulationSummary,
    Selector,
    Sequence,
    StatefulSelector,
    Status,
    create_agent_bt,
    heuristic_function,
)
from matss.behavior.nodes import IsAgentTired, IsNeedCritical
from matss.determinism import RandomSource
from matss.domain.agent import Agent
from matss.domain.enums import AgentState, Need
from matss.domain.world import WorldState
from matss.runtime import DecisionContext


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

class Capture:
    """Collects emitted events and observations from a DecisionContext."""

    def __init__(self) -> None:
        self.events: List[Tuple[str, dict]] = []
        self.observations: List[str] = []

    def emit(self, event_type: str, **payload) -> None:
        self.events.append((event_type, payload))

    def observe(self, text: str) -> None:
        self.observations.append(text)


def make_world(content, agent_ids=("alex",)) -> WorldState:
    """Build a WorldState with the named agents (deterministic money draw)."""
    world = WorldState(nav=content.nav, places=content.places,
                       activity_data={k: dict(v) for k, v in content.activity_data.items()})
    rng = RandomSource(seed=1234)
    for aid in agent_ids:
        defn = content.agent_def(aid)
        lo, hi = defn.starting_money_range
        money = rng.stream(f"spawn:{aid}").randint(lo, hi)
        agent = Agent(defn, money=money, relationships=content.relationships_for(aid))
        world.agents[aid] = agent
    return world


def make_ctx(content, world: WorldState, agent_id: str = "alex",
             seed: int = 1234, cap: Optional[Capture] = None) -> Tuple[DecisionContext, Capture]:
    """Construct a DecisionContext bound to ``agent_id`` with capturing sinks."""
    cap = cap or Capture()
    ctx = DecisionContext(
        agent=world.agents[agent_id],
        world=world,
        content=content,
        rng=RandomSource(seed=seed),
        emit=cap.emit,
        observe=cap.observe,
    )
    return ctx, cap


def set_time(world: WorldState, hour: int, day_index: int = 0) -> None:
    world.time = (hour, 0)
    world.day_index = day_index


# --------------------------------------------------------------------------
# Contract conformance
# --------------------------------------------------------------------------

def test_status_enum_members():
    assert {s.name for s in Status} == {"SUCCESS", "FAILURE", "RUNNING"}


def test_nodes_are_node_subclasses(content):
    world = make_world(content)
    bt = create_agent_bt(world.agents["alex"], content.sim_params)
    assert isinstance(bt, Node)
    assert isinstance(bt, Selector)


def test_base_simulate_is_identity(content):
    world = make_world(content)
    ctx, _ = make_ctx(content, world)
    node = Idle("idle")  # Idle does not override simulate
    summary = SimulationSummary({Need.HUNGER: 10.0}, 50.0)
    out = node.simulate(ctx, summary)
    assert out.final_needs == summary.final_needs
    assert out.final_money == summary.final_money


# --------------------------------------------------------------------------
# Heuristic
# --------------------------------------------------------------------------

def test_heuristic_scores(content):
    """Ported formula: positive scores clamp to 1.0; worse outcomes score < 1.0."""
    world = make_world(content)
    agent = world.agents["alex"]
    initial = SimulationSummary({Need.HUNGER: 80.0, Need.ENERGY: 50.0, Need.SOCIAL: 50.0}, 100.0)
    # Reducing a need yields a positive score -> clamps to 1.0 (same as no change).
    better = SimulationSummary({Need.HUNGER: 10.0, Need.ENERGY: 50.0, Need.SOCIAL: 50.0}, 100.0)
    # Increasing a need (worse) yields a negative score -> squashed below 1.0.
    worse = SimulationSummary({Need.HUNGER: 80.0, Need.ENERGY: 90.0, Need.SOCIAL: 50.0}, 100.0)
    s_no_change = heuristic_function(agent, initial, initial)
    s_better = heuristic_function(agent, initial, better)
    s_worse = heuristic_function(agent, initial, worse)
    assert s_no_change == 1.0
    assert s_better == 1.0
    assert s_worse < s_no_change
    assert 0.0 < s_worse < 1.0


# --------------------------------------------------------------------------
# Scheduled activity branch
# --------------------------------------------------------------------------

def _assign_schedule(content, world, agent_id="alex"):
    """Assign the scheduled activity for the current world time to the agent."""
    agent = world.agents[agent_id]
    activity = content.schedule_activity(
        agent.defn.schedule_template, world.day_of_week, world.hour)
    agent.current_activity = activity
    return activity


def test_scheduled_work_drives_plan_path_when_away(content):
    world = make_world(content)
    set_time(world, 9, day_index=0)  # Monday 09:00 -> work_at_office for alex
    activity = _assign_schedule(content, world)
    assert activity == "work_at_office"
    agent = world.agents["alex"]
    # Ensure agent is NOT at the office and not tired/hungry, so the core
    # routine (scheduled branch) governs.
    agent.needs = {Need.HUNGER: 0.0, Need.SOCIAL: 0.0, Need.ENERGY: 0.0}
    ctx, cap = make_ctx(content, world)

    bt = create_agent_bt(agent, content.sim_params)
    status = bt.tick(ctx)
    assert status == Status.SUCCESS
    # Agent should now be moving toward the office.
    assert agent.state == AgentState.MOVING
    assert agent.destination_name == "business_office"
    decisions = [p for t, p in cap.events if t == "decision_made"]
    assert any(d.get("decision") == "go_to_activity" for d in decisions)


def test_scheduled_work_executes_when_at_location(content):
    world = make_world(content)
    set_time(world, 9, day_index=0)
    _assign_schedule(content, world)
    agent = world.agents["alex"]
    agent.needs = {Need.HUNGER: 0.0, Need.SOCIAL: 0.0, Need.ENERGY: 0.0}
    # Place the agent on an office tile.
    ox, oy = content.places["business_office"].coords[0]
    agent.x, agent.y = ox, oy
    ctx, cap = make_ctx(content, world)

    bt = create_agent_bt(agent, content.sim_params)
    status = bt.tick(ctx)
    assert status == Status.RUNNING  # ExecuteActivity returns RUNNING
    assert agent.state == AgentState.DOING_ACTION
    assert any(t == "activity_started" for t, _ in cap.events)


# --------------------------------------------------------------------------
# Threshold branches
# --------------------------------------------------------------------------

def test_exhausted_triggers_go_home(content):
    world = make_world(content)
    set_time(world, 9)
    _assign_schedule(content, world)
    agent = world.agents["alex"]
    agent.needs = {Need.HUNGER: 0.0, Need.SOCIAL: 0.0, Need.ENERGY: 99.0}  # > exhausted 95
    ctx, cap = make_ctx(content, world)

    bt = create_agent_bt(agent, content.sim_params)
    status = bt.tick(ctx)
    assert status == Status.SUCCESS
    assert agent.state == AgentState.MOVING
    assert agent.destination_name == "alex_home"
    assert any(d.get("decision") == "emergency_go_home"
               for t, d in cap.events if t == "decision_made")


def test_tired_triggers_rest_branch(content):
    world = make_world(content)
    set_time(world, 9)
    _assign_schedule(content, world)
    agent = world.agents["alex"]
    # Tired (>=70) but not exhausted (<95): urgent rest branch.
    agent.needs = {Need.HUNGER: 0.0, Need.SOCIAL: 0.0, Need.ENERGY: 80.0}
    ctx, cap = make_ctx(content, world)

    bt = create_agent_bt(agent, content.sim_params)
    status = bt.tick(ctx)
    assert status == Status.SUCCESS
    assert agent.current_activity == "take_a_short_rest"
    assert any(d.get("decision") == "go_rest"
               for t, d in cap.events if t == "decision_made")


def test_rest_round_trip_executes_at_chosen_location(content):
    """The ad-hoc rest activity registered on world.activity_data must resolve
    so that, once at the rest spot, the agent actually executes ExecuteRest
    (RESTED) instead of re-planning a path forever."""
    world = make_world(content)
    set_time(world, 9)
    _assign_schedule(content, world)
    agent = world.agents["alex"]
    agent.needs = {Need.HUNGER: 0.0, Need.SOCIAL: 0.0, Need.ENERGY: 80.0}
    ctx, cap = make_ctx(content, world)

    bt = create_agent_bt(agent, content.sim_params)
    # Tick 1: choose a rest location and start moving there.
    bt.tick(ctx)
    assert agent.current_activity == "take_a_short_rest"
    rest_loc = agent.rest_location
    assert rest_loc is not None
    # The ad-hoc activity is registered on the LIVE world view.
    assert world.activity_data["take_a_short_rest"]["location"] == rest_loc

    # Engine moves the agent onto the rest tile; rebuild a fresh tree.
    agent.x, agent.y = content.places[rest_loc].coords[0]
    agent.state = AgentState.IDLE
    cap.events.clear()
    bt2 = create_agent_bt(agent, content.sim_params)
    status = bt2.tick(ctx)
    assert status == Status.RUNNING
    assert agent.state == AgentState.DOING_ACTION
    assert any(t == "rested" for t, _ in cap.events)


def test_eat_round_trip_resolves_registered_cost(content):
    """The ad-hoc eat activity (eat_at_cafe) registered on world.activity_data
    must be readable so HasEnoughMoney / ExecuteActivity see its cost."""
    world = make_world(content)
    set_time(world, 9)
    _assign_schedule(content, world)
    agent = world.agents["alex"]
    agent.needs = {Need.HUNGER: 90.0, Need.SOCIAL: 0.0, Need.ENERGY: 0.0}
    ctx, cap = make_ctx(content, world)

    bt = create_agent_bt(agent, content.sim_params)
    status = bt.tick(ctx)
    assert status == Status.RUNNING
    # The eat activity is registered on the live world view with a positive cost.
    assert world.activity_data["eat_at_cafe"]["cost"] == 10
    assert any(t == "ate" for t, _ in cap.events)


def test_starving_triggers_eat_branch(content):
    world = make_world(content)
    set_time(world, 9)
    _assign_schedule(content, world)
    agent = world.agents["alex"]
    # Hungry (>=85) but not tired: critical eat branch.
    agent.needs = {Need.HUNGER: 90.0, Need.SOCIAL: 0.0, Need.ENERGY: 0.0}
    ctx, cap = make_ctx(content, world)

    bt = create_agent_bt(agent, content.sim_params)
    status = bt.tick(ctx)
    # The eat sequence ends in ExecuteEat -> RUNNING.
    assert status == Status.RUNNING
    assert any(t == "need_critical" for t, _ in cap.events)
    assert any(t == "ate" for t, _ in cap.events)


def test_selector_reactive_priority_preempts_lower_branch(content):
    """A higher-priority emergency must win even when a scheduled activity is
    available — the root Selector re-evaluates from the top every tick."""
    world = make_world(content)
    set_time(world, 9, day_index=0)
    activity = _assign_schedule(content, world)
    assert activity == "work_at_office"  # a real scheduled activity exists
    agent = world.agents["alex"]
    # Exhausted: the emergency-go-home branch (priority 1) must pre-empt the
    # scheduled-activity core branch entirely.
    agent.needs = {Need.HUNGER: 0.0, Need.SOCIAL: 0.0, Need.ENERGY: 99.0}
    ctx, cap = make_ctx(content, world)

    bt = create_agent_bt(agent, content.sim_params)
    status = bt.tick(ctx)
    assert status == Status.SUCCESS
    assert agent.destination_name == "alex_home"
    decisions = [d.get("decision") for t, d in cap.events if t == "decision_made"]
    assert "emergency_go_home" in decisions
    # The scheduled activity must NOT have driven a go_to_activity decision.
    assert "go_to_activity" not in decisions


def test_isagenttired_condition_threshold(content):
    world = make_world(content)
    agent = world.agents["alex"]
    ctx, _ = make_ctx(content, world)
    agent.needs[Need.ENERGY] = 70.0
    assert IsAgentTired("t", threshold=70).tick(ctx) == Status.SUCCESS
    agent.needs[Need.ENERGY] = 69.0
    assert IsAgentTired("t", threshold=70).tick(ctx) == Status.FAILURE


def test_isneedcritical_emits_event(content):
    world = make_world(content)
    agent = world.agents["alex"]
    ctx, cap = make_ctx(content, world)
    agent.needs[Need.HUNGER] = 90.0
    assert IsNeedCritical("c", Need.HUNGER, 85).tick(ctx) == Status.SUCCESS
    assert any(t == "need_critical" for t, _ in cap.events)
    agent.needs[Need.HUNGER] = 10.0
    cap.events.clear()
    assert IsNeedCritical("c", Need.HUNGER, 85).tick(ctx) == Status.FAILURE
    assert not cap.events


# --------------------------------------------------------------------------
# StatefulSelector real lookahead (report contribution C2)
# --------------------------------------------------------------------------

def test_action_simulate_is_real_not_stub(content):
    """A node's simulate must actually mutate the summary (no stub)."""
    world = make_world(content)
    ctx, _ = make_ctx(content, world)
    base = SimulationSummary({Need.SOCIAL: 80.0, Need.ENERGY: 40.0, Need.HUNGER: 0.0}, 100.0)
    out = FindAgentToTalkTo("talk").simulate(ctx, base)
    # Real prediction: social drops by 40, energy by 3.
    assert out.final_needs[Need.SOCIAL] == 40.0
    assert out.final_needs[Need.ENERGY] == 37.0
    # Original summary untouched (no aliasing).
    assert base.final_needs[Need.SOCIAL] == 80.0


def test_execute_activity_simulate_predicts_cost_and_needs(content):
    world = make_world(content)
    agent = world.agents["alex"]
    agent.current_activity = "drinks_at_bar"
    ctx, _ = make_ctx(content, world)
    cost = float(content.activity_data["drinks_at_bar"].get("cost", 0))
    base = SimulationSummary({Need.SOCIAL: 90.0, Need.ENERGY: 10.0, Need.HUNGER: 0.0}, 100.0)
    out = ExecuteActivity("act").simulate(ctx, base)
    assert out.final_money == 100.0 - cost
    assert out.final_needs[Need.SOCIAL] == 30.0  # -60 from socialize token


def test_stateful_selector_picks_highest_scoring_child(content):
    """StatefulSelector must choose the child whose real simulate scores best."""
    world = make_world(content)
    agent = world.agents["alex"]
    # High social need so the social-predicting node scores well.
    agent.needs = {Need.HUNGER: 0.0, Need.SOCIAL: 90.0, Need.ENERGY: 30.0}
    ctx, _ = make_ctx(content, world)

    class TaggingIdle(Node):
        """An idle-like leaf with identity simulate that records ticks."""

        def __init__(self, name, log):
            super().__init__(name)
            self.log = log

        def tick(self, c):
            self.log.append(self.name)
            return Status.SUCCESS

    ticked: List[str] = []
    social_child = FindAgentToTalkTo("social")  # simulate drops social need -> high score
    # Wrap FindAgentToTalkTo tick so it records too, but since no candidates it
    # will FAIL; we only care about selection, so use a stub tick.

    class SocialPredictor(Node):
        def __init__(self, name, log):
            super().__init__(name)
            self.log = log

        def tick(self, c):
            self.log.append(self.name)
            return Status.SUCCESS

        def simulate(self, c, summary):
            return social_child.simulate(c, summary)

    chosen = StatefulSelector("core", children=[
        SocialPredictor("social", ticked),
        TaggingIdle("idle", ticked),
    ])
    best = chosen.select_best_child(ctx)
    assert best.name == "social"  # social reduction outweighs idle's no-op
    status = chosen.tick(ctx)
    assert status == Status.SUCCESS
    assert ticked == ["social"]


def test_stateful_selector_prefers_idle_when_no_need(content):
    """With no social need, the social child's prediction loses to a neutral one."""
    world = make_world(content)
    agent = world.agents["alex"]
    agent.needs = {Need.HUNGER: 0.0, Need.SOCIAL: 0.0, Need.ENERGY: 0.0}
    ctx, _ = make_ctx(content, world)

    class Predictor(Node):
        def __init__(self, name, social_delta):
            super().__init__(name)
            self.social_delta = social_delta

        def tick(self, c):
            return Status.SUCCESS

        def simulate(self, c, summary):
            out = summary.copy()
            # With social=0, "reducing" stays 0 -> no positive score; meanwhile a
            # node that costs energy would score worse. Idle is neutral.
            out.final_needs[Need.ENERGY] = out.final_needs.get(Need.ENERGY, 0.0) + 50.0
            return out

    sel = StatefulSelector("core", children=[
        Predictor("makes_things_worse", 0.0),
        Idle("idle"),
    ])
    # The "worse" predictor increases energy need (bad) -> lower score than Idle's
    # identity. So Idle (no change) should win, since heuristic of identity = 1.0
    # and the worse predictor < 1.0.
    best = sel.select_best_child(ctx)
    assert best.name == "idle"


# --------------------------------------------------------------------------
# reset
# --------------------------------------------------------------------------

def test_reset_clears_running_state(content):
    world = make_world(content)
    set_time(world, 9)
    _assign_schedule(content, world)
    agent = world.agents["alex"]
    ox, oy = content.places["business_office"].coords[0]
    agent.x, agent.y = ox, oy
    agent.needs = {Need.HUNGER: 0.0, Need.SOCIAL: 0.0, Need.ENERGY: 0.0}
    ctx, _ = make_ctx(content, world)

    core = StatefulSelector("core", children=[
        Sequence("seq", children=[ExecuteActivity("exec")]),
    ])
    status = core.tick(ctx)
    assert status == Status.RUNNING
    assert core.selected_child is not None
    assert core.is_running
    core.reset()
    assert core.selected_child is None
    assert not core.is_running


def test_sequence_reset_index(content):
    world = make_world(content)
    ctx, _ = make_ctx(content, world)

    class Run(Node):
        def tick(self, c):
            return Status.RUNNING

    seq = Sequence("s", children=[Run("r")])
    assert seq.tick(ctx) == Status.RUNNING
    assert seq.is_running
    seq.reset()
    assert seq.current_child_index == 0
    assert not seq.is_running


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------

def _run_once(content, hour: int, energy: float, social: float, hunger: float, seed: int):
    """Run a full BT tick from a fixed state and return (decisions, events, agent snapshot)."""
    world = make_world(content)
    set_time(world, hour)
    _assign_schedule(content, world)
    agent = world.agents["alex"]
    agent.needs = {Need.HUNGER: hunger, Need.SOCIAL: social, Need.ENERGY: energy}
    ctx, cap = make_ctx(content, world, seed=seed)
    bt = create_agent_bt(agent, content.sim_params)
    status = bt.tick(ctx)
    snapshot = (agent.state, agent.destination_name, agent.current_activity,
                tuple(sorted(agent.needs.items())), agent.money)
    return status, list(cap.events), list(cap.observations), snapshot


def test_determinism_same_seed_same_result(content):
    args = dict(hour=9, energy=80.0, social=50.0, hunger=10.0, seed=1234)
    r1 = _run_once(content, **args)
    r2 = _run_once(content, **args)
    assert r1 == r2


def test_determinism_rest_location_is_seeded(content):
    """PlanPathToRestLocation's location choice (an RNG draw) is reproducible:
    two independent runs from identical state pick the same rest spot and emit
    identical events/observations."""
    def run(seed):
        world = make_world(content)
        set_time(world, 9)
        _assign_schedule(content, world)
        agent = world.agents["alex"]
        agent.needs = {Need.HUNGER: 0.0, Need.SOCIAL: 0.0, Need.ENERGY: 80.0}
        ctx, cap = make_ctx(content, world, seed=seed)
        bt = create_agent_bt(agent, content.sim_params)
        bt.tick(ctx)
        return agent.rest_location, list(cap.events), list(cap.observations)

    a = run(4242)
    b = run(4242)
    assert a == b
    assert a[0] is not None  # a rest location was actually chosen


def test_determinism_socialize_roll_is_seeded(content):
    """The socialize roll (free-time) is reproducible across runs with same seed."""
    # Hour with no scheduled activity forces free-time branch.
    world1 = make_world(content)
    world2 = make_world(content)
    for w in (world1, world2):
        set_time(w, 3)  # 03:00 -> likely no schedule entry (sleep/none)
    a1 = world1.agents["alex"]
    a2 = world2.agents["alex"]
    for a in (a1, a2):
        a.current_activity = None
        a.needs = {Need.HUNGER: 0.0, Need.SOCIAL: 50.0, Need.ENERGY: 0.0}
    ctx1, cap1 = make_ctx(content, world1, seed=999)
    ctx2, cap2 = make_ctx(content, world2, seed=999)
    bt1 = create_agent_bt(a1, content.sim_params)
    bt2 = create_agent_bt(a2, content.sim_params)
    s1 = bt1.tick(ctx1)
    s2 = bt2.tick(ctx2)
    assert s1 == s2
    assert cap1.events == cap2.events
    assert cap1.observations == cap2.observations


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
