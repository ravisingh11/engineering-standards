from __future__ import annotations

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path


INSTALLER = Path(__file__).resolve().parents[1] / "install.py"
SPEC = importlib.util.spec_from_file_location("guardrails_v2_install", INSTALLER)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class InstalledScorecardWorkflowTests(unittest.TestCase):
    def test_trusted_collection_and_evaluation_paths_exist_after_install(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            trusted_checkout = Path(temporary) / ".guardrails-trusted"
            trusted_checkout.mkdir()
            MODULE.install(trusted_checkout, dry_run=False, profiles=["github"])

            workflow = (
                trusted_checkout / ".github/workflows/guardrails-scorecard.yml"
            ).read_text(encoding="utf-8")
            invoked_scripts = re.findall(
                r"python3 (\.guardrails-trusted/[^\s\\]+)", workflow
            )
            trusted_paths = set(
                re.findall(r"\.guardrails-trusted/[A-Za-z0-9._/-]+", workflow)
            )

            self.assertEqual(
                invoked_scripts,
                [
                    ".guardrails-trusted/.guardrails/github_evidence.py",
                    ".guardrails-trusted/.guardrails/scorecard.py",
                    ".guardrails-trusted/.guardrails/scorecard.py",
                ],
            )
            self.assertTrue(trusted_paths)
            missing = sorted(
                path
                for path in trusted_paths
                if not (Path(temporary) / path).is_file()
            )
            self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
