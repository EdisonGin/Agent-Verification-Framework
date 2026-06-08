"""Post-freeze analysis layer."""

from .dataset_analysis import (
    PHASE4A_ANALYSIS_VERSION,
    Phase4AAnalysisArtifacts,
    Phase4AAnalysisResult,
    analyze_phase4a_dataset,
    infer_artifact_root,
)
from .component_effects import (
    PHASE4B_ANALYSIS_VERSION,
    Phase4BComponentEffectArtifacts,
    Phase4BComponentEffectResult,
    summarize_phase4b_component_effects,
)
from .trajectory_diagnostics import (
    PHASE4C_ANALYSIS_VERSION,
    Phase4CTrajectoryDiagnosticArtifacts,
    Phase4CTrajectoryDiagnosticResult,
    diagnose_phase4c_trajectories,
)

__all__ = [
    "PHASE4A_ANALYSIS_VERSION",
    "PHASE4B_ANALYSIS_VERSION",
    "PHASE4C_ANALYSIS_VERSION",
    "Phase4AAnalysisArtifacts",
    "Phase4AAnalysisResult",
    "Phase4BComponentEffectArtifacts",
    "Phase4BComponentEffectResult",
    "Phase4CTrajectoryDiagnosticArtifacts",
    "Phase4CTrajectoryDiagnosticResult",
    "analyze_phase4a_dataset",
    "diagnose_phase4c_trajectories",
    "infer_artifact_root",
    "summarize_phase4b_component_effects",
]
