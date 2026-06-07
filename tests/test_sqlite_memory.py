from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from avf.agents.memory import SQLiteMemory  # noqa: E402
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


class SQLiteMemoryTests(unittest.TestCase):
    def test_write_read_and_search_are_deterministic(self) -> None:
        memory = SQLiteMemory()

        first_id = memory.write("user_preference", "use concise summaries", {"task_id": "task_a"})
        second_id = memory.write("user_preference", "use detailed reports", {"task_id": "task_b"})

        self.assertEqual(first_id, "mem_001")
        self.assertEqual(second_id, "mem_002")
        self.assertEqual(
            [record["value"] for record in memory.read("user_preference")],
            ["use concise summaries", "use detailed reports"],
        )
        self.assertEqual(
            [record["value"] for record in memory.search("user_preference", {"task_id": "task_b"}, 10)],
            ["use detailed reports"],
        )

    def test_file_backed_memory_persists_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "memory.sqlite"
            first = SQLiteMemory(db_path)
            first.write("user_preference", "use concise summaries", {"task_id": "task_a"})
            first.close()

            second = SQLiteMemory(db_path)
            records = second.search("user_preference", {"task_id": "task_a"}, 1)
            second.close()

        self.assertEqual(records[0]["record_id"], "mem_001")
        self.assertEqual(records[0]["value"], "use concise summaries")

    def test_search_validates_limit(self) -> None:
        memory = SQLiteMemory()

        with self.assertRaises(ValueError):
            memory.search("user_preference", {}, 0)

    def test_mock_memory_service_delegates_to_sqlite_backend(self) -> None:
        service = MockMemoryService(memory_backend=SQLiteMemory())

        write = service.call_tool(
            tool_call(
                "memory.write",
                {"key": "user_preference", "value": "use concise summaries", "metadata": {"task_id": "task_a"}},
                "write",
            )
        )
        query = service.call_tool(
            tool_call(
                "memory.query",
                {"query": "user_preference", "metadata_filter": {"task_id": "task_a"}, "limit": 1},
                "query",
            )
        )

        self.assertEqual(write.status, "success")
        self.assertEqual(write.output["record_id"], "mem_001")
        self.assertEqual(query.status, "success")
        self.assertEqual(query.output["records"][0]["value"], "use concise summaries")


if __name__ == "__main__":
    unittest.main()
