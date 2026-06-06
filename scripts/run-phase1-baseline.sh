#!/usr/bin/env sh
set -eu

ARTIFACT_ROOT="${AVF_ARTIFACT_ROOT:-artifacts}"
PYTHONPATH="${PYTHONPATH:-src}"
export PYTHONPATH

python3 -m avf run-baseline \
  --task test_data/tasks/memory_recall_001.json \
  --config test_data/configs/baseline_seed_001.json \
  --components test_data/components/A1_B1_C1.json \
  --tool-spec test_data/tool_specs/memory.write.json \
  --tool-spec test_data/tool_specs/memory.query.json \
  --artifact-root "$ARTIFACT_ROOT"
