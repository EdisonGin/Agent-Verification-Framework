"""Phase 3D results-index and dashboard readiness review."""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from avf.contracts import SCHEMA_VERSION, ValidationError
from avf.storage import FileSystemResultsStore

from .dataset_freeze import DATASET_INDEX_FILE, FROZEN_DATASET_MANIFEST_FILE
from .experiment_matrix import ExperimentConfig, load_experiment_config


READINESS_REVIEW_VERSION = "1.0"
STORAGE_VOLUME_REVIEW_FILE = "storage_volume_review.json"
QUERY_REQUIREMENTS_FILE = "query_requirements.json"
DASHBOARD_REQUIREMENTS_FILE = "dashboard_requirements.md"
RESULTS_INDEX_DECISION_FILE = "results_index_decision.json"
PHASE3D_REVIEW_REPORT_FILE = "phase3d_review.md"

DEFAULT_DATABASE_RUN_THRESHOLD = 100
DEFAULT_DATABASE_BYTES_THRESHOLD = 50_000_000


@dataclass(frozen=True)
class Phase3DReadinessReviewArtifacts:
    """Artifacts produced by the Phase 3D readiness review."""

    storage_volume_review: Path
    query_requirements: Path
    dashboard_requirements: Path
    results_index_decision: Path
    review_report: Path

    def to_dict(self) -> Dict[str, str]:
        return {
            "storage_volume_review": str(self.storage_volume_review),
            "query_requirements": str(self.query_requirements),
            "dashboard_requirements": str(self.dashboard_requirements),
            "results_index_decision": str(self.results_index_decision),
            "review_report": str(self.review_report),
        }


@dataclass(frozen=True)
class Phase3DReadinessReviewResult:
    """Outputs from a Phase 3D results-index/dashboard readiness review."""

    experiment_id: str
    dataset_id: str
    artifacts: Phase3DReadinessReviewArtifacts
    storage_volume_review: Dict[str, object]
    query_requirements: Dict[str, object]
    results_index_decision: Dict[str, object]
    dashboard_requirements_markdown: str
    review_report: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "experiment_id": self.experiment_id,
            "dataset_id": self.dataset_id,
            "filesystem_sufficient": self.results_index_decision["filesystem_sufficient"],
            "database_recommended": self.results_index_decision["database_recommended"],
            "dashboard_recommended_now": self.results_index_decision["dashboard_recommended_now"],
            "artifacts": self.artifacts.to_dict(),
        }


def run_phase3d_readiness_review(
    config: ExperimentConfig,
    operator_notes: str = "Phase 3D results-index and dashboard readiness review.",
    database_run_threshold: int = DEFAULT_DATABASE_RUN_THRESHOLD,
    database_bytes_threshold: int = DEFAULT_DATABASE_BYTES_THRESHOLD,
) -> Phase3DReadinessReviewResult:
    """Review frozen dataset artifacts and decide whether DB/dashboard work is justified."""

    store = _results_store(config)
    experiment_dir = store.layout.artifact_root / "experiments" / config.experiment_id
    dataset_index_path = experiment_dir / DATASET_INDEX_FILE
    frozen_manifest_path = experiment_dir / FROZEN_DATASET_MANIFEST_FILE
    dataset_index = _read_json(dataset_index_path)
    frozen_manifest = _read_json(frozen_manifest_path)
    _validate_frozen_inputs(dataset_index, frozen_manifest)

    artifacts = Phase3DReadinessReviewArtifacts(
        storage_volume_review=experiment_dir / STORAGE_VOLUME_REVIEW_FILE,
        query_requirements=experiment_dir / QUERY_REQUIREMENTS_FILE,
        dashboard_requirements=experiment_dir / DASHBOARD_REQUIREMENTS_FILE,
        results_index_decision=experiment_dir / RESULTS_INDEX_DECISION_FILE,
        review_report=experiment_dir / PHASE3D_REVIEW_REPORT_FILE,
    )

    storage_review = build_storage_volume_review(
        dataset_index=dataset_index,
        frozen_manifest=frozen_manifest,
        dataset_index_path=dataset_index_path,
        frozen_manifest_path=frozen_manifest_path,
        store=store,
    )
    query_requirements = build_query_requirements(dataset_index)
    decision = build_results_index_decision(
        dataset_index=dataset_index,
        storage_volume_review=storage_review,
        query_requirements=query_requirements,
        operator_notes=operator_notes,
        database_run_threshold=database_run_threshold,
        database_bytes_threshold=database_bytes_threshold,
    )
    dashboard_markdown = build_dashboard_requirements_markdown(dataset_index, decision)
    review_report = build_phase3d_review_report(storage_review, query_requirements, decision)

    _write_json(artifacts.storage_volume_review, storage_review)
    _write_json(artifacts.query_requirements, query_requirements)
    _write_json(artifacts.results_index_decision, decision)
    _write_text(artifacts.dashboard_requirements, dashboard_markdown)
    _write_text(artifacts.review_report, review_report)

    return Phase3DReadinessReviewResult(
        experiment_id=str(dataset_index["experiment_id"]),
        dataset_id=str(dataset_index["dataset_id"]),
        artifacts=artifacts,
        storage_volume_review=storage_review,
        query_requirements=query_requirements,
        results_index_decision=decision,
        dashboard_requirements_markdown=dashboard_markdown,
        review_report=review_report,
    )


def run_phase3d_readiness_review_from_config(
    experiment_config_path: Path,
    artifact_root: Optional[Path] = None,
    operator_notes: str = "Phase 3D results-index and dashboard readiness review.",
    database_run_threshold: int = DEFAULT_DATABASE_RUN_THRESHOLD,
    database_bytes_threshold: int = DEFAULT_DATABASE_BYTES_THRESHOLD,
) -> Phase3DReadinessReviewResult:
    """Load an experiment config and review its frozen dataset artifacts."""

    config = load_experiment_config(Path(experiment_config_path))
    if artifact_root is not None:
        config = config.with_overrides(artifact_root=artifact_root)
    return run_phase3d_readiness_review(
        config=config,
        operator_notes=operator_notes,
        database_run_threshold=database_run_threshold,
        database_bytes_threshold=database_bytes_threshold,
    )


def build_storage_volume_review(
    dataset_index: Mapping[str, Any],
    frozen_manifest: Mapping[str, Any],
    dataset_index_path: Path,
    frozen_manifest_path: Path,
    store: FileSystemResultsStore,
) -> Dict[str, object]:
    """Summarise frozen artifact volume and current filesystem scan cost."""

    records = _records(dataset_index)
    artifact_records = [
        artifact
        for record in records
        for artifact in _artifact_records(record).values()
    ]
    total_artifact_bytes = sum(_artifact_size(artifact) for artifact in artifact_records)
    source_artifact_count = len(frozen_manifest.get("source_artifacts", {}))
    freeze_artifact_count = len(frozen_manifest.get("freeze_artifacts", {}))
    average_artifact_bytes = int(total_artifact_bytes / len(artifact_records)) if artifact_records else 0

    return {
        "schema_version": SCHEMA_VERSION,
        "readiness_review_version": READINESS_REVIEW_VERSION,
        "dataset_id": dataset_index["dataset_id"],
        "experiment_id": dataset_index["experiment_id"],
        "run_count": dataset_index["run_count"],
        "included_run_count": dataset_index["included_run_count"],
        "excluded_run_count": dataset_index["excluded_run_count"],
        "run_artifact_count": len(artifact_records),
        "source_artifact_count": source_artifact_count,
        "freeze_artifact_count": freeze_artifact_count,
        "total_run_artifact_bytes": total_artifact_bytes,
        "average_run_artifact_bytes": average_artifact_bytes,
        "dataset_index_artifact": _artifact_record("dataset_index", dataset_index_path, store),
        "frozen_dataset_manifest_artifact": _artifact_record(
            "frozen_dataset_manifest",
            frozen_manifest_path,
            store,
        ),
        "storage_backend": "filesystem",
        "current_scan_strategy": "read frozen dataset_index.json and referenced artifact records",
    }


def build_query_requirements(dataset_index: Mapping[str, Any]) -> Dict[str, object]:
    """Derive query requirements from the frozen dataset index fields."""

    records = _records(dataset_index)
    component_ids = sorted({_record_str(record, "component_config_id") for record in records})
    task_ids = sorted({_record_str(record, "task_id") for record in records})
    seeds = sorted({_record_int(record, "seed") for record in records})
    schedules = sorted({_record_str(record, "perturbation_schedule_id") for record in records})

    return {
        "schema_version": SCHEMA_VERSION,
        "readiness_review_version": READINESS_REVIEW_VERSION,
        "dataset_id": dataset_index["dataset_id"],
        "primary_analysis_entrypoint": "dataset_index.json",
        "required_filters": [
            "component_config_id",
            "task_id",
            "seed",
            "perturbation_schedule_id",
            "inclusion_status",
            "artifact_validation_passed",
        ],
        "required_groupings": [
            "memory_backend",
            "retrieval_strategy",
            "scheduling_policy",
            "component_config_id",
            "task_id",
        ],
        "required_joins": [
            "run metadata to trace artifact",
            "run metadata to verification artifact",
            "run metadata to metrics artifact",
            "run metadata to report artifact",
            "run metadata to manifest artifact",
        ],
        "current_cardinalities": {
            "component_config_id": len(component_ids),
            "task_id": len(task_ids),
            "seed": len(seeds),
            "perturbation_schedule_id": len(schedules),
        },
        "dashboard_candidate_views": [
            "dataset overview",
            "component comparison matrix",
            "run drilldown",
            "artifact integrity table",
            "QA and freeze summary",
        ],
    }


def build_results_index_decision(
    dataset_index: Mapping[str, Any],
    storage_volume_review: Mapping[str, Any],
    query_requirements: Mapping[str, Any],
    operator_notes: str,
    database_run_threshold: int,
    database_bytes_threshold: int,
) -> Dict[str, object]:
    """Decide whether the current frozen dataset justifies a DB or dashboard."""

    run_count = int(storage_volume_review["run_count"])
    total_bytes = int(storage_volume_review["total_run_artifact_bytes"])
    query_count = (
        len(query_requirements["required_filters"])
        + len(query_requirements["required_groupings"])
        + len(query_requirements["required_joins"])
    )
    database_recommended = run_count > database_run_threshold or total_bytes > database_bytes_threshold
    filesystem_sufficient = not database_recommended
    dashboard_recommended_now = database_recommended and run_count > 0

    return {
        "schema_version": SCHEMA_VERSION,
        "readiness_review_version": READINESS_REVIEW_VERSION,
        "dataset_id": dataset_index["dataset_id"],
        "experiment_id": dataset_index["experiment_id"],
        "operator_notes": operator_notes,
        "filesystem_sufficient": filesystem_sufficient,
        "database_recommended": database_recommended,
        "database_decision": "defer_results_database" if filesystem_sufficient else "plan_sqlite_read_model",
        "database_rationale": (
            "The frozen dataset is small enough for direct dataset_index.json consumption."
            if filesystem_sufficient
            else "The frozen dataset exceeds configured volume thresholds and should use a queryable read model."
        ),
        "database_thresholds": {
            "run_count": database_run_threshold,
            "total_artifact_bytes": database_bytes_threshold,
        },
        "observed_volume": {
            "run_count": run_count,
            "total_artifact_bytes": total_bytes,
            "query_requirement_count": query_count,
        },
        "read_model_policy": {
            "would_be_read_only": True,
            "source_of_truth": "frozen filesystem artifacts",
            "raw_artifacts_replaced": False,
            "candidate_backend": "sqlite",
            "candidate_phase": "future_extension_after_phase3d",
        },
        "dashboard_recommended_now": dashboard_recommended_now,
        "dashboard_decision": "defer_dashboard_until_analysis_needs_expand"
        if not dashboard_recommended_now
        else "plan_dashboard_over_read_model",
        "dashboard_rationale": (
            "The frozen dataset can be inspected from Markdown and JSON artifacts; dashboard scope is documented for later analysis."
            if not dashboard_recommended_now
            else "The dataset volume justifies interactive filtering and run drilldown."
        ),
        "phase3d_acceptance_criteria": {
            "filesystem_sufficiency_recorded": True,
            "database_if_needed_is_read_model": True,
            "dashboard_scope_based_on_frozen_dataset": True,
        },
    }


def build_dashboard_requirements_markdown(
    dataset_index: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> str:
    """Build dashboard requirements derived from the frozen dataset."""

    records = _records(dataset_index)
    lines = [
        "# Phase 3D Dashboard Requirements Review",
        "",
        "## Decision",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Dataset ID | `{dataset_index['dataset_id']}` |",
        f"| Run count | {dataset_index['run_count']} |",
        f"| Dashboard recommended now | `{str(decision['dashboard_recommended_now']).lower()}` |",
        f"| Dashboard decision | `{decision['dashboard_decision']}` |",
        "",
        "## Required Filters",
        "",
        "- Component configuration",
        "- Task",
        "- Seed",
        "- Perturbation schedule",
        "- Inclusion status",
        "- Artifact validation status",
        "",
        "## Candidate Views",
        "",
        "- Dataset overview with included/excluded run counts",
        "- Component comparison matrix over memory, retrieval, and scheduling levels",
        "- Run drilldown with links to trace, verification, metrics, report, and manifest artifacts",
        "- Artifact integrity table with SHA-256 hashes and byte sizes",
        "- QA and freeze summary showing pilot decision and freeze prerequisites",
        "",
        "## Current Dataset Scope",
        "",
        f"The frozen dataset currently contains {len(records)} run records. "
        "The dashboard should remain deferred until analysis needs require repeated interactive filtering.",
        "",
    ]
    return "\n".join(lines)


def build_phase3d_review_report(
    storage_review: Mapping[str, Any],
    query_requirements: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> str:
    """Build a human-readable Phase 3D readiness review report."""

    lines = [
        "# Phase 3D Results Index and Dashboard Readiness Review",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Dataset ID | `{storage_review['dataset_id']}` |",
        f"| Run count | {storage_review['run_count']} |",
        f"| Run artifact count | {storage_review['run_artifact_count']} |",
        f"| Total run artifact bytes | {storage_review['total_run_artifact_bytes']} |",
        f"| Filesystem sufficient | `{str(decision['filesystem_sufficient']).lower()}` |",
        f"| Database recommended | `{str(decision['database_recommended']).lower()}` |",
        f"| Database decision | `{decision['database_decision']}` |",
        f"| Dashboard recommended now | `{str(decision['dashboard_recommended_now']).lower()}` |",
        "",
        "## Query Requirements",
        "",
        f"- Filters: {', '.join(query_requirements['required_filters'])}",
        f"- Groupings: {', '.join(query_requirements['required_groupings'])}",
        f"- Joins: {len(query_requirements['required_joins'])} artifact lookups from run metadata",
        "",
        "## Read Model Policy",
        "",
        "If a database is introduced later, it must be a read-only index over frozen filesystem artifacts. "
        "It must not replace raw trace, verification, metrics, report, manifest, or dataset index artifacts.",
        "",
    ]
    return "\n".join(lines)


def _results_store(config: ExperimentConfig) -> FileSystemResultsStore:
    if config.artifact_root is not None:
        return FileSystemResultsStore.from_artifact_root(config.artifact_root)
    return FileSystemResultsStore.from_artifact_root(Path("artifacts"))


def _validate_frozen_inputs(dataset_index: Mapping[str, Any], frozen_manifest: Mapping[str, Any]) -> None:
    if dataset_index.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError("dataset_index.schema_version is invalid")
    if frozen_manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError("frozen_dataset_manifest.schema_version is invalid")
    if not frozen_manifest.get("frozen"):
        raise ValidationError("frozen dataset manifest must have frozen=true")
    if dataset_index.get("dataset_id") != frozen_manifest.get("dataset_id"):
        raise ValidationError("dataset index and frozen manifest dataset_id values do not match")
    if dataset_index.get("experiment_id") != frozen_manifest.get("experiment_id"):
        raise ValidationError("dataset index and frozen manifest experiment_id values do not match")


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


def _artifact_size(artifact: Mapping[str, Any]) -> int:
    value = artifact.get("size_bytes")
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError("artifact.size_bytes must be an integer")
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


def _artifact_record(name: str, path: Path, store: FileSystemResultsStore) -> Dict[str, object]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ValidationError(f"Could not read review artifact {path}: {exc}") from exc
    return {
        "name": name,
        "path": store.relative_path(path),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"Required Phase 3D input not found: {path}") from exc
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValidationError(f"Invalid Phase 3D JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError(f"Phase 3D JSON artifact must contain an object: {path}")
    return payload
