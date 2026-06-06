"""Perception/input processing for the Phase 1E baseline SUT agent."""

from __future__ import annotations

from avf.contracts import AgentRunInput

from .state import AgentState


class PerceptionInputProcessor:
    """Parse the orchestrator-provided task into initial agent state."""

    def process(self, agent_input: AgentRunInput) -> AgentState:
        state = AgentState(
            run_id=agent_input.run_id,
            task_id=agent_input.task.task_id,
            task_family=agent_input.task.family,
            input_state=dict(agent_input.task.input_state),
        )
        preference = agent_input.task.input_state.get("user_preference")
        if isinstance(preference, str):
            state.stored_preference = preference
        return state

