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
- Phase 2J: Phase 2 integration baseline.

Next planned phase:

- Phase 3: experimental execution and iteration.

## Documentation

Start with:

- `docs/README.md`
- `docs/implementation-roadmap.md`
- `docs/architecture-overview.md`
- `docs/base-agent-design.md`
- `docs/contracts-and-schemas.md`
- `docs/phase-1-infrastructure.md`
- `docs/phase-2-infrastructure.md`
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

## Package Layout

```text
src/avf/
  contracts/
  orchestration/
  mock_services/
  agents/
  tracing/
  verification/
  metrics/
  reporting/
```

The current implementation intentionally uses standard-library dataclasses and JSON fixtures to keep the initial scaffold dependency-light and reproducible.
