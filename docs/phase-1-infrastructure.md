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

Future containerisation is still a project requirement. The early implementation will preserve clear package boundaries so that orchestration, SUT/base agent, mock services, verification, results storage, and dashboard components can be moved into Docker containers later without changing the core contracts.

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

Status: complete.

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

Implemented outputs:

- fixture loaders in `src/avf/orchestration/loaders.py`,
- deterministic run-context builder in `src/avf/orchestration/run_context.py`,
- execution-engine shell in `src/avf/orchestration/execution_engine.py`,
- CLI command through `python -m avf create-run-context`,
- tests in `tests/test_orchestration.py`.

Phase 1D records a `created` run status only. It does not execute the SUT agent, mock services, verification, metrics, or reporting. Those are handled by later Phase 1 subphases.

Verification:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
env PYTHONPATH=src python3 -m avf create-run-context --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --components test_data/components/A1_B1_C1.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json
```

### Phase 1E: Baseline SUT Agent

Status: complete.

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

Implemented outputs:

- deterministic baseline SUT agent in `src/avf/agents/core/baseline_agent.py`,
- perception/input processing in `src/avf/agents/core/perception.py`,
- deterministic planning in `src/avf/agents/core/planner.py`,
- action execution in `src/avf/agents/core/action_executor.py`,
- observation processing in `src/avf/agents/core/observation_processor.py`,
- deterministic trace-event construction in `src/avf/agents/core/trace.py`,
- agent state model in `src/avf/agents/core/state.py`,
- MCP-style `ToolClient` protocol in `src/avf/agents/tools/client.py`,
- stable memory, retrieval, and scheduling module interfaces,
- sequential scheduler implementation for the baseline agent,
- tests in `tests/test_baseline_agent.py`.

Phase 1E uses an injected tool-client interface. The tests provide an in-memory tool-client double to validate the SUT tool boundary. Concrete mock service implementation remains Phase 1F.

Verification:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
env PYTHONPATH=src python3 -m avf create-run-context --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --components test_data/components/A1_B1_C1.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json
```

### Phase 1F: Minimal Mock Service

Status: complete.

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

Implemented outputs:

- deterministic mock memory service in `src/avf/mock_services/memory_service.py`,
- `memory.write` endpoint,
- `memory.query` endpoint,
- structured error responses for unsupported tools and invalid arguments,
- no-op perturbation controller,
- static deterministic perturbation hook for later schedule integration,
- tests in `tests/test_mock_services.py`.

The mock service implements the same `ToolClient` protocol consumed by the Phase 1E baseline SUT agent. This validates the SUT-to-mock-service boundary without introducing network or container orchestration yet.

Verification:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
env PYTHONPATH=src python3 -m avf create-run-context --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --components test_data/components/A1_B1_C1.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json
env PYTHONPATH=src python3 -c "from avf.mock_services import MockMemoryService, StaticPerturbationController; print('mock services import ok')"
```

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

## Phase Commit Protocol

After each subphase is implemented and tested, the implementation should pause before committing. The user must approve the detailed commit message and push to the remote GitHub repository.

Phase implementation work should be committed on a phase-specific branch rather than directly on `main`. The user will manually create the GitHub pull request.

Each phase-completion commit should include:

- the implemented subphase scope,
- changed source modules,
- changed fixtures or artifacts,
- documentation updates,
- test and CLI verification commands,
- any implementation decisions added to the decision log.

Example branch names:

- `phase-1d-minimal-orchestrator`
- `phase-1e-baseline-sut-agent`
- `phase-1f-minimal-mock-service`
