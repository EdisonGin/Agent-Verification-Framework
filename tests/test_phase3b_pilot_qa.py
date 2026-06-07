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
    RerunRecord,
    load_experiment_config,
    read_failure_notes,
    read_rerun_records,
    run_phase3b_pilot_qa,
    validate_dataset_execution_gate,
    validate_failure_notes,
    validate_rerun_records,
    write_rerun_records,
)


EXPERIMENT_CONFIG_PATH = ROOT / "test_data/experiments/phase3_full_factorial_v1.json"


class Phase3BPilotQATests(unittest.TestCase):
    def test_pilot_runner_writes_pilot_log_rerun_records_and_failure_notes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = load_experiment_config(EXPERIMENT_CONFIG_PATH).with_overrides(artifact_root=Path(directory))
            result = run_phase3b_pilot_qa(
                config=config,
                experiment_config_path=EXPERIMENT_CONFIG_PATH,
                operator_notes="unit test pilot",
                known_limitations=["single deterministic task fixture"],
                timestamp="2026-06-07T00:00:00Z",
                commit_hash="test_commit",
            )
            qa_summary = json.loads(result.artifacts.qa_summary.read_text(encoding="utf-8"))
            rerun_payload = json.loads(result.artifacts.rerun_records.read_text(encoding="utf-8"))
            failure_payload = json.loads(result.artifacts.failure_notes_json.read_text(encoding="utf-8"))
            pilot_log = result.artifacts.pilot_log.read_text(encoding="utf-8")
            failure_notes_md = result.artifacts.failure_notes_markdown.read_text(encoding="utf-8")

        self.assertEqual(result.phase3a_result.matrix.row_count, 8)
        self.assertEqual(qa_summary["pilot_mode"], "full_factorial_pilot")
        self.assertEqual(qa_summary["expected_run_count"], 8)
        self.assertEqual(qa_summary["completed_run_count"], 8)
        self.assertEqual(qa_summary["commit_hash"], "test_commit")
        self.assertEqual(qa_summary["operator_notes"], "unit test pilot")
        self.assertEqual(qa_summary["failure_note_count"], 0)
        self.assertEqual(qa_summary["rerun_record_count"], 0)
        self.assertFalse(qa_summary["dataset_execution_blocked"])
        self.assertTrue(qa_summary["ready_for_dataset_execution"])
        self.assertEqual(qa_summary["pilot_decision"], "proceed_to_dataset_execution")
        self.assertEqual(rerun_payload["record_count"], 0)
        self.assertEqual(failure_payload["record_count"], 0)
        self.assertEqual(len(failure_payload["templates"]), 4)
        self.assertIn("Phase 3B Pilot QA Log", pilot_log)
        self.assertIn("test_commit", pilot_log)
        self.assertIn("unit test pilot", pilot_log)
        self.assertIn("No pilot failures recorded", pilot_log)
        self.assertIn("Phase 3B Failure Notes", failure_notes_md)
        self.assertIn("infrastructure_failure", failure_notes_md)

    def test_rerun_records_can_be_written_read_and_validated(self) -> None:
        record = RerunRecord(
            schema_version=SCHEMA_VERSION,
            rerun_id="rerun_001",
            original_run_id="run_example",
            component_config_id="A1_B1_C1",
            task_id="memory_recall_001",
            seed=42,
            perturbation_schedule_id="schedule_none_v1",
            reason="Artifact missing due to interrupted pilot execution",
            decision="overwrite",
            operator_notes="rerun same controlled cell",
            timestamp="2026-06-07T00:00:00Z",
            commit_hash="test_commit",
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rerun_records.json"
            write_rerun_records(path, [record])
            loaded = read_rerun_records(path)

        validation = validate_rerun_records(loaded)

        self.assertTrue(validation.passed)
        self.assertEqual(validation.issues, [])
        self.assertEqual(loaded, [record])

    def test_failure_notes_support_required_failure_classes_and_blocking_gate(self) -> None:
        notes = [
            _failure_note("run_task", "task_failure", "include"),
            _failure_note("run_verifier", "verifier_failure", "include"),
            _failure_note("run_artifact", "artifact_failure", "rerun"),
            _failure_note("run_infra", "infrastructure_failure", "block_freeze"),
        ]

        validation = validate_failure_notes(notes)
        gate = validate_dataset_execution_gate(notes)

        self.assertTrue(validation.passed)
        self.assertFalse(gate.passed)
        self.assertEqual(
            gate.issues,
            ["Unresolved infrastructure failure blocks dataset execution: run_infra"],
        )

    def test_failure_note_rejects_unknown_failure_class(self) -> None:
        payload = _failure_note("run_bad", "task_failure", "include").to_dict()
        payload["failure_class"] = "unknown_failure"

        with self.assertRaises(ValidationError):
            FailureNote.from_dict(payload)

    def test_phase3b_cli_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = cli_main(
                    [
                        "run-phase3b-pilot",
                        "--experiment-config",
                        str(EXPERIMENT_CONFIG_PATH),
                        "--artifact-root",
                        directory,
                        "--operator-notes",
                        "cli pilot",
                        "--known-limitation",
                        "single task fixture",
                        "--commit-hash",
                        "cli_commit",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            pilot_log_exists = Path(payload["pilot_log"]).exists()
            rerun_records_exists = Path(payload["rerun_records"]).exists()
            failure_notes_exists = Path(payload["failure_notes_json"]).exists()
            qa_summary_exists = Path(payload["qa_summary"]).exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["pilot_mode"], "full_factorial_pilot")
        self.assertEqual(payload["expected_run_count"], 8)
        self.assertEqual(payload["completed_run_count"], 8)
        self.assertEqual(payload["failure_note_count"], 0)
        self.assertEqual(payload["rerun_record_count"], 0)
        self.assertFalse(payload["dataset_execution_blocked"])
        self.assertTrue(payload["ready_for_dataset_execution"])
        self.assertTrue(pilot_log_exists)
        self.assertTrue(rerun_records_exists)
        self.assertTrue(failure_notes_exists)
        self.assertTrue(qa_summary_exists)

    def test_phase3b_script_runs_with_artifact_root_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ)
            env["AVF_ARTIFACT_ROOT"] = directory
            env["PYTHONPATH"] = "src"

            completed = subprocess.run(
                [str(ROOT / "scripts/run-phase3b-pilot.sh")],
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
        self.assertFalse(payload["dataset_execution_blocked"])
        self.assertTrue(payload["ready_for_dataset_execution"])


def _failure_note(run_id: str, failure_class: str, dataset_decision: str) -> FailureNote:
    return FailureNote(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        component_config_id="A1_B1_C1",
        task_id="memory_recall_001",
        seed=42,
        perturbation_schedule_id="schedule_none_v1",
        failure_class=failure_class,
        observed_symptom=f"{failure_class} observed",
        root_cause="unknown",
        dataset_decision=dataset_decision,
        evidence_paths=["traces/run_example.json"],
    )


if __name__ == "__main__":
    unittest.main()
