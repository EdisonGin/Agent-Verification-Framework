"""Component registry for controlled SUT module selection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Optional

from avf.agents.memory import MemoryModule, SQLiteMemory, VectorMemory
from avf.agents.retrieval import BM25Retriever, EmbeddingRetriever, RetrievalModule
from avf.agents.scheduling import RuleBasedScheduler, Scheduler, SequentialScheduler
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
    memory_module: Optional[MemoryModule] = None
    retrieval_module: Optional[RetrievalModule] = None

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
            scheduler=self._scheduler(config.scheduling_policy),
            memory_module=self._memory_module(config.memory_backend),
            retrieval_module=self._retrieval_module(config.retrieval_strategy),
        )

    def _memory(self, variant: str) -> ComponentDescriptor:
        if variant == "sqlite":
            return ComponentDescriptor(
                family="memory",
                variant="sqlite",
                implementation_id="sqlite_memory_backend",
                status="available",
                planned_phase="Phase 2B",
                description=(
                    "SQLite episodic memory backend selected by ComponentConfig "
                    "and available through the memory interface."
                ),
            )
        if variant == "vector":
            return ComponentDescriptor(
                family="memory",
                variant="vector",
                implementation_id="vector_memory_backend",
                status="available",
                planned_phase="Phase 2E",
                description=(
                    "Vector-backed episodic memory selected by ComponentConfig "
                    "and available through the memory interface."
                ),
            )
        raise self._unsupported("memory_backend", variant)

    def _memory_module(self, variant: str) -> MemoryModule:
        if variant == "sqlite":
            return SQLiteMemory()
        if variant == "vector":
            return VectorMemory()
        raise self._unsupported("memory_backend", variant)

    def _retrieval(self, variant: str) -> ComponentDescriptor:
        if variant == "bm25":
            return ComponentDescriptor(
                family="retrieval",
                variant="bm25",
                implementation_id="bm25_retrieval",
                status="available",
                planned_phase="Phase 2C",
                description=(
                    "BM25 retrieval selected by ComponentConfig "
                    "and available through the retrieval interface."
                ),
            )
        if variant == "embedding":
            return ComponentDescriptor(
                family="retrieval",
                variant="embedding",
                implementation_id="embedding_retrieval",
                status="available",
                planned_phase="Phase 2F",
                description=(
                    "Embedding retrieval selected by ComponentConfig "
                    "and available through the retrieval interface."
                ),
            )
        raise self._unsupported("retrieval_strategy", variant)

    def _retrieval_module(self, variant: str) -> RetrievalModule:
        if variant == "bm25":
            return BM25Retriever()
        if variant == "embedding":
            return EmbeddingRetriever()
        raise self._unsupported("retrieval_strategy", variant)

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
        if variant == "rule_based":
            return ComponentDescriptor(
                family="scheduling",
                variant="rule_based",
                implementation_id="rule_based_scheduler",
                status="available",
                planned_phase="Phase 2D",
                description=(
                    "Rule-based scheduler selected by ComponentConfig "
                    "and available through the scheduler interface."
                ),
            )
        raise self._unsupported("scheduling_policy", variant)

    def _scheduler(self, variant: str) -> Scheduler:
        if variant == "sequential":
            return SequentialScheduler()
        if variant == "rule_based":
            return RuleBasedScheduler()
        raise self._unsupported("scheduling_policy", variant, {"rule_based": "Phase 2D"})

    def _unsupported(self, field: str, variant: str, planned: Optional[Dict[str, str]] = None) -> ValidationError:
        planned = planned or {}
        planned_phase = planned.get(variant)
        suffix = f"; planned for {planned_phase}" if planned_phase else ""
        return ValidationError(f"Component variant not implemented for {field}={variant}{suffix}")


component_registry = ComponentRegistry()
