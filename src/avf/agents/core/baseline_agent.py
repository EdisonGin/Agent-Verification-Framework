"""Deterministic Phase 1E baseline SUT agent."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List

from avf.contracts import (
    AgentAction,
    AgentObservation,
    AgentOutput,
    AgentRunInput,
    SCHEMA_VERSION,
    TraceEvent,
    ValidationError,
)
from avf.agents.scheduling import SequentialScheduler
from avf.agents.tools import ToolClient

from .action_executor import ActionExecutor
from .observation_processor import ObservationProcessor
from .perception import PerceptionInputProcessor
from .planner import BaselinePlanner
from .trace import TraceBuilder


@dataclass(frozen=True)
class BaselineAgentResult:
    """Full agent-side result before Phase 1G trace persistence exists."""

    output: AgentOutput
    actions: List[AgentAction]
    observations: List[AgentObservation]
    trace_events: List[TraceEvent]

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


class BaselineSUTAgent:
    """Minimal deterministic SUT agent for validating the agent boundary."""

    def __init__(self) -> None:
        self.perception = PerceptionInputProcessor()
        self.planner = BaselinePlanner()
        self.scheduler = SequentialScheduler()
        self.observation_processor = ObservationProcessor()

    def run(self, agent_input: AgentRunInput, tool_client: ToolClient) -> BaselineAgentResult:
        state = self.perception.process(agent_input)
        trace = TraceBuilder(agent_input.run_id)
        actions: List[AgentAction] = []
        observations: List[AgentObservation] = []
        trace_events: List[TraceEvent] = []

        trace_events.append(trace.event("agent_step", 0, {"stage": "perception", "state": state.to_dict()}))
        trace_events.append(
            trace.event(
                "agent_step",
                0,
                {
                    "stage": "component_config",
                    "component_config": agent_input.component_config.to_dict(),
                },
            )
        )
        trace_events.append(trace.event("agent_step", 0, {"stage": "reasoning", "strategy": "deterministic_baseline"}))

        plan = self.planner.create_plan(state)
        scheduled_actions = self.scheduler.schedule(plan)
        trace_events.append(
            trace.event(
                "agent_step",
                0,
                {"stage": "planning", "action_ids": [action.action_id for action in scheduled_actions]},
            )
        )

        max_steps = int(agent_input.execution_controls.get("max_steps", len(scheduled_actions)))
        executor = ActionExecutor(
            tool_client=tool_client,
            tool_specs={tool.tool_name: tool for tool in agent_input.tool_specs},
        )

        status = "completed"
        for action in scheduled_actions:
            if action.step_index >= max_steps:
                status = "timeout"
                state.errors.append("max_steps exceeded before action execution")
                break

            actions.append(action)
            trace_events.append(
                trace.event(
                    "agent_step",
                    action.step_index,
                    {"stage": "act", "action": action.to_dict()},
                )
            )

            if action.action_type == "tool_call":
                trace_events.append(
                    trace.event(
                        "tool_call",
                        action.step_index,
                        {"tool_name": action.name, "arguments": dict(action.arguments)},
                    )
                )

            observation = executor.execute(state, action)
            observations.append(observation)
            trace_events.append(
                trace.event(
                    "observation",
                    action.step_index,
                    {"observation": observation.to_dict()},
                )
            )
            if action.action_type == "tool_call":
                trace_events.append(
                    trace.event(
                        "tool_result",
                        action.step_index,
                        {"source": observation.source, "status": observation.status, "content": observation.content},
                    )
                )

            state = self.observation_processor.process(state, action, observation)
            trace_events.append(
                trace.event(
                    "state_update",
                    action.step_index,
                    {"state": state.to_dict(), "state_delta": observation.state_delta},
                )
            )

            if observation.status == "error":
                status = "failed"
                break

        if state.final_answer:
            trace_events.append(
                trace.event("final_answer", max(state.current_step - 1, 0), {"final_answer": state.final_answer})
            )
        elif status == "completed":
            status = "failed"
            state.errors.append("baseline agent did not produce a final answer")

        output = AgentOutput(
            schema_version=SCHEMA_VERSION,
            run_id=agent_input.run_id,
            status=status,
            final_answer=state.final_answer,
            artifacts=[],
            metrics={
                "steps": len(actions),
                "tool_calls": len([action for action in actions if action.action_type == "tool_call"]),
                "errors": len(state.errors),
            },
            trace_event_ids=[event.event_id for event in trace_events],
        )

        if status not in AgentOutput.statuses:
            raise ValidationError(f"Unsupported baseline agent status: {status}")

        return BaselineAgentResult(
            output=output,
            actions=actions,
            observations=observations,
            trace_events=trace_events,
        )
