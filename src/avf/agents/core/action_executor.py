"""Action execution for the Phase 1E baseline SUT agent."""

from __future__ import annotations

from typing import Dict

from avf.contracts import AgentAction, AgentObservation, ToolCall, ToolSpec, ValidationError
from avf.agents.tools import ToolClient

from .state import AgentState


class ActionExecutor:
    """Execute internal/final actions and dispatch tool actions via ToolClient."""

    def __init__(self, tool_client: ToolClient, tool_specs: Dict[str, ToolSpec]) -> None:
        self.tool_client = tool_client
        self.tool_specs = dict(tool_specs)

    def execute(self, state: AgentState, action: AgentAction) -> AgentObservation:
        if action.action_type == "tool_call":
            return self._execute_tool_call(action)
        if action.action_type == "final_answer":
            return self._execute_final_answer(state, action)
        return AgentObservation(
            observation_id=f"{action.action_id}_observation",
            run_id=action.run_id,
            step_index=action.step_index,
            source=action.name,
            status="success",
            content={"ok": True},
            state_delta={},
        )

    def _execute_tool_call(self, action: AgentAction) -> AgentObservation:
        if action.name not in self.tool_specs:
            raise ValidationError(f"No ToolSpec available for action {action.name}")

        tool_call = ToolCall(
            tool_call_id=f"{action.action_id}_tool_call",
            run_id=action.run_id,
            step_index=action.step_index,
            tool_name=action.name,
            arguments=dict(action.arguments),
            requested_at=f"1970-01-01T00:00:{action.step_index + 1:02d}Z",
        )
        result = self.tool_client.call_tool(tool_call)
        status = "success" if result.status == "success" else "error"
        content = dict(result.output)
        if result.error:
            content["error"] = result.error
        return AgentObservation(
            observation_id=f"{action.action_id}_observation",
            run_id=action.run_id,
            step_index=action.step_index,
            source=action.name,
            status=status,
            content=content,
            state_delta={"tool_call_id": tool_call.tool_call_id, "tool_status": result.status},
        )

    def _execute_final_answer(self, state: AgentState, action: AgentAction) -> AgentObservation:
        preference = state.retrieved_preference or state.stored_preference
        if preference:
            answer = f"The recorded preference is to {preference}."
            status = "success"
            state_delta = {"answer_returned": True}
        else:
            answer = None
            status = "error"
            state_delta = {"answer_returned": False}

        content = {"final_answer": answer} if answer else {"message": "No preference was available to answer."}
        return AgentObservation(
            observation_id=f"{action.action_id}_observation",
            run_id=action.run_id,
            step_index=action.step_index,
            source=action.name,
            status=status,
            content=content,
            state_delta=state_delta,
        )

