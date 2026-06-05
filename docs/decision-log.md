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

Resolution target:

Phase 1E.
