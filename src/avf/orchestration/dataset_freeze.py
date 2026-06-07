"""Phase 3C dataset freeze over validated experiment artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from avf.contracts import SCHEMA_VERSION, ValidationError
from avf.storage import ArtifactRecord, FileSystemResultsStore

from .experiment_matrix import ExperimentConfig, build_experiment_matrix, load_experiment_config
from .pilot_qa import (
    FAILURE_NOTES_JSON_FILE,
    PILOT_LOG_FILE,
    PILOT_QA_SUMMARY_FILE,
    RERUN_RECORD_FILE,
    FailureNote,
    QAValidationResult,
    current_commit_hash,
    read_failure_notes,
    read_rerun_records,
    utc_timestamp,
    validate_dataset_execution_gate,
    validate_failure_notes,
    validate_rerun_records,
)


DATASET_FREEZE_VERSION = "1.0"
DATASET_INDEX_FILE = "dataset_index.json"
FROZEN_DATASET_MANIFEST_FILE = "frozen_dataset_manifest.json"
DATASET_REPORT_FILE = "dataset_report.md"


@dataclass(frozen=True)
class Phase3CDatasetFreezeArtifacts:
    """Dataset freeze artifacts produced by Phase 3C."""

    dataset_index: Path
    frozen_dataset_manifest: Path
    dataset_report: Path

    def to_dict(self) -> Dict[str, str]:
        return {
            "dataset_index": str(self.dataset_index),
            "frozen_dataset_manifest": str(self.frozen_dataset_manifest),
            "dataset_report": str(self.dataset_report),
        }


@dataclass(frozen=True)
class Phase3CDatasetFreezeResult:
    """Outputs from a Phase 3C dataset freeze."""

    dataset_id: str
    experiment_id: str
    artifacts: Phase3CDatasetFreezeArtifacts
    dataset_index: Dict[str, object]
    frozen_dataset_manifest: Dict[str, object]
    dataset_report: str
    validation: QAValidationResult

    def to_dict(self) -> Dict[str, object]:
        return {
            "dataset_id": self.dataset_id,
            "experiment_id": self.experiment_id,
            "included_run_count": self.dataset_index["included_run_count"],
            "excluded_run_count": self.dataset_index["excluded_run_count"],
            "frozen": self.frozen_dataset_manifest["frozen"],
            "validation": self.validation.to_dict(),
            "artifacts": self.artifacts.to_dict(),
        }


def freeze_phase3c_dataset(
    config: ExperimentConfig,
    experiment_config_path: Optional[Path] = None,
    dataset_id: Optional[str] = None,
    frozen_at: Optional[str] = None,
    commit_hash: Optional[str] = None,
    operator_notes: str = "Phase 3C dataset freeze.",
) -> Phase3CDatasetFreezeResult:
    """Freeze an accepted Phase 3 pilot artifact set for analysis.

    This function does not execute the experiment. It reads the Phase 3A/3B
    artifact set, validates the pilot QA gate, records artifact hashes, and
    writes dataset-level index, manifest, and report artifacts.
    """

    store = _results_store(config)
    experiment_dir = store.layout.artifact_root / "experiments" / config.experiment_id
    artifacts = Phase3CDatasetFreezeArtifacts(
        dataset_index=experiment_dir / DATASET_INDEX_FILE,
        frozen_dataset_manifest=experiment_dir / FROZEN_DATASET_MANIFEST_FILE,
        dataset_report=experiment_dir / DATASET_REPORT_FILE,
    )
    freeze_dataset_id = dataset_id or f"{config.experiment_id}_dataset_v1"
    freeze_timestamp = frozen_at or utc_timestamp()
    freeze_commit = commit_hash or current_commit_hash()

    source = _load_source_artifacts(config, store, experiment_dir)
    validation = validate_dataset_freeze_inputs(source)
    if not validation.passed:
        raise ValidationError("Dataset freeze blocked: " + "; ".join(validation.issues))

    dataset_index = build_dataset_index(
        config=config,
        store=store,
        dataset_id=freeze_dataset_id,
        frozen_at=freeze_timestamp,
        commit_hash=freeze_commit,
        operator_notes=operator_notes,
        experiment_config_path=experiment_config_path,
        source=source,
    )
    _write_json(artifacts.dataset_index, dataset_index)

    dataset_report = build_dataset_report(dataset_index)
    _write_text(artifacts.dataset_report, dataset_report)

    frozen_manifest = build_frozen_dataset_manifest(
        dataset_index=dataset_index,
        store=store,
        artifacts=artifacts,
        source=source,
    )
    _write_json(artifacts.frozen_dataset_manifest, frozen_manifest)

    return Phase3CDatasetFreezeResult(
        dataset_id=freeze_dataset_id,
        experiment_id=config.experiment_id,
        artifacts=artifacts,
        dataset_index=dataset_index,
        frozen_dataset_manifest=frozen_manifest,
        dataset_report=dataset_report,
        validation=validation,
    )


def freeze_phase3c_dataset_from_config(
    experiment_config_path: Path,
    artifact_root: Optional[Path] = None,
    dataset_id: Optional[str] = None,
    frozen_at: Optional[str] = None,
    commit_hash: Optional[str] = None,
    operator_notes: str = "Phase 3C dataset freeze.",
) -> Phase3CDatasetFreezeResult:
    """Load an experiment config and freeze its accepted dataset artifacts."""

    config_path = Path(experiment_config_path)
    config = load_experiment_config(config_path)
    config = config.with_overrides(artifact_root=artifact_root) if artifact_root is not None else config
    return freeze_phase3c_dataset(
        config=config,
        experiment_config_path=config_path,
        dataset_id=dataset_id,
        frozen_at=frozen_at,
        commit_hash=commit_hash,
        operator_notes=operator_notes,
    )


def validate_dataset_freeze_inputs(source: Mapping[str, Any]) -> QAValidationResult:
    """Validate that a Phase 3B artifact set is eligible for freeze."""

    issues: List[str] = []
    required_paths = source["required_paths"]
    if not isinstance(required_paths, Mapping):
        raise ValidationError("required_paths must be an object")
    for name, path in sorted(required_paths.items()):
        if not Path(str(path)).exists():
            issues.append(f"Missing required freeze input artifact: {name}={path}")

    pilot_summary = source["pilot_qa_summary"]
    if not isinstance(pilot_summary, Mapping):
        raise ValidationError("pilot_qa_summary must be an object")
    if not pilot_summary.get("ready_for_dataset_execution"):
        issues.append("Pilot QA summary is not ready for dataset execution")
    if pilot_summary.get("dataset_execution_blocked"):
        issues.append("Pilot QA summary indicates dataset execution is blocked")

    matrix = source["matrix"]
    run_index = source["run_index"]
    if not isinstance(matrix, Mapping) or not isinstance(run_index, Mapping):
        raise ValidationError("matrix and run_index must be objects")
    if matrix.get("row_count") != run_index.get("record_count"):
        issues.append("Matrix row count does not match run index record count")

    rerun_validation = validate_rerun_records(source["rerun_records"])
    failure_validation = validate_failure_notes(source["failure_notes"])
    gate_validation = validate_dataset_execution_gate(source["failure_notes"])
    issues.extend(rerun_validation.issues)
    issues.extend(failure_validation.issues)
    issues.extend(gate_validation.issues)

    for note in source["failure_notes"]:
        if note.dataset_decision in {"rerun", "block_freeze"}:
            issues.append(
                f"Unresolved failure note blocks freeze: {note.run_id} decision={note.dataset_decision}"
            )

    records = _records(run_index)
    failure_notes_by_run = _failure_notes_by_run(source["failure_notes"])
    for record in records:
        run_id = _record_str(record, "run_id")
        note = failure_notes_by_run.get(run_id)
        if note is None or note.dataset_decision == "include":
            validation = source["artifact_validations"].get(run_id)
            if validation is None:
                issues.append(f"Missing artifact validation for included run: {run_id}")
            elif not validation.passed:
                issues.append(f"Included run has invalid artifacts: {run_id}")
        elif note.dataset_decision == "exclude":
            continue
        else:
            issues.append(f"Run has unresolved dataset decision: {run_id} decision={note.dataset_decision}")

    return QAValidationResult(passed=not issues, issues=issues)


def build_dataset_index(
    config: ExperimentConfig,
    store: FileSystemResultsStore,
    dataset_id: str,
    frozen_at: str,
    commit_hash: str,
    operator_notes: str,
    experiment_config_path: Optional[Path],
    source: Mapping[str, Any],
) -> Dict[str, object]:
    """Build the analysis-facing dataset index."""

    matrix = source["matrix"]
    run_index = source["run_index"]
    pilot_summary = source["pilot_qa_summary"]
    failure_notes = source["failure_notes"]
    rerun_records = source["rerun_records"]
    failure_notes_by_run = _failure_notes_by_run(failure_notes)

    records: List[Dict[str, object]] = []
    included_count = 0
    excluded_count = 0
    for record in _records(run_index):
        run_id = _record_str(record, "run_id")
        note = failure_notes_by_run.get(run_id)
        inclusion_status = "included"
        dataset_decision = "include"
        exclusion_reason: Optional[str] = None
        if note is not None:
            dataset_decision = note.dataset_decision
            if note.dataset_decision == "exclude":
                inclusion_status = "excluded"
                exclusion_reason = note.observed_symptom

        validation = source["artifact_validations"].get(run_id)
        artifact_records: Dict[str, object] = {}
        if validation is not None:
            artifact_records = {
                name: artifact.to_dict()
                for name, artifact in sorted(validation.artifacts.items())
            }
        manifest_path = store.manifest_path(run_id)
        if manifest_path.exists():
            artifact_records["manifest"] = _artifact_record("manifest", manifest_path, store).to_dict()

        if inclusion_status == "included":
            included_count += 1
        else:
            excluded_count += 1

        records.append(
            {
                "row_id": _record_str(record, "row_id"),
                "run_id": run_id,
                "inclusion_status": inclusion_status,
                "dataset_decision": dataset_decision,
                "exclusion_reason": exclusion_reason,
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
                "task_success": bool(record.get("task_success")),
                "verification_passed": bool(record.get("verification_passed")),
                "artifact_validation_passed": validation.passed if validation is not None else False,
                "artifact_records": artifact_records,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_index_version": DATASET_FREEZE_VERSION,
        "dataset_id": dataset_id,
        "experiment_id": config.experiment_id,
        "frozen_at": frozen_at,
        "commit_hash": commit_hash,
        "operator_notes": operator_notes,
        "experiment_config_path": str(experiment_config_path) if experiment_config_path is not None else None,
        "experiment_config_artifact": _relative_required_path(source, "experiment_config", store),
        "matrix_artifact": _relative_required_path(source, "matrix", store),
        "run_index_artifact": _relative_required_path(source, "run_index", store),
        "pilot_qa_summary_artifact": _relative_required_path(source, "pilot_qa_summary", store),
        "fixture_versions": _fixture_versions(config),
        "matrix_summary": {
            "row_count": matrix["row_count"],
            "task_ids": sorted({_record_str(record, "task_id") for record in records}),
            "run_config_ids": sorted({_record_str(record, "run_config_id") for record in records}),
            "seeds": sorted({_record_int(record, "seed") for record in records}),
            "perturbation_schedule_ids": sorted(
                {_record_str(record, "perturbation_schedule_id") for record in records}
            ),
            "component_config_ids": [_record_str(record, "component_config_id") for record in records],
        },
        "qa_summary": {
            "pilot_mode": pilot_summary["pilot_mode"],
            "pilot_decision": pilot_summary["pilot_decision"],
            "ready_for_dataset_execution": pilot_summary["ready_for_dataset_execution"],
            "failure_note_count": len(failure_notes),
            "rerun_record_count": len(rerun_records),
        },
        "run_count": len(records),
        "included_run_count": included_count,
        "excluded_run_count": excluded_count,
        "records": records,
    }


def build_frozen_dataset_manifest(
    dataset_index: Mapping[str, object],
    store: FileSystemResultsStore,
    artifacts: Phase3CDatasetFreezeArtifacts,
    source: Mapping[str, Any],
) -> Dict[str, object]:
    """Build the immutable frozen dataset manifest."""

    source_records = {
        name: _artifact_record(name, Path(str(path)), store).to_dict()
        for name, path in sorted(source["required_paths"].items())
        if Path(str(path)).exists()
    }
    freeze_records = {
        "dataset_index": _artifact_record("dataset_index", artifacts.dataset_index, store).to_dict(),
        "dataset_report": _artifact_record("dataset_report", artifacts.dataset_report, store).to_dict(),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "frozen_dataset_manifest_version": DATASET_FREEZE_VERSION,
        "dataset_id": dataset_index["dataset_id"],
        "experiment_id": dataset_index["experiment_id"],
        "frozen_at": dataset_index["frozen_at"],
        "commit_hash": dataset_index["commit_hash"],
        "experiment_config_path": dataset_index["experiment_config_path"],
        "experiment_config_artifact": dataset_index["experiment_config_artifact"],
        "frozen": True,
        "immutability_policy": "raw run artifacts and dataset index are read-only after freeze",
        "freeze_prerequisites": {
            "matrix_complete": dataset_index["run_count"] == dataset_index["matrix_summary"]["row_count"],
            "all_included_runs_have_valid_artifacts": all(
                record["artifact_validation_passed"]
                for record in dataset_index["records"]
                if record["inclusion_status"] == "included"
            ),
            "excluded_runs_have_documented_reasons": all(
                bool(record["exclusion_reason"])
                for record in dataset_index["records"]
                if record["inclusion_status"] == "excluded"
            ),
            "pilot_qa_ready": dataset_index["qa_summary"]["ready_for_dataset_execution"],
        },
        "source_artifacts": source_records,
        "freeze_artifacts": freeze_records,
    }


def build_dataset_report(dataset_index: Mapping[str, object]) -> str:
    """Build the human-readable Phase 3C dataset report."""

    lines = [
        "# Phase 3C Frozen Dataset Report",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Dataset ID | `{dataset_index['dataset_id']}` |",
        f"| Experiment ID | `{dataset_index['experiment_id']}` |",
        f"| Frozen at | `{dataset_index['frozen_at']}` |",
        f"| Commit hash | `{dataset_index['commit_hash']}` |",
        f"| Run count | {dataset_index['run_count']} |",
        f"| Included runs | {dataset_index['included_run_count']} |",
        f"| Excluded runs | {dataset_index['excluded_run_count']} |",
        f"| Pilot decision | `{dataset_index['qa_summary']['pilot_decision']}` |",
        "",
        "## Included Runs",
        "",
        "| Run ID | Component | Task | Seed | Schedule | Artifacts valid |",
        "|---|---|---|---|---|---|",
    ]
    for record in dataset_index["records"]:
        if record["inclusion_status"] != "included":
            continue
        lines.append(
            f"| `{record['run_id']}` | `{record['component_config_id']}` | "
            f"`{record['task_id']}` | `{record['seed']}` | "
            f"`{record['perturbation_schedule_id']}` | "
            f"`{str(record['artifact_validation_passed']).lower()}` |"
        )

    excluded = [record for record in dataset_index["records"] if record["inclusion_status"] == "excluded"]
    lines.extend(["", "## Excluded Runs", ""])
    if excluded:
        lines.extend(["| Run ID | Decision | Reason |", "|---|---|---|"])
        for record in excluded:
            lines.append(
                f"| `{record['run_id']}` | `{record['dataset_decision']}` | {record['exclusion_reason']} |"
            )
    else:
        lines.append("No runs were excluded from this dataset freeze.")

    lines.extend(
        [
            "",
            "## Analysis Use",
            "",
            "Use `dataset_index.json` as the analysis entrypoint. It records run metadata, "
            "inclusion decisions, artifact paths, and artifact hashes, so analysis can load "
            "the frozen dataset without rerunning the experiment.",
            "",
        ]
    )
    return "\n".join(lines)


def _load_source_artifacts(
    config: ExperimentConfig,
    store: FileSystemResultsStore,
    experiment_dir: Path,
) -> Dict[str, Any]:
    comparison_path = store.layout.artifact_root / "comparisons" / f"{config.experiment_id}.json"
    required_paths = {
        "experiment_config": experiment_dir / "experiment_config.json",
        "matrix": experiment_dir / "matrix.json",
        "run_index": experiment_dir / "run_index.json",
        "comparison_summary": comparison_path,
        "pilot_log": experiment_dir / PILOT_LOG_FILE,
        "pilot_qa_summary": experiment_dir / PILOT_QA_SUMMARY_FILE,
        "rerun_records": experiment_dir / RERUN_RECORD_FILE,
        "failure_notes": experiment_dir / FAILURE_NOTES_JSON_FILE,
    }
    matrix = _read_json(required_paths["matrix"])
    run_index = _read_json(required_paths["run_index"])
    pilot_qa_summary = _read_json(required_paths["pilot_qa_summary"])
    rerun_records = read_rerun_records(required_paths["rerun_records"])
    failure_notes = read_failure_notes(required_paths["failure_notes"])
    artifact_validations = {
        _record_str(record, "run_id"): store.validate_run_artifacts(_record_str(record, "run_id"))
        for record in _records(run_index)
    }
    expected_matrix = build_experiment_matrix(config)
    if expected_matrix.row_count != matrix.get("row_count"):
        raise ValidationError("Configured matrix row count does not match stored matrix artifact")

    return {
        "required_paths": required_paths,
        "matrix": matrix,
        "run_index": run_index,
        "pilot_qa_summary": pilot_qa_summary,
        "rerun_records": rerun_records,
        "failure_notes": failure_notes,
        "artifact_validations": artifact_validations,
    }


def _results_store(config: ExperimentConfig) -> FileSystemResultsStore:
    if config.artifact_root is not None:
        return FileSystemResultsStore.from_artifact_root(config.artifact_root)
    run_config_path = config.run_config_fixtures[0]
    payload = _read_json(run_config_path)
    from avf.contracts import RunConfig

    return FileSystemResultsStore.from_run_config(RunConfig.from_dict(payload))


def _fixture_versions(config: ExperimentConfig) -> Dict[str, object]:
    return {
        "task_fixtures": [str(path) for path in config.task_fixtures],
        "run_config_fixtures": [str(path) for path in config.run_config_fixtures],
        "component_fixtures": [str(path) for path in config.component_fixtures],
        "tool_spec_fixtures": [str(path) for path in config.tool_spec_fixtures],
        "perturbation_schedules": list(config.perturbation_schedules),
    }


def _failure_notes_by_run(notes: List[FailureNote]) -> Dict[str, FailureNote]:
    values: Dict[str, FailureNote] = {}
    for note in notes:
        values[note.run_id] = note
    return values


def _relative_required_path(source: Mapping[str, Any], name: str, store: FileSystemResultsStore) -> str:
    return store.relative_path(Path(str(source["required_paths"][name])))


def _records(payload: Mapping[str, Any]) -> List[Dict[str, Any]]:
    records = payload.get("records")
    if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
        raise ValidationError("records must be a list of objects")
    return records


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


def _artifact_record(name: str, path: Path, store: FileSystemResultsStore) -> ArtifactRecord:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ValidationError(f"Could not read artifact for freeze: {path}: {exc}") from exc
    return ArtifactRecord(
        name=name,
        path=store.relative_path(path),
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
    )


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
        raise ValidationError(f"Required dataset freeze input not found: {path}") from exc
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValidationError(f"Invalid dataset freeze JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError(f"Dataset freeze JSON artifact must contain an object: {path}")
    return payload
