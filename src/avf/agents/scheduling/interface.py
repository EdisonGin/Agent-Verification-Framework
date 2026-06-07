"""Scheduling module interfaces for SUT agent action ordering."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Protocol

from avf.contracts import AgentAction


@dataclass(frozen=True)
class SchedulingDecision:
    """Explain one scheduler ordering decision."""

    action_id: str
    action_name: str
    original_step_index: int
    scheduled_step_index: int
    priority: int
    rule: str
    reason: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


class Scheduler(Protocol):
    """Shared scheduler interface for sequential and rule-based policies."""

    def schedule(self, actions: List[AgentAction]) -> List[AgentAction]:
        """Return actions in the order they should be dispatched."""

    def decisions(self) -> List[Dict[str, object]]:
        """Return explanatory scheduling decisions from the most recent schedule call."""


class SequentialScheduler:
    """Phase 1E scheduler that preserves planner order."""

    def __init__(self) -> None:
        self._last_decisions: List[SchedulingDecision] = []

    def schedule(self, actions: List[AgentAction]) -> List[AgentAction]:
        scheduled = list(actions)
        self._last_decisions = [
            SchedulingDecision(
                action_id=action.action_id,
                action_name=action.name,
                original_step_index=action.step_index,
                scheduled_step_index=action.step_index,
                priority=index,
                rule="preserve_planner_order",
                reason="Sequential scheduler preserves the planner-proposed action order.",
            )
            for index, action in enumerate(scheduled)
        ]
        return scheduled

    def decisions(self) -> List[Dict[str, object]]:
        return [decision.to_dict() for decision in self._last_decisions]
