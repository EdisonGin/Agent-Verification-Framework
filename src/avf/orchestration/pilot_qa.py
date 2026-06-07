"""Phase 3B pilot QA, rerun records, and failure notes."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, Dict, Iterable, List, Mapping, Optional

from avf.contracts import SCHEMA_VERSION, ValidationError
from avf.storage import FileSystemResultsStore

from .experiment_matrix import (
    ExperimentConfig,
    ExperimentMatrixRow,
    Phase3AExperimentResult,
    run_phase3a_full_factorial,
)


DEFAULT_PILOT_MODE = "full_factorial_pilot"
RERUN_RECORD_FILE = "rerun_records.json"
FAILURE_NOTES_JSON_FILE = "failure_notes.json"
FAILURE_NOTES_MD_FILE = "failure_notes.md"
PILOT_LOG_FILE = "pilot_log.md"
PILOT_QA_SUMMARY_FILE = "pilot_qa_summary.json"


@dataclass(frozen=True)
class QAValidationResult:
    """Validation result for Phase 3B QA records."""

    passed: bool
    issues: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "passed": self.passed,
            "issues": list(self.issues),
        }


@dataclass(frozen=True)
class RerunRecord:
    """Document why a controlled cell was rerun or should be rerun."""

    schema_version: str
    rerun_id: str
    original_run_id: str
    component_config_id: str
    task_id: str
    seed: int
    perturbation_schedule_id: str
    reason: str
    decision: str
    operator_notes: str
    timestamp: str
    commit_hash: str

    fields: ClassVar[List[str]] = [
        "schema_version",
        "rerun_id",
        "original_run_id",
        "component_config_id",
        "task_id",
        "seed",
        "perturbation_schedule_id",
        "reason",
        "decision",
        "operator_notes",
        "timestamp",
        "commit_hash",
    ]
    decisions: ClassVar[List[str]] = [
        "overwrite",
        "exclude",
        "preserve_failed_attempt",
        "restart_block",
    ]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RerunRecord":
        data = _require_mapping(data, cls.__name__)
        _no_extra(data, cls.fields, cls.__name__)
        return cls(
            schema_version=_require_schema_version(data, cls.__name__),
            rerun_id=_require_str(data, "rerun_id", cls.__name__),
            original_run_id=_require_str(data, "original_run_id", cls.__name__),
            component_config_id=_require_str(data, "component_config_id", cls.__name__),
            task_id=_require_str(data, "task_id", cls.__name__),
            seed=_require_int(data, "seed", cls.__name__, minimum=0),
            perturbation_schedule_id=_require_str(data, "perturbation_schedule_id", cls.__name__),
            reason=_require_str(data, "reason", cls.__name__),
            decision=_require_enum(data, "decision", cls.__name__, cls.decisions),
            operator_notes=_require_str(data, "operator_notes", cls.__name__),
            timestamp=_require_str(data, "timestamp", cls.__name__),
            commit_hash=_require_str(data, "commit_hash", cls.__name__),
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "rerun_id": self.rerun_id,
            "original_run_id": self.original_run_id,
            "component_config_id": self.component_config_id,
            "task_id": self.task_id,
            "seed": self.seed,
            "perturbation_schedule_id": self.perturbation_schedule_id,
            "reason": self.reason,
            "decision": self.decision,
            "operator_notes": self.operator_notes,
            "timestamp": self.timestamp,
            "commit_hash": self.commit_hash,
        }


@dataclass(frozen=True)
class FailureNote:
    """Classify a pilot-run failure and its dataset decision."""

    schema_version: str
    run_id: str
    component_config_id: str
    task_id: str
    seed: int
    perturbation_schedule_id: str
    failure_class: str
    observed_symptom: str
    root_cause: str
    dataset_decision: str
    evidence_paths: List[str]

    fields: ClassVar[List[str]] = [
        "schema_version",
        "run_id",
        "component_config_id",
        "task_id",
        "seed",
        "perturbation_schedule_id",
        "failure_class",
        "observed_symptom",
        "root_cause",
        "dataset_decision",
        "evidence_paths",
    ]
    failure_classes: ClassVar[List[str]] = [
        "task_failure",
        "verifier_failure",
        "artifact_failure",
        "infrastructure_failure",
    ]
    dataset_decisions: ClassVar[List[str]] = [
        "include",
        "exclude",
        "rerun",
        "block_freeze",
    ]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FailureNote":
        data = _require_mapping(data, cls.__name__)
        _no_extra(data, cls.fields, cls.__name__)
        return cls(
            schema_version=_require_schema_version(data, cls.__name__),
            run_id=_require_str(data, "run_id", cls.__name__),
            component_config_id=_require_str(data, "component_config_id", cls.__name__),
            task_id=_require_str(data, "task_id", cls.__name__),
            seed=_require_int(data, "seed", cls.__name__, minimum=0),
            perturbation_schedule_id=_require_str(data, "perturbation_schedule_id", cls.__name__),
            failure_class=_require_enum(data, "failure_class", cls.__name__, cls.failure_classes),
            observed_symptom=_require_str(data, "observed_symptom", cls.__name__),
            root_cause=_require_str(data, "root_cause", cls.__name__),
            dataset_decision=_require_enum(data, "dataset_decision", cls.__name__, cls.dataset_decisions),
            evidence_paths=_require_str_list(data, "evidence_paths", cls.__name__),
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "component_config_id": self.component_config_id,
            "task_id": self.task_id,
            "seed": self.seed,
            "perturbation_schedule_id": self.perturbation_schedule_id,
            "failure_class": self.failure_class,
            "observed_symptom": self.observed_symptom,
            "root_cause": self.root_cause,
            "dataset_decision": self.dataset_decision,
            "evidence_paths": list(self.evidence_paths),
        }


@dataclass(frozen=True)
class Phase3BPilotQAArtifacts:
    """Experiment-level QA artifacts produced by the Phase 3B pilot runner."""

    pilot_log: Path
    rerun_records: Path
    failure_notes_json: Path
    failure_notes_markdown: Path
    qa_summary: Path

    def to_dict(self) -> Dict[str, str]:
        return {
            "pilot_log": str(self.pilot_log),
            "rerun_records": str(self.rerun_records),
            "failure_notes_json": str(self.failure_notes_json),
            "failure_notes_markdown": str(self.failure_notes_markdown),
            "qa_summary": str(self.qa_summary),
        }


@dataclass(frozen=True)
class Phase3BPilotQAResult:
    """Outputs from a Phase 3B pilot QA execution."""

    phase3a_result: Phase3AExperimentResult
    artifacts: Phase3BPilotQAArtifacts
    rerun_records: List[RerunRecord]
    failure_notes: List[FailureNote]
    qa_summary: Dict[str, object]
    rerun_record_validation: QAValidationResult
    failure_note_validation: QAValidationResult

    def to_dict(self) -> Dict[str, object]:
        return {
            "experiment_id": self.phase3a_result.experiment.experiment_id,
            "pilot_mode": self.qa_summary["pilot_mode"],
            "expected_run_count": self.qa_summary["expected_run_count"],
            "completed_run_count": self.qa_summary["completed_run_count"],
            "failure_note_count": len(self.failure_notes),
            "rerun_record_count": len(self.rerun_records),
            "dataset_execution_blocked": self.qa_summary["dataset_execution_blocked"],
            "ready_for_dataset_execution": self.qa_summary["ready_for_dataset_execution"],
            "qa_summary": dict(self.qa_summary),
            "artifacts": self.artifacts.to_dict(),
            "rerun_record_validation": self.rerun_record_validation.to_dict(),
            "failure_note_validation": self.failure_note_validation.to_dict(),
        }


def run_phase3b_pilot_qa(
    config: ExperimentConfig,
    experiment_config_path: Optional[Path] = None,
    operator_notes: str = "Phase 3B pilot QA execution.",
    known_limitations: Optional[List[str]] = None,
    timestamp: Optional[str] = None,
    commit_hash: Optional[str] = None,
) -> Phase3BPilotQAResult:
    """Run the Phase 3A matrix in pilot mode and write Phase 3B QA artifacts."""

    pilot_timestamp = timestamp or utc_timestamp()
    pilot_commit = commit_hash or current_commit_hash()
    limitations = list(known_limitations or [])
    phase3a_result = run_phase3a_full_factorial(config)
    results_store = _results_store(config, phase3a_result)
    experiment_dir = results_store.layout.artifact_root / "experiments" / config.experiment_id
    artifacts = Phase3BPilotQAArtifacts(
        pilot_log=experiment_dir / PILOT_LOG_FILE,
        rerun_records=experiment_dir / RERUN_RECORD_FILE,
        failure_notes_json=experiment_dir / FAILURE_NOTES_JSON_FILE,
        failure_notes_markdown=experiment_dir / FAILURE_NOTES_MD_FILE,
        qa_summary=experiment_dir / PILOT_QA_SUMMARY_FILE,
    )

    failure_notes = build_failure_notes(phase3a_result, results_store)
    rerun_records: List[RerunRecord] = []
    rerun_record_validation = validate_rerun_records(rerun_records)
    failure_note_validation = validate_failure_notes(failure_notes)
    qa_summary = build_pilot_qa_summary(
        phase3a_result=phase3a_result,
        failure_notes=failure_notes,
        rerun_records=rerun_records,
        rerun_record_validation=rerun_record_validation,
        failure_note_validation=failure_note_validation,
        timestamp=pilot_timestamp,
        commit_hash=pilot_commit,
        experiment_config_path=experiment_config_path,
        operator_notes=operator_notes,
        known_limitations=limitations,
        results_store=results_store,
        artifacts=artifacts,
    )

    write_rerun_records(artifacts.rerun_records, rerun_records)
    write_failure_notes_json(artifacts.failure_notes_json, failure_notes)
    write_failure_notes_markdown(artifacts.failure_notes_markdown, failure_notes)
    _write_json(artifacts.qa_summary, qa_summary)
    _write_text(artifacts.pilot_log, build_pilot_log(qa_summary, failure_notes, rerun_records))

    return Phase3BPilotQAResult(
        phase3a_result=phase3a_result,
        artifacts=artifacts,
        rerun_records=rerun_records,
        failure_notes=failure_notes,
        qa_summary=qa_summary,
        rerun_record_validation=rerun_record_validation,
        failure_note_validation=failure_note_validation,
    )


def build_failure_notes(
    phase3a_result: Phase3AExperimentResult,
    results_store: FileSystemResultsStore,
) -> List[FailureNote]:
    """Build failure notes for non-passing pilot rows."""

    notes: List[FailureNote] = []
    for row, run in zip(phase3a_result.matrix.rows, phase3a_result.run_results):
        validation = phase3a_result.artifact_validations[run.trace.run_id]
        evidence_paths = list(results_store.relative_paths(run.artifact_paths.to_dict()).values())
        if not validation.passed:
            notes.append(
                _failure_note(
                    row=row,
                    run_id=run.trace.run_id,
                    failure_class="artifact_failure",
                    observed_symptom="Artifact validation failed: " + "; ".join(validation.issues),
                    root_cause="unknown",
                    dataset_decision="rerun",
                    evidence_paths=evidence_paths,
                )
            )
            continue

        if run.trace.status != "completed":
            notes.append(
                _failure_note(
                    row=row,
                    run_id=run.trace.run_id,
                    failure_class="infrastructure_failure",
                    observed_symptom=f"Run status was {run.trace.status}",
                    root_cause="unknown",
                    dataset_decision="block_freeze",
                    evidence_paths=evidence_paths,
                )
            )
            continue

        if not run.verification.passed:
            notes.append(
                _failure_note(
                    row=row,
                    run_id=run.trace.run_id,
                    failure_class="verifier_failure",
                    observed_symptom="Rule-based verification did not pass",
                    root_cause="agent_behavior",
                    dataset_decision="include",
                    evidence_paths=evidence_paths,
                )
            )
            continue

        if not run.metrics.task_success:
            notes.append(
                _failure_note(
                    row=row,
                    run_id=run.trace.run_id,
                    failure_class="task_failure",
                    observed_symptom="Task success metric is false",
                    root_cause="agent_behavior",
                    dataset_decision="include",
                    evidence_paths=evidence_paths,
                )
            )

    return notes


def build_pilot_qa_summary(
    phase3a_result: Phase3AExperimentResult,
    failure_notes: List[FailureNote],
    rerun_records: List[RerunRecord],
    rerun_record_validation: QAValidationResult,
    failure_note_validation: QAValidationResult,
    timestamp: str,
    commit_hash: str,
    experiment_config_path: Optional[Path],
    operator_notes: str,
    known_limitations: List[str],
    results_store: FileSystemResultsStore,
    artifacts: Phase3BPilotQAArtifacts,
) -> Dict[str, object]:
    """Build the machine-readable Phase 3B pilot QA summary."""

    aggregation = phase3a_result.experiment.aggregation
    unresolved_infrastructure = has_unresolved_infrastructure_failures(failure_notes)
    unresolved_qa_actions = [
        note for note in failure_notes
        if note.dataset_decision in {"rerun", "block_freeze"}
    ]
    ready_for_dataset_execution = (
        not unresolved_infrastructure
        and not unresolved_qa_actions
        and rerun_record_validation.passed
        and failure_note_validation.passed
        and aggregation["expected_run_count"] == aggregation["completed_run_count"]
        and aggregation["artifact_validation_pass_rate"] == 1.0
    )
    acceptance = {
        "pilot_log_written": True,
        "rerun_records_written": True,
        "rerun_records_valid": rerun_record_validation.passed,
        "failure_notes_written": True,
        "failure_notes_valid": failure_note_validation.passed,
        "failures_classified": failure_note_validation.passed,
        "unresolved_infrastructure_failures_block_dataset_execution": not unresolved_infrastructure,
        "pilot_states_dataset_decision": True,
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "pilot_mode": DEFAULT_PILOT_MODE,
        "experiment_id": phase3a_result.experiment.experiment_id,
        "timestamp": timestamp,
        "commit_hash": commit_hash,
        "experiment_config_path": str(experiment_config_path) if experiment_config_path is not None else None,
        "operator_notes": operator_notes,
        "known_limitations": list(known_limitations),
        "expected_run_count": aggregation["expected_run_count"],
        "completed_run_count": aggregation["completed_run_count"],
        "task_success_rate": aggregation["task_success_rate"],
        "verification_pass_rate": aggregation["verification_pass_rate"],
        "artifact_validation_pass_rate": aggregation["artifact_validation_pass_rate"],
        "failure_note_count": len(failure_notes),
        "rerun_record_count": len(rerun_records),
        "dataset_execution_blocked": unresolved_infrastructure,
        "ready_for_dataset_execution": ready_for_dataset_execution,
        "pilot_decision": "proceed_to_dataset_execution" if ready_for_dataset_execution else "revise_or_rerun_before_dataset_execution",
        "qa_acceptance_criteria": acceptance,
        "phase3a_artifacts": phase3a_result.experiment.analysis_artifacts,
        "phase3b_artifacts": {
            name: results_store.relative_path(path)
            for name, path in artifacts.to_dict().items()
        },
    }


def build_pilot_log(
    qa_summary: Mapping[str, object],
    failure_notes: List[FailureNote],
    rerun_records: List[RerunRecord],
) -> str:
    """Build the human-readable Phase 3B pilot log."""

    lines = [
        "# Phase 3B Pilot QA Log",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Experiment ID | `{qa_summary['experiment_id']}` |",
        f"| Pilot mode | `{qa_summary['pilot_mode']}` |",
        f"| Timestamp | `{qa_summary['timestamp']}` |",
        f"| Commit hash | `{qa_summary['commit_hash']}` |",
        f"| Experiment config path | `{qa_summary['experiment_config_path']}` |",
        f"| Expected runs | {qa_summary['expected_run_count']} |",
        f"| Completed runs | {qa_summary['completed_run_count']} |",
        f"| Artifact validation pass rate | {qa_summary['artifact_validation_pass_rate']:.4f} |",
        f"| Failure notes | {qa_summary['failure_note_count']} |",
        f"| Rerun records | {qa_summary['rerun_record_count']} |",
        f"| Dataset execution blocked | `{str(qa_summary['dataset_execution_blocked']).lower()}` |",
        f"| Pilot decision | `{qa_summary['pilot_decision']}` |",
        "",
        "## Known Limitations",
        "",
    ]
    limitations = qa_summary.get("known_limitations", [])
    if limitations:
        lines.extend([f"- {limitation}" for limitation in limitations])
    else:
        lines.append("- None recorded.")

    lines.extend(
        [
            "",
            "## Operator Notes",
            "",
            str(qa_summary["operator_notes"]),
            "",
            "## QA Acceptance Criteria",
            "",
            "| Criterion | Passed |",
            "|---|---|",
        ]
    )
    criteria = qa_summary["qa_acceptance_criteria"]
    if not isinstance(criteria, Mapping):
        raise ValidationError("qa_acceptance_criteria must be an object")
    for name, passed in sorted(criteria.items()):
        lines.append(f"| `{name}` | `{str(passed).lower()}` |")

    lines.extend(
        [
            "",
            "## Failure Notes",
            "",
        ]
    )
    if failure_notes:
        for note in failure_notes:
            lines.extend(
                [
                    f"### `{note.run_id}`",
                    "",
                    f"- Class: `{note.failure_class}`",
                    f"- Dataset decision: `{note.dataset_decision}`",
                    f"- Observed symptom: {note.observed_symptom}",
                    f"- Root cause: {note.root_cause}",
                    "",
                ]
            )
    else:
        lines.append("No pilot failures recorded.")

    lines.extend(
        [
            "",
            "## Rerun Records",
            "",
        ]
    )
    if rerun_records:
        for record in rerun_records:
            lines.extend(
                [
                    f"### `{record.rerun_id}`",
                    "",
                    f"- Original run ID: `{record.original_run_id}`",
                    f"- Decision: `{record.decision}`",
                    f"- Reason: {record.reason}",
                    "",
                ]
            )
    else:
        lines.append("No rerun records were required for this pilot execution.")

    lines.append("")
    return "\n".join(lines)


def write_rerun_records(path: Path, records: List[RerunRecord]) -> Path:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "record_count": len(records),
        "records": [record.to_dict() for record in records],
    }
    _write_json(path, payload)
    return path


def read_rerun_records(path: Path) -> List[RerunRecord]:
    payload = _read_json(path)
    _validate_record_set_payload(payload, "RerunRecordSet")
    return [RerunRecord.from_dict(record) for record in payload["records"]]


def validate_rerun_records(records: List[RerunRecord]) -> QAValidationResult:
    issues: List[str] = []
    seen_ids = set()
    for record in records:
        try:
            RerunRecord.from_dict(record.to_dict())
        except ValidationError as exc:
            issues.append(str(exc))
            continue
        if record.rerun_id in seen_ids:
            issues.append(f"Duplicate rerun_id: {record.rerun_id}")
        seen_ids.add(record.rerun_id)
    return QAValidationResult(passed=not issues, issues=issues)


def write_failure_notes_json(path: Path, notes: List[FailureNote]) -> Path:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "record_count": len(notes),
        "records": [note.to_dict() for note in notes],
        "templates": failure_note_templates(),
    }
    _write_json(path, payload)
    return path


def read_failure_notes(path: Path) -> List[FailureNote]:
    payload = _read_json(path)
    _validate_record_set_payload(payload, "FailureNoteSet")
    return [FailureNote.from_dict(record) for record in payload["records"]]


def validate_failure_notes(notes: List[FailureNote]) -> QAValidationResult:
    issues: List[str] = []
    for note in notes:
        try:
            FailureNote.from_dict(note.to_dict())
        except ValidationError as exc:
            issues.append(str(exc))
    return QAValidationResult(passed=not issues, issues=issues)


def write_failure_notes_markdown(path: Path, notes: List[FailureNote]) -> Path:
    _write_text(path, build_failure_notes_markdown(notes))
    return path


def build_failure_notes_markdown(notes: List[FailureNote]) -> str:
    lines = [
        "# Phase 3B Failure Notes",
        "",
        "## Recorded Failures",
        "",
    ]
    if notes:
        for note in notes:
            lines.extend(
                [
                    f"### `{note.run_id}`",
                    "",
                    f"- Component config: `{note.component_config_id}`",
                    f"- Task: `{note.task_id}`",
                    f"- Seed: `{note.seed}`",
                    f"- Perturbation schedule: `{note.perturbation_schedule_id}`",
                    f"- Failure class: `{note.failure_class}`",
                    f"- Dataset decision: `{note.dataset_decision}`",
                    f"- Observed symptom: {note.observed_symptom}",
                    f"- Root cause: {note.root_cause}",
                    "",
                ]
            )
    else:
        lines.append("No pilot failures recorded.")

    lines.extend(
        [
            "",
            "## Templates",
            "",
            "| Failure class | Default dataset decision | Purpose |",
            "|---|---|---|",
        ]
    )
    for template in failure_note_templates():
        lines.append(
            f"| `{template['failure_class']}` | `{template['dataset_decision']}` | "
            f"{template['purpose']} |"
        )
    lines.append("")
    return "\n".join(lines)


def failure_note_templates() -> List[Dict[str, str]]:
    return [
        {
            "failure_class": "task_failure",
            "dataset_decision": "include",
            "purpose": "A completed run failed the task and should normally remain as an experimental outcome.",
        },
        {
            "failure_class": "verifier_failure",
            "dataset_decision": "include",
            "purpose": "The verifier rejected the run; include if artifacts are valid and the failure is agent behavior.",
        },
        {
            "failure_class": "artifact_failure",
            "dataset_decision": "rerun",
            "purpose": "Artifact validation failed; rerun after the cause is understood.",
        },
        {
            "failure_class": "infrastructure_failure",
            "dataset_decision": "block_freeze",
            "purpose": "Infrastructure failures block dataset execution until resolved.",
        },
    ]


def has_unresolved_infrastructure_failures(notes: List[FailureNote]) -> bool:
    return any(
        note.failure_class == "infrastructure_failure"
        and note.dataset_decision == "block_freeze"
        for note in notes
    )


def validate_dataset_execution_gate(notes: List[FailureNote]) -> QAValidationResult:
    issues = [
        f"Unresolved infrastructure failure blocks dataset execution: {note.run_id}"
        for note in notes
        if note.failure_class == "infrastructure_failure"
        and note.dataset_decision == "block_freeze"
    ]
    return QAValidationResult(passed=not issues, issues=issues)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def current_commit_hash() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "unknown"
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _failure_note(
    row: ExperimentMatrixRow,
    run_id: str,
    failure_class: str,
    observed_symptom: str,
    root_cause: str,
    dataset_decision: str,
    evidence_paths: List[str],
) -> FailureNote:
    return FailureNote(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        component_config_id=row.component_config_id,
        task_id=row.task_id,
        seed=row.seed,
        perturbation_schedule_id=row.perturbation_schedule_id,
        failure_class=failure_class,
        observed_symptom=observed_symptom,
        root_cause=root_cause,
        dataset_decision=dataset_decision,
        evidence_paths=evidence_paths,
    )


def _results_store(
    config: ExperimentConfig,
    phase3a_result: Phase3AExperimentResult,
) -> FileSystemResultsStore:
    if config.artifact_root is not None:
        return FileSystemResultsStore.from_artifact_root(config.artifact_root)
    return FileSystemResultsStore.from_run_config(phase3a_result.run_results[0].run_context.run_config)


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
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValidationError(f"Invalid QA JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError(f"QA JSON artifact must contain an object: {path}")
    return payload


def _validate_record_set_payload(payload: Mapping[str, Any], model_name: str) -> None:
    _require_schema_version(payload, model_name)
    record_count = _require_int(payload, "record_count", model_name, minimum=0)
    records = _require_object_list(payload, "records", model_name)
    if record_count != len(records):
        raise ValidationError(
            f"{model_name}.record_count must match records length: expected {record_count}, found {len(records)}"
        )


def _require_mapping(data: Mapping[str, Any], model_name: str) -> Mapping[str, Any]:
    if not isinstance(data, Mapping):
        raise ValidationError(f"{model_name} must be an object")
    return data


def _no_extra(data: Mapping[str, Any], allowed: Iterable[str], model_name: str) -> None:
    extra = sorted(set(data) - set(allowed))
    if extra:
        raise ValidationError(f"{model_name} has unsupported fields: {', '.join(extra)}")


def _require(data: Mapping[str, Any], field: str, model_name: str) -> Any:
    if field not in data:
        raise ValidationError(f"{model_name}.{field} is required")
    return data[field]


def _require_schema_version(data: Mapping[str, Any], model_name: str) -> str:
    version = _require_str(data, "schema_version", model_name)
    if version != SCHEMA_VERSION:
        raise ValidationError(f"{model_name}.schema_version must be {SCHEMA_VERSION}")
    return version


def _require_str(data: Mapping[str, Any], field: str, model_name: str) -> str:
    value = _require(data, field, model_name)
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{model_name}.{field} must be a non-empty string")
    return value


def _require_int(data: Mapping[str, Any], field: str, model_name: str, minimum: Optional[int] = None) -> int:
    value = _require(data, field, model_name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{model_name}.{field} must be an integer")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{model_name}.{field} must be >= {minimum}")
    return value


def _require_str_list(data: Mapping[str, Any], field: str, model_name: str) -> List[str]:
    value = _require(data, field, model_name)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValidationError(f"{model_name}.{field} must be a list of non-empty strings")
    return list(value)


def _require_object_list(data: Mapping[str, Any], field: str, model_name: str) -> List[Dict[str, Any]]:
    value = _require(data, field, model_name)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValidationError(f"{model_name}.{field} must be a list of objects")
    return list(value)


def _require_enum(
    data: Mapping[str, Any],
    field: str,
    model_name: str,
    allowed: Iterable[str],
) -> str:
    value = _require_str(data, field, model_name)
    allowed_set = set(allowed)
    if value not in allowed_set:
        raise ValidationError(f"{model_name}.{field} must be one of: {', '.join(sorted(allowed_set))}")
    return value
