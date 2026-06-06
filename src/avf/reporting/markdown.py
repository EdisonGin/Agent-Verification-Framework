"""Markdown report generation for one baseline run."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from avf.contracts import MetricResult, RunTrace, TaskCase, VerificationResult
from avf.verification import observed_tool_names


def build_run_report(
    task: TaskCase,
    trace: RunTrace,
    verification: VerificationResult,
    metrics: MetricResult,
    artifact_paths: Optional[Dict[str, str]] = None,
) -> str:
    paths = artifact_paths or {}
    tool_names = observed_tool_names(trace)
    lines = [
        "# Phase 1 Baseline Run Report",
        "",
        "## Run Summary",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Run ID | `{trace.run_id}` |",
        f"| Task | `{task.task_id}` - {task.name} |",
        f"| Component config | `{trace.component_config_id}` |",
        f"| Seed | `{trace.seed}` |",
        f"| Perturbation schedule | `{trace.perturbation_schedule_id}` |",
        f"| Run status | `{trace.status}` |",
        f"| Task success | `{str(metrics.task_success).lower()}` |",
        f"| Verifier | `{verification.verifier_id}` |",
        f"| Verifier passed | `{str(verification.passed).lower()}` |",
        "",
        "## Tool Calls",
        "",
        "| Index | Tool |",
        "|---:|---|",
    ]
    if tool_names:
        for index, tool_name in enumerate(tool_names, start=1):
            lines.append(f"| {index} | `{tool_name}` |")
    else:
        lines.append("| 0 | none |")

    lines.extend(
        [
            "",
            "## Metrics",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Step count | {metrics.step_count} |",
            f"| Tool call count | {metrics.tool_call_count} |",
            f"| Latency ms | {metrics.latency_ms} |",
            f"| Goal drift | {metrics.goal_drift:.4f} |",
            f"| Repetition rate | {metrics.repetition_rate:.4f} |",
            f"| Recovery steps | {_format_optional_int(metrics.recovery_steps)} |",
            "",
            "## Verification Evidence",
            "",
            "| Check | Passed | Evidence |",
            "|---|---|---|",
        ]
    )
    for item in verification.evidence:
        check = str(item.get("check", "unknown"))
        passed = str(item.get("passed", False)).lower()
        evidence = _format_evidence(item)
        lines.append(f"| `{check}` | `{passed}` | {evidence} |")

    if verification.failure_reasons:
        lines.extend(["", "## Failure Reasons", ""])
        for reason in verification.failure_reasons:
            lines.append(f"- {reason}")

    if paths:
        lines.extend(["", "## Artifacts", "", "| Artifact | Path |", "|---|---|"])
        for name in sorted(paths):
            lines.append(f"| {name} | `{paths[name]}` |")

    return "\n".join(lines) + "\n"


class MarkdownReportWriter:
    """Write one Markdown report per run."""

    def __init__(self, report_dir: Path) -> None:
        self.report_dir = Path(report_dir)

    def path_for(self, run_id: str) -> Path:
        return self.report_dir / f"{run_id}.md"

    def write(self, run_id: str, content: str, path: Optional[Path] = None) -> Path:
        output_path = Path(path) if path is not None else self.path_for(run_id)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        return output_path


def write_run_report(
    task: TaskCase,
    trace: RunTrace,
    verification: VerificationResult,
    metrics: MetricResult,
    report_dir: Path,
    artifact_paths: Optional[Dict[str, str]] = None,
) -> Path:
    content = build_run_report(task, trace, verification, metrics, artifact_paths)
    return MarkdownReportWriter(report_dir).write(trace.run_id, content)


def _format_optional_int(value: Optional[int]) -> str:
    return "none" if value is None else str(value)


def _format_evidence(item: Dict[str, object]) -> str:
    if "event_id" in item:
        return f"`{item['event_id']}`"
    if "expected" in item:
        return f"expected `{item['expected']}`"
    return str(item.get("description", ""))
