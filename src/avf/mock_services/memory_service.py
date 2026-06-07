"""Deterministic mock memory service with optional memory-backend delegation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from avf.agents.memory import MemoryModule
from avf.agents.tools import ToolClient
from avf.contracts import ToolCall, ToolResult

from .perturbations import NoPerturbationController, PerturbationController


@dataclass(frozen=True)
class MemoryRecord:
    """Stored mock memory record."""

    record_id: str
    key: str
    value: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MockMemoryService(ToolClient):
    """Tool service implementing memory.write and memory.query."""

    supported_tools = {"memory.write", "memory.query"}

    def __init__(
        self,
        perturbations: Optional[PerturbationController] = None,
        memory_backend: Optional[MemoryModule] = None,
    ) -> None:
        self.perturbations = perturbations or NoPerturbationController()
        self.memory_backend = memory_backend
        self._records: List[MemoryRecord] = []
        self.calls: List[ToolCall] = []

    @property
    def records(self) -> List[MemoryRecord]:
        return list(self._records)

    def call_tool(self, tool_call: ToolCall) -> ToolResult:
        self.calls.append(tool_call)

        if tool_call.tool_name == "memory.write":
            result = self._write(tool_call)
        elif tool_call.tool_name == "memory.query":
            result = self._query(tool_call)
        else:
            result = self._error_result(
                tool_call=tool_call,
                error_type="unsupported_tool",
                message=f"Unsupported tool: {tool_call.tool_name}",
            )

        return self.perturbations.apply(tool_call, result)

    def _write(self, tool_call: ToolCall) -> ToolResult:
        key = tool_call.arguments.get("key")
        value = tool_call.arguments.get("value")
        metadata = tool_call.arguments.get("metadata", {})

        if not isinstance(key, str) or not key:
            return self._error_result(tool_call, "invalid_arguments", "memory.write requires a non-empty string key")
        if not isinstance(value, str):
            return self._error_result(tool_call, "invalid_arguments", "memory.write requires a string value")
        if not isinstance(metadata, dict):
            return self._error_result(tool_call, "invalid_arguments", "memory.write metadata must be an object")

        if self.memory_backend is not None:
            try:
                record_id = self.memory_backend.write(key, value, dict(metadata))
            except ValueError as exc:
                return self._error_result(tool_call, "invalid_arguments", str(exc))
            return ToolResult(
                tool_call_id=tool_call.tool_call_id,
                status="success",
                output={"ok": True, "record_id": record_id},
                error=None,
                latency_ms=0,
                perturbation_applied=None,
            )

        record = MemoryRecord(
            record_id=f"mem_{len(self._records) + 1:03d}",
            key=key,
            value=value,
            metadata=dict(metadata),
        )
        self._records.append(record)
        return ToolResult(
            tool_call_id=tool_call.tool_call_id,
            status="success",
            output={"ok": True, "record_id": record.record_id},
            error=None,
            latency_ms=0,
            perturbation_applied=None,
        )

    def _query(self, tool_call: ToolCall) -> ToolResult:
        query = tool_call.arguments.get("query")
        metadata_filter = tool_call.arguments.get("metadata_filter", {})
        limit = tool_call.arguments.get("limit", len(self._records) or 1)

        if not isinstance(query, str) or not query:
            return self._error_result(tool_call, "invalid_arguments", "memory.query requires a non-empty string query")
        if not isinstance(metadata_filter, dict):
            return self._error_result(tool_call, "invalid_arguments", "memory.query metadata_filter must be an object")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            return self._error_result(tool_call, "invalid_arguments", "memory.query limit must be a positive integer")

        if self.memory_backend is not None:
            try:
                records = self.memory_backend.search(query, metadata_filter, limit)
            except ValueError as exc:
                return self._error_result(tool_call, "invalid_arguments", str(exc))
            return ToolResult(
                tool_call_id=tool_call.tool_call_id,
                status="success",
                output={"ok": True, "records": records},
                error=None,
                latency_ms=0,
                perturbation_applied=None,
            )

        matches = [
            record
            for record in self._records
            if record.key == query and self._metadata_matches(record.metadata, metadata_filter)
        ][:limit]
        return ToolResult(
            tool_call_id=tool_call.tool_call_id,
            status="success",
            output={"ok": True, "records": [record.to_dict() for record in matches]},
            error=None,
            latency_ms=0,
            perturbation_applied=None,
        )

    def _metadata_matches(self, metadata: Dict[str, Any], metadata_filter: Dict[str, Any]) -> bool:
        return all(metadata.get(key) == value for key, value in metadata_filter.items())

    def _error_result(self, tool_call: ToolCall, error_type: str, message: str) -> ToolResult:
        return ToolResult(
            tool_call_id=tool_call.tool_call_id,
            status="error",
            output={},
            error={"type": error_type, "message": message},
            latency_ms=0,
            perturbation_applied=None,
        )
