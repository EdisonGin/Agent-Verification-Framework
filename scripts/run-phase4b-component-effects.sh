#!/usr/bin/env sh
set -eu

ARTIFACT_ROOT="${AVF_ARTIFACT_ROOT:-artifacts}"
ANALYSIS_ROOT="${AVF_ANALYSIS_ROOT:-$ARTIFACT_ROOT/analysis}"
PYTHONPATH="${PYTHONPATH:-src}"
export PYTHONPATH

AVF_ARTIFACT_ROOT="$ARTIFACT_ROOT" AVF_ANALYSIS_ROOT="$ANALYSIS_ROOT" ./scripts/run-phase4a-analysis.sh >/dev/null

python3 -m avf summarize-component-effects \
  --metrics-table "$ANALYSIS_ROOT/phase3_full_factorial_v1_dataset_v1/metrics_table.json" \
  --analysis-root "$ANALYSIS_ROOT" \
  --code-version "phase4b_script"
