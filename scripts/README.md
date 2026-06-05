# Scripts

This directory is reserved for reproducible project scripts.

Phase 1B/1C currently uses the Python CLI directly:

```text
env PYTHONPATH=src python3 -m avf validate-fixtures --root test_data
python3 -m unittest discover -s tests
```

Later phases will add baseline run, verification, and experiment execution scripts.

