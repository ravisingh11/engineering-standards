from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class SemgrepWorkflowTests(unittest.TestCase):
    def test_rule_fixtures_use_supported_json_scans(self) -> None:
        workflow = (ROOT / "workflows" / "semgrep-ce.yml").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("semgrep --test", workflow)
        self.assertIn(
            "semgrep scan --metrics off --config .guardrails/semgrep-rules.yml --json",
            workflow,
        )
        self.assertIn("semgrep-unsafe.json", workflow)
        self.assertIn("semgrep-safe.json", workflow)
        self.assertIn("guardrails.python-disabled-tls-verification", workflow)
        self.assertIn("guardrails.javascript-disabled-tls-verification", workflow)
        self.assertIn('check_id.removeprefix("guardrails.")', workflow)
        self.assertEqual(workflow.count("--metrics off"), 3)
        self.assertIn(
            "--exclude examples/python-demo/.guardrails/semgrep-tests/fixtures",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
