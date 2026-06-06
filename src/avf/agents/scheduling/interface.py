"""Scheduling module interfaces for SUT agent action ordering."""

from __future__ import annotations

from typing import List, Protocol

from avf.contracts import AgentAction


class Scheduler(Protocol):
    """Shared scheduler interface for sequential and rule-based policies."""

    def schedule(self, actions: List[AgentAction]) -> List[AgentAction]:
        """Return actions in the order they should be dispatched."""


class SequentialScheduler:
    """Phase 1E scheduler that preserves planner order."""

    def schedule(self, actions: List[AgentAction]) -> List[AgentAction]:
        return list(actions)

