"""Command line interface for framework setup and fixture validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Optional

from avf.contracts import ValidationError
from avf.contracts.fixture_loader import validate_fixture_tree


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

    parser.error(f"Unknown command: {args.command}")
    return 2

