from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from avf.contracts import ComponentConfig, ValidationError, load_fixture_tree  # noqa: E402
from avf.orchestration import (  # noqa: E402
    ExecutionEngine,
    build_run_context,
    build_run_context_from_files,
    deterministic_run_id,
)


class OrchestrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture_root = ROOT / "test_data"
        loaded = load_fixture_tree(self.fixture_root)
        self.task = loaded["tasks"][0]
        self.run_config = loaded["configs"][0]
        self.component_config = loaded["components"][0]
        self.tool_specs = sorted(loaded["tool_specs"], key=lambda tool: tool.tool_name)

    def test_build_run_context_from_contracts(self) -> None:
        context = build_run_context(
            task=self.task,
            run_config=self.run_config,
            component_config=self.component_config,
            tool_specs=self.tool_specs,
        )

        self.assertEqual(context.status, "created")
        self.assertEqual(context.seed, 42)
        self.assertEqual(context.task.task_id, "memory_recall_001")
        self.assertEqual(context.component_config.config_id, "A1_B1_C1")
        self.assertEqual(context.perturbation_schedule_id, "schedule_none_v1")
        self.assertEqual(context.execution_controls["max_steps"], 8)
        self.assertEqual(context.execution_controls["retry_policy"], "none")
        self.assertEqual(context.execution_controls["logging"], "full_trace")

    def test_run_id_is_deterministic(self) -> None:
        first = build_run_context(self.task, self.run_config, self.component_config, self.tool_specs)
        second = build_run_context(self.task, self.run_config, self.component_config, list(reversed(self.tool_specs)))

        self.assertEqual(first.run_id, second.run_id)
        self.assertEqual(
            first.run_id,
            deterministic_run_id(self.task, self.run_config, self.component_config, self.tool_specs),
        )

    def test_run_id_changes_when_component_changes(self) -> None:
        alternate_component = ComponentConfig.from_dict({
            "schema_version": "1.0",
            "config_id": "A2_B1_C1",
            "memory_backend": "vector",
            "retrieval_strategy": "bm25",
            "scheduling_policy": "sequential"
        })

        baseline = build_run_context(self.task, self.run_config, self.component_config, self.tool_specs)
        alternate = build_run_context(self.task, self.run_config, alternate_component, self.tool_specs)

        self.assertNotEqual(baseline.run_id, alternate.run_id)

    def test_context_converts_to_agent_run_input(self) -> None:
        context = build_run_context(self.task, self.run_config, self.component_config, self.tool_specs)
        agent_input = context.to_agent_run_input()

        self.assertEqual(agent_input.run_id, context.run_id)
        self.assertEqual(agent_input.task.task_id, self.task.task_id)
        self.assertEqual(agent_input.component_config.config_id, self.component_config.config_id)

    def test_context_rejects_missing_tool_specs(self) -> None:
        with self.assertRaises(ValidationError):
            build_run_context(self.task, self.run_config, self.component_config, self.tool_specs[:1])

    def test_context_rejects_undeclared_tool_specs(self) -> None:
        undeclared_tool = self.tool_specs[0].__class__.from_dict({
            "schema_version": "1.0",
            "tool_name": "filesystem.read",
            "tool_schema_version": "1.0",
            "description": "Read a file.",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "error_model": {}
        })

        with self.assertRaises(ValidationError):
            build_run_context(
                self.task,
                self.run_config,
                self.component_config,
                self.tool_specs + [undeclared_tool],
            )

    def test_build_run_context_from_files(self) -> None:
        context = build_run_context_from_files(
            task_path=self.fixture_root / "tasks" / "memory_recall_001.json",
            run_config_path=self.fixture_root / "configs" / "baseline_seed_001.json",
            component_config_path=self.fixture_root / "components" / "A1_B1_C1.json",
            tool_spec_paths=[
                self.fixture_root / "tool_specs" / "memory.write.json",
                self.fixture_root / "tool_specs" / "memory.query.json",
            ],
        )

        self.assertEqual(context.status, "created")

    def test_execution_engine_creates_context(self) -> None:
        engine = ExecutionEngine()
        context = engine.create_run_context(self.task, self.run_config, self.component_config, self.tool_specs)

        self.assertEqual(context.status, "created")


if __name__ == "__main__":
    unittest.main()

