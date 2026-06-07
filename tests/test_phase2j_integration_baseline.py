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
from avf.orchestration import run_phase2_integration_baseline  # noqa: E402


TASK_PATH = ROOT / "test_data/tasks/memory_recall_001.json"
CONFIG_PATH = ROOT / "test_data/configs/baseline_seed_001.json"
COMPONENT_PATHS = [
    ROOT / "test_data/components/A1_B1_C1.json",
    ROOT / "test_data/components/A2_B2_C2.json",
]
TOOL_SPEC_PATHS = [
    ROOT / "test_data/tool_specs/memory.write.json",
    ROOT / "test_data/tool_specs/memory.query.json",
]


class Phase2JIntegrationBaselineTests(unittest.TestCase):
    def test_phase2_integration_baseline_writes_comparison_and_exit_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_phase2_integration_baseline(
                task_path=TASK_PATH,
                run_config_path=CONFIG_PATH,
                component_config_paths=COMPONENT_PATHS,
                tool_spec_paths=TOOL_SPEC_PATHS,
                artifact_root=Path(directory),
            )
            comparison_payload = json.loads(result.comparison_summary_path.read_text(encoding="utf-8"))
            exit_report = result.exit_report_path.read_text(encoding="utf-8")

        experiment = ExperimentResult.from_dict(comparison_payload)
        criteria = experiment.aggregation["phase2_exit_criteria"]
        rows = experiment.aggregation["comparison_rows"]

        self.assertEqual(experiment.experiment_id, "phase2_integration_baseline")
        self.assertEqual(experiment.factorial_design["component_config_ids"], ["A1_B1_C1", "A2_B2_C2"])
        self.assertEqual(experiment.aggregation["cell_count"], 2)
        self.assertEqual(experiment.aggregation["task_success_rate"], 1.0)
        self.assertEqual(experiment.aggregation["verification_pass_rate"], 1.0)
        self.assertEqual(experiment.aggregation["artifact_validation_pass_rate"], 1.0)
        self.assertTrue(criteria["ready_for_phase3_full_factorial"])
        self.assertEqual([row["component_config_id"] for row in rows], ["A1_B1_C1", "A2_B2_C2"])
        self.assertEqual(rows[0]["memory_backend"], "sqlite")
        self.assertEqual(rows[1]["memory_backend"], "vector")
        self.assertEqual(rows[1]["retrieval_strategy"], "embedding")
        self.assertEqual(rows[1]["scheduling_policy"], "rule_based")

        self.assertIn("Phase 2 Integration Baseline Exit Report", exit_report)
        self.assertIn("A1_B1_C1", exit_report)
        self.assertIn("A2_B2_C2", exit_report)
        self.assertIn("ready_for_phase3_full_factorial", exit_report)
        self.assertIn("full `2^3` factorial experiment", exit_report)

    def test_phase2_integration_baseline_validates_each_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_phase2_integration_baseline(
                task_path=TASK_PATH,
                run_config_path=CONFIG_PATH,
                component_config_paths=COMPONENT_PATHS,
                tool_spec_paths=TOOL_SPEC_PATHS,
                artifact_root=Path(directory),
            )

            for run in result.run_results:
                with self.subTest(config_id=run.component_bundle.config_id):
                    self.assertTrue(run.artifact_paths.trace.exists())
                    self.assertTrue(run.artifact_paths.verification.exists())
                    self.assertTrue(run.artifact_paths.metrics.exists())
                    self.assertTrue(run.artifact_paths.report.exists())
                    self.assertTrue(run.artifact_paths.manifest.exists())
                    validation = result.artifact_validations[run.trace.run_id]
                    self.assertTrue(validation.passed)
                    self.assertEqual(validation.issues, [])

    def test_phase2_integration_cli_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = cli_main(
                    [
                        "run-phase2-integration",
                        "--task",
                        str(TASK_PATH),
                        "--config",
                        str(CONFIG_PATH),
                        "--component",
                        str(COMPONENT_PATHS[0]),
                        "--component",
                        str(COMPONENT_PATHS[1]),
                        "--tool-spec",
                        str(TOOL_SPEC_PATHS[0]),
                        "--tool-spec",
                        str(TOOL_SPEC_PATHS[1]),
                        "--artifact-root",
                        directory,
                    ]
                )
            comparison_exists = Path(json.loads(stdout.getvalue())["comparison_summary"]).exists()
            exit_report_exists = Path(json.loads(stdout.getvalue())["exit_report"]).exists()

        payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["run_count"], 2)
        self.assertEqual(payload["component_config_ids"], ["A1_B1_C1", "A2_B2_C2"])
        self.assertEqual(payload["task_success_rate"], 1.0)
        self.assertEqual(payload["artifact_validation_pass_rate"], 1.0)
        self.assertTrue(payload["ready_for_phase3_full_factorial"])
        self.assertTrue(comparison_exists)
        self.assertTrue(exit_report_exists)

    def test_phase2_integration_script_runs_with_artifact_root_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ)
            env["AVF_ARTIFACT_ROOT"] = directory
            env["PYTHONPATH"] = "src"

            completed = subprocess.run(
                [str(ROOT / "scripts/run-phase2-integration.sh")],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["run_count"], 2)
        self.assertEqual(payload["component_config_ids"], ["A1_B1_C1", "A2_B2_C2"])
        self.assertTrue(payload["ready_for_phase3_full_factorial"])


if __name__ == "__main__":
    unittest.main()
