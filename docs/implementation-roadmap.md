# Implementation Roadmap

## Purpose

This document defines the staged implementation plan for the automated testing infrastructure used in the dissertation project, "Controlled Component-Level Evaluation of AI Agents via Modular Benchmarking".

The roadmap translates the research proposal and architecture diagram into a software delivery sequence. The emphasis is on building a reproducible, controlled, and auditable evaluation framework rather than an ad hoc testing script.

## Implementation Strategy

The system will be developed using a thin-slice-first approach.

Instead of completing the orchestration layer, mock services layer, verification layer, and reporting layer in isolation, the first implementation goal is a minimal end-to-end pipeline:

```text
task config
  -> orchestrator
  -> base agent / SUT
  -> mock service
  -> base agent observation
  -> trace log
  -> verifier
  -> metrics
  -> report
```

This approach validates the contracts between layers early. Once the first reproducible run works, each layer can be expanded systematically.

## Research Requirements

The implementation must preserve the controlled evaluation protocol described in the project proposal:

- fixed model backbone,
- fixed prompt templates and system instructions,
- fixed task suite and input data,
- fixed tool interfaces and schemas,
- fixed runtime configuration,
- shared seed set,
- pre-generated perturbation schedules,
- complete execution traces,
- matched task-seed-schedule comparisons,
- full factorial component comparison over memory, retrieval, and scheduling variants.

## Base Agent Scope

The System Under Test is the base agent defined in `SUT-base-agent-design.png` and documented in `base-agent-design.md`.

The base agent contains:

- an agent core using a think-plan-act-observe loop,
- a pluggable memory module,
- a pluggable retrieval/search module,
- a pluggable scheduling module,
- an MCP-style tool/action layer,
- telemetry and audit outputs.

Phase 1 implements a minimal deterministic baseline SUT agent. Phase 2 introduces the controlled memory, retrieval, and scheduling variants required for the dissertation's `2^3` factorial design.

## System Phases

### Phase 1: Infrastructure and Baseline Setup

Goal: establish a reproducible benchmark environment with validated schemas, deterministic mock services, trace collection, and one baseline run.

Subphases:

| Subphase | Name | Output |
|---|---|---|
| 1A | Documentation baseline | Roadmap, architecture overview, contracts, phase plan, decision log |
| 1B | Project scaffold | Python package structure, CLI entrypoint, tests, configuration layout |
| 1C | Contracts and schemas | Typed schemas for tasks, runs, tools, traces, verification, and metrics |
| 1D | Minimal orchestrator | Load one task and run one fixed-seed execution |
| 1E | Baseline SUT agent | Minimal think-plan-act-observe loop with stable module interfaces |
| 1F | Minimal mock service | Deterministic mock service with one or more tool endpoints |
| 1G | Trace logging | Complete trace capture for steps, tool calls, observations, errors, and state |
| 1H | Rule-based verification | Deterministic success checks and schema validation |
| 1I | Baseline run | Reproducible run script and first metrics/report artifact |

Milestone M1: reproducible environment capable of fixed-seed and fixed-schedule baseline execution with reliable trace collection.

Deliverable D1: containerised benchmark environment, tool schemas, trace pipeline, and baseline agent run scripts.

The Phase 1 trace pipeline starts with local JSON `RunTrace` artifacts. Streaming systems such as Kafka or Flink are not required for the baseline and should only be introduced later if experiment scale or live dashboard requirements justify the extra infrastructure.

The Phase 1 verification pipeline starts with deterministic rule-based checks against `TaskCase.success_criteria`. LLM-as-judge and consensus verification are later extensions, not prerequisites for the first reproducible baseline.

Phase 1I completes the first local thin slice by producing trace, verification, metric, and Markdown report artifacts from one deterministic baseline run. This validates the full local artifact pipeline before Phase 2 component variants are added.

### Phase 2: Modular Component Integration

Goal: implement interchangeable memory, retrieval, and scheduling components while keeping their interfaces fixed.

Detailed planning for this phase is maintained in `phase-2-infrastructure.md`.

Phase 2A introduces filesystem storage abstractions and a component registry/factory. It does not add a results database dependency. Phase 2B introduces SQLite as a SUT memory backend, not as the experiment results store. Phase 2C introduces BM25 as the first concrete retrieval strategy. Phase 2D introduces rule-based scheduling as the second scheduling factor level. Phase 2E introduces vector memory with deterministic local sparse vectors. Phase 2F introduces embedding retrieval with the same deterministic local embedding utility. Phase 2G adds the complete `2^3` `ComponentConfig` fixture set for the dissertation factor matrix. Phase 2H wires the baseline run pipeline to those resolved component bundles and records selected variants in artifacts. Phase 2I adds artifact-set validation, deterministic manifests, and a documented rerun overwrite policy for the filesystem results store. Phase 2J runs a small integration baseline, writes a comparison summary, and produces a Phase 2 exit report before Phase 3 full-factorial execution.

Required factors and fixture coding:

| Factor | ComponentConfig field | Level 1 | Level 2 |
|---|---|---|---|
| A: memory backend | `memory_backend` | `A1=sqlite` | `A2=vector` |
| B: retrieval strategy | `retrieval_strategy` | `B1=bm25` | `B2=embedding` |
| C: scheduling policy | `scheduling_policy` | `C1=sequential` | `C2=rule_based` |

Additional base-agent variants shown in the SUT diagram, including file/Redis memory, hybrid retrieval, RAG, DAG scheduling, and parallel scheduling, are deferred unless needed as extensions. The dissertation's core experimental design remains the two-level factors above.

Milestone M2: modular architecture with clean component swaps and no interface changes.

Deliverable D2: validated modular implementation of memory, retrieval, and scheduling variants.

### Phase 3: Experimental Execution and Iteration

Goal: run the full factorial experiment and produce a quality-checked trace dataset.

Detailed planning for this phase is maintained in `phase-3-infrastructure.md`.

Phase 3A introduces a versioned `ExperimentConfig`, resolves the current one-task, one-seed, one-schedule, eight-component matrix, runs each row through the component-aware baseline runner, writes the experiment matrix and run index, and produces an `ExperimentResult` comparison summary plus a Markdown full factorial report. It remains filesystem- and artifact-first.

Phase 3B adds the pilot QA gate before dataset freeze. It runs the current matrix in pilot mode, writes `pilot_log.md`, `rerun_records.json`, `failure_notes.json`, `failure_notes.md`, and `pilot_qa_summary.json`, validates rerun/failure-note records, and blocks progression when unresolved infrastructure failures remain.

Phase 3C freezes the accepted artifact set by writing `dataset_index.json`, `frozen_dataset_manifest.json`, and `dataset_report.md`. The dataset index records run metadata, inclusion decisions, artifact paths, and hashes so analysis can consume the frozen dataset without rerunning experiments. Results-index databases and dashboard work remain Phase 3D or Phase 4 responsibilities.

Phase 3D reviews the frozen dataset to decide whether additional indexing or dashboard work is justified. It writes storage volume, query requirement, dashboard requirement, and results-index decision artifacts. The current eight-run dataset remains suitable for direct `dataset_index.json` analysis, so no database or dashboard is implemented before Phase 4.

Required outputs:

- eight component configurations,
- matched task-seed-perturbation cells,
- pilot run logs,
- rerun records,
- failure QA notes,
- frozen trace dataset.

Milestone M3: verified experimental dataset of execution traces and performance metrics.

Deliverable D3: curated execution-trace dataset with pilot logs, rerun records, and quality checks.

### Phase 4: Analysis and Diagnostics

Goal: compute outcome metrics, trajectory diagnostics, and component effect estimates.

Detailed planning for this phase is maintained in `phase-4-analysis.md`.

Phase 4 consumes the frozen Phase 3 dataset through `dataset_index.json` and writes derived analysis artifacts under `artifacts/analysis/<dataset_id>/`. Phase 4A implements a read-only analysis scaffold and normalized metrics table over the frozen artifacts. Phase 4B implements descriptive component effect summaries, matched-block completeness checks, factorial interaction contrasts, and dissertation table fragments over the Phase 4A metrics table. Phase 4C implements trace-derived trajectory diagnostics over stored `RunTrace` artifacts referenced by the metrics table. Phase 4D implements failure taxonomy analysis, QA decision linkage, infrastructure/artifact failure separation, and the dissertation-facing analysis report. Phase 4E implements a derived JSON read model and static dashboard snapshot over the completed Phase 4 analysis package while recording that the current dataset still does not justify a live database or dashboard.

Required metrics:

- task success,
- latency,
- token/cost usage where available,
- goal drift,
- repetition rate,
- recovery steps.

Required analysis:

- pooled component effects,
- task-family-specific contrasts,
- matched/block-aware comparisons,
- confidence intervals or uncertainty estimates,
- failure analysis.

Milestone M4: analysis package with interpretable component effects, validated trajectory diagnostics, and failure analysis.

Deliverable D4: analysis package covering outcome metrics, trajectory diagnostics, effect sizes, interaction estimates where justified, failure taxonomy, QA evidence, dashboard/read-model artifacts, and limitations.

### Phase 5: Dissertation Finalisation

Goal: consolidate the implementation, experiments, analysis, and limitations into the final dissertation.

Required outputs:

- final dissertation text,
- reproducibility instructions,
- archived configs and data,
- final limitations and ethics discussion.

Milestone M5: final dissertation submission.

Deliverable D5: final dissertation document and reproducibility artifacts.

## Future Containerisation Plan

The framework starts as a modular Python package in one repository. The source-code boundaries are:

```text
src/avf/orchestration/
src/avf/mock_services/
src/avf/agents/
src/avf/verification/
src/avf/metrics/
src/avf/reporting/
```

Later Docker deployment should follow these boundaries. The likely containerisation path is:

| Container | Likely contents |
|---|---|
| `avf-runner` | orchestration, contracts, tracing, metrics, experiment runner |
| `sut-agent` | base agent and memory/retrieval/scheduling variants |
| `mock-*-mcp` | deterministic mock MCP/tool servers |
| `results-store` | traces, verifier outputs, metrics, reports, mounted artifacts |
| `dashboard` | reporting UI and failure drill-down views |
| `verifier` | optional heavier verification or LLM-as-judge service |

Containerisation is therefore a later deployment and reproducibility mechanism. It should not be treated as the initial design boundary during Phase 1.

## Acceptance Criteria

The system is considered implementation-ready for experimentation only when the following conditions hold:

- every task is represented by a versioned task schema,
- every run is reproducible from run configuration plus task, seed, and perturbation schedule,
- every tool call is logged with request, response, timing, and error fields,
- every verification result includes evidence and a verifier identifier,
- every metric can be traced back to a specific run trace,
- component variants can be swapped without changing task definitions or tool schemas,
- generated reports are based only on stored traces and result artifacts.

## Dissertation Use

This roadmap supports the dissertation implementation chapter by documenting:

- why the system was built incrementally,
- how the implementation maps to the proposed methodology,
- how reproducibility was protected from the first development phase,
- how the final framework supports component-level attribution.
