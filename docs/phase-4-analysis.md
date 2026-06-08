# Phase 4 Analysis and Diagnostics Plan

## Purpose

Phase 4 converts the frozen Phase 3 experiment dataset into dissertation analysis evidence.

Phase 3 produced an artifact-backed execution dataset: component-aware runs, trace artifacts, verification results, metric artifacts, run reports, QA records, a frozen dataset index, and a readiness review. Phase 4 must consume those artifacts without rerunning experiments, compute interpretable component-level summaries, diagnose agent trajectories, and prepare dissertation-ready tables and analysis reports.

The goal is not to build a dashboard first. The goal is to produce a reproducible analysis package that can support the dissertation's results, discussion, and limitations chapters.

## Phase 4 Milestone

Milestone M4:

> Analysis package with interpretable component effects and validated trajectory diagnostics.

## Phase 4 Deliverable

Deliverable D4:

> Analysis report covering outcome metrics, trace-derived diagnostics, component effect summaries, interaction estimates where justified, failure analysis, and reproducibility notes.

## Relationship to Phase 3

Phase 4 starts only after Phase 3C and Phase 3D have completed.

Required Phase 3 inputs:

- `dataset_index.json`,
- `frozen_dataset_manifest.json`,
- `dataset_report.md`,
- `pilot_qa_summary.json`,
- `rerun_records.json`,
- `failure_notes.json`,
- `storage_volume_review.json`,
- `query_requirements.json`,
- `results_index_decision.json`,
- `dashboard_requirements.md`.

The authoritative analysis entrypoint is:

```text
artifacts/experiments/<experiment_id>/dataset_index.json
```

The current Phase 3D decision is that the eight-run frozen dataset is small enough for direct filesystem analysis. Therefore, Phase 4 should begin with a dependency-light artifact reader and analysis writer, not a database or dashboard.

## Phase 4 Design Principles

1. Analysis reads frozen artifacts and never mutates raw run outputs.
2. `dataset_index.json` is the analysis entrypoint; analysis code must not infer the dataset by scanning mutable directories.
3. Every metric, summary, table, and diagnostic must link back to run IDs and artifact paths.
4. Component comparisons must be matched by task, seed, perturbation schedule, run config, and tool schema set.
5. Infrastructure QA failures must be separated from agent task failures.
6. The current one-task, one-seed, one-schedule dataset supports descriptive analysis only.
7. Statistical claims require additional tasks, seeds, or perturbation schedules.
8. Database and dashboard work should start only after analysis queries exceed what the frozen artifact index supports.

## Current Dataset Position

The current frozen dataset contains:

```text
1 task x 1 seed x 1 perturbation schedule x 8 component cells = 8 runs
```

This is sufficient for:

- validating the analysis pipeline,
- producing descriptive component summaries,
- checking the artifact-to-analysis chain,
- testing dissertation table formats,
- identifying whether more experiment blocks are needed.

It is not sufficient for strong inferential claims about general component performance. Before final dissertation analysis, the experiment matrix should be expanded if time and compute budget allow:

```text
N tasks x M seeds x P perturbation schedules x 8 component cells
```

The minimum expansion should prioritise more tasks and seeds before adding new component variants. This preserves the original `2^3` factorial design while improving the reliability of component effect estimates.

## Analysis Inputs

Phase 4 analysis should read the following artifact classes.

| Artifact | Purpose |
|---|---|
| `dataset_index.json` | Frozen run list, inclusion decisions, artifact paths, and hashes |
| `frozen_dataset_manifest.json` | Dataset integrity record and freeze provenance |
| `pilot_qa_summary.json` | Pilot readiness and unresolved failure status |
| `rerun_records.json` | Rerun audit trail |
| `failure_notes.json` | Failure classification and dataset decisions |
| `results_index_decision.json` | Database/dashboard decision evidence |
| `*.metrics.json` | Per-run metric values |
| `*.rule_based_success_criteria_v1.json` | Verification outcomes and evidence |
| `*.json` trace artifacts | Step events, tool calls, observations, and final output |
| `*.manifest.json` | Per-run artifact integrity evidence |
| Markdown reports | Human-readable run and dataset summaries |

## Phase 4 Artifact Layout

Phase 4 should write analysis outputs under a dataset-specific directory:

```text
artifacts/
  analysis/
    <dataset_id>/
      analysis_config.json
      analysis_input_manifest.json
      metrics_table.json
      metrics_table.csv
      metrics_table.md
      component_effects.json
      component_effects.md
      interaction_summary.json
      interaction_summary.md
      trajectory_diagnostics.json
      trajectory_diagnostics.md
      failure_analysis.json
      failure_analysis.md
      dissertation_tables.md
      analysis_report.md
```

The analysis directory is a derived artifact set. It must be reproducible from the frozen dataset and code version, and it must not replace the raw run artifacts.

## Metrics Plan

Phase 4 should distinguish between metrics already stored in Phase 3 artifacts and diagnostics derived during analysis.

| Metric | Source | Phase 4 treatment |
|---|---|---|
| Task success | Verification artifact | Use as primary binary outcome |
| Verification pass/fail | Verification artifact | Report with verifier ID and evidence reference |
| Latency | Metric artifact or trace timing | Use where available; mark missing values explicitly |
| Step count | Trace artifact | Derive from trace events |
| Tool call count | Trace artifact | Derive from `ToolCall` and `ToolResult` events |
| Final answer presence | Agent output and verification evidence | Report as completion diagnostic |
| Goal drift | Trace-derived heuristic | Introduce in Phase 4C with documented rule |
| Repetition rate | Trace-derived heuristic | Introduce in Phase 4C with documented rule |
| Recovery steps | Trace-derived heuristic | Introduce in Phase 4C where perturbations/errors exist |
| Token usage | Not currently guaranteed | Report only when model adapters expose it |
| Cost usage | Not currently guaranteed | Report only when model adapters expose it |

Missing metrics must be represented explicitly rather than silently omitted. For dissertation writing, this avoids implying that token or cost analysis exists before the framework has a real LLM/API adapter that records those values.

## Component Effect Design

The dissertation's core component factors remain:

| Factor | ComponentConfig field | Level 1 | Level 2 |
|---|---|---|---|
| A: memory backend | `memory_backend` | `A1=sqlite` | `A2=vector` |
| B: retrieval strategy | `retrieval_strategy` | `B1=bm25` | `B2=embedding` |
| C: scheduling policy | `scheduling_policy` | `C1=sequential` | `C2=rule_based` |

The basic unit of comparison is a matched block:

```text
task_id + run_config_id + seed + perturbation_schedule_id + tool_schema_set
```

Within each complete matched block, all eight component cells should be present. Component effects should be reported as within-block contrasts where possible.

Recommended summaries:

- A main effect: average outcome difference between `A2` and `A1`,
- B main effect: average outcome difference between `B2` and `B1`,
- C main effect: average outcome difference between `C2` and `C1`,
- two-way interactions: `A:B`, `A:C`, and `B:C`,
- three-way interaction: `A:B:C`, only if the dataset has enough blocks to interpret it responsibly.

For the current eight-run dataset, these summaries should be labelled as descriptive. Confidence intervals or formal uncertainty estimates should be deferred until the dataset contains enough matched blocks.

## Subphase Breakdown

### Phase 4A: Analysis Scaffold and Metrics Table

Status: complete.

Goal:

Create the read-only analysis entrypoint over a frozen dataset.

Outputs:

- analysis config model or structured loader,
- dataset index reader,
- frozen manifest/hash validation helper,
- normalized metrics table,
- JSON, CSV, and Markdown table writers,
- CLI entrypoint for dataset analysis,
- tests using generated Phase 3 artifacts.

Acceptance criteria:

- analysis reads `dataset_index.json` without rerunning experiments,
- included and excluded runs are represented correctly,
- per-run metric, verification, trace, report, and manifest paths are resolved from the dataset index,
- artifact hashes are checked where the dataset index provides them,
- `metrics_table.json`, `metrics_table.csv`, and `metrics_table.md` are written,
- missing metric values are explicit,
- no database or dashboard is introduced.

Suggested branch name:

```text
phase-4a-analysis-scaffold
```

Implemented outputs:

- `src/avf/analysis/dataset_analysis.py` implements the Phase 4A analysis scaffold,
- `analyze_phase4a_dataset` reads a frozen `dataset_index.json` and does not rerun experiments,
- `analysis_config.json` records the analysis ID, dataset ID, artifact root, analysis root, code version, timestamp, and no-rerun policy,
- `analysis_input_manifest.json` records companion Phase 3 artifacts, per-run artifact hash checks, and Phase 4A acceptance criteria,
- `metrics_table.json` records one normalized analysis row per dataset record,
- `metrics_table.csv` provides a tabular export for dissertation analysis,
- `metrics_table.md` provides a compact human-readable metrics table,
- `python3 -m avf analyze-dataset` exposes the analysis workflow through the CLI,
- `scripts/run-phase4a-analysis.sh` runs the Phase 3D prerequisite workflow and then writes Phase 4A analysis artifacts,
- tests cover direct analysis, CLI execution, script execution, and hash-mismatch blocking.

Verification:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
env AVF_ARTIFACT_ROOT=/private/tmp/avf_phase4a_script PYTHONPATH=src ./scripts/run-phase4a-analysis.sh
env PYTHONPATH=src python3 -m avf analyze-dataset --dataset-index /private/tmp/avf_phase4a_script/experiments/phase3_full_factorial_v1/dataset_index.json --artifact-root /private/tmp/avf_phase4a_script --analysis-root /private/tmp/avf_phase4a_script/analysis --generated-at 2026-06-08T00:00:00Z --code-version phase4a_verify
env PYTHONPATH=src python3 -c "from avf.analysis import analyze_phase4a_dataset; print('phase4a analysis import ok')"
```

Phase 4A remains artifact-first. It does not introduce a results database or dashboard. If an artifact hash no longer matches the frozen dataset index, the analysis input manifest is written and the analysis run fails before metrics tables are produced from compromised inputs.

### Phase 4B: Component Effect Summaries

Status: complete.

Goal:

Compute dissertation-ready component summaries over the frozen metrics table.

Outputs:

- factor-level aggregation,
- matched-block completeness checks,
- main-effect summaries,
- interaction summaries where the dataset supports them,
- dissertation table fragments.

Acceptance criteria:

- every summary records the dataset ID and analysis code version,
- all component effects are traceable to run IDs,
- incomplete matched blocks are flagged and excluded from matched contrasts,
- current small-sample outputs are labelled descriptive,
- no inferential confidence interval is reported unless the sample size justifies it,
- `component_effects.md`, `interaction_summary.md`, and `dissertation_tables.md` are written.

Suggested branch name:

```text
phase-4b-component-effect-summaries
```

Implemented outputs:

- `src/avf/analysis/component_effects.py` implements Phase 4B component-effect analysis,
- `summarize_phase4b_component_effects` reads the Phase 4A `metrics_table.json`,
- matched blocks are keyed by task, run config, seed, perturbation schedule, and tool schema set,
- complete blocks require all eight `2^3` component cells,
- incomplete blocks are flagged and excluded from contrasts,
- `component_effects.json` records factor definitions, factor-level summaries, main effects, matched-block coverage, limitations, and acceptance criteria,
- `component_effects.md` provides a human-readable main-effect report,
- `interaction_summary.json` records two-way and three-way factorial interaction contrasts,
- `interaction_summary.md` provides a human-readable interaction report,
- `dissertation_tables.md` provides compact tables for matched-block coverage, primary main effects, and interaction contrasts,
- `python3 -m avf summarize-component-effects` exposes the workflow through the CLI,
- `scripts/run-phase4b-component-effects.sh` runs the Phase 4A prerequisite workflow and then writes Phase 4B outputs,
- tests cover direct summary generation, CLI execution, incomplete-block handling, and script execution.

Verification:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
env AVF_ARTIFACT_ROOT=/private/tmp/avf_phase4b_script PYTHONPATH=src ./scripts/run-phase4b-component-effects.sh
env PYTHONPATH=src python3 -m avf summarize-component-effects --metrics-table /private/tmp/avf_phase4b_script/analysis/phase3_full_factorial_v1_dataset_v1/metrics_table.json --analysis-root /private/tmp/avf_phase4b_script/analysis --generated-at 2026-06-08T00:00:00Z --code-version phase4b_verify
env PYTHONPATH=src python3 -c "from avf.analysis import summarize_phase4b_component_effects; print('phase4b component effects import ok')"
```

Phase 4B remains descriptive for the current dataset. It does not report confidence intervals because the current experiment contains only one complete matched block.

### Phase 4C: Trajectory Diagnostics

Status: planned.

Goal:

Derive trace-level diagnostics that explain how different component cells behave, not only whether they pass.

Outputs:

- step-count diagnostics,
- tool-sequence summaries,
- observation/error summaries,
- repetition-rate heuristic,
- goal-drift heuristic,
- recovery-step heuristic,
- trace drill-down references.

Acceptance criteria:

- every diagnostic is derived from stored `RunTrace` artifacts,
- heuristic definitions are documented before results are reported,
- diagnostic rows link to run IDs and trace paths,
- repeated tool calls and repeated observations are counted deterministically,
- trajectory diagnostics are written in JSON and Markdown,
- diagnostics distinguish agent behavior from infrastructure failures.

Suggested branch name:

```text
phase-4c-trajectory-diagnostics
```

### Phase 4D: Failure Analysis and Final Analysis Report

Status: planned.

Goal:

Produce the dissertation-facing analysis narrative and failure taxonomy summary.

Outputs:

- failure taxonomy summary,
- task/verifier/artifact/infrastructure failure separation,
- run-level evidence references,
- final analysis report,
- dissertation-ready methods/results text fragments.

Acceptance criteria:

- failure analysis consumes `failure_notes.json`, verification artifacts, metric artifacts, and traces,
- infrastructure failures are not counted as ordinary task outcomes unless explicitly justified,
- every exclusion or rerun decision is linked to QA artifacts,
- `failure_analysis.md` and `analysis_report.md` are written,
- the report states dataset limitations and whether results are descriptive or inferential.

Suggested branch name:

```text
phase-4d-failure-analysis-report
```

### Phase 4E: Optional Results Read Model and Dashboard

Status: conditional.

Goal:

Introduce a database or dashboard only if Phase 4 analysis creates a concrete need for repeated querying or interactive review.

Database work should begin if at least one of the following is true:

- the dataset grows beyond the filesystem thresholds documented in Phase 3D,
- repeated joins over runs, metrics, traces, manifests, and failure notes slow down analysis,
- dissertation review requires interactive filtering across many tasks, seeds, or schedules,
- dashboard drill-down would materially improve failure inspection.

If implemented, the database must be a read-only index over frozen artifacts. It must not replace raw artifacts, QA records, the dataset index, or the frozen manifest.

Dashboard work should begin after the analysis table and component summaries exist, because those outputs define the real views needed by the interface.

Candidate dashboard views:

- dataset overview,
- component-cell comparison,
- task and seed filters,
- verification outcome breakdown,
- trajectory diagnostic drill-down,
- failure taxonomy review,
- artifact integrity status.

Acceptance criteria:

- the database/dashboard decision cites `results_index_decision.json` and Phase 4 query needs,
- any database is reproducible from the frozen dataset,
- dashboard views read derived analysis artifacts or the read-only index,
- no dashboard view becomes the source of truth for dissertation results.

Suggested branch name:

```text
phase-4e-analysis-dashboard-read-model
```

## Recommended Implementation Order

1. Implement Phase 4A to prove frozen dataset ingestion and normalized metrics extraction.
2. Implement Phase 4B to compute component effects and dissertation tables.
3. Implement Phase 4C to add trajectory diagnostics from traces.
4. Implement Phase 4D to consolidate failure analysis and the final analysis report.
5. Revisit Phase 4E only if artifact volume or review needs justify a read model or dashboard.

This order keeps analysis reproducible before adding presentation infrastructure.

## Pilot QA for Analysis

Before treating Phase 4 outputs as dissertation evidence, run an analysis QA pass:

- confirm the dataset ID matches the frozen manifest,
- confirm all included run artifacts exist,
- confirm artifact hashes match the dataset index,
- confirm the metrics table has one row per included run,
- confirm factor levels are parsed correctly from component config IDs,
- confirm matched-block completeness is reported,
- confirm missing metrics are visible,
- confirm analysis output can be regenerated byte-for-byte when timestamps are fixed.

The QA result should be recorded in `analysis_report.md` and, if useful, a machine-readable `analysis_input_manifest.json`.

## Testing Strategy

Phase 4 tests should cover:

- loading a frozen dataset index,
- resolving artifact paths from the dataset index,
- validating artifact hashes,
- extracting verification outcomes,
- extracting metric values,
- deriving trace diagnostics,
- detecting incomplete matched blocks,
- writing deterministic JSON, CSV, and Markdown analysis outputs,
- CLI execution over a temporary Phase 3 artifact set.

Suggested verification commands for Phase 4 implementation:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
env PYTHONPATH=src python3 -m avf analyze-dataset --dataset-index artifacts/experiments/<experiment_id>/dataset_index.json --analysis-root artifacts/analysis
```

The exact CLI name can be finalised during Phase 4A.

## Rerun and Dataset Policy During Analysis

Phase 4 should not rerun experiments automatically.

If analysis reveals missing, corrupt, or inconsistent artifacts:

| Situation | Action |
|---|---|
| Missing analysis-derived file | Regenerate Phase 4 outputs from frozen inputs |
| Missing raw run artifact | Stop analysis and record dataset integrity issue |
| Artifact hash mismatch | Stop analysis and require amended dataset review |
| Incomplete matched block | Exclude that block from matched contrasts and report the limitation |
| New task or seed is added | Create a new experiment run and new dataset freeze |
| Code bug in analysis logic | Fix analysis code and regenerate derived artifacts from the same frozen dataset |

Any change to raw experiment artifacts after freeze requires a new dataset ID or an explicit amended dataset record.

## Dissertation Use

Phase 4 supports the dissertation results and discussion chapters by documenting:

- how frozen run artifacts are converted into analysis tables,
- which metrics are available and which are intentionally absent,
- how component effects are estimated under matched comparisons,
- how trajectory diagnostics are derived from traces,
- how task failures are separated from infrastructure failures,
- why the current dataset supports descriptive or inferential claims,
- when database or dashboard infrastructure is justified.

The analysis report should be written so that a reader can trace every claim back to a dataset ID, run ID, component cell, and stored artifact.
