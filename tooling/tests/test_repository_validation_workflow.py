from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class RepositoryValidationWorkflowTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
