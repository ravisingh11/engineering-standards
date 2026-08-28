from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "validate_repository.py"
SPEC = importlib.util.spec_from_file_location("repository_validator", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class RepositoryValidatorTests(unittest.TestCase):
    def test_machine_path_scan_ignores_superpowers_scratch_but_scans_product_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scratch = root / ".superpowers" / "notes.md"
            scratch.parent.mkdir()
            machine_path = "/" + "Users/example"
            scratch.write_text(f"{machine_path}/scratch\n", encoding="utf-8")

            with mock.patch.object(MODULE, "ROOT", root):
                MODULE.validate_no_machine_paths()

            product = root / "docs" / "product.md"
            product.parent.mkdir()
            product.write_text(f"{machine_path}/product\n", encoding="utf-8")
            stderr = io.StringIO()

            with mock.patch.object(MODULE, "ROOT", root):
                with contextlib.redirect_stderr(stderr):
                    with self.assertRaises(SystemExit):
                        MODULE.validate_no_machine_paths()

            self.assertIn("docs/product.md", stderr.getvalue())
            self.assertNotIn(".superpowers/notes.md", stderr.getvalue())

    def test_machine_path_scan_ignores_generated_guardrail_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / ".artifacts" / "guardrails" / "scorecard.md"
            report.parent.mkdir(parents=True)
            machine_path = "/" + "Users/example/repository/evidence.json"
            report.write_text(f"Evidence: {machine_path}\n", encoding="utf-8")

            with mock.patch.object(MODULE, "ROOT", root):
                MODULE.validate_no_machine_paths()


if __name__ == "__main__":
    unittest.main()
