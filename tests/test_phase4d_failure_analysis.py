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
)
from avf.cli import main as cli_main  # noqa: E402
from avf.contracts import SCHEMA_VERSION  # noqa: E402
from avf.orchestration import (  # noqa: E402
    freeze_phase3c_dataset,
    load_experiment_config,
    run_phase3b_pilot_qa,
    run_phase3d_readiness_review,
)


EXPERIMENT_CONFIG_PATH = ROOT / "test_data/experiments/phase3_full_factorial_v1.json"


class Phase4DFailureAnalysisTests(unittest.TestCase):
    def test_phase4d_writes_failure_analysis_and_final_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            metrics_table = _prepare_phase4d_inputs(Path(directory))
            result = write_phase4d_failure_analysis_report(
                metrics_table_path=metrics_table,
                analysis_root=Path(directory) / "analysis",
                generated_at="2026-06-08T00:00:00Z",
                code_version="phase4d_test",
            )
            failure_analysis = json.loads(result.artifacts.failure_analysis_json.read_text(encoding="utf-8"))
            failure_md = result.artifacts.failure_analysis_markdown.read_text(encoding="utf-8")
            analysis_report = result.artifacts.analysis_report.read_text(encoding="utf-8")

        self.assertEqual(result.dataset_id, "phase3_full_factorial_v1_dataset_v1")
        self.assertEqual(failure_analysis["run_count"], 8)
        self.assertEqual(failure_analysis["ordinary_task_outcome_count"], 8)
        self.assertEqual(failure_analysis["taxonomy_counts"]["passed"], 8)
        self.assertEqual(failure_analysis["taxonomy_counts"]["infrastructure_failure"], 0)
        self.assertEqual(failure_analysis["failure_note_count"], 0)
        self.assertEqual(failure_analysis["rerun_record_count"], 0)
        self.assertFalse(failure_analysis["infrastructure_separation"]["counted_as_ordinary_task_outcomes"])
        self.assertTrue(
            failure_analysis["analysis_acceptance_criteria"][
                "infrastructure_failures_not_counted_as_task_outcomes"
            ]
        )
        self.assertTrue(failure_analysis["analysis_acceptance_criteria"]["failure_notes_consumed"])
        self.assertTrue(failure_analysis["limitations"]["descriptive_only"])
        self.assertEqual(failure_analysis["limitations"]["claim_level"], "descriptive")
        self.assertIn("Phase 4D Failure Analysis", failure_md)
        self.assertIn("Phase 4 Analysis Report", analysis_report)
        self.assertIn("Claim level", analysis_report)
        self.assertIn("descriptive", analysis_report)

    def test_phase4d_cli_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            metrics_table = _prepare_phase4d_inputs(Path(directory))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = cli_main(
                    [
                        "write-analysis-report",
                        "--metrics-table",
                        str(metrics_table),
                        "--analysis-root",
                        str(Path(directory) / "analysis"),
                        "--generated-at",
                        "2026-06-08T00:00:00Z",
                        "--code-version",
                        "phase4d_cli",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            failure_json_exists = Path(payload["failure_analysis_json"]).exists()
            failure_md_exists = Path(payload["failure_analysis_markdown"]).exists()
            report_exists = Path(payload["analysis_report"]).exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["run_count"], 8)
        self.assertEqual(payload["ordinary_task_outcome_count"], 8)
        self.assertEqual(payload["infrastructure_failure_count"], 0)
        self.assertTrue(payload["descriptive_only"])
        self.assertTrue(failure_json_exists)
        self.assertTrue(failure_md_exists)
        self.assertTrue(report_exists)

    def test_phase4d_links_exclusion_and_rerun_decisions_to_qa_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            metrics_table = _prepare_phase4d_inputs(root)
            experiment_dir = root / "experiments/phase3_full_factorial_v1"
            metrics_payload = json.loads(metrics_table.read_text(encoding="utf-8"))
            run_id = metrics_payload["rows"][0]["run_id"]
            _write_failure_notes_with_rerun_decision(experiment_dir / "failure_notes.json", run_id)
            _write_rerun_records(experiment_dir / "rerun_records.json", run_id)

            result = write_phase4d_failure_analysis_report(
                metrics_table_path=metrics_table,
                analysis_root=root / "analysis",
                generated_at="2026-06-08T00:00:00Z",
                code_version="phase4d_qa_link_test",
            )
            links = result.failure_analysis["qa_decision_links"]

        self.assertEqual(result.failure_analysis["failure_note_count"], 1)
        self.assertEqual(result.failure_analysis["rerun_record_count"], 1)
        self.assertEqual(len(links), 2)
        self.assertTrue(all(link["linked_to_qa_artifact"] for link in links))
        self.assertTrue(
            result.failure_analysis["analysis_acceptance_criteria"][
                "exclusion_and_rerun_decisions_linked_to_qa_artifacts"
            ]
        )

    def test_phase4d_script_runs_phase4c_prerequisite_and_final_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ)
            env["AVF_ARTIFACT_ROOT"] = directory
            env["AVF_ANALYSIS_ROOT"] = str(Path(directory) / "analysis")
            env["PYTHONPATH"] = "src"

            completed = subprocess.run(
                [str(ROOT / "scripts/run-phase4d-analysis-report.sh")],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout) if completed.stdout else {}
            report_exists = Path(str(payload.get("analysis_report", ""))).exists()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["run_count"], 8)
        self.assertEqual(payload["ordinary_task_outcome_count"], 8)
        self.assertTrue(payload["descriptive_only"])
        self.assertTrue(report_exists)


def _prepare_phase4d_inputs(artifact_root: Path) -> Path:
    config = load_experiment_config(EXPERIMENT_CONFIG_PATH).with_overrides(artifact_root=artifact_root)
    run_phase3b_pilot_qa(
        config=config,
        experiment_config_path=EXPERIMENT_CONFIG_PATH,
        timestamp="2026-06-07T00:00:00Z",
        commit_hash="pilot_commit",
        operator_notes="phase4d test pilot",
    )
    freeze_phase3c_dataset(
        config=config,
        experiment_config_path=EXPERIMENT_CONFIG_PATH,
        frozen_at="2026-06-07T00:00:00Z",
        commit_hash="freeze_commit",
        operator_notes="phase4d test freeze",
    )
    run_phase3d_readiness_review(
        config=config,
        operator_notes="phase4d readiness prerequisite",
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
    return phase4a.artifacts.metrics_table_json


def _write_failure_notes_with_rerun_decision(path: Path, run_id: str) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "record_count": 1,
        "records": [
            {
                "schema_version": SCHEMA_VERSION,
                "run_id": run_id,
                "component_config_id": "A1_B1_C1",
                "task_id": "memory_recall_001",
                "seed": 42,
                "perturbation_schedule_id": "schedule_none_v1",
                "failure_class": "artifact_failure",
                "observed_symptom": "simulated rerun decision for Phase 4D QA link test",
                "root_cause": "test_fixture",
                "dataset_decision": "rerun",
                "evidence_paths": [f"traces/{run_id}.json"],
            }
        ],
        "templates": [],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_rerun_records(path: Path, run_id: str) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "record_count": 1,
        "records": [
            {
                "schema_version": SCHEMA_VERSION,
                "rerun_id": "rerun_phase4d_test_001",
                "original_run_id": run_id,
                "component_config_id": "A1_B1_C1",
                "task_id": "memory_recall_001",
                "seed": 42,
                "perturbation_schedule_id": "schedule_none_v1",
                "reason": "simulated rerun record for Phase 4D QA link test",
                "decision": "overwrite",
                "operator_notes": "unit test rerun linkage",
                "timestamp": "2026-06-08T00:00:00Z",
                "commit_hash": "phase4d_test",
            }
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
