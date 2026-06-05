"""Versioned contract models for the automated testing infrastructure.

The implementation intentionally uses standard-library dataclasses. The goal in
Phase 1B/1C is strict, dependency-light validation of JSON fixtures before any
orchestration, agent execution, mock service, verification, or reporting logic
is implemented.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, ClassVar, Dict, Iterable, List, Optional, Type, TypeVar


SCHEMA_VERSION = "1.0"


class ValidationError(ValueError):
    """Raised when a contract payload does not satisfy the documented schema."""


T = TypeVar("T", bound="ContractModel")


def _require_dict(data: Any, model_name: str) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValidationError(f"{model_name} must be an object")
    return data


def _no_extra(data: Dict[str, Any], allowed: Iterable[str], model_name: str) -> None:
    extra = sorted(set(data) - set(allowed))
    if extra:
        raise ValidationError(f"{model_name} has unsupported fields: {', '.join(extra)}")


def _require(data: Dict[str, Any], field: str, model_name: str) -> Any:
    if field not in data:
        raise ValidationError(f"{model_name}.{field} is required")
    return data[field]


def _require_str(data: Dict[str, Any], field: str, model_name: str) -> str:
    value = _require(data, field, model_name)
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{model_name}.{field} must be a non-empty string")
    return value


def _optional_str(data: Dict[str, Any], field: str, model_name: str) -> Optional[str]:
    value = _require(data, field, model_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{model_name}.{field} must be a string or null")
    return value


def _require_int(data: Dict[str, Any], field: str, model_name: str, minimum: Optional[int] = None) -> int:
    value = _require(data, field, model_name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{model_name}.{field} must be an integer")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{model_name}.{field} must be >= {minimum}")
    return value


def _optional_int(data: Dict[str, Any], field: str, model_name: str, minimum: Optional[int] = None) -> Optional[int]:
    value = _require(data, field, model_name)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{model_name}.{field} must be an integer or null")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{model_name}.{field} must be >= {minimum}")
    return value


def _require_number(data: Dict[str, Any], field: str, model_name: str, minimum: Optional[float] = None) -> float:
    value = _require(data, field, model_name)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValidationError(f"{model_name}.{field} must be a number")
    numeric = float(value)
    if minimum is not None and numeric < minimum:
        raise ValidationError(f"{model_name}.{field} must be >= {minimum}")
    return numeric


def _optional_number(data: Dict[str, Any], field: str, model_name: str) -> Optional[float]:
    value = _require(data, field, model_name)
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValidationError(f"{model_name}.{field} must be a number or null")
    return float(value)


def _require_bool(data: Dict[str, Any], field: str, model_name: str) -> bool:
    value = _require(data, field, model_name)
    if not isinstance(value, bool):
        raise ValidationError(f"{model_name}.{field} must be a boolean")
    return value


def _require_object(data: Dict[str, Any], field: str, model_name: str) -> Dict[str, Any]:
    value = _require(data, field, model_name)
    if not isinstance(value, dict):
        raise ValidationError(f"{model_name}.{field} must be an object")
    return value


def _optional_object(data: Dict[str, Any], field: str, model_name: str) -> Optional[Dict[str, Any]]:
    value = _require(data, field, model_name)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValidationError(f"{model_name}.{field} must be an object or null")
    return value


def _require_str_list(data: Dict[str, Any], field: str, model_name: str) -> List[str]:
    value = _require(data, field, model_name)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValidationError(f"{model_name}.{field} must be a list of non-empty strings")
    return list(value)


def _require_object_list(data: Dict[str, Any], field: str, model_name: str) -> List[Dict[str, Any]]:
    value = _require(data, field, model_name)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValidationError(f"{model_name}.{field} must be a list of objects")
    return list(value)


def _require_enum(data: Dict[str, Any], field: str, model_name: str, allowed: Iterable[str]) -> str:
    value = _require_str(data, field, model_name)
    allowed_set = set(allowed)
    if value not in allowed_set:
        raise ValidationError(
            f"{model_name}.{field} must be one of: {', '.join(sorted(allowed_set))}"
        )
    return value


def _require_schema_version(data: Dict[str, Any], model_name: str) -> str:
    version = _require_str(data, "schema_version", model_name)
    if version != SCHEMA_VERSION:
        raise ValidationError(f"{model_name}.schema_version must be {SCHEMA_VERSION}")
    return version


def _coerce_model(model_cls: Type[T], value: Any, field: str, model_name: str) -> T:
    if isinstance(value, model_cls):
        return value
    if isinstance(value, dict):
        return model_cls.from_dict(value)
    raise ValidationError(f"{model_name}.{field} must be a {model_cls.__name__} object")


def _coerce_model_list(model_cls: Type[T], value: Any, field: str, model_name: str) -> List[T]:
    if not isinstance(value, list):
        raise ValidationError(f"{model_name}.{field} must be a list")
    return [_coerce_model(model_cls, item, field, model_name) for item in value]


@dataclass(frozen=True)
class ContractModel:
    """Base model API shared by all contracts."""

    fields: ClassVar[List[str]] = []

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        raise NotImplementedError

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskCase(ContractModel):
    schema_version: str
    task_id: str
    task_version: str
    name: str
    family: str
    description: str
    input_state: Dict[str, Any]
    allowed_tools: List[str]
    success_criteria: Dict[str, Any]
    progress_model: Dict[str, Any]
    max_steps: int

    fields: ClassVar[List[str]] = [
        "schema_version",
        "task_id",
        "task_version",
        "name",
        "family",
        "description",
        "input_state",
        "allowed_tools",
        "success_criteria",
        "progress_model",
        "max_steps",
    ]
    families: ClassVar[List[str]] = ["memory", "retrieval", "recovery"]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskCase":
        data = _require_dict(data, cls.__name__)
        _no_extra(data, cls.fields, cls.__name__)
        return cls(
            schema_version=_require_schema_version(data, cls.__name__),
            task_id=_require_str(data, "task_id", cls.__name__),
            task_version=_require_str(data, "task_version", cls.__name__),
            name=_require_str(data, "name", cls.__name__),
            family=_require_enum(data, "family", cls.__name__, cls.families),
            description=_require_str(data, "description", cls.__name__),
            input_state=_require_object(data, "input_state", cls.__name__),
            allowed_tools=_require_str_list(data, "allowed_tools", cls.__name__),
            success_criteria=_require_object(data, "success_criteria", cls.__name__),
            progress_model=_require_object(data, "progress_model", cls.__name__),
            max_steps=_require_int(data, "max_steps", cls.__name__, minimum=1),
        )


@dataclass(frozen=True)
class RunConfig(ContractModel):
    schema_version: str
    run_config_id: str
    model: Dict[str, Any]
    prompt: Dict[str, Any]
    seed: int
    perturbation_schedule_id: str
    runtime: Dict[str, Any]
    artifacts: Dict[str, Any]

    fields: ClassVar[List[str]] = [
        "schema_version",
        "run_config_id",
        "model",
        "prompt",
        "seed",
        "perturbation_schedule_id",
        "runtime",
        "artifacts",
    ]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunConfig":
        data = _require_dict(data, cls.__name__)
        _no_extra(data, cls.fields, cls.__name__)
        return cls(
            schema_version=_require_schema_version(data, cls.__name__),
            run_config_id=_require_str(data, "run_config_id", cls.__name__),
            model=_require_object(data, "model", cls.__name__),
            prompt=_require_object(data, "prompt", cls.__name__),
            seed=_require_int(data, "seed", cls.__name__, minimum=0),
            perturbation_schedule_id=_require_str(data, "perturbation_schedule_id", cls.__name__),
            runtime=_require_object(data, "runtime", cls.__name__),
            artifacts=_require_object(data, "artifacts", cls.__name__),
        )


@dataclass(frozen=True)
class ComponentConfig(ContractModel):
    schema_version: str
    config_id: str
    memory_backend: str
    retrieval_strategy: str
    scheduling_policy: str

    fields: ClassVar[List[str]] = [
        "schema_version",
        "config_id",
        "memory_backend",
        "retrieval_strategy",
        "scheduling_policy",
    ]
    memory_backends: ClassVar[List[str]] = ["sqlite", "vector"]
    retrieval_strategies: ClassVar[List[str]] = ["bm25", "embedding"]
    scheduling_policies: ClassVar[List[str]] = ["sequential", "rule_based"]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComponentConfig":
        data = _require_dict(data, cls.__name__)
        _no_extra(data, cls.fields, cls.__name__)
        return cls(
            schema_version=_require_schema_version(data, cls.__name__),
            config_id=_require_str(data, "config_id", cls.__name__),
            memory_backend=_require_enum(data, "memory_backend", cls.__name__, cls.memory_backends),
            retrieval_strategy=_require_enum(data, "retrieval_strategy", cls.__name__, cls.retrieval_strategies),
            scheduling_policy=_require_enum(data, "scheduling_policy", cls.__name__, cls.scheduling_policies),
        )


@dataclass(frozen=True)
class AgentRunInput(ContractModel):
    schema_version: str
    run_id: str
    task: TaskCase
    run_config: RunConfig
    component_config: ComponentConfig
    tool_specs: List["ToolSpec"]
    execution_controls: Dict[str, Any]

    fields: ClassVar[List[str]] = [
        "schema_version",
        "run_id",
        "task",
        "run_config",
        "component_config",
        "tool_specs",
        "execution_controls",
    ]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentRunInput":
        data = _require_dict(data, cls.__name__)
        _no_extra(data, cls.fields, cls.__name__)
        return cls(
            schema_version=_require_schema_version(data, cls.__name__),
            run_id=_require_str(data, "run_id", cls.__name__),
            task=_coerce_model(TaskCase, _require(data, "task", cls.__name__), "task", cls.__name__),
            run_config=_coerce_model(RunConfig, _require(data, "run_config", cls.__name__), "run_config", cls.__name__),
            component_config=_coerce_model(
                ComponentConfig,
                _require(data, "component_config", cls.__name__),
                "component_config",
                cls.__name__,
            ),
            tool_specs=_coerce_model_list(ToolSpec, _require(data, "tool_specs", cls.__name__), "tool_specs", cls.__name__),
            execution_controls=_require_object(data, "execution_controls", cls.__name__),
        )


@dataclass(frozen=True)
class AgentAction(ContractModel):
    action_id: str
    run_id: str
    step_index: int
    action_type: str
    name: str
    arguments: Dict[str, Any]
    rationale: Optional[str]

    fields: ClassVar[List[str]] = [
        "action_id",
        "run_id",
        "step_index",
        "action_type",
        "name",
        "arguments",
        "rationale",
    ]
    action_types: ClassVar[List[str]] = ["internal", "tool_call", "final_answer"]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentAction":
        data = _require_dict(data, cls.__name__)
        _no_extra(data, cls.fields, cls.__name__)
        return cls(
            action_id=_require_str(data, "action_id", cls.__name__),
            run_id=_require_str(data, "run_id", cls.__name__),
            step_index=_require_int(data, "step_index", cls.__name__, minimum=0),
            action_type=_require_enum(data, "action_type", cls.__name__, cls.action_types),
            name=_require_str(data, "name", cls.__name__),
            arguments=_require_object(data, "arguments", cls.__name__),
            rationale=_optional_str(data, "rationale", cls.__name__),
        )


@dataclass(frozen=True)
class AgentObservation(ContractModel):
    observation_id: str
    run_id: str
    step_index: int
    source: str
    status: str
    content: Dict[str, Any]
    state_delta: Dict[str, Any]

    fields: ClassVar[List[str]] = [
        "observation_id",
        "run_id",
        "step_index",
        "source",
        "status",
        "content",
        "state_delta",
    ]
    statuses: ClassVar[List[str]] = ["success", "error", "partial"]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentObservation":
        data = _require_dict(data, cls.__name__)
        _no_extra(data, cls.fields, cls.__name__)
        return cls(
            observation_id=_require_str(data, "observation_id", cls.__name__),
            run_id=_require_str(data, "run_id", cls.__name__),
            step_index=_require_int(data, "step_index", cls.__name__, minimum=0),
            source=_require_str(data, "source", cls.__name__),
            status=_require_enum(data, "status", cls.__name__, cls.statuses),
            content=_require_object(data, "content", cls.__name__),
            state_delta=_require_object(data, "state_delta", cls.__name__),
        )


@dataclass(frozen=True)
class AgentOutput(ContractModel):
    schema_version: str
    run_id: str
    status: str
    final_answer: Optional[str]
    artifacts: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    trace_event_ids: List[str]

    fields: ClassVar[List[str]] = [
        "schema_version",
        "run_id",
        "status",
        "final_answer",
        "artifacts",
        "metrics",
        "trace_event_ids",
    ]
    statuses: ClassVar[List[str]] = ["completed", "failed", "timeout"]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentOutput":
        data = _require_dict(data, cls.__name__)
        _no_extra(data, cls.fields, cls.__name__)
        return cls(
            schema_version=_require_schema_version(data, cls.__name__),
            run_id=_require_str(data, "run_id", cls.__name__),
            status=_require_enum(data, "status", cls.__name__, cls.statuses),
            final_answer=_optional_str(data, "final_answer", cls.__name__),
            artifacts=_require_object_list(data, "artifacts", cls.__name__),
            metrics=_require_object(data, "metrics", cls.__name__),
            trace_event_ids=_require_str_list(data, "trace_event_ids", cls.__name__),
        )


@dataclass(frozen=True)
class ToolSpec(ContractModel):
    schema_version: str
    tool_name: str
    tool_schema_version: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    error_model: Dict[str, Any]

    fields: ClassVar[List[str]] = [
        "schema_version",
        "tool_name",
        "tool_schema_version",
        "description",
        "input_schema",
        "output_schema",
        "error_model",
    ]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolSpec":
        data = _require_dict(data, cls.__name__)
        _no_extra(data, cls.fields, cls.__name__)
        return cls(
            schema_version=_require_schema_version(data, cls.__name__),
            tool_name=_require_str(data, "tool_name", cls.__name__),
            tool_schema_version=_require_str(data, "tool_schema_version", cls.__name__),
            description=_require_str(data, "description", cls.__name__),
            input_schema=_require_object(data, "input_schema", cls.__name__),
            output_schema=_require_object(data, "output_schema", cls.__name__),
            error_model=_require_object(data, "error_model", cls.__name__),
        )


@dataclass(frozen=True)
class ToolCall(ContractModel):
    tool_call_id: str
    run_id: str
    step_index: int
    tool_name: str
    arguments: Dict[str, Any]
    requested_at: str

    fields: ClassVar[List[str]] = [
        "tool_call_id",
        "run_id",
        "step_index",
        "tool_name",
        "arguments",
        "requested_at",
    ]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolCall":
        data = _require_dict(data, cls.__name__)
        _no_extra(data, cls.fields, cls.__name__)
        return cls(
            tool_call_id=_require_str(data, "tool_call_id", cls.__name__),
            run_id=_require_str(data, "run_id", cls.__name__),
            step_index=_require_int(data, "step_index", cls.__name__, minimum=0),
            tool_name=_require_str(data, "tool_name", cls.__name__),
            arguments=_require_object(data, "arguments", cls.__name__),
            requested_at=_require_str(data, "requested_at", cls.__name__),
        )


@dataclass(frozen=True)
class ToolResult(ContractModel):
    tool_call_id: str
    status: str
    output: Dict[str, Any]
    error: Optional[Dict[str, Any]]
    latency_ms: int
    perturbation_applied: Optional[Dict[str, Any]]

    fields: ClassVar[List[str]] = [
        "tool_call_id",
        "status",
        "output",
        "error",
        "latency_ms",
        "perturbation_applied",
    ]
    statuses: ClassVar[List[str]] = ["success", "error", "perturbed"]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolResult":
        data = _require_dict(data, cls.__name__)
        _no_extra(data, cls.fields, cls.__name__)
        return cls(
            tool_call_id=_require_str(data, "tool_call_id", cls.__name__),
            status=_require_enum(data, "status", cls.__name__, cls.statuses),
            output=_require_object(data, "output", cls.__name__),
            error=_optional_object(data, "error", cls.__name__),
            latency_ms=_require_int(data, "latency_ms", cls.__name__, minimum=0),
            perturbation_applied=_optional_object(data, "perturbation_applied", cls.__name__),
        )


@dataclass(frozen=True)
class TraceEvent(ContractModel):
    event_id: str
    run_id: str
    event_type: str
    step_index: int
    timestamp: str
    payload: Dict[str, Any]

    fields: ClassVar[List[str]] = [
        "event_id",
        "run_id",
        "event_type",
        "step_index",
        "timestamp",
        "payload",
    ]
    event_types: ClassVar[List[str]] = [
        "agent_step",
        "tool_call",
        "tool_result",
        "observation",
        "state_update",
        "error",
        "recovery",
        "final_answer",
    ]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraceEvent":
        data = _require_dict(data, cls.__name__)
        _no_extra(data, cls.fields, cls.__name__)
        return cls(
            event_id=_require_str(data, "event_id", cls.__name__),
            run_id=_require_str(data, "run_id", cls.__name__),
            event_type=_require_enum(data, "event_type", cls.__name__, cls.event_types),
            step_index=_require_int(data, "step_index", cls.__name__, minimum=0),
            timestamp=_require_str(data, "timestamp", cls.__name__),
            payload=_require_object(data, "payload", cls.__name__),
        )


@dataclass(frozen=True)
class RunTrace(ContractModel):
    schema_version: str
    run_id: str
    task_id: str
    run_config_id: str
    component_config_id: str
    seed: int
    perturbation_schedule_id: str
    started_at: str
    completed_at: Optional[str]
    status: str
    events: List[TraceEvent]

    fields: ClassVar[List[str]] = [
        "schema_version",
        "run_id",
        "task_id",
        "run_config_id",
        "component_config_id",
        "seed",
        "perturbation_schedule_id",
        "started_at",
        "completed_at",
        "status",
        "events",
    ]
    statuses: ClassVar[List[str]] = ["completed", "failed", "timeout"]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunTrace":
        data = _require_dict(data, cls.__name__)
        _no_extra(data, cls.fields, cls.__name__)
        return cls(
            schema_version=_require_schema_version(data, cls.__name__),
            run_id=_require_str(data, "run_id", cls.__name__),
            task_id=_require_str(data, "task_id", cls.__name__),
            run_config_id=_require_str(data, "run_config_id", cls.__name__),
            component_config_id=_require_str(data, "component_config_id", cls.__name__),
            seed=_require_int(data, "seed", cls.__name__, minimum=0),
            perturbation_schedule_id=_require_str(data, "perturbation_schedule_id", cls.__name__),
            started_at=_require_str(data, "started_at", cls.__name__),
            completed_at=_optional_str(data, "completed_at", cls.__name__),
            status=_require_enum(data, "status", cls.__name__, cls.statuses),
            events=_coerce_model_list(TraceEvent, _require(data, "events", cls.__name__), "events", cls.__name__),
        )


@dataclass(frozen=True)
class VerificationResult(ContractModel):
    schema_version: str
    run_id: str
    verifier_id: str
    verifier_type: str
    passed: bool
    score: Optional[float]
    evidence: List[Dict[str, Any]]
    failure_reasons: List[str]

    fields: ClassVar[List[str]] = [
        "schema_version",
        "run_id",
        "verifier_id",
        "verifier_type",
        "passed",
        "score",
        "evidence",
        "failure_reasons",
    ]
    verifier_types: ClassVar[List[str]] = ["rule_based", "llm_judge", "consensus"]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerificationResult":
        data = _require_dict(data, cls.__name__)
        _no_extra(data, cls.fields, cls.__name__)
        return cls(
            schema_version=_require_schema_version(data, cls.__name__),
            run_id=_require_str(data, "run_id", cls.__name__),
            verifier_id=_require_str(data, "verifier_id", cls.__name__),
            verifier_type=_require_enum(data, "verifier_type", cls.__name__, cls.verifier_types),
            passed=_require_bool(data, "passed", cls.__name__),
            score=_optional_number(data, "score", cls.__name__),
            evidence=_require_object_list(data, "evidence", cls.__name__),
            failure_reasons=_require_str_list(data, "failure_reasons", cls.__name__),
        )


@dataclass(frozen=True)
class MetricResult(ContractModel):
    schema_version: str
    run_id: str
    task_success: bool
    latency_ms: int
    step_count: int
    tool_call_count: int
    goal_drift: float
    repetition_rate: float
    recovery_steps: Optional[int]

    fields: ClassVar[List[str]] = [
        "schema_version",
        "run_id",
        "task_success",
        "latency_ms",
        "step_count",
        "tool_call_count",
        "goal_drift",
        "repetition_rate",
        "recovery_steps",
    ]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricResult":
        data = _require_dict(data, cls.__name__)
        _no_extra(data, cls.fields, cls.__name__)
        return cls(
            schema_version=_require_schema_version(data, cls.__name__),
            run_id=_require_str(data, "run_id", cls.__name__),
            task_success=_require_bool(data, "task_success", cls.__name__),
            latency_ms=_require_int(data, "latency_ms", cls.__name__, minimum=0),
            step_count=_require_int(data, "step_count", cls.__name__, minimum=0),
            tool_call_count=_require_int(data, "tool_call_count", cls.__name__, minimum=0),
            goal_drift=_require_number(data, "goal_drift", cls.__name__, minimum=0.0),
            repetition_rate=_require_number(data, "repetition_rate", cls.__name__, minimum=0.0),
            recovery_steps=_optional_int(data, "recovery_steps", cls.__name__, minimum=0),
        )


@dataclass(frozen=True)
class ExperimentResult(ContractModel):
    schema_version: str
    experiment_id: str
    factorial_design: Dict[str, Any]
    run_ids: List[str]
    aggregation: Dict[str, Any]
    analysis_artifacts: Dict[str, Any]

    fields: ClassVar[List[str]] = [
        "schema_version",
        "experiment_id",
        "factorial_design",
        "run_ids",
        "aggregation",
        "analysis_artifacts",
    ]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentResult":
        data = _require_dict(data, cls.__name__)
        _no_extra(data, cls.fields, cls.__name__)
        return cls(
            schema_version=_require_schema_version(data, cls.__name__),
            experiment_id=_require_str(data, "experiment_id", cls.__name__),
            factorial_design=_require_object(data, "factorial_design", cls.__name__),
            run_ids=_require_str_list(data, "run_ids", cls.__name__),
            aggregation=_require_object(data, "aggregation", cls.__name__),
            analysis_artifacts=_require_object(data, "analysis_artifacts", cls.__name__),
        )

