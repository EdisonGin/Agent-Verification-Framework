"""Command line interface for framework setup and fixture validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, Optional

from avf.analysis import (
    Phase4AAnalysisResult,
    Phase4BComponentEffectResult,
    analyze_phase4a_dataset,
    summarize_phase4b_component_effects,
)
from avf.contracts import TaskCase, ValidationError
from avf.contracts.fixture_loader import load_json, validate_fixture_tree
from avf.orchestration import (
    BaselineRunResult,
    Phase2IntegrationResult,
    Phase3AExperimentResult,
    Phase3BPilotQAResult,
    Phase3CDatasetFreezeResult,
    Phase3DReadinessReviewResult,
    build_run_context_from_files,
    freeze_phase3c_dataset_from_config,
    load_experiment_config,
    run_component_aware_baseline,
    run_phase2_integration_baseline,
    run_phase3a_full_factorial,
    run_phase3b_pilot_qa,
    run_phase3d_readiness_review_from_config,
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

    run_phase3a = subparsers.add_parser(
        "run-phase3a-experiment",
        help="Run the Phase 3A full factorial experiment matrix.",
    )
    run_phase3a.add_argument(
        "--experiment-config",
        required=True,
        help="Path to a Phase 3A ExperimentConfig JSON fixture.",
    )
    run_phase3a.add_argument(
        "--artifact-root",
        help="Optional artifact root override. Defaults to the ExperimentConfig or RunConfig artifact paths.",
    )
    run_phase3a.add_argument(
        "--experiment-id",
        help="Optional experiment ID override for ad hoc reruns.",
    )

    run_phase3b = subparsers.add_parser(
        "run-phase3b-pilot",
        help="Run the Phase 3B pilot QA workflow and write QA artifacts.",
    )
    run_phase3b.add_argument(
        "--experiment-config",
        required=True,
        help="Path to a Phase 3 ExperimentConfig JSON fixture.",
    )
    run_phase3b.add_argument(
        "--artifact-root",
        help="Optional artifact root override. Defaults to the ExperimentConfig or RunConfig artifact paths.",
    )
    run_phase3b.add_argument(
        "--experiment-id",
        help="Optional experiment ID override for ad hoc pilot runs.",
    )
    run_phase3b.add_argument(
        "--operator-notes",
        default="Phase 3B pilot QA execution.",
        help="Human operator note to include in the pilot log.",
    )
    run_phase3b.add_argument(
        "--known-limitation",
        action="append",
        default=[],
        help="Known pilot limitation to include in the pilot log. May be supplied more than once.",
    )
    run_phase3b.add_argument(
        "--commit-hash",
        help="Optional commit hash override for reproducibility tests or archived reruns.",
    )

    freeze_phase3c = subparsers.add_parser(
        "freeze-phase3c-dataset",
        help="Freeze an accepted Phase 3 pilot artifact set for analysis.",
    )
    freeze_phase3c.add_argument(
        "--experiment-config",
        required=True,
        help="Path to the Phase 3 ExperimentConfig JSON fixture used for the pilot.",
    )
    freeze_phase3c.add_argument(
        "--artifact-root",
        help="Artifact root containing Phase 3A and Phase 3B outputs.",
    )
    freeze_phase3c.add_argument(
        "--dataset-id",
        help="Optional frozen dataset identifier. Defaults to <experiment_id>_dataset_v1.",
    )
    freeze_phase3c.add_argument(
        "--frozen-at",
        help="Optional freeze timestamp override for reproducibility tests.",
    )
    freeze_phase3c.add_argument(
        "--commit-hash",
        help="Optional commit hash override for archived freezes.",
    )
    freeze_phase3c.add_argument(
        "--operator-notes",
        default="Phase 3C dataset freeze.",
        help="Human operator note to include in the dataset index.",
    )

    review_phase3d = subparsers.add_parser(
        "review-phase3d-readiness",
        help="Review whether a results index database or dashboard is justified.",
    )
    review_phase3d.add_argument(
        "--experiment-config",
        required=True,
        help="Path to the Phase 3 ExperimentConfig JSON fixture used for the frozen dataset.",
    )
    review_phase3d.add_argument(
        "--artifact-root",
        help="Artifact root containing the frozen dataset artifacts.",
    )
    review_phase3d.add_argument(
        "--operator-notes",
        default="Phase 3D results-index and dashboard readiness review.",
        help="Human operator note to include in the decision record.",
    )
    review_phase3d.add_argument(
        "--database-run-threshold",
        type=int,
        default=100,
        help="Run-count threshold above which a SQLite read model should be planned.",
    )
    review_phase3d.add_argument(
        "--database-bytes-threshold",
        type=int,
        default=50000000,
        help="Artifact-byte threshold above which a SQLite read model should be planned.",
    )

    analyze_dataset = subparsers.add_parser(
        "analyze-dataset",
        help="Run the Phase 4A read-only analysis scaffold over a frozen dataset index.",
    )
    analyze_dataset.add_argument(
        "--dataset-index",
        required=True,
        help="Path to the frozen dataset_index.json artifact.",
    )
    analyze_dataset.add_argument(
        "--artifact-root",
        help="Artifact root used to resolve relative artifact paths. Inferred from dataset index by default.",
    )
    analyze_dataset.add_argument(
        "--analysis-root",
        help="Directory where analysis artifacts should be written. Defaults to <artifact_root>/analysis.",
    )
    analyze_dataset.add_argument(
        "--analysis-id",
        help="Optional analysis identifier. Defaults to <dataset_id>_phase4a.",
    )
    analyze_dataset.add_argument(
        "--generated-at",
        help="Optional timestamp override for reproducible analysis tests.",
    )
    analyze_dataset.add_argument(
        "--code-version",
        help="Optional code version override for archived analysis artifacts.",
    )

    summarize_effects = subparsers.add_parser(
        "summarize-component-effects",
        help="Run the Phase 4B component-effect summary over a Phase 4A metrics table.",
    )
    summarize_effects.add_argument(
        "--metrics-table",
        required=True,
        help="Path to the Phase 4A metrics_table.json artifact.",
    )
    summarize_effects.add_argument(
        "--analysis-root",
        help="Directory where Phase 4B analysis artifacts should be written. Defaults to the metrics table analysis root.",
    )
    summarize_effects.add_argument(
        "--generated-at",
        help="Optional timestamp override for reproducible analysis tests.",
    )
    summarize_effects.add_argument(
        "--code-version",
        help="Optional code version override for archived component-effect artifacts.",
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

    if args.command == "run-phase3a-experiment":
        try:
            config = load_experiment_config(Path(args.experiment_config))
            config = config.with_overrides(
                experiment_id=args.experiment_id,
                artifact_root=Path(args.artifact_root) if args.artifact_root else None,
            )
            result = run_phase3a_full_factorial(config)
        except ValidationError as exc:
            print(f"Phase 3A experiment failed: {exc}", file=sys.stderr)
            return 1

        print(json.dumps(_phase3a_experiment_cli_summary(result), indent=2, sort_keys=True))
        return 0 if result.experiment.aggregation["phase3a_acceptance_criteria"]["ready_for_phase3b_pilot_qa"] else 1

    if args.command == "run-phase3b-pilot":
        try:
            experiment_config_path = Path(args.experiment_config)
            config = load_experiment_config(experiment_config_path)
            config = config.with_overrides(
                experiment_id=args.experiment_id,
                artifact_root=Path(args.artifact_root) if args.artifact_root else None,
            )
            result = run_phase3b_pilot_qa(
                config=config,
                experiment_config_path=experiment_config_path,
                operator_notes=args.operator_notes,
                known_limitations=list(args.known_limitation),
                commit_hash=args.commit_hash,
            )
        except ValidationError as exc:
            print(f"Phase 3B pilot QA failed: {exc}", file=sys.stderr)
            return 1

        print(json.dumps(_phase3b_pilot_cli_summary(result), indent=2, sort_keys=True))
        return 0 if result.qa_summary["ready_for_dataset_execution"] else 1

    if args.command == "freeze-phase3c-dataset":
        try:
            result = freeze_phase3c_dataset_from_config(
                experiment_config_path=Path(args.experiment_config),
                artifact_root=Path(args.artifact_root) if args.artifact_root else None,
                dataset_id=args.dataset_id,
                frozen_at=args.frozen_at,
                commit_hash=args.commit_hash,
                operator_notes=args.operator_notes,
            )
        except ValidationError as exc:
            print(f"Phase 3C dataset freeze failed: {exc}", file=sys.stderr)
            return 1

        print(json.dumps(_phase3c_freeze_cli_summary(result), indent=2, sort_keys=True))
        return 0 if result.validation.passed else 1

    if args.command == "review-phase3d-readiness":
        try:
            result = run_phase3d_readiness_review_from_config(
                experiment_config_path=Path(args.experiment_config),
                artifact_root=Path(args.artifact_root) if args.artifact_root else None,
                operator_notes=args.operator_notes,
                database_run_threshold=args.database_run_threshold,
                database_bytes_threshold=args.database_bytes_threshold,
            )
        except ValidationError as exc:
            print(f"Phase 3D readiness review failed: {exc}", file=sys.stderr)
            return 1

        print(json.dumps(_phase3d_review_cli_summary(result), indent=2, sort_keys=True))
        return 0

    if args.command == "analyze-dataset":
        try:
            result = analyze_phase4a_dataset(
                dataset_index_path=Path(args.dataset_index),
                artifact_root=Path(args.artifact_root) if args.artifact_root else None,
                analysis_root=Path(args.analysis_root) if args.analysis_root else None,
                analysis_id=args.analysis_id,
                generated_at=args.generated_at,
                code_version=args.code_version,
            )
        except ValidationError as exc:
            print(f"Phase 4A dataset analysis failed: {exc}", file=sys.stderr)
            return 1

        print(json.dumps(_phase4a_analysis_cli_summary(result), indent=2, sort_keys=True))
        return 0 if result.analysis_input_manifest["artifact_hash_validation_passed"] else 1

    if args.command == "summarize-component-effects":
        try:
            result = summarize_phase4b_component_effects(
                metrics_table_path=Path(args.metrics_table),
                analysis_root=Path(args.analysis_root) if args.analysis_root else None,
                generated_at=args.generated_at,
                code_version=args.code_version,
            )
        except ValidationError as exc:
            print(f"Phase 4B component-effect summary failed: {exc}", file=sys.stderr)
            return 1

        print(json.dumps(_phase4b_effects_cli_summary(result), indent=2, sort_keys=True))
        return 0

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


def _phase3a_experiment_cli_summary(result: Phase3AExperimentResult) -> Dict[str, object]:
    aggregation = result.experiment.aggregation
    criteria = aggregation["phase3a_acceptance_criteria"]
    return {
        "experiment_id": result.experiment.experiment_id,
        "expected_run_count": aggregation["expected_run_count"],
        "completed_run_count": aggregation["completed_run_count"],
        "run_count": len(result.run_results),
        "run_ids": result.experiment.run_ids,
        "component_config_ids": [
            run.component_bundle.config_id
            for run in result.run_results
        ],
        "matrix": str(result.artifacts.matrix),
        "run_index": str(result.artifacts.run_index),
        "comparison_summary": str(result.artifacts.comparison_summary),
        "experiment_report": str(result.artifacts.experiment_report),
        "task_success_rate": aggregation["task_success_rate"],
        "artifact_validation_pass_rate": aggregation["artifact_validation_pass_rate"],
        "ready_for_phase3b_pilot_qa": criteria["ready_for_phase3b_pilot_qa"],
    }


def _phase3b_pilot_cli_summary(result: Phase3BPilotQAResult) -> Dict[str, object]:
    return {
        "experiment_id": result.phase3a_result.experiment.experiment_id,
        "pilot_mode": result.qa_summary["pilot_mode"],
        "expected_run_count": result.qa_summary["expected_run_count"],
        "completed_run_count": result.qa_summary["completed_run_count"],
        "failure_note_count": len(result.failure_notes),
        "rerun_record_count": len(result.rerun_records),
        "dataset_execution_blocked": result.qa_summary["dataset_execution_blocked"],
        "ready_for_dataset_execution": result.qa_summary["ready_for_dataset_execution"],
        "pilot_decision": result.qa_summary["pilot_decision"],
        "pilot_log": str(result.artifacts.pilot_log),
        "rerun_records": str(result.artifacts.rerun_records),
        "failure_notes_json": str(result.artifacts.failure_notes_json),
        "failure_notes_markdown": str(result.artifacts.failure_notes_markdown),
        "qa_summary": str(result.artifacts.qa_summary),
    }


def _phase3c_freeze_cli_summary(result: Phase3CDatasetFreezeResult) -> Dict[str, object]:
    return {
        "dataset_id": result.dataset_id,
        "experiment_id": result.experiment_id,
        "included_run_count": result.dataset_index["included_run_count"],
        "excluded_run_count": result.dataset_index["excluded_run_count"],
        "frozen": result.frozen_dataset_manifest["frozen"],
        "dataset_index": str(result.artifacts.dataset_index),
        "frozen_dataset_manifest": str(result.artifacts.frozen_dataset_manifest),
        "dataset_report": str(result.artifacts.dataset_report),
    }


def _phase3d_review_cli_summary(result: Phase3DReadinessReviewResult) -> Dict[str, object]:
    return {
        "experiment_id": result.experiment_id,
        "dataset_id": result.dataset_id,
        "filesystem_sufficient": result.results_index_decision["filesystem_sufficient"],
        "database_recommended": result.results_index_decision["database_recommended"],
        "database_decision": result.results_index_decision["database_decision"],
        "dashboard_recommended_now": result.results_index_decision["dashboard_recommended_now"],
        "dashboard_decision": result.results_index_decision["dashboard_decision"],
        "storage_volume_review": str(result.artifacts.storage_volume_review),
        "query_requirements": str(result.artifacts.query_requirements),
        "dashboard_requirements": str(result.artifacts.dashboard_requirements),
        "results_index_decision": str(result.artifacts.results_index_decision),
        "review_report": str(result.artifacts.review_report),
    }


def _phase4a_analysis_cli_summary(result: Phase4AAnalysisResult) -> Dict[str, object]:
    return {
        "dataset_id": result.dataset_id,
        "experiment_id": result.experiment_id,
        "row_count": result.metrics_table["row_count"],
        "included_run_count": result.metrics_table["included_run_count"],
        "excluded_run_count": result.metrics_table["excluded_run_count"],
        "artifact_hash_validation_passed": result.analysis_input_manifest[
            "artifact_hash_validation_passed"
        ],
        "analysis_config": str(result.artifacts.analysis_config),
        "analysis_input_manifest": str(result.artifacts.analysis_input_manifest),
        "metrics_table_json": str(result.artifacts.metrics_table_json),
        "metrics_table_csv": str(result.artifacts.metrics_table_csv),
        "metrics_table_markdown": str(result.artifacts.metrics_table_markdown),
    }


def _phase4b_effects_cli_summary(result: Phase4BComponentEffectResult) -> Dict[str, object]:
    return {
        "dataset_id": result.dataset_id,
        "experiment_id": result.experiment_id,
        "complete_block_count": result.component_effects["complete_block_count"],
        "incomplete_block_count": result.component_effects["incomplete_block_count"],
        "main_effect_count": len(result.component_effects["main_effects"]),
        "interaction_count": len(result.interaction_summary["interactions"]),
        "descriptive_only": result.component_effects["limitations"]["descriptive_only"],
        "component_effects_json": str(result.artifacts.component_effects_json),
        "component_effects_markdown": str(result.artifacts.component_effects_markdown),
        "interaction_summary_json": str(result.artifacts.interaction_summary_json),
        "interaction_summary_markdown": str(result.artifacts.interaction_summary_markdown),
        "dissertation_tables": str(result.artifacts.dissertation_tables),
    }
