# Architecture Overview

## Purpose

This document describes the automated testing infrastructure at the architectural level. It maps the implementation to the four-layer design shown in `automated-testing-infra.png` and the System Under Test design shown in `SUT-base-agent-design.png`:

1. orchestration layer,
2. mock service layer,
3. verification layer,
4. reporting layer.

The system is designed to evaluate AI agents under controlled, repeatable conditions. Its primary research purpose is component-level attribution, not maximising raw agent performance.

## Architectural Principle

The framework separates execution, environment simulation, verification, and reporting.

Each layer communicates through stable contracts. This allows memory, retrieval, and scheduling variants to be substituted while holding task definitions, tool schemas, prompts, seeds, and runtime settings constant.

## System Under Test: Base Agent

The System Under Test (SUT) is the base agent evaluated by the framework.

The SUT is not treated as an opaque black box during implementation. It is a controlled modular agent with:

- an agent core,
- a memory module,
- a retrieval/search module,
- a skill/tool scheduling module,
- an MCP-style tool/action layer,
- telemetry and audit outputs.

The agent core follows a think-plan-act-observe loop:

```text
perception / input processing
  -> reasoning
  -> planning
  -> action execution
  -> observation processing
  -> updated state or final answer
```

The SUT receives test cases, scenario configuration, environment configuration, mock service configuration, and execution controls from the orchestration layer.

The SUT returns a final answer, execution trace, artifacts, and metrics. These outputs are consumed by trace logging, verification, metrics, and reporting.

Only three SUT module families are part of the core dissertation factorial design:

| Module family | Factor levels |
|---|---|
| Memory | SQLite-backed episodic memory; vector-index-backed episodic memory |
| Retrieval/search | BM25 retrieval; embedding-based retrieval |
| Scheduling | sequential execution; rule-based prioritisation |

Other variants shown in the SUT design, such as Redis memory, hybrid retrieval, RAG, DAG scheduling, and parallel scheduling, are documented as possible extensions but are outside the initial `2^3` experiment.

## Layer 1: Orchestration Layer

The orchestration layer controls test execution.

Responsibilities:

- load test cases and run configurations,
- validate schemas before execution,
- select component configuration,
- apply fixed seeds and perturbation schedules,
- initialise mock services,
- execute the agent or agent adapter,
- collect trace events,
- pass completed traces to verification and metrics.

Primary modules planned:

```text
src/avf/orchestration/
  test_case_loader.py
  scheduler.py
  execution_engine.py
  resource_manager.py
  run_context.py
```

The orchestration layer configures the SUT but does not implement the SUT's internal reasoning, memory, retrieval, or scheduling logic.

Initial Phase 1 scope:

- load one task case,
- load one run configuration,
- execute one deterministic baseline run,
- emit one complete trace.

## Layer 2: Mock Service Layer

The mock service layer simulates external services that the agent can use through MCP-style tools.

Responsibilities:

- provide deterministic tool responses,
- emulate database, file, and API interactions,
- apply perturbations from fixed schedules,
- record tool-level timing and errors,
- avoid live API drift and network dependency.

Planned mock services:

| Service | Purpose |
|---|---|
| Mock database service | State persistence, structured lookup, memory-dependent tasks |
| Mock file service | Document access, file reads/writes, task artifacts |
| Mock API service | API-style calls, failures, partial observations |
| Mock collaboration services | Later extension for GitHub, Slack, Google API style scenarios |

Initial Phase 1 scope:

- one deterministic mock service,
- one or two tools,
- fixed input and output schemas,
- perturbation hook present but minimal.

The SUT accesses mock services through its MCP-style tool/action layer. The mock services therefore validate both the external tool interface and the SUT's action-execution path.

Phase 1F implementation:

- the first mock service is `MockMemoryService`,
- implemented tools are `memory.write` and `memory.query`,
- the service implements the SUT `ToolClient` protocol,
- perturbation support is represented by no-op and static perturbation controllers.

## Trace Logging Boundary

Trace logging is the artifact boundary between execution and verification.

Responsibilities:

- assemble ordered agent-emitted `TraceEvent` values,
- preserve run metadata from the orchestration `RunContext`,
- validate trace completeness before verification,
- persist deterministic JSON `RunTrace` artifacts,
- reload trace artifacts for verifier, metrics, and reporting stages.

Phase 1G implementation:

- trace construction is implemented in `src/avf/tracing/builder.py`,
- trace validation is implemented in `src/avf/tracing/validation.py`,
- trace persistence is implemented in `src/avf/tracing/writer.py`,
- trace loading is implemented in `src/avf/tracing/reader.py`.

The initial trace pipeline does not use Kafka, Flink, or streaming infrastructure. Local JSON artifacts are more appropriate for the dissertation baseline because they are deterministic, inspectable, easy to archive, and sufficient for the first verifier and report. Streaming infrastructure remains a future scalability option, not a Phase 1 requirement.

## Layer 3: Verification Layer

The verification layer judges whether a run satisfied task requirements and computes evidence-backed diagnostic results.

Responsibilities:

- check deterministic success criteria,
- validate trace and tool schemas,
- detect failed assertions,
- compute trajectory-level metrics,
- optionally invoke LLM-as-judge verification for semantic checks,
- combine verifier results through a consensus layer.

Verifier types:

| Verifier | Role |
|---|---|
| Rule-based verifier | Deterministic checks, assertions, schemas, state transitions |
| LLM-as-judge verifier | Optional semantic quality and reasoning assessment |
| Consistency/consensus verifier | Aggregate results and resolve conflicts |

Initial Phase 1 scope:

- rule-based verifier only,
- deterministic success/failure,
- evidence captured from trace events.

Phase 1H implementation:

- the first verifier is `RuleBasedVerifier`,
- it consumes `TaskCase` and `RunTrace`,
- it returns a `VerificationResult`,
- it checks trace validity, task identity, completed status, required final-answer text, and required tool-call presence,
- it writes optional JSON verification result artifacts for later metrics and reporting.

LLM-as-judge and consensus verification remain later extensions. The baseline verifier is deterministic so that early experimental results are reproducible and evidence-backed.

## Layer 4: Reporting Layer

The reporting layer turns traces, metrics, and verifier outputs into human-readable artifacts.

Responsibilities:

- store raw results and logs,
- summarise task outcomes,
- show trends across configurations,
- expose coverage and failure diagnostics,
- support dissertation analysis and auditability.

Initial reporting formats:

- JSON result artifacts,
- Markdown run reports,
- CLI summary.

Phase 1I implementation:

- baseline orchestration writes one `RunTrace` artifact,
- rule-based verification writes one `VerificationResult` artifact,
- deterministic metric calculation writes one `MetricResult` artifact,
- Markdown reporting writes one run report,
- the CLI and shell script provide the first reproducible baseline run entrypoints.

Later reporting formats:

- dashboard views,
- trend tracking,
- coverage analytics,
- failure drill-down,
- alerts or notifications.

## Data Flow

```text
test designers / engineers
  -> test data repository
  -> orchestrator
  -> system under test / base agent
  -> mock services
  -> system under test observations
  -> trace logger
  -> verification layer
  -> results store
  -> reports and dashboard
  -> stakeholders
```

## Controlled Evaluation Guarantees

The architecture is intended to guarantee:

- repeatable runs under fixed seeds,
- deterministic mock environment behaviour conditional on schedule,
- stable tool interfaces,
- complete trace logging,
- component-level substitution without unrelated changes,
- analysis based on matched experimental cells.

## Phase 2A Storage and Component Registry

Phase 2A formalises two architecture boundaries that were implicit in Phase 1:

- the test data repository is represented by `FileSystemTestDataRepository`,
- the results store is represented by `FileSystemResultsStore`.

Both remain filesystem-backed. This preserves the Phase 1 artifact-first design while creating a cleaner boundary for later storage changes.

Phase 2A also introduces the SUT component registry and factory:

- `ComponentConfig` is resolved through `ComponentRegistry`,
- the existing `A1_B1_C1` cell resolves deterministically,
- sequential scheduling is available as the current concrete scheduler,
- SQLite memory is available as a concrete memory backend from Phase 2B,
- vector memory is available as a concrete memory backend from Phase 2E,
- BM25 retrieval is available as a concrete retrieval strategy from Phase 2C,
- embedding retrieval is available as a concrete retrieval strategy from Phase 2F,
- rule-based scheduling is available as a concrete scheduler from Phase 2D,
- unsupported variants fail explicitly rather than silently falling back to baseline behavior.

Phase 2B introduces the first real SUT memory database:

- `SQLiteMemory` uses Python standard-library `sqlite3`,
- memory records are persisted through the memory interface,
- the mock memory tool service can delegate `memory.write` and `memory.query` to the SQLite backend,
- the filesystem results store is unchanged and remains separate from SUT memory storage.

Phase 2C introduces the first real SUT retrieval strategy:

- `BM25Retriever` implements the shared retrieval interface,
- the implementation uses dependency-light Okapi BM25 scoring,
- memory records are indexed as retrieval documents by the mock memory tool service,
- `memory.query` uses the selected retrieval module for deterministic ranking when `retrieval_strategy=bm25`.

Phase 2D introduces the second concrete SUT scheduling policy:

- `RuleBasedScheduler` implements the shared scheduler interface,
- scheduling rules prioritise internal actions, memory writes, memory queries, generic tool calls, and final answers,
- scheduler decisions are emitted into the run trace,
- sequential scheduling remains unchanged for the baseline `A1_B1_C1` cell.

Phase 2E introduces the second SUT memory backend:

- `VectorMemory` implements the same memory interface as SQLite memory,
- memory records are represented with deterministic sparse lexical vectors,
- `search` ranks records by local cosine similarity with stable insertion-order tie-breaking,
- no hosted embedding API or network access is required.

Phase 2F introduces the second SUT retrieval strategy:

- `EmbeddingRetriever` implements the same retrieval interface as BM25 retrieval,
- documents are indexed with deterministic local sparse embeddings,
- query results use the same ranked payload shape as BM25,
- retrieval strategy remains independent from the selected memory backend.

Phase 2G completes the component fixture matrix:

- all eight `A#_B#_C#` `ComponentConfig` fixtures exist under `test_data/components/`,
- each fixture resolves through the component registry,
- factor IDs map directly to memory, retrieval, and scheduling selections,
- switching cells does not require task fixture or tool schema changes.

Phase 2H makes the baseline runner component-aware:

- `python -m avf run-baseline` resolves `ComponentConfig` through the component factory,
- the selected scheduler is passed into the baseline SUT agent,
- the selected memory and retrieval modules are passed into the mock memory service,
- trace, CLI, and Markdown report outputs identify the selected component bundle.

Phase 2I strengthens the filesystem results store:

- baseline runs write deterministic artifact manifests under `manifests/`,
- `FileSystemResultsStore` validates trace, verification, metric, and report artifacts as one set,
- validation checks `run_id` consistency and missing artifacts before full experiment execution,
- repeated runs use deterministic overwrite rather than versioned rerun directories.

Phase 2J adds the integration baseline boundary:

- `run-phase2-integration` executes a Level 1 baseline cell and a Level 2 variant cell,
- each run produces trace, verification, metrics, report, and manifest artifacts,
- an `ExperimentResult` JSON comparison summary is written under `comparisons/`,
- a Markdown Phase 2 exit report records component differences and Phase 3 readiness.

Phase 3A adds the experiment matrix boundary:

- `ExperimentConfig` records the ordered task, run config, component, tool schema, schedule, execution-policy, and dataset-policy references for one experiment,
- `build_experiment_matrix` resolves the full matched matrix and computes deterministic expected run IDs,
- `run-phase3a-experiment` executes the current one-task, one-seed, one-schedule, eight-component matrix,
- every matrix row delegates to the existing component-aware baseline runner,
- per-run trace, verification, metrics, report, and manifest artifacts remain the source of truth,
- experiment-level `experiment_config.json`, `matrix.json`, `run_index.json`, comparison summary, and Markdown report artifacts index the run set.

This layer does not introduce a database, dashboard, new verifier, or new SUT component. It coordinates already validated Phase 2 components into the first full factorial execution.

Phase 3B adds the pilot QA boundary:

- `run-phase3b-pilot` executes the current matrix in pilot mode,
- `pilot_log.md` records timestamp, commit hash, experiment config path, expected/completed run counts, validation summary, limitations, operator notes, and the pilot decision,
- `rerun_records.json` records rerun intent and remains valid when no reruns are required,
- `failure_notes.json` and `failure_notes.md` classify task, verifier, artifact, and infrastructure failures,
- the dataset-execution gate blocks progression when unresolved infrastructure failures remain.

Phase 3B is an audit and QA layer over existing artifacts. It does not change agent behavior, task schemas, verifier logic, metric definitions, the results store backend, or dashboard timing.

## Thin-Slice Implementation

The first executable version will include all layers in minimal form:

```text
one task
one run config
one baseline SUT agent core
one mock service
one trace
one rule-based verifier
one metrics output
one report
```

This thin slice validates the layer boundaries before scaling to the full system.

## Dissertation Use

This architecture overview can support the dissertation by explaining:

- how the implementation reflects the proposed automated testing infrastructure,
- how the SUT base-agent design supports controlled component substitution,
- why mock services were chosen over live services,
- how modularity enables component-level ablations,
- how trace logging supports trajectory-level diagnostics,
- how reporting links software artifacts to research claims.
