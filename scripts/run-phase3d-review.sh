#!/usr/bin/env sh
set -eu

ARTIFACT_ROOT="${AVF_ARTIFACT_ROOT:-artifacts}"
PYTHONPATH="${PYTHONPATH:-src}"
export PYTHONPATH

AVF_ARTIFACT_ROOT="$ARTIFACT_ROOT" ./scripts/run-phase3c-freeze.sh >/dev/null

python3 -m avf review-phase3d-readiness \
  --experiment-config test_data/experiments/phase3_full_factorial_v1.json \
  --artifact-root "$ARTIFACT_ROOT" \
  --operator-notes "Phase 3D review over frozen dataset artifacts."
