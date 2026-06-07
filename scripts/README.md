# Scripts

This directory is reserved for reproducible project scripts.

Phase 1B/1C currently uses the Python CLI directly:

```text
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
python3 -m unittest discover -s tests
```

Phase 1D adds deterministic run-context creation:

```text
env PYTHONPATH=src python3 -m avf create-run-context --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --components test_data/components/A1_B1_C1.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json
```

Phase 1E validates the baseline SUT agent through the unit test suite:

```text
python3 -m unittest discover -s tests
```

Phase 1F validates the mock memory service through the unit test suite and import check:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -c "from avf.mock_services import MockMemoryService, StaticPerturbationController; print('mock services import ok')"
```

Phase 1G validates trace logging through the unit test suite and import check:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -c "from avf.tracing import TraceWriter, TraceReader, build_run_trace; print('tracing imports ok')"
```

Phase 1H validates rule-based verification through the unit test suite and import check:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -c "from avf.verification import RuleBasedVerifier, VerificationResultWriter; print('verification imports ok')"
```

Once a trace artifact exists, run:

```text
env PYTHONPATH=src python3 -m avf verify-trace --task test_data/tasks/memory_recall_001.json --trace artifacts/traces/<run_id>.json --result-dir artifacts/results
```

Phase 1I adds the first reproducible baseline run script:

```text
./scripts/run-phase1-baseline.sh
```

It writes:

```text
artifacts/traces/<run_id>.json
artifacts/results/<run_id>.rule_based_success_criteria_v1.json
artifacts/results/<run_id>.metrics.json
artifacts/reports/<run_id>.md
artifacts/manifests/<run_id>.manifest.json
```

Use `AVF_ARTIFACT_ROOT` to redirect outputs for reproducibility checks:

```text
env AVF_ARTIFACT_ROOT=/private/tmp/avf_phase1i PYTHONPATH=src ./scripts/run-phase1-baseline.sh
```

Later phases will add component-variant execution and experiment scripts.

Phase 2A validates storage abstractions and component registry resolution through the unit test suite and import check:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -c "from avf.storage import FileSystemTestDataRepository, FileSystemResultsStore; from avf.agents.components import build_component_bundle; print('phase2a imports ok')"
```

Phase 2B validates the SQLite memory backend through the unit test suite, baseline run, and import check:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf run-baseline --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --components test_data/components/A1_B1_C1.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json --artifact-root /private/tmp/avf_phase2b_cli
env PYTHONPATH=src python3 -c "from avf.agents.memory import SQLiteMemory; from avf.agents.components import build_component_bundle; print('phase2b imports ok')"
```

Phase 2C validates the BM25 retrieval strategy through the unit test suite, baseline run, and import check:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf run-baseline --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --components test_data/components/A1_B1_C1.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json --artifact-root /private/tmp/avf_phase2c_cli
env PYTHONPATH=src python3 -c "from avf.agents.retrieval import BM25Retriever; from avf.agents.components import build_component_bundle; print('phase2c imports ok')"
```

Phase 2D validates the rule-based scheduler through the unit test suite, baseline run, and import check:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf run-baseline --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --components test_data/components/A1_B1_C1.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json --artifact-root /private/tmp/avf_phase2d_cli
env PYTHONPATH=src python3 -c "from avf.agents.scheduling import RuleBasedScheduler; from avf.agents.components import build_component_bundle; print('phase2d imports ok')"
```

Phase 2E validates the vector memory backend through the unit test suite, baseline run, and import check:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf run-baseline --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --components test_data/components/A1_B1_C1.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json --artifact-root /private/tmp/avf_phase2e_cli
env PYTHONPATH=src python3 -c "from avf.agents.memory import VectorMemory; from avf.agents.components import build_component_bundle; print('phase2e imports ok')"
```

Phase 2F validates the embedding retrieval strategy through the unit test suite, baseline run, and import check:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf run-baseline --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --components test_data/components/A1_B1_C1.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json --artifact-root /private/tmp/avf_phase2f_cli
env PYTHONPATH=src python3 -c "from avf.agents.retrieval import EmbeddingRetriever; from avf.agents.components import build_component_bundle; print('phase2f imports ok')"
```

Phase 2G validates the complete factorial component fixture set:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
env PYTHONPATH=src python3 -m avf run-baseline --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --components test_data/components/A1_B1_C1.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json --artifact-root /private/tmp/avf_phase2g_cli
env PYTHONPATH=src python3 -c "from pathlib import Path; from avf.storage import FileSystemTestDataRepository; from avf.agents.components import ComponentRegistry; repo = FileSystemTestDataRepository(Path('test_data')); components = repo.load_tree()['components']; registry = ComponentRegistry(); [registry.resolve(component) for component in components]; print(f'validated {len(components)} component fixtures')"
```

Phase 2H validates component-aware baseline execution:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf run-baseline --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --components test_data/components/A1_B1_C1.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json --artifact-root /private/tmp/avf_phase2h_a1
env PYTHONPATH=src python3 -m avf run-baseline --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --components test_data/components/A2_B2_C2.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json --artifact-root /private/tmp/avf_phase2h_a2
env PYTHONPATH=src python3 -c "from avf.orchestration import run_component_aware_baseline; print('phase2h runner import ok')"
```

Phase 2I validates storage and artifact QA:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf run-baseline --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --components test_data/components/A1_B1_C1.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json --artifact-root /private/tmp/avf_phase2i_cli
env PYTHONPATH=src python3 -m avf validate-artifacts --artifact-root /private/tmp/avf_phase2i_cli --run-id run_e4b4e294123506ad --write-manifest
env PYTHONPATH=src python3 -c "from avf.storage import ArtifactManifest, ArtifactValidationResult, FileSystemResultsStore; print('phase2i storage qa import ok')"
```

Phase 2J validates the component-aware integration baseline:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf run-phase2-integration --task test_data/tasks/memory_recall_001.json --config test_data/configs/baseline_seed_001.json --component test_data/components/A1_B1_C1.json --component test_data/components/A2_B2_C2.json --tool-spec test_data/tool_specs/memory.write.json --tool-spec test_data/tool_specs/memory.query.json --artifact-root /private/tmp/avf_phase2j_cli
env AVF_ARTIFACT_ROOT=/private/tmp/avf_phase2j_script PYTHONPATH=src ./scripts/run-phase2-integration.sh
env PYTHONPATH=src python3 -c "from avf.orchestration import run_phase2_integration_baseline; print('phase2j integration import ok')"
```

Phase 3A validates the experiment matrix and full factorial runner:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf run-phase3a-experiment --experiment-config test_data/experiments/phase3_full_factorial_v1.json --artifact-root /private/tmp/avf_phase3a_cli
env AVF_ARTIFACT_ROOT=/private/tmp/avf_phase3a_script PYTHONPATH=src ./scripts/run-phase3a-experiment.sh
env PYTHONPATH=src python3 -c "from avf.orchestration import build_experiment_matrix, run_phase3a_full_factorial; print('phase3a experiment imports ok')"
```

The Phase 3A runner writes the usual per-run trace, verification, metrics, report, and manifest artifacts for all eight component cells. It also writes experiment-level `experiment_config.json`, `matrix.json`, `run_index.json`, `comparisons/<experiment_id>.json`, and `<experiment_id>_full_factorial_report.md` artifacts.

Phase 3B validates pilot QA, rerun records, and failure-note gating:

```text
python3 -m unittest discover -s tests
env PYTHONPATH=src python3 -m avf run-phase3b-pilot --experiment-config test_data/experiments/phase3_full_factorial_v1.json --artifact-root /private/tmp/avf_phase3b_cli --operator-notes "Phase 3B CLI verification" --commit-hash phase3b_verify
env AVF_ARTIFACT_ROOT=/private/tmp/avf_phase3b_script PYTHONPATH=src ./scripts/run-phase3b-pilot.sh
env PYTHONPATH=src python3 -c "from avf.orchestration import FailureNote, RerunRecord, run_phase3b_pilot_qa; print('phase3b pilot qa imports ok')"
```

The Phase 3B pilot writes `pilot_log.md`, `rerun_records.json`, `failure_notes.json`, `failure_notes.md`, and `pilot_qa_summary.json` under `artifacts/experiments/<experiment_id>/`. It also reruns the Phase 3A artifact-producing matrix because the pilot log is evidence over an actual pilot execution, not a static validation-only pass.

Phase 3C validates dataset freeze:

```text
python3 -m unittest discover -s tests
env AVF_ARTIFACT_ROOT=/private/tmp/avf_phase3c_script PYTHONPATH=src ./scripts/run-phase3c-freeze.sh
env PYTHONPATH=src python3 -m avf freeze-phase3c-dataset --experiment-config test_data/experiments/phase3_full_factorial_v1.json --artifact-root /private/tmp/avf_phase3c_script --dataset-id phase3c_verify_dataset --frozen-at 2026-06-07T00:00:00Z --commit-hash phase3c_verify
env PYTHONPATH=src python3 -c "from avf.orchestration import freeze_phase3c_dataset, freeze_phase3c_dataset_from_config; print('phase3c dataset freeze imports ok')"
```

The Phase 3C freeze command reads an accepted Phase 3B artifact set and writes `dataset_index.json`, `frozen_dataset_manifest.json`, and `dataset_report.md` under `artifacts/experiments/<experiment_id>/`. The dataset index is the analysis entrypoint and includes run metadata, inclusion decisions, artifact paths, and SHA-256 hashes.

Phase 3D validates results-index and dashboard readiness review:

```text
python3 -m unittest discover -s tests
env AVF_ARTIFACT_ROOT=/private/tmp/avf_phase3d_script PYTHONPATH=src ./scripts/run-phase3d-review.sh
env PYTHONPATH=src python3 -m avf review-phase3d-readiness --experiment-config test_data/experiments/phase3_full_factorial_v1.json --artifact-root /private/tmp/avf_phase3d_script --operator-notes "Phase 3D CLI verification"
env PYTHONPATH=src python3 -c "from avf.orchestration import run_phase3d_readiness_review, run_phase3d_readiness_review_from_config; print('phase3d readiness review imports ok')"
```

The Phase 3D review writes `storage_volume_review.json`, `query_requirements.json`, `results_index_decision.json`, `dashboard_requirements.md`, and `phase3d_review.md` under `artifacts/experiments/<experiment_id>/`. The current decision keeps the filesystem-backed dataset index as sufficient and defers database/dashboard implementation.
