"""Deterministic trace-event construction for the Phase 1E baseline agent."""

from __future__ import annotations

from typing import Any, Dict

from avf.contracts import TraceEvent


class TraceBuilder:
    """Build trace events without timestamps from wall-clock time."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._counter = 0

    def event(self, event_type: str, step_index: int, payload: Dict[str, Any]) -> TraceEvent:
        self._counter += 1
        return TraceEvent(
            event_id=f"{self.run_id}_event_{self._counter:03d}",
            run_id=self.run_id,
            event_type=event_type,
            step_index=step_index,
            timestamp=f"1970-01-01T00:00:{self._counter:02d}Z",
            payload=payload,
        )

