"""Phase 4A artifact-backed analysis scaffold."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from avf.contracts import MetricResult, RunTrace, SCHEMA_VERSION, ValidationError, VerificationResult
from avf.orchestration.dataset_freeze import (
    DATASET_REPORT_FILE,
    FROZEN_DATASET_MANIFEST_FILE,
)
from avf.orchestration.pilot_qa import (
    FAILURE_NOTES_JSON_FILE,
    PILOT_QA_SUMMARY_FILE,
    RERUN_RECORD_FILE,
    current_commit_hash,
    utc_timestamp,
)
from avf.orchestration.readiness_review import (
    DASHBOARD_REQUIREMENTS_FILE,
    QUERY_REQUIREMENTS_FILE,
    RESULTS_INDEX_DECISION_FILE,
    STORAGE_VOLUME_REVIEW_FILE,
)


PHASE4A_ANALYSIS_VERSION = "1.0"
ANALYSIS_CONFIG_FILE = "analysis_config.json"
ANALYSIS_INPUT_MANIFEST_FILE = "analysis_input_manifest.json"
METRICS_TABLE_JSON_FILE = "metrics_table.json"
METRICS_TABLE_CSV_FILE = "metrics_table.csv"
METRICS_TABLE_MARKDOWN_FILE = "metrics_table.md"

REQUIRED_COMPANION_FILES: Dict[str, str] = {
    "frozen_dataset_manifest": FROZEN_DATASET_MANIFEST_FILE,
    "dataset_report": DATASET_REPORT_FILE,
    "pilot_qa_summary": PILOT_QA_SUMMARY_FILE,
    "rerun_records": RERUN_RECORD_FILE,
    "failure_notes": FAILURE_NOTES_JSON_FILE,
    "storage_volume_review": STORAGE_VOLUME_REVIEW_FILE,
    "query_requirements": QUERY_REQUIREMENTS_FILE,
    "results_index_decision": RESULTS_INDEX_DECISION_FILE,
    "dashboard_requirements": DASHBOARD_REQUIREMENTS_FILE,
}

METRICS_TABLE_FIELDS = [
    "dataset_id",
    "experiment_id",
    "row_id",
    "run_id",
    "inclusion_status",
    "dataset_decision",
    "exclusion_reason",
    "task_id",
    "task_version",
    "run_config_id",
    "seed",
    "perturbation_schedule_id",
    "component_config_id",
    "memory_backend",
    "retrieval_strategy",
    "scheduling_policy",
    "tool_names",
    "status",
    "artifact_validation_passed",
    "artifact_hash_validation_passed",
    "task_success",
    "verification_passed",
    "verifier_id",
    "verifier_type",
    "verification_score",
    "failure_reason_count",
    "latency_ms",
    "step_count",
    "tool_call_count",
    "goal_drift",
    "repetition_rate",
    "recovery_steps",
    "trace_status",
    "trace_event_count",
    "final_answer_present",
    "token_usage",
    "cost_usage",
    "missing_metrics",
    "analysis_issues",
    "artifact_paths",
]


@dataclass(frozen=True)
class Phase4AAnalysisArtifacts:
    """Artifacts produced by the Phase 4A analysis scaffold."""

    analysis_config: Path
    analysis_input_manifest: Path
    metrics_table_json: Path
    metrics_table_csv: Path
    metrics_table_markdown: Path

    def to_dict(self) -> Dict[str, str]:
        return {
            "analysis_config": str(self.analysis_config),
            "analysis_input_manifest": str(self.analysis_input_manifest),
            "metrics_table_json": str(self.metrics_table_json),
            "metrics_table_csv": str(self.metrics_table_csv),
            "metrics_table_markdown": str(self.metrics_table_markdown),
        }


@dataclass(frozen=True)
class Phase4AAnalysisResult:
    """Outputs from Phase 4A frozen dataset analysis."""

    dataset_id: str
    experiment_id: str
    artifacts: Phase4AAnalysisArtifacts
    analysis_config: Dict[str, object]
    analysis_input_manifest: Dict[str, object]
    metrics_table: Dict[str, object]
    metrics_table_markdown: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "dataset_id": self.dataset_id,
            "experiment_id": self.experiment_id,
            "row_count": self.metrics_table["row_count"],
            "included_run_count": self.metrics_table["included_run_count"],
            "excluded_run_count": self.metrics_table["excluded_run_count"],
            "artifact_hash_validation_passed": self.analysis_input_manifest[
                "artifact_hash_validation_passed"
            ],
            "artifacts": self.artifacts.to_dict(),
        }


def analyze_phase4a_dataset(
    dataset_index_path: Path,
    analysis_root: Optional[Path] = None,
    artifact_root: Optional[Path] = None,
    analysis_id: Optional[str] = None,
    generated_at: Optional[str] = None,
    code_version: Optional[str] = None,
) -> Phase4AAnalysisResult:
    """Analyse a frozen Phase 3 dataset without rerunning experiments."""

    dataset_path = Path(dataset_index_path)
    dataset_index = _read_json_object(dataset_path, "dataset_index")
    _validate_dataset_index_shape(dataset_index)

    root = Path(artifact_root) if artifact_root is not None else infer_artifact_root(dataset_path)
    companion_artifacts = _load_companion_artifacts(dataset_path.parent, root)
    frozen_manifest = _companion_json(companion_artifacts, "frozen_dataset_manifest")
    _validate_frozen_manifest(dataset_index, frozen_manifest, dataset_path, root)

    dataset_id = _index_str(dataset_index, "dataset_id")
    experiment_id = _index_str(dataset_index, "experiment_id")
    timestamp = generated_at or utc_timestamp()
    version = code_version or current_commit_hash()
    resolved_analysis_id = analysis_id or f"{dataset_id}_phase4a"

    output_root = Path(analysis_root) if analysis_root is not None else root / "analysis"
    analysis_dir = output_root / dataset_id
    artifacts = Phase4AAnalysisArtifacts(
        analysis_config=analysis_dir / ANALYSIS_CONFIG_FILE,
        analysis_input_manifest=analysis_dir / ANALYSIS_INPUT_MANIFEST_FILE,
        metrics_table_json=analysis_dir / METRICS_TABLE_JSON_FILE,
        metrics_table_csv=analysis_dir / METRICS_TABLE_CSV_FILE,
        metrics_table_markdown=analysis_dir / METRICS_TABLE_MARKDOWN_FILE,
    )

    analysis_config = build_analysis_config(
        dataset_index=dataset_index,
        dataset_index_path=dataset_path,
        artifact_root=root,
        analysis_root=output_root,
        analysis_id=resolved_analysis_id,
        generated_at=timestamp,
        code_version=version,
    )
    input_manifest, hash_checks_by_run = build_analysis_input_manifest(
        dataset_index=dataset_index,
        dataset_index_path=dataset_path,
        frozen_manifest=frozen_manifest,
        companion_artifacts=companion_artifacts,
        artifact_root=root,
        generated_at=timestamp,
    )

    _write_json(artifacts.analysis_config, analysis_config)
    _write_json(artifacts.analysis_input_manifest, input_manifest)

    if not input_manifest["artifact_hash_validation_passed"]:
        issues = input_manifest["integrity_issues"]
        raise ValidationError(
            "Phase 4A analysis input validation failed; see "
            f"{artifacts.analysis_input_manifest}: {'; '.join(str(issue) for issue in issues)}"
        )

    rows = build_metrics_rows(dataset_index, root, hash_checks_by_run)
    metrics_table = build_metrics_table_payload(
        dataset_index=dataset_index,
        rows=rows,
        generated_at=timestamp,
        code_version=version,
    )
    metrics_markdown = build_metrics_table_markdown(metrics_table)

    _write_json(artifacts.metrics_table_json, metrics_table)
    _write_csv(artifacts.metrics_table_csv, rows)
    _write_text(artifacts.metrics_table_markdown, metrics_markdown)

    return Phase4AAnalysisResult(
        dataset_id=dataset_id,
        experiment_id=experiment_id,
        artifacts=artifacts,
        analysis_config=analysis_config,
        analysis_input_manifest=input_manifest,
        metrics_table=metrics_table,
        metrics_table_markdown=metrics_markdown,
    )


def infer_artifact_root(dataset_index_path: Path) -> Path:
    """Infer the artifact root from an experiment-level dataset index path."""

    path = Path(dataset_index_path)
    parent = path.parent
    if parent.parent.name == "experiments":
        return parent.parent.parent
    return Path("artifacts")


def build_analysis_config(
    dataset_index: Mapping[str, Any],
    dataset_index_path: Path,
    artifact_root: Path,
    analysis_root: Path,
    analysis_id: str,
    generated_at: str,
    code_version: str,
) -> Dict[str, object]:
    """Build the reproducibility record for Phase 4A analysis."""

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_version": PHASE4A_ANALYSIS_VERSION,
        "analysis_id": analysis_id,
        "dataset_id": dataset_index["dataset_id"],
        "experiment_id": dataset_index["experiment_id"],
        "dataset_index_path": str(dataset_index_path),
        "artifact_root": str(artifact_root),
        "analysis_root": str(analysis_root),
        "generated_at": generated_at,
        "code_version": code_version,
        "source_of_truth": "frozen filesystem artifacts referenced by dataset_index.json",
        "execution_policy": {
            "rerun_experiments": False,
            "mutate_raw_artifacts": False,
            "database_required": False,
            "dashboard_required": False,
        },
    }


def build_analysis_input_manifest(
    dataset_index: Mapping[str, Any],
    dataset_index_path: Path,
    frozen_manifest: Mapping[str, Any],
    companion_artifacts: Mapping[str, Dict[str, object]],
    artifact_root: Path,
    generated_at: str,
) -> Tuple[Dict[str, object], Dict[str, List[Dict[str, object]]]]:
    """Build and validate the Phase 4A input manifest."""

    dataset_record = _artifact_record("dataset_index", dataset_index_path, artifact_root)
    frozen_record = _artifact_record(
        "frozen_dataset_manifest",
        Path(str(companion_artifacts["frozen_dataset_manifest"]["path"])),
        artifact_root,
    )
    companion_records = {
        name: value["record"]
        for name, value in sorted(companion_artifacts.items())
    }

    integrity_issues = _frozen_manifest_integrity_issues(
        dataset_index=dataset_index,
        frozen_manifest=frozen_manifest,
        dataset_index_record=dataset_record,
    )
    artifact_checks: List[Dict[str, object]] = []
    checks_by_run: Dict[str, List[Dict[str, object]]] = {}
    for record in _records(dataset_index):
        run_id = _record_str(record, "run_id")
        run_checks: List[Dict[str, object]] = []
        for artifact_name, artifact in sorted(_artifact_records(record).items()):
            check = _build_hash_check(
                run_id=run_id,
                artifact_name=artifact_name,
                artifact_record=artifact,
                artifact_root=artifact_root,
            )
            artifact_checks.append(check)
            run_checks.append(check)
            if not check["passed"]:
                integrity_issues.extend(check["issues"])
        checks_by_run[run_id] = run_checks

    artifact_hash_validation_passed = not integrity_issues and all(
        bool(check["passed"]) for check in artifact_checks
    )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "analysis_version": PHASE4A_ANALYSIS_VERSION,
        "dataset_id": dataset_index["dataset_id"],
        "experiment_id": dataset_index["experiment_id"],
        "generated_at": generated_at,
        "dataset_index_artifact": dataset_record,
        "frozen_dataset_manifest_artifact": frozen_record,
        "companion_artifacts": companion_records,
        "run_artifact_checks": artifact_checks,
        "run_artifact_check_count": len(artifact_checks),
        "artifact_hash_validation_passed": artifact_hash_validation_passed,
        "integrity_issues": integrity_issues,
        "analysis_acceptance_criteria": {
            "dataset_index_consumed_without_rerun": True,
            "included_and_excluded_runs_represented": True,
            "artifact_paths_resolved_from_dataset_index": True,
            "artifact_hashes_checked": True,
            "database_or_dashboard_introduced": False,
        },
    }
    return manifest, checks_by_run


def build_metrics_rows(
    dataset_index: Mapping[str, Any],
    artifact_root: Path,
    hash_checks_by_run: Mapping[str, List[Mapping[str, object]]],
) -> List[Dict[str, object]]:
    """Build one normalized metrics row per dataset index record."""

    rows: List[Dict[str, object]] = []
    for record in _records(dataset_index):
        run_id = _record_str(record, "run_id")
        artifact_paths = _artifact_paths(record, artifact_root)
        analysis_issues: List[str] = []
        missing_metrics = ["token_usage", "cost_usage"]
        hash_checks = list(hash_checks_by_run.get(run_id, []))
        artifact_hash_validation_passed = bool(hash_checks) and all(
            bool(check["passed"]) for check in hash_checks
        )

        metrics = _load_metric_result(artifact_paths.get("metrics"), run_id, analysis_issues)
        verification = _load_verification_result(artifact_paths.get("verification"), run_id, analysis_issues)
        trace = _load_run_trace(artifact_paths.get("trace"), run_id, analysis_issues)

        if metrics is None:
            missing_metrics.extend(
                [
                    "task_success",
                    "latency_ms",
                    "step_count",
                    "tool_call_count",
                    "goal_drift",
                    "repetition_rate",
                    "recovery_steps",
                ]
            )

        row = {
            "dataset_id": dataset_index["dataset_id"],
            "experiment_id": dataset_index["experiment_id"],
            "row_id": _record_str(record, "row_id"),
            "run_id": run_id,
            "inclusion_status": _record_str(record, "inclusion_status"),
            "dataset_decision": _record_str(record, "dataset_decision"),
            "exclusion_reason": record.get("exclusion_reason"),
            "task_id": _record_str(record, "task_id"),
            "task_version": _record_str(record, "task_version"),
            "run_config_id": _record_str(record, "run_config_id"),
            "seed": _record_int(record, "seed"),
            "perturbation_schedule_id": _record_str(record, "perturbation_schedule_id"),
            "component_config_id": _record_str(record, "component_config_id"),
            "memory_backend": _record_str(record, "memory_backend"),
            "retrieval_strategy": _record_str(record, "retrieval_strategy"),
            "scheduling_policy": _record_str(record, "scheduling_policy"),
            "tool_names": list(record.get("tool_names", [])),
            "status": _record_str(record, "status"),
            "artifact_validation_passed": _record_bool(record, "artifact_validation_passed"),
            "artifact_hash_validation_passed": artifact_hash_validation_passed,
            "task_success": metrics.task_success if metrics is not None else record.get("task_success"),
            "verification_passed": verification.passed if verification is not None else record.get("verification_passed"),
            "verifier_id": verification.verifier_id if verification is not None else None,
            "verifier_type": verification.verifier_type if verification is not None else None,
            "verification_score": verification.score if verification is not None else None,
            "failure_reason_count": len(verification.failure_reasons) if verification is not None else None,
            "latency_ms": metrics.latency_ms if metrics is not None else None,
            "step_count": metrics.step_count if metrics is not None else None,
            "tool_call_count": metrics.tool_call_count if metrics is not None else None,
            "goal_drift": metrics.goal_drift if metrics is not None else None,
            "repetition_rate": metrics.repetition_rate if metrics is not None else None,
            "recovery_steps": metrics.recovery_steps if metrics is not None else None,
            "trace_status": trace.status if trace is not None else None,
            "trace_event_count": len(trace.events) if trace is not None else None,
            "final_answer_present": _final_answer_present(trace) if trace is not None else None,
            "token_usage": None,
            "cost_usage": None,
            "missing_metrics": sorted(set(missing_metrics)),
            "analysis_issues": analysis_issues,
            "artifact_paths": {
                name: str(path)
                for name, path in sorted(artifact_paths.items())
            },
        }
        rows.append(row)
    return rows


def build_metrics_table_payload(
    dataset_index: Mapping[str, Any],
    rows: List[Dict[str, object]],
    generated_at: str,
    code_version: str,
) -> Dict[str, object]:
    """Build the machine-readable normalized metrics table."""

    included = [row for row in rows if row["inclusion_status"] == "included"]
    excluded = [row for row in rows if row["inclusion_status"] == "excluded"]
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_version": PHASE4A_ANALYSIS_VERSION,
        "dataset_id": dataset_index["dataset_id"],
        "experiment_id": dataset_index["experiment_id"],
        "generated_at": generated_at,
        "code_version": code_version,
        "row_count": len(rows),
        "included_run_count": len(included),
        "excluded_run_count": len(excluded),
        "fields": list(METRICS_TABLE_FIELDS),
        "rows": rows,
        "limitations": {
            "current_dataset_is_descriptive": True,
            "token_usage_available": False,
            "cost_usage_available": False,
            "database_or_dashboard_required": False,
        },
    }


def build_metrics_table_markdown(metrics_table: Mapping[str, Any]) -> str:
    """Build a compact human-readable Phase 4A metrics table."""

    lines = [
        "# Phase 4A Metrics Table",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Dataset ID | `{metrics_table['dataset_id']}` |",
        f"| Experiment ID | `{metrics_table['experiment_id']}` |",
        f"| Row count | {metrics_table['row_count']} |",
        f"| Included runs | {metrics_table['included_run_count']} |",
        f"| Excluded runs | {metrics_table['excluded_run_count']} |",
        f"| Generated at | `{metrics_table['generated_at']}` |",
        "",
        "## Normalized Run Metrics",
        "",
        "| Run ID | Component | Included | Task success | Verification | Steps | Tools | Final answer | Missing metrics |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in metrics_table["rows"]:
        lines.append(
            f"| `{row['run_id']}` | `{row['component_config_id']}` | "
            f"`{row['inclusion_status']}` | `{_markdown_bool(row['task_success'])}` | "
            f"`{_markdown_bool(row['verification_passed'])}` | `{_markdown_value(row['step_count'])}` | "
            f"`{_markdown_value(row['tool_call_count'])}` | `{_markdown_bool(row['final_answer_present'])}` | "
            f"{', '.join(str(item) for item in row['missing_metrics'])} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation Note",
            "",
            "This Phase 4A table is a normalized analysis scaffold over frozen artifacts. "
            "The current dataset is suitable for descriptive checks and later component-effect "
            "summaries, but token and cost metrics are unavailable until model adapters expose them.",
            "",
        ]
    )
    return "\n".join(lines)


def _load_companion_artifacts(experiment_dir: Path, artifact_root: Path) -> Dict[str, Dict[str, object]]:
    values: Dict[str, Dict[str, object]] = {}
    for name, filename in sorted(REQUIRED_COMPANION_FILES.items()):
        path = experiment_dir / filename
        if not path.exists():
            raise ValidationError(f"Required Phase 4A input artifact not found: {path}")
        payload: Optional[Dict[str, Any]] = None
        if path.suffix == ".json":
            payload = _read_json_object(path, name)
        values[name] = {
            "path": path,
            "payload": payload,
            "record": _artifact_record(name, path, artifact_root),
        }
    return values


def _companion_json(companion_artifacts: Mapping[str, Mapping[str, object]], name: str) -> Dict[str, Any]:
    payload = companion_artifacts[name].get("payload")
    if not isinstance(payload, dict):
        raise ValidationError(f"Phase 4A companion artifact must be JSON: {name}")
    return payload


def _validate_dataset_index_shape(dataset_index: Mapping[str, Any]) -> None:
    if dataset_index.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError("dataset_index.schema_version is invalid")
    _index_str(dataset_index, "dataset_id")
    _index_str(dataset_index, "experiment_id")
    run_count = _index_int(dataset_index, "run_count")
    records = _records(dataset_index)
    if run_count != len(records):
        raise ValidationError("dataset_index.run_count does not match records length")


def _validate_frozen_manifest(
    dataset_index: Mapping[str, Any],
    frozen_manifest: Mapping[str, Any],
    dataset_index_path: Path,
    artifact_root: Path,
) -> None:
    dataset_record = _artifact_record("dataset_index", dataset_index_path, artifact_root)
    issues = _frozen_manifest_integrity_issues(dataset_index, frozen_manifest, dataset_record)
    if issues:
        raise ValidationError("Invalid frozen dataset manifest: " + "; ".join(issues))


def _frozen_manifest_integrity_issues(
    dataset_index: Mapping[str, Any],
    frozen_manifest: Mapping[str, Any],
    dataset_index_record: Mapping[str, object],
) -> List[str]:
    issues: List[str] = []
    if frozen_manifest.get("schema_version") != SCHEMA_VERSION:
        issues.append("frozen_dataset_manifest.schema_version is invalid")
    if frozen_manifest.get("dataset_id") != dataset_index.get("dataset_id"):
        issues.append("dataset index and frozen manifest dataset_id values do not match")
    if frozen_manifest.get("experiment_id") != dataset_index.get("experiment_id"):
        issues.append("dataset index and frozen manifest experiment_id values do not match")
    if frozen_manifest.get("frozen") is not True:
        issues.append("frozen dataset manifest must have frozen=true")

    freeze_artifacts = frozen_manifest.get("freeze_artifacts")
    if not isinstance(freeze_artifacts, dict):
        issues.append("frozen_dataset_manifest.freeze_artifacts must be an object")
    else:
        expected = freeze_artifacts.get("dataset_index")
        if not isinstance(expected, dict):
            issues.append("frozen manifest must include dataset_index freeze artifact")
        elif expected.get("sha256") != dataset_index_record.get("sha256"):
            issues.append("dataset_index hash does not match frozen manifest")
    return issues


def _build_hash_check(
    run_id: str,
    artifact_name: str,
    artifact_record: Mapping[str, Any],
    artifact_root: Path,
) -> Dict[str, object]:
    recorded_path = _artifact_record_str(artifact_record, "path", artifact_name)
    expected_sha = _artifact_record_str(artifact_record, "sha256", artifact_name)
    expected_size = _artifact_record_int(artifact_record, "size_bytes", artifact_name)
    resolved_path = _resolve_artifact_path(recorded_path, artifact_root)
    issues: List[str] = []
    actual_sha: Optional[str] = None
    actual_size: Optional[int] = None
    if not resolved_path.exists():
        issues.append(f"Missing {artifact_name} artifact for {run_id}: {resolved_path}")
    else:
        try:
            payload = resolved_path.read_bytes()
        except OSError as exc:
            issues.append(f"Could not read {artifact_name} artifact for {run_id}: {exc}")
        else:
            actual_sha = hashlib.sha256(payload).hexdigest()
            actual_size = len(payload)
            if actual_sha != expected_sha:
                issues.append(f"{artifact_name} artifact hash mismatch for {run_id}")
            if actual_size != expected_size:
                issues.append(f"{artifact_name} artifact size mismatch for {run_id}")

    return {
        "run_id": run_id,
        "artifact_name": artifact_name,
        "recorded_path": recorded_path,
        "resolved_path": str(resolved_path),
        "expected_sha256": expected_sha,
        "actual_sha256": actual_sha,
        "expected_size_bytes": expected_size,
        "actual_size_bytes": actual_size,
        "passed": not issues,
        "issues": issues,
    }


def _artifact_paths(record: Mapping[str, Any], artifact_root: Path) -> Dict[str, Path]:
    return {
        name: _resolve_artifact_path(_artifact_record_str(artifact, "path", name), artifact_root)
        for name, artifact in sorted(_artifact_records(record).items())
    }


def _load_metric_result(path: Optional[Path], run_id: str, issues: List[str]) -> Optional[MetricResult]:
    if path is None:
        issues.append(f"Missing metrics artifact path for {run_id}")
        return None
    try:
        metrics = MetricResult.from_dict(_read_json_object(path, "metrics"))
    except ValidationError as exc:
        issues.append(str(exc))
        return None
    if metrics.run_id != run_id:
        issues.append(f"Metrics run_id mismatch for {run_id}: {metrics.run_id}")
        return None
    return metrics


def _load_verification_result(path: Optional[Path], run_id: str, issues: List[str]) -> Optional[VerificationResult]:
    if path is None:
        issues.append(f"Missing verification artifact path for {run_id}")
        return None
    try:
        verification = VerificationResult.from_dict(_read_json_object(path, "verification"))
    except ValidationError as exc:
        issues.append(str(exc))
        return None
    if verification.run_id != run_id:
        issues.append(f"Verification run_id mismatch for {run_id}: {verification.run_id}")
        return None
    return verification


def _load_run_trace(path: Optional[Path], run_id: str, issues: List[str]) -> Optional[RunTrace]:
    if path is None:
        issues.append(f"Missing trace artifact path for {run_id}")
        return None
    try:
        trace = RunTrace.from_dict(_read_json_object(path, "trace"))
    except ValidationError as exc:
        issues.append(str(exc))
        return None
    if trace.run_id != run_id:
        issues.append(f"Trace run_id mismatch for {run_id}: {trace.run_id}")
        return None
    return trace


def _final_answer_present(trace: RunTrace) -> bool:
    for event in trace.events:
        if event.event_type != "final_answer":
            continue
        answer = event.payload.get("final_answer")
        if isinstance(answer, str) and answer:
            return True
    return False


def _artifact_record(name: str, path: Path, artifact_root: Path) -> Dict[str, object]:
    try:
        payload = Path(path).read_bytes()
    except OSError as exc:
        raise ValidationError(f"Could not read Phase 4A artifact {path}: {exc}") from exc
    return {
        "name": name,
        "path": _relative_path(Path(path), artifact_root),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def _records(dataset_index: Mapping[str, Any]) -> List[Dict[str, Any]]:
    records = dataset_index.get("records")
    if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
        raise ValidationError("dataset_index.records must be a list of objects")
    return records


def _artifact_records(record: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    artifacts = record.get("artifact_records")
    if not isinstance(artifacts, dict) or any(not isinstance(value, dict) for value in artifacts.values()):
        raise ValidationError("record.artifact_records must be an object of artifact records")
    return dict(artifacts)


def _read_json_object(path: Path, artifact_name: str) -> Dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"Required {artifact_name} artifact not found: {path}") from exc
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValidationError(f"Invalid {artifact_name} JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError(f"{artifact_name} artifact must contain a JSON object: {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_csv(path: Path, rows: List[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=METRICS_TABLE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_cell(row.get(field)) for field in METRICS_TABLE_FIELDS})


def _resolve_artifact_path(recorded_path: str, artifact_root: Path) -> Path:
    path = Path(recorded_path)
    if path.is_absolute():
        return path
    return artifact_root / path


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(Path(path).relative_to(root))
    except ValueError:
        return str(path)


def _csv_cell(value: object) -> object:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    if value is None:
        return ""
    return value


def _markdown_bool(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _markdown_value(value: object) -> str:
    return "n/a" if value is None else str(value)


def _index_str(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ValidationError(f"dataset_index.{field} must be a non-empty string")
    return value


def _index_int(payload: Mapping[str, Any], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"dataset_index.{field} must be an integer")
    return value


def _record_str(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise ValidationError(f"record.{field} must be a non-empty string")
    return value


def _record_int(record: Mapping[str, Any], field: str) -> int:
    value = record.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"record.{field} must be an integer")
    return value


def _record_bool(record: Mapping[str, Any], field: str) -> bool:
    value = record.get(field)
    if not isinstance(value, bool):
        raise ValidationError(f"record.{field} must be a boolean")
    return value


def _artifact_record_str(record: Mapping[str, Any], field: str, artifact_name: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{artifact_name}.{field} must be a non-empty string")
    return value


def _artifact_record_int(record: Mapping[str, Any], field: str, artifact_name: str) -> int:
    value = record.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{artifact_name}.{field} must be an integer")
    return value
