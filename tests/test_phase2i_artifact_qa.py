from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from avf.cli import main as cli_main  # noqa: E402
from avf.orchestration import run_component_aware_baseline  # noqa: E402
from avf.storage import FileSystemResultsStore  # noqa: E402


TASK_PATH = ROOT / "test_data/tasks/memory_recall_001.json"
CONFIG_PATH = ROOT / "test_data/configs/baseline_seed_001.json"
COMPONENT_PATH = ROOT / "test_data/components/A1_B1_C1.json"
TOOL_SPEC_PATHS = [
    ROOT / "test_data/tool_specs/memory.write.json",
    ROOT / "test_data/tool_specs/memory.query.json",
]


class Phase2IArtifactQATests(unittest.TestCase):
    def test_baseline_run_writes_valid_artifact_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = _run_baseline(Path(directory))
            manifest = json.loads(result.artifact_paths.manifest.read_text(encoding="utf-8"))

        self.assertEqual(manifest["schema_version"], "1.0")
        self.assertEqual(manifest["manifest_version"], "1.0")
        self.assertEqual(manifest["run_id"], result.trace.run_id)
        self.assertEqual(manifest["rerun_policy"], "deterministic_overwrite")
        self.assertTrue(manifest["validation"]["passed"])
        self.assertEqual(manifest["validation"]["issues"], [])
        self.assertEqual(
            sorted(manifest["validation"]["artifacts"]),
            ["metrics", "report", "trace", "verification"],
        )
        self.assertEqual(manifest["validation"]["artifacts"]["trace"]["path"], f"traces/{result.trace.run_id}.json")

    def test_result_store_validates_generated_artifacts_as_a_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = _run_baseline(Path(directory))
            store = FileSystemResultsStore.from_artifact_root(Path(directory))
            validation = store.validate_run_artifacts(result.trace.run_id)

        self.assertTrue(validation.passed)
        self.assertEqual(validation.issues, [])
        self.assertEqual(sorted(validation.artifacts), ["metrics", "report", "trace", "verification"])
        self.assertTrue(all(record.sha256 for record in validation.artifacts.values()))

    def test_result_store_reports_missing_artifacts_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = _run_baseline(Path(directory))
            result.artifact_paths.report.unlink()
            store = FileSystemResultsStore.from_artifact_root(Path(directory))
            validation = store.validate_run_artifacts(result.trace.run_id)

        self.assertFalse(validation.passed)
        self.assertIn(f"Missing report artifact: reports/{result.trace.run_id}.md", validation.issues)

    def test_result_store_reports_run_id_mismatch_across_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = _run_baseline(Path(directory))
            metrics_payload = json.loads(result.artifact_paths.metrics.read_text(encoding="utf-8"))
            metrics_payload["run_id"] = "run_wrong_id"
            result.artifact_paths.metrics.write_text(
                json.dumps(metrics_payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            store = FileSystemResultsStore.from_artifact_root(Path(directory))
            validation = store.validate_run_artifacts(result.trace.run_id)

        self.assertFalse(validation.passed)
        self.assertIn(
            f"metrics artifact run_id mismatch: expected {result.trace.run_id}, found run_wrong_id",
            validation.issues,
        )
        self.assertIn("Artifact run_id values do not agree", validation.issues[-1])

    def test_repeated_runs_use_deterministic_overwrite_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact_root = Path(directory)
            first = _run_baseline(artifact_root)
            first_manifest_path = first.artifact_paths.manifest
            first_manifest = first_manifest_path.read_text(encoding="utf-8")
            second = _run_baseline(artifact_root)
            second_manifest = second.artifact_paths.manifest.read_text(encoding="utf-8")

        self.assertEqual(first.trace.run_id, second.trace.run_id)
        self.assertEqual(first_manifest_path, second.artifact_paths.manifest)
        self.assertEqual(first_manifest, second_manifest)

    def test_validate_artifacts_cli_reports_validation_summary_and_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = _run_baseline(Path(directory))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = cli_main(
                    [
                        "validate-artifacts",
                        "--artifact-root",
                        directory,
                        "--run-id",
                        result.trace.run_id,
                        "--write-manifest",
                    ]
                )

        payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["issues"], [])
        self.assertEqual(payload["run_id"], result.trace.run_id)
        self.assertTrue(payload["manifest"].endswith(f"{result.trace.run_id}.manifest.json"))


def _run_baseline(artifact_root: Path) -> object:
    return run_component_aware_baseline(
        task_path=TASK_PATH,
        run_config_path=CONFIG_PATH,
        component_config_path=COMPONENT_PATH,
        tool_spec_paths=TOOL_SPEC_PATHS,
        artifact_root=artifact_root,
    )


if __name__ == "__main__":
    unittest.main()
