"""Perturbation hooks for deterministic mock services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from avf.contracts import ToolCall, ToolResult


class PerturbationController(Protocol):
    """Hook that can transform a mock-service result deterministically."""

    def apply(self, tool_call: ToolCall, result: ToolResult) -> ToolResult:
        """Return the original result or a deterministic perturbed result."""


class NoPerturbationController:
    """Default perturbation hook used by Phase 1F baseline tests."""

    def apply(self, tool_call: ToolCall, result: ToolResult) -> ToolResult:
        return result


@dataclass(frozen=True)
class StaticPerturbationController:
    """Deterministically perturb calls to one tool.

    This is intentionally small: it provides the hook required by Phase 1F
    without implementing full perturbation schedules. Schedule loading and
    replay can build on this interface in later phases.
    """

    tool_name: str
    kind: str = "temporary_unavailability"
    message: str = "Tool temporarily unavailable under fixed perturbation."
    latency_ms: int = 0

    def apply(self, tool_call: ToolCall, result: ToolResult) -> ToolResult:
        if tool_call.tool_name != self.tool_name:
            return result
        return ToolResult(
            tool_call_id=tool_call.tool_call_id,
            status="perturbed",
            output={},
            error={"type": self.kind, "message": self.message},
            latency_ms=self.latency_ms,
            perturbation_applied={
                "kind": self.kind,
                "tool_name": self.tool_name,
            },
        )

