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
