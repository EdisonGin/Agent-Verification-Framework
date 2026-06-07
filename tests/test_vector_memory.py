from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from avf.agents.memory import SQLiteMemory, VectorMemory  # noqa: E402
from avf.contracts import ToolCall  # noqa: E402
from avf.mock_services import MockMemoryService  # noqa: E402


def tool_call(tool_name: str, arguments: dict, call_id: str = "tool_call_001") -> ToolCall:
    return ToolCall(
        tool_call_id=call_id,
        run_id="run_test",
        step_index=0,
        tool_name=tool_name,
        arguments=arguments,
        requested_at="1970-01-01T00:00:01Z",
    )


class VectorMemoryTests(unittest.TestCase):
    def test_vector_memory_matches_sqlite_write_and_read_contract(self) -> None:
        sqlite = SQLiteMemory()
        vector = VectorMemory()

        for memory in [sqlite, vector]:
            first_id = memory.write("user_preference", "use concise summaries", {"task_id": "task_a"})
            second_id = memory.write("user_preference", "use detailed reports", {"task_id": "task_b"})

            self.assertEqual(first_id, "mem_001")
            self.assertEqual(second_id, "mem_002")
            self.assertEqual(
                [record["value"] for record in memory.read("user_preference")],
                ["use concise summaries", "use detailed reports"],
            )

        sqlite.close()

    def test_vector_search_ranks_by_deterministic_similarity(self) -> None:
        memory = VectorMemory()
        memory.write("user_preference", "use detailed compliance reports", {"task_id": "task_a"})
        memory.write("user_preference", "use compact technical summaries", {"task_id": "task_a"})
        memory.write("project_note", "deploy database migrations", {"task_id": "task_b"})

        records = memory.search("compact technical", {"task_id": "task_a"}, 2)

        self.assertEqual([record["record_id"] for record in records], ["mem_002"])
        self.assertEqual(records[0]["value"], "use compact technical summaries")

    def test_vector_search_preserves_insert_order_for_equal_similarity(self) -> None:
        memory = VectorMemory()
        memory.write("user_preference", "use concise summaries", {"task_id": "task_a"})
        memory.write("user_preference", "use detailed reports", {"task_id": "task_b"})

        records = memory.search("user_preference", {}, 2)

        self.assertEqual([record["record_id"] for record in records], ["mem_001", "mem_002"])

    def test_vector_search_validates_limit(self) -> None:
        memory = VectorMemory()

        with self.assertRaises(ValueError):
            memory.search("user_preference", {}, 0)

    def test_mock_memory_service_delegates_to_vector_backend(self) -> None:
        service = MockMemoryService(memory_backend=VectorMemory())
        service.call_tool(
            tool_call(
                "memory.write",
                {
                    "key": "user_preference",
                    "value": "use compact technical summaries",
                    "metadata": {"task_id": "task_a"},
                },
                "write",
            )
        )

        query = service.call_tool(
            tool_call(
                "memory.query",
                {"query": "compact technical", "metadata_filter": {"task_id": "task_a"}, "limit": 1},
                "query",
            )
        )

        self.assertEqual(query.status, "success")
        self.assertEqual(query.output["records"][0]["record_id"], "mem_001")
        self.assertEqual(query.output["records"][0]["value"], "use compact technical summaries")


if __name__ == "__main__":
    unittest.main()
