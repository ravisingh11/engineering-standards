from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "inspect_change_scope.py"
SPEC = importlib.util.spec_from_file_location("change_scope", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def policy() -> dict:
    return {
        "version": 1,
        "limits": {
            "max_files": 2,
            "max_added_lines": 20,
            "max_changed_lines": 30,
            "max_added_lines_per_file": 15,
        },
        "exclude": ["**/*.md"],
    }


class ChangeScopeTests(unittest.TestCase):
    def test_default_policy_uses_guardrails_configuration(self) -> None:
        self.assertEqual(
            MODULE.DEFAULT_POLICY,
            MODULE.ROOT / ".guardrails" / "change-scope.yaml",
        )

    def test_passes_change_within_advisory_thresholds(self) -> None:
        result = MODULE.inspect(
            "git-tree",
            "tree-id",
            [{"path": "src/app.py", "added": 10, "deleted": 2}],
            policy(),
        )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["metrics"]["changed_lines"], 12)

    def test_reports_each_exceeded_threshold_without_blocking_execution(self) -> None:
        result = MODULE.inspect(
            "git-tree",
            "tree-id",
            [
                {"path": "src/app.py", "added": 16, "deleted": 10},
                {"path": "src/api.py", "added": 10, "deleted": 5},
                {"path": "src/web.py", "added": 2, "deleted": 1},
            ],
            policy(),
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(
            {finding["metric"] for finding in result["findings"]},
            {
                "files",
                "added_lines",
                "changed_lines",
                "max_added_lines_per_file",
            },
        )

    def test_excludes_documentation_from_source_scope(self) -> None:
        result = MODULE.inspect(
            "git-tree",
            "tree-id",
            [
                {"path": "README.md", "added": 1000, "deleted": 0},
                {"path": "src/app.py", "added": 1, "deleted": 0},
            ],
            policy(),
        )
        self.assertEqual(result["metrics"]["files"], 1)
        self.assertEqual(result["metrics"]["added_lines"], 1)

    def test_counts_binary_files_without_inventing_line_counts(self) -> None:
        result = MODULE.inspect(
            "git-tree",
            "tree-id",
            [{"path": "assets/logo.png", "added": None, "deleted": None}],
            policy(),
        )
        self.assertEqual(result["metrics"]["binary_files"], 1)
        self.assertEqual(result["metrics"]["changed_lines"], 0)


if __name__ == "__main__":
    unittest.main()
