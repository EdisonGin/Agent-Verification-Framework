"""Filesystem-backed test data repository for Phase 2A."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from avf.contracts import ComponentConfig, RunConfig, TaskCase, ToolSpec
from avf.contracts.fixture_loader import load_fixture_tree, validate_fixture_tree
from avf.orchestration.loaders import load_component_config, load_run_config, load_task_case, load_tool_spec


class FileSystemTestDataRepository:
    """Load versioned test fixtures from the current JSON fixture repository."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def task_path(self, filename: str) -> Path:
        return self.root / "tasks" / filename

    def run_config_path(self, filename: str) -> Path:
        return self.root / "configs" / filename

    def component_config_path(self, filename: str) -> Path:
        return self.root / "components" / filename

    def tool_spec_path(self, filename: str) -> Path:
        return self.root / "tool_specs" / filename

    def load_task_case(self, filename: str) -> TaskCase:
        return load_task_case(self.task_path(filename))

    def load_run_config(self, filename: str) -> RunConfig:
        return load_run_config(self.run_config_path(filename))

    def load_component_config(self, filename: str) -> ComponentConfig:
        return load_component_config(self.component_config_path(filename))

    def load_tool_spec(self, filename: str) -> ToolSpec:
        return load_tool_spec(self.tool_spec_path(filename))

    def load_tool_specs(self, filenames: List[str]) -> List[ToolSpec]:
        return [self.load_tool_spec(filename) for filename in filenames]

    def load_tree(self) -> Dict[str, List[object]]:
        return load_fixture_tree(self.root)

    def validate(self) -> Dict[str, int]:
        return validate_fixture_tree(self.root)
