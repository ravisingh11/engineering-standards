from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tooling.validators import validate_no_migrations


ROOT = Path(__file__).resolve().parents[2]


class RepositoryCommandTests(unittest.TestCase):
    def run_migration_validator(self, root: Path) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(sys, "argv", ["validate_no_migrations.py", "--root", str(root)]),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            status = validate_no_migrations.main()
        return status, stdout.getvalue(), stderr.getvalue()

    def test_build_compiles_python_without_writing_bytecode_into_repository(self) -> None:
        before = set(ROOT.rglob("*.pyc"))

        completed = subprocess.run(
            ["bash", "tooling/build.sh"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(set(ROOT.rglob("*.pyc")), before)

    def test_changed_code_coverage_requires_an_exact_comparison_base(self) -> None:
        environment = os.environ.copy()
        environment.pop("GUARDRAILS_COVERAGE_BASE_REF", None)

        completed = subprocess.run(
            ["bash", "tooling/changed_code_coverage.sh"],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("GUARDRAILS_COVERAGE_BASE_REF", completed.stderr)

    def test_changed_code_coverage_uses_supported_diff_cover_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            binary_directory = Path(directory)
            coverage = binary_directory / "coverage"
            coverage.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "printf '%s\\n' \"$*\" >> \"${COVERAGE_ARGUMENT_LOG}\"\n"
                "if [[ \"${1:-}\" == \"erase\" ]]; then rm -f \"${COVERAGE_FILE:-.coverage}\"; exit 0; fi\n"
                "if [[ \"${1:-}\" == \"xml\" ]]; then\n"
                "  shift\n"
                "  while (($#)); do\n"
                "    if [[ \"$1\" == \"-o\" ]]; then touch \"$2\"; exit 0; fi\n"
                "    shift\n"
                "  done\n"
                "fi\n",
                encoding="utf-8",
            )
            diff_cover = binary_directory / "diff-cover"
            diff_cover.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "for argument in \"$@\"; do\n"
                "  [[ \"${argument}\" != \"--total-percent-float\" ]] || exit 64\n"
                "done\n",
                encoding="utf-8",
            )
            coverage.chmod(0o755)
            diff_cover.chmod(0o755)
            environment = os.environ.copy()
            environment["PATH"] = f"{binary_directory}:/usr/bin:/bin"
            environment["GUARDRAILS_COVERAGE_BASE_REF"] = "base-sha"
            inherited_coverage_file = binary_directory / "outer.coverage"
            inherited_coverage_file.write_text("outer coverage data", encoding="utf-8")
            environment["COVERAGE_FILE"] = str(inherited_coverage_file)
            argument_log = binary_directory / "coverage-arguments.log"
            environment["COVERAGE_ARGUMENT_LOG"] = str(argument_log)

            completed = subprocess.run(
                ["bash", "tooling/changed_code_coverage.sh"],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                inherited_coverage_file.read_text(encoding="utf-8"),
                "outer coverage data",
            )
            arguments = argument_log.read_text(encoding="utf-8")
            self.assertIn("--source=guardrails,tooling,examples/python-demo,skills,security", arguments)
            self.assertIn("skills/_shared-project-ops/scripts/tests", arguments)
            self.assertIn("skills/full-test-suite/scripts/tests", arguments)
            self.assertIn("skills/issue-operator/scripts/tests", arguments)
            self.assertIn("security/semgrep/tests", arguments)

    def test_migration_validator_accepts_repository_without_migrations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            status, stdout, stderr = self.run_migration_validator(Path(directory))

        self.assertEqual(status, 0, stderr)
        self.assertIn("No database migration surface", stdout)

    def test_migration_validator_rejects_a_known_migration_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "db" / "migrate").mkdir(parents=True)
            status, _stdout, stderr = self.run_migration_validator(root)

        self.assertEqual(status, 1)
        self.assertIn("db/migrate", stderr)

    def test_migration_validator_rejects_a_nested_framework_migration_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "example_app" / "migrations").mkdir(parents=True)
            status, _stdout, stderr = self.run_migration_validator(root)

        self.assertEqual(status, 1)
        self.assertIn("example_app/migrations", stderr)

    def test_migration_validator_ignores_dependency_and_generated_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for excluded in (".venv", "node_modules", "vendor", ".worktrees"):
                (root / excluded / "package" / "migrations").mkdir(parents=True)
            status, _stdout, stderr = self.run_migration_validator(root)

        self.assertEqual(status, 0, stderr)


if __name__ == "__main__":
    unittest.main()
