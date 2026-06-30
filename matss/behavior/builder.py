"""Assembles the per-agent Behavior Tree.

The tree is a faithful, deterministic port of the prototype's
``create_agent_bt``: a priority :class:`~matss.behavior.tree.Selector` of
emergency reactions over a deliberative
:class:`~matss.behavior.tree.StatefulSelector` core. Thresholds are read from
content ``sim_params.thresholds`` so the engine stays data-driven.
"""

from __future__ import annotations

from typing import Any, Dict

from ..domain.agent import Agent
from ..domain.enums import Need
from .nodes import (
    ExecuteActivity,
    ExecuteEat,
    ExecuteRest,
    FindAgentToTalkTo,
    HasEnoughMoney,
    Idle,
    IsAgentTired,
    IsAtActivityLocation,
    IsNeedCritical,
    IsScheduledActivity,
    PlanPathToActivityLocation,
    PlanPathToEatLocation,
    PlanPathToHome,
    PlanPathToRestLocation,
    ShouldSocialize,
)
from .tree import Node, Selector, Sequence, StatefulSelector


def create_agent_bt(agent: Agent, params: Dict[str, Any] | None = None) -> Node:
    """Build the priority Behavior Tree for ``agent``.

    The structure (highest priority first) is::

        Selector
        |- Sequence  emergency: go home when exhausted
        |- Sequence  urgent: rest when tired
        |- Sequence  critical: eat when starving
        `- StatefulSelector  core daily routine
           |- Sequence  follow my schedule
           `- StatefulSelector  free time
              |- Sequence  try to socialize
              `- Idle

    Args:
        agent: The agent the tree decides for (used only for naming).
        params: Optional ``sim_params`` mapping; when omitted the default
            thresholds (exhausted 95 / tired 70 / starving 85) are used.

    Returns:
        The root :class:`~matss.behavior.tree.Node` of the agent's tree.
    """
    thresholds = (params or {}).get("thresholds", {}) if params else {}
    exhausted = float(thresholds.get("exhausted", 95))
    tired = float(thresholds.get("tired", 70))
    starving = float(thresholds.get("starving", 85))

    free_time_branch = StatefulSelector("Free Time Activities", children=[
        Sequence("Try to socialize", children=[
            ShouldSocialize("Should I socialize?"),
            FindAgentToTalkTo("Find someone to talk to"),
        ]),
        Idle("Default idle behavior"),
    ])

    scheduled_activity_branch = Sequence("Follow My Schedule", children=[
        IsScheduledActivity("Do I have a scheduled activity?"),
        HasEnoughMoney("Can I afford this activity?"),
        Selector("Execute or Move to Activity", children=[
            Sequence("I'm already here, so do the activity", children=[
                IsAtActivityLocation("Am I at the right location?"),
                ExecuteActivity("Execute the scheduled activity"),
            ]),
            PlanPathToActivityLocation("Go to the activity location"),
        ]),
    ])

    core_behavior_branch = StatefulSelector(
        f"Core Daily Routine for {agent.name}",
        children=[scheduled_activity_branch, free_time_branch],
    )

    root = Selector(f"Behavior Tree Root for {agent.name}", children=[
        Sequence("Emergency: Go Home When Exhausted", children=[
            IsAgentTired("Am I completely exhausted?", threshold=exhausted),
            PlanPathToHome("Emergency path home"),
        ]),
        Sequence("Urgent: Rest when tired", children=[
            IsAgentTired("Am I tired?", threshold=tired),
            Selector("Rest Behavior", children=[
                Sequence("I am at a rest location", children=[
                    IsAtActivityLocation("Am I at the rest spot?"),
                    ExecuteRest("Take a short rest"),
                ]),
                PlanPathToRestLocation("Find a place to rest"),
            ]),
        ]),
        Sequence("Critical: Find Food When Starving", children=[
            IsNeedCritical("Am I starving?", Need.HUNGER, threshold=starving),
            PlanPathToEatLocation("Find a place to eat"),
            ExecuteEat("Eat at the location"),
        ]),
        core_behavior_branch,
    ])

    return root
