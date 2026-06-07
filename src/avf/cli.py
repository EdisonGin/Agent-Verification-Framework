"""Command line interface for framework setup and fixture validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, Optional

from avf.contracts import TaskCase, ValidationError
from avf.contracts.fixture_loader import load_json, validate_fixture_tree
from avf.orchestration import (
    BaselineRunResult,
    Phase2IntegrationResult,
    build_run_context_from_files,
    run_component_aware_baseline,
    run_phase2_integration_baseline,
)
from avf.storage import FileSystemResultsStore
from avf.tracing import read_run_trace
from avf.verification import DEFAULT_RULE_BASED_VERIFIER_ID, RuleBasedVerifier, VerificationResultWriter


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
        help="Run the deterministic component-aware baseline pipeline and write artifacts.",
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

    validate_artifacts = subparsers.add_parser(
        "validate-artifacts",
        help="Validate one run's trace, verification, metrics, and report artifacts as a set.",
    )
    validate_artifacts.add_argument("--artifact-root", required=True, help="Artifact root directory.")
    validate_artifacts.add_argument("--run-id", required=True, help="Run ID to validate.")
    validate_artifacts.add_argument(
        "--verifier-id",
        default=DEFAULT_RULE_BASED_VERIFIER_ID,
        help=f"Verifier ID used in the verification artifact filename. Defaults to {DEFAULT_RULE_BASED_VERIFIER_ID}.",
    )
    validate_artifacts.add_argument(
        "--write-manifest",
        action="store_true",
        help="Write or refresh the deterministic artifact manifest after validation.",
    )

    run_phase2 = subparsers.add_parser(
        "run-phase2-integration",
        help="Run the Phase 2 component-aware integration baseline.",
    )
    run_phase2.add_argument("--task", required=True, help="Path to a TaskCase JSON fixture.")
    run_phase2.add_argument("--config", required=True, help="Path to a RunConfig JSON fixture.")
    run_phase2.add_argument(
        "--component",
        action="append",
        required=True,
        help="Path to a ComponentConfig JSON fixture. Supply at least two.",
    )
    run_phase2.add_argument(
        "--tool-spec",
        action="append",
        required=True,
        help="Path to a ToolSpec JSON fixture. May be supplied more than once.",
    )
    run_phase2.add_argument(
        "--artifact-root",
        help="Optional artifact root. Defaults to paths declared in the RunConfig.",
    )
    run_phase2.add_argument(
        "--experiment-id",
        default="phase2_integration_baseline",
        help="Experiment identifier for comparison summary and exit report artifacts.",
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
            result = run_component_aware_baseline(
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

    if args.command == "validate-artifacts":
        store = FileSystemResultsStore.from_artifact_root(Path(args.artifact_root))
        validation = store.validate_run_artifacts(args.run_id, args.verifier_id)
        payload = validation.to_dict()
        if args.write_manifest:
            manifest = store.build_artifact_manifest(args.run_id, args.verifier_id)
            manifest_path = store.write_artifact_manifest(manifest)
            payload["manifest"] = str(manifest_path)

        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if validation.passed else 1

    if args.command == "run-phase2-integration":
        try:
            result = run_phase2_integration_baseline(
                task_path=Path(args.task),
                run_config_path=Path(args.config),
                component_config_paths=[Path(path) for path in args.component],
                tool_spec_paths=[Path(path) for path in args.tool_spec],
                artifact_root=Path(args.artifact_root) if args.artifact_root else None,
                experiment_id=args.experiment_id,
            )
        except ValidationError as exc:
            print(f"Phase 2 integration failed: {exc}", file=sys.stderr)
            return 1

        print(json.dumps(_phase2_integration_cli_summary(result), indent=2, sort_keys=True))
        return 0 if result.experiment.aggregation["phase2_exit_criteria"]["ready_for_phase3_full_factorial"] else 1

    parser.error(f"Unknown command: {args.command}")
    return 2


def _baseline_run_cli_summary(result: BaselineRunResult) -> Dict[str, object]:
    return {
        "run_id": result.trace.run_id,
        "status": result.trace.status,
        "task_success": result.metrics.task_success,
        "verification_passed": result.verification.passed,
        "component_config_id": result.component_bundle.config_id,
        "component_bundle": result.component_bundle.to_dict(),
        "artifacts": result.artifact_paths.to_dict(),
    }


def _phase2_integration_cli_summary(result: Phase2IntegrationResult) -> Dict[str, object]:
    criteria = result.experiment.aggregation["phase2_exit_criteria"]
    return {
        "experiment_id": result.experiment.experiment_id,
        "run_count": len(result.run_results),
        "run_ids": result.experiment.run_ids,
        "component_config_ids": [
            run.component_bundle.config_id
            for run in result.run_results
        ],
        "comparison_summary": str(result.comparison_summary_path),
        "exit_report": str(result.exit_report_path),
        "task_success_rate": result.experiment.aggregation["task_success_rate"],
        "artifact_validation_pass_rate": result.experiment.aggregation["artifact_validation_pass_rate"],
        "ready_for_phase3_full_factorial": criteria["ready_for_phase3_full_factorial"],
    }
