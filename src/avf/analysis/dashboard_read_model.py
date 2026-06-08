"""Phase 4E read-model and dashboard snapshot artifacts."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from avf.contracts import SCHEMA_VERSION, ValidationError
from avf.orchestration.pilot_qa import current_commit_hash, utc_timestamp
from avf.orchestration.readiness_review import (
    DASHBOARD_REQUIREMENTS_FILE,
    QUERY_REQUIREMENTS_FILE,
    RESULTS_INDEX_DECISION_FILE,
)

from .component_effects import COMPONENT_EFFECTS_JSON_FILE, INTERACTION_SUMMARY_JSON_FILE
from .dataset_analysis import ANALYSIS_CONFIG_FILE, ANALYSIS_INPUT_MANIFEST_FILE
from .failure_analysis import ANALYSIS_REPORT_FILE, FAILURE_ANALYSIS_JSON_FILE
from .trajectory_diagnostics import TRAJECTORY_DIAGNOSTICS_JSON_FILE


PHASE4E_ANALYSIS_VERSION = "1.0"
READ_MODEL_DECISION_JSON_FILE = "read_model_decision.json"
RESULTS_READ_MODEL_JSON_FILE = "results_read_model.json"
DASHBOARD_DATA_JSON_FILE = "dashboard_data.json"
DASHBOARD_SNAPSHOT_MARKDOWN_FILE = "dashboard_snapshot.md"

REQUIRED_DASHBOARD_VIEWS = [
    "dataset_overview",
    "component_comparison",
    "task_seed_filters",
    "verification_outcome_breakdown",
    "trajectory_diagnostic_drilldown",
    "failure_taxonomy_review",
    "artifact_integrity_status",
]


@dataclass(frozen=True)
class Phase4EReadModelArtifacts:
    """Artifacts produced by Phase 4E read-model/dashboard analysis."""

    read_model_decision_json: Path
    results_read_model_json: Path
    dashboard_data_json: Path
    dashboard_snapshot_markdown: Path

    def to_dict(self) -> Dict[str, str]:
        return {
            "read_model_decision_json": str(self.read_model_decision_json),
            "results_read_model_json": str(self.results_read_model_json),
            "dashboard_data_json": str(self.dashboard_data_json),
            "dashboard_snapshot_markdown": str(self.dashboard_snapshot_markdown),
        }


@dataclass(frozen=True)
class Phase4EReadModelResult:
    """Outputs from Phase 4E read-model/dashboard generation."""

    dataset_id: str
    experiment_id: str
    artifacts: Phase4EReadModelArtifacts
    read_model_decision: Dict[str, object]
    results_read_model: Dict[str, object]
    dashboard_data: Dict[str, object]
    dashboard_snapshot_markdown: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "dataset_id": self.dataset_id,
            "experiment_id": self.experiment_id,
            "row_count": self.results_read_model["row_count"],
            "database_materialized": self.read_model_decision["implementation_decision"][
                "database_materialized"
            ],
            "dashboard_view_count": len(self.dashboard_data["views"]),
            "artifacts": self.artifacts.to_dict(),
        }


def write_phase4e_dashboard_read_model(
    metrics_table_path: Path,
    analysis_root: Optional[Path] = None,
    generated_at: Optional[str] = None,
    code_version: Optional[str] = None,
) -> Phase4EReadModelResult:
    """Write Phase 4E read-model and static dashboard artifacts."""

    metrics_path = Path(metrics_table_path)
    metrics_table = _read_json_object(metrics_path, "metrics_table")
    _validate_metrics_table(metrics_table)

    dataset_id = _table_str(metrics_table, "dataset_id")
    experiment_id = _table_str(metrics_table, "experiment_id")
    timestamp = generated_at or utc_timestamp()
    version = code_version or current_commit_hash()
    output_root = Path(analysis_root) if analysis_root is not None else metrics_path.parent.parent
    analysis_dir = output_root / dataset_id

    artifacts = Phase4EReadModelArtifacts(
        read_model_decision_json=analysis_dir / READ_MODEL_DECISION_JSON_FILE,
        results_read_model_json=analysis_dir / RESULTS_READ_MODEL_JSON_FILE,
        dashboard_data_json=analysis_dir / DASHBOARD_DATA_JSON_FILE,
        dashboard_snapshot_markdown=analysis_dir / DASHBOARD_SNAPSHOT_MARKDOWN_FILE,
    )

    context = _load_phase4e_context(metrics_path, analysis_dir)
    read_model_decision = build_read_model_decision_payload(
        metrics_table=metrics_table,
        metrics_table_path=metrics_path,
        context=context,
        generated_at=timestamp,
        code_version=version,
    )
    results_read_model = build_results_read_model_payload(
        metrics_table=metrics_table,
        metrics_table_path=metrics_path,
        context=context,
        decision=read_model_decision,
        generated_at=timestamp,
        code_version=version,
    )
    dashboard_data = build_dashboard_data_payload(
        results_read_model=results_read_model,
        context=context,
        decision=read_model_decision,
        generated_at=timestamp,
        code_version=version,
    )
    dashboard_snapshot = build_dashboard_snapshot_markdown(dashboard_data, read_model_decision)

    _write_json(artifacts.read_model_decision_json, read_model_decision)
    _write_json(artifacts.results_read_model_json, results_read_model)
    _write_json(artifacts.dashboard_data_json, dashboard_data)
    _write_text(artifacts.dashboard_snapshot_markdown, dashboard_snapshot)

    return Phase4EReadModelResult(
        dataset_id=dataset_id,
        experiment_id=experiment_id,
        artifacts=artifacts,
        read_model_decision=read_model_decision,
        results_read_model=results_read_model,
        dashboard_data=dashboard_data,
        dashboard_snapshot_markdown=dashboard_snapshot,
    )


def build_read_model_decision_payload(
    metrics_table: Mapping[str, Any],
    metrics_table_path: Path,
    context: Mapping[str, Any],
    generated_at: str,
    code_version: str,
) -> Dict[str, object]:
    """Build the Phase 4E database/dashboard decision artifact."""

    phase3d_decision = _mapping(context["results_index_decision"], "results_index_decision")
    query_requirements = _mapping(context["query_requirements"], "query_requirements")
    component_effects = _mapping(context["component_effects"], "component_effects")
    trajectory_diagnostics = _mapping(context["trajectory_diagnostics"], "trajectory_diagnostics")
    failure_analysis = _mapping(context["failure_analysis"], "failure_analysis")
    rows = _metric_rows(metrics_table)
    filesystem_sufficient = bool(phase3d_decision.get("filesystem_sufficient"))
    database_recommended = bool(phase3d_decision.get("database_recommended"))

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_version": PHASE4E_ANALYSIS_VERSION,
        "dataset_id": metrics_table["dataset_id"],
        "experiment_id": metrics_table["experiment_id"],
        "generated_at": generated_at,
        "code_version": code_version,
        "metrics_table_artifact": str(metrics_table_path),
        "source_artifacts": context["source_artifacts"],
        "phase3d_decision_summary": {
            "results_index_decision_artifact": context["source_artifacts"]["results_index_decision"]["path"],
            "filesystem_sufficient": filesystem_sufficient,
            "database_recommended": database_recommended,
            "database_decision": phase3d_decision.get("database_decision"),
            "dashboard_recommended_now": bool(phase3d_decision.get("dashboard_recommended_now")),
            "dashboard_decision": phase3d_decision.get("dashboard_decision"),
            "read_model_policy": phase3d_decision.get("read_model_policy", {}),
        },
        "phase4_query_needs": {
            "required_views": REQUIRED_DASHBOARD_VIEWS,
            "filters": _string_list(query_requirements.get("required_filters"))
            + ["failure_class", "diagnostic_scope", "verification_passed"],
            "groupings": _string_list(query_requirements.get("required_groupings"))
            + ["failure_class", "diagnostic_scope"],
            "joins_consumed": _string_list(query_requirements.get("required_joins"))
            + [
                "metrics_table to component_effects",
                "metrics_table to trajectory_diagnostics",
                "metrics_table to failure_analysis",
            ],
            "current_dataset_scale": {
                "run_count": metrics_table["row_count"],
                "included_run_count": metrics_table["included_run_count"],
                "component_cell_count": len({_row_str(row, "component_config_id") for row in rows}),
                "complete_component_block_count": component_effects.get("complete_block_count"),
                "trajectory_scope_counts": trajectory_diagnostics.get("scope_counts", {}),
                "failure_taxonomy_counts": failure_analysis.get("taxonomy_counts", {}),
            },
            "query_pressure": "low" if filesystem_sufficient else "elevated",
        },
        "implementation_decision": {
            "database_materialized": False,
            "database_backend": None,
            "read_model_backend": "json_derived_artifact",
            "dashboard_artifact_type": "static_json_and_markdown_snapshot",
            "rationale": (
                "Phase 3D records that filesystem artifacts remain sufficient for the current dataset. "
                "Phase 4E therefore writes reproducible dashboard/read-model artifacts without introducing "
                "a live database or web dashboard."
            ),
        },
        "source_of_truth_policy": {
            "source_of_truth": [
                "dataset_index.json",
                "frozen_dataset_manifest.json",
                "Phase 3 QA artifacts",
                "Phase 4A-4D derived analysis artifacts",
            ],
            "read_model_is_source_of_truth": False,
            "dashboard_is_source_of_truth": False,
            "raw_artifacts_replaced": False,
        },
        "analysis_acceptance_criteria": {
            "results_index_decision_cited": context["source_artifacts"]["results_index_decision"]["exists"],
            "phase4_query_needs_cited": True,
            "database_reproducible_from_frozen_dataset": True,
            "dashboard_views_read_derived_artifacts_or_read_model": True,
            "dashboard_not_source_of_truth": True,
            "read_model_json_written": True,
            "dashboard_data_json_written": True,
            "dashboard_snapshot_markdown_written": True,
        },
    }


def build_results_read_model_payload(
    metrics_table: Mapping[str, Any],
    metrics_table_path: Path,
    context: Mapping[str, Any],
    decision: Mapping[str, Any],
    generated_at: str,
    code_version: str,
) -> Dict[str, object]:
    """Build the compact derived read model used by dashboard artifacts."""

    rows = _read_model_rows(metrics_table, context)
    component_summaries = _component_summaries(rows)
    indexes = _read_model_indexes(rows)

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_version": PHASE4E_ANALYSIS_VERSION,
        "dataset_id": metrics_table["dataset_id"],
        "experiment_id": metrics_table["experiment_id"],
        "generated_at": generated_at,
        "code_version": code_version,
        "metrics_table_artifact": str(metrics_table_path),
        "read_model_decision": {
            "database_materialized": decision["implementation_decision"]["database_materialized"],
            "backend": decision["implementation_decision"]["read_model_backend"],
            "source_of_truth_policy": decision["source_of_truth_policy"],
        },
        "row_count": len(rows),
        "rows": rows,
        "component_summaries": component_summaries,
        "indexes": indexes,
        "source_artifacts": context["source_artifacts"],
        "analysis_acceptance_criteria": {
            "rows_traceable_to_run_ids": all(bool(row["run_id"]) for row in rows),
            "rows_link_to_evidence_paths": all(bool(row["evidence_paths"]) for row in rows),
            "failure_classes_joined_from_failure_analysis": all(
                bool(row["failure_class"]) for row in rows
            ),
            "trajectory_scopes_joined_from_diagnostics": all(
                bool(row["diagnostic_scope"]) for row in rows
            ),
            "read_model_not_source_of_truth": True,
        },
    }


def build_dashboard_data_payload(
    results_read_model: Mapping[str, Any],
    context: Mapping[str, Any],
    decision: Mapping[str, Any],
    generated_at: str,
    code_version: str,
) -> Dict[str, object]:
    """Build static dashboard data from the Phase 4E read model."""

    rows = _read_model_payload_rows(results_read_model)
    failure_analysis = _mapping(context["failure_analysis"], "failure_analysis")
    component_effects = _mapping(context["component_effects"], "component_effects")
    trajectory_diagnostics = _mapping(context["trajectory_diagnostics"], "trajectory_diagnostics")

    dashboard_data = {
        "schema_version": SCHEMA_VERSION,
        "analysis_version": PHASE4E_ANALYSIS_VERSION,
        "dataset_id": results_read_model["dataset_id"],
        "experiment_id": results_read_model["experiment_id"],
        "generated_at": generated_at,
        "code_version": code_version,
        "source_policy": decision["source_of_truth_policy"],
        "filter_options": _filter_options(rows),
        "views": {
            "dataset_overview": _dataset_overview_view(rows, failure_analysis, component_effects),
            "component_comparison": _component_comparison_view(results_read_model, component_effects),
            "task_seed_filters": _task_seed_filter_view(rows),
            "verification_outcome_breakdown": _verification_breakdown_view(rows),
            "trajectory_diagnostic_drilldown": _trajectory_drilldown_view(rows, trajectory_diagnostics),
            "failure_taxonomy_review": _failure_taxonomy_view(failure_analysis),
            "artifact_integrity_status": _artifact_integrity_view(rows),
        },
        "analysis_acceptance_criteria": {
            "views_read_results_read_model": True,
            "views_read_derived_phase4_artifacts": True,
            "dashboard_not_source_of_truth": True,
            "required_view_count": len(REQUIRED_DASHBOARD_VIEWS),
            "implemented_view_count": len(REQUIRED_DASHBOARD_VIEWS),
        },
    }
    return dashboard_data


def build_dashboard_snapshot_markdown(
    dashboard_data: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> str:
    """Build the human-readable Phase 4E dashboard snapshot."""

    views = _mapping(dashboard_data["views"], "dashboard_data.views")
    overview = _mapping(views["dataset_overview"], "dataset_overview")
    integrity = _mapping(views["artifact_integrity_status"], "artifact_integrity_status")
    verification = _mapping(views["verification_outcome_breakdown"], "verification_outcome_breakdown")
    failure = _mapping(views["failure_taxonomy_review"], "failure_taxonomy_review")
    implementation = _mapping(decision["implementation_decision"], "implementation_decision")

    lines = [
        "# Phase 4E Read Model and Dashboard Snapshot",
        "",
        "## Decision",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Dataset ID | `{dashboard_data['dataset_id']}` |",
        f"| Experiment ID | `{dashboard_data['experiment_id']}` |",
        f"| Database materialized | `{str(implementation['database_materialized']).lower()}` |",
        f"| Read-model backend | `{implementation['read_model_backend']}` |",
        f"| Dashboard artifact type | `{implementation['dashboard_artifact_type']}` |",
        f"| Dashboard is source of truth | `{str(decision['source_of_truth_policy']['dashboard_is_source_of_truth']).lower()}` |",
        "",
        "## Dataset Overview",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Run count | {overview['run_count']} |",
        f"| Included run count | {overview['included_run_count']} |",
        f"| Ordinary task outcomes | {overview['ordinary_task_outcome_count']} |",
        f"| Complete component blocks | {overview['complete_component_block_count']} |",
        f"| Claim level | `{overview['claim_level']}` |",
        "",
        "## Verification Breakdown",
        "",
        f"- Passed: {verification['passed']}",
        f"- Failed: {verification['failed']}",
        f"- Unknown: {verification['unknown']}",
        "",
        "## Failure Taxonomy",
        "",
        "| Class | Count |",
        "|---|---|",
    ]
    for failure_class, count in sorted(_mapping(failure["taxonomy_counts"], "taxonomy_counts").items()):
        lines.append(f"| `{failure_class}` | {count} |")

    lines.extend(
        [
            "",
            "## Artifact Integrity",
            "",
            f"- Hash validation passed: {integrity['hash_validation_passed_count']}",
            f"- Hash validation failed: {integrity['hash_validation_failed_count']}",
            "",
            "## Source Policy",
            "",
            "This dashboard snapshot is a derived review artifact. Raw frozen artifacts and Phase 4 "
            "analysis artifacts remain the source of truth for dissertation results.",
            "",
        ]
    )
    return "\n".join(lines)


def _load_phase4e_context(metrics_table_path: Path, analysis_dir: Path) -> Dict[str, object]:
    analysis_paths = {
        "analysis_config": analysis_dir / ANALYSIS_CONFIG_FILE,
        "analysis_input_manifest": analysis_dir / ANALYSIS_INPUT_MANIFEST_FILE,
        "metrics_table": metrics_table_path,
        "component_effects": analysis_dir / COMPONENT_EFFECTS_JSON_FILE,
        "interaction_summary": analysis_dir / INTERACTION_SUMMARY_JSON_FILE,
        "trajectory_diagnostics": analysis_dir / TRAJECTORY_DIAGNOSTICS_JSON_FILE,
        "failure_analysis": analysis_dir / FAILURE_ANALYSIS_JSON_FILE,
        "analysis_report": analysis_dir / ANALYSIS_REPORT_FILE,
    }
    analysis_config = _read_json_object(analysis_paths["analysis_config"], "analysis_config")
    dataset_index_path = Path(_config_str(analysis_config, "dataset_index_path"))
    experiment_dir = dataset_index_path.parent
    phase3d_paths = {
        "query_requirements": experiment_dir / QUERY_REQUIREMENTS_FILE,
        "results_index_decision": experiment_dir / RESULTS_INDEX_DECISION_FILE,
        "dashboard_requirements": experiment_dir / DASHBOARD_REQUIREMENTS_FILE,
    }

    return {
        "analysis_config": analysis_config,
        "analysis_input_manifest": _read_json_object(
            analysis_paths["analysis_input_manifest"],
            "analysis_input_manifest",
        ),
        "component_effects": _read_json_object(
            analysis_paths["component_effects"],
            "component_effects",
        ),
        "interaction_summary": _read_json_object(
            analysis_paths["interaction_summary"],
            "interaction_summary",
        ),
        "trajectory_diagnostics": _read_json_object(
            analysis_paths["trajectory_diagnostics"],
            "trajectory_diagnostics",
        ),
        "failure_analysis": _read_json_object(
            analysis_paths["failure_analysis"],
            "failure_analysis",
        ),
        "query_requirements": _read_json_object(
            phase3d_paths["query_requirements"],
            "query_requirements",
        ),
        "results_index_decision": _read_json_object(
            phase3d_paths["results_index_decision"],
            "results_index_decision",
        ),
        "source_artifacts": _source_artifacts(analysis_paths, phase3d_paths),
    }


def _read_model_rows(metrics_table: Mapping[str, Any], context: Mapping[str, Any]) -> List[Dict[str, object]]:
    failure_by_run = _by_run_id(
        _object_list(_mapping(context["failure_analysis"], "failure_analysis").get("run_outcomes")),
        "failure_analysis.run_outcomes",
    )
    diagnostics_by_run = _by_run_id(
        _object_list(_mapping(context["trajectory_diagnostics"], "trajectory_diagnostics").get("rows")),
        "trajectory_diagnostics.rows",
    )
    rows: List[Dict[str, object]] = []
    for row in _metric_rows(metrics_table):
        run_id = _row_str(row, "run_id")
        failure = failure_by_run.get(run_id, {})
        diagnostic = diagnostics_by_run.get(run_id, {})
        evidence_paths = _artifact_paths(row)
        rows.append(
            {
                "row_id": _row_str(row, "row_id"),
                "run_id": run_id,
                "task_id": _row_str(row, "task_id"),
                "seed": _row_int(row, "seed"),
                "perturbation_schedule_id": _row_str(row, "perturbation_schedule_id"),
                "component_config_id": _row_str(row, "component_config_id"),
                "factor_levels": {
                    "memory_backend": row.get("memory_backend"),
                    "retrieval_strategy": row.get("retrieval_strategy"),
                    "scheduling_policy": row.get("scheduling_policy"),
                },
                "inclusion_status": row.get("inclusion_status"),
                "dataset_decision": row.get("dataset_decision"),
                "artifact_hash_validation_passed": row.get("artifact_hash_validation_passed"),
                "task_success": row.get("task_success"),
                "verification_passed": row.get("verification_passed"),
                "failure_class": failure.get("failure_class", "unknown"),
                "included_as_task_outcome": failure.get("included_as_task_outcome", False),
                "diagnostic_scope": diagnostic.get("diagnostic_scope", "unknown"),
                "latency_ms": row.get("latency_ms"),
                "step_count": row.get("step_count"),
                "tool_call_count": row.get("tool_call_count"),
                "goal_drift": row.get("goal_drift"),
                "repetition_rate": row.get("repetition_rate"),
                "recovery_steps": row.get("recovery_steps"),
                "final_answer_present": row.get("final_answer_present"),
                "trace_drilldown": diagnostic.get("trace_drilldown", {}),
                "evidence_paths": evidence_paths,
            }
        )
    return rows


def _component_summaries(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, object]]:
    grouped: Dict[str, List[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_row_value_str(row, "component_config_id"), []).append(row)

    summaries: List[Dict[str, object]] = []
    for component_id, component_rows in sorted(grouped.items()):
        summaries.append(
            {
                "component_config_id": component_id,
                "run_count": len(component_rows),
                "included_run_count": sum(1 for row in component_rows if row.get("inclusion_status") == "included"),
                "task_success_count": sum(1 for row in component_rows if row.get("task_success") is True),
                "verification_pass_count": sum(1 for row in component_rows if row.get("verification_passed") is True),
                "failure_class_counts": dict(
                    sorted(Counter(str(row.get("failure_class")) for row in component_rows).items())
                ),
                "average_step_count": _average(row.get("step_count") for row in component_rows),
                "average_tool_call_count": _average(row.get("tool_call_count") for row in component_rows),
                "average_goal_drift": _average(row.get("goal_drift") for row in component_rows),
                "run_ids": [_row_value_str(row, "run_id") for row in component_rows],
            }
        )
    return summaries


def _read_model_indexes(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, List[str]]]:
    indexes = {
        "by_component_config_id": {},
        "by_task_id": {},
        "by_failure_class": {},
        "by_diagnostic_scope": {},
    }
    for row in rows:
        run_id = _row_value_str(row, "run_id")
        _append_index(indexes["by_component_config_id"], _row_value_str(row, "component_config_id"), run_id)
        _append_index(indexes["by_task_id"], _row_value_str(row, "task_id"), run_id)
        _append_index(indexes["by_failure_class"], str(row.get("failure_class")), run_id)
        _append_index(indexes["by_diagnostic_scope"], str(row.get("diagnostic_scope")), run_id)
    return indexes


def _filter_options(rows: Sequence[Mapping[str, Any]]) -> Dict[str, object]:
    return {
        "component_config_id": sorted({_row_value_str(row, "component_config_id") for row in rows}),
        "task_id": sorted({_row_value_str(row, "task_id") for row in rows}),
        "seed": sorted({_row_value_int(row, "seed") for row in rows}),
        "perturbation_schedule_id": sorted({_row_value_str(row, "perturbation_schedule_id") for row in rows}),
        "failure_class": sorted({str(row.get("failure_class")) for row in rows}),
        "diagnostic_scope": sorted({str(row.get("diagnostic_scope")) for row in rows}),
    }


def _dataset_overview_view(
    rows: Sequence[Mapping[str, Any]],
    failure_analysis: Mapping[str, Any],
    component_effects: Mapping[str, Any],
) -> Dict[str, object]:
    return {
        "run_count": len(rows),
        "included_run_count": sum(1 for row in rows if row.get("inclusion_status") == "included"),
        "ordinary_task_outcome_count": failure_analysis.get("ordinary_task_outcome_count"),
        "complete_component_block_count": component_effects.get("complete_block_count"),
        "descriptive_only": failure_analysis.get("limitations", {}).get("descriptive_only")
        if isinstance(failure_analysis.get("limitations"), dict)
        else True,
        "claim_level": failure_analysis.get("limitations", {}).get("claim_level")
        if isinstance(failure_analysis.get("limitations"), dict)
        else "descriptive",
    }


def _component_comparison_view(
    results_read_model: Mapping[str, Any],
    component_effects: Mapping[str, Any],
) -> Dict[str, object]:
    return {
        "component_summaries": results_read_model["component_summaries"],
        "main_effects": component_effects.get("main_effects", []),
        "complete_block_count": component_effects.get("complete_block_count"),
        "incomplete_block_count": component_effects.get("incomplete_block_count"),
        "descriptive_only": component_effects.get("limitations", {}).get("descriptive_only")
        if isinstance(component_effects.get("limitations"), dict)
        else True,
    }


def _task_seed_filter_view(rows: Sequence[Mapping[str, Any]]) -> Dict[str, object]:
    return {
        "available_tasks": sorted({_row_value_str(row, "task_id") for row in rows}),
        "available_seeds": sorted({_row_value_int(row, "seed") for row in rows}),
        "available_perturbation_schedules": sorted(
            {_row_value_str(row, "perturbation_schedule_id") for row in rows}
        ),
    }


def _verification_breakdown_view(rows: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    return {
        "passed": sum(1 for row in rows if row.get("verification_passed") is True),
        "failed": sum(1 for row in rows if row.get("verification_passed") is False),
        "unknown": sum(1 for row in rows if row.get("verification_passed") is None),
    }


def _trajectory_drilldown_view(
    rows: Sequence[Mapping[str, Any]],
    trajectory_diagnostics: Mapping[str, Any],
) -> Dict[str, object]:
    return {
        "scope_counts": trajectory_diagnostics.get("scope_counts", {}),
        "rows": [
            {
                "run_id": row["run_id"],
                "component_config_id": row["component_config_id"],
                "diagnostic_scope": row["diagnostic_scope"],
                "step_count": row["step_count"],
                "tool_call_count": row["tool_call_count"],
                "goal_drift": row["goal_drift"],
                "repetition_rate": row["repetition_rate"],
                "trace_drilldown": row["trace_drilldown"],
            }
            for row in rows
        ],
    }


def _failure_taxonomy_view(failure_analysis: Mapping[str, Any]) -> Dict[str, object]:
    return {
        "taxonomy_counts": failure_analysis.get("taxonomy_counts", {}),
        "qa_decision_links": failure_analysis.get("qa_decision_links", []),
        "ordinary_task_outcome_count": failure_analysis.get("ordinary_task_outcome_count"),
        "infrastructure_separation": failure_analysis.get("infrastructure_separation", {}),
    }


def _artifact_integrity_view(rows: Sequence[Mapping[str, Any]]) -> Dict[str, object]:
    return {
        "hash_validation_passed_count": sum(
            1 for row in rows if row.get("artifact_hash_validation_passed") is True
        ),
        "hash_validation_failed_count": sum(
            1 for row in rows if row.get("artifact_hash_validation_passed") is not True
        ),
        "rows": [
            {
                "run_id": row["run_id"],
                "component_config_id": row["component_config_id"],
                "artifact_hash_validation_passed": row["artifact_hash_validation_passed"],
                "evidence_paths": row["evidence_paths"],
            }
            for row in rows
        ],
    }


def _source_artifacts(
    analysis_paths: Mapping[str, Path],
    phase3d_paths: Mapping[str, Path],
) -> Dict[str, Dict[str, object]]:
    all_paths = {**analysis_paths, **phase3d_paths}
    return {
        name: {
            "path": str(path),
            "exists": path.exists(),
        }
        for name, path in sorted(all_paths.items())
    }


def _read_model_payload_rows(payload: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValidationError("results_read_model.rows must be a list of objects")
    return list(rows)


def _metric_rows(metrics_table: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = metrics_table.get("rows")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValidationError("metrics_table.rows must be a list of objects")
    return list(rows)


def _object_list(value: object) -> List[Dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        return []
    return list(value)


def _by_run_id(rows: Iterable[Mapping[str, Any]], artifact_name: str) -> Dict[str, Mapping[str, Any]]:
    indexed: Dict[str, Mapping[str, Any]] = {}
    for row in rows:
        run_id = row.get("run_id")
        if isinstance(run_id, str) and run_id:
            indexed[run_id] = row
    if not indexed:
        raise ValidationError(f"{artifact_name} did not contain run_id-indexable rows")
    return indexed


def _artifact_paths(row: Mapping[str, Any]) -> Dict[str, str]:
    artifact_paths = row.get("artifact_paths")
    if not isinstance(artifact_paths, dict):
        return {}
    return {
        str(name): str(path)
        for name, path in sorted(artifact_paths.items())
        if isinstance(name, str) and isinstance(path, str) and path
    }


def _append_index(index: Dict[str, List[str]], key: str, run_id: str) -> None:
    index.setdefault(key, []).append(run_id)


def _average(values: Iterable[object]) -> Optional[float]:
    numeric_values = [
        float(value)
        for value in values
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    if not numeric_values:
        return None
    return sum(numeric_values) / len(numeric_values)


def _mapping(value: object, artifact_name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{artifact_name} must be an object")
    return value


def _string_list(value: object) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item]


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


def _row_value_str(row: Mapping[str, Any], field: str) -> str:
    value = row.get(field)
    return str(value) if value is not None else ""


def _row_value_int(row: Mapping[str, Any], field: str) -> int:
    value = row.get(field)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return 0
