"""Deterministic rule-based action scheduler."""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Tuple

from avf.contracts import AgentAction

from .interface import SchedulingDecision


class RuleBasedScheduler:
    """Prioritise actions with explicit deterministic rules."""

    def __init__(self) -> None:
        self._last_decisions: List[SchedulingDecision] = []

    def schedule(self, actions: List[AgentAction]) -> List[AgentAction]:
        ranked: List[Tuple[int, int, str, AgentAction]] = []
        for original_index, action in enumerate(actions):
            priority, _rule, _reason = self._classification(action)
            ranked.append((priority, original_index, action.action_id, action))

        ranked.sort(key=lambda item: (item[0], item[1], item[2]))

        scheduled_actions: List[AgentAction] = []
        decisions: List[SchedulingDecision] = []
        for scheduled_index, (_priority, _original_index, _action_id, action) in enumerate(ranked):
            priority_value, rule, reason = self._classification(action)
            scheduled_action = replace(action, step_index=scheduled_index)
            scheduled_actions.append(scheduled_action)
            decisions.append(
                SchedulingDecision(
                    action_id=scheduled_action.action_id,
                    action_name=scheduled_action.name,
                    original_step_index=action.step_index,
                    scheduled_step_index=scheduled_index,
                    priority=priority_value,
                    rule=rule,
                    reason=reason,
                )
            )

        self._last_decisions = decisions
        return scheduled_actions

    def decisions(self) -> List[Dict[str, object]]:
        return [decision.to_dict() for decision in self._last_decisions]

    def _classification(self, action: AgentAction) -> Tuple[int, str, str]:
        if action.action_type == "internal":
            return (
                10,
                "internal_before_tools",
                "Internal actions are scheduled before external tool calls.",
            )
        if action.name == "memory.write":
            return (
                20,
                "memory_write_before_memory_query",
                "Memory writes are scheduled before memory queries to preserve read-after-write dependencies.",
            )
        if action.name == "memory.query":
            return (
                30,
                "memory_query_after_memory_write",
                "Memory queries are scheduled after writes so retrieval sees the latest stored records.",
            )
        if action.action_type == "tool_call":
            return (
                40,
                "generic_tool_call_after_memory_dependencies",
                "Other tool calls are scheduled after explicit memory dependencies.",
            )
        if action.action_type == "final_answer":
            return (
                100,
                "final_answer_last",
                "Final answers are scheduled after evidence-producing actions.",
            )
        return (
            50,
            "stable_fallback_order",
            "Unrecognised actions keep deterministic priority and original-order tie-breaking.",
        )
