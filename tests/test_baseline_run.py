from __future__ import annotations

import json
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from avf.cli import main as cli_main  # noqa: E402
from avf.contracts import MetricResult, RunTrace, VerificationResult  # noqa: E402
from avf.orchestration import run_phase1_baseline  # noqa: E402


TASK_PATH = ROOT / "test_data/tasks/memory_recall_001.json"
CONFIG_PATH = ROOT / "test_data/configs/baseline_seed_001.json"
COMPONENT_PATH = ROOT / "test_data/components/A1_B1_C1.json"
TOOL_SPEC_PATHS = [
    ROOT / "test_data/tool_specs/memory.write.json",
    ROOT / "test_data/tool_specs/memory.query.json",
]


class Phase1BaselineRunTests(unittest.TestCase):
    def test_baseline_run_writes_trace_verification_metrics_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_phase1_baseline(
                task_path=TASK_PATH,
                run_config_path=CONFIG_PATH,
                component_config_path=COMPONENT_PATH,
                tool_spec_paths=TOOL_SPEC_PATHS,
                artifact_root=Path(directory),
            )

            self.assertTrue(result.artifact_paths.trace.exists())
            self.assertTrue(result.artifact_paths.verification.exists())
            self.assertTrue(result.artifact_paths.metrics.exists())
            self.assertTrue(result.artifact_paths.report.exists())

            trace = RunTrace.from_dict(_read_json(result.artifact_paths.trace))
            verification = VerificationResult.from_dict(_read_json(result.artifact_paths.verification))
            metrics = MetricResult.from_dict(_read_json(result.artifact_paths.metrics))
            report = result.artifact_paths.report.read_text(encoding="utf-8")

        self.assertEqual(trace.run_id, result.trace.run_id)
        self.assertTrue(verification.passed)
        self.assertTrue(metrics.task_success)
        self.assertEqual(metrics.step_count, 3)
        self.assertEqual(metrics.tool_call_count, 2)
        self.assertIn("Task success", report)
        self.assertIn("memory.write", report)
        self.assertIn("memory.query", report)
        self.assertIn("rule_based_success_criteria_v1", report)

    def test_baseline_run_artifact_contents_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = run_phase1_baseline(
                task_path=TASK_PATH,
                run_config_path=CONFIG_PATH,
                component_config_path=COMPONENT_PATH,
                tool_spec_paths=TOOL_SPEC_PATHS,
                artifact_root=Path(first_dir),
            )
            second = run_phase1_baseline(
                task_path=TASK_PATH,
                run_config_path=CONFIG_PATH,
                component_config_path=COMPONENT_PATH,
                tool_spec_paths=TOOL_SPEC_PATHS,
                artifact_root=Path(second_dir),
            )
            first_contents = _artifact_contents(first)
            second_contents = _artifact_contents(second)

        self.assertEqual(first.trace.run_id, second.trace.run_id)
        self.assertEqual(first_contents, second_contents)

    def test_run_baseline_cli_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = cli_main(
                    [
                        "run-baseline",
                        "--task",
                        str(TASK_PATH),
                        "--config",
                        str(CONFIG_PATH),
                        "--components",
                        str(COMPONENT_PATH),
                        "--tool-spec",
                        str(TOOL_SPEC_PATHS[0]),
                        "--tool-spec",
                        str(TOOL_SPEC_PATHS[1]),
                        "--artifact-root",
                        directory,
                    ]
                )
            root = Path(directory)
            traces = list((root / "traces").glob("*.json"))
            results = list((root / "results").glob("*.json"))
            reports = list((root / "reports").glob("*.md"))

        self.assertEqual(exit_code, 0)
        self.assertTrue(json.loads(output.getvalue())["task_success"])
        self.assertEqual(len(traces), 1)
        self.assertEqual(len(results), 2)
        self.assertEqual(len(reports), 1)

    def test_phase1_baseline_script_runs_with_artifact_root_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ)
            env["AVF_ARTIFACT_ROOT"] = directory
            env["PYTHONPATH"] = "src"

            completed = subprocess.run(
                [str(ROOT / "scripts/run-phase1-baseline.sh")],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            root = Path(directory)
            traces = list((root / "traces").glob("*.json"))
            results = list((root / "results").glob("*.json"))
            reports = list((root / "reports").glob("*.md"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(len(traces), 1)
        self.assertEqual(len(results), 2)
        self.assertEqual(len(reports), 1)
        self.assertTrue(json.loads(completed.stdout)["task_success"])


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_contents(result: object) -> dict:
    return {
        "trace": result.artifact_paths.trace.read_text(encoding="utf-8"),
        "verification": result.artifact_paths.verification.read_text(encoding="utf-8"),
        "metrics": result.artifact_paths.metrics.read_text(encoding="utf-8"),
        "report": result.artifact_paths.report.read_text(encoding="utf-8"),
    }


if __name__ == "__main__":
    unittest.main()
