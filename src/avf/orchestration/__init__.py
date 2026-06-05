"""Orchestration layer.

Phase 1D implements deterministic run-context creation only. It does not execute
the SUT agent, mock services, verification, metrics, or reporting.
"""

from .execution_engine import ExecutionEngine
from .loaders import load_component_config, load_run_config, load_task_case, load_tool_spec
from .run_context import RunContext, build_run_context, build_run_context_from_files, deterministic_run_id

__all__ = [
    "ExecutionEngine",
    "RunContext",
    "build_run_context",
    "build_run_context_from_files",
    "deterministic_run_id",
    "load_component_config",
    "load_run_config",
    "load_task_case",
    "load_tool_spec",
]
