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

Resolution target:

Phase 1F.

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
