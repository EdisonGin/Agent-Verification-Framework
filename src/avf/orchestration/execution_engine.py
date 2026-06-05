"""Execution-engine shell for Phase 1D.

The engine currently creates a run context only. Agent execution starts in
Phase 1E, mock services in Phase 1F, and trace/result production in later
Phase 1 subphases.
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

