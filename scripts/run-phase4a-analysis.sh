#!/usr/bin/env sh
set -eu

ARTIFACT_ROOT="${AVF_ARTIFACT_ROOT:-artifacts}"
ANALYSIS_ROOT="${AVF_ANALYSIS_ROOT:-$ARTIFACT_ROOT/analysis}"
PYTHONPATH="${PYTHONPATH:-src}"
export PYTHONPATH

AVF_ARTIFACT_ROOT="$ARTIFACT_ROOT" ./scripts/run-phase3d-review.sh >/dev/null

python3 -m avf analyze-dataset \
  --dataset-index "$ARTIFACT_ROOT/experiments/phase3_full_factorial_v1/dataset_index.json" \
  --artifact-root "$ARTIFACT_ROOT" \
  --analysis-root "$ANALYSIS_ROOT" \
  --analysis-id "phase4a_analysis_v1"
