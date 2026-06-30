"""Post-hoc narrative synthesis (report recommendations #6/#10, contribution C4).

The :class:`NarrativeSystem` turns the Tier-1 event stream into prose: per-agent
diaries and a single town-wide story. It is strictly post-hoc — it reads
finished memories and emits text, never mutating simulation state.

Two synthesis schemes are supported when compiling the town story:

* **flat** — one :data:`~matss.ports.ModelTier.FRONTIER` call over every diary.
  Simple, but the frontier input grows linearly with the agent count.
* **hierarchical** — an agent -> group -> town fan-in: a cheaper
  :data:`~matss.ports.ModelTier.BALANCED` summary per group, then one frontier
  call over the (small, bounded) set of group summaries. This caps the
  expensive frontier input at the number of groups rather than agents.

:meth:`NarrativeSystem.estimate_cost` exposes that trade-off as a transparent,
LLM-free cost model so callers can reason about token spend before paying for it.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

from .. import ports
from ..domain.agent import AgentDef
from ..domain.memory import MemoryRecord
from ..ports import LLMProvider, LLMRequest, ModelTier

# Default per-call token budgets. Diaries are a few paragraphs; the town story
# is longer-form. These are conservative defaults the caller can rely on.
_DIARY_MAX_TOKENS = 1024
_TOWN_MAX_TOKENS = 2048
_GROUP_MAX_TOKENS = 1024


class NarrativeSystem:
    """Synthesises diaries and town stories from agent memories.

    Attributes:
        provider: The LLM provider used for every synthesis call.
        content: Optional resolved world content (currently advisory; kept for
            symmetry with other subsystems and future world-grounding).
    """

    def __init__(self, provider: LLMProvider, content: object = None) -> None:
        """Initialise the narrative system.

        Args:
            provider: A :class:`~matss.ports.LLMProvider` implementation.
            content: Optional resolved world content, or ``None``.
        """
        self.provider = provider
        self.content = content

    # --- per-agent diaries ----------------------------------------------------

    def _persona_prefix(self, agent_def: AgentDef) -> str:
        """Build the stable, cacheable persona/background block for ``agent_def``.

        This portion is identical across every diary call for the same agent, so
        it is passed as ``cache_prefix`` to let a caching adapter deduplicate it.
        """
        personality = ", ".join(agent_def.personality) or "unremarkable"
        lines = [
            f"You are {agent_def.name}.",
            f"Personality: {personality}.",
        ]
        if agent_def.background:
            lines.append(f"Background: {agent_def.background}")
        lines.append(
            "Write in the first person, in your own voice, as a private diary "
            "entry reflecting honestly on your day."
        )
        return "\n".join(lines)

    def write_diary(
        self,
        agent_def: AgentDef,
        day: str,
        day_number: int,
        memories: List[MemoryRecord],
    ) -> str:
        """Write a first-person diary entry for one agent for one day.

        Args:
            agent_def: The agent's immutable definition (persona/background).
            day: The day-of-week label (e.g. ``"Monday"``).
            day_number: The 1-based simulation day index.
            memories: The agent's memories for that day, in occurrence order.

        Returns:
            The diary text returned by the provider.
        """
        persona = self._persona_prefix(agent_def)

        if memories:
            memory_block = "\n".join(f"- {m.text}" for m in memories)
        else:
            memory_block = "(Nothing of note happened today.)"

        prompt = (
            f"Today is {day} (day {day_number}). "
            "Here is what you experienced and observed today:\n"
            f"{memory_block}\n\n"
            f"Write your diary entry for {day}."
        )

        request = LLMRequest(
            prompt=prompt,
            system=persona,
            tier=ModelTier.BALANCED,
            max_tokens=_DIARY_MAX_TOKENS,
            cache_prefix=persona,
            metadata={
                "kind": "diary",
                "agent_id": agent_def.id,
                "day": day,
                "day_number": day_number,
            },
        )
        return self.provider.complete(request).text

    # --- town-wide story ------------------------------------------------------

    def _summarise_group(
        self,
        diaries: Dict[str, str],
        group: Sequence[str],
        day: str,
        day_number: int,
    ) -> str:
        """Summarise one group's diaries with a single BALANCED call."""
        present = [aid for aid in group if aid in diaries]
        block = "\n\n".join(
            f"[{aid}]\n{diaries[aid]}" for aid in present
        ) or "(No diaries in this group.)"
        prompt = (
            f"Day {day_number} ({day}). Summarise the key events, relationships, "
            "and tensions from these residents' diary entries into a concise "
            "group digest:\n\n"
            f"{block}"
        )
        request = LLMRequest(
            prompt=prompt,
            tier=ModelTier.BALANCED,
            max_tokens=_GROUP_MAX_TOKENS,
            metadata={
                "kind": "group_summary",
                "day": day,
                "day_number": day_number,
                "group": list(present),
            },
        )
        return self.provider.complete(request).text

    def compile_town_story(
        self,
        diaries: Dict[str, str],
        day: str,
        day_number: int,
        groups: Optional[List[List[str]]] = None,
        hierarchical: bool = False,
    ) -> str:
        """Compile a single town-wide story for the day from agent diaries.

        Args:
            diaries: Mapping of ``agent_id -> diary text``.
            day: The day-of-week label.
            day_number: The 1-based simulation day index.
            groups: Optional partition of agent ids into groups, used only by the
                hierarchical scheme. If ``None`` while ``hierarchical`` is set, a
                single group containing all diaries is used.
            hierarchical: When ``True``, summarise per group (BALANCED) then fuse
                the summaries (FRONTIER). When ``False`` (default), a single
                FRONTIER call spans all diaries.

        Returns:
            The town-story text returned by the final frontier call.
        """
        if hierarchical:
            return self._compile_hierarchical(diaries, day, day_number, groups)
        return self._compile_flat(diaries, day, day_number)

    def _compile_flat(
        self, diaries: Dict[str, str], day: str, day_number: int
    ) -> str:
        """Flat scheme: one FRONTIER call over every diary."""
        block = "\n\n".join(
            f"[{aid}]\n{text}" for aid, text in diaries.items()
        ) or "(No diaries were written today.)"
        prompt = (
            f"Day {day_number} ({day}). The following are the private diary "
            "entries of every resident of the town. Weave them into a single, "
            "coherent third-person story of the town's day, surfacing the shared "
            "events and how lives intersected:\n\n"
            f"{block}"
        )
        request = LLMRequest(
            prompt=prompt,
            tier=ModelTier.FRONTIER,
            max_tokens=_TOWN_MAX_TOKENS,
            metadata={
                "kind": "town_story",
                "scheme": "flat",
                "day": day,
                "day_number": day_number,
            },
        )
        return self.provider.complete(request).text

    def _compile_hierarchical(
        self,
        diaries: Dict[str, str],
        day: str,
        day_number: int,
        groups: Optional[List[List[str]]],
    ) -> str:
        """Hierarchical scheme: BALANCED per-group summaries, then one FRONTIER."""
        if groups is None:
            groups = [list(diaries.keys())]

        summaries: List[str] = []
        for idx, group in enumerate(groups):
            summaries.append(self._summarise_group(diaries, group, day, day_number))

        block = "\n\n".join(
            f"[group {i}]\n{s}" for i, s in enumerate(summaries)
        ) or "(No group summaries were produced today.)"
        prompt = (
            f"Day {day_number} ({day}). The following are digests of what "
            "happened within each cluster of residents. Fuse them into a single, "
            "coherent third-person story of the town's day:\n\n"
            f"{block}"
        )
        request = LLMRequest(
            prompt=prompt,
            tier=ModelTier.FRONTIER,
            max_tokens=_TOWN_MAX_TOKENS,
            metadata={
                "kind": "town_story",
                "scheme": "hierarchical",
                "day": day,
                "day_number": day_number,
                "num_groups": len(groups),
            },
        )
        return self.provider.complete(request).text

    # --- transparent cost model (no LLM calls) --------------------------------

    def estimate_cost(
        self,
        n_agents: int,
        hierarchical: bool,
        avg_diary_tokens: int = 600,
        group_size: int = 4,
    ) -> Dict[str, object]:
        """Estimate the LLM cost of compiling a town story (LLM-free model).

        The model counts the *town-story compilation* calls only (the per-agent
        diary calls are common to both schemes and excluded so the schemes are
        comparable). It makes the flat-vs-hierarchical trade-off explicit:

        * **flat** — 1 FRONTIER call whose input is ~``n_agents * avg_diary``
          tokens, i.e. it grows linearly with the population.
        * **hierarchical** — ``ceil(n / group_size)`` BALANCED group calls plus 1
          FRONTIER town call whose input is bounded by the *number of groups*,
          not the population.

        Args:
            n_agents: The number of agents (and diaries).
            hierarchical: Whether to model the hierarchical scheme.
            avg_diary_tokens: Assumed average token length of one diary.
            group_size: Agents per group in the hierarchical scheme.

        Returns:
            A dict with keys ``"scheme"``, ``"calls"``, ``"input_tokens_est"``
            (total estimated input tokens across all modelled calls) and
            ``"tiers"`` (per-tier breakdown of ``{"calls", "input_tokens"}``).
        """
        n_agents = max(0, int(n_agents))
        avg_diary_tokens = max(0, int(avg_diary_tokens))
        group_size = max(1, int(group_size))

        if hierarchical:
            num_groups = math.ceil(n_agents / group_size) if n_agents else 0
            # Each group summary call reads the diaries in that group. Across all
            # groups every diary is read once -> ~n * avg total balanced input.
            balanced_input = n_agents * avg_diary_tokens
            # Assume each group summary is roughly one diary's worth of tokens;
            # the town call reads one summary per group -> bounded by group count.
            frontier_input = num_groups * avg_diary_tokens
            tiers: Dict[str, Dict[str, int]] = {
                ModelTier.BALANCED: {
                    "calls": num_groups,
                    "input_tokens": balanced_input,
                },
                ModelTier.FRONTIER: {
                    "calls": 1 if num_groups else 0,
                    "input_tokens": frontier_input,
                },
            }
            calls = num_groups + (1 if num_groups else 0)
            return {
                "scheme": "hierarchical",
                "calls": calls,
                "num_groups": num_groups,
                "input_tokens_est": balanced_input + frontier_input,
                "tiers": tiers,
            }

        # Flat: a single frontier call over every diary.
        frontier_input = n_agents * avg_diary_tokens
        calls = 1 if n_agents else 0
        tiers = {
            ModelTier.FRONTIER: {
                "calls": calls,
                "input_tokens": frontier_input,
            },
        }
        return {
            "scheme": "flat",
            "calls": calls,
            "input_tokens_est": frontier_input,
            "tiers": tiers,
        }


# Static contract conformance check (cheap, import-time).
assert hasattr(ports, "LLMProvider")
