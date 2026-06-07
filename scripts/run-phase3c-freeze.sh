#!/usr/bin/env sh
set -eu

ARTIFACT_ROOT="${AVF_ARTIFACT_ROOT:-artifacts}"
PYTHONPATH="${PYTHONPATH:-src}"
export PYTHONPATH

python3 -m avf run-phase3b-pilot \
  --experiment-config test_data/experiments/phase3_full_factorial_v1.json \
  --artifact-root "$ARTIFACT_ROOT" \
  --operator-notes "Phase 3C prerequisite pilot QA run." >/dev/null

python3 -m avf freeze-phase3c-dataset \
  --experiment-config test_data/experiments/phase3_full_factorial_v1.json \
  --artifact-root "$ARTIFACT_ROOT" \
  --operator-notes "Phase 3C dataset freeze over accepted pilot artifacts."
