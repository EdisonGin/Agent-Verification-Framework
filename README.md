# Agent Verification Framework

Controlled component-level evaluation framework for AI agents.

This repository implements the dissertation project **Controlled Component-Level Evaluation of AI Agents via Modular Benchmarking**. The framework is designed to support reproducible evaluation of agent architectures under fixed tasks, fixed tool schemas, fixed seeds, deterministic mock MCP-style services, complete trace logging, and controlled component substitutions.

## Current Status

Implemented:

- Phase 1A: documentation baseline,
- Phase 1B: Python project scaffold,
- Phase 1C: initial contract/schema models, JSON fixtures, validation CLI, and tests,
- Phase 1D: minimal orchestrator and deterministic run-context creation,
- Phase 1E: deterministic baseline SUT agent core,
- Phase 1F: deterministic mock memory service,
- Phase 1G: deterministic trace logging and trace artifact validation,
- Phase 1H: deterministic rule-based verification,
- Phase 1I: first reproducible baseline run with trace, verification, metrics, and Markdown report artifacts,
- Phase 2A: filesystem storage abstractions and component registry/factory,
- Phase 2B: SQLite episodic memory backend,
- Phase 2C: BM25 retrieval strategy,
- Phase 2D: rule-based scheduler,
- Phase 2E: vector memory backend,
- Phase 2F: embedding retrieval strategy,
- Phase 2G: full component configuration fixture set,
- Phase 2H: component-aware baseline runner,
- Phase 2I: storage and artifact QA,
- Phase 2J: Phase 2 integration baseline,
- Phase 3A: experiment matrix and full factorial runner,
- Phase 3B: pilot QA, rerun records, and failure-note templates,
- Phase 3C: dataset freeze index, manifest, and report,
- Phase 3D: results index and dashboard readiness review,
- Phase 4A: artifact-backed analysis scaffold and normalized metrics table,
- Phase 4B: component effect summaries, interaction contrasts, and dissertation table fragments,
- Phase 4C: trace-derived trajectory diagnostics,
- Phase 4D: failure analysis and final analysis report,
- Phase 4E: read-only dashboard/read-model artifacts over the completed Phase 4 analysis package.

Next planned phase:

- Phase 5: dissertation finalisation and optional expanded experiment execution if stronger evidence is required.

## Documentation

Start with:

- `docs/README.md`
- `docs/implementation-roadmap.md`
- `docs/architecture-overview.md`
- `docs/base-agent-design.md`
- `docs/contracts-and-schemas.md`
- `docs/phase-1-infrastructure.md`
- `docs/phase-2-infrastructure.md`
- `docs/phase-3-infrastructure.md`
- `docs/phase-4-analysis.md`
- `docs/decision-log.md`

Source architecture diagrams:

- `docs/automated-testing-infra.png`
- `docs/SUT-base-agent-design.png`

## Validation Commands

Run tests:

```text
python3 -m unittest discover -s tests
```

Validate fixtures:

```text
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
```

Run the Phase 1 baseline:

```text
./scripts/run-phase1-baseline.sh
```

Run the Phase 3A full factorial experiment:

```text
./scripts/run-phase3a-experiment.sh
```

Run the Phase 3B pilot QA workflow:

```text
./scripts/run-phase3b-pilot.sh
```

Run the Phase 3C dataset freeze workflow:

```text
./scripts/run-phase3c-freeze.sh
```

Run the Phase 3D readiness review:

```text
./scripts/run-phase3d-review.sh
```

Run the Phase 4A analysis scaffold:

```text
./scripts/run-phase4a-analysis.sh
```

Run the Phase 4B component effect summaries:

```text
./scripts/run-phase4b-component-effects.sh
```

Run the Phase 4C trajectory diagnostics:

```text
./scripts/run-phase4c-trajectory-diagnostics.sh
```

Run the Phase 4D failure analysis and final report:

```text
./scripts/run-phase4d-analysis-report.sh
```

Run the Phase 4E dashboard/read-model artifact generation:

```text
./scripts/run-phase4e-dashboard-read-model.sh
```

## Package Layout

```text
src/avf/
  contracts/
  orchestration/
  mock_services/
  agents/
  analysis/
  tracing/
  verification/
  metrics/
  reporting/
```

The current implementation intentionally uses standard-library dataclasses and JSON fixtures to keep the initial scaffold dependency-light and reproducible.
