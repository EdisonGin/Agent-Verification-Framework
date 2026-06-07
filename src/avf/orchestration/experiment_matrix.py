"""Phase 3A experiment matrix and full factorial runner."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from itertools import product
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from avf.contracts import (
    ComponentConfig,
    ExperimentResult,
    RunConfig,
    SCHEMA_VERSION,
    TaskCase,
    ToolSpec,
    ValidationError,
)
from avf.contracts.fixture_loader import load_json
from avf.storage import ArtifactValidationResult, FileSystemResultsStore

from .baseline_run import BaselineRunResult, run_component_aware_baseline
from .loaders import load_component_config, load_run_config, load_task_case, load_tool_spec
from .run_context import build_run_context


DEFAULT_PHASE3A_EXPERIMENT_ID = "phase3_full_factorial_v1"

FACTORIAL_COMPONENT_CELLS: Dict[str, Dict[str, str]] = {
    "A1_B1_C1": {
        "memory_backend": "sqlite",
        "retrieval_strategy": "bm25",
        "scheduling_policy": "sequential",
    },
    "A1_B1_C2": {
        "memory_backend": "sqlite",
        "retrieval_strategy": "bm25",
        "scheduling_policy": "rule_based",
    },
    "A1_B2_C1": {
        "memory_backend": "sqlite",
        "retrieval_strategy": "embedding",
        "scheduling_policy": "sequential",
    },
    "A1_B2_C2": {
        "memory_backend": "sqlite",
        "retrieval_strategy": "embedding",
        "scheduling_policy": "rule_based",
    },
    "A2_B1_C1": {
        "memory_backend": "vector",
        "retrieval_strategy": "bm25",
        "scheduling_policy": "sequential",
    },
    "A2_B1_C2": {
        "memory_backend": "vector",
        "retrieval_strategy": "bm25",
        "scheduling_policy": "rule_based",
    },
    "A2_B2_C1": {
        "memory_backend": "vector",
        "retrieval_strategy": "embedding",
        "scheduling_policy": "sequential",
    },
    "A2_B2_C2": {
        "memory_backend": "vector",
        "retrieval_strategy": "embedding",
        "scheduling_policy": "rule_based",
    },
}


@dataclass(frozen=True)
class ExperimentConfig:
    """Versioned experiment configuration for Phase 3A matrix execution."""

    schema_version: str
    experiment_id: str
    task_fixtures: List[Path]
    run_config_fixtures: List[Path]
    component_fixtures: List[Path]
    tool_spec_fixtures: List[Path]
    perturbation_schedules: List[str]
    execution_policy: Dict[str, Any]
    artifact_root: Optional[Path]
    dataset_policy: Dict[str, Any]

    fields = [
        "schema_version",
        "experiment_id",
        "task_fixtures",
        "run_config_fixtures",
        "component_fixtures",
        "tool_spec_fixtures",
        "perturbation_schedules",
        "execution_policy",
        "artifact_root",
        "dataset_policy",
    ]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], base_dir: Optional[Path] = None) -> "ExperimentConfig":
        data = _require_mapping(data, cls.__name__)
        _no_extra(data, cls.fields, cls.__name__)
        artifact_root = _optional_path(data, "artifact_root", cls.__name__, base_dir=None)
        return cls(
            schema_version=_require_schema_version(data, cls.__name__),
            experiment_id=_require_str(data, "experiment_id", cls.__name__),
            task_fixtures=_require_path_list(data, "task_fixtures", cls.__name__, base_dir),
            run_config_fixtures=_require_path_list(data, "run_config_fixtures", cls.__name__, base_dir),
            component_fixtures=_require_path_list(data, "component_fixtures", cls.__name__, base_dir),
            tool_spec_fixtures=_require_path_list(data, "tool_spec_fixtures", cls.__name__, base_dir),
            perturbation_schedules=_require_str_list(data, "perturbation_schedules", cls.__name__),
            execution_policy=_require_object(data, "execution_policy", cls.__name__),
            artifact_root=artifact_root,
            dataset_policy=_require_object(data, "dataset_policy", cls.__name__),
        )

    def with_overrides(
        self,
        experiment_id: Optional[str] = None,
        artifact_root: Optional[Path] = None,
    ) -> "ExperimentConfig":
        updates: Dict[str, object] = {}
        if experiment_id is not None:
            updates["experiment_id"] = experiment_id
        if artifact_root is not None:
            updates["artifact_root"] = Path(artifact_root)
        return replace(self, **updates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "task_fixtures": _path_strings(self.task_fixtures),
            "run_config_fixtures": _path_strings(self.run_config_fixtures),
            "component_fixtures": _path_strings(self.component_fixtures),
            "tool_spec_fixtures": _path_strings(self.tool_spec_fixtures),
            "perturbation_schedules": list(self.perturbation_schedules),
            "execution_policy": dict(self.execution_policy),
            "artifact_root": str(self.artifact_root) if self.artifact_root is not None else None,
            "dataset_policy": dict(self.dataset_policy),
        }


@dataclass(frozen=True)
class ExperimentMatrixRow:
    """One concrete task/run-config/component/tool-schema cell."""

    row_id: str
    task_fixture: Path
    run_config_fixture: Path
    component_fixture: Path
    tool_spec_fixtures: List[Path]
    task_id: str
    task_version: str
    run_config_id: str
    seed: int
    perturbation_schedule_id: str
    component_config_id: str
    memory_backend: str
    retrieval_strategy: str
    scheduling_policy: str
    tool_names: List[str]
    tool_schema_versions: Dict[str, str]
    expected_run_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row_id": self.row_id,
            "task_fixture": str(self.task_fixture),
            "run_config_fixture": str(self.run_config_fixture),
            "component_fixture": str(self.component_fixture),
            "tool_spec_fixtures": _path_strings(self.tool_spec_fixtures),
            "task_id": self.task_id,
            "task_version": self.task_version,
            "run_config_id": self.run_config_id,
            "seed": self.seed,
            "perturbation_schedule_id": self.perturbation_schedule_id,
            "component_config_id": self.component_config_id,
            "memory_backend": self.memory_backend,
            "retrieval_strategy": self.retrieval_strategy,
            "scheduling_policy": self.scheduling_policy,
            "tool_names": list(self.tool_names),
            "tool_schema_versions": dict(self.tool_schema_versions),
            "expected_run_id": self.expected_run_id,
        }


@dataclass(frozen=True)
class ExperimentMatrix:
    """Resolved experiment matrix for a Phase 3A run."""

    schema_version: str
    experiment_id: str
    row_count: int
    rows: List[ExperimentMatrixRow]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "row_count": self.row_count,
            "rows": [row.to_dict() for row in self.rows],
        }


@dataclass(frozen=True)
class Phase3AExperimentArtifacts:
    """Experiment-level artifacts produced by the Phase 3A runner."""

    experiment_config: Path
    matrix: Path
    run_index: Path
    comparison_summary: Path
    experiment_report: Path

    def to_dict(self) -> Dict[str, str]:
        return {
            "experiment_config": str(self.experiment_config),
            "matrix": str(self.matrix),
            "run_index": str(self.run_index),
            "comparison_summary": str(self.comparison_summary),
            "experiment_report": str(self.experiment_report),
        }


@dataclass(frozen=True)
class Phase3AExperimentResult:
    """Outputs from the Phase 3A full factorial experiment runner."""

    config: ExperimentConfig
    matrix: ExperimentMatrix
    experiment: ExperimentResult
    run_results: List[BaselineRunResult]
    artifact_validations: Dict[str, ArtifactValidationResult]
    artifacts: Phase3AExperimentArtifacts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "matrix": self.matrix.to_dict(),
            "experiment": self.experiment.to_dict(),
            "run_count": len(self.run_results),
            "run_ids": [run.trace.run_id for run in self.run_results],
            "component_config_ids": [run.component_bundle.config_id for run in self.run_results],
            "artifacts": self.artifacts.to_dict(),
            "artifact_validations": {
                run_id: validation.to_dict()
                for run_id, validation in sorted(self.artifact_validations.items())
            },
        }


def load_experiment_config(path: Path) -> ExperimentConfig:
    """Load a Phase 3A experiment config from JSON."""

    config_path = Path(path)
    return ExperimentConfig.from_dict(load_json(config_path), base_dir=config_path.parent)


def build_experiment_matrix(config: ExperimentConfig) -> ExperimentMatrix:
    """Resolve the full factorial matrix from an experiment configuration."""

    if not config.task_fixtures:
        raise ValidationError("ExperimentConfig.task_fixtures must contain at least one TaskCase fixture")
    if not config.run_config_fixtures:
        raise ValidationError("ExperimentConfig.run_config_fixtures must contain at least one RunConfig fixture")
    if not config.component_fixtures:
        raise ValidationError("ExperimentConfig.component_fixtures must contain at least one ComponentConfig fixture")
    if not config.tool_spec_fixtures:
        raise ValidationError("ExperimentConfig.tool_spec_fixtures must contain at least one ToolSpec fixture")

    tasks = [(path, load_task_case(path)) for path in config.task_fixtures]
    run_configs = [(path, load_run_config(path)) for path in config.run_config_fixtures]
    components = [(path, load_component_config(path)) for path in config.component_fixtures]
    tool_specs = [(path, load_tool_spec(path)) for path in config.tool_spec_fixtures]

    _validate_perturbation_schedules(config.perturbation_schedules, [run_config for _, run_config in run_configs])
    if config.execution_policy.get("require_full_factorial", True):
        _validate_full_factorial_components([component for _, component in components])

    rows: List[ExperimentMatrixRow] = []
    for index, ((task_path, task), (run_config_path, run_config), (component_path, component)) in enumerate(
        product(tasks, run_configs, components),
        start=1,
    ):
        ordered_tool_specs = [tool for _, tool in tool_specs]
        context = build_run_context(task, run_config, component, ordered_tool_specs)
        rows.append(
            _matrix_row(
                row_id=f"row_{index:03d}",
                task_path=task_path,
                task=task,
                run_config_path=run_config_path,
                run_config=run_config,
                component_path=component_path,
                component=component,
                tool_specs=tool_specs,
                expected_run_id=context.run_id,
            )
        )

    return ExperimentMatrix(
        schema_version=SCHEMA_VERSION,
        experiment_id=config.experiment_id,
        row_count=len(rows),
        rows=rows,
    )


def run_phase3a_full_factorial(config: ExperimentConfig) -> Phase3AExperimentResult:
    """Execute every row in the Phase 3A experiment matrix and write indexes."""

    matrix = build_experiment_matrix(config)
    artifact_root = config.artifact_root

    run_results = [
        run_component_aware_baseline(
            task_path=row.task_fixture,
            run_config_path=row.run_config_fixture,
            component_config_path=row.component_fixture,
            tool_spec_paths=row.tool_spec_fixtures,
            artifact_root=artifact_root,
        )
        for row in matrix.rows
    ]
    _validate_run_identity(matrix.rows, run_results)

    results_store = _results_store(config, run_results)
    artifact_validations: Dict[str, ArtifactValidationResult] = {}
    for run in run_results:
        manifest = results_store.build_artifact_manifest(run.trace.run_id, run.verification.verifier_id)
        results_store.write_artifact_manifest(manifest)
        artifact_validations[run.trace.run_id] = manifest.validation

    experiment_dir = results_store.layout.artifact_root / "experiments" / config.experiment_id
    comparison_summary_path = results_store.layout.artifact_root / "comparisons" / f"{config.experiment_id}.json"
    experiment_report_path = results_store.layout.report_dir / f"{config.experiment_id}_full_factorial_report.md"
    artifacts = Phase3AExperimentArtifacts(
        experiment_config=experiment_dir / "experiment_config.json",
        matrix=experiment_dir / "matrix.json",
        run_index=experiment_dir / "run_index.json",
        comparison_summary=comparison_summary_path,
        experiment_report=experiment_report_path,
    )

    run_index = _build_run_index(matrix.rows, run_results, artifact_validations, results_store)
    experiment = _build_experiment_result(
        config=config,
        matrix=matrix,
        run_results=run_results,
        artifact_validations=artifact_validations,
        results_store=results_store,
        artifacts=artifacts,
        run_index=run_index,
    )

    _write_json(artifacts.experiment_config, config.to_dict())
    _write_json(artifacts.matrix, matrix.to_dict())
    _write_json(artifacts.run_index, run_index)
    _write_json(artifacts.comparison_summary, experiment.to_dict())
    _write_text(
        artifacts.experiment_report,
        _build_phase3a_report(experiment, matrix.rows, run_results, artifact_validations),
    )

    return Phase3AExperimentResult(
        config=config,
        matrix=matrix,
        experiment=experiment,
        run_results=run_results,
        artifact_validations=artifact_validations,
        artifacts=artifacts,
    )


def _matrix_row(
    row_id: str,
    task_path: Path,
    task: TaskCase,
    run_config_path: Path,
    run_config: RunConfig,
    component_path: Path,
    component: ComponentConfig,
    tool_specs: Sequence[tuple[Path, ToolSpec]],
    expected_run_id: str,
) -> ExperimentMatrixRow:
    return ExperimentMatrixRow(
        row_id=row_id,
        task_fixture=task_path,
        run_config_fixture=run_config_path,
        component_fixture=component_path,
        tool_spec_fixtures=[path for path, _ in tool_specs],
        task_id=task.task_id,
        task_version=task.task_version,
        run_config_id=run_config.run_config_id,
        seed=run_config.seed,
        perturbation_schedule_id=run_config.perturbation_schedule_id,
        component_config_id=component.config_id,
        memory_backend=component.memory_backend,
        retrieval_strategy=component.retrieval_strategy,
        scheduling_policy=component.scheduling_policy,
        tool_names=[tool.tool_name for _, tool in tool_specs],
        tool_schema_versions={
            tool.tool_name: tool.tool_schema_version
            for _, tool in tool_specs
        },
        expected_run_id=expected_run_id,
    )


def _validate_perturbation_schedules(schedule_ids: List[str], run_configs: Iterable[RunConfig]) -> None:
    declared = set(schedule_ids)
    for run_config in run_configs:
        if run_config.perturbation_schedule_id not in declared:
            raise ValidationError(
                "RunConfig "
                f"{run_config.run_config_id} uses undeclared perturbation schedule "
                f"{run_config.perturbation_schedule_id}"
            )


def _validate_full_factorial_components(components: List[ComponentConfig]) -> None:
    observed_ids = [component.config_id for component in components]
    if len(set(observed_ids)) != len(observed_ids):
        raise ValidationError("ExperimentConfig.component_fixtures contains duplicate ComponentConfig IDs")

    expected_ids = sorted(FACTORIAL_COMPONENT_CELLS)
    if sorted(observed_ids) != expected_ids:
        raise ValidationError(
            "Phase 3A requires the complete 2^3 component fixture set: "
            + ", ".join(expected_ids)
        )

    for component in components:
        expected = FACTORIAL_COMPONENT_CELLS[component.config_id]
        observed = {
            "memory_backend": component.memory_backend,
            "retrieval_strategy": component.retrieval_strategy,
            "scheduling_policy": component.scheduling_policy,
        }
        if observed != expected:
            raise ValidationError(
                f"ComponentConfig {component.config_id} does not match documented factor coding"
            )


def _validate_run_identity(rows: List[ExperimentMatrixRow], run_results: List[BaselineRunResult]) -> None:
    if len(rows) != len(run_results):
        raise ValidationError("Experiment matrix row count does not match completed run count")
    for row, run in zip(rows, run_results):
        if run.trace.run_id != row.expected_run_id:
            raise ValidationError(
                f"Run identity mismatch for {row.row_id}: expected {row.expected_run_id}, got {run.trace.run_id}"
            )
        if run.component_bundle.config_id != row.component_config_id:
            raise ValidationError(
                f"Component identity mismatch for {row.row_id}: expected {row.component_config_id}, "
                f"got {run.component_bundle.config_id}"
            )


def _results_store(config: ExperimentConfig, run_results: List[BaselineRunResult]) -> FileSystemResultsStore:
    if config.artifact_root is not None:
        return FileSystemResultsStore.from_artifact_root(config.artifact_root)
    if not run_results:
        raise ValidationError("Cannot create a results store for an empty experiment")
    return FileSystemResultsStore.from_run_config(run_results[0].run_context.run_config)


def _build_run_index(
    rows: List[ExperimentMatrixRow],
    run_results: List[BaselineRunResult],
    artifact_validations: Mapping[str, ArtifactValidationResult],
    results_store: FileSystemResultsStore,
) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []
    for row, run in zip(rows, run_results):
        validation = artifact_validations[run.trace.run_id]
        records.append(
            {
                "row_id": row.row_id,
                "run_id": run.trace.run_id,
                "task_id": row.task_id,
                "task_version": row.task_version,
                "run_config_id": row.run_config_id,
                "seed": row.seed,
                "perturbation_schedule_id": row.perturbation_schedule_id,
                "component_config_id": row.component_config_id,
                "memory_backend": row.memory_backend,
                "retrieval_strategy": row.retrieval_strategy,
                "scheduling_policy": row.scheduling_policy,
                "tool_names": list(row.tool_names),
                "status": run.trace.status,
                "task_success": run.metrics.task_success,
                "verification_passed": run.verification.passed,
                "artifact_validation_passed": validation.passed,
                "artifact_validation_issues": list(validation.issues),
                "artifacts": results_store.relative_paths(run.artifact_paths.to_dict()),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "record_count": len(records),
        "records": records,
    }


def _build_experiment_result(
    config: ExperimentConfig,
    matrix: ExperimentMatrix,
    run_results: List[BaselineRunResult],
    artifact_validations: Mapping[str, ArtifactValidationResult],
    results_store: FileSystemResultsStore,
    artifacts: Phase3AExperimentArtifacts,
    run_index: Mapping[str, Any],
) -> ExperimentResult:
    expected_run_count = matrix.row_count
    completed_run_count = sum(1 for run in run_results if run.trace.status == "completed")
    success_count = sum(1 for run in run_results if run.metrics.task_success)
    verification_count = sum(1 for run in run_results if run.verification.passed)
    artifact_validation_count = sum(1 for validation in artifact_validations.values() if validation.passed)
    expected_vs_completed_recorded = expected_run_count == matrix.row_count and completed_run_count <= expected_run_count
    acceptance = _phase3a_acceptance_criteria(
        matrix,
        run_results,
        artifact_validations,
        expected_vs_completed_recorded,
    )

    return ExperimentResult(
        schema_version=SCHEMA_VERSION,
        experiment_id=config.experiment_id,
        factorial_design={
            "scope": "phase3a_full_factorial",
            "description": "Initial Phase 3 full factorial execution over the 2^3 component matrix.",
            "task_ids": sorted({row.task_id for row in matrix.rows}),
            "run_config_ids": sorted({row.run_config_id for row in matrix.rows}),
            "seeds": sorted({row.seed for row in matrix.rows}),
            "perturbation_schedule_ids": sorted({row.perturbation_schedule_id for row in matrix.rows}),
            "component_config_ids": [row.component_config_id for row in matrix.rows],
            "tool_names": sorted({tool_name for row in matrix.rows for tool_name in row.tool_names}),
            "factors": {
                "A": {"field": "memory_backend", "A1": "sqlite", "A2": "vector"},
                "B": {"field": "retrieval_strategy", "B1": "bm25", "B2": "embedding"},
                "C": {"field": "scheduling_policy", "C1": "sequential", "C2": "rule_based"},
            },
        },
        run_ids=[run.trace.run_id for run in run_results],
        aggregation={
            "expected_run_count": expected_run_count,
            "completed_run_count": completed_run_count,
            "matrix_row_count": matrix.row_count,
            "task_count": len({row.task_id for row in matrix.rows}),
            "run_config_count": len({row.run_config_id for row in matrix.rows}),
            "seed_count": len({row.seed for row in matrix.rows}),
            "perturbation_schedule_count": len({row.perturbation_schedule_id for row in matrix.rows}),
            "component_cell_count": len({row.component_config_id for row in matrix.rows}),
            "task_success_rate": _rate(success_count, expected_run_count),
            "verification_pass_rate": _rate(verification_count, expected_run_count),
            "artifact_validation_pass_rate": _rate(artifact_validation_count, expected_run_count),
            "run_index": run_index,
            "phase3a_acceptance_criteria": acceptance,
        },
        analysis_artifacts={
            "experiment_config": results_store.relative_path(artifacts.experiment_config),
            "matrix": results_store.relative_path(artifacts.matrix),
            "run_index": results_store.relative_path(artifacts.run_index),
            "comparison_summary": results_store.relative_path(artifacts.comparison_summary),
            "experiment_report": results_store.relative_path(artifacts.experiment_report),
        },
    )


def _phase3a_acceptance_criteria(
    matrix: ExperimentMatrix,
    run_results: List[BaselineRunResult],
    artifact_validations: Mapping[str, ArtifactValidationResult],
    expected_vs_completed_recorded: bool,
) -> Dict[str, bool]:
    expected_component_ids = sorted(FACTORIAL_COMPONENT_CELLS)
    observed_component_ids = sorted({row.component_config_id for row in matrix.rows})
    matrix_rows_complete = all(
        row.task_id
        and row.run_config_id
        and row.component_config_id
        and row.seed is not None
        and row.perturbation_schedule_id
        and row.tool_names
        for row in matrix.rows
    )
    per_run_artifacts_written = all(
        run.artifact_paths.trace.exists()
        and run.artifact_paths.verification.exists()
        and run.artifact_paths.metrics.exists()
        and run.artifact_paths.report.exists()
        and run.artifact_paths.manifest.exists()
        for run in run_results
    )

    return {
        "all_eight_component_cells_included": observed_component_ids == expected_component_ids,
        "matrix_rows_include_required_references": matrix_rows_complete,
        "current_matrix_completed_end_to_end": matrix.row_count == len(run_results)
        and all(run.trace.status == "completed" for run in run_results),
        "per_run_artifacts_written": per_run_artifacts_written,
        "per_run_artifact_manifests_valid": all(validation.passed for validation in artifact_validations.values()),
        "experiment_summary_records_expected_vs_completed": expected_vs_completed_recorded,
        "ready_for_phase3b_pilot_qa": observed_component_ids == expected_component_ids
        and matrix_rows_complete
        and per_run_artifacts_written
        and all(validation.passed for validation in artifact_validations.values())
        and all(run.verification.passed and run.metrics.task_success for run in run_results),
    }


def _build_phase3a_report(
    experiment: ExperimentResult,
    rows: List[ExperimentMatrixRow],
    run_results: List[BaselineRunResult],
    artifact_validations: Mapping[str, ArtifactValidationResult],
) -> str:
    aggregation = experiment.aggregation
    acceptance = aggregation["phase3a_acceptance_criteria"]
    run_by_id = {run.trace.run_id: run for run in run_results}
    lines = [
        "# Phase 3A Full Factorial Experiment Report",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Experiment ID | `{experiment.experiment_id}` |",
        f"| Expected runs | {aggregation['expected_run_count']} |",
        f"| Completed runs | {aggregation['completed_run_count']} |",
        f"| Component cells | {aggregation['component_cell_count']} |",
        f"| Task success rate | {aggregation['task_success_rate']:.4f} |",
        f"| Verification pass rate | {aggregation['verification_pass_rate']:.4f} |",
        f"| Artifact validation pass rate | {aggregation['artifact_validation_pass_rate']:.4f} |",
        f"| Ready for Phase 3B pilot QA | `{str(acceptance['ready_for_phase3b_pilot_qa']).lower()}` |",
        "",
        "## Matrix Rows",
        "",
        "| Row | Component | Memory | Retrieval | Scheduling | Run ID | Task success | Artifacts valid |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        run = run_by_id[row.expected_run_id]
        validation = artifact_validations[run.trace.run_id]
        lines.append(
            f"| `{row.row_id}` | `{row.component_config_id}` | `{row.memory_backend}` | "
            f"`{row.retrieval_strategy}` | `{row.scheduling_policy}` | `{run.trace.run_id}` | "
            f"`{str(run.metrics.task_success).lower()}` | `{str(validation.passed).lower()}` |"
        )

    lines.extend(
        [
            "",
            "## Acceptance Criteria",
            "",
            "| Criterion | Passed |",
            "|---|---|",
        ]
    )
    for name, passed in sorted(acceptance.items()):
        lines.append(f"| `{name}` | `{str(passed).lower()}` |")

    lines.extend(
        [
            "",
            "## Artifact Index",
            "",
            "| Artifact | Relative path |",
            "|---|---|",
        ]
    )
    for name, path in sorted(experiment.analysis_artifacts.items()):
        lines.append(f"| `{name}` | `{path}` |")

    lines.extend(
        [
            "",
            "This Phase 3A run executes the initial one-task, one-seed, one-schedule, eight-component matrix. "
            "Pilot QA, rerun records, failure notes, and dataset freezing are intentionally deferred to later "
            "Phase 3 subphases.",
            "",
        ]
    )
    return "\n".join(lines)


def _rate(count: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return count / denominator


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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


def _require_str_list(data: Mapping[str, Any], field: str, model_name: str) -> List[str]:
    value = _require(data, field, model_name)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValidationError(f"{model_name}.{field} must be a list of non-empty strings")
    return list(value)


def _require_object(data: Mapping[str, Any], field: str, model_name: str) -> Dict[str, Any]:
    value = _require(data, field, model_name)
    if not isinstance(value, dict):
        raise ValidationError(f"{model_name}.{field} must be an object")
    return dict(value)


def _require_path_list(
    data: Mapping[str, Any],
    field: str,
    model_name: str,
    base_dir: Optional[Path],
) -> List[Path]:
    values = _require_str_list(data, field, model_name)
    return [_resolve_path(Path(value), base_dir) for value in values]


def _optional_path(
    data: Mapping[str, Any],
    field: str,
    model_name: str,
    base_dir: Optional[Path],
) -> Optional[Path]:
    value = _require(data, field, model_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{model_name}.{field} must be a non-empty string or null")
    return _resolve_path(Path(value), base_dir)


def _resolve_path(path: Path, base_dir: Optional[Path]) -> Path:
    if path.is_absolute() or base_dir is None:
        return path
    return (base_dir / path).resolve()


def _path_strings(paths: Iterable[Path]) -> List[str]:
    return [str(path) for path in paths]
