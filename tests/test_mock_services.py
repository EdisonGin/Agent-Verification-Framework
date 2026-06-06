from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from avf.agents import BaselineSUTAgent  # noqa: E402
from avf.contracts import ToolCall, load_fixture_tree  # noqa: E402
from avf.mock_services import MockMemoryService, StaticPerturbationController  # noqa: E402
from avf.orchestration import build_run_context  # noqa: E402


def tool_call(tool_name: str, arguments: dict, call_id: str = "tool_call_001") -> ToolCall:
    return ToolCall(
        tool_call_id=call_id,
        run_id="run_test",
        step_index=0,
        tool_name=tool_name,
        arguments=arguments,
        requested_at="1970-01-01T00:00:01Z",
    )


class MockMemoryServiceTests(unittest.TestCase):
    def test_write_and_query_are_deterministic(self) -> None:
        first = MockMemoryService()
        second = MockMemoryService()

        write = tool_call(
            "memory.write",
            {"key": "user_preference", "value": "use concise summaries", "metadata": {"task_id": "task_001"}},
        )
        query = tool_call(
            "memory.query",
            {"query": "user_preference", "metadata_filter": {"task_id": "task_001"}, "limit": 1},
            call_id="tool_call_002",
        )

        first_outputs = [first.call_tool(write).to_dict(), first.call_tool(query).to_dict()]
        second_outputs = [second.call_tool(write).to_dict(), second.call_tool(query).to_dict()]

        self.assertEqual(first_outputs, second_outputs)
        self.assertEqual(first_outputs[0]["status"], "success")
        self.assertEqual(first_outputs[0]["output"]["record_id"], "mem_001")
        self.assertEqual(first_outputs[1]["output"]["records"][0]["value"], "use concise summaries")

    def test_query_respects_metadata_filter(self) -> None:
        service = MockMemoryService()
        service.call_tool(tool_call(
            "memory.write",
            {"key": "user_preference", "value": "value A", "metadata": {"task_id": "task_a"}},
            call_id="write_a",
        ))
        service.call_tool(tool_call(
            "memory.write",
            {"key": "user_preference", "value": "value B", "metadata": {"task_id": "task_b"}},
            call_id="write_b",
        ))

        result = service.call_tool(tool_call(
            "memory.query",
            {"query": "user_preference", "metadata_filter": {"task_id": "task_b"}, "limit": 2},
            call_id="query_b",
        ))

        self.assertEqual(len(result.output["records"]), 1)
        self.assertEqual(result.output["records"][0]["value"], "value B")

    def test_invalid_arguments_return_structured_errors(self) -> None:
        service = MockMemoryService()

        result = service.call_tool(tool_call("memory.write", {"value": "missing key"}))

        self.assertEqual(result.status, "error")
        self.assertEqual(result.error["type"], "invalid_arguments")
        self.assertIn("key", result.error["message"])

    def test_unsupported_tool_returns_structured_error(self) -> None:
        service = MockMemoryService()

        result = service.call_tool(tool_call("filesystem.read", {"path": "x"}))

        self.assertEqual(result.status, "error")
        self.assertEqual(result.error["type"], "unsupported_tool")

    def test_static_perturbation_hook_applies_to_matching_tool(self) -> None:
        service = MockMemoryService(
            perturbations=StaticPerturbationController(
                tool_name="memory.query",
                kind="temporary_unavailability",
                message="query unavailable in fixed schedule",
                latency_ms=25,
            )
        )
        service.call_tool(tool_call(
            "memory.write",
            {"key": "user_preference", "value": "use concise summaries"},
            call_id="write",
        ))

        result = service.call_tool(tool_call(
            "memory.query",
            {"query": "user_preference", "limit": 1},
            call_id="query",
        ))

        self.assertEqual(result.status, "perturbed")
        self.assertEqual(result.error["type"], "temporary_unavailability")
        self.assertEqual(result.latency_ms, 25)
        self.assertEqual(result.perturbation_applied["tool_name"], "memory.query")

    def test_baseline_agent_runs_against_mock_memory_service(self) -> None:
        loaded = load_fixture_tree(ROOT / "test_data")
        context = build_run_context(
            task=loaded["tasks"][0],
            run_config=loaded["configs"][0],
            component_config=loaded["components"][0],
            tool_specs=sorted(loaded["tool_specs"], key=lambda tool: tool.tool_name),
        )
        service = MockMemoryService()

        result = BaselineSUTAgent().run(context.to_agent_run_input(), service)

        self.assertEqual(result.output.status, "completed")
        self.assertIn("concise summaries", result.output.final_answer or "")
        self.assertEqual([call.tool_name for call in service.calls], ["memory.write", "memory.query"])


if __name__ == "__main__":
    unittest.main()

