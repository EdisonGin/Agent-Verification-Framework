# Phase 3 Infrastructure Plan

## Purpose

Phase 3 turns the validated Phase 2 component framework into a controlled experimental execution pipeline.

Phase 2 proved that the framework can execute component-aware runs, select concrete memory/retrieval/scheduling variants through `ComponentConfig`, persist trace/verification/metric/report artifacts, validate artifact sets, write deterministic manifests, and generate a Phase 2 integration baseline. Phase 3 builds on that foundation by running the full matched factorial experiment and producing a quality-controlled trace dataset for dissertation analysis.

The main Phase 3 objective is experimental execution and iteration. The framework must run a complete component matrix under fixed tasks, fixed seeds, fixed perturbation schedules, fixed tool schemas, and fixed verification logic, then preserve enough QA evidence to justify which runs enter the frozen analysis dataset.

## Phase 3 Milestone

Milestone M3:

> Verified experimental dataset of execution traces and performance metrics.

## Phase 3 Deliverable

Deliverable D3:

> Curated execution-trace dataset with pilot logs, rerun records, failure QA notes, artifact manifests, and frozen dataset index.

## Relationship to Phase 2

Phase 2 produced the modular component pipeline:

```text
TaskCase + RunConfig + ComponentConfig + ToolSpec fixtures
  -> RunContext
  -> ComponentRegistry / ComponentBundle
  -> BaselineSUTAgent
  -> MockMemoryService
  -> RunTrace
  -> RuleBasedVerifier
  -> MetricResult
  -> Markdown run report
  -> ArtifactManifest
```

Phase 2J also introduced a small integration baseline:

```text
A1_B1_C1 + A2_B2_C2
  -> per-run artifacts and manifests
  -> ExperimentResult comparison summary
  -> Phase 2 exit report
```

Phase 3 keeps these contracts and expands the execution scope. It should not change task schemas, tool schemas, component schema fields, verifier rules, or metric definitions without explicit documentation because such changes would compromise matched component comparisons.

## Phase 3 Design Principles

1. Experiment configuration is explicit and versioned.
2. Every run belongs to a known task, seed, perturbation schedule, and component cell.
3. The same task/config/tool fixtures are reused across component cells.
4. Pilot runs happen before dataset-producing runs.
5. Failed runs are inspected and documented before rerun or exclusion.
6. Frozen datasets are immutable dissertation evidence.
7. Analysis and dashboard features read from frozen artifacts; they must not mutate raw run outputs.
8. Database/dashboard work begins only when artifact volume or querying needs justify it.

## Experiment Matrix Design

The core Phase 3 matrix is the dissertation's `2^3` component design.

| Factor | ComponentConfig field | Level 1 | Level 2 |
|---|---|---|---|
| A: memory backend | `memory_backend` | `A1=sqlite` | `A2=vector` |
| B: retrieval strategy | `retrieval_strategy` | `B1=bm25` | `B2=embedding` |
| C: scheduling policy | `scheduling_policy` | `C1=sequential` | `C2=rule_based` |

The initial matrix cells are the eight fixtures in `test_data/components/`:

```text
A1_B1_C1
A1_B1_C2
A1_B2_C1
A1_B2_C2
A2_B1_C1
A2_B1_C2
A2_B2_C1
A2_B2_C2
```

The minimal Phase 3 matrix should begin with:

```text
1 task x 1 seed x 1 perturbation schedule x 8 component cells = 8 runs
```

The dissertation-ready matrix should scale to:

```text
N tasks x M seeds x P perturbation schedules x 8 component cells
```

Matched comparison rule:

For a given task, seed, perturbation schedule, run config, and tool schema set, every component cell must be executed before that block is considered complete. This protects component-level attribution by ensuring comparisons are made between like-for-like run contexts.

## Phase 3 Artifact Layout

Phase 3 should keep the Phase 2 artifact-first results store and add experiment-level directories.

Recommended layout:

```text
artifacts/
  traces/
    <run_id>.json
  results/
    <run_id>.rule_based_success_criteria_v1.json
    <run_id>.metrics.json
  reports/
    <run_id>.md
    <experiment_id>_pilot_report.md
    <experiment_id>_dataset_report.md
  manifests/
    <run_id>.manifest.json
  comparisons/
    <experiment_id>.json
  experiments/
    <experiment_id>/
      experiment_config.json
      matrix.json
      run_index.json
      pilot_log.md
      rerun_records.json
      failure_notes.md
      dataset_index.json
      frozen_dataset_manifest.json
```

The existing per-run artifacts remain the source of truth. Experiment-level files are indexes, summaries, and QA evidence over those artifacts.

## Experiment Configuration

Phase 3 should introduce an explicit experiment configuration artifact before running the full matrix.

Recommended fields:

| Field | Purpose |
|---|---|
| `experiment_id` | Stable identifier, for example `phase3_full_factorial_v1` |
| `schema_version` | Experiment config schema version |
| `task_fixtures` | Ordered task fixture paths |
| `run_config_fixtures` | Ordered run config paths or seed-specific configs |
| `component_fixtures` | Ordered list of the eight component cells |
| `tool_spec_fixtures` | Fixed tool schema set |
| `perturbation_schedules` | Explicit perturbation schedule IDs |
| `execution_policy` | Run ordering, retry limits, timeout policy |
| `artifact_root` | Output root |
| `dataset_policy` | Inclusion, exclusion, rerun, and freeze rules |

Phase 3A can start with JSON rather than a new dependency or database.

## Pilot QA

Pilot QA should happen before full experiment execution.

Pilot objectives:

- confirm every component cell can run end to end,
- confirm artifact manifests validate,
- confirm run reports expose component metadata,
- confirm the experiment matrix has the expected number of cells,
- confirm repeated runs remain deterministic under the same inputs,
- identify task or fixture issues before producing dissertation data.

Pilot acceptance criteria:

- all pilot runs complete or have documented failure notes,
- every successful pilot run has trace, verification, metric, report, and manifest artifacts,
- every successful pilot manifest passes validation,
- no task/tool/schema changes are made after the pilot without incrementing fixture versions,
- pilot notes state whether the experiment can proceed to dataset-producing execution.

Pilot log format:

```text
artifacts/experiments/<experiment_id>/pilot_log.md
```

The pilot log should include:

- date/time of execution,
- commit hash,
- experiment config path,
- run count expected vs run count produced,
- validation summary,
- known limitations,
- decision to proceed, rerun, or revise fixtures.

## Rerun Policy

Phase 2I uses deterministic overwrite for identical controlled cells. Phase 3 should keep that default for clean deterministic reruns, but it must also record rerun intent and outcome because experiment execution is now part of dissertation evidence.

Recommended policy:

| Situation | Action |
|---|---|
| Artifact missing due to interrupted run | Rerun same cell and record reason |
| Manifest validation failure | Preserve failure note, rerun after cause is understood |
| Deterministic run produces different artifact hash | Block dataset freeze until investigated |
| Fixture or code change required | Increment experiment config or fixture version and restart affected block |
| External model/API behavior introduced later | Do not overwrite; use versioned rerun records |

Rerun record fields:

| Field | Purpose |
|---|---|
| `rerun_id` | Stable rerun record identifier |
| `original_run_id` | Deterministic run ID for the cell |
| `component_config_id` | Component cell |
| `task_id` | Task |
| `seed` | Seed |
| `perturbation_schedule_id` | Schedule |
| `reason` | Why rerun was needed |
| `decision` | overwrite, exclude, preserve_failed_attempt, or restart_block |
| `operator_notes` | Human QA note |
| `timestamp` | When record was created |
| `commit_hash` | Code version used |

Rerun records should be stored at:

```text
artifacts/experiments/<experiment_id>/rerun_records.json
```

## Failure QA Notes

Failure QA is separate from verification failure.

A run may fail because:

- the SUT did not complete the task,
- artifact validation failed,
- a fixture was invalid,
- a tool call failed,
- a timeout occurred,
- a deterministic assumption was violated.

Failure notes should explain whether the failure is an experimental outcome or an infrastructure problem.

Recommended failure note fields:

| Field | Purpose |
|---|---|
| `run_id` | Affected run |
| `failure_class` | task_failure, verifier_failure, artifact_failure, infrastructure_failure |
| `observed_symptom` | What happened |
| `root_cause` | Known cause or unknown |
| `dataset_decision` | include, exclude, rerun, or block_freeze |
| `evidence_paths` | Trace/report/manifest paths |

Failure notes should be maintained in both human-readable and machine-readable form:

```text
artifacts/experiments/<experiment_id>/failure_notes.md
artifacts/experiments/<experiment_id>/failure_notes.json
```

## Dataset Freeze Process

The dataset freeze converts experiment outputs into dissertation evidence.

Freeze prerequisites:

- experiment matrix is complete,
- every expected run has a run record,
- every included run has valid trace, verification, metric, report, and manifest artifacts,
- every missing or failed run has a QA decision,
- rerun records are complete,
- no unresolved artifact validation failures remain,
- experiment config is archived,
- code commit hash is recorded.

Frozen dataset outputs:

```text
artifacts/experiments/<experiment_id>/dataset_index.json
artifacts/experiments/<experiment_id>/frozen_dataset_manifest.json
artifacts/experiments/<experiment_id>/dataset_report.md
```

The dataset index should include:

- experiment ID,
- code commit hash,
- fixture versions,
- run IDs,
- component config IDs,
- task IDs,
- seeds,
- perturbation schedule IDs,
- artifact paths,
- artifact hashes,
- inclusion/exclusion status.

After freeze:

- raw run artifacts should be treated as read-only,
- analysis should consume the dataset index rather than scanning mutable directories,
- changes require a new experiment ID or explicit amended dataset record.

## Database and Dashboard Timing

Phase 3 should still start artifact-first.

Database work should begin only if at least one of the following becomes true:

- the number of runs makes artifact scanning slow or error-prone,
- rerun records need queryable history,
- the dashboard needs fast filtering across many runs,
- analysis requires repeated joins over run metadata, metrics, and artifact manifests.

Recommended sequence:

| Capability | Recommended timing | Reason |
|---|---|---|
| Filesystem experiment matrix | Phase 3A | Required before running the full factorial |
| Full factorial runner | Phase 3A | Required for dataset generation |
| Pilot QA logs | Phase 3B | Required before dataset freeze |
| Rerun records | Phase 3B | Required for dissertation audit trail |
| Dataset freeze index | Phase 3C | Required before analysis |
| SQLite results index | Phase 3D, if needed | Useful after real run volume exists |
| Dashboard | Phase 4A or late Phase 3D | Useful after frozen artifacts and metrics exist |
| Postgres results store | Later extension | Only needed for multi-user or large-scale deployment |

The dashboard should not be implemented before the experiment dataset exists because it would otherwise be designed around placeholder data. Once Phase 3C freezes a dataset, dashboard requirements can be derived from real analysis questions: component filters, task filters, success/failure views, trace drilldown, manifest validation status, and comparison summaries.

## Subphase Breakdown

### Phase 3A: Experiment Matrix and Full Factorial Runner

Status: complete.

Goal:

Implement the experiment matrix configuration and full factorial runner.

Outputs:

- experiment config schema or structured loader,
- matrix builder over tasks, seeds, schedules, and component configs,
- full factorial runner,
- experiment run index,
- experiment-level `ExperimentResult` summary,
- tests for matrix size, run identity, and artifact generation.

Acceptance criteria:

- all eight component cells are included,
- every matrix row has task, seed, schedule, component config, and tool schema references,
- runner executes the current one-task matrix end to end,
- every run writes trace, verification, metrics, report, and manifest artifacts,
- experiment summary records expected vs completed runs.

Implemented outputs:

- `test_data/experiments/phase3_full_factorial_v1.json` defines the current experiment input set,
- `src/avf/orchestration/experiment_matrix.py` loads `ExperimentConfig`, builds the matrix, and runs all rows,
- `python3 -m avf run-phase3a-experiment` executes the configured matrix,
- `scripts/run-phase3a-experiment.sh` provides the reproducible local entrypoint,
- experiment-level artifacts are written under `artifacts/experiments/<experiment_id>/`,
- comparison summaries are written under `artifacts/comparisons/`,
- the experiment Markdown report is written under `artifacts/reports/`,
- Phase 3A tests cover matrix size, row references, run identity, artifact generation, CLI execution, and script execution.

Verification:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
env PYTHONPATH=src python3 -m avf run-phase3a-experiment --experiment-config test_data/experiments/phase3_full_factorial_v1.json --artifact-root /private/tmp/avf_phase3a_cli
env AVF_ARTIFACT_ROOT=/private/tmp/avf_phase3a_script PYTHONPATH=src ./scripts/run-phase3a-experiment.sh
env PYTHONPATH=src python3 -c "from avf.orchestration import build_experiment_matrix, run_phase3a_full_factorial; print('phase3a experiment imports ok')"
```

Phase 3A remains artifact-first. It does not introduce a results database or dashboard. The database/dashboard decision remains scheduled for Phase 3D or Phase 4A after real experiment artifacts can inform the query and interface requirements.

Suggested branch name:

```text
phase-3a-experiment-matrix-runner
```

### Phase 3B: Pilot QA and Rerun Records

Status: complete.

Goal:

Add the QA process required before generating the final dataset.

Outputs:

- pilot execution mode,
- pilot log artifact,
- rerun record model,
- failure note templates,
- QA validation tests.

Acceptance criteria:

- pilot runs produce a pilot log,
- rerun records can be written and validated,
- failures can be classified as task, verifier, artifact, or infrastructure failures,
- dataset execution is blocked if unresolved infrastructure failures remain.

Implemented outputs:

- `src/avf/orchestration/pilot_qa.py` defines the Phase 3B QA layer,
- `run_phase3b_pilot_qa` runs the Phase 3A matrix in pilot mode and writes QA artifacts,
- `RerunRecord` stores rerun intent, decision, operator notes, timestamp, and commit hash,
- `FailureNote` classifies pilot failures as `task_failure`, `verifier_failure`, `artifact_failure`, or `infrastructure_failure`,
- `failure_note_templates` documents default dataset decisions for each failure class,
- `validate_dataset_execution_gate` blocks dataset execution when unresolved infrastructure failures remain,
- `python3 -m avf run-phase3b-pilot` exposes the pilot workflow through the CLI,
- `scripts/run-phase3b-pilot.sh` provides the reproducible local entrypoint,
- Phase 3B writes `pilot_log.md`, `rerun_records.json`, `failure_notes.json`, `failure_notes.md`, and `pilot_qa_summary.json` under `artifacts/experiments/<experiment_id>/`,
- tests cover pilot artifact generation, rerun record write/read/validation, failure class validation, infrastructure failure blocking, CLI execution, and script execution.

Verification:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
env PYTHONPATH=src python3 -m avf run-phase3b-pilot --experiment-config test_data/experiments/phase3_full_factorial_v1.json --artifact-root /private/tmp/avf_phase3b_cli --operator-notes "Phase 3B CLI verification" --commit-hash phase3b_verify
env AVF_ARTIFACT_ROOT=/private/tmp/avf_phase3b_script PYTHONPATH=src ./scripts/run-phase3b-pilot.sh
env PYTHONPATH=src python3 -c "from avf.orchestration import FailureNote, RerunRecord, run_phase3b_pilot_qa; print('phase3b pilot qa imports ok')"
```

Phase 3B does not freeze the dataset. It records pilot QA evidence and gates later dataset execution. Phase 3C remains responsible for producing the dataset index, frozen dataset manifest, and dataset report.

Suggested branch name:

```text
phase-3b-pilot-qa-rerun-records
```

### Phase 3C: Dataset Freeze

Status: complete.

Goal:

Freeze the accepted experiment dataset for analysis.

Outputs:

- dataset index,
- frozen dataset manifest,
- dataset report,
- inclusion/exclusion summary,
- reproducibility notes.

Acceptance criteria:

- every included run has valid artifacts and hashes,
- excluded runs have documented reasons,
- frozen dataset manifest references the experiment config and commit hash,
- analysis can consume the dataset index without rerunning experiments.

Implemented outputs:

- `src/avf/orchestration/dataset_freeze.py` defines the Phase 3C freeze layer,
- `freeze_phase3c_dataset` reads an existing accepted Phase 3A/3B artifact set and writes the frozen dataset artifacts,
- `freeze-phase3c-dataset` exposes the freeze operation through the CLI,
- `scripts/run-phase3c-freeze.sh` runs the Phase 3B prerequisite pilot and then freezes the accepted artifact set,
- `dataset_index.json` records run metadata, inclusion status, artifact paths, artifact hashes, fixture references, QA summary, commit hash, and freeze timestamp,
- `frozen_dataset_manifest.json` records the dataset ID, experiment ID, commit hash, experiment config reference, freeze prerequisites, source artifact hashes, and freeze artifact hashes,
- `dataset_report.md` provides a human-readable freeze summary and analysis-use note,
- tests cover successful freeze, analysis-ready dataset index contents, unresolved infrastructure failure blocking, CLI execution, and script execution.

Verification:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
env AVF_ARTIFACT_ROOT=/private/tmp/avf_phase3c_script PYTHONPATH=src ./scripts/run-phase3c-freeze.sh
env PYTHONPATH=src python3 -m avf freeze-phase3c-dataset --experiment-config test_data/experiments/phase3_full_factorial_v1.json --artifact-root /private/tmp/avf_phase3c_script --dataset-id phase3c_verify_dataset --frozen-at 2026-06-07T00:00:00Z --commit-hash phase3c_verify
env PYTHONPATH=src python3 -c "from avf.orchestration import freeze_phase3c_dataset, freeze_phase3c_dataset_from_config; print('phase3c dataset freeze imports ok')"
```

Phase 3C does not implement a database or dashboard. The frozen dataset index is the analysis entrypoint until Phase 3D determines whether a separate results index or dashboard is justified.

Suggested branch name:

```text
phase-3c-dataset-freeze
```

### Phase 3D: Results Index and Dashboard Readiness Review

Goal:

Decide whether a lightweight results index or dashboard is justified after real experiment artifacts exist.

Outputs:

- storage volume review,
- query requirements,
- dashboard requirements,
- database decision record,
- optional SQLite results index plan.

Acceptance criteria:

- decision log records whether filesystem artifacts remain sufficient,
- if a database is needed, it is a read-model/index over artifacts rather than a replacement for raw artifacts,
- dashboard scope is based on frozen dataset analysis needs.

Suggested branch name:

```text
phase-3d-results-index-dashboard-review
```

## Phase 3 Exit Criteria

Phase 3 is complete when:

- the full configured experiment matrix has run,
- every run has validated artifacts or documented exclusion,
- pilot logs are complete,
- rerun records are complete,
- failure notes are complete,
- the dataset index is written,
- the frozen dataset manifest is written,
- the dataset report is written,
- the framework can reproduce the dataset from documented configs,
- Phase 4 analysis can start without rerunning Phase 3.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Full factorial matrix grows faster than expected | Execution time increases | Start with one-task matrix, then scale tasks/seeds deliberately |
| Reruns hide real task failures | Invalid dataset | Separate infrastructure failures from task/verifier failures |
| Artifact directories become hard to query | Analysis slows down | Add SQLite read-model only after artifact volume justifies it |
| Dataset changes after analysis begins | Unstable dissertation results | Freeze dataset and require amended dataset IDs for changes |
| Dashboard distracts from experiment completion | Delayed dataset | Defer dashboard until frozen artifacts exist |
| Component comparison becomes confounded by fixture changes | Invalid attribution | Freeze task/tool/run fixtures before full experiment execution |

## Dissertation Use

This Phase 3 plan supports the dissertation by documenting:

- how the validated prototype becomes an experimental dataset generator,
- how the full `2^3` component design is executed,
- how matched comparisons are protected,
- how pilot QA and rerun decisions are recorded,
- how artifact manifests support auditability,
- how the dataset is frozen before analysis,
- why database and dashboard work are deferred until real experiment artifacts justify them.
