"""Evidence extraction helpers for rule-based verification."""

from __future__ import annotations

from typing import List, Optional

from avf.contracts import RunTrace, TraceEvent


def final_answer_event(trace: RunTrace) -> Optional[TraceEvent]:
    """Return the last final-answer event in a trace, if present."""

    for event in reversed(trace.events):
        if event.event_type == "final_answer":
            return event
    return None


def final_answer_text(trace: RunTrace) -> Optional[str]:
    event = final_answer_event(trace)
    if event is None:
        return None
    value = event.payload.get("final_answer")
    return value if isinstance(value, str) else None


def tool_call_events(trace: RunTrace) -> List[TraceEvent]:
    return [event for event in trace.events if event.event_type == "tool_call"]


def observed_tool_names(trace: RunTrace) -> List[str]:
    names: List[str] = []
    for event in tool_call_events(trace):
        value = event.payload.get("tool_name")
        if isinstance(value, str):
            names.append(value)
    return names
