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

from avf.analysis import analyze_phase4a_dataset, diagnose_phase4c_trajectories  # noqa: E402
from avf.cli import main as cli_main  # noqa: E402
from avf.orchestration import (  # noqa: E402
    freeze_phase3c_dataset,
    load_experiment_config,
    run_phase3b_pilot_qa,
    run_phase3d_readiness_review,
)


EXPERIMENT_CONFIG_PATH = ROOT / "test_data/experiments/phase3_full_factorial_v1.json"


class Phase4CTrajectoryDiagnosticTests(unittest.TestCase):
    def test_phase4c_writes_trace_derived_json_and_markdown_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            metrics_table = _prepare_phase4c_metrics_table(Path(directory))
            result = diagnose_phase4c_trajectories(
                metrics_table_path=metrics_table,
                analysis_root=Path(directory) / "analysis",
                generated_at="2026-06-08T00:00:00Z",
                code_version="phase4c_test",
            )
            diagnostics = json.loads(result.artifacts.trajectory_diagnostics_json.read_text(encoding="utf-8"))
            markdown = result.artifacts.trajectory_diagnostics_markdown.read_text(encoding="utf-8")

        self.assertEqual(result.dataset_id, "phase3_full_factorial_v1_dataset_v1")
        self.assertEqual(diagnostics["diagnostic_row_count"], 8)
        self.assertEqual(diagnostics["scope_counts"]["agent_behavior"], 8)
        self.assertIn("heuristic_definitions", diagnostics)
        self.assertTrue(diagnostics["analysis_acceptance_criteria"]["diagnostics_derived_from_runtrace_artifacts"])
        self.assertTrue(diagnostics["analysis_acceptance_criteria"]["heuristic_definitions_documented"])
        self.assertTrue(diagnostics["analysis_acceptance_criteria"]["agent_behavior_and_infrastructure_issues_distinguished"])

        first = diagnostics["rows"][0]
        self.assertEqual(first["diagnostic_scope"], "agent_behavior")
        self.assertEqual(first["action_count"], 3)
        self.assertEqual(first["tool_call_count"], 2)
        self.assertEqual(first["tool_sequence"], ["memory.write", "memory.query"])
        self.assertEqual(first["repeated_tool_call_count"], 0)
        self.assertEqual(first["repeated_observation_count"], 0)
        self.assertEqual(first["goal_drift"], 0.0)
        self.assertEqual(first["recovery_steps"], 0)
        self.assertTrue(first["final_answer_present"])
        self.assertTrue(first["trace_drilldown"]["tool_call_event_ids"])
        self.assertIn("Phase 4C Trajectory Diagnostics", markdown)
        self.assertIn("Heuristic Definitions", markdown)

    def test_phase4c_cli_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            metrics_table = _prepare_phase4c_metrics_table(Path(directory))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = cli_main(
                    [
                        "diagnose-trajectories",
                        "--metrics-table",
                        str(metrics_table),
                        "--analysis-root",
                        str(Path(directory) / "analysis"),
                        "--generated-at",
                        "2026-06-08T00:00:00Z",
                        "--code-version",
                        "phase4c_cli",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            diagnostics_exists = Path(payload["trajectory_diagnostics_json"]).exists()
            markdown_exists = Path(payload["trajectory_diagnostics_markdown"]).exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["diagnostic_row_count"], 8)
        self.assertEqual(payload["agent_behavior_row_count"], 8)
        self.assertTrue(diagnostics_exists)
        self.assertTrue(markdown_exists)

    def test_phase4c_counts_repeated_tools_and_observations_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            metrics_table = _prepare_phase4c_metrics_table(root)
            table = json.loads(metrics_table.read_text(encoding="utf-8"))
            first_row = table["rows"][0]
            trace_path = Path(first_row["artifact_paths"]["trace"])
            trace_payload = json.loads(trace_path.read_text(encoding="utf-8"))
            tool_call = next(event for event in trace_payload["events"] if event["event_type"] == "tool_call")
            observation = next(event for event in trace_payload["events"] if event["event_type"] == "observation")
            duplicated_tool_call = dict(tool_call)
            duplicated_tool_call["event_id"] = f"{trace_payload['run_id']}_event_901"
            duplicated_tool_call["timestamp"] = "1970-01-01T00:15:01Z"
            duplicated_observation = dict(observation)
            duplicated_observation["event_id"] = f"{trace_payload['run_id']}_event_902"
            duplicated_observation["timestamp"] = "1970-01-01T00:15:02Z"

            tool_index = trace_payload["events"].index(tool_call)
            observation_index = trace_payload["events"].index(observation)
            trace_payload["events"].insert(tool_index + 1, duplicated_tool_call)
            trace_payload["events"].insert(observation_index + 2, duplicated_observation)
            trace_path.write_text(json.dumps(trace_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            result = diagnose_phase4c_trajectories(
                metrics_table_path=metrics_table,
                analysis_root=root / "analysis",
                generated_at="2026-06-08T00:00:00Z",
                code_version="phase4c_repeat_test",
            )
            diagnostics = result.trajectory_diagnostics
            first_diagnostic = next(
                row
                for row in diagnostics["rows"]
                if row["run_id"] == first_row["run_id"]
            )

        self.assertEqual(first_diagnostic["repeated_tool_call_count"], 1)
        self.assertEqual(first_diagnostic["repeated_observation_count"], 1)
        self.assertEqual(first_diagnostic["tool_sequence"][0:2], ["memory.write", "memory.write"])

    def test_phase4c_script_runs_phase4b_prerequisite_and_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ)
            env["AVF_ARTIFACT_ROOT"] = directory
            env["AVF_ANALYSIS_ROOT"] = str(Path(directory) / "analysis")
            env["PYTHONPATH"] = "src"

            completed = subprocess.run(
                [str(ROOT / "scripts/run-phase4c-trajectory-diagnostics.sh")],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout) if completed.stdout else {}
            diagnostics_exists = Path(str(payload.get("trajectory_diagnostics_json", ""))).exists()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["diagnostic_row_count"], 8)
        self.assertEqual(payload["agent_behavior_row_count"], 8)
        self.assertTrue(diagnostics_exists)


def _prepare_phase4c_metrics_table(artifact_root: Path) -> Path:
    config = load_experiment_config(EXPERIMENT_CONFIG_PATH).with_overrides(artifact_root=artifact_root)
    run_phase3b_pilot_qa(
        config=config,
        experiment_config_path=EXPERIMENT_CONFIG_PATH,
        timestamp="2026-06-07T00:00:00Z",
        commit_hash="pilot_commit",
        operator_notes="phase4c test pilot",
    )
    freeze_phase3c_dataset(
        config=config,
        experiment_config_path=EXPERIMENT_CONFIG_PATH,
        frozen_at="2026-06-07T00:00:00Z",
        commit_hash="freeze_commit",
        operator_notes="phase4c test freeze",
    )
    run_phase3d_readiness_review(
        config=config,
        operator_notes="phase4c readiness prerequisite",
    )
    dataset_index = artifact_root / "experiments/phase3_full_factorial_v1/dataset_index.json"
    result = analyze_phase4a_dataset(
        dataset_index_path=dataset_index,
        artifact_root=artifact_root,
        analysis_root=artifact_root / "analysis",
        generated_at="2026-06-08T00:00:00Z",
        code_version="phase4a_test",
    )
    return result.artifacts.metrics_table_json


if __name__ == "__main__":
    unittest.main()
