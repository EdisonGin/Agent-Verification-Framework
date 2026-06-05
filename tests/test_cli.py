from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from avf.cli import main  # noqa: E402


class CliTests(unittest.TestCase):
    def test_validate_fixtures_command(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = main(["validate-fixtures", "--root", str(ROOT / "test_data")])

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("tasks:", output)
        self.assertIn("configs:", output)
        self.assertIn("components:", output)
        self.assertIn("tool_specs:", output)

    def test_create_run_context_command(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = main([
                "create-run-context",
                "--task",
                str(ROOT / "test_data" / "tasks" / "memory_recall_001.json"),
                "--config",
                str(ROOT / "test_data" / "configs" / "baseline_seed_001.json"),
                "--components",
                str(ROOT / "test_data" / "components" / "A1_B1_C1.json"),
                "--tool-spec",
                str(ROOT / "test_data" / "tool_specs" / "memory.write.json"),
                "--tool-spec",
                str(ROOT / "test_data" / "tool_specs" / "memory.query.json"),
            ])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "created")
        self.assertEqual(payload["seed"], 42)
        self.assertEqual(payload["task"]["task_id"], "memory_recall_001")
        self.assertEqual(payload["component_config"]["config_id"], "A1_B1_C1")
        self.assertTrue(payload["run_id"].startswith("run_"))


if __name__ == "__main__":
    unittest.main()
