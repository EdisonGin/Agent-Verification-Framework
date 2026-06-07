# SUT Base Agent Design

## Purpose

This document records the planned architecture for the base agent used as the System Under Test (SUT). It is based on `SUT-base-agent-design.png`.

The base agent is the controlled agent implementation evaluated by the automated testing infrastructure. It must be modular enough to support memory, retrieval, and scheduling substitutions, while keeping the model, prompts, task suite, tool schemas, and runtime settings fixed.

## Architectural Role

The base agent sits between the test orchestrator and the mock MCP/tool servers.

```text
test orchestrator
  -> base agent / SUT
  -> MCP client tool layer
  -> mock MCP/tool servers
  -> base agent observations
  -> final answer, trace, artifacts, metrics
```

The testing framework evaluates this agent by controlling its inputs, environment, component configuration, and execution limits.

## Inputs from Test Orchestrator

The base agent receives:

| Input | Purpose |
|---|---|
| Test case | Instructions, goals, expected outcomes, allowed tools |
| Scenario config | Agent configuration, model, tools, limits |
| Environment config | Memory, search, and scheduler settings |
| Mock service config | Tool endpoints, deterministic data, service behaviours |
| Execution controls | Timeout, max steps, retry policy, logging settings |

These inputs must be versioned and recorded in the run trace.

## Agent Core

The agent core follows a controlled think-plan-act-observe loop.

Core stages:

| Stage | Responsibility |
|---|---|
| Perception / input processor | Parse task instructions and initialise context/state |
| Reasoning module | Decide the next action under the fixed model/prompt configuration |
| Planner | Create or update a plan/subgoal sequence |
| Action executor | Execute internal actions or tool calls |
| Observation processor | Process tool results, update state, and determine next step |

Initial Phase 1 scope:

- deterministic local baseline reasoning,
- simple plan generation,
- sequential action execution,
- observation-to-state update,
- final answer generation.

The first implementation may use a stubbed or deterministic baseline model so the infrastructure can be validated without external model dependency.

## Pluggable Modules

The base agent has three module families that align with the dissertation's component-level experimental factors.

### Memory Module

Interface:

```text
read / write / search
```

Planned implementations:

| Variant | Role |
|---|---|
| SQLite structured memory | Dissertation Factor A1 |
| Vector-backed memory | Dissertation Factor A2 |
| File-based JSON/YAML memory | Development fallback or later extension |
| Redis key-value/cache memory | Later extension, not part of initial factorial design |

### Retrieval / Search Module

Interface:

```text
query / retrieve
```

Planned implementations:

| Variant | Role |
|---|---|
| BM25 keyword search | Dissertation Factor B1 |
| Semantic embedding search | Dissertation Factor B2 |
| Hybrid BM25 + semantic search | Later extension |
| RAG pipeline | Later extension |

### Skill / Tool Scheduling Module

Interface:

```text
schedule / dispatch
```

Planned implementations:

| Variant | Role |
|---|---|
| Sequential scheduler | Dissertation Factor C1 |
| Rule-based priority scheduler | Dissertation Factor C2 |
| DAG-based scheduler | Later extension |
| Parallel/concurrent scheduler | Later extension |

Phase 2G records these dissertation factors as explicit `ComponentConfig` fixtures. The fixture ID format is `A#_B#_C#`, where A selects memory, B selects retrieval, and C selects scheduling. This keeps component substitution separate from task fixtures, tool schemas, and verification rules.

## Tool / Action Layer

The tool/action layer acts as an MCP-style client.

Responsibilities:

- convert selected actions into tool calls,
- validate tool arguments,
- dispatch calls to mock MCP/tool servers,
- receive structured tool results,
- pass observations back to the agent core,
- emit trace events for every action and result.

Planned tools:

| Tool | Phase |
|---|---|
| Memory/database tool | Phase 1 |
| File system tool | Phase 1 or Phase 2 |
| API-style tool | Phase 2 |
| GitHub/Slack/Google-style tools | Later coverage expansion |

## Outputs

The base agent produces:

| Output | Purpose |
|---|---|
| Final answer | User/test-facing result |
| Execution trace | Ordered steps, actions, observations, state updates |
| Artifacts | Files, data, logs, generated outputs |
| Metrics | Token usage, time, steps, errors where available |

The execution trace is the most important research artifact because it supports verification, trajectory metrics, and failure analysis.

## Telemetry and Audit

The base agent must emit internal telemetry suitable for audit:

- execution log,
- audit trail,
- metrics and tracing,
- error tracking.

These telemetry events should be represented as trace events so that the verification and reporting layers can consume them uniformly.

## Phase 1 Baseline Agent

The Phase 1 baseline agent will implement the smallest useful subset:

```text
perception
  -> deterministic reasoning/planning
  -> sequential action execution
  -> mock memory tool call
  -> observation processing
  -> final answer
```

Required properties:

- no live external API dependency,
- deterministic under fixed seed and configuration,
- complete trace event emission,
- stable tool-call interface,
- clear separation between agent core and pluggable modules.

Phase 1E implementation:

- the baseline SUT agent accepts `AgentRunInput` from the Phase 1D `RunContext`,
- perception, planning, action execution, observation processing, and final answer generation are implemented as separate modules,
- tool calls are dispatched through an injected `ToolClient` protocol,
- trace events are generated deterministically without wall-clock timestamps,
- memory, retrieval, and scheduling interfaces are declared for later component variants,
- the concrete mock service implementation is deferred to Phase 1F.

Phase 1F implementation:

- `MockMemoryService` implements the `ToolClient` protocol used by the baseline SUT agent,
- `memory.write` and `memory.query` provide deterministic mock memory behavior,
- structured errors are returned through `ToolResult`,
- a perturbation hook exists for later fixed perturbation schedules.

Phase 1G implementation:

- agent-emitted `TraceEvent` values are assembled into a complete `RunTrace`,
- the trace logger validates event order, run ID consistency, unique event IDs, and final-answer presence for completed runs,
- trace artifacts are written as deterministic local JSON files for verification and reporting,
- streaming telemetry infrastructure is deferred until the local reproducible baseline is complete.

## Phase 2 Expansion

Phase 2 expands the baseline agent into the controlled modular SUT:

- introduce SQLite and vector memory variants through the same memory interface,
- introduce BM25 and embedding retrieval variants through the same retrieval interface,
- introduce sequential and rule-based scheduling variants through the same scheduler interface,
- validate that component swaps do not change task definitions, prompt templates, or tool schemas.

Phase 2B implementation:

- `SQLiteMemory` implements the first concrete memory backend,
- the backend uses Python standard-library `sqlite3`,
- memory tool calls can be delegated to the SQLite backend through the mock memory service,
- SQLite memory remains separate from the filesystem results store.

Phase 2C implementation:

- `BM25Retriever` implements the first concrete retrieval strategy,
- memory records are indexed as retrieval documents with metadata and source payloads,
- `memory.query` uses BM25 ranking when `retrieval_strategy=bm25`,
- retrieval remains separate from memory storage and scheduling.

Phase 2F implementation:

- `EmbeddingRetriever` implements the second concrete retrieval strategy,
- retrieval documents are indexed with deterministic sparse lexical embeddings,
- embedding retrieval exposes the same ranked result payload as BM25 retrieval,
- embedding retrieval remains independent from the selected memory backend.

Phase 2D implementation:

- `RuleBasedScheduler` implements the second concrete scheduling policy,
- the scheduler prioritises internal actions, memory writes, memory queries, generic tool calls, and final answers,
- scheduler decisions are recorded in trace payloads,
- the scheduler controls action ordering only; tool execution remains in the action executor.

Phase 2E implementation:

- `VectorMemory` implements the second concrete memory backend,
- memory records are stored with deterministic sparse lexical vectors,
- vector search ranks records by cosine similarity without a hosted embedding API,
- vector memory exposes the same write, read, and search methods as SQLite memory.

Phase 2H implementation:

- the baseline runner constructs the SUT from the resolved `ComponentBundle`,
- scheduler, memory, and retrieval modules are selected by `ComponentConfig`,
- the same task, run config, and tool fixtures are reused across component cells,
- selected component variants are recorded in trace, CLI, and report outputs.

## Out-of-Scope for Initial Dissertation Factorial Design

The SUT diagram includes additional useful variants. These are documented but deferred unless time allows:

- Redis memory,
- hybrid retrieval,
- full RAG pipeline,
- DAG scheduling,
- parallel/concurrent scheduling,
- broad GitHub/Slack/Google API coverage.

They may be useful for future work or tool-calling coverage extensions, but they are not required for the core `2^3` experiment.

## Dissertation Use

This document supports the dissertation by explaining:

- what the SUT agent is,
- how the agent core executes tasks,
- which modules are controlled experimental factors,
- why only selected variants are included in the factorial design,
- how telemetry and traces are generated for verification.
