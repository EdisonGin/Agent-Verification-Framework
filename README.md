# Agent Verification Framework

Controlled component-level evaluation framework for AI agents.

This repository implements the dissertation project **Controlled Component-Level Evaluation of AI Agents via Modular Benchmarking**. The framework is designed to support reproducible evaluation of agent architectures under fixed tasks, fixed tool schemas, fixed seeds, deterministic mock MCP-style services, complete trace logging, and controlled component substitutions.

## Current Status

Implemented:

- Phase 1A: documentation baseline,
- Phase 1B: Python project scaffold,
- Phase 1C: initial contract/schema models, JSON fixtures, validation CLI, and tests,
- Phase 1D: minimal orchestrator and deterministic run-context creation,
- Phase 1E: deterministic baseline SUT agent core.

Next planned phase:

- Phase 1F: minimal mock service.

## Documentation

Start with:

- `docs/README.md`
- `docs/implementation-roadmap.md`
- `docs/architecture-overview.md`
- `docs/base-agent-design.md`
- `docs/contracts-and-schemas.md`
- `docs/phase-1-infrastructure.md`
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
