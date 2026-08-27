from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "validate_ground_truth.py"


class GroundTruthValidatorTests(unittest.TestCase):
    def run_validator(self, root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )

    def write_policy(self, root: Path, documents: list[dict[str, str]]) -> Path:
        policy = root / "policy.yaml"
        policy.write_text(
            json.dumps({"version": 1, "documents": documents}),
            encoding="utf-8",
        )
        return policy

    def test_valid_inventory_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("# Instructions\n", encoding="utf-8")
            policy = self.write_policy(root, [{"path": "AGENTS.md"}])

            result = self.run_validator(root, "--policy", str(policy))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("passed (1 documents)", result.stdout)

    def test_missing_declared_document_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = self.write_policy(root, [{"path": "missing.md"}])

            result = self.run_validator(root, "--policy", str(policy))

            self.assertEqual(result.returncode, 1)
            self.assertIn("- missing.md", result.stdout)

    def test_malformed_json_compatible_yaml_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = root / "policy.yaml"
            policy.write_text("version: 1\n", encoding="utf-8")

            result = self.run_validator(root, "--policy", str(policy))

            self.assertEqual(result.returncode, 1)
            self.assertIn("cannot read ground-truth policy", result.stdout)

    def test_missing_policy_path_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            result = self.run_validator(root, "--policy", "missing-policy.yaml")

            self.assertEqual(result.returncode, 1)
            self.assertIn("cannot read ground-truth policy", result.stdout)

    def test_default_policy_uses_guardrails_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = root / ".guardrails" / "ground-truth-ai.yaml"
            policy.parent.mkdir()
            policy.write_text(
                json.dumps({"version": 1, "documents": []}),
                encoding="utf-8",
            )

            result = self.run_validator(root)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("passed (0 documents)", result.stdout)


if __name__ == "__main__":
    unittest.main()
