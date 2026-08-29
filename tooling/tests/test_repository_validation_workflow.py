from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def scope_run_script(workflow: str) -> str:
    scope_job = workflow.split("  scope:\n", 1)[1]
    run_line = next(
        line for line in scope_job.splitlines() if line.startswith("      - run:")
    )
    if run_line != "      - run: |":
        return run_line.split("      - run: ", 1)[1]
    lines = scope_job.splitlines()
    start = lines.index(run_line) + 1
    end = next(
        (
            index
            for index in range(start, len(lines))
            if lines[index] == "        env:"
            or (lines[index] and not lines[index].startswith("        "))
        ),
        len(lines),
    )
    return "\n".join(line[8:] for line in lines[start:end])


class RepositoryValidationWorkflowTests(unittest.TestCase):
    def test_standards_source_validation_is_a_separate_non_authoritative_check(self) -> None:
        workflow = (ROOT / "workflows" / "repository-validation.yml").read_text(
            encoding="utf-8"
        )
        repository_job = workflow.split("  repository:\n", 1)[1].split(
            "  standards-source:\n", 1
        )[0]
        standards_job = workflow.split("  standards-source:\n", 1)[1].split(
            "  docs:\n", 1
        )[0]

        self.assertIn("python3 .guardrails/validators/validate_repository.py", repository_job)
        self.assertNotIn("tooling/validators/validate_repository.py", repository_job)
        self.assertIn("name: Validate / standards source", standards_job)
        self.assertIn("hashFiles('tooling/validators/validate_repository.py')", standards_job)
        self.assertIn("python3 tooling/validators/validate_repository.py", standards_job)

    def test_pull_request_documentation_scan_uses_exact_event_revisions(self) -> None:
        workflow = (ROOT / "workflows" / "repository-validation.yml").read_text(
            encoding="utf-8"
        )
        docs_job = workflow.split("  docs:\n", 1)[1].split("  ground-truth:\n", 1)[0]

        self.assertIn("fetch-depth: 0", docs_job)
        self.assertIn(
            'validate_documentation.py --base-ref "${BASE_REF}" --head-ref "${HEAD_REF}"',
            docs_job,
        )
        self.assertIn(
            "BASE_REF: ${{ github.event.pull_request.base.sha || 'HEAD~1' }}",
            docs_job,
        )
        self.assertIn(
            "HEAD_REF: ${{ github.event.pull_request.head.sha || github.sha }}",
            docs_job,
        )
        self.assertIn("pull_request:\n", workflow)
        self.assertNotIn("pull_request_target:", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)

    def test_scope_job_fails_when_structured_result_is_failed(self) -> None:
        for relative_path in (
            "workflows/repository-validation.yml",
            ".github/workflows/repository-validation.yml",
        ):
            with self.subTest(workflow=relative_path), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                validator = root / ".guardrails/validators/inspect_change_scope.py"
                validator.parent.mkdir(parents=True)
                validator.write_text(
                    """#!/usr/bin/env python3
import json
import sys
from pathlib import Path

output = Path(sys.argv[sys.argv.index("--output") + 1])
output.write_text(json.dumps({"status": "failed"}), encoding="utf-8")
""",
                    encoding="utf-8",
                )
                workflow = (ROOT / relative_path).read_text(encoding="utf-8")
                environment = os.environ | {
                    "BASE_REF": "base",
                    "HEAD_REF": "head",
                    "RUNNER_TEMP": str(root / "runner-temp"),
                }
                (root / "runner-temp").mkdir()

                completed = subprocess.run(
                    ["bash", "-e", "-c", scope_run_script(workflow)],
                    cwd=root,
                    env=environment,
                    capture_output=True,
                    text=True,
                )

                self.assertNotEqual(completed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
