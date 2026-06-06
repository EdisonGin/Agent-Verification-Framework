"""Command line interface for framework setup and fixture validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, Optional

from avf.contracts import TaskCase, ValidationError
from avf.contracts.fixture_loader import load_json, validate_fixture_tree
from avf.orchestration import BaselineRunResult, build_run_context_from_files, run_phase1_baseline
from avf.tracing import read_run_trace
from avf.verification import RuleBasedVerifier, VerificationResultWriter


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

    verify_trace = subparsers.add_parser(
        "verify-trace",
        help="Verify a RunTrace JSON artifact against a TaskCase fixture.",
    )
    verify_trace.add_argument("--task", required=True, help="Path to a TaskCase JSON fixture.")
    verify_trace.add_argument("--trace", required=True, help="Path to a RunTrace JSON artifact.")
    artifact_destination = verify_trace.add_mutually_exclusive_group()
    artifact_destination.add_argument(
        "--result-dir",
        help="Directory where the VerificationResult JSON artifact should be written.",
    )
    artifact_destination.add_argument(
        "--output",
        help="Exact path where the VerificationResult JSON artifact should be written.",
    )

    run_baseline = subparsers.add_parser(
        "run-baseline",
        help="Run the deterministic Phase 1I baseline pipeline and write artifacts.",
    )
    run_baseline.add_argument("--task", required=True, help="Path to a TaskCase JSON fixture.")
    run_baseline.add_argument("--config", required=True, help="Path to a RunConfig JSON fixture.")
    run_baseline.add_argument(
        "--components",
        required=True,
        help="Path to a ComponentConfig JSON fixture.",
    )
    run_baseline.add_argument(
        "--tool-spec",
        action="append",
        required=True,
        help="Path to a ToolSpec JSON fixture. May be supplied more than once.",
    )
    run_baseline.add_argument(
        "--artifact-root",
        help="Optional artifact root. Defaults to paths declared in the RunConfig.",
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

    if args.command == "verify-trace":
        try:
            task = TaskCase.from_dict(load_json(Path(args.task)))
            trace = read_run_trace(Path(args.trace))
            result = RuleBasedVerifier().verify(task, trace)
            if args.output:
                VerificationResultWriter(Path(args.output).parent).write(result, Path(args.output))
            elif args.result_dir:
                VerificationResultWriter(Path(args.result_dir)).write(result)
        except ValidationError as exc:
            print(f"Trace verification failed: {exc}", file=sys.stderr)
            return 1

        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0 if result.passed else 1

    if args.command == "run-baseline":
        try:
            result = run_phase1_baseline(
                task_path=Path(args.task),
                run_config_path=Path(args.config),
                component_config_path=Path(args.components),
                tool_spec_paths=[Path(path) for path in args.tool_spec],
                artifact_root=Path(args.artifact_root) if args.artifact_root else None,
            )
        except ValidationError as exc:
            print(f"Baseline run failed: {exc}", file=sys.stderr)
            return 1

        print(json.dumps(_baseline_run_cli_summary(result), indent=2, sort_keys=True))
        return 0 if result.verification.passed else 1

    parser.error(f"Unknown command: {args.command}")
    return 2


def _baseline_run_cli_summary(result: BaselineRunResult) -> Dict[str, object]:
    return {
        "run_id": result.trace.run_id,
        "status": result.trace.status,
        "task_success": result.metrics.task_success,
        "verification_passed": result.verification.passed,
        "artifacts": result.artifact_paths.to_dict(),
    }
