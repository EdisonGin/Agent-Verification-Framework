"""JSON trace artifact reader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from avf.contracts import RunTrace, ValidationError

from .validation import validate_run_trace


class TraceReader:
    """Read and validate RunTrace JSON artifacts."""

    def read(self, path: Path) -> RunTrace:
        try:
            with Path(path).open("r", encoding="utf-8") as handle:
                payload: Dict[str, Any] = json.load(handle)
        except FileNotFoundError as exc:
            raise ValidationError(f"RunTrace artifact not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid RunTrace JSON in {path}: {exc}") from exc

        if not isinstance(payload, dict):
            raise ValidationError(f"RunTrace artifact must contain a JSON object: {path}")

        trace = RunTrace.from_dict(payload)
        validate_run_trace(trace)
        return trace


def read_run_trace(path: Path) -> RunTrace:
    return TraceReader().read(path)

