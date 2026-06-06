"""Deterministic planning for the Phase 1E baseline SUT agent."""

from __future__ import annotations

from typing import List

from avf.contracts import AgentAction

from .state import AgentState


class BaselinePlanner:
    """Create a fixed sequential plan for the Phase 1 memory-recall task."""

    def create_plan(self, state: AgentState) -> List[AgentAction]:
        preference = state.stored_preference or ""
        return [
            AgentAction(
                action_id=f"{state.run_id}_action_001",
                run_id=state.run_id,
                step_index=0,
                action_type="tool_call",
                name="memory.write",
                arguments={
                    "key": "user_preference",
                    "value": preference,
                    "metadata": {"task_id": state.task_id},
                },
                rationale="Store the task preference before attempting recall.",
            ),
            AgentAction(
                action_id=f"{state.run_id}_action_002",
                run_id=state.run_id,
                step_index=1,
                action_type="tool_call",
                name="memory.query",
                arguments={
                    "query": "user_preference",
                    "metadata_filter": {"task_id": state.task_id},
                    "limit": 1,
                },
                rationale="Retrieve the stored preference using the shared memory query contract.",
            ),
            AgentAction(
                action_id=f"{state.run_id}_action_003",
                run_id=state.run_id,
                step_index=2,
                action_type="final_answer",
                name="final_answer",
                arguments={},
                rationale="Return the recalled preference to the test harness.",
            ),
        ]

