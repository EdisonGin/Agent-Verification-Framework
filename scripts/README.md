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
