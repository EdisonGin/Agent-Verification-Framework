"""JSON artifact writer for metric results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from avf.contracts import MetricResult


class MetricResultWriter:
    """Write one MetricResult JSON artifact per run."""

    def __init__(self, result_dir: Path) -> None:
        self.result_dir = Path(result_dir)

    def path_for(self, result: MetricResult) -> Path:
        return self.result_dir / f"{result.run_id}.metrics.json"

    def write(self, result: MetricResult, path: Optional[Path] = None) -> Path:
        MetricResult.from_dict(result.to_dict())
        output_path = Path(path) if path is not None else self.path_for(result)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(result.to_dict(), handle, indent=2, sort_keys=True)
            handle.write("\n")
        return output_path


def write_metric_result(result: MetricResult, result_dir: Path) -> Path:
    return MetricResultWriter(result_dir).write(result)
