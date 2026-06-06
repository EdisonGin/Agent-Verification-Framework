"""Internal state model for the Phase 1E baseline SUT agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentState:
    """Mutable state for one deterministic baseline-agent run."""

    run_id: str
    task_id: str
    task_family: str
    input_state: Dict[str, Any]
    current_step: int = 0
    stored_preference: Optional[str] = None
    retrieved_preference: Optional[str] = None
    final_answer: Optional[str] = None
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "task_family": self.task_family,
            "input_state": self.input_state,
            "current_step": self.current_step,
            "stored_preference": self.stored_preference,
            "retrieved_preference": self.retrieved_preference,
            "final_answer": self.final_answer,
            "errors": list(self.errors),
        }

