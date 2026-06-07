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

from avf.cli import main as cli_main  # noqa: E402
from avf.orchestration import (  # noqa: E402
    freeze_phase3c_dataset,
    load_experiment_config,
    run_phase3b_pilot_qa,
    run_phase3d_readiness_review,
)


EXPERIMENT_CONFIG_PATH = ROOT / "test_data/experiments/phase3_full_factorial_v1.json"


class Phase3DReadinessReviewTests(unittest.TestCase):
    def test_readiness_review_writes_decision_artifacts_for_current_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = _freeze_dataset(Path(directory))
            result = run_phase3d_readiness_review(
                config=config,
                operator_notes="unit test review",
            )
            storage_review = json.loads(result.artifacts.storage_volume_review.read_text(encoding="utf-8"))
            query_requirements = json.loads(result.artifacts.query_requirements.read_text(encoding="utf-8"))
            decision = json.loads(result.artifacts.results_index_decision.read_text(encoding="utf-8"))
            dashboard_requirements = result.artifacts.dashboard_requirements.read_text(encoding="utf-8")
            report = result.artifacts.review_report.read_text(encoding="utf-8")

        self.assertEqual(storage_review["run_count"], 8)
        self.assertEqual(storage_review["included_run_count"], 8)
        self.assertEqual(storage_review["run_artifact_count"], 40)
        self.assertEqual(storage_review["storage_backend"], "filesystem")
        self.assertEqual(query_requirements["primary_analysis_entrypoint"], "dataset_index.json")
        self.assertIn("component_config_id", query_requirements["required_filters"])
        self.assertIn("run metadata to metrics artifact", query_requirements["required_joins"])
        self.assertTrue(decision["filesystem_sufficient"])
        self.assertFalse(decision["database_recommended"])
        self.assertEqual(decision["database_decision"], "defer_results_database")
        self.assertFalse(decision["dashboard_recommended_now"])
        self.assertEqual(decision["read_model_policy"]["source_of_truth"], "frozen filesystem artifacts")
        self.assertFalse(decision["read_model_policy"]["raw_artifacts_replaced"])
        self.assertTrue(decision["phase3d_acceptance_criteria"]["filesystem_sufficiency_recorded"])
        self.assertIn("Phase 3D Dashboard Requirements Review", dashboard_requirements)
        self.assertIn("Component comparison matrix", dashboard_requirements)
        self.assertIn("Phase 3D Results Index and Dashboard Readiness Review", report)

    def test_review_recommends_sqlite_read_model_when_volume_threshold_is_exceeded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = _freeze_dataset(Path(directory))
            result = run_phase3d_readiness_review(
                config=config,
                database_run_threshold=1,
                operator_notes="threshold test",
            )

        decision = result.results_index_decision

        self.assertFalse(decision["filesystem_sufficient"])
        self.assertTrue(decision["database_recommended"])
        self.assertEqual(decision["database_decision"], "plan_sqlite_read_model")
        self.assertEqual(decision["read_model_policy"]["candidate_backend"], "sqlite")
        self.assertTrue(decision["read_model_policy"]["would_be_read_only"])
        self.assertFalse(decision["read_model_policy"]["raw_artifacts_replaced"])
        self.assertTrue(decision["dashboard_recommended_now"])

    def test_phase3d_cli_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _freeze_dataset(Path(directory))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = cli_main(
                    [
                        "review-phase3d-readiness",
                        "--experiment-config",
                        str(EXPERIMENT_CONFIG_PATH),
                        "--artifact-root",
                        directory,
                        "--operator-notes",
                        "cli review",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            storage_exists = Path(payload["storage_volume_review"]).exists()
            query_exists = Path(payload["query_requirements"]).exists()
            decision_exists = Path(payload["results_index_decision"]).exists()
            dashboard_exists = Path(payload["dashboard_requirements"]).exists()
            report_exists = Path(payload["review_report"]).exists()

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["filesystem_sufficient"])
        self.assertFalse(payload["database_recommended"])
        self.assertEqual(payload["database_decision"], "defer_results_database")
        self.assertFalse(payload["dashboard_recommended_now"])
        self.assertTrue(storage_exists)
        self.assertTrue(query_exists)
        self.assertTrue(decision_exists)
        self.assertTrue(dashboard_exists)
        self.assertTrue(report_exists)

    def test_phase3d_script_runs_with_artifact_root_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ)
            env["AVF_ARTIFACT_ROOT"] = directory
            env["PYTHONPATH"] = "src"

            completed = subprocess.run(
                [str(ROOT / "scripts/run-phase3d-review.sh")],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["filesystem_sufficient"])
        self.assertFalse(payload["database_recommended"])
        self.assertFalse(payload["dashboard_recommended_now"])


def _freeze_dataset(artifact_root: Path) -> object:
    config = load_experiment_config(EXPERIMENT_CONFIG_PATH).with_overrides(artifact_root=artifact_root)
    run_phase3b_pilot_qa(
        config=config,
        experiment_config_path=EXPERIMENT_CONFIG_PATH,
        timestamp="2026-06-07T00:00:00Z",
        commit_hash="pilot_commit",
        operator_notes="phase3d test pilot",
    )
    freeze_phase3c_dataset(
        config=config,
        experiment_config_path=EXPERIMENT_CONFIG_PATH,
        frozen_at="2026-06-07T00:00:00Z",
        commit_hash="freeze_commit",
        operator_notes="phase3d test freeze",
    )
    return config


if __name__ == "__main__":
    unittest.main()
