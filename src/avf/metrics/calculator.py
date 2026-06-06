"""Deterministic Phase 1 metric calculation."""

from __future__ import annotations

from typing import List, Optional

from avf.contracts import MetricResult, RunTrace, SCHEMA_VERSION, VerificationResult


def calculate_metric_result(trace: RunTrace, verification: VerificationResult) -> MetricResult:
    """Calculate the first deterministic metric artifact for one run.

    Phase 1I avoids wall-clock timing so repeated baseline runs produce
    equivalent artifacts under the same seed and fixtures.
    """

    action_names = _action_names(trace)
    step_count = len(action_names)
    tool_call_count = len([event for event in trace.events if event.event_type == "tool_call"])
    return MetricResult(
        schema_version=SCHEMA_VERSION,
        run_id=trace.run_id,
        task_success=verification.passed,
        latency_ms=0,
        step_count=step_count,
        tool_call_count=tool_call_count,
        goal_drift=_goal_drift(trace, verification.passed, step_count),
        repetition_rate=_repetition_rate(action_names),
        recovery_steps=_recovery_steps(trace),
    )


def _action_names(trace: RunTrace) -> List[str]:
    names: List[str] = []
    for event in trace.events:
        if event.event_type != "agent_step":
            continue
        if event.payload.get("stage") != "act":
            continue
        action = event.payload.get("action")
        if isinstance(action, dict) and isinstance(action.get("name"), str):
            names.append(action["name"])
    return names


def _goal_drift(trace: RunTrace, task_success: bool, step_count: int) -> float:
    if step_count == 0:
        return 0.0 if task_success else 1.0
    if task_success:
        return 0.0
    progressing_updates = 0
    for event in trace.events:
        if event.event_type != "state_update":
            continue
        state_delta = event.payload.get("state_delta")
        if isinstance(state_delta, dict) and state_delta:
            progressing_updates += 1
    non_progressing = max(step_count - progressing_updates, 0)
    return non_progressing / step_count


def _repetition_rate(action_names: List[str]) -> float:
    if not action_names:
        return 0.0
    repeated = 0
    previous: Optional[str] = None
    for name in action_names:
        if name == previous:
            repeated += 1
        previous = name
    return repeated / len(action_names)


def _recovery_steps(trace: RunTrace) -> Optional[int]:
    recovery_events = [event for event in trace.events if event.event_type == "recovery"]
    if not recovery_events:
        return None
    return len(recovery_events)
