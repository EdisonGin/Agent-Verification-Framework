"""Deterministic vector-backed episodic memory implementation."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class VectorMemoryRecord:
    """Stored memory record with a deterministic sparse vector."""

    record_index: int
    record_id: str
    key: str
    value: str
    metadata: Dict[str, Any]
    vector: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "key": self.key,
            "value": self.value,
            "metadata": dict(self.metadata),
        }


class DeterministicTextEmbedder:
    """Create reproducible sparse lexical vectors without external embedding APIs."""

    def embed(self, text: str) -> Dict[str, float]:
        if not isinstance(text, str) or not text:
            raise ValueError("DeterministicTextEmbedder text must be a non-empty string")

        counts = Counter(TOKEN_PATTERN.findall(text.lower()))
        if not counts:
            return {}

        norm = math.sqrt(sum(count * count for count in counts.values()))
        if norm == 0:
            return {}
        return {token: count / norm for token, count in sorted(counts.items())}


class VectorMemory:
    """Store records in memory and rank searches with deterministic cosine similarity."""

    def __init__(self, embedder: Optional[DeterministicTextEmbedder] = None) -> None:
        self.embedder = embedder or DeterministicTextEmbedder()
        self._records: List[VectorMemoryRecord] = []

    def write(self, key: str, value: str, metadata: Dict[str, Any]) -> str:
        self._validate_key(key)
        if not isinstance(value, str):
            raise ValueError("VectorMemory.write value must be a string")
        if not isinstance(metadata, dict):
            raise ValueError("VectorMemory.write metadata must be an object")

        record_index = len(self._records) + 1
        record_id = f"mem_{record_index:03d}"
        record = VectorMemoryRecord(
            record_index=record_index,
            record_id=record_id,
            key=key,
            value=value,
            metadata=dict(metadata),
            vector=self.embedder.embed(self._record_text(key, value)),
        )
        self._records.append(record)
        return record_id

    def read(self, key: str) -> List[Dict[str, Any]]:
        self._validate_key(key)
        return [record.to_dict() for record in self._records if record.key == key]

    def search(self, query: str, metadata_filter: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        self._validate_key(query)
        if not isinstance(metadata_filter, dict):
            raise ValueError("VectorMemory.search metadata_filter must be an object")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ValueError("VectorMemory.search limit must be a positive integer")

        query_vector = self.embedder.embed(query)
        if not query_vector:
            return []

        scored = []
        for record in self._records:
            if not self._metadata_matches(record.metadata, metadata_filter):
                continue
            score = self._cosine_similarity(query_vector, record.vector)
            if score <= 0:
                continue
            scored.append((score, record))

        scored.sort(key=lambda item: (-item[0], item[1].record_index, item[1].record_id))
        return [record.to_dict() for _score, record in scored[:limit]]

    def _record_text(self, key: str, value: str) -> str:
        return f"{key} {value}"

    def _cosine_similarity(self, left: Dict[str, float], right: Dict[str, float]) -> float:
        if len(left) > len(right):
            left, right = right, left
        return sum(weight * right.get(token, 0.0) for token, weight in left.items())

    def _metadata_matches(self, metadata: Dict[str, Any], metadata_filter: Dict[str, Any]) -> bool:
        return all(metadata.get(key) == value for key, value in metadata_filter.items())

    def _validate_key(self, key: str) -> None:
        if not isinstance(key, str) or not key:
            raise ValueError("VectorMemory key/query must be a non-empty string")
