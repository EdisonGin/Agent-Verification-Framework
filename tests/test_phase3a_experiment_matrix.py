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
from avf.contracts import ExperimentResult  # noqa: E402
from avf.orchestration import build_experiment_matrix, load_experiment_config, run_phase3a_full_factorial  # noqa: E402


EXPERIMENT_CONFIG_PATH = ROOT / "test_data/experiments/phase3_full_factorial_v1.json"
EXPECTED_COMPONENT_IDS = [
    "A1_B1_C1",
    "A1_B1_C2",
    "A1_B2_C1",
    "A1_B2_C2",
    "A2_B1_C1",
    "A2_B1_C2",
    "A2_B2_C1",
    "A2_B2_C2",
]


class Phase3AExperimentMatrixTests(unittest.TestCase):
    def test_matrix_builder_resolves_current_full_factorial_matrix(self) -> None:
        config = load_experiment_config(EXPERIMENT_CONFIG_PATH)
        matrix = build_experiment_matrix(config)

        self.assertEqual(matrix.experiment_id, "phase3_full_factorial_v1")
        self.assertEqual(matrix.row_count, 8)
        self.assertEqual([row.component_config_id for row in matrix.rows], EXPECTED_COMPONENT_IDS)
        self.assertEqual(len({row.expected_run_id for row in matrix.rows}), 8)

        for row in matrix.rows:
            with self.subTest(row_id=row.row_id):
                self.assertEqual(row.task_id, "memory_recall_001")
                self.assertEqual(row.task_version, "1.0")
                self.assertEqual(row.run_config_id, "baseline_seed_001")
                self.assertEqual(row.seed, 42)
                self.assertEqual(row.perturbation_schedule_id, "schedule_none_v1")
                self.assertEqual(row.tool_names, ["memory.write", "memory.query"])
                self.assertEqual(row.tool_schema_versions["memory.write"], "1.0")
                self.assertEqual(row.tool_schema_versions["memory.query"], "1.0")
                self.assertTrue(row.expected_run_id.startswith("run_"))
                self.assertTrue(row.task_fixture.exists())
                self.assertTrue(row.run_config_fixture.exists())
                self.assertTrue(row.component_fixture.exists())
                self.assertTrue(all(path.exists() for path in row.tool_spec_fixtures))

    def test_full_factorial_runner_writes_experiment_indexes_and_run_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = load_experiment_config(EXPERIMENT_CONFIG_PATH).with_overrides(artifact_root=Path(directory))
            result = run_phase3a_full_factorial(config)
            comparison_payload = json.loads(result.artifacts.comparison_summary.read_text(encoding="utf-8"))
            matrix_payload = json.loads(result.artifacts.matrix.read_text(encoding="utf-8"))
            run_index_payload = json.loads(result.artifacts.run_index.read_text(encoding="utf-8"))
            report = result.artifacts.experiment_report.read_text(encoding="utf-8")

            for run in result.run_results:
                with self.subTest(run_id=run.trace.run_id):
                    self.assertTrue(run.artifact_paths.trace.exists())
                    self.assertTrue(run.artifact_paths.verification.exists())
                    self.assertTrue(run.artifact_paths.metrics.exists())
                    self.assertTrue(run.artifact_paths.report.exists())
                    self.assertTrue(run.artifact_paths.manifest.exists())
                    self.assertTrue(result.artifact_validations[run.trace.run_id].passed)

        experiment = ExperimentResult.from_dict(comparison_payload)
        criteria = experiment.aggregation["phase3a_acceptance_criteria"]

        self.assertEqual(result.matrix.row_count, 8)
        self.assertEqual(len(result.run_results), 8)
        self.assertEqual(experiment.aggregation["expected_run_count"], 8)
        self.assertEqual(experiment.aggregation["completed_run_count"], 8)
        self.assertEqual(experiment.aggregation["component_cell_count"], 8)
        self.assertEqual(experiment.aggregation["task_success_rate"], 1.0)
        self.assertEqual(experiment.aggregation["verification_pass_rate"], 1.0)
        self.assertEqual(experiment.aggregation["artifact_validation_pass_rate"], 1.0)
        self.assertTrue(criteria["all_eight_component_cells_included"])
        self.assertTrue(criteria["matrix_rows_include_required_references"])
        self.assertTrue(criteria["current_matrix_completed_end_to_end"])
        self.assertTrue(criteria["per_run_artifacts_written"])
        self.assertTrue(criteria["per_run_artifact_manifests_valid"])
        self.assertTrue(criteria["experiment_summary_records_expected_vs_completed"])
        self.assertTrue(criteria["ready_for_phase3b_pilot_qa"])
        self.assertEqual(matrix_payload["row_count"], 8)
        self.assertEqual(run_index_payload["record_count"], 8)
        self.assertEqual(
            [record["component_config_id"] for record in run_index_payload["records"]],
            EXPECTED_COMPONENT_IDS,
        )
        self.assertIn("Phase 3A Full Factorial Experiment Report", report)
        self.assertIn("Expected runs", report)
        self.assertIn("A2_B2_C2", report)

    def test_phase3a_cli_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = cli_main(
                    [
                        "run-phase3a-experiment",
                        "--experiment-config",
                        str(EXPERIMENT_CONFIG_PATH),
                        "--artifact-root",
                        directory,
                    ]
                )
            payload = json.loads(stdout.getvalue())
            matrix_exists = Path(payload["matrix"]).exists()
            run_index_exists = Path(payload["run_index"]).exists()
            comparison_exists = Path(payload["comparison_summary"]).exists()
            report_exists = Path(payload["experiment_report"]).exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["expected_run_count"], 8)
        self.assertEqual(payload["completed_run_count"], 8)
        self.assertEqual(payload["run_count"], 8)
        self.assertEqual(payload["component_config_ids"], EXPECTED_COMPONENT_IDS)
        self.assertEqual(payload["task_success_rate"], 1.0)
        self.assertEqual(payload["artifact_validation_pass_rate"], 1.0)
        self.assertTrue(payload["ready_for_phase3b_pilot_qa"])
        self.assertTrue(matrix_exists)
        self.assertTrue(run_index_exists)
        self.assertTrue(comparison_exists)
        self.assertTrue(report_exists)

    def test_phase3a_script_runs_with_artifact_root_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ)
            env["AVF_ARTIFACT_ROOT"] = directory
            env["PYTHONPATH"] = "src"

            completed = subprocess.run(
                [str(ROOT / "scripts/run-phase3a-experiment.sh")],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["expected_run_count"], 8)
        self.assertEqual(payload["completed_run_count"], 8)
        self.assertEqual(payload["component_config_ids"], EXPECTED_COMPONENT_IDS)
        self.assertTrue(payload["ready_for_phase3b_pilot_qa"])


if __name__ == "__main__":
    unittest.main()
