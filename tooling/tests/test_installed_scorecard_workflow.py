from __future__ import annotations

import importlib.util
import re
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


INSTALLER = Path(__file__).resolve().parents[1] / "install.py"
SPEC = importlib.util.spec_from_file_location("guardrails_v2_install", INSTALLER)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def workflow_step_script(workflow: str, step_name: str) -> str:
    lines = workflow.splitlines()
    marker = f"      - name: {step_name}"
    start = lines.index(marker)
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith("      - name:")
        ),
        len(lines),
    )
    run = next(
        (index for index in range(start + 1, end) if lines[index] == "        run: |"),
        None,
    )
    if run is None:
        raise AssertionError(f"workflow step {step_name!r} does not contain a run script")
    return textwrap.dedent("\n".join(lines[run + 1 : end])) + "\n"


class InstalledScorecardWorkflowTests(unittest.TestCase):
    def test_candidate_validation_rejects_semantically_invalid_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            trusted_checkout = target / ".guardrails-trusted"
            candidate_policy = (
                target / ".guardrails-candidate/.guardrails/policy.yaml"
            )
            trusted_checkout.mkdir()
            candidate_policy.parent.mkdir(parents=True)
            MODULE.install(trusted_checkout, dry_run=False, profiles=["github"])
            candidate_policy.write_text(
                """{
  "version": 2,
  "name": "invalid candidate",
  "profiles": ["unknown-profile"],
  "overrides": {"change": {}, "release": {}}
}
""",
                encoding="utf-8",
            )

            workflow = (
                trusted_checkout / ".github/workflows/guardrails-scorecard.yml"
            ).read_text(encoding="utf-8")
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    workflow_step_script(
                        workflow, "Validate candidate configuration paths"
                    ),
                ],
                cwd=target,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown-profile", result.stderr)

    def test_enforcement_uses_only_the_trusted_base_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            MODULE.install(target, dry_run=False, profiles=["github"])
            workflow = (
                target / ".github/workflows/guardrails-scorecard.yml"
            ).read_text(encoding="utf-8")
            enforcement_scripts = "".join(
                workflow_step_script(workflow, step_name)
                for step_name in (
                    "Collect selected provider checks",
                    "Render scorecard",
                )
            )

            self.assertEqual(
                enforcement_scripts.count(
                    "--policy .guardrails-trusted/.guardrails/policy.yaml"
                ),
                3,
            )
            self.assertNotIn(
                "--policy .guardrails-candidate/.guardrails/policy.yaml",
                enforcement_scripts,
            )

    def test_collection_wait_covers_longest_installed_producer_with_bounded_headroom(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            MODULE.install(target, dry_run=False)
            workflows = target / ".github/workflows"
            scorecard = (workflows / "guardrails-scorecard.yml").read_text(
                encoding="utf-8"
            )

            wait_match = re.search(r"--wait-seconds (\d+)", scorecard)
            scorecard_timeout_match = re.search(
                r"timeout-minutes:\s*(\d+)", scorecard
            )
            self.assertIsNotNone(wait_match)
            self.assertIsNotNone(scorecard_timeout_match)
            assert wait_match and scorecard_timeout_match
            wait_seconds = int(wait_match.group(1))
            scorecard_timeout_minutes = int(scorecard_timeout_match.group(1))

            producer_timeout_minutes = max(
                int(timeout)
                for workflow in workflows.glob("*.yml")
                if workflow.name != "guardrails-scorecard.yml"
                for timeout in re.findall(
                    r"timeout-minutes:\s*(\d+)",
                    workflow.read_text(encoding="utf-8"),
                )
            )

            self.assertGreaterEqual(
                wait_seconds,
                producer_timeout_minutes * 60,
                "collector polling must cover the longest installed producer timeout",
            )
            self.assertGreater(
                scorecard_timeout_minutes * 60,
                wait_seconds,
                "the scorecard job needs bounded time to render and upload after polling",
            )
            self.assertLessEqual(
                scorecard_timeout_minutes,
                producer_timeout_minutes + 10,
                "scorecard runtime headroom must remain bounded",
            )

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
                    ".guardrails-trusted/.guardrails/configure.py",
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
