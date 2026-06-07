"""Dependency-light BM25 retrieval implementation."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class IndexedDocument:
    """Normalised document stored inside the BM25 index."""

    document_id: str
    text: str
    metadata: Dict[str, Any]
    source: Dict[str, Any]
    document_index: int
    term_counts: Counter[str]
    length: int


class BM25Retriever:
    """Rank indexed documents using Okapi BM25 with deterministic tie-breaking."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        if k1 <= 0:
            raise ValueError("BM25Retriever k1 must be positive")
        if b < 0 or b > 1:
            raise ValueError("BM25Retriever b must be between 0 and 1")
        self.k1 = k1
        self.b = b
        self._documents: List[IndexedDocument] = []
        self._document_frequencies: Dict[str, int] = {}
        self._average_document_length = 0.0

    def index(self, documents: Iterable[Dict[str, Any]]) -> None:
        indexed: List[IndexedDocument] = []
        for position, document in enumerate(documents):
            indexed.append(self._normalise_document(document, position))

        document_frequencies: Dict[str, int] = {}
        for document in indexed:
            for term in document.term_counts:
                document_frequencies[term] = document_frequencies.get(term, 0) + 1

        self._documents = indexed
        self._document_frequencies = document_frequencies
        if indexed:
            self._average_document_length = sum(document.length for document in indexed) / len(indexed)
        else:
            self._average_document_length = 0.0

    def query(
        self,
        text: str,
        top_k: int,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not isinstance(text, str) or not text:
            raise ValueError("BM25Retriever query text must be a non-empty string")
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            raise ValueError("BM25Retriever top_k must be a positive integer")
        if metadata_filter is not None and not isinstance(metadata_filter, dict):
            raise ValueError("BM25Retriever metadata_filter must be an object")

        query_terms = self._tokenize(text)
        if not query_terms or not self._documents:
            return []

        filter_payload = metadata_filter or {}
        scored = []
        for document in self._documents:
            if not self._metadata_matches(document.metadata, filter_payload):
                continue
            score = self._score_document(query_terms, document)
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

    def _normalise_document(self, document: Dict[str, Any], position: int) -> IndexedDocument:
        if not isinstance(document, dict):
            raise ValueError("BM25Retriever documents must be objects")

        document_id = document.get("document_id") or document.get("record_id")
        text = document.get("text")
        metadata = document.get("metadata", {})
        source = document.get("source", document)

        if not isinstance(document_id, str) or not document_id:
            raise ValueError("BM25Retriever document_id must be a non-empty string")
        if not isinstance(text, str) or not text:
            raise ValueError("BM25Retriever text must be a non-empty string")
        if not isinstance(metadata, dict):
            raise ValueError("BM25Retriever metadata must be an object")
        if not isinstance(source, dict):
            raise ValueError("BM25Retriever source must be an object")

        tokens = self._tokenize(text)
        return IndexedDocument(
            document_id=document_id,
            text=text,
            metadata=dict(metadata),
            source=dict(source),
            document_index=position,
            term_counts=Counter(tokens),
            length=len(tokens),
        )

    def _score_document(self, query_terms: List[str], document: IndexedDocument) -> float:
        if document.length == 0 or self._average_document_length == 0:
            return 0.0

        score = 0.0
        document_total = len(self._documents)
        for term in query_terms:
            term_frequency = document.term_counts.get(term, 0)
            if term_frequency == 0:
                continue

            document_frequency = self._document_frequencies.get(term, 0)
            idf = math.log(1 + (document_total - document_frequency + 0.5) / (document_frequency + 0.5))
            denominator = term_frequency + self.k1 * (
                1 - self.b + self.b * (document.length / self._average_document_length)
            )
            score += idf * ((term_frequency * (self.k1 + 1)) / denominator)
        return score

    def _result(self, rank: int, score: float, document: IndexedDocument) -> Dict[str, Any]:
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

    def _tokenize(self, text: str) -> List[str]:
        return TOKEN_PATTERN.findall(text.lower())
