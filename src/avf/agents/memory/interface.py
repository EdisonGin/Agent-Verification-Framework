"""Memory module interface for future component variants."""

from __future__ import annotations

from typing import Any, Dict, List, Protocol


class MemoryModule(Protocol):
    """Shared memory interface for SQLite/vector-backed implementations."""

    def write(self, key: str, value: str, metadata: Dict[str, Any]) -> str:
        """Store a memory record and return its record identifier."""

    def read(self, key: str) -> List[Dict[str, Any]]:
        """Read records by structured key."""

    def search(self, query: str, metadata_filter: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """Search memory using the shared read/query contract."""

