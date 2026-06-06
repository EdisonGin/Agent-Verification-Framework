"""Execution-engine shell for Phase 1D run-context creation.

Phase 1I baseline execution is implemented separately in baseline_run.py.
"""

from __future__ import annotations

from typing import List

from avf.contracts.schemas import ComponentConfig, RunConfig, TaskCase, ToolSpec

from .run_context import RunContext, build_run_context


class ExecutionEngine:
    """Minimal orchestration shell for creating validated run contexts."""

    def create_run_context(
        self,
        task: TaskCase,
        run_config: RunConfig,
        component_config: ComponentConfig,
        tool_specs: List[ToolSpec],
    ) -> RunContext:
        return build_run_context(task, run_config, component_config, tool_specs)
