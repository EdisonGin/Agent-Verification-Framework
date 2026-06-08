"""Phase 4B component-effect summaries over normalized metrics tables."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from avf.contracts import SCHEMA_VERSION, ValidationError
from avf.orchestration.pilot_qa import current_commit_hash, utc_timestamp


PHASE4B_ANALYSIS_VERSION = "1.0"
COMPONENT_EFFECTS_JSON_FILE = "component_effects.json"
COMPONENT_EFFECTS_MARKDOWN_FILE = "component_effects.md"
INTERACTION_SUMMARY_JSON_FILE = "interaction_summary.json"
INTERACTION_SUMMARY_MARKDOWN_FILE = "interaction_summary.md"
DISSERTATION_TABLES_FILE = "dissertation_tables.md"

FACTOR_DEFINITIONS = [
    {
        "factor_id": "A",
        "factor_name": "memory backend",
        "field": "memory_backend",
        "level_1_code": "A1",
        "level_1_value": "sqlite",
        "level_2_code": "A2",
        "level_2_value": "vector",
    },
    {
        "factor_id": "B",
        "factor_name": "retrieval strategy",
        "field": "retrieval_strategy",
        "level_1_code": "B1",
        "level_1_value": "bm25",
        "level_2_code": "B2",
        "level_2_value": "embedding",
    },
    {
        "factor_id": "C",
        "factor_name": "scheduling policy",
        "field": "scheduling_policy",
        "level_1_code": "C1",
        "level_1_value": "sequential",
        "level_2_code": "C2",
        "level_2_value": "rule_based",
    },
]

METRIC_DEFINITIONS = [
    {"metric_name": "task_success", "metric_type": "binary", "direction": "higher_is_better"},
    {"metric_name": "verification_passed", "metric_type": "binary", "direction": "higher_is_better"},
    {"metric_name": "latency_ms", "metric_type": "numeric", "direction": "lower_is_better"},
    {"metric_name": "step_count", "metric_type": "numeric", "direction": "lower_is_better"},
    {"metric_name": "tool_call_count", "metric_type": "numeric", "direction": "lower_is_better"},
    {"metric_name": "goal_drift", "metric_type": "numeric", "direction": "lower_is_better"},
    {"metric_name": "repetition_rate", "metric_type": "numeric", "direction": "lower_is_better"},
    {"metric_name": "final_answer_present", "metric_type": "binary", "direction": "higher_is_better"},
]

EXPECTED_COMPONENT_IDS = [
    "A1_B1_C1",
    "A1_B1_C2",
    "A1_B2_C1",
    "A1_B2_C2",
    "A2_B1_C1",
    "A2_B1_C2",
    "A2_B2_C1",
    "A2_B2_C2",
]

INTERACTION_DEFINITIONS = [
    ("A:B", ("A", "B")),
    ("A:C", ("A", "C")),
    ("B:C", ("B", "C")),
    ("A:B:C", ("A", "B", "C")),
]


@dataclass(frozen=True)
class Phase4BComponentEffectArtifacts:
    """Artifacts produced by Phase 4B component-effect analysis."""

    component_effects_json: Path
    component_effects_markdown: Path
    interaction_summary_json: Path
    interaction_summary_markdown: Path
    dissertation_tables: Path

    def to_dict(self) -> Dict[str, str]:
        return {
            "component_effects_json": str(self.component_effects_json),
            "component_effects_markdown": str(self.component_effects_markdown),
            "interaction_summary_json": str(self.interaction_summary_json),
            "interaction_summary_markdown": str(self.interaction_summary_markdown),
            "dissertation_tables": str(self.dissertation_tables),
        }


@dataclass(frozen=True)
class Phase4BComponentEffectResult:
    """Outputs from Phase 4B component-effect analysis."""

    dataset_id: str
    experiment_id: str
    artifacts: Phase4BComponentEffectArtifacts
    component_effects: Dict[str, object]
    interaction_summary: Dict[str, object]
    dissertation_tables_markdown: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "dataset_id": self.dataset_id,
            "experiment_id": self.experiment_id,
            "complete_block_count": self.component_effects["complete_block_count"],
            "incomplete_block_count": self.component_effects["incomplete_block_count"],
            "descriptive_only": self.component_effects["limitations"]["descriptive_only"],
            "artifacts": self.artifacts.to_dict(),
        }


def summarize_phase4b_component_effects(
    metrics_table_path: Path,
    analysis_root: Optional[Path] = None,
    generated_at: Optional[str] = None,
    code_version: Optional[str] = None,
) -> Phase4BComponentEffectResult:
    """Compute descriptive component-effect summaries over a Phase 4A metrics table."""

    metrics_path = Path(metrics_table_path)
    metrics_table = _read_json_object(metrics_path, "metrics_table")
    _validate_metrics_table(metrics_table)
    rows = _eligible_rows(metrics_table)
    blocks = build_matched_blocks(rows)

    dataset_id = _table_str(metrics_table, "dataset_id")
    experiment_id = _table_str(metrics_table, "experiment_id")
    timestamp = generated_at or utc_timestamp()
    version = code_version or current_commit_hash()

    output_root = Path(analysis_root) if analysis_root is not None else metrics_path.parent.parent
    analysis_dir = output_root / dataset_id
    artifacts = Phase4BComponentEffectArtifacts(
        component_effects_json=analysis_dir / COMPONENT_EFFECTS_JSON_FILE,
        component_effects_markdown=analysis_dir / COMPONENT_EFFECTS_MARKDOWN_FILE,
        interaction_summary_json=analysis_dir / INTERACTION_SUMMARY_JSON_FILE,
        interaction_summary_markdown=analysis_dir / INTERACTION_SUMMARY_MARKDOWN_FILE,
        dissertation_tables=analysis_dir / DISSERTATION_TABLES_FILE,
    )

    component_effects = build_component_effects_payload(
        metrics_table=metrics_table,
        blocks=blocks,
        metrics_table_path=metrics_path,
        generated_at=timestamp,
        code_version=version,
    )
    interaction_summary = build_interaction_summary_payload(
        metrics_table=metrics_table,
        blocks=blocks,
        generated_at=timestamp,
        code_version=version,
    )
    component_markdown = build_component_effects_markdown(component_effects)
    interaction_markdown = build_interaction_summary_markdown(interaction_summary)
    dissertation_tables = build_dissertation_tables_markdown(component_effects, interaction_summary)

    _write_json(artifacts.component_effects_json, component_effects)
    _write_json(artifacts.interaction_summary_json, interaction_summary)
    _write_text(artifacts.component_effects_markdown, component_markdown)
    _write_text(artifacts.interaction_summary_markdown, interaction_markdown)
    _write_text(artifacts.dissertation_tables, dissertation_tables)

    return Phase4BComponentEffectResult(
        dataset_id=dataset_id,
        experiment_id=experiment_id,
        artifacts=artifacts,
        component_effects=component_effects,
        interaction_summary=interaction_summary,
        dissertation_tables_markdown=dissertation_tables,
    )


def build_matched_blocks(rows: List[Mapping[str, Any]]) -> Dict[str, object]:
    """Group rows into complete and incomplete matched factorial blocks."""

    grouped: Dict[Tuple[object, ...], List[Mapping[str, Any]]] = {}
    for row in rows:
        key = _block_key(row)
        grouped.setdefault(key, []).append(row)

    complete_blocks: List[Dict[str, object]] = []
    incomplete_blocks: List[Dict[str, object]] = []
    for key, block_rows in sorted(grouped.items(), key=lambda item: str(item[0])):
        block = _block_summary(key, block_rows)
        if block["is_complete"]:
            complete_blocks.append(block)
        else:
            incomplete_blocks.append(block)

    return {
        "complete_blocks": complete_blocks,
        "incomplete_blocks": incomplete_blocks,
    }


def build_component_effects_payload(
    metrics_table: Mapping[str, Any],
    blocks: Mapping[str, Any],
    metrics_table_path: Path,
    generated_at: str,
    code_version: str,
) -> Dict[str, object]:
    """Build factor-level and main-effect summaries."""

    complete_blocks = _complete_blocks(blocks)
    incomplete_blocks = _incomplete_blocks(blocks)
    factor_level_summaries = _factor_level_summaries(complete_blocks)
    main_effects = _main_effects(complete_blocks)

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_version": PHASE4B_ANALYSIS_VERSION,
        "dataset_id": metrics_table["dataset_id"],
        "experiment_id": metrics_table["experiment_id"],
        "generated_at": generated_at,
        "code_version": code_version,
        "metrics_table_artifact": str(metrics_table_path),
        "row_count": metrics_table["row_count"],
        "eligible_run_count": sum(len(block["rows"]) for block in complete_blocks)
        + sum(len(block["rows"]) for block in incomplete_blocks),
        "complete_block_count": len(complete_blocks),
        "incomplete_block_count": len(incomplete_blocks),
        "factor_definitions": FACTOR_DEFINITIONS,
        "metric_definitions": METRIC_DEFINITIONS,
        "factor_level_summaries": factor_level_summaries,
        "main_effects": main_effects,
        "matched_blocks": [
            _block_without_rows(block)
            for block in complete_blocks
        ],
        "incomplete_blocks": [
            _block_without_rows(block)
            for block in incomplete_blocks
        ],
        "limitations": _limitations(len(complete_blocks)),
        "analysis_acceptance_criteria": {
            "dataset_id_recorded": True,
            "analysis_code_version_recorded": True,
            "component_effects_traceable_to_run_ids": True,
            "incomplete_blocks_flagged": True,
            "incomplete_blocks_excluded_from_contrasts": True,
            "current_small_sample_labelled_descriptive": True,
            "inferential_confidence_interval_reported": False,
        },
    }


def build_interaction_summary_payload(
    metrics_table: Mapping[str, Any],
    blocks: Mapping[str, Any],
    generated_at: str,
    code_version: str,
) -> Dict[str, object]:
    """Build two-way and three-way factorial interaction summaries."""

    complete_blocks = _complete_blocks(blocks)
    interaction_effects = _interaction_effects(complete_blocks)
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_version": PHASE4B_ANALYSIS_VERSION,
        "dataset_id": metrics_table["dataset_id"],
        "experiment_id": metrics_table["experiment_id"],
        "generated_at": generated_at,
        "code_version": code_version,
        "complete_block_count": len(complete_blocks),
        "interactions": interaction_effects,
        "limitations": _limitations(len(complete_blocks)),
    }


def build_component_effects_markdown(component_effects: Mapping[str, Any]) -> str:
    """Build a dissertation-readable main-effect report."""

    lines = [
        "# Phase 4B Component Effect Summaries",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Dataset ID | `{component_effects['dataset_id']}` |",
        f"| Experiment ID | `{component_effects['experiment_id']}` |",
        f"| Complete matched blocks | {component_effects['complete_block_count']} |",
        f"| Incomplete matched blocks | {component_effects['incomplete_block_count']} |",
        f"| Descriptive only | `{str(component_effects['limitations']['descriptive_only']).lower()}` |",
        "",
        "## Main Effects",
        "",
        "| Factor | Metric | Level 1 mean | Level 2 mean | Effect | Blocks |",
        "|---|---|---|---|---|---|",
    ]
    for effect in component_effects["main_effects"]:
        lines.append(
            f"| `{effect['factor_id']}` {effect['factor_name']} | `{effect['metric_name']}` | "
            f"{_format_number(effect['level_1_mean'])} | {_format_number(effect['level_2_mean'])} | "
            f"{_format_number(effect['effect'])} | {effect['block_count']} |"
        )

    lines.extend(["", "## Incomplete Blocks", ""])
    if component_effects["incomplete_blocks"]:
        lines.extend(["| Block key | Missing component cells |", "|---|---|"])
        for block in component_effects["incomplete_blocks"]:
            lines.append(
                f"| `{block['block_id']}` | {', '.join(block['missing_component_config_ids'])} |"
            )
    else:
        lines.append("No incomplete matched blocks were detected.")

    lines.extend(
        [
            "",
            "## Interpretation Note",
            "",
            component_effects["limitations"]["reason"],
            "",
        ]
    )
    return "\n".join(lines)


def build_interaction_summary_markdown(interaction_summary: Mapping[str, Any]) -> str:
    """Build a dissertation-readable interaction summary."""

    lines = [
        "# Phase 4B Interaction Summary",
        "",
        "| Interaction | Metric | Positive mean | Negative mean | Contrast | Blocks |",
        "|---|---|---|---|---|---|",
    ]
    for interaction in interaction_summary["interactions"]:
        lines.append(
            f"| `{interaction['interaction_id']}` | `{interaction['metric_name']}` | "
            f"{_format_number(interaction['positive_sign_mean'])} | "
            f"{_format_number(interaction['negative_sign_mean'])} | "
            f"{_format_number(interaction['contrast'])} | {interaction['block_count']} |"
        )
    if not interaction_summary["interactions"]:
        lines.append("| n/a | n/a | n/a | n/a | n/a | 0 |")
    lines.extend(
        [
            "",
            "Interaction contrasts are descriptive. No inferential confidence intervals are reported for the current dataset.",
            "",
        ]
    )
    return "\n".join(lines)


def build_dissertation_tables_markdown(
    component_effects: Mapping[str, Any],
    interaction_summary: Mapping[str, Any],
) -> str:
    """Build compact Markdown tables that can be adapted for dissertation text."""

    lines = [
        "# Phase 4B Dissertation Tables",
        "",
        "## Table 1: Matched Block Coverage",
        "",
        "| Dataset | Complete blocks | Incomplete blocks | Analysis claim level |",
        "|---|---|---|---|",
        f"| `{component_effects['dataset_id']}` | {component_effects['complete_block_count']} | "
        f"{component_effects['incomplete_block_count']} | descriptive |",
        "",
        "## Table 2: Main Effects for Primary Outcome Metrics",
        "",
        "| Factor | Metric | Level 1 mean | Level 2 mean | Effect |",
        "|---|---|---|---|---|",
    ]
    primary_metrics = {"task_success", "verification_passed", "step_count", "tool_call_count"}
    for effect in component_effects["main_effects"]:
        if effect["metric_name"] not in primary_metrics:
            continue
        lines.append(
            f"| `{effect['factor_id']}` {effect['factor_name']} | `{effect['metric_name']}` | "
            f"{_format_number(effect['level_1_mean'])} | {_format_number(effect['level_2_mean'])} | "
            f"{_format_number(effect['effect'])} |"
        )

    lines.extend(
        [
            "",
            "## Table 3: Interaction Contrasts for Primary Outcome Metrics",
            "",
            "| Interaction | Metric | Positive mean | Negative mean | Contrast |",
            "|---|---|---|---|---|",
        ]
    )
    for interaction in interaction_summary["interactions"]:
        if interaction["metric_name"] not in primary_metrics:
            continue
        lines.append(
            f"| `{interaction['interaction_id']}` | `{interaction['metric_name']}` | "
            f"{_format_number(interaction['positive_sign_mean'])} | "
            f"{_format_number(interaction['negative_sign_mean'])} | "
            f"{_format_number(interaction['contrast'])} |"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Effects are computed as Level 2 mean minus Level 1 mean for each factor.",
            "- Interaction contrasts compare positive-sign cells with negative-sign cells under two-level factorial coding.",
            "- The current dataset is labelled descriptive because it contains only one matched block.",
            "",
        ]
    )
    return "\n".join(lines)


def _factor_level_summaries(complete_blocks: List[Mapping[str, Any]]) -> List[Dict[str, object]]:
    summaries: List[Dict[str, object]] = []
    rows = _flatten_block_rows(complete_blocks)
    for factor in FACTOR_DEFINITIONS:
        field = str(factor["field"])
        for code_field, value_field in (("level_1_code", "level_1_value"), ("level_2_code", "level_2_value")):
            level_rows = [row for row in rows if row.get(field) == factor[value_field]]
            for metric in METRIC_DEFINITIONS:
                values = _metric_values(level_rows, str(metric["metric_name"]))
                summaries.append(
                    {
                        "factor_id": factor["factor_id"],
                        "factor_name": factor["factor_name"],
                        "field": field,
                        "level_code": factor[code_field],
                        "level_value": factor[value_field],
                        "metric_name": metric["metric_name"],
                        "metric_type": metric["metric_type"],
                        "count": len(values),
                        "mean": _mean(values),
                        "min": min(values) if values else None,
                        "max": max(values) if values else None,
                        "run_ids": [_row_str(row, "run_id") for row in level_rows if _metric_value(row, str(metric["metric_name"])) is not None],
                    }
                )
    return summaries


def _main_effects(complete_blocks: List[Mapping[str, Any]]) -> List[Dict[str, object]]:
    effects: List[Dict[str, object]] = []
    for factor in FACTOR_DEFINITIONS:
        field = str(factor["field"])
        for metric in METRIC_DEFINITIONS:
            metric_name = str(metric["metric_name"])
            block_effects: List[Dict[str, object]] = []
            for block in complete_blocks:
                rows = list(block["rows"])
                level_1_rows = [row for row in rows if row.get(field) == factor["level_1_value"]]
                level_2_rows = [row for row in rows if row.get(field) == factor["level_2_value"]]
                level_1_values = _metric_values(level_1_rows, metric_name)
                level_2_values = _metric_values(level_2_rows, metric_name)
                if not level_1_values or not level_2_values:
                    continue
                block_effects.append(
                    {
                        "block_id": block["block_id"],
                        "level_1_mean": _mean(level_1_values),
                        "level_2_mean": _mean(level_2_values),
                        "effect": _mean(level_2_values) - _mean(level_1_values),
                        "level_1_run_ids": [_row_str(row, "run_id") for row in level_1_rows],
                        "level_2_run_ids": [_row_str(row, "run_id") for row in level_2_rows],
                    }
                )
            if not block_effects:
                continue
            level_1_means = [float(item["level_1_mean"]) for item in block_effects]
            level_2_means = [float(item["level_2_mean"]) for item in block_effects]
            effect_values = [float(item["effect"]) for item in block_effects]
            effects.append(
                {
                    "factor_id": factor["factor_id"],
                    "factor_name": factor["factor_name"],
                    "field": field,
                    "level_1": {
                        "code": factor["level_1_code"],
                        "value": factor["level_1_value"],
                    },
                    "level_2": {
                        "code": factor["level_2_code"],
                        "value": factor["level_2_value"],
                    },
                    "metric_name": metric_name,
                    "metric_type": metric["metric_type"],
                    "direction": metric["direction"],
                    "level_1_mean": _mean(level_1_means),
                    "level_2_mean": _mean(level_2_means),
                    "effect": _mean(effect_values),
                    "block_count": len(block_effects),
                    "block_effects": block_effects,
                    "run_ids": sorted(
                        {
                            run_id
                            for item in block_effects
                            for run_id in item["level_1_run_ids"] + item["level_2_run_ids"]
                        }
                    ),
                    "descriptive_only": True,
                }
            )
    return effects


def _interaction_effects(complete_blocks: List[Mapping[str, Any]]) -> List[Dict[str, object]]:
    effects: List[Dict[str, object]] = []
    for interaction_id, factor_ids in INTERACTION_DEFINITIONS:
        for metric in METRIC_DEFINITIONS:
            metric_name = str(metric["metric_name"])
            block_effects: List[Dict[str, object]] = []
            for block in complete_blocks:
                positive_rows: List[Mapping[str, Any]] = []
                negative_rows: List[Mapping[str, Any]] = []
                for row in block["rows"]:
                    sign = _interaction_sign(row, factor_ids)
                    if sign > 0:
                        positive_rows.append(row)
                    else:
                        negative_rows.append(row)
                positive_values = _metric_values(positive_rows, metric_name)
                negative_values = _metric_values(negative_rows, metric_name)
                if not positive_values or not negative_values:
                    continue
                positive_mean = _mean(positive_values)
                negative_mean = _mean(negative_values)
                block_effects.append(
                    {
                        "block_id": block["block_id"],
                        "positive_sign_mean": positive_mean,
                        "negative_sign_mean": negative_mean,
                        "contrast": positive_mean - negative_mean,
                        "positive_run_ids": [_row_str(row, "run_id") for row in positive_rows],
                        "negative_run_ids": [_row_str(row, "run_id") for row in negative_rows],
                    }
                )
            if not block_effects:
                continue
            positive_means = [float(item["positive_sign_mean"]) for item in block_effects]
            negative_means = [float(item["negative_sign_mean"]) for item in block_effects]
            contrasts = [float(item["contrast"]) for item in block_effects]
            effects.append(
                {
                    "interaction_id": interaction_id,
                    "factor_ids": list(factor_ids),
                    "metric_name": metric_name,
                    "metric_type": metric["metric_type"],
                    "positive_sign_mean": _mean(positive_means),
                    "negative_sign_mean": _mean(negative_means),
                    "contrast": _mean(contrasts),
                    "block_count": len(block_effects),
                    "block_effects": block_effects,
                    "run_ids": sorted(
                        {
                            run_id
                            for item in block_effects
                            for run_id in item["positive_run_ids"] + item["negative_run_ids"]
                        }
                    ),
                    "descriptive_only": True,
                }
            )
    return effects


def _interaction_sign(row: Mapping[str, Any], factor_ids: Sequence[str]) -> int:
    sign = 1
    for factor_id in factor_ids:
        factor = _factor_by_id(factor_id)
        value = row.get(str(factor["field"]))
        if value == factor["level_2_value"]:
            sign *= 1
        elif value == factor["level_1_value"]:
            sign *= -1
        else:
            raise ValidationError(f"Unexpected factor level for {factor_id}: {value}")
    return sign


def _block_key(row: Mapping[str, Any]) -> Tuple[object, ...]:
    return (
        _row_str(row, "task_id"),
        _row_str(row, "run_config_id"),
        _row_int(row, "seed"),
        _row_str(row, "perturbation_schedule_id"),
        tuple(row.get("tool_names", [])),
    )


def _block_summary(key: Tuple[object, ...], block_rows: List[Mapping[str, Any]]) -> Dict[str, object]:
    observed = [_row_str(row, "component_config_id") for row in block_rows]
    observed_set = set(observed)
    duplicates = sorted({component_id for component_id in observed if observed.count(component_id) > 1})
    missing = [component_id for component_id in EXPECTED_COMPONENT_IDS if component_id not in observed_set]
    is_complete = not missing and not duplicates and len(block_rows) == len(EXPECTED_COMPONENT_IDS)
    task_id, run_config_id, seed, schedule_id, tool_names = key
    return {
        "block_id": _block_id(key),
        "task_id": task_id,
        "run_config_id": run_config_id,
        "seed": seed,
        "perturbation_schedule_id": schedule_id,
        "tool_names": list(tool_names),
        "run_count": len(block_rows),
        "is_complete": is_complete,
        "observed_component_config_ids": sorted(observed_set),
        "missing_component_config_ids": missing,
        "duplicate_component_config_ids": duplicates,
        "run_ids": sorted(_row_str(row, "run_id") for row in block_rows),
        "rows": sorted(block_rows, key=lambda row: _row_str(row, "component_config_id")),
    }


def _block_id(key: Tuple[object, ...]) -> str:
    task_id, run_config_id, seed, schedule_id, tool_names = key
    tools = "+".join(str(tool) for tool in tool_names) if tool_names else "no_tools"
    return f"{task_id}|{run_config_id}|seed={seed}|schedule={schedule_id}|tools={tools}"


def _block_without_rows(block: Mapping[str, Any]) -> Dict[str, object]:
    return {
        key: value
        for key, value in block.items()
        if key != "rows"
    }


def _eligible_rows(metrics_table: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    rows = metrics_table.get("rows")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValidationError("metrics_table.rows must be a list of objects")
    return [
        row
        for row in rows
        if row.get("inclusion_status") == "included"
        and row.get("artifact_hash_validation_passed") is True
    ]


def _complete_blocks(blocks: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    values = blocks.get("complete_blocks")
    if not isinstance(values, list):
        raise ValidationError("complete_blocks must be a list")
    return values


def _incomplete_blocks(blocks: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    values = blocks.get("incomplete_blocks")
    if not isinstance(values, list):
        raise ValidationError("incomplete_blocks must be a list")
    return values


def _flatten_block_rows(blocks: Iterable[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    rows: List[Mapping[str, Any]] = []
    for block in blocks:
        rows.extend(list(block["rows"]))
    return rows


def _metric_values(rows: List[Mapping[str, Any]], metric_name: str) -> List[float]:
    values: List[float] = []
    for row in rows:
        value = _metric_value(row, metric_name)
        if value is not None:
            values.append(value)
    return values


def _metric_value(row: Mapping[str, Any], metric_name: str) -> Optional[float]:
    value = row.get(metric_name)
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _mean(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _limitations(complete_block_count: int) -> Dict[str, object]:
    if complete_block_count == 0:
        reason = (
            "No complete matched blocks are available, so Phase 4B reports no component contrasts. "
            "Incomplete blocks are documented and excluded from effect estimates."
        )
    elif complete_block_count == 1:
        reason = (
            "The current dataset contains one complete matched block, so Phase 4B reports descriptive "
            "component contrasts only. Additional tasks, seeds, or perturbation schedules are required "
            "before reporting inferential uncertainty estimates."
        )
    else:
        reason = "Phase 4B currently reports descriptive contrasts; inferential uncertainty estimates are deferred."
    return {
        "descriptive_only": True,
        "confidence_intervals_reported": False,
        "reason": reason,
    }


def _validate_metrics_table(metrics_table: Mapping[str, Any]) -> None:
    if metrics_table.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError("metrics_table.schema_version is invalid")
    _table_str(metrics_table, "dataset_id")
    _table_str(metrics_table, "experiment_id")
    row_count = _table_int(metrics_table, "row_count")
    rows = metrics_table.get("rows")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValidationError("metrics_table.rows must be a list of objects")
    if row_count != len(rows):
        raise ValidationError("metrics_table.row_count does not match rows length")


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


def _factor_by_id(factor_id: str) -> Mapping[str, object]:
    for factor in FACTOR_DEFINITIONS:
        if factor["factor_id"] == factor_id:
            return factor
    raise ValidationError(f"Unknown factor ID: {factor_id}")


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
