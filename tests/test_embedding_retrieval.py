from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from avf.agents.memory import SQLiteMemory  # noqa: E402
from avf.agents.retrieval import EmbeddingRetriever  # noqa: E402
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


class EmbeddingRetrieverTests(unittest.TestCase):
    def test_query_ranks_documents_deterministically(self) -> None:
        retriever = EmbeddingRetriever()
        retriever.index([
            {
                "document_id": "doc_001",
                "text": "compact concise summaries",
                "metadata": {"family": "style"},
                "source": {"record_id": "mem_001"},
            },
            {
                "document_id": "doc_002",
                "text": "detailed compliance reports",
                "metadata": {"family": "style"},
                "source": {"record_id": "mem_002"},
            },
            {
                "document_id": "doc_003",
                "text": "compact compact technical notes",
                "metadata": {"family": "technical"},
                "source": {"record_id": "mem_003"},
            },
        ])

        results = retriever.query("compact technical", 2)

        self.assertEqual([result["document_id"] for result in results], ["doc_003", "doc_001"])
        self.assertEqual([result["rank"] for result in results], [1, 2])
        self.assertGreater(results[0]["score"], results[1]["score"])

    def test_query_applies_metadata_filter(self) -> None:
        retriever = EmbeddingRetriever()
        retriever.index([
            {
                "document_id": "doc_001",
                "text": "compact concise summaries",
                "metadata": {"family": "style"},
                "source": {"record_id": "mem_001"},
            },
            {
                "document_id": "doc_002",
                "text": "compact technical notes",
                "metadata": {"family": "technical"},
                "source": {"record_id": "mem_002"},
            },
        ])

        results = retriever.query("compact", 5, {"family": "technical"})

        self.assertEqual([result["document_id"] for result in results], ["doc_002"])

    def test_query_returns_empty_for_non_matching_text(self) -> None:
        retriever = EmbeddingRetriever()
        retriever.index([
            {"document_id": "doc_a", "text": "alpha beta", "metadata": {}, "source": {"record_id": "a"}},
        ])

        self.assertEqual(retriever.query("unrelated", 3), [])

    def test_ties_preserve_index_order(self) -> None:
        retriever = EmbeddingRetriever()
        retriever.index([
            {"document_id": "doc_a", "text": "alpha beta", "metadata": {}, "source": {"record_id": "a"}},
            {"document_id": "doc_b", "text": "alpha beta", "metadata": {}, "source": {"record_id": "b"}},
        ])

        results = retriever.query("alpha", 2)

        self.assertEqual([result["document_id"] for result in results], ["doc_a", "doc_b"])

    def test_query_validates_top_k(self) -> None:
        retriever = EmbeddingRetriever()
        retriever.index([
            {"document_id": "doc_a", "text": "alpha beta", "metadata": {}, "source": {"record_id": "a"}},
        ])

        with self.assertRaises(ValueError):
            retriever.query("alpha", 0)

    def test_mock_memory_service_uses_embedding_retrieval_for_memory_query_ranking(self) -> None:
        service = MockMemoryService(
            memory_backend=SQLiteMemory(),
            retrieval_module=EmbeddingRetriever(),
        )
        service.call_tool(
            tool_call(
                "memory.write",
                {
                    "key": "user_preference",
                    "value": "use detailed compliance reports",
                    "metadata": {"task_id": "task_a"},
                },
                "write_001",
            )
        )
        service.call_tool(
            tool_call(
                "memory.write",
                {
                    "key": "user_preference",
                    "value": "use compact technical summaries",
                    "metadata": {"task_id": "task_a"},
                },
                "write_002",
            )
        )

        query = service.call_tool(
            tool_call(
                "memory.query",
                {"query": "compact technical", "metadata_filter": {"task_id": "task_a"}, "limit": 1},
                "query_001",
            )
        )

        self.assertEqual(query.status, "success")
        self.assertEqual(query.output["records"][0]["record_id"], "mem_002")
        self.assertEqual(query.output["records"][0]["value"], "use compact technical summaries")
        self.assertEqual(query.output["retrieval_results"][0]["document_id"], "mem_002")


if __name__ == "__main__":
    unittest.main()
