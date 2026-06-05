"""Deterministic run-context construction for Phase 1D."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, ClassVar, Dict, Iterable, List

from avf.contracts.schemas import (
    SCHEMA_VERSION,
    AgentRunInput,
    ComponentConfig,
    RunConfig,
    TaskCase,
    ToolSpec,
    ValidationError,
)

from .loaders import load_component_config, load_run_config, load_task_case, load_tool_spec


@dataclass(frozen=True)
class RunContext:
    """Validated orchestration context for one task/config/component cell."""

    schema_version: str
    run_id: str
    status: str
    task: TaskCase
    run_config: RunConfig
    component_config: ComponentConfig
    tool_specs: List[ToolSpec]
    seed: int
    perturbation_schedule_id: str
    execution_controls: Dict[str, Any]

    statuses: ClassVar[List[str]] = ["created"]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_agent_run_input(self) -> AgentRunInput:
        """Convert the context to the documented SUT input contract."""
        return AgentRunInput(
            schema_version=self.schema_version,
            run_id=self.run_id,
            task=self.task,
            run_config=self.run_config,
            component_config=self.component_config,
            tool_specs=self.tool_specs,
            execution_controls=self.execution_controls,
        )


def deterministic_run_id(
    task: TaskCase,
    run_config: RunConfig,
    component_config: ComponentConfig,
    tool_specs: Iterable[ToolSpec],
) -> str:
    """Build a stable run ID from controlled run inputs.

    The ID intentionally excludes timestamps and filesystem paths. Re-running
    the same task/config/component/tool-schema cell produces the same ID.
    """

    payload = {
        "task_id": task.task_id,
        "task_version": task.task_version,
        "run_config_id": run_config.run_config_id,
        "seed": run_config.seed,
        "perturbation_schedule_id": run_config.perturbation_schedule_id,
        "component_config_id": component_config.config_id,
        "memory_backend": component_config.memory_backend,
        "retrieval_strategy": component_config.retrieval_strategy,
        "scheduling_policy": component_config.scheduling_policy,
        "tool_specs": sorted(
            [
                {
                    "tool_name": tool.tool_name,
                    "tool_schema_version": tool.tool_schema_version,
                }
                for tool in tool_specs
            ],
            key=lambda item: item["tool_name"],
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()[:16]
    return f"run_{digest}"


def build_execution_controls(run_config: RunConfig) -> Dict[str, Any]:
    controls = dict(run_config.runtime)
    controls.setdefault("retry_policy", "none")
    controls.setdefault("logging", "full_trace")
    return controls


def validate_task_tools(task: TaskCase, tool_specs: Iterable[ToolSpec]) -> None:
    allowed = set(task.allowed_tools)
    provided = {tool.tool_name for tool in tool_specs}

    missing = sorted(allowed - provided)
    if missing:
        raise ValidationError(f"Missing required tool specs for task {task.task_id}: {', '.join(missing)}")

    undeclared = sorted(provided - allowed)
    if undeclared:
        raise ValidationError(f"Tool specs not allowed by task {task.task_id}: {', '.join(undeclared)}")


def build_run_context(
    task: TaskCase,
    run_config: RunConfig,
    component_config: ComponentConfig,
    tool_specs: List[ToolSpec],
) -> RunContext:
    if not tool_specs:
        raise ValidationError("At least one ToolSpec is required to create a RunContext")

    validate_task_tools(task, tool_specs)
    run_id = deterministic_run_id(task, run_config, component_config, tool_specs)

    return RunContext(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        status="created",
        task=task,
        run_config=run_config,
        component_config=component_config,
        tool_specs=list(tool_specs),
        seed=run_config.seed,
        perturbation_schedule_id=run_config.perturbation_schedule_id,
        execution_controls=build_execution_controls(run_config),
    )


def build_run_context_from_files(
    task_path: Path,
    run_config_path: Path,
    component_config_path: Path,
    tool_spec_paths: List[Path],
) -> RunContext:
    task = load_task_case(task_path)
    run_config = load_run_config(run_config_path)
    component_config = load_component_config(component_config_path)
    tool_specs = [load_tool_spec(path) for path in tool_spec_paths]

    return build_run_context(task, run_config, component_config, tool_specs)

