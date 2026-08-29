from __future__ import annotations

import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "workflows" / "dependabot-verification.yml"
INSTALLED = ROOT / ".github" / "workflows" / "dependabot-verification.yml"


def workflow_script(path: Path) -> str:
    scripts = []
    for run_block in path.read_text(encoding="utf-8").split("        run: |\n")[1:]:
        lines = []
        for line in run_block.splitlines():
            if line and not line.startswith("          "):
                break
            lines.append(line[10:] if line else "")
        scripts.append("\n".join(lines))
    return "\n".join(scripts) + "\n"


class DependabotWorkflowTests(unittest.TestCase):
    def run_probe(
        self, updates_response: str, updates_exit: int = 0, updates_error: str = ""
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            gh = fake_bin / "gh"
            gh.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    arguments="$*"
                    if [[ "$arguments" == *"/check-runs"* ]]; then
                      tee "$MOCK_PAYLOAD" >/dev/null
                    elif [[ "$arguments" == *"/vulnerability-alerts"* ]]; then
                      exit "$MOCK_ALERTS_EXIT"
                    elif [[ "$arguments" == *"/automated-security-fixes"* ]]; then
                      printf '%s' "$MOCK_UPDATES_RESPONSE"
                      printf '%s' "$MOCK_UPDATES_ERROR" >&2
                      exit "$MOCK_UPDATES_EXIT"
                    else
                      exit 90
                    fi
                    """
                ),
                encoding="utf-8",
            )
            gh.chmod(0o755)
            payload = root / "payload.json"
            env = {
                **os.environ,
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
                "TOKEN_CONFIGURED": "true",
                "SETTINGS_TOKEN": "settings-token",
                "GH_TOKEN": "workflow-token",
                "GITHUB_REPOSITORY": "owner/repo",
                "GITHUB_SERVER_URL": "https://github.example",
                "GITHUB_RUN_ID": "12345",
                "EVENT_NAME": "pull_request_target",
                "BASE_SHA": "base456",
                "BASE_REF": "refs/heads/main",
                "HEAD_SHA": "abc123",
                "RUNNER_TEMP": str(root),
                "MOCK_ALERTS_EXIT": "0",
                "MOCK_UPDATES_EXIT": str(updates_exit),
                "MOCK_UPDATES_RESPONSE": updates_response,
                "MOCK_UPDATES_ERROR": updates_error,
                "MOCK_PAYLOAD": str(payload),
            }
            completed = subprocess.run(
                ["bash", "-c", workflow_script(CANONICAL)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            return completed, json.loads(payload.read_text(encoding="utf-8"))

    def test_canonical_and_installed_workflows_are_identical(self) -> None:
        self.assertEqual(CANONICAL.read_bytes(), INSTALLED.read_bytes())

    def test_enabled_unpaused_response_passes(self) -> None:
        completed, payload = self.run_probe('{"enabled":true,"paused":false}')

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["conclusion"], "success")

    def test_empty_success_is_no_result(self) -> None:
        completed, payload = self.run_probe("")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["conclusion"], "skipped")
        self.assertIn("did not expose", payload["output"]["summary"])

    def test_malformed_response_is_no_result(self) -> None:
        completed, payload = self.run_probe('{"enabled":true')

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["conclusion"], "skipped")
        self.assertIn("did not expose", payload["output"]["summary"])

    def test_whitespace_only_response_is_no_result(self) -> None:
        completed, payload = self.run_probe(" \n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["conclusion"], "skipped")
        self.assertIn("did not expose", payload["output"]["summary"])

    def test_multiple_json_values_are_no_result(self) -> None:
        completed, payload = self.run_probe(
            '{"enabled":true,"paused":false}\n'
            '{"enabled":true,"paused":false}'
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["conclusion"], "skipped")
        self.assertIn("did not expose", payload["output"]["summary"])

    def test_missing_required_field_is_no_result(self) -> None:
        for response in ('{"enabled":true}', '{"paused":false}'):
            with self.subTest(response=response):
                completed, payload = self.run_probe(response)

                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(payload["conclusion"], "skipped")
                self.assertIn("did not expose", payload["output"]["summary"])

    def test_wrong_typed_required_field_is_no_result(self) -> None:
        for response in (
            '{"enabled":"true","paused":false}',
            '{"enabled":true,"paused":0}',
        ):
            with self.subTest(response=response):
                completed, payload = self.run_probe(response)

                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(payload["conclusion"], "skipped")
                self.assertIn("did not expose", payload["output"]["summary"])

    def test_disabled_response_fails(self) -> None:
        completed, payload = self.run_probe('{"enabled":false,"paused":false}')

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(payload["conclusion"], "failure")
        self.assertIn("disabled", payload["output"]["summary"])

    def test_paused_response_fails(self) -> None:
        completed, payload = self.run_probe('{"enabled":true,"paused":true}')

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(payload["conclusion"], "failure")
        self.assertIn("paused", payload["output"]["summary"])

    def test_permission_or_unknown_response_is_no_result(self) -> None:
        completed, payload = self.run_probe("", updates_exit=1, updates_error="HTTP 403: Resource not accessible")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["conclusion"], "skipped")
        self.assertIn("did not expose", payload["output"]["summary"])

    def test_documented_404_means_dependabot_is_disabled_and_fails(self) -> None:
        completed, payload = self.run_probe(
            "", updates_exit=1, updates_error="HTTP 404: Dependabot is not enabled"
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(payload["conclusion"], "failure")
        self.assertIn("disabled", payload["output"]["summary"])


if __name__ == "__main__":
    unittest.main()
