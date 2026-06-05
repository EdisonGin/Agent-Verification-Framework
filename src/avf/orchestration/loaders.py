"""Fixture loaders used by the Phase 1D orchestrator."""

from __future__ import annotations

from pathlib import Path

from avf.contracts.fixture_loader import load_json
from avf.contracts.schemas import ComponentConfig, RunConfig, TaskCase, ToolSpec


def load_task_case(path: Path) -> TaskCase:
    return TaskCase.from_dict(load_json(path))


def load_run_config(path: Path) -> RunConfig:
    return RunConfig.from_dict(load_json(path))


def load_component_config(path: Path) -> ComponentConfig:
    return ComponentConfig.from_dict(load_json(path))


def load_tool_spec(path: Path) -> ToolSpec:
    return ToolSpec.from_dict(load_json(path))

