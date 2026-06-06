from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from avf.agents import BaselineSUTAgent  # noqa: E402
from avf.contracts import TraceEvent, ValidationError, load_fixture_tree  # noqa: E402
from avf.mock_services import MockMemoryService  # noqa: E402
from avf.orchestration import build_run_context  # noqa: E402
from avf.tracing import (  # noqa: E402
    TraceReader,
    TraceWriter,
    build_run_trace,
    build_run_trace_from_agent_result,
    read_run_trace,
    validate_run_trace,
    write_run_trace,
)


class TraceLoggingTests(unittest.TestCase):
    def setUp(self) -> None:
        loaded = load_fixture_tree(ROOT / "test_data")
        self.context = build_run_context(
            task=loaded["tasks"][0],
            run_config=loaded["configs"][0],
            component_config=loaded["components"][0],
            tool_specs=sorted(loaded["tool_specs"], key=lambda tool: tool.tool_name),
        )
        self.agent_result = BaselineSUTAgent().run(self.context.to_agent_run_input(), MockMemoryService())

    def test_build_run_trace_from_agent_result_preserves_run_metadata(self) -> None:
        trace = build_run_trace_from_agent_result(self.context, self.agent_result)

        self.assertEqual(trace.run_id, self.context.run_id)
        self.assertEqual(trace.task_id, self.context.task.task_id)
        self.assertEqual(trace.run_config_id, self.context.run_config.run_config_id)
        self.assertEqual(trace.component_config_id, self.context.component_config.config_id)
        self.assertEqual(trace.seed, self.context.seed)
        self.assertEqual(trace.perturbation_schedule_id, self.context.perturbation_schedule_id)
        self.assertEqual(trace.status, "completed")
        self.assertEqual(trace.started_at, trace.events[0].timestamp)
        self.assertEqual(trace.completed_at, trace.events[-1].timestamp)

    def test_build_run_trace_preserves_event_order(self) -> None:
        trace = build_run_trace(
            run_context=self.context,
            events=self.agent_result.trace_events,
            status=self.agent_result.output.status,
        )

        self.assertEqual(
            [event.event_id for event in trace.events],
            [event.event_id for event in self.agent_result.trace_events],
        )

    def test_trace_writer_and_reader_round_trip(self) -> None:
        trace = build_run_trace_from_agent_result(self.context, self.agent_result)

        with tempfile.TemporaryDirectory() as directory:
            path = TraceWriter(Path(directory)).write(trace)
            loaded = TraceReader().read(path)

        self.assertEqual(loaded.to_dict(), trace.to_dict())

    def test_trace_helper_functions_round_trip(self) -> None:
        trace = build_run_trace_from_agent_result(self.context, self.agent_result)

        with tempfile.TemporaryDirectory() as directory:
            path = write_run_trace(trace, Path(directory))
            loaded = read_run_trace(path)

        self.assertEqual(loaded.to_dict(), trace.to_dict())

    def test_trace_writer_uses_run_id_artifact_name(self) -> None:
        trace = build_run_trace_from_agent_result(self.context, self.agent_result)

        with tempfile.TemporaryDirectory() as directory:
            path = TraceWriter(Path(directory)).write(trace)

        self.assertEqual(path.name, f"{trace.run_id}.json")

    def test_validate_trace_rejects_mismatched_event_run_id(self) -> None:
        trace = build_run_trace_from_agent_result(self.context, self.agent_result)
        bad_event = replace(trace.events[0], run_id="other_run")
        bad_trace = replace(trace, events=[bad_event] + trace.events[1:])

        with self.assertRaises(ValidationError):
            validate_run_trace(bad_trace)

    def test_validate_trace_rejects_duplicate_event_ids(self) -> None:
        trace = build_run_trace_from_agent_result(self.context, self.agent_result)
        duplicate = replace(trace.events[1], event_id=trace.events[0].event_id)
        bad_trace = replace(trace, events=[trace.events[0], duplicate] + trace.events[2:])

        with self.assertRaises(ValidationError):
            validate_run_trace(bad_trace)

    def test_completed_trace_requires_final_answer_event(self) -> None:
        events = [event for event in self.agent_result.trace_events if event.event_type != "final_answer"]

        with self.assertRaises(ValidationError):
            build_run_trace(self.context, events, status="completed")

    def test_build_trace_rejects_agent_output_event_id_mismatch(self) -> None:
        bad_output = replace(self.agent_result.output, trace_event_ids=["wrong_event"])
        bad_result = replace(self.agent_result, output=bad_output)

        with self.assertRaises(ValidationError):
            build_run_trace_from_agent_result(self.context, bad_result)

    def test_build_trace_rejects_empty_events(self) -> None:
        with self.assertRaises(ValidationError):
            build_run_trace(self.context, [], status="failed")


if __name__ == "__main__":
    unittest.main()

