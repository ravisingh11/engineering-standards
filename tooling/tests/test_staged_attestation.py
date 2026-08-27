from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "attest_staged_change.py"
SPEC = importlib.util.spec_from_file_location("staged_attestation", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class StagedAttestationTests(unittest.TestCase):
    def test_staged_snapshot_uses_guardrails_configuration(self) -> None:
        self.assertEqual(MODULE.POLICY_PATH, Path(".guardrails/policy.yaml"))
        self.assertEqual(MODULE.SCOPE_POLICY_PATH, Path(".guardrails/change-scope.yaml"))

    @staticmethod
    def scope(status: str = "passed") -> dict:
        return {
            "status": status,
            "metrics": {
                "files": 1,
                "added_lines": 10,
                "changed_lines": 12,
                "max_added_lines_per_file": 10,
                "binary_files": 0,
            },
            "findings": [] if status == "passed" else [{"metric": "files"}],
        }

    def test_passes_repository_validation_only_when_both_producers_pass(self) -> None:
        evidence = MODULE.build_evidence("tree-id", 0, 0, 0, self.scope())
        check = evidence["checks"]["repository-validation"]
        self.assertEqual(check["status"], "passed")
        self.assertEqual(evidence["subject"]["revision"], "tree-id")

    def test_preserves_failed_producer_result(self) -> None:
        for validation, diff_check in ((1, 0), (0, 1), (1, 1)):
            with self.subTest(validation=validation, diff_check=diff_check):
                evidence = MODULE.build_evidence(
                    "tree-id",
                    validation,
                    diff_check,
                    0,
                    self.scope(),
                )
                check = evidence["checks"]["repository-validation"]
                self.assertEqual(check["status"], "failed")
                self.assertIn(f"(exit {validation})", check["evidence"][0])
                self.assertIn(f"(exit {diff_check})", check["evidence"][1])

    def test_preserves_documentation_failure_as_required_evidence(self) -> None:
        evidence = MODULE.build_evidence("tree-id", 0, 0, 1, self.scope())
        self.assertEqual(evidence["checks"]["documentation"]["status"], "failed")

    def test_preserves_change_scope_finding_as_advisory_evidence(self) -> None:
        evidence = MODULE.build_evidence(
            "tree-id",
            0,
            0,
            0,
            self.scope("failed"),
        )
        check = evidence["checks"]["change-scope"]
        self.assertEqual(check["status"], "failed")
        self.assertIn("advisory findings: 1", check["evidence"])


if __name__ == "__main__":
    unittest.main()
