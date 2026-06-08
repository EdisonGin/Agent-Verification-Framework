"""Phase 4D failure analysis and final analysis report."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from avf.contracts import MetricResult, RunTrace, SCHEMA_VERSION, ValidationError, VerificationResult
from avf.orchestration.pilot_qa import (
    FAILURE_NOTES_JSON_FILE,
    PILOT_LOG_FILE,
    PILOT_QA_SUMMARY_FILE,
    RERUN_RECORD_FILE,
    current_commit_hash,
    utc_timestamp,
)


PHASE4D_ANALYSIS_VERSION = "1.0"
FAILURE_ANALYSIS_JSON_FILE = "failure_analysis.json"
FAILURE_ANALYSIS_MARKDOWN_FILE = "failure_analysis.md"
ANALYSIS_REPORT_FILE = "analysis_report.md"

COMPONENT_EFFECTS_JSON_FILE = "component_effects.json"
INTERACTION_SUMMARY_JSON_FILE = "interaction_summary.json"
TRAJECTORY_DIAGNOSTICS_JSON_FILE = "trajectory_diagnostics.json"
ANALYSIS_CONFIG_FILE = "analysis_config.json"

FAILURE_CLASSES = [
    "passed",
    "task_failure",
    "verifier_failure",
    "artifact_failure",
    "infrastructure_failure",
    "dataset_excluded",
]


@dataclass(frozen=True)
class Phase4DFailureAnalysisArtifacts:
    """Artifacts produced by Phase 4D failure analysis."""

    failure_analysis_json: Path
    failure_analysis_markdown: Path
    analysis_report: Path

    def to_dict(self) -> Dict[str, str]:
        return {
            "failure_analysis_json": str(self.failure_analysis_json),
            "failure_analysis_markdown": str(self.failure_analysis_markdown),
            "analysis_report": str(self.analysis_report),
        }


@dataclass(frozen=True)
class Phase4DFailureAnalysisResult:
    """Outputs from Phase 4D failure analysis and final report generation."""

    dataset_id: str
    experiment_id: str
    artifacts: Phase4DFailureAnalysisArtifacts
    failure_analysis: Dict[str, object]
    failure_analysis_markdown: str
    analysis_report: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "dataset_id": self.dataset_id,
            "experiment_id": self.experiment_id,
            "run_count": self.failure_analysis["run_count"],
            "ordinary_task_outcome_count": self.failure_analysis["ordinary_task_outcome_count"],
            "infrastructure_failure_count": self.failure_analysis["taxonomy_counts"]["infrastructure_failure"],
            "descriptive_only": self.failure_analysis["limitations"]["descriptive_only"],
            "artifacts": self.artifacts.to_dict(),
        }


def write_phase4d_failure_analysis_report(
    metrics_table_path: Path,
    analysis_root: Optional[Path] = None,
    generated_at: Optional[str] = None,
    code_version: Optional[str] = None,
) -> Phase4DFailureAnalysisResult:
    """Write Phase 4D failure analysis and final analysis report artifacts."""

    metrics_path = Path(metrics_table_path)
    metrics_table = _read_json_object(metrics_path, "metrics_table")
    _validate_metrics_table(metrics_table)

    dataset_id = _table_str(metrics_table, "dataset_id")
    experiment_id = _table_str(metrics_table, "experiment_id")
    timestamp = generated_at or utc_timestamp()
    version = code_version or current_commit_hash()
    output_root = Path(analysis_root) if analysis_root is not None else metrics_path.parent.parent
    analysis_dir = output_root / dataset_id
    artifacts = Phase4DFailureAnalysisArtifacts(
        failure_analysis_json=analysis_dir / FAILURE_ANALYSIS_JSON_FILE,
        failure_analysis_markdown=analysis_dir / FAILURE_ANALYSIS_MARKDOWN_FILE,
        analysis_report=analysis_dir / ANALYSIS_REPORT_FILE,
    )

    context = _load_phase4d_context(metrics_path, analysis_dir)
    failure_analysis = build_failure_analysis_payload(
        metrics_table=metrics_table,
        metrics_table_path=metrics_path,
        context=context,
        generated_at=timestamp,
        code_version=version,
    )
    failure_markdown = build_failure_analysis_markdown(failure_analysis)
    analysis_report = build_analysis_report_markdown(failure_analysis)

    _write_json(artifacts.failure_analysis_json, failure_analysis)
    _write_text(artifacts.failure_analysis_markdown, failure_markdown)
    _write_text(artifacts.analysis_report, analysis_report)

    return Phase4DFailureAnalysisResult(
        dataset_id=dataset_id,
        experiment_id=experiment_id,
        artifacts=artifacts,
        failure_analysis=failure_analysis,
        failure_analysis_markdown=failure_markdown,
        analysis_report=analysis_report,
    )


def build_failure_analysis_payload(
    metrics_table: Mapping[str, Any],
    metrics_table_path: Path,
    context: Mapping[str, Any],
    generated_at: str,
    code_version: str,
) -> Dict[str, object]:
    """Build the machine-readable Phase 4D failure analysis artifact."""

    rows = _metric_rows(metrics_table)
    run_outcomes = [build_run_failure_outcome(row) for row in rows]
    taxonomy_counts = Counter(str(outcome["failure_class"]) for outcome in run_outcomes)
    for failure_class in FAILURE_CLASSES:
        taxonomy_counts.setdefault(failure_class, 0)

    failure_notes = list(context["failure_notes"])
    rerun_records = list(context["rerun_records"])
    qa_decision_links = _qa_decision_links(
        failure_notes=failure_notes,
        rerun_records=rerun_records,
        context=context,
    )
    infrastructure_outcomes = [
        outcome
        for outcome in run_outcomes
        if outcome["failure_class"] in {"artifact_failure", "infrastructure_failure"}
    ]
    ordinary_task_outcomes = [
        outcome
        for outcome in run_outcomes
        if outcome["included_as_task_outcome"] is True
    ]
    component_effects = context.get("component_effects") or {}
    trajectory_diagnostics = context.get("trajectory_diagnostics") or {}
    pilot_qa_summary = context.get("pilot_qa_summary") or {}

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_version": PHASE4D_ANALYSIS_VERSION,
        "dataset_id": metrics_table["dataset_id"],
        "experiment_id": metrics_table["experiment_id"],
        "generated_at": generated_at,
        "code_version": code_version,
        "metrics_table_artifact": str(metrics_table_path),
        "analysis_artifacts_consumed": context["analysis_artifacts"],
        "qa_artifacts_consumed": context["qa_artifacts"],
        "run_count": metrics_table["row_count"],
        "ordinary_task_outcome_count": len(ordinary_task_outcomes),
        "taxonomy_counts": dict(sorted(taxonomy_counts.items())),
        "failure_note_count": len(failure_notes),
        "rerun_record_count": len(rerun_records),
        "failure_notes_by_class": _failure_notes_by_class(failure_notes),
        "qa_decision_links": qa_decision_links,
        "run_outcomes": run_outcomes,
        "infrastructure_separation": {
            "infrastructure_or_artifact_issue_count": len(infrastructure_outcomes),
            "counted_as_ordinary_task_outcomes": False,
            "policy": (
                "artifact_failure and infrastructure_failure rows are preserved for auditability "
                "but excluded from ordinary task outcome counts unless explicitly justified."
            ),
        },
        "analysis_summary": {
            "component_complete_block_count": component_effects.get("complete_block_count"),
            "component_incomplete_block_count": component_effects.get("incomplete_block_count"),
            "trajectory_agent_behavior_row_count": (
                trajectory_diagnostics.get("scope_counts", {}).get("agent_behavior")
                if isinstance(trajectory_diagnostics.get("scope_counts"), dict)
                else None
            ),
            "pilot_decision": pilot_qa_summary.get("pilot_decision"),
            "ready_for_dataset_execution": pilot_qa_summary.get("ready_for_dataset_execution"),
        },
        "limitations": _limitations(component_effects),
        "analysis_acceptance_criteria": {
            "failure_notes_consumed": context["qa_artifacts"]["failure_notes"]["exists"],
            "verification_artifacts_consumed": all(
                bool(outcome["evidence_paths"].get("verification")) for outcome in run_outcomes
            ),
            "metric_artifacts_consumed": all(
                bool(outcome["evidence_paths"].get("metrics")) for outcome in run_outcomes
            ),
            "trace_artifacts_consumed": all(
                bool(outcome["evidence_paths"].get("trace")) for outcome in run_outcomes
            ),
            "infrastructure_failures_not_counted_as_task_outcomes": True,
            "exclusion_and_rerun_decisions_linked_to_qa_artifacts": all(
                bool(link["linked_to_qa_artifact"]) for link in qa_decision_links
            ),
            "failure_analysis_markdown_written": True,
            "analysis_report_written": True,
            "limitations_and_claim_level_stated": True,
        },
    }


def build_run_failure_outcome(row: Mapping[str, Any]) -> Dict[str, object]:
    """Classify one run using metrics, verification, and trace artifacts."""

    run_id = _row_str(row, "run_id")
    artifact_paths = _artifact_paths(row)
    issues: List[str] = []
    verification = _load_verification(artifact_paths.get("verification"), run_id, issues)
    metrics = _load_metrics(artifact_paths.get("metrics"), run_id, issues)
    trace = _load_trace(artifact_paths.get("trace"), run_id, issues)

    failure_class = "passed"
    included_as_task_outcome = True
    if row.get("inclusion_status") != "included":
        failure_class = "dataset_excluded"
        included_as_task_outcome = False
    elif row.get("artifact_hash_validation_passed") is not True or issues:
        failure_class = "artifact_failure"
        included_as_task_outcome = False
    elif trace is None or trace.status != "completed":
        failure_class = "infrastructure_failure"
        included_as_task_outcome = False
    elif verification is not None and not verification.passed:
        failure_class = "verifier_failure"
    elif metrics is not None and not metrics.task_success:
        failure_class = "task_failure"

    return {
        "run_id": run_id,
        "component_config_id": _row_str(row, "component_config_id"),
        "task_id": _row_str(row, "task_id"),
        "seed": _row_int(row, "seed"),
        "perturbation_schedule_id": _row_str(row, "perturbation_schedule_id"),
        "failure_class": failure_class,
        "included_as_task_outcome": included_as_task_outcome,
        "dataset_decision": row.get("dataset_decision"),
        "inclusion_status": row.get("inclusion_status"),
        "trace_status": trace.status if trace is not None else None,
        "task_success": metrics.task_success if metrics is not None else row.get("task_success"),
        "verification_passed": verification.passed if verification is not None else row.get("verification_passed"),
        "verification_failure_reasons": verification.failure_reasons if verification is not None else [],
        "analysis_issues": issues + list(row.get("analysis_issues", [])),
        "evidence_paths": {
            name: str(path)
            for name, path in sorted(artifact_paths.items())
        },
    }


def build_failure_analysis_markdown(failure_analysis: Mapping[str, Any]) -> str:
    """Build the human-readable Phase 4D failure analysis report."""

    counts = failure_analysis["taxonomy_counts"]
    lines = [
        "# Phase 4D Failure Analysis",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Dataset ID | `{failure_analysis['dataset_id']}` |",
        f"| Experiment ID | `{failure_analysis['experiment_id']}` |",
        f"| Run count | {failure_analysis['run_count']} |",
        f"| Ordinary task outcomes | {failure_analysis['ordinary_task_outcome_count']} |",
        f"| Failure notes | {failure_analysis['failure_note_count']} |",
        f"| Rerun records | {failure_analysis['rerun_record_count']} |",
        "",
        "## Failure Taxonomy",
        "",
        "| Class | Count |",
        "|---|---|",
    ]
    for failure_class in FAILURE_CLASSES:
        lines.append(f"| `{failure_class}` | {counts[failure_class]} |")

    lines.extend(
        [
            "",
            "## QA Decisions",
            "",
        ]
    )
    if failure_analysis["qa_decision_links"]:
        lines.extend(["| Decision ID | Run ID | Type | Linked | Evidence |", "|---|---|---|---|---|"])
        for link in failure_analysis["qa_decision_links"]:
            lines.append(
                f"| `{link['decision_id']}` | `{link['run_id']}` | `{link['decision_type']}` | "
                f"`{str(link['linked_to_qa_artifact']).lower()}` | {', '.join(link['evidence_paths'])} |"
            )
    else:
        lines.append("No exclusion or rerun decisions were recorded for this dataset.")

    lines.extend(
        [
            "",
            "## Run-Level Evidence",
            "",
            "| Run ID | Component | Class | Included as task outcome | Verification | Task success | Trace |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for outcome in failure_analysis["run_outcomes"]:
        lines.append(
            f"| `{outcome['run_id']}` | `{outcome['component_config_id']}` | "
            f"`{outcome['failure_class']}` | `{str(outcome['included_as_task_outcome']).lower()}` | "
            f"`{_markdown_bool(outcome['verification_passed'])}` | "
            f"`{_markdown_bool(outcome['task_success'])}` | `{outcome['evidence_paths'].get('trace')}` |"
        )

    lines.extend(
        [
            "",
            "## Infrastructure Separation",
            "",
            failure_analysis["infrastructure_separation"]["policy"],
            "",
        ]
    )
    return "\n".join(lines)


def build_analysis_report_markdown(failure_analysis: Mapping[str, Any]) -> str:
    """Build the final Phase 4 dissertation-facing analysis report."""

    limitations = failure_analysis["limitations"]
    summary = failure_analysis["analysis_summary"]
    lines = [
        "# Phase 4 Analysis Report",
        "",
        "## Dataset",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Dataset ID | `{failure_analysis['dataset_id']}` |",
        f"| Experiment ID | `{failure_analysis['experiment_id']}` |",
        f"| Run count | {failure_analysis['run_count']} |",
        f"| Ordinary task outcomes | {failure_analysis['ordinary_task_outcome_count']} |",
        f"| Claim level | `{limitations['claim_level']}` |",
        f"| Descriptive only | `{str(limitations['descriptive_only']).lower()}` |",
        "",
        "## Method Summary",
        "",
        "The analysis consumes the frozen Phase 3 dataset through the Phase 4A metrics table and "
        "the stored trace, verification, metric, QA, and readiness artifacts. Phase 4B component "
        "contrasts and Phase 4C trajectory diagnostics are treated as derived artifacts over the "
        "same frozen dataset.",
        "",
        "## Results Summary",
        "",
        f"- Complete component-effect matched blocks: {summary['component_complete_block_count']}",
        f"- Incomplete component-effect matched blocks: {summary['component_incomplete_block_count']}",
        f"- Agent-behavior trajectory rows: {summary['trajectory_agent_behavior_row_count']}",
        f"- Pilot decision: `{summary['pilot_decision']}`",
        "",
        "## Failure Analysis",
        "",
        "Infrastructure and artifact failures are not counted as ordinary task outcomes unless "
        "explicitly justified. In this artifact set, the ordinary task outcome count is recorded "
        "separately from infrastructure or artifact issue counts.",
        "",
        "## Limitations",
        "",
        f"- {limitations['sample_size_note']}",
        f"- {limitations['claim_note']}",
        f"- Confidence intervals reported: `{str(limitations['confidence_intervals_reported']).lower()}`",
        "",
        "## Dissertation Text Fragment",
        "",
        "The current analysis should be described as a reproducible, artifact-backed descriptive "
        "analysis of the controlled component matrix. The results validate the analysis pipeline "
        "and provide traceable component and trajectory summaries, but broader inferential claims "
        "require additional tasks, seeds, or perturbation schedules.",
        "",
    ]
    return "\n".join(lines)


def _load_phase4d_context(metrics_table_path: Path, analysis_dir: Path) -> Dict[str, object]:
    analysis_config_path = analysis_dir / ANALYSIS_CONFIG_FILE
    analysis_config = _read_json_object(analysis_config_path, "analysis_config")
    dataset_index_path = Path(_config_str(analysis_config, "dataset_index_path"))
    experiment_dir = dataset_index_path.parent

    qa_paths = {
        "failure_notes": experiment_dir / FAILURE_NOTES_JSON_FILE,
        "rerun_records": experiment_dir / RERUN_RECORD_FILE,
        "pilot_qa_summary": experiment_dir / PILOT_QA_SUMMARY_FILE,
        "pilot_log": experiment_dir / PILOT_LOG_FILE,
    }
    analysis_paths = {
        "analysis_config": analysis_config_path,
        "metrics_table": metrics_table_path,
        "component_effects": analysis_dir / COMPONENT_EFFECTS_JSON_FILE,
        "interaction_summary": analysis_dir / INTERACTION_SUMMARY_JSON_FILE,
        "trajectory_diagnostics": analysis_dir / TRAJECTORY_DIAGNOSTICS_JSON_FILE,
    }
    failure_notes_payload = _read_json_object(qa_paths["failure_notes"], "failure_notes")
    rerun_records_payload = _read_json_object(qa_paths["rerun_records"], "rerun_records")
    return {
        "analysis_config": analysis_config,
        "failure_notes": _record_list(failure_notes_payload, "failure_notes"),
        "rerun_records": _record_list(rerun_records_payload, "rerun_records"),
        "pilot_qa_summary": _read_json_object(qa_paths["pilot_qa_summary"], "pilot_qa_summary"),
        "component_effects": _optional_json_object(analysis_paths["component_effects"], "component_effects"),
        "interaction_summary": _optional_json_object(analysis_paths["interaction_summary"], "interaction_summary"),
        "trajectory_diagnostics": _optional_json_object(
            analysis_paths["trajectory_diagnostics"],
            "trajectory_diagnostics",
        ),
        "qa_artifacts": _artifact_existence(qa_paths),
        "analysis_artifacts": _artifact_existence(analysis_paths),
    }


def _qa_decision_links(
    failure_notes: Sequence[Mapping[str, Any]],
    rerun_records: Sequence[Mapping[str, Any]],
    context: Mapping[str, Any],
) -> List[Dict[str, object]]:
    links: List[Dict[str, object]] = []
    failure_notes_artifact = context["qa_artifacts"]["failure_notes"]
    rerun_records_artifact = context["qa_artifacts"]["rerun_records"]
    for note in failure_notes:
        decision = str(note.get("dataset_decision"))
        if decision not in {"exclude", "rerun", "block_freeze"}:
            continue
        evidence_paths = _string_list(note.get("evidence_paths"))
        links.append(
            {
                "decision_id": f"failure_note:{note.get('run_id')}:{decision}",
                "run_id": note.get("run_id"),
                "decision_type": decision,
                "source_artifact": failure_notes_artifact["path"],
                "linked_to_qa_artifact": bool(failure_notes_artifact["exists"] and evidence_paths),
                "evidence_paths": evidence_paths,
            }
        )
    for record in rerun_records:
        links.append(
            {
                "decision_id": f"rerun_record:{record.get('rerun_id')}",
                "run_id": record.get("original_run_id"),
                "decision_type": record.get("decision"),
                "source_artifact": rerun_records_artifact["path"],
                "linked_to_qa_artifact": bool(rerun_records_artifact["exists"]),
                "evidence_paths": [str(rerun_records_artifact["path"])],
            }
        )
    return links


def _failure_notes_by_class(notes: Sequence[Mapping[str, Any]]) -> Dict[str, List[Dict[str, object]]]:
    grouped: Dict[str, List[Dict[str, object]]] = {failure_class: [] for failure_class in FAILURE_CLASSES}
    for note in notes:
        failure_class = str(note.get("failure_class"))
        grouped.setdefault(failure_class, []).append(dict(note))
    return grouped


def _limitations(component_effects: Mapping[str, Any]) -> Dict[str, object]:
    complete_blocks = component_effects.get("complete_block_count")
    descriptive_only = True
    return {
        "descriptive_only": descriptive_only,
        "confidence_intervals_reported": False,
        "claim_level": "descriptive",
        "sample_size_note": (
            f"The current component-effect analysis contains {complete_blocks} complete matched block(s)."
            if complete_blocks is not None
            else "Component-effect matched-block coverage was not available."
        ),
        "claim_note": (
            "The current dataset validates the analysis pipeline and supports descriptive interpretation. "
            "Inferential claims require additional tasks, seeds, or perturbation schedules."
        ),
    }


def _artifact_paths(row: Mapping[str, Any]) -> Dict[str, Path]:
    artifacts = row.get("artifact_paths")
    if not isinstance(artifacts, dict):
        return {}
    values: Dict[str, Path] = {}
    for name, path in artifacts.items():
        if isinstance(name, str) and isinstance(path, str) and path:
            values[name] = Path(path)
    return values


def _load_verification(path: Optional[Path], run_id: str, issues: List[str]) -> Optional[VerificationResult]:
    if path is None:
        issues.append(f"Missing verification artifact path for {run_id}")
        return None
    try:
        result = VerificationResult.from_dict(_read_json_object(path, "verification"))
    except ValidationError as exc:
        issues.append(str(exc))
        return None
    if result.run_id != run_id:
        issues.append(f"Verification run_id mismatch for {run_id}: {result.run_id}")
        return None
    return result


def _load_metrics(path: Optional[Path], run_id: str, issues: List[str]) -> Optional[MetricResult]:
    if path is None:
        issues.append(f"Missing metrics artifact path for {run_id}")
        return None
    try:
        result = MetricResult.from_dict(_read_json_object(path, "metrics"))
    except ValidationError as exc:
        issues.append(str(exc))
        return None
    if result.run_id != run_id:
        issues.append(f"Metrics run_id mismatch for {run_id}: {result.run_id}")
        return None
    return result


def _load_trace(path: Optional[Path], run_id: str, issues: List[str]) -> Optional[RunTrace]:
    if path is None:
        issues.append(f"Missing trace artifact path for {run_id}")
        return None
    try:
        result = RunTrace.from_dict(_read_json_object(path, "trace"))
    except ValidationError as exc:
        issues.append(str(exc))
        return None
    if result.run_id != run_id:
        issues.append(f"Trace run_id mismatch for {run_id}: {result.run_id}")
        return None
    return result


def _artifact_existence(paths: Mapping[str, Path]) -> Dict[str, Dict[str, object]]:
    return {
        name: {
            "path": str(path),
            "exists": path.exists(),
        }
        for name, path in sorted(paths.items())
    }


def _optional_json_object(path: Path, artifact_name: str) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    return _read_json_object(path, artifact_name)


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


def _validate_metrics_table(metrics_table: Mapping[str, Any]) -> None:
    if metrics_table.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError("metrics_table.schema_version is invalid")
    _table_str(metrics_table, "dataset_id")
    _table_str(metrics_table, "experiment_id")
    row_count = _table_int(metrics_table, "row_count")
    rows = _metric_rows(metrics_table)
    if row_count != len(rows):
        raise ValidationError("metrics_table.row_count does not match rows length")


def _metric_rows(metrics_table: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = metrics_table.get("rows")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValidationError("metrics_table.rows must be a list of objects")
    return list(rows)


def _record_list(payload: Mapping[str, Any], artifact_name: str) -> List[Dict[str, Any]]:
    records = payload.get("records")
    if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
        raise ValidationError(f"{artifact_name}.records must be a list of objects")
    return list(records)


def _string_list(value: object) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item]


def _markdown_bool(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _table_str(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ValidationError(f"metrics_table.{field} must be a non-empty string")
    return value


def _table_int(payload: Mapping[str, Any], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"metrics_table.{field} must be an integer")
    return value


def _config_str(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ValidationError(f"analysis_config.{field} must be a non-empty string")
    return value


def _row_str(row: Mapping[str, Any], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ValidationError(f"metrics row {field} must be a non-empty string")
    return value


def _row_int(row: Mapping[str, Any], field: str) -> int:
    value = row.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"metrics row {field} must be an integer")
    return value
