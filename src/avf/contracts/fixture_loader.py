"""JSON fixture loading and validation for Phase 1 contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple, Type

from .schemas import ComponentConfig, ContractModel, RunConfig, TaskCase, ToolSpec, ValidationError


FixtureSpec = Tuple[str, Type[ContractModel]]


FIXTURE_SPECS: List[FixtureSpec] = [
    ("tasks", TaskCase),
    ("configs", RunConfig),
    ("components", ComponentConfig),
    ("tool_specs", ToolSpec),
]


def load_json(path: Path) -> Dict[str, object]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise ValidationError(f"Fixture not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValidationError(f"Fixture must contain a JSON object: {path}")
    return payload


def load_fixture_dir(root: Path, relative_dir: str, model_cls: Type[ContractModel]) -> List[ContractModel]:
    directory = root / relative_dir
    if not directory.exists():
        raise ValidationError(f"Fixture directory does not exist: {directory}")
    if not directory.is_dir():
        raise ValidationError(f"Fixture path is not a directory: {directory}")

    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise ValidationError(f"No JSON fixtures found in {directory}")

    models: List[ContractModel] = []
    for path in paths:
        try:
            models.append(model_cls.from_dict(load_json(path)))
        except ValidationError as exc:
            raise ValidationError(f"{path}: {exc}") from exc
    return models


def load_fixture_tree(root: Path) -> Dict[str, List[ContractModel]]:
    return {
        relative_dir: load_fixture_dir(root, relative_dir, model_cls)
        for relative_dir, model_cls in FIXTURE_SPECS
    }


def validate_fixture_tree(root: Path) -> Dict[str, int]:
    loaded = load_fixture_tree(root)
    return {relative_dir: len(models) for relative_dir, models in loaded.items()}

