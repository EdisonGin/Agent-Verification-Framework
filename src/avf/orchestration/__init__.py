"""Orchestration layer."""

from .execution_engine import ExecutionEngine
from .loaders import load_component_config, load_run_config, load_task_case, load_tool_spec
from .run_context import RunContext, build_run_context, build_run_context_from_files, deterministic_run_id

__all__ = [
    "BaselineRunArtifactPaths",
    "BaselineRunResult",
    "ExecutionEngine",
    "ExperimentConfig",
    "ExperimentMatrix",
    "ExperimentMatrixRow",
    "FailureNote",
    "Phase2IntegrationResult",
    "Phase3AExperimentResult",
    "Phase3BPilotQAResult",
    "QAValidationResult",
    "RerunRecord",
    "RunContext",
    "build_failure_notes",
    "build_run_context",
    "build_run_context_from_files",
    "build_experiment_matrix",
    "has_unresolved_infrastructure_failures",
    "load_experiment_config",
    "read_failure_notes",
    "read_rerun_records",
    "run_phase3b_pilot_qa",
    "run_phase3a_full_factorial",
    "run_phase2_integration_baseline",
    "run_component_aware_baseline",
    "validate_dataset_execution_gate",
    "validate_failure_notes",
    "validate_rerun_records",
    "write_failure_notes_json",
    "write_rerun_records",
    "deterministic_run_id",
    "load_component_config",
    "load_run_config",
    "load_task_case",
    "load_tool_spec",
    "run_phase1_baseline",
]


def __getattr__(name: str) -> object:
    if name in {
        "BaselineRunArtifactPaths",
        "BaselineRunResult",
        "run_component_aware_baseline",
        "run_phase1_baseline",
    }:
        from . import baseline_run

        return getattr(baseline_run, name)
    if name in {"Phase2IntegrationResult", "run_phase2_integration_baseline"}:
        from . import phase2_integration

        return getattr(phase2_integration, name)
    if name in {
        "ExperimentConfig",
        "ExperimentMatrix",
        "ExperimentMatrixRow",
        "Phase3AExperimentResult",
        "build_experiment_matrix",
        "load_experiment_config",
        "run_phase3a_full_factorial",
    }:
        from . import experiment_matrix

        return getattr(experiment_matrix, name)
    if name in {
        "FailureNote",
        "Phase3BPilotQAResult",
        "QAValidationResult",
        "RerunRecord",
        "build_failure_notes",
        "has_unresolved_infrastructure_failures",
        "read_failure_notes",
        "read_rerun_records",
        "run_phase3b_pilot_qa",
        "validate_dataset_execution_gate",
        "validate_failure_notes",
        "validate_rerun_records",
        "write_failure_notes_json",
        "write_rerun_records",
    }:
        from . import pilot_qa

        return getattr(pilot_qa, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
