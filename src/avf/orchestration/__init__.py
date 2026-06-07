"""Orchestration layer."""

from .execution_engine import ExecutionEngine
from .loaders import load_component_config, load_run_config, load_task_case, load_tool_spec
from .run_context import RunContext, build_run_context, build_run_context_from_files, deterministic_run_id

__all__ = [
    "BaselineRunArtifactPaths",
    "BaselineRunResult",
    "ExecutionEngine",
    "Phase2IntegrationResult",
    "RunContext",
    "build_run_context",
    "build_run_context_from_files",
    "run_phase2_integration_baseline",
    "run_component_aware_baseline",
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
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
