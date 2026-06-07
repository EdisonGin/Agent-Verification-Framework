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
from avf.contracts import SCHEMA_VERSION, ValidationError  # noqa: E402
from avf.orchestration import (  # noqa: E402
    FailureNote,
    freeze_phase3c_dataset,
    freeze_phase3c_dataset_from_config,
    load_experiment_config,
    run_phase3b_pilot_qa,
    write_failure_notes_json,
)


EXPERIMENT_CONFIG_PATH = ROOT / "test_data/experiments/phase3_full_factorial_v1.json"


class Phase3CDatasetFreezeTests(unittest.TestCase):
    def test_dataset_freeze_writes_index_manifest_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = _run_pilot(Path(directory))
            result = freeze_phase3c_dataset(
                config=config,
                experiment_config_path=EXPERIMENT_CONFIG_PATH,
                dataset_id="phase3_test_dataset",
                frozen_at="2026-06-07T00:00:00Z",
                commit_hash="freeze_commit",
                operator_notes="unit test freeze",
            )
            dataset_index = json.loads(result.artifacts.dataset_index.read_text(encoding="utf-8"))
            manifest = json.loads(result.artifacts.frozen_dataset_manifest.read_text(encoding="utf-8"))
            report = result.artifacts.dataset_report.read_text(encoding="utf-8")

        self.assertTrue(result.validation.passed)
        self.assertEqual(dataset_index["dataset_id"], "phase3_test_dataset")
        self.assertEqual(dataset_index["commit_hash"], "freeze_commit")
        self.assertEqual(dataset_index["run_count"], 8)
        self.assertEqual(dataset_index["included_run_count"], 8)
        self.assertEqual(dataset_index["excluded_run_count"], 0)
        self.assertEqual(len(dataset_index["records"]), 8)
        self.assertTrue(all(record["inclusion_status"] == "included" for record in dataset_index["records"]))
        self.assertTrue(all(record["artifact_validation_passed"] for record in dataset_index["records"]))
        self.assertIn("trace", dataset_index["records"][0]["artifact_records"])
        self.assertIn("sha256", dataset_index["records"][0]["artifact_records"]["trace"])
        self.assertIn("manifest", dataset_index["records"][0]["artifact_records"])

        self.assertTrue(manifest["frozen"])
        self.assertEqual(manifest["dataset_id"], "phase3_test_dataset")
        self.assertEqual(manifest["commit_hash"], "freeze_commit")
        self.assertEqual(manifest["experiment_config_path"], str(EXPERIMENT_CONFIG_PATH))
        self.assertTrue(manifest["freeze_prerequisites"]["matrix_complete"])
        self.assertTrue(manifest["freeze_prerequisites"]["all_included_runs_have_valid_artifacts"])
        self.assertTrue(manifest["freeze_prerequisites"]["pilot_qa_ready"])
        self.assertIn("dataset_index", manifest["freeze_artifacts"])
        self.assertIn("experiment_config", manifest["source_artifacts"])

        self.assertIn("Phase 3C Frozen Dataset Report", report)
        self.assertIn("phase3_test_dataset", report)
        self.assertIn("Use `dataset_index.json` as the analysis entrypoint", report)

    def test_dataset_index_can_be_consumed_without_rerunning_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = _run_pilot(Path(directory))
            result = freeze_phase3c_dataset(
                config=config,
                experiment_config_path=EXPERIMENT_CONFIG_PATH,
                frozen_at="2026-06-07T00:00:00Z",
                commit_hash="freeze_commit",
            )
            dataset_index = json.loads(result.artifacts.dataset_index.read_text(encoding="utf-8"))

        first_record = dataset_index["records"][0]

        self.assertEqual(dataset_index["matrix_summary"]["row_count"], 8)
        self.assertEqual(dataset_index["qa_summary"]["ready_for_dataset_execution"], True)
        self.assertEqual(first_record["task_id"], "memory_recall_001")
        self.assertEqual(first_record["seed"], 42)
        self.assertEqual(first_record["perturbation_schedule_id"], "schedule_none_v1")
        self.assertEqual(first_record["component_config_id"], "A1_B1_C1")
        self.assertEqual(sorted(first_record["artifact_records"]), ["manifest", "metrics", "report", "trace", "verification"])

    def test_dataset_freeze_blocks_unresolved_infrastructure_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = _run_pilot(root)
            failure_notes_path = root / "experiments/phase3_full_factorial_v1/failure_notes.json"
            write_failure_notes_json(
                failure_notes_path,
                [
                    FailureNote(
                        schema_version=SCHEMA_VERSION,
                        run_id="run_e4b4e294123506ad",
                        component_config_id="A1_B1_C1",
                        task_id="memory_recall_001",
                        seed=42,
                        perturbation_schedule_id="schedule_none_v1",
                        failure_class="infrastructure_failure",
                        observed_symptom="simulated infrastructure interruption",
                        root_cause="unknown",
                        dataset_decision="block_freeze",
                        evidence_paths=["traces/run_e4b4e294123506ad.json"],
                    )
                ],
            )

            with self.assertRaises(ValidationError) as raised:
                freeze_phase3c_dataset(config=config, experiment_config_path=EXPERIMENT_CONFIG_PATH)

        self.assertIn("Dataset freeze blocked", str(raised.exception))
        self.assertIn("Unresolved infrastructure failure blocks dataset execution", str(raised.exception))

    def test_phase3c_cli_freezes_existing_pilot_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _run_pilot(Path(directory))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = cli_main(
                    [
                        "freeze-phase3c-dataset",
                        "--experiment-config",
                        str(EXPERIMENT_CONFIG_PATH),
                        "--artifact-root",
                        directory,
                        "--dataset-id",
                        "cli_dataset",
                        "--frozen-at",
                        "2026-06-07T00:00:00Z",
                        "--commit-hash",
                        "cli_freeze_commit",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            dataset_index_exists = Path(payload["dataset_index"]).exists()
            manifest_exists = Path(payload["frozen_dataset_manifest"]).exists()
            report_exists = Path(payload["dataset_report"]).exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["dataset_id"], "cli_dataset")
        self.assertEqual(payload["included_run_count"], 8)
        self.assertEqual(payload["excluded_run_count"], 0)
        self.assertTrue(payload["frozen"])
        self.assertTrue(dataset_index_exists)
        self.assertTrue(manifest_exists)
        self.assertTrue(report_exists)

    def test_phase3c_script_runs_pilot_and_freeze_with_artifact_root_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ)
            env["AVF_ARTIFACT_ROOT"] = directory
            env["PYTHONPATH"] = "src"

            completed = subprocess.run(
                [str(ROOT / "scripts/run-phase3c-freeze.sh")],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["included_run_count"], 8)
        self.assertEqual(payload["excluded_run_count"], 0)
        self.assertTrue(payload["frozen"])


def _run_pilot(artifact_root: Path) -> object:
    config = load_experiment_config(EXPERIMENT_CONFIG_PATH).with_overrides(artifact_root=artifact_root)
    run_phase3b_pilot_qa(
        config=config,
        experiment_config_path=EXPERIMENT_CONFIG_PATH,
        timestamp="2026-06-07T00:00:00Z",
        commit_hash="pilot_commit",
        operator_notes="phase3c test pilot",
    )
    return config


if __name__ == "__main__":
    unittest.main()
