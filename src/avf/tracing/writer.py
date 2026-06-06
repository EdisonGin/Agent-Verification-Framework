"""JSON trace artifact writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from avf.contracts import RunTrace

from .validation import validate_run_trace


class TraceWriter:
    """Write one complete RunTrace JSON artifact per run."""

    def __init__(self, trace_dir: Path) -> None:
        self.trace_dir = Path(trace_dir)

    def path_for(self, run_id: str) -> Path:
        return self.trace_dir / f"{run_id}.json"

    def write(self, trace: RunTrace, path: Optional[Path] = None) -> Path:
        validate_run_trace(trace)
        output_path = Path(path) if path is not None else self.path_for(trace.run_id)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(trace.to_dict(), handle, indent=2, sort_keys=True)
            handle.write("\n")
        return output_path


def write_run_trace(trace: RunTrace, trace_dir: Path) -> Path:
    return TraceWriter(trace_dir).write(trace)

