from __future__ import annotations

import contextlib
import io
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


if __name__ == "__main__":
    unittest.main()

