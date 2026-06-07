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


TASK_PATH = ROOT / "test_data/tasks/memory_recall_001.json"
CONFIG_PATH = ROOT / "test_data/configs/baseline_seed_001.json"
TOOL_SPEC_PATHS = [
    ROOT / "test_data/tool_specs/memory.write.json",
    ROOT / "test_data/tool_specs/memory.query.json",
]

EXPECTED_FACTORS = {
    "A1_B1_C1": ("sqlite", "bm25", "sequential"),
    "A1_B2_C2": ("sqlite", "embedding", "rule_based"),
    "A2_B2_C2": ("vector", "embedding", "rule_based"),
}


class Phase2HComponentAwareBaselineTests(unittest.TestCase):
    def test_runner_selects_components_from_distinct_component_configs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = _run_cell("A1_B1_C1", root / "A1_B1_C1")
            variant = _run_cell("A2_B2_C2", root / "A2_B2_C2")

            baseline_report = baseline.artifact_paths.report.read_text(encoding="utf-8")
            variant_report = variant.artifact_paths.report.read_text(encoding="utf-8")

        self.assertTrue(baseline.metrics.task_success)
        self.assertTrue(variant.metrics.task_success)
        self.assertNotEqual(baseline.trace.run_id, variant.trace.run_id)

        self.assertEqual(baseline.trace.task_id, variant.trace.task_id)
        self.assertEqual(baseline.trace.run_config_id, variant.trace.run_config_id)
        self.assertEqual(baseline.trace.seed, variant.trace.seed)
        self.assertEqual(baseline.trace.perturbation_schedule_id, variant.trace.perturbation_schedule_id)
        self.assertEqual(_tool_call_names(baseline), _tool_call_names(variant))

        self.assertEqual(_bundle_factors(baseline), EXPECTED_FACTORS["A1_B1_C1"])
        self.assertEqual(_bundle_factors(variant), EXPECTED_FACTORS["A2_B2_C2"])
        self.assertEqual(_component_bundle_event_payload(baseline)["component_bundle"], baseline.component_bundle.to_dict())
        self.assertEqual(_component_bundle_event_payload(variant)["component_bundle"], variant.component_bundle.to_dict())

        self.assertIn("Component Selection", baseline_report)
        self.assertIn("sqlite_memory_backend", baseline_report)
        self.assertIn("Component Selection", variant_report)
        self.assertIn("vector_memory_backend", variant_report)
        self.assertIn("embedding_retrieval", variant_report)
        self.assertIn("rule_based_scheduler", variant_report)

    def test_component_aware_baseline_is_reproducible_for_same_component_cell(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = _run_cell("A2_B2_C2", Path(first_dir))
            second = _run_cell("A2_B2_C2", Path(second_dir))
            first_contents = _artifact_contents(first)
            second_contents = _artifact_contents(second)

        self.assertEqual(first.trace.run_id, second.trace.run_id)
        self.assertEqual(_bundle_factors(first), EXPECTED_FACTORS["A2_B2_C2"])
        self.assertEqual(first_contents, second_contents)

    def test_run_baseline_cli_summary_identifies_selected_component_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = cli_main(
                    [
                        "run-baseline",
                        "--task",
                        str(TASK_PATH),
                        "--config",
                        str(CONFIG_PATH),
                        "--components",
                        str(_component_path("A1_B2_C2")),
                        "--tool-spec",
                        str(TOOL_SPEC_PATHS[0]),
                        "--tool-spec",
                        str(TOOL_SPEC_PATHS[1]),
                        "--artifact-root",
                        directory,
                    ]
                )

        payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["component_config_id"], "A1_B2_C2")
        self.assertTrue(payload["task_success"])
        self.assertTrue(payload["verification_passed"])
        self.assertEqual(payload["component_bundle"]["memory"]["variant"], "sqlite")
        self.assertEqual(payload["component_bundle"]["retrieval"]["variant"], "embedding")
        self.assertEqual(payload["component_bundle"]["scheduling"]["variant"], "rule_based")


def _run_cell(config_id: str, artifact_root: Path) -> object:
    return run_component_aware_baseline(
        task_path=TASK_PATH,
        run_config_path=CONFIG_PATH,
        component_config_path=_component_path(config_id),
        tool_spec_paths=TOOL_SPEC_PATHS,
        artifact_root=artifact_root,
    )


def _component_path(config_id: str) -> Path:
    return ROOT / "test_data/components" / f"{config_id}.json"


def _bundle_factors(result: object) -> tuple[str, str, str]:
    return (
        result.component_bundle.memory.variant,
        result.component_bundle.retrieval.variant,
        result.component_bundle.scheduling.variant,
    )


def _component_bundle_event_payload(result: object) -> dict:
    matches = [
        event.payload for event in result.trace.events
        if event.payload.get("stage") == "component_bundle"
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one component_bundle trace event, found {len(matches)}")
    return matches[0]


def _tool_call_names(result: object) -> list[str]:
    return [
        event.payload["tool_name"] for event in result.trace.events
        if event.event_type == "tool_call"
    ]


def _artifact_contents(result: object) -> dict:
    return {
        "trace": result.artifact_paths.trace.read_text(encoding="utf-8"),
        "verification": result.artifact_paths.verification.read_text(encoding="utf-8"),
        "metrics": result.artifact_paths.metrics.read_text(encoding="utf-8"),
        "report": result.artifact_paths.report.read_text(encoding="utf-8"),
        "manifest": result.artifact_paths.manifest.read_text(encoding="utf-8"),
    }


if __name__ == "__main__":
    unittest.main()
