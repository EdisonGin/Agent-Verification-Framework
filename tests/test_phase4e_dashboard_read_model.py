from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from avf.analysis import (  # noqa: E402
    analyze_phase4a_dataset,
    diagnose_phase4c_trajectories,
    summarize_phase4b_component_effects,
    write_phase4d_failure_analysis_report,
    write_phase4e_dashboard_read_model,
)
from avf.cli import main as cli_main  # noqa: E402
from avf.orchestration import (  # noqa: E402
    freeze_phase3c_dataset,
    load_experiment_config,
    run_phase3b_pilot_qa,
    run_phase3d_readiness_review,
)


EXPERIMENT_CONFIG_PATH = ROOT / "test_data/experiments/phase3_full_factorial_v1.json"


class Phase4EDashboardReadModelTests(unittest.TestCase):
    def test_phase4e_writes_read_model_decision_and_dashboard_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            metrics_table = _prepare_phase4e_inputs(Path(directory))
            result = write_phase4e_dashboard_read_model(
                metrics_table_path=metrics_table,
                analysis_root=Path(directory) / "analysis",
                generated_at="2026-06-08T00:00:00Z",
                code_version="phase4e_test",
            )
            decision = json.loads(result.artifacts.read_model_decision_json.read_text(encoding="utf-8"))
            read_model = json.loads(result.artifacts.results_read_model_json.read_text(encoding="utf-8"))
            dashboard_data = json.loads(result.artifacts.dashboard_data_json.read_text(encoding="utf-8"))
            snapshot = result.artifacts.dashboard_snapshot_markdown.read_text(encoding="utf-8")

        self.assertEqual(result.dataset_id, "phase3_full_factorial_v1_dataset_v1")
        self.assertEqual(decision["phase3d_decision_summary"]["database_decision"], "defer_results_database")
        self.assertFalse(decision["implementation_decision"]["database_materialized"])
        self.assertEqual(decision["implementation_decision"]["read_model_backend"], "json_derived_artifact")
        self.assertTrue(decision["analysis_acceptance_criteria"]["results_index_decision_cited"])
        self.assertTrue(decision["analysis_acceptance_criteria"]["phase4_query_needs_cited"])
        self.assertTrue(decision["analysis_acceptance_criteria"]["dashboard_not_source_of_truth"])
        self.assertIn("failure_class", decision["phase4_query_needs"]["filters"])

        self.assertEqual(read_model["row_count"], 8)
        self.assertEqual(len(read_model["component_summaries"]), 8)
        self.assertEqual(len(read_model["indexes"]["by_failure_class"]["passed"]), 8)
        self.assertFalse(read_model["read_model_decision"]["source_of_truth_policy"]["read_model_is_source_of_truth"])
        self.assertTrue(read_model["analysis_acceptance_criteria"]["failure_classes_joined_from_failure_analysis"])
        self.assertTrue(read_model["analysis_acceptance_criteria"]["trajectory_scopes_joined_from_diagnostics"])

        views = dashboard_data["views"]
        self.assertEqual(len(views), 7)
        self.assertFalse(dashboard_data["source_policy"]["dashboard_is_source_of_truth"])
        self.assertEqual(views["dataset_overview"]["run_count"], 8)
        self.assertEqual(views["dataset_overview"]["claim_level"], "descriptive")
        self.assertEqual(views["verification_outcome_breakdown"]["passed"], 8)
        self.assertEqual(views["failure_taxonomy_review"]["taxonomy_counts"]["passed"], 8)
        self.assertIn("Phase 4E Read Model and Dashboard Snapshot", snapshot)
        self.assertIn("source of truth", snapshot)

    def test_phase4e_cli_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            metrics_table = _prepare_phase4e_inputs(Path(directory))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = cli_main(
                    [
                        "write-dashboard-read-model",
                        "--metrics-table",
                        str(metrics_table),
                        "--analysis-root",
                        str(Path(directory) / "analysis"),
                        "--generated-at",
                        "2026-06-08T00:00:00Z",
                        "--code-version",
                        "phase4e_cli",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            decision_exists = Path(payload["read_model_decision_json"]).exists()
            read_model_exists = Path(payload["results_read_model_json"]).exists()
            dashboard_data_exists = Path(payload["dashboard_data_json"]).exists()
            snapshot_exists = Path(payload["dashboard_snapshot_markdown"]).exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["row_count"], 8)
        self.assertFalse(payload["database_materialized"])
        self.assertEqual(payload["read_model_backend"], "json_derived_artifact")
        self.assertEqual(payload["dashboard_view_count"], 7)
        self.assertTrue(payload["dashboard_not_source_of_truth"])
        self.assertTrue(decision_exists)
        self.assertTrue(read_model_exists)
        self.assertTrue(dashboard_data_exists)
        self.assertTrue(snapshot_exists)

    def test_phase4e_links_dashboard_views_to_read_model_and_derived_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            metrics_table = _prepare_phase4e_inputs(root)
            result = write_phase4e_dashboard_read_model(
                metrics_table_path=metrics_table,
                analysis_root=root / "analysis",
                generated_at="2026-06-08T00:00:00Z",
                code_version="phase4e_source_policy_test",
            )

        source_artifacts = result.read_model_decision["source_artifacts"]
        self.assertTrue(source_artifacts["results_index_decision"]["exists"])
        self.assertTrue(source_artifacts["component_effects"]["exists"])
        self.assertTrue(source_artifacts["trajectory_diagnostics"]["exists"])
        self.assertTrue(source_artifacts["failure_analysis"]["exists"])
        self.assertFalse(result.read_model_decision["source_of_truth_policy"]["raw_artifacts_replaced"])
        self.assertFalse(result.dashboard_data["source_policy"]["read_model_is_source_of_truth"])
        self.assertTrue(
            result.dashboard_data["analysis_acceptance_criteria"][
                "views_read_derived_phase4_artifacts"
            ]
        )
        self.assertTrue(
            result.dashboard_data["analysis_acceptance_criteria"][
                "dashboard_not_source_of_truth"
            ]
        )

    def test_phase4e_script_runs_phase4d_prerequisite_and_dashboard_read_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ)
            env["AVF_ARTIFACT_ROOT"] = directory
            env["AVF_ANALYSIS_ROOT"] = str(Path(directory) / "analysis")
            env["PYTHONPATH"] = "src"

            completed = subprocess.run(
                [str(ROOT / "scripts/run-phase4e-dashboard-read-model.sh")],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout) if completed.stdout else {}
            dashboard_data_exists = Path(str(payload.get("dashboard_data_json", ""))).exists()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["row_count"], 8)
        self.assertFalse(payload["database_materialized"])
        self.assertTrue(payload["dashboard_not_source_of_truth"])
        self.assertTrue(dashboard_data_exists)


def _prepare_phase4e_inputs(artifact_root: Path) -> Path:
    config = load_experiment_config(EXPERIMENT_CONFIG_PATH).with_overrides(artifact_root=artifact_root)
    run_phase3b_pilot_qa(
        config=config,
        experiment_config_path=EXPERIMENT_CONFIG_PATH,
        timestamp="2026-06-07T00:00:00Z",
        commit_hash="pilot_commit",
        operator_notes="phase4e test pilot",
    )
    freeze_phase3c_dataset(
        config=config,
        experiment_config_path=EXPERIMENT_CONFIG_PATH,
        frozen_at="2026-06-07T00:00:00Z",
        commit_hash="freeze_commit",
        operator_notes="phase4e test freeze",
    )
    run_phase3d_readiness_review(
        config=config,
        operator_notes="phase4e readiness prerequisite",
    )
    dataset_index = artifact_root / "experiments/phase3_full_factorial_v1/dataset_index.json"
    phase4a = analyze_phase4a_dataset(
        dataset_index_path=dataset_index,
        artifact_root=artifact_root,
        analysis_root=artifact_root / "analysis",
        generated_at="2026-06-08T00:00:00Z",
        code_version="phase4a_test",
    )
    summarize_phase4b_component_effects(
        metrics_table_path=phase4a.artifacts.metrics_table_json,
        analysis_root=artifact_root / "analysis",
        generated_at="2026-06-08T00:00:00Z",
        code_version="phase4b_test",
    )
    diagnose_phase4c_trajectories(
        metrics_table_path=phase4a.artifacts.metrics_table_json,
        analysis_root=artifact_root / "analysis",
        generated_at="2026-06-08T00:00:00Z",
        code_version="phase4c_test",
    )
    write_phase4d_failure_analysis_report(
        metrics_table_path=phase4a.artifacts.metrics_table_json,
        analysis_root=artifact_root / "analysis",
        generated_at="2026-06-08T00:00:00Z",
        code_version="phase4d_test",
    )
    return phase4a.artifacts.metrics_table_json


if __name__ == "__main__":
    unittest.main()
