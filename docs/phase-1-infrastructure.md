# Phase 1 Infrastructure Plan

## Purpose

Phase 1 establishes the minimal reproducible evaluation infrastructure. It is the foundation for the later modular component experiments.

The goal is not to build the complete automated testing system immediately. The goal is to build a validated baseline pipeline that proves the architecture can execute fixed tasks, interact with deterministic mock services, collect complete traces, verify results, and produce reports.

## Phase 1 Milestone

Milestone M1:

> Reproducible benchmark environment with validated logging, schemas, and fixed-seed / fixed-schedule baseline execution.

## Phase 1 Deliverable

Deliverable D1:

> Containerised benchmark environment, tool schemas, trace pipeline, and baseline agent run scripts.

Containerisation may be introduced after the local baseline pipeline is working. The immediate priority is a deterministic local implementation with stable contracts.

## Subphase Breakdown

### Phase 1A: Documentation Baseline

Status: complete.

Outputs:

- `docs/implementation-roadmap.md`
- `docs/architecture-overview.md`
- `docs/base-agent-design.md`
- `docs/contracts-and-schemas.md`
- `docs/phase-1-infrastructure.md`
- `docs/decision-log.md`

Acceptance criteria:

- architecture layers are documented,
- implementation phases are documented,
- initial contract set is documented,
- open decisions are recorded,
- documents are suitable for dissertation reuse.

### Phase 1B: Project Scaffold

Status: complete.

Outputs:

```text
pyproject.toml
src/avf/
tests/
scripts/
test_data/
artifacts/
```

Planned package structure:

```text
src/avf/
  contracts/
  orchestration/
  mock_services/
  agents/
    core/
    memory/
    retrieval/
    scheduling/
    tools/
  tracing/
  verification/
  metrics/
  reporting/
```

Acceptance criteria:

- package imports successfully,
- tests can run,
- CLI entrypoint exists,
- no external service is required.

Implemented outputs:

- `pyproject.toml`
- `src/avf/`
- `tests/`
- `scripts/`
- `test_data/`
- `artifacts/`
- CLI entrypoint through `python -m avf validate-fixtures`

### Phase 1C: Contracts and Schemas

Status: complete.

Outputs:

- typed schema definitions,
- validation tests,
- example task fixture,
- example run config fixture,
- example component config fixture,
- example tool spec fixture.

Acceptance criteria:

- one `TaskCase` fixture loads and validates,
- one `RunConfig` fixture loads and validates,
- one `ComponentConfig` fixture loads and validates,
- one `ToolSpec` fixture loads and validates.

Implemented outputs:

- standard-library dataclass contract models in `src/avf/contracts/schemas.py`,
- fixture loading and validation in `src/avf/contracts/fixture_loader.py`,
- example JSON fixtures under `test_data/`,
- unit tests under `tests/`,
- CLI fixture validation.

Verification:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
```

### Phase 1D: Minimal Orchestrator

Outputs:

- test case loader,
- run context builder,
- execution engine,
- deterministic run ID generation,
- fixed seed handling.

Acceptance criteria:

- orchestrator loads one task and one config,
- orchestrator creates a run context,
- orchestrator executes a baseline run,
- run status is recorded.

### Phase 1E: Baseline SUT Agent

Outputs:

- perception/input processor,
- deterministic baseline reasoning/planning path,
- sequential action executor,
- observation processor,
- stable memory/retrieval/scheduler interfaces,
- MCP-style tool client interface.

Acceptance criteria:

- base agent accepts orchestrator inputs,
- base agent executes one think-plan-act-observe loop,
- base agent emits trace events for internal steps,
- base agent can call the minimal mock service through a tool interface,
- base agent returns a final answer and structured outputs.

### Phase 1F: Minimal Mock Service

Outputs:

- one mock service,
- one or two tool endpoints,
- deterministic tool responses,
- perturbation hook.

Acceptance criteria:

- mock service accepts a `ToolCall`,
- mock service returns a `ToolResult`,
- invalid inputs produce structured errors,
- tool behavior is deterministic under fixed inputs.

### Phase 1G: Trace Logging

Outputs:

- trace event writer,
- run trace writer,
- artifact path handling,
- trace validation.

Acceptance criteria:

- agent steps are logged,
- tool calls are logged,
- tool results are logged,
- final answer is logged,
- trace can be consumed by verifier.

### Phase 1H: Rule-Based Verification

Outputs:

- deterministic verifier,
- success criteria checks,
- evidence extraction,
- verification result artifact.

Acceptance criteria:

- verifier consumes `RunTrace` and `TaskCase`,
- verifier returns `VerificationResult`,
- pass/fail decision is evidence-backed,
- failure reasons are explicit.

### Phase 1I: First Reproducible Baseline Run

Outputs:

- baseline run script,
- first trace artifact,
- first verification artifact,
- first metric artifact,
- first Markdown report.

Acceptance criteria:

- running the script twice with the same seed produces equivalent results,
- artifacts are written to known locations,
- report summarises task success, tool calls, and verifier outcome,
- Phase 1 baseline is ready for extension.

## Initial Thin Slice

The first runnable system will use:

- one memory-focused task,
- one minimal base agent / SUT implementation,
- one deterministic think-plan-act-observe loop,
- one mock memory service,
- one fixed seed,
- one no-op perturbation schedule,
- one rule-based verifier,
- one JSON result,
- one Markdown report.

This thin slice is intentionally small. It validates every layer without creating unnecessary complexity.

## Testing Strategy

Phase 1 tests will cover:

- schema validation,
- fixture loading,
- baseline SUT input/output behavior,
- base-agent tool dispatch,
- deterministic tool behavior,
- orchestrator run context creation,
- trace event ordering,
- verifier pass/fail behavior,
- metrics computation,
- report generation.

## Reproducibility Controls

Phase 1 will introduce these controls immediately:

- fixed seed stored in `RunConfig`,
- perturbation schedule ID stored in `RunTrace`,
- component config ID stored in `RunTrace`,
- schema versions stored in all persisted artifacts,
- deterministic mock service behavior,
- complete trace event logging.

## Documentation Outputs for Dissertation

Phase 1 produces documentation that can support the dissertation implementation chapter:

- staged build methodology,
- rationale for thin-slice-first development,
- contract-first design,
- reproducibility controls,
- trace-based verification pipeline,
- limitations of the initial baseline.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Overbuilding before validating contracts | Integration delays | Build one thin end-to-end slice first |
| Schema drift | Invalid experimental comparisons | Version schemas and fixtures |
| Incomplete traces | Weak diagnostics | Make trace completeness a Phase 1 acceptance criterion |
| Mock environment too unrealistic | Weak external validity | Add controlled perturbations after deterministic baseline |
| Component coupling | Confounded ablation results | Stable contracts before variants |

## Exit Criteria for Phase 1

Phase 1 is complete when:

- one baseline task can be executed end to end,
- the run is reproducible under the same seed,
- trace, verification, metric, and report artifacts are generated,
- all Phase 1 tests pass,
- implementation decisions are recorded in the decision log.
