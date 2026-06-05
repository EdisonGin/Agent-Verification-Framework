"""Command line interface for framework setup and fixture validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Optional

from avf.contracts import ValidationError
from avf.contracts.fixture_loader import validate_fixture_tree
from avf.orchestration import build_run_context_from_files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="avf")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate-fixtures",
        help="Validate JSON fixtures under the test_data directory.",
    )
    validate.add_argument(
        "--root",
        default="test_data",
        help="Fixture root directory. Defaults to test_data.",
    )

    create_context = subparsers.add_parser(
        "create-run-context",
        help="Create a deterministic Phase 1D run context from fixture files.",
    )
    create_context.add_argument("--task", required=True, help="Path to a TaskCase JSON fixture.")
    create_context.add_argument("--config", required=True, help="Path to a RunConfig JSON fixture.")
    create_context.add_argument(
        "--components",
        required=True,
        help="Path to a ComponentConfig JSON fixture.",
    )
    create_context.add_argument(
        "--tool-spec",
        action="append",
        required=True,
        help="Path to a ToolSpec JSON fixture. May be supplied more than once.",
    )

    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "validate-fixtures":
        try:
            summary = validate_fixture_tree(Path(args.root))
        except ValidationError as exc:
            print(f"Fixture validation failed: {exc}", file=sys.stderr)
            return 1

        print("Validated fixtures:")
        for name in sorted(summary):
            print(f"  {name}: {summary[name]}")
        return 0

    if args.command == "create-run-context":
        try:
            context = build_run_context_from_files(
                task_path=Path(args.task),
                run_config_path=Path(args.config),
                component_config_path=Path(args.components),
                tool_spec_paths=[Path(path) for path in args.tool_spec],
            )
        except ValidationError as exc:
            print(f"Run context creation failed: {exc}", file=sys.stderr)
            return 1

        print(json.dumps(context.to_dict(), indent=2, sort_keys=True))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
