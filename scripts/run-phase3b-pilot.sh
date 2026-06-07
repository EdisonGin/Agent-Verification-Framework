#!/usr/bin/env sh
set -eu

ARTIFACT_ROOT="${AVF_ARTIFACT_ROOT:-artifacts}"
PYTHONPATH="${PYTHONPATH:-src}"
export PYTHONPATH

python3 -m avf run-phase3b-pilot \
  --experiment-config test_data/experiments/phase3_full_factorial_v1.json \
  --artifact-root "$ARTIFACT_ROOT" \
  --operator-notes "Phase 3B pilot QA run using the current local fixture matrix."
