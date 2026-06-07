from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from avf.agents.components import ComponentFactory, ComponentRegistry, build_component_bundle  # noqa: E402
from avf.agents.memory import VectorMemory  # noqa: E402
from avf.agents.retrieval import EmbeddingRetriever  # noqa: E402
from avf.agents.scheduling import RuleBasedScheduler, SequentialScheduler  # noqa: E402
from avf.contracts import MetricResult, RunTrace, ValidationError, VerificationResult  # noqa: E402
from avf.orchestration import build_run_context, run_phase1_baseline  # noqa: E402
from avf.storage import FileSystemResultsStore, FileSystemTestDataRepository  # noqa: E402


class Phase2AStorageAndComponentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FileSystemTestDataRepository(ROOT / "test_data")
        self.task = self.repository.load_task_case("memory_recall_001.json")
        self.run_config = self.repository.load_run_config("baseline_seed_001.json")
        self.component_config = self.repository.load_component_config("A1_B1_C1.json")
        self.tool_specs = self.repository.load_tool_specs(["memory.write.json", "memory.query.json"])

    def test_test_data_repository_loads_existing_fixture_tree(self) -> None:
        summary = self.repository.validate()
        loaded = self.repository.load_tree()

        self.assertEqual(summary["tasks"], 1)
        self.assertEqual(summary["configs"], 1)
        self.assertEqual(summary["components"], 1)
        self.assertEqual(summary["tool_specs"], 2)
        self.assertEqual(loaded["tasks"][0].task_id, "memory_recall_001")

    def test_component_registry_resolves_current_baseline_cell(self) -> None:
        bundle = ComponentRegistry().resolve(self.component_config)

        self.assertEqual(bundle.config_id, "A1_B1_C1")
        self.assertEqual(bundle.memory.variant, "sqlite")
        self.assertEqual(bundle.memory.status, "available")
        self.assertEqual(bundle.memory.planned_phase, "Phase 2B")
        self.assertIsNotNone(bundle.memory_module)
        self.assertEqual(bundle.retrieval.variant, "bm25")
        self.assertEqual(bundle.retrieval.status, "available")
        self.assertEqual(bundle.retrieval.planned_phase, "Phase 2C")
        self.assertIsNotNone(bundle.retrieval_module)
        self.assertEqual(bundle.scheduling.variant, "sequential")
        self.assertEqual(bundle.scheduling.status, "available")
        self.assertIsInstance(bundle.scheduler, SequentialScheduler)

    def test_component_factory_helper_returns_deterministic_bundle(self) -> None:
        first = ComponentFactory().build(self.component_config)
        second = build_component_bundle(self.component_config)

        self.assertEqual(first.to_dict(), second.to_dict())

    def test_component_registry_resolves_vector_memory_backend(self) -> None:
        config = replace(self.component_config, memory_backend="vector")
        bundle = ComponentRegistry().resolve(config)

        self.assertEqual(bundle.memory.variant, "vector")
        self.assertEqual(bundle.memory.status, "available")
        self.assertEqual(bundle.memory.planned_phase, "Phase 2E")
        self.assertIsInstance(bundle.memory_module, VectorMemory)

    def test_component_registry_rejects_unknown_memory_variant(self) -> None:
        config = replace(self.component_config, memory_backend="redis")

        with self.assertRaisesRegex(ValidationError, "memory_backend=redis"):
            ComponentRegistry().resolve(config)

    def test_component_registry_resolves_embedding_retrieval_strategy(self) -> None:
        config = replace(self.component_config, retrieval_strategy="embedding")
        bundle = ComponentRegistry().resolve(config)

        self.assertEqual(bundle.retrieval.variant, "embedding")
        self.assertEqual(bundle.retrieval.status, "available")
        self.assertEqual(bundle.retrieval.planned_phase, "Phase 2F")
        self.assertIsInstance(bundle.retrieval_module, EmbeddingRetriever)

    def test_component_registry_rejects_unknown_retrieval_variant(self) -> None:
        config = replace(self.component_config, retrieval_strategy="hybrid")

        with self.assertRaisesRegex(ValidationError, "retrieval_strategy=hybrid"):
            ComponentRegistry().resolve(config)

    def test_component_registry_resolves_rule_based_scheduler(self) -> None:
        config = replace(self.component_config, scheduling_policy="rule_based")
        bundle = ComponentRegistry().resolve(config)

        self.assertEqual(bundle.scheduling.variant, "rule_based")
        self.assertEqual(bundle.scheduling.status, "available")
        self.assertEqual(bundle.scheduling.planned_phase, "Phase 2D")
        self.assertIsInstance(bundle.scheduler, RuleBasedScheduler)

    def test_component_registry_rejects_unknown_scheduling_variant(self) -> None:
        config = replace(self.component_config, scheduling_policy="dag")

        with self.assertRaisesRegex(ValidationError, "scheduling_policy=dag"):
            ComponentRegistry().resolve(config)

    def test_results_store_writes_baseline_artifact_contracts(self) -> None:
        context = build_run_context(self.task, self.run_config, self.component_config, self.tool_specs)

        with tempfile.TemporaryDirectory() as directory:
            run = run_phase1_baseline(
                task_path=self.repository.task_path("memory_recall_001.json"),
                run_config_path=self.repository.run_config_path("baseline_seed_001.json"),
                component_config_path=self.repository.component_config_path("A1_B1_C1.json"),
                tool_spec_paths=[
                    self.repository.tool_spec_path("memory.write.json"),
                    self.repository.tool_spec_path("memory.query.json"),
                ],
                artifact_root=Path(directory),
            )
            store = FileSystemResultsStore.from_run_config(self.run_config, Path(directory))
            relative_paths = store.relative_paths(
                {
                    "trace": run.artifact_paths.trace,
                    "verification": run.artifact_paths.verification,
                    "metrics": run.artifact_paths.metrics,
                    "report": run.artifact_paths.report,
                }
            )

            trace_payload = json.loads(run.artifact_paths.trace.read_text(encoding="utf-8"))
            verification_payload = json.loads(run.artifact_paths.verification.read_text(encoding="utf-8"))
            metrics_payload = json.loads(run.artifact_paths.metrics.read_text(encoding="utf-8"))

        self.assertEqual(context.run_id, run.trace.run_id)
        self.assertEqual(relative_paths["trace"], f"traces/{run.trace.run_id}.json")
        self.assertEqual(relative_paths["report"], f"reports/{run.trace.run_id}.md")
        self.assertIsInstance(RunTrace.from_dict(trace_payload), RunTrace)
        self.assertIsInstance(VerificationResult.from_dict(verification_payload), VerificationResult)
        self.assertIsInstance(MetricResult.from_dict(metrics_payload), MetricResult)

    def test_phase1_baseline_run_still_passes_with_component_registry_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_phase1_baseline(
                task_path=self.repository.task_path("memory_recall_001.json"),
                run_config_path=self.repository.run_config_path("baseline_seed_001.json"),
                component_config_path=self.repository.component_config_path("A1_B1_C1.json"),
                tool_spec_paths=[
                    self.repository.tool_spec_path("memory.write.json"),
                    self.repository.tool_spec_path("memory.query.json"),
                ],
                artifact_root=Path(directory),
            )

        self.assertTrue(result.verification.passed)
        self.assertTrue(result.metrics.task_success)
        self.assertEqual(result.component_bundle.config_id, "A1_B1_C1")
        self.assertEqual(result.component_bundle.memory.status, "available")
        self.assertEqual(result.component_bundle.retrieval.status, "available")
        self.assertEqual(result.component_bundle.scheduling.variant, "sequential")

    def test_baseline_trace_records_selected_component_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_phase1_baseline(
                task_path=self.repository.task_path("memory_recall_001.json"),
                run_config_path=self.repository.run_config_path("baseline_seed_001.json"),
                component_config_path=self.repository.component_config_path("A1_B1_C1.json"),
                tool_spec_paths=[
                    self.repository.tool_spec_path("memory.write.json"),
                    self.repository.tool_spec_path("memory.query.json"),
                ],
                artifact_root=Path(directory),
            )

        component_events = [
            event for event in result.trace.events
            if event.payload.get("stage") == "component_config"
        ]

        self.assertEqual(len(component_events), 1)
        self.assertEqual(component_events[0].payload["component_config"]["memory_backend"], "sqlite")
        self.assertEqual(component_events[0].payload["component_config"]["retrieval_strategy"], "bm25")

    def test_baseline_trace_records_scheduler_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_phase1_baseline(
                task_path=self.repository.task_path("memory_recall_001.json"),
                run_config_path=self.repository.run_config_path("baseline_seed_001.json"),
                component_config_path=self.repository.component_config_path("A1_B1_C1.json"),
                tool_spec_paths=[
                    self.repository.tool_spec_path("memory.write.json"),
                    self.repository.tool_spec_path("memory.query.json"),
                ],
                artifact_root=Path(directory),
            )

        scheduling_events = [
            event for event in result.trace.events
            if event.payload.get("stage") == "scheduling"
        ]

        self.assertEqual(len(scheduling_events), 1)
        self.assertEqual(scheduling_events[0].payload["policy"], "sequential")
        self.assertEqual(
            [decision["rule"] for decision in scheduling_events[0].payload["decisions"]],
            ["preserve_planner_order", "preserve_planner_order", "preserve_planner_order"],
        )


if __name__ == "__main__":
    unittest.main()
