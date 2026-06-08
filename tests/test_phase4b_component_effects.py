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

from avf.analysis import analyze_phase4a_dataset, summarize_phase4b_component_effects  # noqa: E402
from avf.cli import main as cli_main  # noqa: E402
from avf.orchestration import (  # noqa: E402
    freeze_phase3c_dataset,
    load_experiment_config,
    run_phase3b_pilot_qa,
    run_phase3d_readiness_review,
)


EXPERIMENT_CONFIG_PATH = ROOT / "test_data/experiments/phase3_full_factorial_v1.json"


class Phase4BComponentEffectTests(unittest.TestCase):
    def test_phase4b_writes_component_effect_interaction_and_dissertation_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            metrics_table = _prepare_phase4b_metrics_table(Path(directory))
            result = summarize_phase4b_component_effects(
                metrics_table_path=metrics_table,
                analysis_root=Path(directory) / "analysis",
                generated_at="2026-06-08T00:00:00Z",
                code_version="phase4b_test",
            )
            component_effects = json.loads(result.artifacts.component_effects_json.read_text(encoding="utf-8"))
            interactions = json.loads(result.artifacts.interaction_summary_json.read_text(encoding="utf-8"))
            component_md = result.artifacts.component_effects_markdown.read_text(encoding="utf-8")
            interaction_md = result.artifacts.interaction_summary_markdown.read_text(encoding="utf-8")
            dissertation_tables = result.artifacts.dissertation_tables.read_text(encoding="utf-8")

        self.assertEqual(result.dataset_id, "phase3_full_factorial_v1_dataset_v1")
        self.assertEqual(component_effects["complete_block_count"], 1)
        self.assertEqual(component_effects["incomplete_block_count"], 0)
        self.assertTrue(component_effects["limitations"]["descriptive_only"])
        self.assertFalse(component_effects["limitations"]["confidence_intervals_reported"])
        self.assertTrue(component_effects["analysis_acceptance_criteria"]["component_effects_traceable_to_run_ids"])
        self.assertTrue(component_effects["analysis_acceptance_criteria"]["current_small_sample_labelled_descriptive"])
        self.assertEqual(len(component_effects["factor_definitions"]), 3)
        self.assertEqual(len(component_effects["matched_blocks"]), 1)

        main_effects = component_effects["main_effects"]
        task_success_effects = [
            effect
            for effect in main_effects
            if effect["metric_name"] == "task_success"
        ]
        self.assertEqual({effect["factor_id"] for effect in task_success_effects}, {"A", "B", "C"})
        self.assertTrue(all(effect["effect"] == 0.0 for effect in task_success_effects))
        self.assertTrue(all(len(effect["run_ids"]) == 8 for effect in task_success_effects))

        interaction_ids = {
            interaction["interaction_id"]
            for interaction in interactions["interactions"]
            if interaction["metric_name"] == "task_success"
        }
        self.assertEqual(interaction_ids, {"A:B", "A:C", "B:C", "A:B:C"})
        self.assertEqual(interactions["complete_block_count"], 1)
        self.assertIn("Phase 4B Component Effect Summaries", component_md)
        self.assertIn("Phase 4B Interaction Summary", interaction_md)
        self.assertIn("Table 2: Main Effects", dissertation_tables)
        self.assertIn("descriptive", dissertation_tables)

    def test_phase4b_cli_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            metrics_table = _prepare_phase4b_metrics_table(Path(directory))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = cli_main(
                    [
                        "summarize-component-effects",
                        "--metrics-table",
                        str(metrics_table),
                        "--analysis-root",
                        str(Path(directory) / "analysis"),
                        "--generated-at",
                        "2026-06-08T00:00:00Z",
                        "--code-version",
                        "phase4b_cli",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            component_effects_exists = Path(payload["component_effects_json"]).exists()
            interaction_summary_exists = Path(payload["interaction_summary_json"]).exists()
            dissertation_tables_exists = Path(payload["dissertation_tables"]).exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["complete_block_count"], 1)
        self.assertEqual(payload["incomplete_block_count"], 0)
        self.assertTrue(payload["descriptive_only"])
        self.assertGreater(payload["main_effect_count"], 0)
        self.assertGreater(payload["interaction_count"], 0)
        self.assertTrue(component_effects_exists)
        self.assertTrue(interaction_summary_exists)
        self.assertTrue(dissertation_tables_exists)

    def test_phase4b_flags_and_excludes_incomplete_matched_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            metrics_table = _prepare_phase4b_metrics_table(root)
            payload = json.loads(metrics_table.read_text(encoding="utf-8"))
            payload["rows"] = [
                row
                for row in payload["rows"]
                if row["component_config_id"] != "A2_B2_C2"
            ]
            payload["row_count"] = len(payload["rows"])
            metrics_table.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            result = summarize_phase4b_component_effects(
                metrics_table_path=metrics_table,
                analysis_root=root / "analysis",
                generated_at="2026-06-08T00:00:00Z",
                code_version="phase4b_incomplete",
            )
            component_effects = result.component_effects

        self.assertEqual(component_effects["complete_block_count"], 0)
        self.assertEqual(component_effects["incomplete_block_count"], 1)
        self.assertEqual(component_effects["main_effects"], [])
        self.assertIn("A2_B2_C2", component_effects["incomplete_blocks"][0]["missing_component_config_ids"])
        self.assertTrue(component_effects["analysis_acceptance_criteria"]["incomplete_blocks_flagged"])
        self.assertTrue(component_effects["analysis_acceptance_criteria"]["incomplete_blocks_excluded_from_contrasts"])

    def test_phase4b_script_runs_phase4a_prerequisite_and_effect_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ)
            env["AVF_ARTIFACT_ROOT"] = directory
            env["AVF_ANALYSIS_ROOT"] = str(Path(directory) / "analysis")
            env["PYTHONPATH"] = "src"

            completed = subprocess.run(
                [str(ROOT / "scripts/run-phase4b-component-effects.sh")],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout) if completed.stdout else {}
            component_effects_exists = Path(str(payload.get("component_effects_json", ""))).exists()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["complete_block_count"], 1)
        self.assertEqual(payload["incomplete_block_count"], 0)
        self.assertTrue(payload["descriptive_only"])
        self.assertTrue(component_effects_exists)


def _prepare_phase4b_metrics_table(artifact_root: Path) -> Path:
    config = load_experiment_config(EXPERIMENT_CONFIG_PATH).with_overrides(artifact_root=artifact_root)
    run_phase3b_pilot_qa(
        config=config,
        experiment_config_path=EXPERIMENT_CONFIG_PATH,
        timestamp="2026-06-07T00:00:00Z",
        commit_hash="pilot_commit",
        operator_notes="phase4b test pilot",
    )
    freeze_phase3c_dataset(
        config=config,
        experiment_config_path=EXPERIMENT_CONFIG_PATH,
        frozen_at="2026-06-07T00:00:00Z",
        commit_hash="freeze_commit",
        operator_notes="phase4b test freeze",
    )
    run_phase3d_readiness_review(
        config=config,
        operator_notes="phase4b readiness prerequisite",
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
