"""Phase 1I reproducible baseline run orchestration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

from avf.agents import BaselineSUTAgent
from avf.agents.components import ComponentBundle, build_component_bundle
from avf.contracts import MetricResult, RunTrace, VerificationResult
from avf.metrics import calculate_metric_result
from avf.mock_services import MockMemoryService
from avf.reporting.markdown import build_run_report
from avf.storage import FileSystemResultsStore
from avf.tracing import build_run_trace_from_agent_result
from avf.verification import RuleBasedVerifier

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
    component_bundle: ComponentBundle
    trace: RunTrace
    verification: VerificationResult
    metrics: MetricResult
    artifact_paths: BaselineRunArtifactPaths

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.trace.run_id,
            "status": self.trace.status,
            "task_success": self.metrics.task_success,
            "component_bundle": self.component_bundle.to_dict(),
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
    component_bundle = build_component_bundle(run_context.component_config)
    results_store = FileSystemResultsStore.from_run_config(run_context.run_config, artifact_root)

    agent_result = BaselineSUTAgent().run(
        run_context.to_agent_run_input(),
        MockMemoryService(memory_backend=component_bundle.memory_module),
    )
    trace = build_run_trace_from_agent_result(run_context, agent_result)
    verification = RuleBasedVerifier().verify(run_context.task, trace)
    metrics = calculate_metric_result(trace, verification)

    trace_path = results_store.write_trace(trace)
    verification_path = results_store.write_verification_result(verification)
    metrics_path = results_store.write_metric_result(metrics)

    artifact_paths = BaselineRunArtifactPaths(
        trace=trace_path,
        verification=verification_path,
        metrics=metrics_path,
        report=results_store.report_path(trace.run_id),
    )
    report = build_run_report(
        task=run_context.task,
        trace=trace,
        verification=verification,
        metrics=metrics,
        artifact_paths=results_store.relative_paths(asdict(artifact_paths)),
    )
    report_path = results_store.write_report(trace.run_id, report)

    return BaselineRunResult(
        run_context=run_context,
        component_bundle=component_bundle,
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
