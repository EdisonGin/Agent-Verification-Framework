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

Later phases will add baseline run, verification, and experiment execution scripts.
