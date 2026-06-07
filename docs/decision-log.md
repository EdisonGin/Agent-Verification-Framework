# Decision Log

## Purpose

This document records important implementation decisions for the automated testing infrastructure.

The decision log supports dissertation transparency by showing why architectural and methodological choices were made. It should be updated whenever a decision affects reproducibility, component isolation, data collection, analysis, or reporting.

## Decision Format

Each decision uses the following format:

```text
Decision ID:
Date:
Status:
Context:
Decision:
Rationale:
Consequences:
```

Status values:

- `proposed`
- `accepted`
- `revised`
- `rejected`

## Decisions

### DEC-001: Use Thin-Slice-First Implementation

Decision ID: DEC-001

Date: 2026-06-05

Status: accepted

Context:

The architecture contains multiple layers: orchestration, mock services, verification, and reporting. Building each layer to completion before integration would delay validation of the interfaces between layers.

Decision:

Build a minimal end-to-end slice first, then expand each layer incrementally.

Rationale:

The research depends on reliable contracts and reproducible traces. A thin slice validates the complete pipeline early:

```text
task -> orchestrator -> mock service -> agent -> trace -> verifier -> metrics -> report
```

Consequences:

- Early implementation focuses on one task and one mock service.
- Dashboard development is deferred until trace and result artifacts exist.
- Interfaces are tested before the framework scales to the full factorial experiment.

### DEC-002: Define Contracts Before Code-Level Components

Decision ID: DEC-002

Date: 2026-06-05

Status: accepted

Context:

The dissertation requires controlled comparisons across memory, retrieval, and scheduling components. If component interfaces are allowed to drift, observed differences may be confounded by implementation changes.

Decision:

Define contracts and schemas before implementing component variants.

Rationale:

Stable contracts ensure that SQLite memory and vector memory expose the same memory interface, BM25 and embedding retrieval expose the same retrieval interface, and sequential and rule-based scheduling expose the same scheduling interface.

Consequences:

- Phase 1A documents the schema set.
- Phase 1C will implement and test the schemas.
- Component variants are deferred until the common interfaces are stable.

### DEC-003: Prefer Mock Services Over Live APIs for Core Experiments

Decision ID: DEC-003

Date: 2026-06-05

Status: accepted

Context:

The project aims to estimate component-level effects under controlled conditions. Live APIs introduce interface drift, latency variation, outages, and non-deterministic failures.

Decision:

Use deterministic mock MCP-style services for core experiments.

Rationale:

Mock services support repeatable task execution, fixed perturbation schedules, and matched comparisons across configurations.

Consequences:

- External validity is limited compared with live environments.
- Reproducibility and causal attribution are stronger.
- Controlled perturbations will be added to simulate delays, temporary unavailability, and noisy observations.

### DEC-004: Start Reporting with JSON and Markdown Artifacts

Decision ID: DEC-004

Date: 2026-06-05

Status: accepted

Context:

The architecture includes a dashboard, but a dashboard depends on stable trace, verification, and metric artifacts.

Decision:

Start with JSON artifacts and Markdown reports before implementing a richer dashboard.

Rationale:

JSON and Markdown are easier to validate, version, cite, and archive. They provide enough evidence for early dissertation development and avoid premature frontend work.

Consequences:

- Dashboard implementation is deferred.
- Reporting still exists in Phase 1 through reproducible artifacts.
- Later dashboard views can read from the same result store.

### DEC-005: Treat Schema Versioning as Mandatory

Decision ID: DEC-005

Date: 2026-06-05

Status: accepted

Context:

Experimental validity depends on knowing exactly which task, prompt, tool schema, and run configuration produced each result.

Decision:

Every persisted artifact must include a `schema_version`, and task/prompt/tool definitions must include their own version fields where applicable.

Rationale:

Versioning prevents silent drift and supports auditability.

Consequences:

- Fixtures require explicit version metadata.
- Trace and result artifacts can be linked to specific schema versions.
- Analysis can exclude incompatible artifacts if schemas change.

### DEC-006: Treat the Base Agent as the System Under Test

Decision ID: DEC-006

Date: 2026-06-05

Status: accepted

Context:

The project now includes a dedicated SUT base-agent architecture. The base agent contains an agent core, pluggable memory, retrieval/search, and scheduling modules, an MCP-style tool/action layer, and telemetry/audit outputs.

Decision:

Implement the base agent as the controlled System Under Test rather than treating it as an opaque external dependency.

Rationale:

The dissertation requires component-level attribution. Treating the base agent as a controlled SUT allows memory, retrieval, and scheduling variants to be swapped through stable interfaces while holding task definitions, prompts, tool schemas, seeds, and runtime settings fixed.

Consequences:

- Phase 1 adds a minimal baseline SUT agent.
- Phase 2 expands the SUT with the controlled component variants.
- Additional variants shown in the SUT diagram are deferred unless they support the core `2^3` experiment.

### DEC-007: Use Standard-Library Dataclasses for Phase 1 Contracts

Decision ID: DEC-007

Date: 2026-06-05

Status: accepted

Context:

Phase 1B/1C requires typed schema models and fixture validation, but the project should remain dependency-light until a stronger need for runtime validation libraries emerges.

Decision:

Implement the initial contract models with Python standard-library dataclasses and explicit validation helpers.

Rationale:

Dataclasses keep the scaffold lightweight, reproducible, and easy to inspect. Explicit validation keeps schema assumptions visible in the source code and avoids adding external dependencies before the baseline pipeline exists.

Consequences:

- Contract models are implemented in `src/avf/contracts/schemas.py`.
- Validation errors use the project-level `ValidationError`.
- A future move to Pydantic remains possible if later phases require richer validation.

### DEC-008: Use JSON for Initial Fixtures

Decision ID: DEC-008

Date: 2026-06-05

Status: accepted

Context:

The framework needs persisted examples for task cases, run configs, component configs, and tool specs. The fixture format should be strict, dependency-free, and easy to validate in Phase 1.

Decision:

Use JSON for initial test data fixtures.

Rationale:

JSON is available through the Python standard library, maps directly to the documented contracts, and avoids adding a YAML dependency during the scaffold phase.

Consequences:

- Initial fixtures are stored under `test_data/`.
- The fixture validation CLI validates JSON fixtures.
- YAML can be revisited later if authoring ergonomics become more important than dependency minimisation.

### DEC-009: Use Modular Source Boundaries Before Multi-Container Deployment

Decision ID: DEC-009

Date: 2026-06-05

Status: accepted

Context:

The framework has multiple architectural layers: orchestration, SUT/base agent, mock services, verification, metrics, reporting, and dashboard. These layers may eventually be deployed as separate Docker containers, but implementing them as separate containers too early would add operational complexity before the contracts and local execution path are validated.

Decision:

Use a single repository and modular Python package structure first. Preserve clear source-code and contract boundaries between layers, then introduce Docker/container deployment later once the local baseline pipeline is stable.

Rationale:

The dissertation requires a reproducible, inspectable implementation. Source-level modularity allows the contracts, tests, fixtures, and execution path to mature before introducing container orchestration. Containerisation should support reproducibility and deployment, not replace the software design boundaries.

Consequences:

- Phase 1D and the rest of the early baseline pipeline remain inside `src/avf/`.
- Mock services can become separate containers once their tool contracts are stable.
- The dashboard can become a separate container after reporting artifacts exist.
- The SUT/base agent may remain in-process initially and move to a separate container if isolation or deployment reproducibility requires it.
- Future Docker Compose planning should preserve the existing contract boundaries rather than reorganising the source tree around containers.

### DEC-010: Generate Run IDs Deterministically from Controlled Inputs

Decision ID: DEC-010

Date: 2026-06-05

Status: accepted

Context:

Phase 1D introduces a minimal orchestrator that creates a run context before agent execution. The run identifier must support replayability and matched comparisons across task, seed, perturbation schedule, and component configuration cells.

Decision:

Generate `run_id` values deterministically from controlled run inputs rather than using timestamps, random UUIDs, or filesystem paths.

Rationale:

Deterministic run IDs make it easier to confirm that repeated setup from the same task, run configuration, component configuration, and tool schemas refers to the same experimental cell. This supports reproducibility and later rerun tracking.

Consequences:

- `run_id` generation uses task ID/version, run config ID, seed, perturbation schedule, component factor levels, and tool schema versions.
- Timestamps and local paths are excluded from the run ID payload.
- A change to controlled inputs intentionally changes the run ID.
- Later execution phases can attach trace, verification, metric, and report artifacts to the same deterministic run identity.

### DEC-011: Require User Approval Before Phase Commits and Pushes

Decision ID: DEC-011

Date: 2026-06-05

Status: accepted

Context:

Each implementation phase should be reviewed and verified before it is recorded in Git and pushed to the remote GitHub repository.

Decision:

After implementing and testing each phase, pause and ask the user for approval before creating a detailed commit and pushing to the remote repository.

Rationale:

This keeps version-control history aligned with reviewed phase boundaries and gives the user control over when dissertation-relevant milestones are published.

Consequences:

- Phase completion summaries should include verification commands and current working-tree status.
- Commits should use detailed messages describing scope, implementation decisions, fixtures, tests, and verification results.
- No phase commit or push should be performed without explicit user approval.

### DEC-012: Push Phase Work to Phase-Specific Branches

Decision ID: DEC-012

Date: 2026-06-05

Status: accepted

Context:

The user wants to manually create pull requests on GitHub after each implementation phase. Pushing phase work directly to `main` would bypass that review workflow.

Decision:

For each implementation phase, create a new branch with a name relevant to that phase, commit the phase work on that branch, and push the branch to the remote repository. The user will manually open the GitHub pull request.

Rationale:

Phase-specific branches make the repository history easier to review and keep phase milestones aligned with pull requests. This also supports dissertation traceability by making each phase implementation a distinct review unit.

Consequences:

- Future phase work should not be pushed directly to `origin/main`.
- Branch names should be descriptive, for example `phase-1d-minimal-orchestrator`.
- After implementation and verification, the assistant should ask for approval before creating the branch commit and pushing it.
- The user remains responsible for opening and merging pull requests on GitHub.

### DEC-013: Use Deterministic Baseline Reasoning for Phase 1E

Decision ID: DEC-013

Date: 2026-06-05

Status: accepted

Context:

Phase 1E needs a baseline SUT agent to validate the agent boundary, tool dispatch path, trace event emission, and final answer output. Calling a live or hosted LLM at this stage would introduce external dependency and non-determinism before mock services, verification, and reporting are implemented.

Decision:

Implement Phase 1E with deterministic local baseline reasoning and planning.

Rationale:

The goal of Phase 1E is infrastructure validation, not model-quality measurement. Deterministic reasoning makes tests repeatable and keeps the fixed-seed baseline independent of external model availability.

Consequences:

- The baseline planner creates a fixed memory-write, memory-query, final-answer plan for the initial memory task.
- The agent emits deterministic trace events and trace IDs.
- A fixed LLM adapter can be introduced later without changing the `AgentRunInput`, `AgentAction`, `AgentObservation`, or `AgentOutput` contracts.

### DEC-014: Inject Tool Clients into the Baseline SUT Agent

Decision ID: DEC-014

Date: 2026-06-05

Status: accepted

Context:

Phase 1E must demonstrate that the SUT can call tools through an MCP-style interface, but concrete mock services are scheduled for Phase 1F.

Decision:

The baseline SUT agent depends on an injected `ToolClient` protocol rather than constructing or owning mock services directly.

Rationale:

This preserves the boundary between the SUT agent and the mock service layer. It allows Phase 1E tests to use a deterministic in-memory tool-client double while keeping production mock service implementation deferred to Phase 1F.

Consequences:

- The SUT agent can be tested without live APIs or concrete mock-service containers.
- Phase 1F can implement mock services that satisfy the same tool-client boundary.
- The agent core remains focused on perception, planning, action execution, observation processing, and final answer generation.

### DEC-015: Use Memory as the First Mock Service

Decision ID: DEC-015

Date: 2026-06-06

Status: accepted

Context:

Phase 1F requires one deterministic mock service with one or two tool endpoints. The current Phase 1 task is memory-focused, and the Phase 1E baseline SUT agent already dispatches `memory.write` and `memory.query` actions through the `ToolClient` protocol.

Decision:

Implement a deterministic mock memory service first, with `memory.write` and `memory.query` endpoints.

Rationale:

The memory mock service directly supports the existing memory-recall task and validates the SUT-to-tool boundary without adding unrelated file/API complexity. It also aligns with memory as one of the dissertation's controlled component factors.

Consequences:

- `MockMemoryService` stores in-memory records deterministically.
- The service returns documented `ToolResult` values.
- Unsupported tools and invalid arguments produce structured errors.
- File, API, and collaboration-style mock services remain deferred.

### DEC-016: Add Perturbation Hooks Before Full Perturbation Schedules

Decision ID: DEC-016

Date: 2026-06-06

Status: accepted

Context:

The dissertation requires controlled perturbations, but Phase 1F only needs a minimal mock service. Full perturbation schedule replay depends on later orchestration and trace integration.

Decision:

Add a small perturbation hook interface to mock services now, with no-op and static deterministic implementations. Defer full schedule loading and replay semantics to later phases.

Rationale:

This keeps the mock service deterministic while preserving a clear extension point for temporary unavailability, noisy observations, and latency perturbations.

Consequences:

- Phase 1F uses `NoPerturbationController` by default.
- `StaticPerturbationController` validates that service results can be deterministically perturbed.
- Later schedule replay can build on the same hook without changing the `ToolClient` boundary.

### DEC-017: Use Local JSON Trace Artifacts for Phase 1G

Decision ID: DEC-017

Date: 2026-06-06

Status: accepted

Context:

Phase 1G introduces trace logging. A possible alternative would be to introduce Kafka, Flink, or another streaming/event-processing stack immediately. However, the current baseline still needs deterministic local verification, metrics, and reporting before scaling to distributed execution.

Decision:

Implement Phase 1G as a local JSON trace artifact pipeline using the existing `RunTrace` and `TraceEvent` contracts. Defer Kafka, Flink, and streaming telemetry infrastructure.

Rationale:

The dissertation baseline requires replayable, inspectable, and versioned trace evidence. Local JSON artifacts satisfy the current verifier and reporting needs with less operational complexity and fewer sources of non-determinism. Streaming infrastructure would be premature before the local end-to-end pipeline is validated.

Consequences:

- `RunTrace` artifacts are persisted as deterministic JSON files under the configured trace directory.
- Trace validation happens before writing artifacts and after reading artifacts.
- Verification, metrics, and reporting can consume the same persisted trace contract.
- Kafka, Flink, or similar infrastructure may be revisited later for large-scale runs, dashboards, or live monitoring, but they are not part of Phase 1G.

### DEC-018: Start Verification with Deterministic Rule-Based Checks

Decision ID: DEC-018

Date: 2026-06-06

Status: accepted

Context:

Phase 1H requires a verifier that can consume a stored `RunTrace` and a `TaskCase` and return an evidence-backed `VerificationResult`. The architecture allows later LLM-as-judge and consensus verification, but those would introduce model dependency and semantic variability before the local baseline pipeline is complete.

Decision:

Implement Phase 1H with a deterministic rule-based verifier. Defer LLM-as-judge and consensus verification until deterministic trace, metrics, and reporting artifacts are stable.

Rationale:

The first verifier should validate the framework's contracts and task success criteria without external services or non-deterministic judging. Rule-based checks are directly auditable, easy to reproduce, and sufficient for the initial memory-recall task.

Consequences:

- `RuleBasedVerifier` checks trace validity, task identity, run completion, required final-answer text, and required tool calls.
- Every verification output is represented as a versioned `VerificationResult`.
- Failed checks produce explicit failure reasons and structured evidence.
- Semantic or subjective answer-quality checks remain future extensions rather than Phase 1 dependencies.

### DEC-019: Use Deterministic File Artifacts for the First Baseline Run

Decision ID: DEC-019

Date: 2026-06-06

Status: accepted

Context:

Phase 1I must demonstrate the first reproducible end-to-end baseline run. The framework now has contracts, deterministic orchestration, a baseline SUT agent, a deterministic mock memory service, trace logging, and rule-based verification.

Decision:

Implement the first baseline run as a deterministic local artifact pipeline that writes a `RunTrace`, `VerificationResult`, `MetricResult`, and Markdown run report.

Rationale:

The Phase 1 goal is to prove the local benchmark environment before adding component variants, containers, dashboards, or large-scale experiment execution. File artifacts are inspectable, easy to compare across repeated runs, and suitable for dissertation audit evidence.

Consequences:

- `scripts/run-phase1-baseline.sh` is the first reproducible run entrypoint.
- `python -m avf run-baseline` provides the equivalent CLI command.
- Running the same task/config/component/tool-schema cell with the same seed produces equivalent artifact contents.
- Metrics are deterministic and avoid wall-clock timing in Phase 1.
- More sophisticated metrics, report formats, and dashboards remain later extensions.

### DEC-020: Introduce Storage Abstractions Before Database-Backed Stores

Decision ID: DEC-020

Date: 2026-06-06

Status: accepted

Context:

Phase 2 begins modular component integration. The architecture includes a test data repository and results store, but Phase 1 implemented both as filesystem directories. The project also needs a SQLite memory backend as part of the SUT memory factor, which should not be confused with the experiment results store.

Decision:

Introduce filesystem-backed repository/store abstractions in Phase 2A and defer database-backed results storage. Implement SQLite first as a SUT memory backend in Phase 2B.

Rationale:

The current JSON and Markdown artifacts are reproducible, inspectable, and sufficient for early component integration. Adding a results database before experiment volume requires it would add complexity without improving component attribution. By contrast, SQLite memory is part of the experimental factor design and should be implemented as SUT behavior.

Consequences:

- `FileSystemTestDataRepository` formalises the current `test_data/` fixture repository.
- `FileSystemResultsStore` formalises the current `artifacts/` result store.
- The results store remains artifact-first.
- SQLite is introduced as a memory component in Phase 2B, not as a replacement for result artifacts.
- A results index database can be revisited in Phase 3 if experiment scale or dashboard requirements justify it.

### DEC-021: Use Explicit Deferred Component Descriptors in Phase 2A

Decision ID: DEC-021

Date: 2026-06-06

Status: accepted

Context:

Phase 2A needs `ComponentConfig` to resolve through a component registry, but the real SQLite memory and BM25 retrieval implementations are scheduled for later subphases. The existing `A1_B1_C1` fixture must remain executable without pretending that all component variants already exist.

Decision:

Resolve the current `A1_B1_C1` cell through explicit component descriptors. Mark SQLite memory and BM25 retrieval as deferred, mark sequential scheduling as available, and reject unimplemented vector, embedding, and rule-based variants with explicit validation errors.

Rationale:

This creates the component-selection boundary without silently falling back for unsupported variants. It keeps the Phase 1 baseline running while preserving dissertation clarity about which component implementations exist.

Consequences:

- `ComponentRegistry` resolves the current baseline cell deterministically.
- Deferred descriptors document the planned implementation phase for memory and retrieval.
- Unsupported variants fail clearly.
- Later Phase 2 subphases can replace deferred descriptors with concrete implementations without changing `ComponentConfig`.

### DEC-022: Use Standard-Library SQLite for the First Memory Backend

Decision ID: DEC-022

Date: 2026-06-06

Status: accepted

Context:

Phase 2B requires a real SQLite-backed episodic memory backend for the SUT memory factor. The implementation must remain reproducible, dependency-light, and separate from the filesystem results store.

Decision:

Implement `memory_backend=sqlite` with Python standard-library `sqlite3`. Use SQLite only for SUT memory state, not for trace, verification, metric, or report artifacts.

Rationale:

The standard-library SQLite driver keeps the implementation dependency-light and easy to inspect. It also supports temporary databases in tests, deterministic schema creation, and persistent records during a run or across instances when a file path is supplied.

Consequences:

- `SQLiteMemory` implements the shared memory interface.
- `MockMemoryService` can delegate memory tools to the SQLite backend.
- `ComponentRegistry` marks SQLite memory as available.
- The results store remains filesystem-backed.
- Vector memory remains deferred to Phase 2E.

### DEC-023: Use Dependency-Light Okapi BM25 for the First Retrieval Strategy

Decision ID: DEC-023

Date: 2026-06-07

Status: accepted

Context:

Phase 2C requires the first concrete retrieval strategy for the dissertation's retrieval factor. The implementation must be deterministic, inspectable, and independent from the SQLite memory storage backend.

Decision:

Implement `retrieval_strategy=bm25` as a local Okapi BM25 retriever using only the Python standard library. The retrieval module owns document indexing and ranking; the memory backend owns record persistence.

Rationale:

BM25 provides a transparent keyword-ranking baseline that is appropriate for controlled comparison against later embedding retrieval. Keeping the implementation local avoids adding an external search engine or dependency before the component contracts have stabilised.

Consequences:

- `BM25Retriever` implements the shared retrieval interface.
- `MockMemoryService` indexes memory records into the selected retrieval module.
- `memory.query` can return deterministic ranked records and retrieval evidence.
- SQLite remains a storage component rather than a ranking implementation.
- At Phase 2C completion, embedding retrieval remained deferred to Phase 2F.

### DEC-024: Use Explainable Rule Priorities for the Second Scheduler

Decision ID: DEC-024

Date: 2026-06-07

Status: accepted

Context:

Phase 2D requires the second scheduling factor level for the dissertation's component comparison. The scheduler must be deterministic, explainable, and observable in traces without introducing parallel execution or changing task fixtures.

Decision:

Implement `scheduling_policy=rule_based` as a deterministic priority scheduler. The rule order is internal actions, memory writes, memory queries, generic tool calls, and final answers. Ties preserve planner order.

Rationale:

This provides a concrete scheduling contrast against the sequential baseline while keeping the rules simple enough to inspect and defend in the dissertation. Recording scheduler decisions in the trace supports component-level attribution.

Consequences:

- `RuleBasedScheduler` implements the shared scheduler interface.
- `SequentialScheduler` remains unchanged for the baseline cell.
- Scheduler decisions are emitted in trace payloads.
- The scheduler orders actions but does not execute tools or modify memory/retrieval behavior.
- DAG and parallel scheduling remain deferred extensions.

### DEC-025: Use Deterministic Sparse Vectors for Vector Memory

Decision ID: DEC-025

Date: 2026-06-07

Status: accepted

Context:

Phase 2E requires the second memory backend for the dissertation's memory factor. The implementation must expose the same memory interface as SQLite memory, support deterministic similarity ranking, and avoid live embedding API dependencies.

Decision:

Implement `memory_backend=vector` as an in-process vector memory backend using deterministic sparse lexical vectors and cosine similarity. Do not call a hosted embedding model in Phase 2E.

Rationale:

The sparse-vector implementation validates the vector memory component boundary without introducing network access, API keys, model-version drift, or non-reproducible embedding behavior. This keeps Phase 2 focused on controlled component substitution.

Consequences:

- `VectorMemory` implements the shared memory interface.
- Vector memory records use deterministic `mem_###` identifiers.
- Similarity ranking is reproducible and testable offline.
- The current vector representation is lexical rather than semantic.
- Hosted or model-based embeddings remain deferred until their reproducibility impact is documented.

### DEC-026: Use Deterministic Local Embeddings for the Second Retrieval Strategy

Decision ID: DEC-026

Date: 2026-06-07

Status: accepted

Context:

Phase 2F requires the second retrieval strategy for the dissertation's retrieval factor. The implementation must expose the same retrieval interface as BM25, remain independent from the selected memory backend, and avoid hosted embedding API dependencies by default.

Decision:

Implement `retrieval_strategy=embedding` as a local embedding retriever using the shared deterministic sparse lexical embedder. Do not call a hosted embedding service in Phase 2F.

Rationale:

This validates the embedding retrieval component boundary while preserving reproducibility and avoiding model-version drift, API keys, network access, and cost variability. The implementation remains inspectable and can later be replaced by a hosted or model-backed adapter if that tradeoff is explicitly documented.

Consequences:

- `EmbeddingRetriever` implements the shared retrieval interface.
- Embedding retrieval can be paired with SQLite memory or vector memory through `ComponentConfig`.
- Retrieval result payloads match the BM25 shape.
- Ranking is reproducible and testable offline.
- The current embedding representation is lexical rather than semantic.

## Open Decisions

### OPEN-001: Schema Implementation Library

Question:

Should contracts be implemented using dataclasses, Pydantic, or plain typed dictionaries?

Initial preference:

Use standard library dataclasses first if dependency minimisation is preferred. Use Pydantic if stronger runtime validation is needed.

Resolution:

Resolved by DEC-007. Phase 1B/1C uses standard-library dataclasses.

### OPEN-002: Fixture Format

Question:

Should test cases and run configs be stored as JSON or YAML?

Initial preference:

Use JSON initially because it is dependency-free, strict, and directly compatible with schema validation.

Resolution:

Resolved by DEC-008. Phase 1B/1C uses JSON fixtures.

### OPEN-003: First Mock Service

Question:

Should the first mock service be memory-focused, file-focused, or API-focused?

Initial preference:

Use a memory-focused mock service because memory is one of the dissertation's target experimental factors and supports a simple first task.

Resolution:

Resolved by DEC-015. Phase 1F implements a deterministic mock memory service.

### OPEN-004: Containerisation Timing

Question:

Should Docker/containerisation be introduced before or after the local baseline pipeline?

Initial preference:

Build the deterministic local baseline first, then containerise after the scripts and artifact layout are stable.

Resolution target:

End of Phase 1 or start of Phase 2.

### OPEN-005: Baseline Reasoning Implementation

Question:

Should the Phase 1 baseline SUT use a deterministic stubbed reasoning module or call a real fixed LLM backbone?

Initial preference:

Use a deterministic stubbed reasoning module first to validate orchestration, mock services, tracing, verification, and reporting without external model dependency. Introduce a fixed LLM adapter only after the baseline infrastructure is stable.

Resolution:

Resolved by DEC-013. Phase 1E uses deterministic local baseline reasoning.
