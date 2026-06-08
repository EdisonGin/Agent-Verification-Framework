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

from avf.analysis import analyze_phase4a_dataset  # noqa: E402
from avf.cli import main as cli_main  # noqa: E402
from avf.contracts import ValidationError  # noqa: E402
from avf.orchestration import (  # noqa: E402
    freeze_phase3c_dataset,
    load_experiment_config,
    run_phase3b_pilot_qa,
    run_phase3d_readiness_review,
)


EXPERIMENT_CONFIG_PATH = ROOT / "test_data/experiments/phase3_full_factorial_v1.json"


class Phase4AAnalysisTests(unittest.TestCase):
    def test_phase4a_analysis_writes_metrics_table_and_input_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dataset_index = _prepare_phase4_inputs(Path(directory))
            result = analyze_phase4a_dataset(
                dataset_index_path=dataset_index,
                artifact_root=Path(directory),
                analysis_root=Path(directory) / "analysis",
                generated_at="2026-06-08T00:00:00Z",
                code_version="analysis_commit",
            )
            config = json.loads(result.artifacts.analysis_config.read_text(encoding="utf-8"))
            manifest = json.loads(result.artifacts.analysis_input_manifest.read_text(encoding="utf-8"))
            metrics_json = json.loads(result.artifacts.metrics_table_json.read_text(encoding="utf-8"))
            metrics_csv = result.artifacts.metrics_table_csv.read_text(encoding="utf-8")
            metrics_md = result.artifacts.metrics_table_markdown.read_text(encoding="utf-8")

        self.assertEqual(result.dataset_id, "phase3_full_factorial_v1_dataset_v1")
        self.assertEqual(config["execution_policy"]["rerun_experiments"], False)
        self.assertEqual(config["execution_policy"]["database_required"], False)
        self.assertTrue(manifest["artifact_hash_validation_passed"])
        self.assertEqual(manifest["run_artifact_check_count"], 40)
        self.assertIn("results_index_decision", manifest["companion_artifacts"])
        self.assertTrue(manifest["analysis_acceptance_criteria"]["dataset_index_consumed_without_rerun"])
        self.assertFalse(manifest["analysis_acceptance_criteria"]["database_or_dashboard_introduced"])

        self.assertEqual(metrics_json["row_count"], 8)
        self.assertEqual(metrics_json["included_run_count"], 8)
        self.assertEqual(metrics_json["excluded_run_count"], 0)
        self.assertEqual(len(metrics_json["rows"]), 8)
        first = metrics_json["rows"][0]
        self.assertEqual(first["component_config_id"], "A1_B1_C1")
        self.assertTrue(first["artifact_hash_validation_passed"])
        self.assertTrue(first["task_success"])
        self.assertTrue(first["verification_passed"])
        self.assertEqual(first["latency_ms"], 0)
        self.assertEqual(first["step_count"], 3)
        self.assertEqual(first["tool_call_count"], 2)
        self.assertTrue(first["final_answer_present"])
        self.assertIn("token_usage", first["missing_metrics"])
        self.assertIn("cost_usage", first["missing_metrics"])
        self.assertIn("metrics_table.csv", str(result.artifacts.metrics_table_csv))
        self.assertIn("run_id", metrics_csv.splitlines()[0])
        self.assertIn("Phase 4A Metrics Table", metrics_md)

    def test_phase4a_cli_analyzes_frozen_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dataset_index = _prepare_phase4_inputs(Path(directory))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = cli_main(
                    [
                        "analyze-dataset",
                        "--dataset-index",
                        str(dataset_index),
                        "--artifact-root",
                        directory,
                        "--analysis-root",
                        str(Path(directory) / "analysis"),
                        "--generated-at",
                        "2026-06-08T00:00:00Z",
                        "--code-version",
                        "cli_analysis_commit",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            metrics_table_exists = Path(payload["metrics_table_json"]).exists()
            metrics_csv_exists = Path(payload["metrics_table_csv"]).exists()
            metrics_md_exists = Path(payload["metrics_table_markdown"]).exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["row_count"], 8)
        self.assertEqual(payload["included_run_count"], 8)
        self.assertTrue(payload["artifact_hash_validation_passed"])
        self.assertTrue(metrics_table_exists)
        self.assertTrue(metrics_csv_exists)
        self.assertTrue(metrics_md_exists)

    def test_phase4a_analysis_fails_on_hash_mismatch_after_writing_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset_index = _prepare_phase4_inputs(root)
            payload = json.loads(dataset_index.read_text(encoding="utf-8"))
            metrics_path = root / payload["records"][0]["artifact_records"]["metrics"]["path"]
            metrics_path.write_text("{}\n", encoding="utf-8")

            with self.assertRaises(ValidationError) as raised:
                analyze_phase4a_dataset(
                    dataset_index_path=dataset_index,
                    artifact_root=root,
                    analysis_root=root / "analysis",
                    generated_at="2026-06-08T00:00:00Z",
                    code_version="analysis_commit",
                )
            manifest_path = root / "analysis/phase3_full_factorial_v1_dataset_v1/analysis_input_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertIn("Phase 4A analysis input validation failed", str(raised.exception))
        self.assertFalse(manifest["artifact_hash_validation_passed"])
        self.assertTrue(any("hash mismatch" in issue for issue in manifest["integrity_issues"]))

    def test_phase4a_script_runs_phase3d_prerequisite_and_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ)
            env["AVF_ARTIFACT_ROOT"] = directory
            env["AVF_ANALYSIS_ROOT"] = str(Path(directory) / "analysis")
            env["PYTHONPATH"] = "src"

            completed = subprocess.run(
                [str(ROOT / "scripts/run-phase4a-analysis.sh")],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout) if completed.stdout else {}
            metrics_table_exists = Path(str(payload.get("metrics_table_json", ""))).exists()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["row_count"], 8)
        self.assertTrue(payload["artifact_hash_validation_passed"])
        self.assertTrue(metrics_table_exists)


def _prepare_phase4_inputs(artifact_root: Path) -> Path:
    config = load_experiment_config(EXPERIMENT_CONFIG_PATH).with_overrides(artifact_root=artifact_root)
    run_phase3b_pilot_qa(
        config=config,
        experiment_config_path=EXPERIMENT_CONFIG_PATH,
        timestamp="2026-06-07T00:00:00Z",
        commit_hash="pilot_commit",
        operator_notes="phase4a test pilot",
    )
    freeze_phase3c_dataset(
        config=config,
        experiment_config_path=EXPERIMENT_CONFIG_PATH,
        frozen_at="2026-06-07T00:00:00Z",
        commit_hash="freeze_commit",
        operator_notes="phase4a test freeze",
    )
    run_phase3d_readiness_review(
        config=config,
        operator_notes="phase4a readiness prerequisite",
    )
    return artifact_root / "experiments/phase3_full_factorial_v1/dataset_index.json"


if __name__ == "__main__":
    unittest.main()
