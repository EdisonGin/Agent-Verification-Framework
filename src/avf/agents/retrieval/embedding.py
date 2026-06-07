"""Deterministic embedding-based retrieval implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from avf.agents.embeddings import DeterministicTextEmbedder


@dataclass(frozen=True)
class EmbeddedDocument:
    """Normalised document stored in the embedding retrieval index."""

    document_id: str
    text: str
    metadata: Dict[str, Any]
    source: Dict[str, Any]
    document_index: int
    vector: Dict[str, float]


class EmbeddingRetriever:
    """Rank indexed documents with deterministic local embeddings."""

    def __init__(self, embedder: Optional[DeterministicTextEmbedder] = None) -> None:
        self.embedder = embedder or DeterministicTextEmbedder()
        self._documents: List[EmbeddedDocument] = []

    def index(self, documents: Iterable[Dict[str, Any]]) -> None:
        self._documents = [
            self._normalise_document(document, position)
            for position, document in enumerate(documents)
        ]

    def query(
        self,
        text: str,
        top_k: int,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not isinstance(text, str) or not text:
            raise ValueError("EmbeddingRetriever query text must be a non-empty string")
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            raise ValueError("EmbeddingRetriever top_k must be a positive integer")
        if metadata_filter is not None and not isinstance(metadata_filter, dict):
            raise ValueError("EmbeddingRetriever metadata_filter must be an object")

        query_vector = self.embedder.embed(text)
        if not query_vector or not self._documents:
            return []

        filter_payload = metadata_filter or {}
        scored = []
        for document in self._documents:
            if not self._metadata_matches(document.metadata, filter_payload):
                continue
            score = self._cosine_similarity(query_vector, document.vector)
            if score <= 0:
                continue
            scored.append((score, document))

        scored.sort(key=lambda item: (-item[0], item[1].document_index, item[1].document_id))
        return [
            self._result(rank=rank, score=score, document=document)
            for rank, (score, document) in enumerate(scored[:top_k], start=1)
        ]

    @property
    def document_count(self) -> int:
        return len(self._documents)

    def _normalise_document(self, document: Dict[str, Any], position: int) -> EmbeddedDocument:
        if not isinstance(document, dict):
            raise ValueError("EmbeddingRetriever documents must be objects")

        document_id = document.get("document_id") or document.get("record_id")
        text = document.get("text")
        metadata = document.get("metadata", {})
        source = document.get("source", document)

        if not isinstance(document_id, str) or not document_id:
            raise ValueError("EmbeddingRetriever document_id must be a non-empty string")
        if not isinstance(text, str) or not text:
            raise ValueError("EmbeddingRetriever text must be a non-empty string")
        if not isinstance(metadata, dict):
            raise ValueError("EmbeddingRetriever metadata must be an object")
        if not isinstance(source, dict):
            raise ValueError("EmbeddingRetriever source must be an object")

        return EmbeddedDocument(
            document_id=document_id,
            text=text,
            metadata=dict(metadata),
            source=dict(source),
            document_index=position,
            vector=self.embedder.embed(text),
        )

    def _result(self, rank: int, score: float, document: EmbeddedDocument) -> Dict[str, Any]:
        return {
            "document_id": document.document_id,
            "rank": rank,
            "score": round(score, 12),
            "text": document.text,
            "metadata": dict(document.metadata),
            "source": dict(document.source),
        }

    def _metadata_matches(self, metadata: Dict[str, Any], metadata_filter: Dict[str, Any]) -> bool:
        return all(metadata.get(key) == value for key, value in metadata_filter.items())

    def _cosine_similarity(self, left: Dict[str, float], right: Dict[str, float]) -> float:
        if len(left) > len(right):
            left, right = right, left
        return sum(weight * right.get(token, 0.0) for token, weight in left.items())
