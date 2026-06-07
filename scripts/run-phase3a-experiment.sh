#!/usr/bin/env sh
set -eu

ARTIFACT_ROOT="${AVF_ARTIFACT_ROOT:-artifacts}"
PYTHONPATH="${PYTHONPATH:-src}"
export PYTHONPATH

python3 -m avf run-phase3a-experiment \
  --experiment-config test_data/experiments/phase3_full_factorial_v1.json \
  --artifact-root "$ARTIFACT_ROOT"
