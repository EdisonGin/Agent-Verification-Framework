"""Observation handling for the Phase 1E baseline SUT agent."""

from __future__ import annotations

from avf.contracts import AgentAction, AgentObservation

from .state import AgentState


class ObservationProcessor:
    """Apply observations to internal state."""

    def process(self, state: AgentState, action: AgentAction, observation: AgentObservation) -> AgentState:
        state.current_step = max(state.current_step, action.step_index + 1)

        if observation.status == "error":
            message = observation.content.get("message") or observation.content.get("error") or "unknown error"
            state.errors.append(str(message))
            return state

        if action.name == "memory.write":
            if observation.content.get("ok") is True:
                state.stored_preference = str(action.arguments.get("value", ""))

        if action.name == "memory.query":
            records = observation.content.get("records", [])
            if isinstance(records, list) and records:
                value = records[0].get("value") if isinstance(records[0], dict) else None
                if isinstance(value, str):
                    state.retrieved_preference = value

        if action.name == "final_answer":
            answer = observation.content.get("final_answer")
            if isinstance(answer, str):
                state.final_answer = answer

        return state

