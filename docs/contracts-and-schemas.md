# Contracts and Schemas

## Purpose

This document defines the initial contracts and schema decisions for the automated testing infrastructure.

The contracts are the foundation of the system. They define how the orchestration, mock service, verification, and reporting layers exchange data. Stable contracts are necessary for reproducible experiments and for controlled component substitution.

## Design Principles

The schema design follows six principles:

1. Contracts are defined at layer boundaries.
2. Schemas are implementation-neutral.
3. Every important artifact is versioned.
4. Every run is replayable from stored inputs.
5. Trace events are sufficiently complete for verification and diagnostics.
6. Component variants share the same external interface.

## Core Schema Set

| Schema | Purpose |
|---|---|
| `TaskCase` | Defines a benchmark task, task family, initial state, tool permissions, success criteria, and progress model |
| `RunConfig` | Defines model, prompt, seed, perturbation schedule, runtime settings, and artifact locations |
| `ComponentConfig` | Selects memory, retrieval, and scheduling variants |
| `ExperimentConfig` | Defines the ordered task, run config, component, tool schema, schedule, execution-policy, and dataset-policy references for an experiment |
| `ExperimentMatrixRow` | Records one resolved task/seed/schedule/component/tool-schema cell and its expected deterministic run ID |
| `RerunRecord` | Records rerun intent, decision, operator notes, timestamp, and commit hash for a controlled cell |
| `FailureNote` | Classifies pilot failures and records the dataset decision for QA gating |
| `DatasetIndex` | Records the frozen analysis entrypoint with run metadata, inclusion decisions, artifact paths, and hashes |
| `FrozenDatasetManifest` | Records dataset freeze metadata, source artifact hashes, freeze artifact hashes, commit hash, and immutability policy |
| `StorageVolumeReview` | Summarises frozen dataset artifact volume and filesystem scan strategy |
| `QueryRequirements` | Records analysis filters, groupings, joins, and dashboard candidate views derived from the frozen dataset |
| `ResultsIndexDecision` | Records whether filesystem artifacts remain sufficient or a read-only results index should be planned |
| `RunContext` | Stores the validated orchestration context created from task, run, component, and tool fixtures |
| `AgentRunInput` | Bundles the orchestrator inputs passed into the base agent / SUT |
| `AgentAction` | Represents an internal action or external tool action selected by the base agent |
| `AgentObservation` | Represents processed feedback returned to the base agent after an action |
| `AgentOutput` | Represents the final answer, artifacts, trace summary, and agent-side metrics |
| `ToolSpec` | Defines a mock MCP-style tool name, input schema, output schema, and error model |
| `ToolCall` | Records one requested tool invocation |
| `ToolResult` | Records one deterministic mock service response or error |
| `TraceEvent` | Records an agent step, tool call, observation, state update, error, or recovery action |
| `RunTrace` | Stores the full trajectory for one task/config/seed/schedule execution |
| `VerificationResult` | Stores verifier decisions, evidence, and failure reasons |
| `MetricResult` | Stores outcome and trajectory metrics for one run |
| `ExperimentResult` | Stores aggregated results for factorial analysis and reporting |

## Versioning

Each persisted artifact should include:

```json
{
  "schema_version": "1.0"
}
```

Additional version fields are used where appropriate:

```json
{
  "task_version": "1.0",
  "prompt_version": "1.0",
  "tool_schema_version": "1.0",
  "perturbation_schedule_version": "1.0"
}
```

Versioning protects the experiments from silent drift.

## TaskCase

`TaskCase` defines a fixed benchmark task.

Required fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Schema version |
| `task_id` | string | Stable task identifier |
| `task_version` | string | Version of this task definition |
| `name` | string | Human-readable task name |
| `family` | enum | `memory`, `retrieval`, or `recovery` |
| `description` | string | Task description for documentation |
| `input_state` | object | Initial deterministic task state |
| `allowed_tools` | list[string] | Tool names available to the agent |
| `success_criteria` | object | Deterministic criteria used by the verifier |
| `progress_model` | object | State milestones used for progress and goal-drift metrics |
| `max_steps` | integer | Maximum agent steps before termination |

Example:

```json
{
  "schema_version": "1.0",
  "task_id": "memory_recall_001",
  "task_version": "1.0",
  "name": "Recall Stored Project Preference",
  "family": "memory",
  "description": "The agent must store a user preference and later recall it correctly.",
  "input_state": {
    "user_preference": "use concise summaries"
  },
  "allowed_tools": ["memory.write", "memory.query"],
  "success_criteria": {
    "required_final_answer_contains": ["concise summaries"],
    "required_tool_calls": ["memory.write", "memory.query"]
  },
  "progress_model": {
    "milestones": ["preference_stored", "preference_retrieved", "answer_returned"]
  },
  "max_steps": 8
}
```

## RunConfig

`RunConfig` defines the fixed runtime context for a run.

Required fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Schema version |
| `run_config_id` | string | Stable run config identifier |
| `model` | object | Fixed model/backbone configuration |
| `prompt` | object | Prompt and system instruction identifiers |
| `seed` | integer | Fixed execution seed |
| `perturbation_schedule_id` | string | Perturbation schedule identifier |
| `runtime` | object | Decoding and execution limits |
| `artifacts` | object | Output paths for trace and results |

Example:

```json
{
  "schema_version": "1.0",
  "run_config_id": "baseline_seed_001",
  "model": {
    "provider": "local_stub",
    "model_id": "baseline-agent-v1",
    "temperature": 0.0
  },
  "prompt": {
    "system_prompt_id": "baseline_system_v1",
    "prompt_version": "1.0"
  },
  "seed": 42,
  "perturbation_schedule_id": "schedule_none_v1",
  "runtime": {
    "max_steps": 8,
    "timeout_seconds": 60
  },
  "artifacts": {
    "trace_dir": "artifacts/traces",
    "result_dir": "artifacts/results"
  }
}
```

## ComponentConfig

`ComponentConfig` selects the experimental factor levels.

Required fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Schema version |
| `config_id` | string | Stable component configuration identifier |
| `memory_backend` | enum | `sqlite` or `vector` |
| `retrieval_strategy` | enum | `bm25` or `embedding` |
| `scheduling_policy` | enum | `sequential` or `rule_based` |

Example:

```json
{
  "schema_version": "1.0",
  "config_id": "A1_B1_C1",
  "memory_backend": "sqlite",
  "retrieval_strategy": "bm25",
  "scheduling_policy": "sequential"
}
```

Factor coding:

| Code | Field | Value |
|---|---|---|
| `A1` | `memory_backend` | `sqlite` |
| `A2` | `memory_backend` | `vector` |
| `B1` | `retrieval_strategy` | `bm25` |
| `B2` | `retrieval_strategy` | `embedding` |
| `C1` | `scheduling_policy` | `sequential` |
| `C2` | `scheduling_policy` | `rule_based` |

Phase 2G provides the complete fixture matrix:

| Fixture ID | Memory backend | Retrieval strategy | Scheduling policy |
|---|---|---|---|
| `A1_B1_C1` | `sqlite` | `bm25` | `sequential` |
| `A1_B1_C2` | `sqlite` | `bm25` | `rule_based` |
| `A1_B2_C1` | `sqlite` | `embedding` | `sequential` |
| `A1_B2_C2` | `sqlite` | `embedding` | `rule_based` |
| `A2_B1_C1` | `vector` | `bm25` | `sequential` |
| `A2_B1_C2` | `vector` | `bm25` | `rule_based` |
| `A2_B2_C1` | `vector` | `embedding` | `sequential` |
| `A2_B2_C2` | `vector` | `embedding` | `rule_based` |

No `TaskCase`, `ToolSpec`, or run schema field changes are required to switch between these component cells.

## RunContext

`RunContext` is created by the Phase 1D orchestrator. It is the validated execution context for one task/config/component/tool-schema cell.

Required fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Schema version |
| `run_id` | string | Deterministic run identifier |
| `status` | enum | Current orchestration status, initially `created` |
| `task` | object | Resolved `TaskCase` |
| `run_config` | object | Resolved `RunConfig` |
| `component_config` | object | Resolved `ComponentConfig` |
| `tool_specs` | list[object] | Resolved `ToolSpec` entries available to the task |
| `seed` | integer | Fixed execution seed copied from `RunConfig` |
| `perturbation_schedule_id` | string | Fixed perturbation schedule ID copied from `RunConfig` |
| `execution_controls` | object | Runtime controls used by later execution phases |

The deterministic `run_id` is derived from controlled inputs only:

- task ID and task version,
- run config ID,
- seed,
- perturbation schedule ID,
- component configuration ID and factor levels,
- tool names and tool schema versions.

It intentionally excludes timestamps and filesystem paths.

## AgentRunInput

`AgentRunInput` defines the boundary from the orchestrator into the base agent / SUT.

Required fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Schema version |
| `run_id` | string | Stable run identifier |
| `task` | object | Resolved `TaskCase` |
| `run_config` | object | Resolved `RunConfig` |
| `component_config` | object | Resolved `ComponentConfig` |
| `tool_specs` | list[object] | Available tool contracts |
| `execution_controls` | object | Max steps, timeout, retry, and logging controls |

The base agent must be executable from this input without reading hidden state.

## AgentAction

`AgentAction` represents one action chosen by the base agent.

Required fields:

| Field | Type | Description |
|---|---|---|
| `action_id` | string | Stable action identifier |
| `run_id` | string | Parent run identifier |
| `step_index` | integer | Agent step index |
| `action_type` | enum | `internal`, `tool_call`, or `final_answer` |
| `name` | string | Action name |
| `arguments` | object | Action arguments |
| `rationale` | string/null | Optional reasoning summary for audit |

## AgentObservation

`AgentObservation` represents feedback after an action.

Required fields:

| Field | Type | Description |
|---|---|---|
| `observation_id` | string | Stable observation identifier |
| `run_id` | string | Parent run identifier |
| `step_index` | integer | Agent step index |
| `source` | string | Source action, tool, or internal module |
| `status` | enum | `success`, `error`, or `partial` |
| `content` | object | Observation payload |
| `state_delta` | object | State changes inferred from the observation |

## AgentOutput

`AgentOutput` represents the base agent's final response to the orchestrator.

Required fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Schema version |
| `run_id` | string | Parent run identifier |
| `status` | enum | `completed`, `failed`, or `timeout` |
| `final_answer` | string/null | Final answer produced by the agent |
| `artifacts` | list[object] | Agent-produced files, data, or logs |
| `metrics` | object | Agent-side metrics such as steps, tokens, errors, and elapsed time |
| `trace_event_ids` | list[string] | Trace events produced by the agent |

## ToolSpec

`ToolSpec` defines a mock MCP-style tool contract.

Required fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Schema version |
| `tool_name` | string | Stable tool name |
| `tool_schema_version` | string | Tool schema version |
| `description` | string | Tool purpose |
| `input_schema` | object | JSON-schema-style input contract |
| `output_schema` | object | JSON-schema-style output contract |
| `error_model` | object | Declared errors and perturbation behavior |

Example:

```json
{
  "schema_version": "1.0",
  "tool_name": "memory.write",
  "tool_schema_version": "1.0",
  "description": "Store an episodic memory record.",
  "input_schema": {
    "type": "object",
    "required": ["key", "value"],
    "properties": {
      "key": {"type": "string"},
      "value": {"type": "string"},
      "metadata": {"type": "object"}
    }
  },
  "output_schema": {
    "type": "object",
    "required": ["ok", "record_id"],
    "properties": {
      "ok": {"type": "boolean"},
      "record_id": {"type": "string"}
    }
  },
  "error_model": {
    "supports_temporary_unavailability": true,
    "supports_noisy_observation": false
  }
}
```

## ToolCall

`ToolCall` records a requested invocation.

Required fields:

| Field | Type | Description |
|---|---|---|
| `tool_call_id` | string | Unique call identifier |
| `run_id` | string | Parent run identifier |
| `step_index` | integer | Agent step index |
| `tool_name` | string | Tool being called |
| `arguments` | object | Tool input arguments |
| `requested_at` | string | Timestamp |

## ToolResult

`ToolResult` records the mock service response.

Required fields:

| Field | Type | Description |
|---|---|---|
| `tool_call_id` | string | Associated tool call |
| `status` | enum | `success`, `error`, or `perturbed` |
| `output` | object | Tool output payload |
| `error` | object/null | Error detail if applicable |
| `latency_ms` | integer | Simulated or measured latency |
| `perturbation_applied` | object/null | Perturbation metadata |

## TraceEvent

`TraceEvent` is the atomic event type for run logging.

Required fields:

| Field | Type | Description |
|---|---|---|
| `event_id` | string | Unique event identifier |
| `run_id` | string | Parent run identifier |
| `event_type` | enum | `agent_step`, `tool_call`, `tool_result`, `observation`, `state_update`, `error`, `recovery`, `final_answer` |
| `step_index` | integer | Agent step index |
| `timestamp` | string | Timestamp |
| `payload` | object | Event-specific data |

Trace events must be rich enough to support replay, verification, and trajectory metrics.

## RunTrace

`RunTrace` stores a full execution trajectory.

Required fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Schema version |
| `run_id` | string | Stable run identifier |
| `task_id` | string | Task identifier |
| `run_config_id` | string | Run config identifier |
| `component_config_id` | string | Component config identifier |
| `seed` | integer | Execution seed |
| `perturbation_schedule_id` | string | Perturbation schedule |
| `started_at` | string | Start timestamp |
| `completed_at` | string/null | Completion timestamp |
| `status` | enum | `completed`, `failed`, or `timeout` |
| `events` | list[TraceEvent] | Ordered event list |

## VerificationResult

`VerificationResult` stores verifier decisions.

Required fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Schema version |
| `run_id` | string | Parent run identifier |
| `verifier_id` | string | Verifier identifier |
| `verifier_type` | enum | `rule_based`, `llm_judge`, or `consensus` |
| `passed` | boolean | Overall verifier decision |
| `score` | number/null | Optional score |
| `evidence` | list[object] | Trace-backed evidence |
| `failure_reasons` | list[string] | Human-readable failure reasons |

## MetricResult

`MetricResult` stores outcome and trajectory diagnostics.

Required fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Schema version |
| `run_id` | string | Parent run identifier |
| `task_success` | boolean | Final task success |
| `latency_ms` | integer | Total run latency |
| `step_count` | integer | Number of agent steps |
| `tool_call_count` | integer | Number of tool calls |
| `goal_drift` | number | Proportion of non-progressing steps |
| `repetition_rate` | number | Fraction of repeated actions without state change |
| `recovery_steps` | integer/null | Steps to recover after first failure |

## ExperimentResult

`ExperimentResult` stores aggregated results for analysis.

Required fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Schema version |
| `experiment_id` | string | Experiment identifier |
| `factorial_design` | object | Factor levels and configuration IDs |
| `run_ids` | list[string] | Included runs |
| `aggregation` | object | Summary statistics |
| `analysis_artifacts` | object | Paths to reports, tables, and plots |

## ExperimentConfig

`ExperimentConfig` is introduced in Phase 3A as an orchestration artifact for experiment execution. It is stored as JSON under `test_data/experiments/` and archived into each experiment artifact directory before the run index is written.

Required fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Schema version |
| `experiment_id` | string | Stable experiment identifier |
| `task_fixtures` | list[string] | Ordered `TaskCase` fixture paths |
| `run_config_fixtures` | list[string] | Ordered `RunConfig` fixture paths; each encodes seed and perturbation schedule |
| `component_fixtures` | list[string] | Ordered `ComponentConfig` fixture paths |
| `tool_spec_fixtures` | list[string] | Fixed tool schema set used by every row |
| `perturbation_schedules` | list[string] | Declared schedule IDs allowed by the experiment |
| `execution_policy` | object | Local execution mode, rerun policy, retry limit, and full-factorial requirement |
| `artifact_root` | string/null | Optional output root; CLI can override it |
| `dataset_policy` | object | Dataset inclusion/freeze policy metadata for later Phase 3 subphases |

Phase 3A does not use `ExperimentConfig` to change task, tool, verifier, metric, or component schemas. It only records which existing fixtures are included in the matched experiment.

## ExperimentMatrixRow

`ExperimentMatrixRow` is a resolved row produced from `ExperimentConfig`.

Required fields:

| Field | Type | Description |
|---|---|---|
| `row_id` | string | Stable row identifier such as `row_001` |
| `task_fixture` | string | Resolved task fixture path |
| `run_config_fixture` | string | Resolved run config fixture path |
| `component_fixture` | string | Resolved component fixture path |
| `tool_spec_fixtures` | list[string] | Resolved tool spec fixture paths |
| `task_id` | string | Resolved task ID |
| `task_version` | string | Resolved task version |
| `run_config_id` | string | Resolved run config ID |
| `seed` | integer | Seed copied from `RunConfig` |
| `perturbation_schedule_id` | string | Schedule copied from `RunConfig` |
| `component_config_id` | string | Resolved component fixture ID |
| `memory_backend` | string | Selected memory factor level |
| `retrieval_strategy` | string | Selected retrieval factor level |
| `scheduling_policy` | string | Selected scheduling factor level |
| `tool_names` | list[string] | Ordered tool names used by the row |
| `tool_schema_versions` | object | Tool name to schema-version mapping |
| `expected_run_id` | string | Deterministic run ID expected from this row |

Phase 3A stores the resolved matrix at:

```text
artifacts/experiments/<experiment_id>/matrix.json
```

The run index is stored separately at:

```text
artifacts/experiments/<experiment_id>/run_index.json
```

It records the actual run ID, status, success flags, component factors, artifact validation status, and relative artifact paths for each row.

## RerunRecord

`RerunRecord` is introduced in Phase 3B as a QA artifact. It documents why a deterministic run cell was rerun or why a rerun should happen.

Required fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Schema version |
| `rerun_id` | string | Stable rerun record identifier |
| `original_run_id` | string | Deterministic run ID for the affected cell |
| `component_config_id` | string | Component cell |
| `task_id` | string | Task identifier |
| `seed` | integer | Run seed |
| `perturbation_schedule_id` | string | Perturbation schedule |
| `reason` | string | Why rerun was needed |
| `decision` | enum | `overwrite`, `exclude`, `preserve_failed_attempt`, or `restart_block` |
| `operator_notes` | string | Human QA note |
| `timestamp` | string | Record timestamp |
| `commit_hash` | string | Code version used for the rerun decision |

Rerun records are stored at:

```text
artifacts/experiments/<experiment_id>/rerun_records.json
```

Phase 3B writes an empty valid record set when no reruns are required.

## FailureNote

`FailureNote` is introduced in Phase 3B to keep failure QA separate from ordinary verification outcomes.

Required fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Schema version |
| `run_id` | string | Affected run |
| `component_config_id` | string | Component cell |
| `task_id` | string | Task identifier |
| `seed` | integer | Run seed |
| `perturbation_schedule_id` | string | Perturbation schedule |
| `failure_class` | enum | `task_failure`, `verifier_failure`, `artifact_failure`, or `infrastructure_failure` |
| `observed_symptom` | string | What happened |
| `root_cause` | string | Known cause or `unknown` |
| `dataset_decision` | enum | `include`, `exclude`, `rerun`, or `block_freeze` |
| `evidence_paths` | list[string] | Trace, report, manifest, or related artifact paths |

Failure notes are stored at:

```text
artifacts/experiments/<experiment_id>/failure_notes.json
artifacts/experiments/<experiment_id>/failure_notes.md
```

Phase 3B also writes failure-note templates for the four failure classes. Unresolved infrastructure failures use `dataset_decision=block_freeze`; the dataset execution gate blocks progression until such failures are resolved.

## DatasetIndex

`DatasetIndex` is introduced in Phase 3C as the analysis-facing frozen dataset entrypoint.

Required top-level fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Schema version |
| `dataset_index_version` | string | Dataset index format version |
| `dataset_id` | string | Stable frozen dataset identifier |
| `experiment_id` | string | Source experiment identifier |
| `frozen_at` | string | Freeze timestamp |
| `commit_hash` | string | Code version used for the freeze |
| `operator_notes` | string | Human freeze note |
| `experiment_config_path` | string/null | Config fixture path used for the freeze |
| `experiment_config_artifact` | string | Archived config artifact path |
| `matrix_artifact` | string | Matrix artifact path |
| `run_index_artifact` | string | Run index artifact path |
| `pilot_qa_summary_artifact` | string | Pilot QA summary artifact path |
| `fixture_versions` | object | Task, run config, component, tool schema, and perturbation references |
| `matrix_summary` | object | Task IDs, run config IDs, seeds, schedules, and component cells |
| `qa_summary` | object | Pilot decision, readiness flag, failure-note count, and rerun-record count |
| `run_count` | integer | Total frozen run records |
| `included_run_count` | integer | Runs included for analysis |
| `excluded_run_count` | integer | Runs excluded from analysis |
| `records` | list[object] | Per-run frozen dataset records |

Each dataset record includes:

- run ID,
- task ID and task version,
- run config ID,
- seed,
- perturbation schedule ID,
- component config ID,
- memory, retrieval, and scheduling levels,
- inclusion status,
- dataset decision,
- exclusion reason when applicable,
- task success and verification status,
- artifact validation status,
- trace, verification, metrics, report, and manifest artifact records with relative paths, SHA-256 hashes, and byte sizes.

The dataset index is stored at:

```text
artifacts/experiments/<experiment_id>/dataset_index.json
```

Analysis should consume `dataset_index.json` rather than scanning mutable directories or rerunning experiments.

## FrozenDatasetManifest

`FrozenDatasetManifest` records the integrity boundary around the frozen dataset.

Required fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Schema version |
| `frozen_dataset_manifest_version` | string | Manifest format version |
| `dataset_id` | string | Frozen dataset identifier |
| `experiment_id` | string | Source experiment identifier |
| `frozen_at` | string | Freeze timestamp |
| `commit_hash` | string | Code version used for the freeze |
| `experiment_config_path` | string/null | Config fixture path used for the freeze |
| `experiment_config_artifact` | string | Archived config artifact path |
| `frozen` | boolean | Always `true` after successful freeze |
| `immutability_policy` | string | Human-readable read-only policy |
| `freeze_prerequisites` | object | Matrix completeness, included-run artifact validity, exclusion documentation, and pilot readiness |
| `source_artifacts` | object | Hashes for source matrix, run index, pilot QA, and comparison artifacts |
| `freeze_artifacts` | object | Hashes for dataset index and dataset report |

The frozen manifest is stored at:

```text
artifacts/experiments/<experiment_id>/frozen_dataset_manifest.json
```

Phase 3C also writes:

```text
artifacts/experiments/<experiment_id>/dataset_report.md
```

## Phase 3D Readiness Review Artifacts

Phase 3D reviews the frozen dataset and records whether database or dashboard implementation is justified.

`StorageVolumeReview` is stored at:

```text
artifacts/experiments/<experiment_id>/storage_volume_review.json
```

It records:

- dataset ID and experiment ID,
- run count,
- included and excluded run counts,
- run artifact count,
- source artifact count,
- freeze artifact count,
- total and average run artifact bytes,
- dataset index and frozen manifest artifact hashes,
- storage backend and scan strategy.

`QueryRequirements` is stored at:

```text
artifacts/experiments/<experiment_id>/query_requirements.json
```

It records:

- the primary analysis entrypoint,
- required filters,
- required groupings,
- required artifact joins,
- current field cardinalities,
- candidate dashboard views.

`ResultsIndexDecision` is stored at:

```text
artifacts/experiments/<experiment_id>/results_index_decision.json
```

It records:

- whether filesystem artifacts remain sufficient,
- whether a database is recommended,
- observed volume and configured thresholds,
- the database decision,
- the read-model policy if a database is later needed,
- whether a dashboard is recommended now,
- dashboard decision and rationale,
- Phase 3D acceptance criteria.

If a database is later introduced, it must be a read-only index over frozen filesystem artifacts. It must not replace raw run artifacts, QA artifacts, `dataset_index.json`, or `frozen_dataset_manifest.json`.

Phase 3D also writes:

```text
artifacts/experiments/<experiment_id>/dashboard_requirements.md
artifacts/experiments/<experiment_id>/phase3d_review.md
```

## Phase 4A Analysis Artifacts

Phase 4A introduces derived analysis artifacts over the frozen dataset. These artifacts are not raw run artifacts and are not the source of truth. They are reproducible outputs from `dataset_index.json`, `frozen_dataset_manifest.json`, Phase 3 QA/readiness artifacts, and the per-run trace, verification, metrics, report, and manifest artifacts.

The analysis entrypoint is:

```text
python3 -m avf analyze-dataset --dataset-index artifacts/experiments/<experiment_id>/dataset_index.json
```

Phase 4A writes:

```text
artifacts/analysis/<dataset_id>/analysis_config.json
artifacts/analysis/<dataset_id>/analysis_input_manifest.json
artifacts/analysis/<dataset_id>/metrics_table.json
artifacts/analysis/<dataset_id>/metrics_table.csv
artifacts/analysis/<dataset_id>/metrics_table.md
```

`AnalysisConfig` records:

| Field | Purpose |
|---|---|
| `schema_version` | Contract schema version |
| `analysis_version` | Phase 4A analysis artifact version |
| `analysis_id` | Analysis run identifier |
| `dataset_id` | Frozen dataset analysed |
| `experiment_id` | Source experiment |
| `dataset_index_path` | Path to the source dataset index |
| `artifact_root` | Root used to resolve relative artifact paths |
| `analysis_root` | Root where derived artifacts are written |
| `generated_at` | Analysis timestamp |
| `code_version` | Code version used for analysis |
| `execution_policy` | Records that experiments are not rerun and no database/dashboard is required |

`AnalysisInputManifest` records:

| Field | Purpose |
|---|---|
| `dataset_index_artifact` | Hash and size of the source dataset index |
| `frozen_dataset_manifest_artifact` | Hash and size of the frozen manifest |
| `companion_artifacts` | Phase 3C/3D QA, freeze, and readiness artifacts consumed by analysis |
| `run_artifact_checks` | Per-run hash checks for trace, verification, metrics, report, and manifest artifacts |
| `artifact_hash_validation_passed` | Whether all referenced run artifacts match the frozen index |
| `integrity_issues` | Hash, size, or missing-artifact issues |
| `analysis_acceptance_criteria` | Phase 4A acceptance criteria evidence |

If any frozen run artifact hash or size no longer matches the dataset index, Phase 4A writes `analysis_input_manifest.json` and fails before writing metrics tables.

`MetricsTable` records one row per dataset index record.

Core fields include:

- run and dataset identifiers,
- inclusion status and dataset decision,
- task, seed, perturbation schedule, and component factor levels,
- artifact validation and hash-validation status,
- task success and verification outcome,
- verifier metadata,
- latency, step count, tool-call count, goal drift, repetition rate, and recovery steps,
- trace status, trace event count, and final-answer presence,
- explicit `token_usage=null` and `cost_usage=null` values until model adapters expose those metrics,
- `missing_metrics` and `analysis_issues`.

The CSV and Markdown outputs are projections of the same normalized metrics table.

## Phase 4B Component Effect Artifacts

Phase 4B introduces derived component-effect artifacts over the Phase 4A metrics table.

The analysis entrypoint is:

```text
python3 -m avf summarize-component-effects --metrics-table artifacts/analysis/<dataset_id>/metrics_table.json
```

Phase 4B writes:

```text
artifacts/analysis/<dataset_id>/component_effects.json
artifacts/analysis/<dataset_id>/component_effects.md
artifacts/analysis/<dataset_id>/interaction_summary.json
artifacts/analysis/<dataset_id>/interaction_summary.md
artifacts/analysis/<dataset_id>/dissertation_tables.md
```

`ComponentEffects` records:

| Field | Purpose |
|---|---|
| `schema_version` | Contract schema version |
| `analysis_version` | Phase 4B analysis artifact version |
| `dataset_id` | Frozen dataset analysed |
| `experiment_id` | Source experiment |
| `generated_at` | Analysis timestamp |
| `code_version` | Code version used for component-effect analysis |
| `metrics_table_artifact` | Source Phase 4A metrics table |
| `complete_block_count` | Matched blocks containing all eight component cells |
| `incomplete_block_count` | Blocks missing one or more component cells |
| `factor_definitions` | A/B/C factor definitions and level mappings |
| `metric_definitions` | Metrics included in descriptive contrasts |
| `factor_level_summaries` | Per-factor, per-level metric aggregates |
| `main_effects` | Level 2 minus Level 1 contrasts for A, B, and C |
| `matched_blocks` | Complete block metadata and traceable run IDs |
| `incomplete_blocks` | Missing/duplicate component cell evidence |
| `limitations` | Descriptive-only and no-confidence-interval rationale |
| `analysis_acceptance_criteria` | Phase 4B acceptance criteria evidence |

`InteractionSummary` records:

| Field | Purpose |
|---|---|
| `dataset_id` | Frozen dataset analysed |
| `experiment_id` | Source experiment |
| `complete_block_count` | Number of blocks used in interaction contrasts |
| `interactions` | `A:B`, `A:C`, `B:C`, and `A:B:C` descriptive contrasts |
| `limitations` | Descriptive-only and no-confidence-interval rationale |

Matched block keys use:

```text
task_id + run_config_id + seed + perturbation_schedule_id + tool_names
```

Only included runs with passing artifact hash validation are eligible. Incomplete matched blocks are listed in the artifacts but excluded from main-effect and interaction contrasts.

For the current dataset, Phase 4B reports descriptive component effects only. Confidence intervals and inferential uncertainty estimates are not reported until additional tasks, seeds, or perturbation schedules create enough matched blocks.

## Phase 4C Trajectory Diagnostic Artifacts

Phase 4C introduces trace-derived trajectory diagnostic artifacts over the Phase 4A metrics table.

The analysis entrypoint is:

```text
python3 -m avf diagnose-trajectories --metrics-table artifacts/analysis/<dataset_id>/metrics_table.json
```

Phase 4C writes:

```text
artifacts/analysis/<dataset_id>/trajectory_diagnostics.json
artifacts/analysis/<dataset_id>/trajectory_diagnostics.md
```

`TrajectoryDiagnostics` records:

| Field | Purpose |
|---|---|
| `schema_version` | Contract schema version |
| `analysis_version` | Phase 4C analysis artifact version |
| `dataset_id` | Frozen dataset analysed |
| `experiment_id` | Source experiment |
| `generated_at` | Analysis timestamp |
| `code_version` | Code version used for trajectory diagnostics |
| `metrics_table_artifact` | Source Phase 4A metrics table |
| `heuristic_definitions` | Definitions for action sequence, tool sequence, repeated observations, repetition rate, goal drift, recovery steps, and diagnostic scope |
| `scope_counts` | Counts of agent-behavior, excluded, unavailable, or artifact/analysis issue rows |
| `component_summaries` | Component-level trajectory aggregates over agent-behavior rows |
| `rows` | One diagnostic row per metrics table row |
| `analysis_acceptance_criteria` | Phase 4C acceptance criteria evidence |

Each trajectory row records:

- run, task, seed, perturbation schedule, component, and trace path,
- diagnostic scope,
- action count and action sequence,
- tool-call count and tool sequence,
- observation status counts,
- repeated action, repeated tool-call, and repeated observation counts,
- trace-derived repetition rate,
- trace-derived goal drift,
- recovery event count,
- final-answer presence,
- error summary,
- trace drill-down event IDs.

Repeated tool calls are counted as adjacent same-tool repetitions in the ordered `tool_call` event sequence. Repeated observations are counted as adjacent identical deterministic observation signatures built from observation source, status, and content. This keeps repeat diagnostics deterministic and independent of wall-clock time.

Rows labelled `agent_behavior` are included, hash-validated experiment outcomes. Rows labelled `dataset_excluded`, `trace_unavailable`, or `artifact_or_analysis_issue` are preserved for auditability but should not be interpreted as ordinary agent behavior.

## Phase 4D Failure Analysis Artifacts

Phase 4D introduces the derived failure-analysis and final-report artifacts over the Phase 4A metrics table and Phase 3 QA artifacts.

The analysis entrypoint is:

```text
python3 -m avf write-analysis-report --metrics-table artifacts/analysis/<dataset_id>/metrics_table.json
```

Phase 4D writes:

```text
artifacts/analysis/<dataset_id>/failure_analysis.json
artifacts/analysis/<dataset_id>/failure_analysis.md
artifacts/analysis/<dataset_id>/analysis_report.md
```

`FailureAnalysis` records:

| Field | Purpose |
|---|---|
| `schema_version` | Contract schema version |
| `analysis_version` | Phase 4D analysis artifact version |
| `dataset_id` | Frozen dataset analysed |
| `experiment_id` | Source experiment |
| `generated_at` | Analysis timestamp |
| `code_version` | Code version used for failure analysis |
| `metrics_table_artifact` | Source Phase 4A metrics table |
| `analysis_artifacts_consumed` | Presence and paths for Phase 4A-4C derived artifacts |
| `qa_artifacts_consumed` | Presence and paths for Phase 3 QA artifacts |
| `taxonomy_counts` | Counts for `passed`, `task_failure`, `verifier_failure`, `artifact_failure`, `infrastructure_failure`, and `dataset_excluded` |
| `failure_notes_by_class` | Failure-note records grouped by failure class |
| `qa_decision_links` | Exclusion and rerun decisions linked to QA artifacts and evidence paths |
| `run_outcomes` | One classified outcome row per metrics table row |
| `infrastructure_separation` | Policy and counts separating infrastructure/artifact issues from ordinary task outcomes |
| `analysis_summary` | Cross-reference summary from component effects, trajectory diagnostics, and pilot QA |
| `limitations` | Claim level, descriptive-only flag, and confidence-interval policy |
| `analysis_acceptance_criteria` | Phase 4D acceptance criteria evidence |

Each `run_outcome` records:

- run, task, seed, perturbation schedule, component, inclusion status, and dataset decision,
- failure class,
- whether the row is included as an ordinary task outcome,
- trace status,
- task success,
- verification pass/fail,
- verifier failure reasons,
- analysis issues,
- evidence paths for trace, verification, metrics, report, and manifest artifacts.

The Phase 4D failure taxonomy separates ordinary agent outcomes from infrastructure evidence:

| Class | Interpretation |
|---|---|
| `passed` | Included run with passing verification and successful task metrics |
| `task_failure` | Included run where metric evidence records task failure |
| `verifier_failure` | Included run where the verifier fails the run |
| `artifact_failure` | Missing, invalid, mismatched, or hash-invalid artifact evidence |
| `infrastructure_failure` | Trace exists but records non-completed execution status |
| `dataset_excluded` | Row preserved in the dataset but excluded by dataset policy |

`artifact_failure`, `infrastructure_failure`, and `dataset_excluded` rows are preserved for auditability but are not counted as ordinary task outcomes unless a future analysis explicitly justifies that policy change.

`failure_analysis.md` is the human-readable failure taxonomy report. `analysis_report.md` is the dissertation-facing summary that combines the Phase 4A metrics table, Phase 4B component summaries, Phase 4C trajectory diagnostics, QA evidence, and limitations. For the current eight-run dataset, Phase 4D states a descriptive claim level and does not report inferential confidence intervals.

## Phase 4E Dashboard Read-Model Artifacts

Phase 4E introduces derived dashboard/read-model artifacts over the completed Phase 4 analysis package. These artifacts are presentation and query-support artifacts; they are not raw results and are not the dissertation source of truth.

The analysis entrypoint is:

```text
python3 -m avf write-dashboard-read-model --metrics-table artifacts/analysis/<dataset_id>/metrics_table.json
```

Phase 4E writes:

```text
artifacts/analysis/<dataset_id>/read_model_decision.json
artifacts/analysis/<dataset_id>/results_read_model.json
artifacts/analysis/<dataset_id>/dashboard_data.json
artifacts/analysis/<dataset_id>/dashboard_snapshot.md
```

`ReadModelDecision` records:

| Field | Purpose |
|---|---|
| `schema_version` | Contract schema version |
| `analysis_version` | Phase 4E artifact version |
| `dataset_id` | Frozen dataset analysed |
| `experiment_id` | Source experiment |
| `generated_at` | Artifact generation timestamp |
| `code_version` | Code version used for generation |
| `metrics_table_artifact` | Source Phase 4A metrics table |
| `source_artifacts` | Paths and existence checks for Phase 3D and Phase 4A-4D inputs |
| `phase3d_decision_summary` | Filesystem/database/dashboard decision copied from `results_index_decision.json` |
| `phase4_query_needs` | Required dashboard views, filters, groupings, joins, and current dataset scale |
| `implementation_decision` | Whether a database was materialized and which read-model/dashboard artifact type is used |
| `source_of_truth_policy` | Explicit record that read-model/dashboard artifacts are not authoritative |
| `analysis_acceptance_criteria` | Phase 4E acceptance criteria evidence |

For the current dataset, `implementation_decision.database_materialized=false` and `read_model_backend=json_derived_artifact`. This follows the Phase 3D decision that filesystem artifacts remain sufficient.

`ResultsReadModel` records:

- one compact row per `metrics_table.json` row,
- task, seed, perturbation schedule, component ID, and factor levels,
- inclusion and dataset decision fields,
- task success and verification outcome,
- failure class joined from `failure_analysis.json`,
- diagnostic scope and drill-down data joined from `trajectory_diagnostics.json`,
- evidence paths for trace, verification, metrics, report, and manifest artifacts,
- component summaries,
- indexes by component ID, task ID, failure class, and diagnostic scope,
- source artifact references and source-of-truth policy.

`DashboardData` records static view data for:

- dataset overview,
- component comparison,
- task and seed filters,
- verification outcome breakdown,
- trajectory diagnostic drill-down,
- failure taxonomy review,
- artifact integrity status.

Dashboard views read from `results_read_model.json` and derived Phase 4 artifacts. They do not replace `dataset_index.json`, raw run artifacts, QA records, or Phase 4 analysis outputs.

`dashboard_snapshot.md` is a human-readable static dashboard snapshot for dissertation review. It is intentionally not a live web dashboard.

## Initial Storage Layout

The planned storage layout is:

```text
test_data/
  tasks/
  configs/
  components/
  prompts/
  perturbations/
  tool_specs/

artifacts/
  traces/
  results/
  reports/
  comparisons/
  experiments/
  audits/
```

## Phase 1B/1C Implementation

The initial contract implementation is dependency-light:

- schema models are implemented as standard-library dataclasses,
- persisted fixtures use JSON,
- validation is implemented in `src/avf/contracts/schemas.py`,
- fixture loading is implemented in `src/avf/contracts/fixture_loader.py`,
- fixture validation is available through `python -m avf validate-fixtures`.

## Phase 1D Implementation

The initial orchestrator implementation creates `RunContext` values:

- fixture-specific loaders are implemented in `src/avf/orchestration/loaders.py`,
- deterministic run ID generation is implemented in `src/avf/orchestration/run_context.py`,
- an execution-engine shell is implemented in `src/avf/orchestration/execution_engine.py`,
- CLI context creation is available through `python -m avf create-run-context`.

Phase 1D does not execute the SUT or mock services.

## Phase 1E Implementation

The baseline SUT agent consumes `AgentRunInput` and returns an agent-side result containing:

- `AgentOutput`,
- emitted `AgentAction` values,
- emitted `AgentObservation` values,
- deterministic `TraceEvent` values.

The baseline SUT agent is implemented in `src/avf/agents/core/`. It dispatches tool calls through the `ToolClient` protocol in `src/avf/agents/tools/client.py`. Concrete mock service behavior is intentionally deferred to Phase 1F.

## Phase 1F Implementation

The first concrete mock service implements the `ToolClient` protocol and consumes `ToolCall` values directly:

- `MockMemoryService` is implemented in `src/avf/mock_services/memory_service.py`,
- `memory.write` stores deterministic in-memory `MemoryRecord` values,
- `memory.query` returns deterministic records filtered by key and metadata,
- unsupported tools and invalid arguments return structured `ToolResult` errors,
- perturbation hooks are defined in `src/avf/mock_services/perturbations.py`.

The mock service returns documented `ToolResult` values and can be injected into the Phase 1E baseline SUT agent.

## Phase 1G Implementation

Trace logging now assembles agent-emitted `TraceEvent` values into a persisted `RunTrace` artifact:

- `build_run_trace` copies run metadata from `RunContext` and preserves emitted event ordering,
- `build_run_trace_from_agent_result` validates that `AgentOutput.trace_event_ids` matches the emitted trace events,
- `validate_run_trace` rejects empty traces, mismatched run IDs, duplicate event IDs, and completed traces without a `final_answer` event,
- `TraceWriter` writes validated traces as deterministic JSON files under the configured trace directory,
- `TraceReader` loads persisted JSON traces back into `RunTrace` contracts for later verification.

The Phase 1G trace artifact is intentionally file-based. It records the contract required by the verifier without introducing Kafka, Flink, or another streaming backend before the local baseline pipeline is complete.

## Phase 1H Implementation

The first verifier consumes the documented `TaskCase` and `RunTrace` contracts and returns a `VerificationResult`:

- `RuleBasedVerifier` is implemented in `src/avf/verification/rule_based.py`,
- trace evidence extraction is implemented in `src/avf/verification/evidence.py`,
- verification result artifact writing is implemented in `src/avf/verification/writer.py`,
- CLI verification is available through `python -m avf verify-trace`.

The deterministic Phase 1H checks are:

- `RunTrace` schema and cross-event consistency validation,
- `RunTrace.task_id` matches `TaskCase.task_id`,
- `RunTrace.status` is `completed`,
- final answer contains each `required_final_answer_contains` string from `TaskCase.success_criteria`,
- trace includes each `required_tool_calls` entry from `TaskCase.success_criteria`.

Each check produces structured evidence. Failed checks produce explicit `failure_reasons` in the returned `VerificationResult`.

## Phase 1I Implementation

The first reproducible baseline run produces all Phase 1 artifact contracts:

- `RunTrace` from the trace logging layer,
- `VerificationResult` from the rule-based verifier,
- `MetricResult` from the deterministic metrics calculator,
- Markdown report from the reporting layer.

The Phase 1I metric calculator is intentionally minimal and deterministic:

- `task_success` is copied from the verification result,
- `latency_ms` is set to `0` because Phase 1 uses synthetic deterministic timestamps rather than wall-clock timing,
- `step_count` is calculated from agent action trace events,
- `tool_call_count` is calculated from `tool_call` trace events,
- `goal_drift`, `repetition_rate`, and `recovery_steps` are derived from available trace events.

The baseline run can be executed through `python -m avf run-baseline` or `scripts/run-phase1-baseline.sh`.

## Phase 2A Implementation

Phase 2A adds implementation-level contracts around storage and component selection while preserving the existing persisted schema set.

New boundary abstractions:

- `FileSystemTestDataRepository` loads versioned fixtures from `test_data/`,
- `FileSystemResultsStore` writes traces, verification results, metric results, and Markdown reports under artifact directories,
- `ComponentRegistry` resolves `ComponentConfig` values into a `ComponentBundle`,
- `ComponentFactory` provides a stable construction facade for future SUT component wiring.

At Phase 2A completion, the current `A1_B1_C1` cell resolved as:

| Family | Variant | Phase 2A status | Concrete implementation phase |
|---|---|---|---|
| Memory | `sqlite` | deferred descriptor | Phase 2B |
| Retrieval | `bm25` | deferred descriptor | Phase 2C |
| Scheduling | `sequential` | available | Phase 1E |

This kept the Phase 2A baseline executable while making it explicit that SQLite memory and BM25 retrieval were not yet implemented as real component variants at that point.

## Phase 2B Implementation

Phase 2B implements SQLite memory as the first real SUT memory backend:

- `SQLiteMemory` implements the shared `MemoryModule` interface,
- records are stored in a deterministic SQLite table,
- `write` returns stable `mem_###` record identifiers,
- `read` returns records by structured key,
- `search` filters records by key, metadata, and limit,
- `MockMemoryService` can delegate memory tools to a `MemoryModule`,
- `ComponentRegistry` marks `memory_backend=sqlite` as available.

SQLite memory is not the results store. Trace, verification, metric, and report artifacts still use `FileSystemResultsStore`.

After Phase 2B, the current `A1_B1_C1` cell resolves as:

| Family | Variant | Status | Concrete implementation phase |
|---|---|---|---|
| Memory | `sqlite` | available | Phase 2B |
| Retrieval | `bm25` | deferred descriptor | Phase 2C |
| Scheduling | `sequential` | available | Phase 1E |

## Phase 2C Implementation

Phase 2C implements BM25 retrieval as the first real SUT retrieval strategy:

- `BM25Retriever` implements the shared `RetrievalModule` interface,
- documents are indexed with `document_id`, text, metadata, and source payloads,
- `query` returns ranked retrieval result dictionaries with `document_id`, `rank`, `score`, `text`, `metadata`, and `source`,
- ranking uses deterministic Okapi BM25 scoring,
- ties are resolved by index order and then document identifier,
- `MockMemoryService` indexes memory records into the selected retrieval module and uses it for `memory.query` ranking.

After Phase 2C, the current `A1_B1_C1` cell resolves as:

| Family | Variant | Status | Concrete implementation phase |
|---|---|---|---|
| Memory | `sqlite` | available | Phase 2B |
| Retrieval | `bm25` | available | Phase 2C |
| Scheduling | `sequential` | available | Phase 1E |

## Phase 2D Implementation

Phase 2D implements rule-based scheduling as the second SUT scheduling policy:

- `RuleBasedScheduler` implements the shared `Scheduler` interface,
- `SchedulingDecision` records explain the rule, priority, original step index, and scheduled step index for each action,
- `SequentialScheduler` remains available and records preserve-order decisions,
- `ComponentRegistry` marks `scheduling_policy=rule_based` as available,
- `BaselineSUTAgent` records a scheduling trace event with selected policy, scheduled action IDs, and decision records.

The rule-based scheduler uses deterministic priority classes:

| Priority | Rule | Action class |
|---|---|---|
| 10 | `internal_before_tools` | internal actions |
| 20 | `memory_write_before_memory_query` | `memory.write` tool calls |
| 30 | `memory_query_after_memory_write` | `memory.query` tool calls |
| 40 | `generic_tool_call_after_memory_dependencies` | other tool calls |
| 100 | `final_answer_last` | final answers |

Ties within the same priority class preserve planner order.

After Phase 2D, the currently implemented component levels are:

| Family | Variant | Status | Concrete implementation phase |
|---|---|---|---|
| Memory | `sqlite` | available | Phase 2B |
| Retrieval | `bm25` | available | Phase 2C |
| Scheduling | `sequential` | available | Phase 1E |
| Scheduling | `rule_based` | available | Phase 2D |

## Phase 2E Implementation

Phase 2E implements vector memory as the second SUT memory backend:

- `VectorMemory` implements the shared `MemoryModule` interface,
- `write` stores the same external record shape as SQLite memory and returns stable `mem_###` identifiers,
- `read` returns records by structured key,
- `search` ranks metadata-filtered records by deterministic cosine similarity,
- `DeterministicTextEmbedder` converts record text into sparse lexical vectors without a hosted embedding service,
- ties are resolved by insertion order and record identifier.

The Phase 2E embedding substitute is intentionally lexical rather than semantic. It exists to validate the vector memory component boundary reproducibly before hosted or model-based embeddings are considered.

After Phase 2E, the currently implemented component levels are:

| Family | Variant | Status | Concrete implementation phase |
|---|---|---|---|
| Memory | `sqlite` | available | Phase 2B |
| Memory | `vector` | available | Phase 2E |
| Retrieval | `bm25` | available | Phase 2C |
| Scheduling | `sequential` | available | Phase 1E |
| Scheduling | `rule_based` | available | Phase 2D |

## Phase 2F Implementation

Phase 2F implements embedding retrieval as the second SUT retrieval strategy:

- `EmbeddingRetriever` implements the shared `RetrievalModule` interface,
- documents are indexed with `document_id`, text, metadata, source payloads, and deterministic sparse vectors,
- `query` returns ranked retrieval result dictionaries with `document_id`, `rank`, `score`, `text`, `metadata`, and `source`,
- ranking uses deterministic cosine similarity over local sparse embeddings,
- metadata filtering and non-matching queries follow the same contract as BM25 retrieval,
- ties are resolved by index order and document identifier.

The Phase 2F retriever uses the shared `DeterministicTextEmbedder` utility. It does not require a hosted embedding service or network access.

After Phase 2F, the currently implemented component levels are:

| Family | Variant | Status | Concrete implementation phase |
|---|---|---|---|
| Memory | `sqlite` | available | Phase 2B |
| Memory | `vector` | available | Phase 2E |
| Retrieval | `bm25` | available | Phase 2C |
| Retrieval | `embedding` | available | Phase 2F |
| Scheduling | `sequential` | available | Phase 1E |
| Scheduling | `rule_based` | available | Phase 2D |

After Phase 2G, every `2^3` `ComponentConfig` fixture resolves to an implemented component bundle. The schema is unchanged; Phase 2G adds fixture coverage and registry validation across all factor cells.

After Phase 2H, baseline-run artifacts include the resolved component bundle without changing the persisted contract schemas:

- `RunTrace.component_config_id` identifies the selected fixture,
- an `agent_step` trace event with `stage=component_bundle` records resolved memory, retrieval, and scheduling descriptors,
- the CLI summary includes `component_config_id` and `component_bundle`,
- the Markdown report includes a component selection table.

After Phase 2I, baseline runs also produce a deterministic artifact manifest. The manifest is results-store metadata rather than a new agent contract.

Manifest fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Manifest schema version, currently `1.0` |
| `manifest_version` | string | Manifest format version, currently `1.0` |
| `run_id` | string | Run ID for the artifact set |
| `rerun_policy` | string | Current policy, `deterministic_overwrite` |
| `validation` | object | Artifact validation summary |

The validation summary records:

- `passed`,
- `issues`,
- artifact records for `trace`, `verification`, `metrics`, and `report`,
- relative artifact paths,
- SHA-256 content hashes,
- byte sizes.

The manifest intentionally does not hash itself. It validates the core run artifacts without creating recursive manifest content.

After Phase 2J, `ExperimentResult` is used for the Phase 2 integration comparison summary:

- `experiment_id` is `phase2_integration_baseline`,
- `factorial_design` records the selected component cells and A/B/C factor coding,
- `run_ids` lists the included component-aware baseline runs,
- `aggregation` stores success rates, artifact validation rates, comparison rows, and Phase 2 exit criteria,
- `analysis_artifacts` links to the comparison summary JSON and Markdown exit report.

This remains a small integration baseline, not the full Phase 3 factorial dataset.

After Phase 3A, `ExperimentResult` is also used for the full factorial execution summary:

- `experiment_id` is `phase3_full_factorial_v1` by default,
- `factorial_design` records the one-task, one-seed, one-schedule, eight-component design,
- `run_ids` lists all eight component-cell runs,
- `aggregation` stores expected run count, completed run count, success rates, artifact validation rates, run index records, and Phase 3A acceptance criteria,
- `analysis_artifacts` links to `experiment_config.json`, `matrix.json`, `run_index.json`, the comparison summary JSON, and the Markdown full factorial report.

The raw per-run artifacts remain authoritative. Phase 3A experiment-level artifacts index the run set and support QA, rerun-record, and dataset-freeze work in later Phase 3 subphases.

After Phase 3B, pilot QA artifacts are written beside the matrix and run index:

- `pilot_log.md` records timestamp, commit hash, config path, run counts, validation summary, limitations, operator notes, and the pilot decision,
- `pilot_qa_summary.json` stores the same QA decision in machine-readable form,
- `rerun_records.json` stores rerun decisions and remains valid even when empty,
- `failure_notes.json` and `failure_notes.md` store classified failure notes and templates.

These QA artifacts do not replace raw run artifacts or the `ExperimentResult` comparison summary. They document whether the experiment can proceed to dataset freeze.

After Phase 3C, dataset freeze artifacts are written beside the QA artifacts:

- `dataset_index.json` becomes the analysis entrypoint,
- `frozen_dataset_manifest.json` records source and freeze artifact hashes,
- `dataset_report.md` summarises included and excluded runs.

Raw per-run artifacts remain the source of truth, but after freeze they should be treated as read-only dissertation evidence.

After Phase 3D, readiness review artifacts are written beside the frozen dataset artifacts:

- `storage_volume_review.json` records current artifact volume,
- `query_requirements.json` records analysis and dashboard query needs,
- `results_index_decision.json` records whether filesystem artifacts remain sufficient,
- `dashboard_requirements.md` records dashboard scope based on the frozen dataset,
- `phase3d_review.md` summarises the readiness decision.

For the current eight-run dataset, filesystem artifacts remain sufficient and dashboard implementation is deferred.

## Boundary Contracts

### Inputs to Orchestrator

The orchestrator consumes:

- `TaskCase`,
- `RunConfig`,
- `ComponentConfig`,
- perturbation schedule,
- tool specifications.

The orchestrator produces:

- `RunContext`.

### Orchestrator to Base Agent / SUT

The orchestrator sends:

- `AgentRunInput`.

The base agent returns:

- `AgentOutput`.

During execution, the base agent emits:

- `AgentAction`,
- `AgentObservation`,
- `TraceEvent`.

### Orchestrator to Mock Services

The orchestrator sends:

- `ToolCall`,
- active run context,
- perturbation context.

Mock services return:

- `ToolResult`.

### Trace Logger to Verification

The trace logger emits:

- `RunTrace`.

The verification layer consumes:

- `RunTrace`,
- `TaskCase`,
- `ToolSpec`,
- success criteria.

### Verification and Metrics to Reporting

The reporting layer consumes:

- `VerificationResult`,
- `MetricResult`,
- `RunTrace`,
- aggregated experiment artifacts.

## Open Questions

The following questions remain open for later phases:

1. Whether richer report formats should be added after the Markdown baseline.

## Dissertation Use

This document supports the dissertation by explaining:

- how reproducibility requirements are represented in software contracts,
- how component isolation is enforced through stable interfaces,
- how trace logging enables trajectory-level diagnostics,
- how schema versioning prevents uncontrolled experimental drift.
