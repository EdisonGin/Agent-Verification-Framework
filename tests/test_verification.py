from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from avf.agents import BaselineSUTAgent  # noqa: E402
from avf.cli import main as cli_main  # noqa: E402
from avf.contracts import VerificationResult, ValidationError, load_fixture_tree  # noqa: E402
from avf.mock_services import MockMemoryService  # noqa: E402
from avf.orchestration import build_run_context  # noqa: E402
from avf.tracing import TraceWriter, build_run_trace_from_agent_result  # noqa: E402
from avf.verification import (  # noqa: E402
    RuleBasedVerifier,
    VerificationResultWriter,
    final_answer_text,
    observed_tool_names,
    verify_task_success,
    write_verification_result,
)


class RuleBasedVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        loaded = load_fixture_tree(ROOT / "test_data")
        self.task = loaded["tasks"][0]
        self.context = build_run_context(
            task=self.task,
            run_config=loaded["configs"][0],
            component_config=loaded["components"][0],
            tool_specs=sorted(loaded["tool_specs"], key=lambda tool: tool.tool_name),
        )
        agent_result = BaselineSUTAgent().run(self.context.to_agent_run_input(), MockMemoryService())
        self.trace = build_run_trace_from_agent_result(self.context, agent_result)

    def test_baseline_trace_passes_task_success_criteria(self) -> None:
        result = RuleBasedVerifier().verify(self.task, self.trace)

        self.assertTrue(result.passed)
        self.assertEqual(result.verifier_type, "rule_based")
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.failure_reasons, [])
        self.assertTrue(any(item["check"] == "required_final_answer_contains" for item in result.evidence))
        self.assertTrue(any(item["check"] == "required_tool_call" for item in result.evidence))

    def test_verify_task_success_helper_uses_rule_based_verifier(self) -> None:
        result = verify_task_success(self.task, self.trace)

        self.assertTrue(result.passed)

    def test_evidence_extractors_return_final_answer_and_tool_names(self) -> None:
        self.assertIn("concise summaries", final_answer_text(self.trace) or "")
        self.assertEqual(observed_tool_names(self.trace), ["memory.write", "memory.query"])

    def test_missing_required_final_answer_text_fails_with_reason(self) -> None:
        task = replace(
            self.task,
            success_criteria={
                **self.task.success_criteria,
                "required_final_answer_contains": ["nonexistent phrase"],
            },
        )

        result = RuleBasedVerifier().verify(task, self.trace)

        self.assertFalse(result.passed)
        self.assertIn("Final answer is missing required text: nonexistent phrase.", result.failure_reasons)

    def test_missing_required_tool_call_fails_with_reason(self) -> None:
        events = [
            event
            for event in self.trace.events
            if not (event.event_type == "tool_call" and event.payload.get("tool_name") == "memory.query")
        ]
        trace = replace(self.trace, events=events)

        result = RuleBasedVerifier().verify(self.task, trace)

        self.assertFalse(result.passed)
        self.assertIn("Required tool call was not observed: memory.query.", result.failure_reasons)

    def test_task_id_mismatch_fails_with_reason(self) -> None:
        task = replace(self.task, task_id="other_task")

        result = RuleBasedVerifier().verify(task, self.trace)

        self.assertFalse(result.passed)
        self.assertIn(
            f"RunTrace.task_id {self.trace.task_id} does not match TaskCase.task_id other_task.",
            result.failure_reasons,
        )

    def test_invalid_trace_returns_failed_verification_result(self) -> None:
        duplicate = replace(self.trace.events[1], event_id=self.trace.events[0].event_id)
        trace = replace(self.trace, events=[self.trace.events[0], duplicate] + self.trace.events[2:])

        result = RuleBasedVerifier().verify(self.task, trace)

        self.assertFalse(result.passed)
        self.assertTrue(result.failure_reasons[0].startswith("RunTrace validation failed: Duplicate TraceEvent ID"))

    def test_invalid_success_criteria_shape_fails_verification(self) -> None:
        task = replace(
            self.task,
            success_criteria={
                **self.task.success_criteria,
                "required_tool_calls": "memory.query",
            },
        )

        result = RuleBasedVerifier().verify(task, self.trace)

        self.assertFalse(result.passed)
        self.assertIn(
            "Task success criteria required_tool_calls must be a list of non-empty strings.",
            result.failure_reasons,
        )

    def test_verification_result_writer_round_trips_contract_json(self) -> None:
        result = RuleBasedVerifier().verify(self.task, self.trace)

        with tempfile.TemporaryDirectory() as directory:
            path = VerificationResultWriter(Path(directory)).write(result)
            payload = json.loads(path.read_text(encoding="utf-8"))

        loaded = VerificationResult.from_dict(payload)
        self.assertEqual(loaded.to_dict(), result.to_dict())

    def test_verification_result_writer_helper_uses_result_dir(self) -> None:
        result = RuleBasedVerifier().verify(self.task, self.trace)

        with tempfile.TemporaryDirectory() as directory:
            path = write_verification_result(result, Path(directory))

        self.assertEqual(path.name, f"{result.run_id}.{result.verifier_id}.json")

    def test_verify_trace_cli_writes_result_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp_root = Path(directory)
            trace_path = TraceWriter(temp_root / "traces").write(self.trace)
            result_dir = temp_root / "results"
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = cli_main(
                    [
                        "verify-trace",
                        "--task",
                        str(ROOT / "test_data/tasks/memory_recall_001.json"),
                        "--trace",
                        str(trace_path),
                        "--result-dir",
                        str(result_dir),
                    ]
                )

            artifact_paths = list(result_dir.glob("*.json"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(artifact_paths), 1)
        self.assertTrue(json.loads(output.getvalue())["passed"])


if __name__ == "__main__":
    unittest.main()
