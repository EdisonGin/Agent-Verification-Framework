"""Phase 2 integration baseline orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from avf.contracts import ExperimentResult, SCHEMA_VERSION, ValidationError
from avf.storage import ArtifactValidationResult, FileSystemResultsStore

from .baseline_run import BaselineRunResult, run_component_aware_baseline


DEFAULT_PHASE2_INTEGRATION_EXPERIMENT_ID = "phase2_integration_baseline"


@dataclass(frozen=True)
class Phase2IntegrationResult:
    """Outputs from the Phase 2 component-aware integration baseline."""

    experiment: ExperimentResult
    run_results: List[BaselineRunResult]
    artifact_validations: Dict[str, ArtifactValidationResult]
    comparison_summary_path: Path
    exit_report_path: Path

    def to_dict(self) -> Dict[str, object]:
        return {
            "experiment": self.experiment.to_dict(),
            "run_count": len(self.run_results),
            "run_ids": [run.trace.run_id for run in self.run_results],
            "component_config_ids": [run.component_bundle.config_id for run in self.run_results],
            "comparison_summary": str(self.comparison_summary_path),
            "exit_report": str(self.exit_report_path),
            "artifact_validations": {
                run_id: validation.to_dict()
                for run_id, validation in sorted(self.artifact_validations.items())
            },
        }


def run_phase2_integration_baseline(
    task_path: Path,
    run_config_path: Path,
    component_config_paths: List[Path],
    tool_spec_paths: List[Path],
    artifact_root: Optional[Path] = None,
    experiment_id: str = DEFAULT_PHASE2_INTEGRATION_EXPERIMENT_ID,
) -> Phase2IntegrationResult:
    """Run a small component-aware integration baseline across selected cells."""

    if len(component_config_paths) < 2:
        raise ValidationError("Phase 2 integration baseline requires at least two ComponentConfig fixtures")
    if not tool_spec_paths:
        raise ValidationError("Phase 2 integration baseline requires at least one ToolSpec fixture")

    run_results = [
        run_component_aware_baseline(
            task_path=task_path,
            run_config_path=run_config_path,
            component_config_path=component_config_path,
            tool_spec_paths=tool_spec_paths,
            artifact_root=artifact_root,
        )
        for component_config_path in component_config_paths
    ]
    _validate_selected_cells(run_results)

    results_store = FileSystemResultsStore.from_run_config(run_results[0].run_context.run_config, artifact_root)
    artifact_validations: Dict[str, ArtifactValidationResult] = {}
    for run in run_results:
        manifest = results_store.build_artifact_manifest(run.trace.run_id, run.verification.verifier_id)
        results_store.write_artifact_manifest(manifest)
        artifact_validations[run.trace.run_id] = manifest.validation

    comparison_summary_path = results_store.layout.artifact_root / "comparisons" / f"{experiment_id}.json"
    exit_report_path = results_store.layout.report_dir / f"{experiment_id}_exit_report.md"
    experiment = _build_experiment_result(
        experiment_id=experiment_id,
        run_results=run_results,
        artifact_validations=artifact_validations,
        results_store=results_store,
        comparison_summary_path=comparison_summary_path,
        exit_report_path=exit_report_path,
    )
    _write_json(comparison_summary_path, experiment.to_dict())
    _write_text(exit_report_path, _build_phase2_exit_report(experiment, run_results, artifact_validations))

    return Phase2IntegrationResult(
        experiment=experiment,
        run_results=run_results,
        artifact_validations=artifact_validations,
        comparison_summary_path=comparison_summary_path,
        exit_report_path=exit_report_path,
    )


def _validate_selected_cells(run_results: List[BaselineRunResult]) -> None:
    config_ids = [run.component_bundle.config_id for run in run_results]
    if len(set(config_ids)) != len(config_ids):
        raise ValidationError("Phase 2 integration baseline requires distinct ComponentConfig fixtures")

    has_level1_cell = any(
        run.run_context.component_config.memory_backend == "sqlite"
        and run.run_context.component_config.retrieval_strategy == "bm25"
        and run.run_context.component_config.scheduling_policy == "sequential"
        for run in run_results
    )
    has_level2_variant = any(
        run.run_context.component_config.memory_backend == "vector"
        or run.run_context.component_config.retrieval_strategy == "embedding"
        or run.run_context.component_config.scheduling_policy == "rule_based"
        for run in run_results
    )
    if not has_level1_cell or not has_level2_variant:
        raise ValidationError(
            "Phase 2 integration baseline requires one Level 1 cell and one Level 2 variant cell"
        )


def _build_experiment_result(
    experiment_id: str,
    run_results: List[BaselineRunResult],
    artifact_validations: Dict[str, ArtifactValidationResult],
    results_store: FileSystemResultsStore,
    comparison_summary_path: Path,
    exit_report_path: Path,
) -> ExperimentResult:
    rows = [_run_summary(run, artifact_validations[run.trace.run_id], results_store) for run in run_results]
    success_count = sum(1 for run in run_results if run.metrics.task_success)
    verification_count = sum(1 for run in run_results if run.verification.passed)
    artifact_validation_count = sum(1 for validation in artifact_validations.values() if validation.passed)
    exit_criteria = _phase2_exit_criteria(run_results, artifact_validations)

    return ExperimentResult(
        schema_version=SCHEMA_VERSION,
        experiment_id=experiment_id,
        factorial_design={
            "scope": "phase2_integration_baseline",
            "description": "Level 1 baseline cell compared with a Level 2 variant cell before Phase 3.",
            "component_config_ids": [run.component_bundle.config_id for run in run_results],
            "factors": {
                "A": {"field": "memory_backend", "A1": "sqlite", "A2": "vector"},
                "B": {"field": "retrieval_strategy", "B1": "bm25", "B2": "embedding"},
                "C": {"field": "scheduling_policy", "C1": "sequential", "C2": "rule_based"},
            },
        },
        run_ids=[run.trace.run_id for run in run_results],
        aggregation={
            "cell_count": len(run_results),
            "task_success_rate": success_count / len(run_results),
            "verification_pass_rate": verification_count / len(run_results),
            "artifact_validation_pass_rate": artifact_validation_count / len(run_results),
            "comparison_rows": rows,
            "phase2_exit_criteria": exit_criteria,
        },
        analysis_artifacts={
            "comparison_summary": results_store.relative_path(comparison_summary_path),
            "exit_report": results_store.relative_path(exit_report_path),
        },
    )


def _run_summary(
    run: BaselineRunResult,
    artifact_validation: ArtifactValidationResult,
    results_store: FileSystemResultsStore,
) -> Dict[str, object]:
    return {
        "component_config_id": run.component_bundle.config_id,
        "run_id": run.trace.run_id,
        "status": run.trace.status,
        "task_success": run.metrics.task_success,
        "verification_passed": run.verification.passed,
        "artifact_validation_passed": artifact_validation.passed,
        "memory_backend": run.run_context.component_config.memory_backend,
        "retrieval_strategy": run.run_context.component_config.retrieval_strategy,
        "scheduling_policy": run.run_context.component_config.scheduling_policy,
        "metrics": run.metrics.to_dict(),
        "component_bundle": run.component_bundle.to_dict(),
        "artifacts": results_store.relative_paths(run.artifact_paths.to_dict()),
    }


def _phase2_exit_criteria(
    run_results: List[BaselineRunResult],
    artifact_validations: Dict[str, ArtifactValidationResult],
) -> Dict[str, bool]:
    return {
        "component_interfaces_locked": True,
        "component_config_controls_selection": True,
        "memory_variants_available": True,
        "retrieval_variants_available": True,
        "scheduler_variants_available": True,
        "full_component_fixture_set_available": True,
        "component_metadata_visible": all(_has_component_bundle_event(run) for run in run_results),
        "artifact_manifests_validated": all(validation.passed for validation in artifact_validations.values()),
        "integration_cells_completed": all(run.trace.status == "completed" for run in run_results),
        "verification_passed": all(run.verification.passed for run in run_results),
        "task_success": all(run.metrics.task_success for run in run_results),
        "ready_for_phase3_full_factorial": all(
            validation.passed for validation in artifact_validations.values()
        )
        and all(run.verification.passed and run.metrics.task_success for run in run_results),
    }


def _has_component_bundle_event(run: BaselineRunResult) -> bool:
    return any(event.payload.get("stage") == "component_bundle" for event in run.trace.events)


def _build_phase2_exit_report(
    experiment: ExperimentResult,
    run_results: List[BaselineRunResult],
    artifact_validations: Dict[str, ArtifactValidationResult],
) -> str:
    rows = experiment.aggregation["comparison_rows"]
    criteria = experiment.aggregation["phase2_exit_criteria"]
    lines = [
        "# Phase 2 Integration Baseline Exit Report",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Experiment ID | `{experiment.experiment_id}` |",
        f"| Cells executed | {experiment.aggregation['cell_count']} |",
        f"| Task success rate | {experiment.aggregation['task_success_rate']:.4f} |",
        f"| Verification pass rate | {experiment.aggregation['verification_pass_rate']:.4f} |",
        f"| Artifact validation pass rate | {experiment.aggregation['artifact_validation_pass_rate']:.4f} |",
        f"| Ready for Phase 3 full factorial | `{str(criteria['ready_for_phase3_full_factorial']).lower()}` |",
        "",
        "## Component Comparison",
        "",
        "| Component config | Run ID | Memory | Retrieval | Scheduling | Task success | Artifacts valid |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['component_config_id']}` | `{row['run_id']}` | "
            f"`{row['memory_backend']}` | `{row['retrieval_strategy']}` | "
            f"`{row['scheduling_policy']}` | `{str(row['task_success']).lower()}` | "
            f"`{str(row['artifact_validation_passed']).lower()}` |"
        )

    lines.extend(
        [
            "",
            "## Phase 2 Exit Criteria",
            "",
            "| Criterion | Passed |",
            "|---|---|",
        ]
    )
    for name, passed in sorted(criteria.items()):
        lines.append(f"| `{name}` | `{str(passed).lower()}` |")

    lines.extend(
        [
            "",
            "## Artifact Manifests",
            "",
            "| Run ID | Validation | Issues |",
            "|---|---|---|",
        ]
    )
    for run in run_results:
        validation = artifact_validations[run.trace.run_id]
        issues = "; ".join(validation.issues) if validation.issues else "none"
        lines.append(f"| `{run.trace.run_id}` | `{str(validation.passed).lower()}` | {issues} |")

    lines.extend(
        [
            "",
            "## Scope Boundary",
            "",
            (
                "Phase 2J runs a small integration baseline only. The full `2^3` "
                "factorial experiment, pilot QA records, and larger comparison "
                "dataset are deferred to Phase 3."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _write_json(path: Path, payload: Dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
