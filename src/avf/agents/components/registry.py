"""Phase 2A component registry for controlled SUT module selection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Optional

from avf.agents.scheduling import Scheduler, SequentialScheduler
from avf.contracts import ComponentConfig, ValidationError


@dataclass(frozen=True)
class ComponentDescriptor:
    """Describe one selected component variant and its implementation state."""

    family: str
    variant: str
    implementation_id: str
    status: str
    planned_phase: str
    description: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ComponentBundle:
    """Resolved components for one ComponentConfig cell."""

    config_id: str
    memory: ComponentDescriptor
    retrieval: ComponentDescriptor
    scheduling: ComponentDescriptor
    scheduler: Scheduler

    def to_dict(self) -> Dict[str, object]:
        return {
            "config_id": self.config_id,
            "memory": self.memory.to_dict(),
            "retrieval": self.retrieval.to_dict(),
            "scheduling": self.scheduling.to_dict(),
        }


class ComponentRegistry:
    """Resolve supported ComponentConfig values to component descriptors."""

    def resolve(self, config: ComponentConfig) -> ComponentBundle:
        memory = self._memory(config.memory_backend)
        retrieval = self._retrieval(config.retrieval_strategy)
        scheduling = self._scheduling(config.scheduling_policy)
        return ComponentBundle(
            config_id=config.config_id,
            memory=memory,
            retrieval=retrieval,
            scheduling=scheduling,
            scheduler=SequentialScheduler(),
        )

    def _memory(self, variant: str) -> ComponentDescriptor:
        if variant == "sqlite":
            return ComponentDescriptor(
                family="memory",
                variant="sqlite",
                implementation_id="sqlite_memory_backend",
                status="deferred",
                planned_phase="Phase 2B",
                description="SQLite episodic memory backend selected by ComponentConfig; implementation deferred to Phase 2B.",
            )
        raise self._unsupported("memory_backend", variant, {"vector": "Phase 2E"})

    def _retrieval(self, variant: str) -> ComponentDescriptor:
        if variant == "bm25":
            return ComponentDescriptor(
                family="retrieval",
                variant="bm25",
                implementation_id="bm25_retrieval",
                status="deferred",
                planned_phase="Phase 2C",
                description="BM25 retrieval selected by ComponentConfig; implementation deferred to Phase 2C.",
            )
        raise self._unsupported("retrieval_strategy", variant, {"embedding": "Phase 2F"})

    def _scheduling(self, variant: str) -> ComponentDescriptor:
        if variant == "sequential":
            return ComponentDescriptor(
                family="scheduling",
                variant="sequential",
                implementation_id="sequential_scheduler",
                status="available",
                planned_phase="Phase 1E",
                description="Sequential scheduler is available and preserves planner order.",
            )
        raise self._unsupported("scheduling_policy", variant, {"rule_based": "Phase 2D"})

    def _unsupported(self, field: str, variant: str, planned: Optional[Dict[str, str]] = None) -> ValidationError:
        planned = planned or {}
        planned_phase = planned.get(variant)
        suffix = f"; planned for {planned_phase}" if planned_phase else ""
        return ValidationError(f"Component variant not implemented for {field}={variant}{suffix}")


component_registry = ComponentRegistry()
