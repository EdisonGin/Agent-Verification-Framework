from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from avf.agents.scheduling import RuleBasedScheduler, SequentialScheduler  # noqa: E402
from avf.contracts import AgentAction  # noqa: E402


def action(
    action_id: str,
    step_index: int,
    action_type: str,
    name: str,
    arguments: Optional[dict] = None,
) -> AgentAction:
    return AgentAction(
        action_id=action_id,
        run_id="run_scheduler_test",
        step_index=step_index,
        action_type=action_type,
        name=name,
        arguments=arguments or {},
        rationale=None,
    )


class RuleBasedSchedulerTests(unittest.TestCase):
    def test_sequential_scheduler_preserves_planner_order(self) -> None:
        actions = [
            action("action_003", 2, "final_answer", "final_answer"),
            action("action_001", 0, "tool_call", "memory.write"),
            action("action_002", 1, "tool_call", "memory.query"),
        ]

        scheduled = SequentialScheduler().schedule(actions)

        self.assertEqual([item.action_id for item in scheduled], ["action_003", "action_001", "action_002"])

    def test_rule_based_scheduler_prioritises_memory_dependencies_and_final_answer(self) -> None:
        scheduler = RuleBasedScheduler()
        actions = [
            action("action_003", 0, "final_answer", "final_answer"),
            action("action_002", 1, "tool_call", "memory.query"),
            action("action_001", 2, "tool_call", "memory.write"),
        ]

        scheduled = scheduler.schedule(actions)

        self.assertEqual([item.name for item in scheduled], ["memory.write", "memory.query", "final_answer"])
        self.assertEqual([item.step_index for item in scheduled], [0, 1, 2])

    def test_rule_based_scheduler_preserves_original_order_for_equal_priority(self) -> None:
        scheduler = RuleBasedScheduler()
        actions = [
            action("action_001", 0, "tool_call", "search.github"),
            action("action_002", 1, "tool_call", "search.google"),
        ]

        scheduled = scheduler.schedule(actions)

        self.assertEqual([item.action_id for item in scheduled], ["action_001", "action_002"])

    def test_rule_based_scheduler_records_explainable_decisions(self) -> None:
        scheduler = RuleBasedScheduler()
        scheduler.schedule([
            action("action_002", 1, "tool_call", "memory.query"),
            action("action_001", 0, "tool_call", "memory.write"),
        ])

        decisions = scheduler.decisions()

        self.assertEqual([decision["rule"] for decision in decisions], [
            "memory_write_before_memory_query",
            "memory_query_after_memory_write",
        ])
        self.assertEqual(decisions[0]["original_step_index"], 0)
        self.assertEqual(decisions[0]["scheduled_step_index"], 0)
        self.assertEqual(decisions[1]["original_step_index"], 1)
        self.assertEqual(decisions[1]["scheduled_step_index"], 1)


if __name__ == "__main__":
    unittest.main()
