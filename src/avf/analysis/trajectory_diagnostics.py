"""Phase 4C trace-derived trajectory diagnostics."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from avf.contracts import RunTrace, SCHEMA_VERSION, TraceEvent, ValidationError
from avf.orchestration.pilot_qa import current_commit_hash, utc_timestamp


PHASE4C_ANALYSIS_VERSION = "1.0"
TRAJECTORY_DIAGNOSTICS_JSON_FILE = "trajectory_diagnostics.json"
TRAJECTORY_DIAGNOSTICS_MARKDOWN_FILE = "trajectory_diagnostics.md"

HEURISTIC_DEFINITIONS = {
    "action_sequence": (
        "Ordered action names from agent_step events where payload.stage is act."
    ),
    "tool_sequence": (
        "Ordered tool names from tool_call events. Repeated tool calls are counted as adjacent "
        "same-tool repetitions in this sequence."
    ),
    "observation_sequence": (
        "Ordered deterministic observation signatures from observation events. Repeated observations "
        "are counted as adjacent identical signatures."
    ),
    "repetition_rate": (
        "Adjacent repeated action names divided by action count. The value is 0.0 when no actions exist."
    ),
    "goal_drift": (
        "If a final answer is present, goal drift is 0.0. Otherwise it is the fraction of action steps "
        "without a non-empty state_delta update."
    ),
    "recovery_steps": "Count of recovery events in the trace.",
    "diagnostic_scope": (
        "agent_behavior when the row is included, hash-validated, and has no analysis issues; otherwise "
        "dataset_excluded, artifact_or_analysis_issue, or trace_unavailable."
    ),
}


@dataclass(frozen=True)
class Phase4CTrajectoryDiagnosticArtifacts:
    """Artifacts produced by Phase 4C trajectory diagnostics."""

    trajectory_diagnostics_json: Path
    trajectory_diagnostics_markdown: Path

    def to_dict(self) -> Dict[str, str]:
        return {
            "trajectory_diagnostics_json": str(self.trajectory_diagnostics_json),
            "trajectory_diagnostics_markdown": str(self.trajectory_diagnostics_markdown),
        }


@dataclass(frozen=True)
class Phase4CTrajectoryDiagnosticResult:
    """Outputs from Phase 4C trajectory diagnostics."""

    dataset_id: str
    experiment_id: str
    artifacts: Phase4CTrajectoryDiagnosticArtifacts
    trajectory_diagnostics: Dict[str, object]
    trajectory_diagnostics_markdown: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "dataset_id": self.dataset_id,
            "experiment_id": self.experiment_id,
            "run_count": self.trajectory_diagnostics["run_count"],
            "diagnostic_row_count": self.trajectory_diagnostics["diagnostic_row_count"],
            "agent_behavior_row_count": self.trajectory_diagnostics["scope_counts"].get("agent_behavior", 0),
            "artifacts": self.artifacts.to_dict(),
        }


def diagnose_phase4c_trajectories(
    metrics_table_path: Path,
    analysis_root: Optional[Path] = None,
    generated_at: Optional[str] = None,
    code_version: Optional[str] = None,
) -> Phase4CTrajectoryDiagnosticResult:
    """Derive trajectory diagnostics from stored RunTrace artifacts."""

    metrics_path = Path(metrics_table_path)
    metrics_table = _read_json_object(metrics_path, "metrics_table")
    _validate_metrics_table(metrics_table)

    dataset_id = _table_str(metrics_table, "dataset_id")
    experiment_id = _table_str(metrics_table, "experiment_id")
    timestamp = generated_at or utc_timestamp()
    version = code_version or current_commit_hash()
    output_root = Path(analysis_root) if analysis_root is not None else metrics_path.parent.parent
    analysis_dir = output_root / dataset_id
    artifacts = Phase4CTrajectoryDiagnosticArtifacts(
        trajectory_diagnostics_json=analysis_dir / TRAJECTORY_DIAGNOSTICS_JSON_FILE,
        trajectory_diagnostics_markdown=analysis_dir / TRAJECTORY_DIAGNOSTICS_MARKDOWN_FILE,
    )

    diagnostics = build_trajectory_diagnostics_payload(
        metrics_table=metrics_table,
        metrics_table_path=metrics_path,
        generated_at=timestamp,
        code_version=version,
    )
    markdown = build_trajectory_diagnostics_markdown(diagnostics)

    _write_json(artifacts.trajectory_diagnostics_json, diagnostics)
    _write_text(artifacts.trajectory_diagnostics_markdown, markdown)

    return Phase4CTrajectoryDiagnosticResult(
        dataset_id=dataset_id,
        experiment_id=experiment_id,
        artifacts=artifacts,
        trajectory_diagnostics=diagnostics,
        trajectory_diagnostics_markdown=markdown,
    )


def build_trajectory_diagnostics_payload(
    metrics_table: Mapping[str, Any],
    metrics_table_path: Path,
    generated_at: str,
    code_version: str,
) -> Dict[str, object]:
    """Build the JSON trajectory diagnostics artifact."""

    rows = _metric_rows(metrics_table)
    diagnostic_rows = [build_trajectory_row(row) for row in rows]
    scope_counts = Counter(str(row["diagnostic_scope"]) for row in diagnostic_rows)
    component_summaries = _component_summaries(diagnostic_rows)

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_version": PHASE4C_ANALYSIS_VERSION,
        "dataset_id": metrics_table["dataset_id"],
        "experiment_id": metrics_table["experiment_id"],
        "generated_at": generated_at,
        "code_version": code_version,
        "metrics_table_artifact": str(metrics_table_path),
        "run_count": metrics_table["row_count"],
        "diagnostic_row_count": len(diagnostic_rows),
        "heuristic_definitions": HEURISTIC_DEFINITIONS,
        "scope_counts": dict(sorted(scope_counts.items())),
        "component_summaries": component_summaries,
        "rows": diagnostic_rows,
        "analysis_acceptance_criteria": {
            "diagnostics_derived_from_runtrace_artifacts": True,
            "heuristic_definitions_documented": True,
            "rows_link_to_run_ids_and_trace_paths": True,
            "repeated_tool_calls_counted_deterministically": True,
            "repeated_observations_counted_deterministically": True,
            "json_and_markdown_outputs_written": True,
            "agent_behavior_and_infrastructure_issues_distinguished": True,
        },
    }


def build_trajectory_row(row: Mapping[str, Any]) -> Dict[str, object]:
    """Build one trace-derived diagnostic row from a Phase 4A metrics row."""

    run_id = _row_str(row, "run_id")
    trace_path = _trace_path(row)
    issues: List[str] = []
    trace = _load_trace(trace_path, run_id, issues)
    scope = _diagnostic_scope(row, trace, issues)

    if trace is None:
        return {
            "run_id": run_id,
            "component_config_id": _row_str(row, "component_config_id"),
            "task_id": _row_str(row, "task_id"),
            "seed": _row_int(row, "seed"),
            "perturbation_schedule_id": _row_str(row, "perturbation_schedule_id"),
            "trace_path": str(trace_path) if trace_path is not None else None,
            "diagnostic_scope": scope,
            "diagnostic_issues": issues,
            "action_sequence": [],
            "tool_sequence": [],
            "observation_status_counts": {},
            "error_summary": {},
            "trace_drilldown": {},
        }

    action_sequence = _action_sequence(trace)
    tool_sequence = _tool_sequence(trace)
    observation_signatures = _observation_signatures(trace)
    observation_status_counts = Counter(_observation_statuses(trace))
    recovery_event_ids = [event.event_id for event in trace.events if event.event_type == "recovery"]
    error_event_ids = [event.event_id for event in trace.events if event.event_type == "error"]
    final_answer_event_ids = [
        event.event_id
        for event in trace.events
        if event.event_type == "final_answer"
    ]
    repeated_action_count = _adjacent_repeat_count(action_sequence)
    repeated_tool_call_count = _adjacent_repeat_count(tool_sequence)
    repeated_observation_count = _adjacent_repeat_count(observation_signatures)
    derived_repetition_rate = repeated_action_count / len(action_sequence) if action_sequence else 0.0
    final_answer_present = bool(final_answer_event_ids)
    derived_goal_drift = _goal_drift(trace, final_answer_present, len(action_sequence))

    return {
        "run_id": run_id,
        "component_config_id": _row_str(row, "component_config_id"),
        "task_id": _row_str(row, "task_id"),
        "seed": _row_int(row, "seed"),
        "perturbation_schedule_id": _row_str(row, "perturbation_schedule_id"),
        "trace_path": str(trace_path),
        "diagnostic_scope": scope,
        "diagnostic_issues": issues,
        "trace_status": trace.status,
        "trace_event_count": len(trace.events),
        "action_count": len(action_sequence),
        "action_sequence": action_sequence,
        "tool_call_count": len(tool_sequence),
        "tool_sequence": tool_sequence,
        "unique_tool_count": len(set(tool_sequence)),
        "repeated_action_count": repeated_action_count,
        "repeated_tool_call_count": repeated_tool_call_count,
        "repeated_observation_count": repeated_observation_count,
        "repetition_rate": derived_repetition_rate,
        "metric_repetition_rate": row.get("repetition_rate"),
        "goal_drift": derived_goal_drift,
        "metric_goal_drift": row.get("goal_drift"),
        "recovery_steps": len(recovery_event_ids),
        "metric_recovery_steps": row.get("recovery_steps"),
        "final_answer_present": final_answer_present,
        "observation_count": len(observation_signatures),
        "observation_status_counts": dict(sorted(observation_status_counts.items())),
        "error_summary": {
            "error_event_count": len(error_event_ids),
            "observation_error_count": int(observation_status_counts.get("error", 0)),
            "analysis_issue_count": len(issues),
        },
        "trace_drilldown": {
            "first_event_id": trace.events[0].event_id if trace.events else None,
            "last_event_id": trace.events[-1].event_id if trace.events else None,
            "tool_call_event_ids": [
                event.event_id for event in trace.events if event.event_type == "tool_call"
            ],
            "observation_event_ids": [
                event.event_id for event in trace.events if event.event_type == "observation"
            ],
            "error_event_ids": error_event_ids,
            "recovery_event_ids": recovery_event_ids,
            "final_answer_event_ids": final_answer_event_ids,
        },
    }


def build_trajectory_diagnostics_markdown(diagnostics: Mapping[str, Any]) -> str:
    """Build the human-readable trajectory diagnostics report."""

    lines = [
        "# Phase 4C Trajectory Diagnostics",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Dataset ID | `{diagnostics['dataset_id']}` |",
        f"| Experiment ID | `{diagnostics['experiment_id']}` |",
        f"| Diagnostic rows | {diagnostics['diagnostic_row_count']} |",
        f"| Agent-behavior rows | {diagnostics['scope_counts'].get('agent_behavior', 0)} |",
        "",
        "## Heuristic Definitions",
        "",
    ]
    for name, definition in diagnostics["heuristic_definitions"].items():
        lines.append(f"- `{name}`: {definition}")

    lines.extend(
        [
            "",
            "## Run Diagnostics",
            "",
            "| Run ID | Component | Scope | Actions | Tools | Repeated tools | Repeated observations | Goal drift | Recovery | Trace |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in diagnostics["rows"]:
        lines.append(
            f"| `{row['run_id']}` | `{row['component_config_id']}` | `{row['diagnostic_scope']}` | "
            f"{row.get('action_count', 'n/a')} | {row.get('tool_call_count', 'n/a')} | "
            f"{row.get('repeated_tool_call_count', 'n/a')} | "
            f"{row.get('repeated_observation_count', 'n/a')} | "
            f"{_format_number(row.get('goal_drift'))} | {row.get('recovery_steps', 'n/a')} | "
            f"`{row.get('trace_path')}` |"
        )

    lines.extend(
        [
            "",
            "## Component Summaries",
            "",
            "| Component | Runs | Mean actions | Mean tools | Mean repeated tools | Mean repeated observations |",
            "|---|---|---|---|---|---|",
        ]
    )
    for summary in diagnostics["component_summaries"]:
        lines.append(
            f"| `{summary['component_config_id']}` | {summary['run_count']} | "
            f"{_format_number(summary['mean_action_count'])} | "
            f"{_format_number(summary['mean_tool_call_count'])} | "
            f"{_format_number(summary['mean_repeated_tool_call_count'])} | "
            f"{_format_number(summary['mean_repeated_observation_count'])} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation Note",
            "",
            "Trajectory diagnostics are derived from stored `RunTrace` artifacts. Rows labelled "
            "`agent_behavior` are included, hash-validated experiment outcomes. Other scopes are "
            "kept separate so infrastructure or artifact issues are not interpreted as agent behavior.",
            "",
        ]
    )
    return "\n".join(lines)


def _component_summaries(rows: List[Mapping[str, Any]]) -> List[Dict[str, object]]:
    grouped: Dict[str, List[Mapping[str, Any]]] = {}
    for row in rows:
        if row.get("diagnostic_scope") != "agent_behavior":
            continue
        grouped.setdefault(str(row["component_config_id"]), []).append(row)

    summaries: List[Dict[str, object]] = []
    for component_id, component_rows in sorted(grouped.items()):
        summaries.append(
            {
                "component_config_id": component_id,
                "run_count": len(component_rows),
                "run_ids": sorted(str(row["run_id"]) for row in component_rows),
                "mean_action_count": _mean(_numeric_values(component_rows, "action_count")),
                "mean_tool_call_count": _mean(_numeric_values(component_rows, "tool_call_count")),
                "mean_repeated_tool_call_count": _mean(
                    _numeric_values(component_rows, "repeated_tool_call_count")
                ),
                "mean_repeated_observation_count": _mean(
                    _numeric_values(component_rows, "repeated_observation_count")
                ),
                "mean_goal_drift": _mean(_numeric_values(component_rows, "goal_drift")),
                "mean_repetition_rate": _mean(_numeric_values(component_rows, "repetition_rate")),
            }
        )
    return summaries


def _load_trace(path: Optional[Path], run_id: str, issues: List[str]) -> Optional[RunTrace]:
    if path is None:
        issues.append(f"Missing trace artifact path for {run_id}")
        return None
    try:
        trace = RunTrace.from_dict(_read_json_object(path, "trace"))
    except ValidationError as exc:
        issues.append(str(exc))
        return None
    if trace.run_id != run_id:
        issues.append(f"Trace run_id mismatch for {run_id}: {trace.run_id}")
        return None
    return trace


def _diagnostic_scope(
    row: Mapping[str, Any],
    trace: Optional[RunTrace],
    issues: Sequence[str],
) -> str:
    if trace is None:
        return "trace_unavailable"
    if row.get("inclusion_status") != "included":
        return "dataset_excluded"
    if row.get("artifact_hash_validation_passed") is not True or row.get("analysis_issues"):
        return "artifact_or_analysis_issue"
    if issues:
        return "artifact_or_analysis_issue"
    return "agent_behavior"


def _trace_path(row: Mapping[str, Any]) -> Optional[Path]:
    artifacts = row.get("artifact_paths")
    if not isinstance(artifacts, dict):
        return None
    path = artifacts.get("trace")
    if not isinstance(path, str) or not path:
        return None
    return Path(path)


def _action_sequence(trace: RunTrace) -> List[str]:
    names: List[str] = []
    for event in trace.events:
        if event.event_type != "agent_step":
            continue
        if event.payload.get("stage") != "act":
            continue
        action = event.payload.get("action")
        if isinstance(action, dict) and isinstance(action.get("name"), str):
            names.append(action["name"])
    return names


def _tool_sequence(trace: RunTrace) -> List[str]:
    names: List[str] = []
    for event in trace.events:
        if event.event_type != "tool_call":
            continue
        tool_name = event.payload.get("tool_name")
        if isinstance(tool_name, str) and tool_name:
            names.append(tool_name)
    return names


def _observation_statuses(trace: RunTrace) -> List[str]:
    statuses: List[str] = []
    for event in trace.events:
        if event.event_type != "observation":
            continue
        observation = event.payload.get("observation")
        if isinstance(observation, dict) and isinstance(observation.get("status"), str):
            statuses.append(observation["status"])
    return statuses


def _observation_signatures(trace: RunTrace) -> List[str]:
    signatures: List[str] = []
    for event in trace.events:
        if event.event_type != "observation":
            continue
        observation = event.payload.get("observation")
        if not isinstance(observation, dict):
            continue
        signature = {
            "source": observation.get("source"),
            "status": observation.get("status"),
            "content": observation.get("content"),
        }
        signatures.append(json.dumps(signature, sort_keys=True, separators=(",", ":")))
    return signatures


def _adjacent_repeat_count(values: Sequence[str]) -> int:
    repeated = 0
    previous: Optional[str] = None
    for value in values:
        if value == previous:
            repeated += 1
        previous = value
    return repeated


def _goal_drift(trace: RunTrace, final_answer_present: bool, action_count: int) -> float:
    if action_count == 0:
        return 0.0 if final_answer_present else 1.0
    if final_answer_present:
        return 0.0
    progressing_updates = 0
    for event in trace.events:
        if event.event_type != "state_update":
            continue
        state_delta = event.payload.get("state_delta")
        if isinstance(state_delta, dict) and state_delta:
            progressing_updates += 1
    non_progressing = max(action_count - progressing_updates, 0)
    return non_progressing / action_count


def _numeric_values(rows: Sequence[Mapping[str, Any]], field: str) -> List[float]:
    values: List[float] = []
    for row in rows:
        value = row.get(field)
        if isinstance(value, bool):
            values.append(1.0 if value else 0.0)
        elif isinstance(value, (int, float)):
            values.append(float(value))
    return values


def _mean(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _validate_metrics_table(metrics_table: Mapping[str, Any]) -> None:
    if metrics_table.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError("metrics_table.schema_version is invalid")
    _table_str(metrics_table, "dataset_id")
    _table_str(metrics_table, "experiment_id")
    row_count = _table_int(metrics_table, "row_count")
    rows = _metric_rows(metrics_table)
    if row_count != len(rows):
        raise ValidationError("metrics_table.row_count does not match rows length")


def _metric_rows(metrics_table: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = metrics_table.get("rows")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValidationError("metrics_table.rows must be a list of objects")
    return list(rows)


def _read_json_object(path: Path, artifact_name: str) -> Dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"Required {artifact_name} artifact not found: {path}") from exc
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValidationError(f"Invalid {artifact_name} JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError(f"{artifact_name} artifact must contain a JSON object: {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _format_number(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def _table_str(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ValidationError(f"metrics_table.{field} must be a non-empty string")
    return value


def _table_int(payload: Mapping[str, Any], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"metrics_table.{field} must be an integer")
    return value


def _row_str(row: Mapping[str, Any], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ValidationError(f"metrics row {field} must be a non-empty string")
    return value


def _row_int(row: Mapping[str, Any], field: str) -> int:
    value = row.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"metrics row {field} must be an integer")
    return value
