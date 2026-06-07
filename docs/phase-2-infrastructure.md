# Phase 2 Infrastructure Plan

## Purpose

Phase 2 turns the Phase 1 thin slice into a modular component evaluation framework.

Phase 1 proved that the framework can load validated fixtures, execute one deterministic baseline agent run, call a mock service, persist a trace, verify the run, compute initial metrics, and generate a Markdown report. Phase 2 builds on that foundation by making the System Under Test genuinely configurable through interchangeable memory, retrieval, and scheduling components.

The main Phase 2 objective is controlled component substitution. Each component variant must be swappable without changing task definitions, tool schemas, run configuration semantics, trace contracts, verification rules, metric contracts, or reporting consumers.

## Phase 2 Milestone

Milestone M2:

> Modular architecture with clean component swaps and no interface changes.

## Phase 2 Deliverable

Deliverable D2:

> Validated modular implementation of memory, retrieval, and scheduling variants for the dissertation's `2^3` component comparison.

## Relationship to Phase 1

Phase 1 produced the first reproducible baseline pipeline:

```text
TaskCase + RunConfig + ComponentConfig + ToolSpec fixtures
  -> RunContext
  -> BaselineSUTAgent
  -> MockMemoryService
  -> RunTrace
  -> RuleBasedVerifier
  -> MetricResult
  -> Markdown report
```

Phase 2 keeps this pipeline but replaces the current hard-coded baseline behavior with a controlled component selection layer.

The Phase 1 baseline currently has these limitations:

- `ComponentConfig.memory_backend` is validated but not yet connected to real memory backend selection.
- `ComponentConfig.retrieval_strategy` is validated but not yet connected to retrieval behavior.
- `ComponentConfig.scheduling_policy` is validated; sequential scheduling is implemented and rule-based scheduling is implemented in Phase 2D.
- `test_data/` acts as the test data repository using JSON files.
- `artifacts/` acts as the results store using JSON and Markdown files.
- no persistent experiment database exists yet.
- the mock memory service is in-memory only and is not the dissertation SQLite memory backend.

Phase 2 addresses these limitations incrementally.

## Storage and Database Position

The architecture diagram includes a test data repository and results store. At the end of Phase 1, both are intentionally file-based.

| Architecture element | Phase 1 implementation | Phase 2 plan |
|---|---|---|
| Test data repository | `test_data/` JSON fixtures | formal repository abstraction over filesystem fixtures |
| Results store | `artifacts/` JSON and Markdown files | formal result-store abstraction over filesystem artifacts |
| Database service | not implemented | deferred unless needed for external-service scenarios |
| SQLite memory backend | implemented in Phase 2B | SUT memory variant for `memory_backend=sqlite` |
| Vector memory backend | implemented in Phase 2E | SUT memory variant for `memory_backend=vector` |
| Dashboard data source | not implemented | deferred until result artifacts and experiment runs stabilise |

The first database-related implementation should be the SQLite memory backend because it is part of the dissertation's controlled memory factor. It should not be confused with the results store. The results store remains file-based until experiment volume or dashboard requirements justify a database-backed store.

## Database and Dashboard Timing

Databases and dashboards should be introduced only when they support a clear experimental or analysis need.

The implementation order should be:

1. implement SQLite as a SUT memory backend in Phase 2B,
2. keep the test data repository and results store filesystem-based through early Phase 2,
3. add result-store integrity checks and artifact manifests in Phase 2I,
4. introduce a results index database in Phase 3 only if factorial experiment volume requires faster querying, rerun tracking, or dashboard support,
5. implement the dashboard in Phase 3 or Phase 4 after real component-run artifacts exist.

This distinction matters for the dissertation:

- SQLite memory is part of the controlled SUT component comparison.
- a results database is infrastructure for managing experiment artifacts.
- a dashboard is an analysis and reporting layer.

These should not be collapsed into one implementation step because doing so would make it harder to explain which software changes affect agent behavior and which only affect storage or presentation.

Recommended timing:

| Capability | Recommended phase | Rationale |
|---|---|---|
| SQLite memory backend | Phase 2B | Required for the `memory_backend=sqlite` factor |
| Vector memory backend | Phase 2E | Required for the second memory factor level |
| Filesystem test data repository abstraction | Phase 2A | Formalises current `test_data/` behavior |
| Filesystem results store abstraction | Phase 2A | Formalises current `artifacts/` behavior |
| Artifact manifest and result-store QA | Phase 2I | Validates trace/result/report consistency before large runs |
| SQLite results index | Phase 3A, if needed | Supports querying many experiment artifacts without replacing artifact files |
| Postgres results store | Later extension | Only needed if SQLite is insufficient for scale or multi-user access |
| Reporting dashboard | Phase 3B or Phase 4A | Needs real experiment artifacts and metrics to be useful |

The default Phase 2 position is therefore:

```text
test data repository = filesystem fixtures
results store = filesystem artifacts
SUT memory backend = real SQLite/vector implementations
dashboard = deferred until experiment artifacts exist
```

## Phase 2 Design Principles

Phase 2 follows these principles:

1. Component interfaces are locked before component variants expand.
2. `ComponentConfig` is the only source of experimental component selection.
3. Variant selection must be deterministic and traceable.
4. Component swaps must not change task fixtures, tool schemas, verifier logic, or report readers.
5. Persistent storage introduced for memory must not silently become the experiment results database.
6. Results remain artifact-first until the dashboard or large-scale experiment runner requires a stronger store.
7. Tests must compare behavior across variants through the same public contracts.

## Target Component Factors

The core dissertation design uses three two-level factors.

| Factor | ComponentConfig field | Level 1 | Level 2 |
|---|---|---|---|
| Memory backend | `memory_backend` | `sqlite` | `vector` |
| Retrieval strategy | `retrieval_strategy` | `bm25` | `embedding` |
| Scheduling policy | `scheduling_policy` | `sequential` | `rule_based` |

This creates eight component cells:

```text
A1_B1_C1  sqlite memory + bm25 retrieval + sequential scheduling
A1_B1_C2  sqlite memory + bm25 retrieval + rule-based scheduling
A1_B2_C1  sqlite memory + embedding retrieval + sequential scheduling
A1_B2_C2  sqlite memory + embedding retrieval + rule-based scheduling
A2_B1_C1  vector memory + bm25 retrieval + sequential scheduling
A2_B1_C2  vector memory + bm25 retrieval + rule-based scheduling
A2_B2_C1  vector memory + embedding retrieval + sequential scheduling
A2_B2_C2  vector memory + embedding retrieval + rule-based scheduling
```

The existing `A1_B1_C1` fixture is the starting cell and must remain valid.

## Planned Package Structure

Phase 2 should preserve the existing modular package structure and extend it conservatively:

```text
src/avf/
  storage/
    test_data_repository.py
    results_store.py
  agents/
    components/
      registry.py
      factory.py
    memory/
      interface.py
      sqlite_memory.py
      vector_memory.py
    retrieval/
      interface.py
      bm25.py
      embedding.py
    scheduling/
      interface.py
      sequential.py
      rule_based.py
  orchestration/
    experiment_config.py
    experiment_runner.py
```

The exact file names may change if the existing code suggests a better local convention, but the ownership boundaries should remain clear.

## Subphase Breakdown

### Phase 2A: Storage Abstractions and Component Registry

Status: complete.

Goal:

Create the explicit bridge from `ComponentConfig` to concrete SUT components, while formalising the current filesystem-based test data repository and results store.

Outputs:

- component registry,
- component factory,
- storage abstraction for `test_data/`,
- storage abstraction for `artifacts/`,
- tests for supported and unsupported component selections,
- documentation of locked Phase 2 interfaces.

Acceptance criteria:

- `ComponentConfig` resolves to a deterministic component bundle,
- unsupported memory/retrieval/scheduling values fail with explicit errors,
- existing `A1_B1_C1` baseline run still passes,
- test data repository abstraction can load the existing fixtures,
- results store abstraction can write trace, verification, metrics, and report paths,
- no database dependency is introduced yet.

Implementation notes:

- Do not implement all variants in Phase 2A.
- Provide placeholder registry entries only where needed, but unsupported variants should not pretend to work.
- The current filesystem behavior remains the default.

Implemented outputs:

- filesystem test data repository in `src/avf/storage/test_data_repository.py`,
- filesystem results store in `src/avf/storage/results_store.py`,
- component registry in `src/avf/agents/components/registry.py`,
- component factory in `src/avf/agents/components/factory.py`,
- baseline-run integration with component bundle resolution,
- baseline-run integration with the filesystem results store,
- tests in `tests/test_phase2a_storage_components.py`.

Phase 2A resolved the existing `A1_B1_C1` component cell. The sequential scheduler was available immediately. At Phase 2A completion, SQLite memory and BM25 retrieval were represented as explicit deferred descriptors rather than fake implementations. Phase 2B replaced the SQLite memory descriptor with a concrete implementation. Phase 2C replaced the BM25 retrieval descriptor with a concrete implementation. Phase 2D added the rule-based scheduler as the second scheduling factor level. Phase 2E adds vector memory as the second memory factor level.

Verification:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
env PYTHONPATH=src python3 -m avf run-baseline --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --components test_data/components/A1_B1_C1.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json --artifact-root /private/tmp/avf_phase2a_cli
env PYTHONPATH=src python3 -c "from avf.storage import FileSystemTestDataRepository, FileSystemResultsStore; from avf.agents.components import build_component_bundle; print('phase2a imports ok')"
```

Suggested branch name:

```text
phase-2a-storage-component-registry
```

### Phase 2B: SQLite Episodic Memory Backend

Status: complete.

Goal:

Implement the first real memory backend for the SUT component factor.

Outputs:

- SQLite-backed episodic memory implementation,
- deterministic schema creation,
- clean test database lifecycle,
- memory read/write/search interface methods,
- trace evidence showing which memory backend was selected.

Acceptance criteria:

- `memory_backend=sqlite` maps to the SQLite memory backend,
- memory writes persist during a run,
- memory reads/searches return deterministic results,
- tests use temporary SQLite databases and leave no repository artifacts,
- baseline `A1_B1_C1` continues to pass,
- memory behavior is accessed through the memory interface rather than direct SQL from the agent core.

Implementation notes:

- Use Python standard-library `sqlite3` initially.
- Keep database files temporary by default in tests.
- Do not replace the results store with SQLite.
- Persist only SUT memory state, not experiment results.

Implemented outputs:

- SQLite memory backend in `src/avf/agents/memory/sqlite_memory.py`,
- standard-library `sqlite3` schema creation and persistence,
- `write`, `read`, and `search` methods through the existing memory interface,
- optional SQLite-backed delegation in `MockMemoryService`,
- component registry update marking `memory_backend=sqlite` as available,
- baseline-run integration using the resolved SQLite memory module,
- trace evidence for selected `ComponentConfig`,
- tests in `tests/test_sqlite_memory.py` and `tests/test_phase2a_storage_components.py`.

Phase 2B keeps the results store filesystem-backed. SQLite is introduced only as SUT memory behavior for the controlled memory factor.

Verification:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
env PYTHONPATH=src python3 -m avf run-baseline --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --components test_data/components/A1_B1_C1.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json --artifact-root /private/tmp/avf_phase2b_cli
env PYTHONPATH=src python3 -c "from avf.agents.memory import SQLiteMemory; from avf.agents.components import build_component_bundle; print('phase2b imports ok')"
```

Suggested branch name:

```text
phase-2b-sqlite-memory-backend
```

### Phase 2C: BM25 Retrieval Strategy

Status: complete.

Goal:

Implement the first real retrieval/search strategy.

Outputs:

- BM25 or BM25-like keyword retrieval implementation,
- indexed document/record representation,
- deterministic ranking behavior,
- retrieval interface tests.

Acceptance criteria:

- `retrieval_strategy=bm25` maps to BM25 retrieval,
- retrieval ranking is deterministic for fixed input records,
- ties are resolved consistently,
- baseline run still passes,
- retrieval logic is separate from memory storage and scheduling.

Implementation notes:

- Prefer dependency-light implementation unless a strong reason emerges.
- If the scope of BM25 grows, document whether the implementation is full BM25 or a simplified deterministic approximation.
- Keep the output shape stable for later embedding retrieval.

Implemented outputs:

- BM25 retrieval implementation in `src/avf/agents/retrieval/bm25.py`,
- explicit retrieval interface with document indexing and metadata-filtered query support,
- deterministic Okapi BM25 ranking with index-order tie-breaking,
- component registry update marking `retrieval_strategy=bm25` as available,
- mock memory service integration so `memory.query` uses the selected retrieval module for ranking,
- baseline-run integration using the resolved BM25 retrieval module,
- tests in `tests/test_bm25_retrieval.py` and `tests/test_phase2a_storage_components.py`.

Phase 2C keeps retrieval separate from memory storage. SQLite stores records; BM25 indexes record text and ranks query results through the retrieval interface.

Verification:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
env PYTHONPATH=src python3 -m avf run-baseline --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --components test_data/components/A1_B1_C1.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json --artifact-root /private/tmp/avf_phase2c_cli
env PYTHONPATH=src python3 -c "from avf.agents.retrieval import BM25Retriever; from avf.agents.components import build_component_bundle; print('phase2c imports ok')"
```

Suggested branch name:

```text
phase-2c-bm25-retrieval
```

### Phase 2D: Rule-Based Scheduler

Status: complete.

Goal:

Implement the second scheduling factor level.

Outputs:

- rule-based scheduling policy,
- explicit scheduling rules,
- tests comparing sequential and rule-based order decisions,
- trace evidence showing selected scheduling policy.

Acceptance criteria:

- `scheduling_policy=rule_based` maps to the rule-based scheduler,
- `scheduling_policy=sequential` remains unchanged,
- scheduling output is deterministic,
- scheduler decisions are visible in trace payloads,
- scheduler can reorder or prioritise actions according to documented rules without changing task fixtures.

Implementation notes:

- Keep rules simple and explainable.
- Avoid parallel execution in this phase.
- Parallel and DAG scheduling remain future extensions.

Implemented outputs:

- rule-based scheduler implementation in `src/avf/agents/scheduling/rule_based.py`,
- explicit scheduler decision records in `src/avf/agents/scheduling/interface.py`,
- component registry update marking `scheduling_policy=rule_based` as available,
- baseline-run integration using the resolved scheduler from `ComponentConfig`,
- trace evidence showing selected scheduling policy and decision records,
- tests in `tests/test_rule_based_scheduler.py` and `tests/test_phase2a_storage_components.py`.

Phase 2D keeps scheduling separate from memory storage and retrieval ranking. The scheduler only orders planned actions; it does not execute tools or change task fixtures.

Rule priority order:

```text
internal actions
  -> memory.write
  -> memory.query
  -> other tool calls
  -> final_answer
```

Verification:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
env PYTHONPATH=src python3 -m avf run-baseline --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --components test_data/components/A1_B1_C1.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json --artifact-root /private/tmp/avf_phase2d_cli
env PYTHONPATH=src python3 -c "from avf.agents.scheduling import RuleBasedScheduler; from avf.agents.components import build_component_bundle; print('phase2d imports ok')"
```

Suggested branch name:

```text
phase-2d-rule-based-scheduler
```

### Phase 2E: Vector Memory Backend

Status: complete.

Goal:

Implement the second memory factor level.

Outputs:

- vector-backed episodic memory implementation,
- deterministic embedding or embedding-stub strategy,
- vector similarity search,
- tests comparing vector memory behavior with SQLite memory through the same interface.

Acceptance criteria:

- `memory_backend=vector` maps to vector memory,
- vector memory supports the same external memory interface as SQLite memory,
- similarity ranking is deterministic,
- no live embedding API is required,
- vector memory tests do not depend on network access.

Implementation notes:

- Start with deterministic local embeddings or simple numeric features.
- Document limitations if a lightweight local embedding substitute is used.
- Do not introduce a hosted embedding dependency until reproducibility impact is documented.

Implemented outputs:

- vector memory implementation in `src/avf/agents/memory/vector_memory.py`,
- deterministic sparse lexical embedding substitute,
- cosine-similarity ranking with insertion-order tie-breaking,
- component registry update marking `memory_backend=vector` as available,
- mock service compatibility through the shared `MemoryModule` interface,
- tests in `tests/test_vector_memory.py` and `tests/test_phase2a_storage_components.py`.

Phase 2E keeps memory storage separate from retrieval strategy. Vector memory stores and ranks memory records through the memory interface; BM25 retrieval remains the selected retrieval strategy for `retrieval_strategy=bm25`.

Limitations:

- the current vector representation is lexical and deterministic,
- it is not a hosted semantic embedding model,
- semantic embedding retrieval remains Phase 2F.

Verification:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
env PYTHONPATH=src python3 -m avf run-baseline --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --components test_data/components/A1_B1_C1.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json --artifact-root /private/tmp/avf_phase2e_cli
env PYTHONPATH=src python3 -c "from avf.agents.memory import VectorMemory; from avf.agents.components import build_component_bundle; print('phase2e imports ok')"
```

Suggested branch name:

```text
phase-2e-vector-memory-backend
```

### Phase 2F: Embedding Retrieval Strategy

Goal:

Implement the second retrieval factor level.

Outputs:

- embedding-based retrieval implementation,
- deterministic embedding generation or adapter,
- retrieval tests against fixed records,
- trace evidence showing retrieval strategy.

Acceptance criteria:

- `retrieval_strategy=embedding` maps to embedding retrieval,
- embedding retrieval exposes the same interface as BM25 retrieval,
- ranking is deterministic,
- no live API is required by default,
- retrieval tests cover both matching and non-matching cases.

Implementation notes:

- Reuse deterministic embedding utilities from vector memory if appropriate.
- Keep retrieval strategy independent from memory backend selection even when both use vector-like representations.

Suggested branch name:

```text
phase-2f-embedding-retrieval
```

### Phase 2G: Full Component Configuration Fixture Set

Goal:

Create the complete `2^3` component fixture set required for matched experiments.

Outputs:

- eight `ComponentConfig` fixtures,
- fixture validation tests,
- component registry tests across all cells,
- documentation of factor coding.

Acceptance criteria:

- all eight component fixtures validate,
- every fixture resolves to an implemented component bundle,
- fixture IDs use consistent factor naming,
- no task or tool schema changes are required to switch cells.

Suggested branch name:

```text
phase-2g-factorial-component-fixtures
```

### Phase 2H: Component-Aware Baseline Runner

Goal:

Ensure the baseline run pipeline uses component bundles rather than hard-coded baseline components.

Outputs:

- component-aware SUT construction,
- updated baseline runner,
- trace metadata for selected components,
- tests for at least two distinct component cells.

Acceptance criteria:

- `python -m avf run-baseline` uses `ComponentConfig` to select components,
- run artifacts identify selected component variants,
- repeated runs remain reproducible,
- changing component config changes component selection without changing task fixtures.

Suggested branch name:

```text
phase-2h-component-aware-baseline-runner
```

### Phase 2I: Storage and Artifact QA

Goal:

Strengthen artifact validation before moving into full experiment execution.

Outputs:

- result-store integrity checks,
- artifact manifest,
- duplicate run handling policy,
- rerun overwrite or versioning decision,
- storage QA tests.

Acceptance criteria:

- generated artifacts can be validated as a set,
- trace, verification, metrics, and report artifacts agree on `run_id`,
- missing artifacts are reported clearly,
- repeated runs are handled according to a documented policy,
- result-store abstraction remains compatible with the existing filesystem artifacts.

Suggested branch name:

```text
phase-2i-storage-artifact-qa
```

### Phase 2J: Phase 2 Integration Baseline

Goal:

Run a small component-aware integration baseline before Phase 3 full experimental execution.

Outputs:

- integration script,
- at least two component-cell runs,
- artifact manifests,
- comparison summary,
- Phase 2 exit report.

Acceptance criteria:

- at least one Level 1 cell and one Level 2 variant cell run end to end,
- artifacts are generated and validated,
- report explains selected component differences,
- full `2^3` experiment execution is ready for Phase 3.

Suggested branch name:

```text
phase-2j-component-integration-baseline
```

## Phase 2 Data and Artifact Flow

The intended Phase 2 data flow is:

```text
test_data repository
  -> fixture loaders
  -> RunContext
  -> component registry
  -> component bundle
  -> base agent / SUT
  -> mock services
  -> RunTrace
  -> verification
  -> metrics
  -> results store
  -> reports
```

The storage responsibilities should remain separate:

| Storage area | Responsibility |
|---|---|
| Test data repository | versioned tasks, configs, component fixtures, tool specs, perturbation schedules |
| SUT memory backend | internal state used by the agent during a run |
| Results store | traces, verifier outputs, metrics, reports, manifests |
| Dashboard store | later optional read model for UI and analytics |

## Testing Strategy

Phase 2 tests should expand in layers:

- unit tests for storage abstractions,
- unit tests for component registry resolution,
- unit tests for each memory backend,
- unit tests for each retrieval strategy,
- unit tests for each scheduler,
- integration tests for component-aware baseline runs,
- fixture validation tests for all eight component cells,
- reproducibility tests for repeated runs under the same seed,
- negative tests for unsupported or incomplete component configurations.

At minimum, each component variant should have:

- contract-level tests,
- deterministic behavior tests,
- failure-mode tests,
- integration tests through the SUT boundary.

## Trace Requirements

Phase 2 traces should make component attribution visible.

Each run trace or trace payload should allow downstream analysis to identify:

- memory backend,
- retrieval strategy,
- scheduling policy,
- component config ID,
- seed,
- perturbation schedule ID,
- task ID and task version,
- tool schemas used.

This metadata is necessary for dissertation analysis because component effects cannot be estimated reliably if traces do not identify the component cell that produced them.

## Reporting Requirements

Phase 2 reporting remains Markdown and JSON first.

Reports should add:

- selected memory backend,
- selected retrieval strategy,
- selected scheduling policy,
- component config ID,
- tool-call summary,
- verifier outcome,
- metric summary,
- artifact paths.

Dashboard implementation remains deferred until component runs produce enough artifacts to justify a richer UI.

## Containerisation Position

Phase 2 should continue to prioritise local deterministic execution.

Docker may be introduced near the end of Phase 2 or at the start of Phase 3 if it improves reproducibility. It should not drive the component design. The likely later container boundaries remain:

| Container | Role |
|---|---|
| `avf-runner` | orchestration, tracing, verification, metrics, experiment runner |
| `sut-agent` | base agent and component variants |
| `mock-*-mcp` | deterministic mock tool services |
| `results-store` | persisted artifacts or database-backed result read model |
| `dashboard` | reporting UI |

## Exit Criteria for Phase 2

Phase 2 is complete when:

- component interfaces are locked,
- `ComponentConfig` controls actual component selection,
- SQLite memory and vector memory are implemented,
- BM25 and embedding retrieval are implemented,
- sequential and rule-based schedulers are implemented,
- all eight component config fixtures validate,
- at least one component-aware integration baseline runs end to end,
- artifacts remain reproducible under the same task/config/seed/schedule,
- implementation decisions are recorded in `docs/decision-log.md`,
- all tests pass.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Component interfaces drift during variant work | Invalid comparisons | Lock interfaces in Phase 2A |
| SQLite memory becomes confused with results storage | Architectural ambiguity | Document separate storage responsibilities |
| Embedding behavior becomes non-deterministic | Weak reproducibility | Use deterministic local embeddings by default |
| Component variants change task or tool schemas | Confounded experiments | Require task/tool schemas to remain fixed across cells |
| Reports hide component metadata | Weak dissertation evidence | Include component config and selected variants in every report |
| Overbuilding storage too early | Delays experiment implementation | Keep filesystem repository/store defaults until Phase 3 needs more |

## Dissertation Use

This Phase 2 plan supports the dissertation by documenting:

- how the prototype becomes a modular evaluation framework,
- how component-level attribution is protected,
- why filesystem storage remains the first results store,
- where SQLite is introduced as a SUT memory backend rather than a results database,
- how the `2^3` factorial design maps to implementation work,
- how Phase 2 prepares the project for full experimental execution in Phase 3.
