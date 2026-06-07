from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from avf.agents.components import ComponentRegistry, build_component_bundle  # noqa: E402
from avf.agents.memory import SQLiteMemory, VectorMemory  # noqa: E402
from avf.agents.retrieval import BM25Retriever, EmbeddingRetriever  # noqa: E402
from avf.agents.scheduling import RuleBasedScheduler, SequentialScheduler  # noqa: E402
from avf.storage import FileSystemTestDataRepository  # noqa: E402


FACTOR_CELLS = {
    "A1_B1_C1": ("sqlite", "bm25", "sequential"),
    "A1_B1_C2": ("sqlite", "bm25", "rule_based"),
    "A1_B2_C1": ("sqlite", "embedding", "sequential"),
    "A1_B2_C2": ("sqlite", "embedding", "rule_based"),
    "A2_B1_C1": ("vector", "bm25", "sequential"),
    "A2_B1_C2": ("vector", "bm25", "rule_based"),
    "A2_B2_C1": ("vector", "embedding", "sequential"),
    "A2_B2_C2": ("vector", "embedding", "rule_based"),
}


class Phase2GComponentFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FileSystemTestDataRepository(ROOT / "test_data")

    def test_repository_validates_all_factorial_component_fixtures(self) -> None:
        summary = self.repository.validate()
        loaded = self.repository.load_tree()

        self.assertEqual(summary["components"], 8)
        self.assertEqual(
            [component.config_id for component in loaded["components"]],
            sorted(FACTOR_CELLS),
        )

    def test_component_fixture_ids_and_factor_values_are_consistent(self) -> None:
        for config_id, factors in FACTOR_CELLS.items():
            with self.subTest(config_id=config_id):
                config = self.repository.load_component_config(f"{config_id}.json")
                memory_backend, retrieval_strategy, scheduling_policy = factors

                self.assertEqual(config.config_id, config_id)
                self.assertEqual(config.memory_backend, memory_backend)
                self.assertEqual(config.retrieval_strategy, retrieval_strategy)
                self.assertEqual(config.scheduling_policy, scheduling_policy)

    def test_every_component_fixture_resolves_to_available_implementations(self) -> None:
        for config_id, factors in FACTOR_CELLS.items():
            with self.subTest(config_id=config_id):
                config = self.repository.load_component_config(f"{config_id}.json")
                bundle = ComponentRegistry().resolve(config)
                memory_backend, retrieval_strategy, scheduling_policy = factors

                self.assertEqual(bundle.to_dict(), build_component_bundle(config).to_dict())
                self.assertEqual(bundle.memory.variant, memory_backend)
                self.assertEqual(bundle.memory.status, "available")
                self.assertEqual(bundle.retrieval.variant, retrieval_strategy)
                self.assertEqual(bundle.retrieval.status, "available")
                self.assertEqual(bundle.scheduling.variant, scheduling_policy)
                self.assertEqual(bundle.scheduling.status, "available")

                if memory_backend == "sqlite":
                    self.assertIsInstance(bundle.memory_module, SQLiteMemory)
                else:
                    self.assertIsInstance(bundle.memory_module, VectorMemory)

                if retrieval_strategy == "bm25":
                    self.assertIsInstance(bundle.retrieval_module, BM25Retriever)
                else:
                    self.assertIsInstance(bundle.retrieval_module, EmbeddingRetriever)

                if scheduling_policy == "sequential":
                    self.assertIsInstance(bundle.scheduler, SequentialScheduler)
                else:
                    self.assertIsInstance(bundle.scheduler, RuleBasedScheduler)

    def test_full_factorial_set_does_not_change_task_or_tool_fixture_counts(self) -> None:
        summary = self.repository.validate()

        self.assertEqual(summary["tasks"], 1)
        self.assertEqual(summary["configs"], 1)
        self.assertEqual(summary["tool_specs"], 2)


if __name__ == "__main__":
    unittest.main()
