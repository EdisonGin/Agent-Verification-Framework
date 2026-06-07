#!/usr/bin/env sh
set -eu

ARTIFACT_ROOT="${AVF_ARTIFACT_ROOT:-artifacts}"
PYTHONPATH="${PYTHONPATH:-src}"
export PYTHONPATH

python3 -m avf run-phase2-integration \
  --task test_data/tasks/memory_recall_001.json \
  --config test_data/configs/baseline_seed_001.json \
  --component test_data/components/A1_B1_C1.json \
  --component test_data/components/A2_B2_C2.json \
  --tool-spec test_data/tool_specs/memory.write.json \
  --tool-spec test_data/tool_specs/memory.query.json \
  --artifact-root "$ARTIFACT_ROOT"
