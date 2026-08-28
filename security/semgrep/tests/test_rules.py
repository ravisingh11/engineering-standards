from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RULES = ROOT / "security/semgrep/guardrails.yml"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class SemgrepRuleTests(unittest.TestCase):
    def run_semgrep(self, fixture: str) -> dict:
        try:
            completed = subprocess.run(
                ["semgrep", "scan", "--config", str(RULES), "--json", str(FIXTURES / fixture)],
                text=True,
                capture_output=True,
            )
        except FileNotFoundError:
            self.skipTest("Semgrep 1.175.0 is required to execute rule fixtures")
        if completed.returncode not in (0, 1):
            self.skipTest("Semgrep 1.175.0 is required to execute rule fixtures")
        return json.loads(completed.stdout)

    def test_tls_verification_rules_match_only_unsafe_fixtures(self) -> None:
        unsafe = self.run_semgrep("unsafe")
        safe = self.run_semgrep("safe")
        self.assertEqual(
            {result["check_id"] for result in unsafe["results"]},
            {"guardrails.python-disabled-tls-verification", "guardrails.javascript-disabled-tls-verification"},
        )
        self.assertEqual(safe["results"], [])


if __name__ == "__main__":
    unittest.main()
