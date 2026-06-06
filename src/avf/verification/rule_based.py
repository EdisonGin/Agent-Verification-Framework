"""Deterministic rule-based verification for Phase 1H."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from avf.contracts import SCHEMA_VERSION, RunTrace, TaskCase, ValidationError, VerificationResult
from avf.tracing import validate_run_trace

from .evidence import final_answer_event, final_answer_text, observed_tool_names, tool_call_events


DEFAULT_RULE_BASED_VERIFIER_ID = "rule_based_success_criteria_v1"


class RuleBasedVerifier:
    """Verify a run trace against deterministic task success criteria."""

    def __init__(self, verifier_id: str = DEFAULT_RULE_BASED_VERIFIER_ID) -> None:
        self.verifier_id = verifier_id

    def verify(self, task: TaskCase, trace: RunTrace) -> VerificationResult:
        evidence: List[Dict[str, Any]] = []
        failure_reasons: List[str] = []

        try:
            validate_run_trace(trace)
            self._add_check(
                evidence,
                failure_reasons,
                check="run_trace_valid",
                passed=True,
                description="RunTrace passes schema and cross-event validation.",
            )
        except ValidationError as exc:
            reason = f"RunTrace validation failed: {exc}"
            self._add_check(
                evidence,
                failure_reasons,
                check="run_trace_valid",
                passed=False,
                description="RunTrace must pass schema and cross-event validation.",
                failure_reason=reason,
            )
            return self._result(trace.run_id, evidence, failure_reasons)

        self._check_task_id(task, trace, evidence, failure_reasons)
        self._check_trace_status(trace, evidence, failure_reasons)
        self._check_required_final_answer_text(task, trace, evidence, failure_reasons)
        self._check_required_tool_calls(task, trace, evidence, failure_reasons)

        return self._result(trace.run_id, evidence, failure_reasons)

    def _check_task_id(
        self,
        task: TaskCase,
        trace: RunTrace,
        evidence: List[Dict[str, Any]],
        failure_reasons: List[str],
    ) -> None:
        passed = trace.task_id == task.task_id
        self._add_check(
            evidence,
            failure_reasons,
            check="task_id_matches",
            passed=passed,
            description="RunTrace task_id must match the TaskCase task_id.",
            expected=task.task_id,
            actual=trace.task_id,
            failure_reason=(
                None
                if passed
                else f"RunTrace.task_id {trace.task_id} does not match TaskCase.task_id {task.task_id}."
            ),
        )

    def _check_trace_status(
        self,
        trace: RunTrace,
        evidence: List[Dict[str, Any]],
        failure_reasons: List[str],
    ) -> None:
        passed = trace.status == "completed"
        self._add_check(
            evidence,
            failure_reasons,
            check="run_completed",
            passed=passed,
            description="RunTrace status must be completed for task success.",
            expected="completed",
            actual=trace.status,
            failure_reason=None if passed else f"RunTrace.status expected completed, got {trace.status}.",
        )

    def _check_required_final_answer_text(
        self,
        task: TaskCase,
        trace: RunTrace,
        evidence: List[Dict[str, Any]],
        failure_reasons: List[str],
    ) -> None:
        required_texts = task.success_criteria.get("required_final_answer_contains", [])
        if not isinstance(required_texts, list) or any(
            not isinstance(item, str) or not item for item in required_texts
        ):
            self._add_check(
                evidence,
                failure_reasons,
                check="required_final_answer_contains_schema",
                passed=False,
                description="Task success criteria must define required_final_answer_contains as a list of strings.",
                actual=required_texts,
                failure_reason="Task success criteria required_final_answer_contains must be a list of non-empty strings.",
            )
            return

        answer = final_answer_text(trace)
        answer_event = final_answer_event(trace)
        normalized_answer = answer.casefold() if isinstance(answer, str) else ""
        event_id = answer_event.event_id if answer_event is not None else None

        for required in required_texts:
            passed = required.casefold() in normalized_answer
            self._add_check(
                evidence,
                failure_reasons,
                check="required_final_answer_contains",
                passed=passed,
                description="Final answer must contain required task evidence text.",
                expected=required,
                actual=answer,
                event_id=event_id,
                failure_reason=None if passed else f"Final answer is missing required text: {required}.",
            )

    def _check_required_tool_calls(
        self,
        task: TaskCase,
        trace: RunTrace,
        evidence: List[Dict[str, Any]],
        failure_reasons: List[str],
    ) -> None:
        required_tools = task.success_criteria.get("required_tool_calls", [])
        if not isinstance(required_tools, list) or any(
            not isinstance(item, str) or not item for item in required_tools
        ):
            self._add_check(
                evidence,
                failure_reasons,
                check="required_tool_calls_schema",
                passed=False,
                description="Task success criteria must define required_tool_calls as a list of strings.",
                actual=required_tools,
                failure_reason="Task success criteria required_tool_calls must be a list of non-empty strings.",
            )
            return

        observed = observed_tool_names(trace)
        events_by_tool: Dict[str, str] = {}
        for event in tool_call_events(trace):
            tool_name = event.payload.get("tool_name")
            if isinstance(tool_name, str) and tool_name not in events_by_tool:
                events_by_tool[tool_name] = event.event_id

        for required in required_tools:
            passed = required in observed
            self._add_check(
                evidence,
                failure_reasons,
                check="required_tool_call",
                passed=passed,
                description="Required tool call must be present in the trace.",
                expected=required,
                actual=observed,
                event_id=events_by_tool.get(required),
                failure_reason=None if passed else f"Required tool call was not observed: {required}.",
            )

    def _result(
        self,
        run_id: str,
        evidence: List[Dict[str, Any]],
        failure_reasons: List[str],
    ) -> VerificationResult:
        total = len(evidence)
        passed_checks = len([item for item in evidence if item.get("passed") is True])
        passed = not failure_reasons
        score: Optional[float] = None if total == 0 else passed_checks / total
        return VerificationResult(
            schema_version=SCHEMA_VERSION,
            run_id=run_id,
            verifier_id=self.verifier_id,
            verifier_type="rule_based",
            passed=passed,
            score=score,
            evidence=evidence,
            failure_reasons=failure_reasons,
        )

    def _add_check(
        self,
        evidence: List[Dict[str, Any]],
        failure_reasons: List[str],
        *,
        check: str,
        passed: bool,
        description: str,
        expected: Any = None,
        actual: Any = None,
        event_id: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> None:
        item: Dict[str, Any] = {
            "check": check,
            "passed": passed,
            "description": description,
        }
        if expected is not None:
            item["expected"] = expected
        if actual is not None:
            item["actual"] = actual
        if event_id is not None:
            item["event_id"] = event_id
        if failure_reason is not None:
            item["failure_reason"] = failure_reason
            failure_reasons.append(failure_reason)
        evidence.append(item)


def verify_task_success(task: TaskCase, trace: RunTrace) -> VerificationResult:
    return RuleBasedVerifier().verify(task, trace)
