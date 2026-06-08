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
from .failure_analysis import (
    PHASE4D_ANALYSIS_VERSION,
    Phase4DFailureAnalysisArtifacts,
    Phase4DFailureAnalysisResult,
    write_phase4d_failure_analysis_report,
)
from .dashboard_read_model import (
    PHASE4E_ANALYSIS_VERSION,
    Phase4EReadModelArtifacts,
    Phase4EReadModelResult,
    write_phase4e_dashboard_read_model,
)

__all__ = [
    "PHASE4A_ANALYSIS_VERSION",
    "PHASE4B_ANALYSIS_VERSION",
    "PHASE4C_ANALYSIS_VERSION",
    "PHASE4D_ANALYSIS_VERSION",
    "PHASE4E_ANALYSIS_VERSION",
    "Phase4AAnalysisArtifacts",
    "Phase4AAnalysisResult",
    "Phase4BComponentEffectArtifacts",
    "Phase4BComponentEffectResult",
    "Phase4CTrajectoryDiagnosticArtifacts",
    "Phase4CTrajectoryDiagnosticResult",
    "Phase4DFailureAnalysisArtifacts",
    "Phase4DFailureAnalysisResult",
    "Phase4EReadModelArtifacts",
    "Phase4EReadModelResult",
    "analyze_phase4a_dataset",
    "diagnose_phase4c_trajectories",
    "infer_artifact_root",
    "summarize_phase4b_component_effects",
    "write_phase4d_failure_analysis_report",
    "write_phase4e_dashboard_read_model",
]
