"""Validation helpers for trace artifacts."""

from __future__ import annotations

from typing import Set

from avf.contracts import RunTrace, ValidationError


def validate_run_trace(trace: RunTrace) -> RunTrace:
    """Validate trace metadata and event consistency beyond dataclass parsing."""

    if not trace.events:
        raise ValidationError("RunTrace.events must not be empty")

    seen_event_ids: Set[str] = set()
    for event in trace.events:
        if event.run_id != trace.run_id:
            raise ValidationError(f"TraceEvent {event.event_id} has run_id {event.run_id}, expected {trace.run_id}")
        if event.event_id in seen_event_ids:
            raise ValidationError(f"Duplicate TraceEvent ID: {event.event_id}")
        seen_event_ids.add(event.event_id)

    if trace.status == "completed":
        event_types = [event.event_type for event in trace.events]
        if "final_answer" not in event_types:
            raise ValidationError("Completed RunTrace must include a final_answer event")

    return trace

