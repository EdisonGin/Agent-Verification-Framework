"""Retrieval/search module interface for future component variants."""

from __future__ import annotations

from typing import Any, Dict, List, Protocol


class RetrievalModule(Protocol):
    """Shared retrieval interface for BM25 and embedding-based retrieval."""

    def query(self, text: str, top_k: int) -> List[Dict[str, Any]]:
        """Retrieve ranked documents for the supplied query."""

