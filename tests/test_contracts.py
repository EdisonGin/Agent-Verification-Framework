from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from avf.contracts import (  # noqa: E402
    AgentAction,
    AgentObservation,
    AgentOutput,
    AgentRunInput,
    ComponentConfig,
    ExperimentResult,
    MetricResult,
    RunConfig,
    RunTrace,
    TaskCase,
    ToolCall,
    ToolResult,
    ToolSpec,
    TraceEvent,
    ValidationError,
    VerificationResult,
    load_fixture_tree,
    validate_fixture_tree,
)


class ContractFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture_root = ROOT / "test_data"
        self.loaded = load_fixture_tree(self.fixture_root)

    def test_required_fixture_tree_validates(self) -> None:
        summary = validate_fixture_tree(self.fixture_root)

        self.assertGreaterEqual(summary["tasks"], 1)
        self.assertGreaterEqual(summary["configs"], 1)
        self.assertGreaterEqual(summary["components"], 1)
        self.assertGreaterEqual(summary["tool_specs"], 1)

    def test_loaded_fixture_types(self) -> None:
        self.assertIsInstance(self.loaded["tasks"][0], TaskCase)
        self.assertIsInstance(self.loaded["configs"][0], RunConfig)
        self.assertIsInstance(self.loaded["components"][0], ComponentConfig)
        self.assertIsInstance(self.loaded["tool_specs"][0], ToolSpec)

    def test_agent_run_input_accepts_nested_contracts(self) -> None:
        payload = {
            "schema_version": "1.0",
            "run_id": "run_memory_recall_001_seed_42",
            "task": self.loaded["tasks"][0].to_dict(),
            "run_config": self.loaded["configs"][0].to_dict(),
            "component_config": self.loaded["components"][0].to_dict(),
            "tool_specs": [tool.to_dict() for tool in self.loaded["tool_specs"]],
            "execution_controls": {
                "max_steps": 8,
                "timeout_seconds": 60,
                "retry_policy": "none",
                "logging": "full_trace"
            }
        }

        model = AgentRunInput.from_dict(payload)

        self.assertEqual(model.run_id, "run_memory_recall_001_seed_42")
        self.assertEqual(model.task.task_id, "memory_recall_001")
        self.assertEqual(model.component_config.config_id, "A1_B1_C1")
        self.assertGreaterEqual(len(model.tool_specs), 1)

    def test_schema_rejects_invalid_task_family(self) -> None:
        payload = self.loaded["tasks"][0].to_dict()
        payload["family"] = "unsupported"

        with self.assertRaises(ValidationError):
            TaskCase.from_dict(payload)

    def test_schema_rejects_unknown_fields(self) -> None:
        payload = self.loaded["components"][0].to_dict()
        payload["unexpected"] = "drift"

        with self.assertRaises(ValidationError):
            ComponentConfig.from_dict(payload)


class ContractModelTests(unittest.TestCase):
    def test_agent_action(self) -> None:
        model = AgentAction.from_dict({
            "action_id": "action_001",
            "run_id": "run_001",
            "step_index": 0,
            "action_type": "tool_call",
            "name": "memory.write",
            "arguments": {"key": "preference", "value": "use concise summaries"},
            "rationale": "Store the preference before recall."
        })
        self.assertEqual(model.action_type, "tool_call")

    def test_agent_observation(self) -> None:
        model = AgentObservation.from_dict({
            "observation_id": "observation_001",
            "run_id": "run_001",
            "step_index": 0,
            "source": "memory.write",
            "status": "success",
            "content": {"ok": True, "record_id": "mem_001"},
            "state_delta": {"preference_stored": True}
        })
        self.assertEqual(model.status, "success")

    def test_agent_output(self) -> None:
        model = AgentOutput.from_dict({
            "schema_version": "1.0",
            "run_id": "run_001",
            "status": "completed",
            "final_answer": "The preference is to use concise summaries.",
            "artifacts": [],
            "metrics": {"steps": 3, "errors": 0},
            "trace_event_ids": ["event_001", "event_002"]
        })
        self.assertEqual(model.status, "completed")

    def test_tool_call_and_result(self) -> None:
        call = ToolCall.from_dict({
            "tool_call_id": "tool_call_001",
            "run_id": "run_001",
            "step_index": 1,
            "tool_name": "memory.query",
            "arguments": {"query": "preference"},
            "requested_at": "2026-06-05T18:00:00Z"
        })
        result = ToolResult.from_dict({
            "tool_call_id": "tool_call_001",
            "status": "success",
            "output": {"ok": True, "records": []},
            "error": None,
            "latency_ms": 0,
            "perturbation_applied": None
        })

        self.assertEqual(call.tool_call_id, result.tool_call_id)

    def test_trace_and_run_trace(self) -> None:
        event = TraceEvent.from_dict({
            "event_id": "event_001",
            "run_id": "run_001",
            "event_type": "agent_step",
            "step_index": 0,
            "timestamp": "2026-06-05T18:00:00Z",
            "payload": {"stage": "perception"}
        })
        trace = RunTrace.from_dict({
            "schema_version": "1.0",
            "run_id": "run_001",
            "task_id": "memory_recall_001",
            "run_config_id": "baseline_seed_001",
            "component_config_id": "A1_B1_C1",
            "seed": 42,
            "perturbation_schedule_id": "schedule_none_v1",
            "started_at": "2026-06-05T18:00:00Z",
            "completed_at": "2026-06-05T18:00:01Z",
            "status": "completed",
            "events": [event.to_dict()]
        })

        self.assertEqual(trace.events[0].event_id, "event_001")

    def test_verification_metric_and_experiment_results(self) -> None:
        verification = VerificationResult.from_dict({
            "schema_version": "1.0",
            "run_id": "run_001",
            "verifier_id": "rule_success_v1",
            "verifier_type": "rule_based",
            "passed": True,
            "score": 1.0,
            "evidence": [{"event_id": "event_001"}],
            "failure_reasons": []
        })
        metrics = MetricResult.from_dict({
            "schema_version": "1.0",
            "run_id": "run_001",
            "task_success": True,
            "latency_ms": 100,
            "step_count": 3,
            "tool_call_count": 2,
            "goal_drift": 0.0,
            "repetition_rate": 0.0,
            "recovery_steps": None
        })
        experiment = ExperimentResult.from_dict({
            "schema_version": "1.0",
            "experiment_id": "phase1_smoke",
            "factorial_design": {"configs": ["A1_B1_C1"]},
            "run_ids": ["run_001"],
            "aggregation": {"task_success_rate": 1.0},
            "analysis_artifacts": {"report": "artifacts/reports/phase1_smoke.md"}
        })

        self.assertTrue(verification.passed)
        self.assertTrue(metrics.task_success)
        self.assertEqual(experiment.experiment_id, "phase1_smoke")


if __name__ == "__main__":
    unittest.main()

