from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from avf.agents import BaselineSUTAgent  # noqa: E402
from avf.contracts import ToolCall, ToolResult, load_fixture_tree  # noqa: E402
from avf.orchestration import build_run_context  # noqa: E402


class MemoryToolClientDouble:
    """Minimal in-memory tool client used to test the SUT tool boundary."""

    def __init__(self) -> None:
        self.records: Dict[str, str] = {}
        self.calls: List[ToolCall] = []

    def call_tool(self, tool_call: ToolCall) -> ToolResult:
        self.calls.append(tool_call)

        if tool_call.tool_name == "memory.write":
            key = str(tool_call.arguments["key"])
            value = str(tool_call.arguments["value"])
            self.records[key] = value
            return ToolResult(
                tool_call_id=tool_call.tool_call_id,
                status="success",
                output={"ok": True, "record_id": f"mem_{len(self.records):03d}"},
                error=None,
                latency_ms=0,
                perturbation_applied=None,
            )

        if tool_call.tool_name == "memory.query":
            query = str(tool_call.arguments["query"])
            value = self.records.get(query)
            records = [{"key": query, "value": value}] if value is not None else []
            return ToolResult(
                tool_call_id=tool_call.tool_call_id,
                status="success",
                output={"ok": True, "records": records},
                error=None,
                latency_ms=0,
                perturbation_applied=None,
            )

        return ToolResult(
            tool_call_id=tool_call.tool_call_id,
            status="error",
            output={},
            error={"message": f"unsupported tool {tool_call.tool_name}"},
            latency_ms=0,
            perturbation_applied=None,
        )


class BaselineSUTAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        loaded = load_fixture_tree(ROOT / "test_data")
        self.context = build_run_context(
            task=loaded["tasks"][0],
            run_config=loaded["configs"][0],
            component_config=loaded["components"][0],
            tool_specs=sorted(loaded["tool_specs"], key=lambda tool: tool.tool_name),
        )
        self.agent_input = self.context.to_agent_run_input()

    def test_baseline_agent_completes_memory_recall_task(self) -> None:
        tool_client = MemoryToolClientDouble()
        result = BaselineSUTAgent().run(self.agent_input, tool_client)

        self.assertEqual(result.output.status, "completed")
        self.assertIn("concise summaries", result.output.final_answer or "")
        self.assertEqual(result.output.metrics["steps"], 3)
        self.assertEqual(result.output.metrics["tool_calls"], 2)
        self.assertEqual(result.output.metrics["errors"], 0)
        self.assertEqual([call.tool_name for call in tool_client.calls], ["memory.write", "memory.query"])

    def test_baseline_agent_emits_agent_actions_observations_and_trace_events(self) -> None:
        result = BaselineSUTAgent().run(self.agent_input, MemoryToolClientDouble())

        self.assertEqual([action.name for action in result.actions], ["memory.write", "memory.query", "final_answer"])
        self.assertEqual([observation.status for observation in result.observations], ["success", "success", "success"])
        self.assertEqual(result.output.trace_event_ids, [event.event_id for event in result.trace_events])

        event_types = [event.event_type for event in result.trace_events]
        self.assertIn("agent_step", event_types)
        self.assertIn("tool_call", event_types)
        self.assertIn("tool_result", event_types)
        self.assertIn("observation", event_types)
        self.assertIn("state_update", event_types)
        self.assertIn("final_answer", event_types)

    def test_baseline_agent_trace_is_deterministic_for_same_input(self) -> None:
        first = BaselineSUTAgent().run(self.agent_input, MemoryToolClientDouble())
        second = BaselineSUTAgent().run(self.agent_input, MemoryToolClientDouble())

        self.assertEqual(first.output.to_dict(), second.output.to_dict())
        self.assertEqual(
            [event.to_dict() for event in first.trace_events],
            [event.to_dict() for event in second.trace_events],
        )

    def test_baseline_agent_reports_failed_status_on_tool_error(self) -> None:
        class FailingToolClient:
            def call_tool(self, tool_call: ToolCall) -> ToolResult:
                return ToolResult(
                    tool_call_id=tool_call.tool_call_id,
                    status="error",
                    output={},
                    error={"message": "forced failure"},
                    latency_ms=0,
                    perturbation_applied=None,
                )

        result = BaselineSUTAgent().run(self.agent_input, FailingToolClient())

        self.assertEqual(result.output.status, "failed")
        self.assertIsNone(result.output.final_answer)
        self.assertEqual(result.output.metrics["errors"], 1)


if __name__ == "__main__":
    unittest.main()

