# Documentation Index

This directory contains the project documentation for the automated testing infrastructure.

The documents are structured to support both implementation and dissertation writing. They should be updated as the system evolves.

## Core Documents

| Document | Purpose |
|---|---|
| `implementation-roadmap.md` | Staged implementation plan from Phase 1 to Phase 5 |
| `architecture-overview.md` | Layered architecture mapped to the automated testing infrastructure diagram |
| `base-agent-design.md` | System Under Test base-agent architecture and pluggable module plan |
| `contracts-and-schemas.md` | Initial schema and interface contracts between layers |
| `phase-1-infrastructure.md` | Detailed Phase 1 execution plan and acceptance criteria |
| `phase-2-infrastructure.md` | Detailed Phase 2 modular component and storage plan |
| `phase-3-infrastructure.md` | Detailed Phase 3 experimental execution, QA, and dataset freeze plan |
| `phase-4-analysis.md` | Detailed Phase 4 analysis, diagnostics, component effects, and dashboard timing plan |
| `decision-log.md` | Record of major design and methodology decisions |

## Source Materials

| File | Purpose |
|---|---|
| `IPP-B283223-ipp-final.pdf` | Dissertation project proposal and methodology baseline |
| `automated-testing-infra.png` | Target architecture diagram |
| `SUT-base-agent-design.png` | Base-agent / System Under Test architecture diagram |

## Recommended Reading Order

1. `implementation-roadmap.md`
2. `architecture-overview.md`
3. `base-agent-design.md`
4. `contracts-and-schemas.md`
5. `phase-1-infrastructure.md`
6. `phase-2-infrastructure.md`
7. `phase-3-infrastructure.md`
8. `phase-4-analysis.md`
9. `decision-log.md`

## Dissertation Use

These documents can support the implementation chapter by explaining:

- the staged build plan,
- the rationale for a thin-slice-first approach,
- the architecture and layer responsibilities,
- the contract-first methodology,
- the reproducibility controls used from Phase 1,
- the decisions made to protect controlled component-level evaluation,
- the analysis plan for converting frozen run artifacts into dissertation evidence.
