"""Filesystem-backed results store for trace, verification, metrics, and reports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional

from avf.contracts import MetricResult, RunConfig, RunTrace, VerificationResult
from avf.metrics.writer import MetricResultWriter
from avf.reporting.markdown import MarkdownReportWriter
from avf.tracing.writer import TraceWriter
from avf.verification.writer import VerificationResultWriter


@dataclass(frozen=True)
class ResultsStoreLayout:
    """Directory layout for one filesystem-backed results store."""

    artifact_root: Path
    trace_dir: Path
    result_dir: Path
    report_dir: Path


class FileSystemResultsStore:
    """Write Phase 1/2 artifacts using the current filesystem results store."""

    def __init__(self, layout: ResultsStoreLayout) -> None:
        self.layout = layout

    @classmethod
    def from_run_config(cls, run_config: RunConfig, artifact_root: Optional[Path] = None) -> "FileSystemResultsStore":
        if artifact_root is not None:
            root = Path(artifact_root)
            return cls(
                ResultsStoreLayout(
                    artifact_root=root,
                    trace_dir=root / "traces",
                    result_dir=root / "results",
                    report_dir=root / "reports",
                )
            )

        trace_dir = Path(str(run_config.artifacts.get("trace_dir", "artifacts/traces")))
        result_dir = Path(str(run_config.artifacts.get("result_dir", "artifacts/results")))
        report_dir = Path(str(run_config.artifacts.get("report_dir", "artifacts/reports")))
        return cls(
            ResultsStoreLayout(
                artifact_root=_common_artifact_root(trace_dir, result_dir, report_dir),
                trace_dir=trace_dir,
                result_dir=result_dir,
                report_dir=report_dir,
            )
        )

    def trace_path(self, run_id: str) -> Path:
        return TraceWriter(self.layout.trace_dir).path_for(run_id)

    def verification_path(self, result: VerificationResult) -> Path:
        return VerificationResultWriter(self.layout.result_dir).path_for(result)

    def metrics_path(self, result: MetricResult) -> Path:
        return MetricResultWriter(self.layout.result_dir).path_for(result)

    def report_path(self, run_id: str) -> Path:
        return MarkdownReportWriter(self.layout.report_dir).path_for(run_id)

    def write_trace(self, trace: RunTrace) -> Path:
        return TraceWriter(self.layout.trace_dir).write(trace)

    def write_verification_result(self, result: VerificationResult) -> Path:
        return VerificationResultWriter(self.layout.result_dir).write(result)

    def write_metric_result(self, result: MetricResult) -> Path:
        return MetricResultWriter(self.layout.result_dir).write(result)

    def write_report(self, run_id: str, content: str) -> Path:
        return MarkdownReportWriter(self.layout.report_dir).write(run_id, content)

    def relative_paths(self, paths: Mapping[str, Path]) -> Dict[str, str]:
        values: Dict[str, str] = {}
        for name, path in paths.items():
            try:
                values[name] = str(Path(path).relative_to(self.layout.artifact_root))
            except ValueError:
                values[name] = str(path)
        return values


def _common_artifact_root(*paths: Path) -> Path:
    parts = [path.parts for path in paths if path.parts]
    if not parts:
        return Path(".")
    shared = []
    for index, part in enumerate(parts[0]):
        if all(len(candidate) > index and candidate[index] == part for candidate in parts):
            shared.append(part)
        else:
            break
    return Path(*shared) if shared else Path(".")
