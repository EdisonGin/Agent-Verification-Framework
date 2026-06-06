"""Tool client interface for the SUT agent action layer."""

from __future__ import annotations

from typing import Protocol

from avf.contracts import ToolCall, ToolResult


class ToolClient(Protocol):
    """Protocol implemented by MCP/mock-service clients."""

    def call_tool(self, tool_call: ToolCall) -> ToolResult:
        """Dispatch one tool call and return a structured result."""

