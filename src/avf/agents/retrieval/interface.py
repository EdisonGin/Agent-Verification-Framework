"""Retrieval/search module interface for component variants."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Protocol


class RetrievalModule(Protocol):
    """Shared retrieval interface for BM25 and embedding-based retrieval."""

    def index(self, documents: Iterable[Dict[str, Any]]) -> None:
        """Replace the retriever's indexed document set."""

    def query(
        self,
        text: str,
        top_k: int,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve ranked documents for the supplied query."""
