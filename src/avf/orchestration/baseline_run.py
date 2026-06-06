"""Phase 1I reproducible baseline run orchestration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

from avf.agents import BaselineSUTAgent
from avf.contracts import MetricResult, RunTrace, VerificationResult
from avf.metrics import MetricResultWriter, calculate_metric_result
from avf.mock_services import MockMemoryService
from avf.reporting import MarkdownReportWriter, build_run_report
from avf.tracing import TraceWriter, build_run_trace_from_agent_result
from avf.verification import RuleBasedVerifier, VerificationResultWriter

from .run_context import RunContext, build_run_context_from_files


@dataclass(frozen=True)
class BaselineRunArtifactPaths:
    """Paths written by one Phase 1I baseline run."""

    trace: Path
    verification: Path
    metrics: Path
    report: Path

    def to_dict(self) -> Dict[str, str]:
        return {name: str(path) for name, path in asdict(self).items()}


@dataclass(frozen=True)
class BaselineRunResult:
    """In-memory and persisted outputs from one baseline run."""

    run_context: RunContext
    trace: RunTrace
    verification: VerificationResult
    metrics: MetricResult
    artifact_paths: BaselineRunArtifactPaths

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.trace.run_id,
            "status": self.trace.status,
            "task_success": self.metrics.task_success,
            "trace": self.trace.to_dict(),
            "verification": self.verification.to_dict(),
            "metrics": self.metrics.to_dict(),
            "artifacts": self.artifact_paths.to_dict(),
        }


def run_phase1_baseline(
    task_path: Path,
    run_config_path: Path,
    component_config_path: Path,
    tool_spec_paths: List[Path],
    artifact_root: Optional[Path] = None,
) -> BaselineRunResult:
    """Execute the deterministic Phase 1 baseline and write all artifacts."""

    run_context = build_run_context_from_files(
        task_path=task_path,
        run_config_path=run_config_path,
        component_config_path=component_config_path,
        tool_spec_paths=tool_spec_paths,
    )
    layout = _artifact_layout(run_context, artifact_root)

    agent_result = BaselineSUTAgent().run(run_context.to_agent_run_input(), MockMemoryService())
    trace = build_run_trace_from_agent_result(run_context, agent_result)
    verification = RuleBasedVerifier().verify(run_context.task, trace)
    metrics = calculate_metric_result(trace, verification)

    trace_path = TraceWriter(layout["trace_dir"]).write(trace)
    verification_path = VerificationResultWriter(layout["result_dir"]).write(verification)
    metrics_path = MetricResultWriter(layout["result_dir"]).write(metrics)

    artifact_paths = BaselineRunArtifactPaths(
        trace=trace_path,
        verification=verification_path,
        metrics=metrics_path,
        report=layout["report_dir"] / f"{trace.run_id}.md",
    )
    report = build_run_report(
        task=run_context.task,
        trace=trace,
        verification=verification,
        metrics=metrics,
        artifact_paths=_relative_artifact_paths(artifact_paths, layout["artifact_root"]),
    )
    report_path = MarkdownReportWriter(layout["report_dir"]).write(trace.run_id, report, artifact_paths.report)

    return BaselineRunResult(
        run_context=run_context,
        trace=trace,
        verification=verification,
        metrics=metrics,
        artifact_paths=BaselineRunArtifactPaths(
            trace=trace_path,
            verification=verification_path,
            metrics=metrics_path,
            report=report_path,
        ),
    )


def _artifact_layout(run_context: RunContext, artifact_root: Optional[Path]) -> Dict[str, Path]:
    if artifact_root is not None:
        root = Path(artifact_root)
        return {
            "artifact_root": root,
            "trace_dir": root / "traces",
            "result_dir": root / "results",
            "report_dir": root / "reports",
        }

    trace_dir = Path(str(run_context.run_config.artifacts.get("trace_dir", "artifacts/traces")))
    result_dir = Path(str(run_context.run_config.artifacts.get("result_dir", "artifacts/results")))
    report_dir = Path(str(run_context.run_config.artifacts.get("report_dir", "artifacts/reports")))
    artifact_root = _common_artifact_root(trace_dir, result_dir, report_dir)
    return {
        "artifact_root": artifact_root,
        "trace_dir": trace_dir,
        "result_dir": result_dir,
        "report_dir": report_dir,
    }


def _relative_artifact_paths(paths: BaselineRunArtifactPaths, artifact_root: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for name, path in asdict(paths).items():
        try:
            values[name] = str(Path(path).relative_to(artifact_root))
        except ValueError:
            values[name] = str(path)
    return values


def _common_artifact_root(*paths: Path) -> Path:
    parts = [path.parts for path in paths if path.parts]
    if not parts:
        return Path(".")
    shared: List[str] = []
    for index, part in enumerate(parts[0]):
        if all(len(candidate) > index and candidate[index] == part for candidate in parts):
            shared.append(part)
        else:
            break
    return Path(*shared) if shared else Path(".")
