"""SQLite-backed episodic memory implementation."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


class SQLiteMemory:
    """Persist episodic memory records through the standard-library sqlite3 module."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else None
        if self.db_path is not None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            database = str(self.db_path)
        else:
            database = ":memory:"
        self._connection = sqlite3.connect(database)
        self._connection.row_factory = sqlite3.Row
        self._ensure_schema()

    def write(self, key: str, value: str, metadata: Dict[str, Any]) -> str:
        self._validate_key(key)
        if not isinstance(value, str):
            raise ValueError("SQLiteMemory.write value must be a string")
        if not isinstance(metadata, dict):
            raise ValueError("SQLiteMemory.write metadata must be an object")

        record_index = self._next_record_index()
        record_id = f"mem_{record_index:03d}"
        self._connection.execute(
            """
            INSERT INTO memory_records (record_index, record_id, key, value, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (record_index, record_id, key, value, self._encode_metadata(metadata)),
        )
        self._connection.commit()
        return record_id

    def read(self, key: str) -> List[Dict[str, Any]]:
        self._validate_key(key)
        rows = self._connection.execute(
            """
            SELECT record_id, key, value, metadata_json
            FROM memory_records
            WHERE key = ?
            ORDER BY record_index ASC
            """,
            (key,),
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def search(self, query: str, metadata_filter: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        self._validate_key(query)
        if not isinstance(metadata_filter, dict):
            raise ValueError("SQLiteMemory.search metadata_filter must be an object")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ValueError("SQLiteMemory.search limit must be a positive integer")

        matches = [
            record
            for record in self.read(query)
            if self._metadata_matches(record["metadata"], metadata_filter)
        ]
        return matches[:limit]

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "SQLiteMemory":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def _ensure_schema(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_records (
                record_index INTEGER NOT NULL UNIQUE,
                record_id TEXT PRIMARY KEY,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memory_records_key
            ON memory_records (key, record_index)
            """
        )
        self._connection.commit()

    def _next_record_index(self) -> int:
        row = self._connection.execute(
            "SELECT COALESCE(MAX(record_index), 0) + 1 AS next_index FROM memory_records"
        ).fetchone()
        return int(row["next_index"])

    def _row_to_record(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "record_id": str(row["record_id"]),
            "key": str(row["key"]),
            "value": str(row["value"]),
            "metadata": json.loads(str(row["metadata_json"])),
        }

    def _encode_metadata(self, metadata: Dict[str, Any]) -> str:
        return json.dumps(metadata, sort_keys=True, separators=(",", ":"))

    def _metadata_matches(self, metadata: Dict[str, Any], metadata_filter: Dict[str, Any]) -> bool:
        return all(metadata.get(key) == value for key, value in metadata_filter.items())

    def _validate_key(self, key: str) -> None:
        if not isinstance(key, str) or not key:
            raise ValueError("SQLiteMemory key/query must be a non-empty string")
