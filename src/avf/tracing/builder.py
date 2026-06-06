"""Build RunTrace contracts from run contexts and emitted trace events."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from avf.contracts import RunTrace, SCHEMA_VERSION, TraceEvent, ValidationError
from avf.orchestration.run_context import RunContext

from .validation import validate_run_trace


def build_run_trace(
    run_context: RunContext,
    events: Iterable[TraceEvent],
    status: str,
    started_at: Optional[str] = None,
    completed_at: Optional[str] = None,
) -> RunTrace:
    event_list = list(events)
    if not event_list:
        raise ValidationError("RunTrace requires at least one TraceEvent")

    trace = RunTrace(
        schema_version=SCHEMA_VERSION,
        run_id=run_context.run_id,
        task_id=run_context.task.task_id,
        run_config_id=run_context.run_config.run_config_id,
        component_config_id=run_context.component_config.config_id,
        seed=run_context.seed,
        perturbation_schedule_id=run_context.perturbation_schedule_id,
        started_at=started_at or event_list[0].timestamp,
        completed_at=completed_at if completed_at is not None else event_list[-1].timestamp,
        status=status,
        events=event_list,
    )
    validate_run_trace(trace)
    return trace


def build_run_trace_from_agent_result(
    run_context: RunContext,
    agent_result: Any,
    started_at: Optional[str] = None,
    completed_at: Optional[str] = None,
) -> RunTrace:
    events = list(agent_result.trace_events)
    expected_event_ids = [event.event_id for event in events]
    output_event_ids = list(agent_result.output.trace_event_ids)
    if output_event_ids != expected_event_ids:
        raise ValidationError("AgentOutput.trace_event_ids do not match emitted TraceEvent IDs")

    return build_run_trace(
        run_context=run_context,
        events=events,
        status=agent_result.output.status,
        started_at=started_at,
        completed_at=completed_at,
    )
