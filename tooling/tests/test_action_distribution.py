from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RETIRED_PATHS = (
    ".ai/" + "guardrails.yaml",
    ".ai/" + "control-catalog.yaml",
    ".ai/" + "documentation.yaml",
    ".ai/" + "change-scope.yaml",
    ".ai/" + "ground-truth.yaml",
)
EXCLUDED_FILES = {
    "tooling/install.py",
    "tooling/tests/test_install.py",
}
EXCLUDED_PREFIXES = (
    "docs/superpowers/specs/",
    "docs/superpowers/plans/",
)


def retired_path_failures(root: Path) -> list[str]:
    tracked = set(
        subprocess.run(
            ["git", "ls-files", "--cached", "-z"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout.decode("utf-8", errors="surrogateescape").split("\0")
    )
    untracked = set(
        subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout.decode("utf-8", errors="surrogateescape").split("\0")
    )
    tracked.discard("")
    untracked.discard("")

    failures: set[str] = set()
    for path in sorted(tracked | untracked):
        if path in EXCLUDED_FILES or path.startswith(EXCLUDED_PREFIXES):
            continue
        if not path.endswith((".md", ".py", ".yml", ".yaml")):
            continue
        contents: set[str] = set()
        if path in tracked:
            contents.add(
                subprocess.run(
                    ["git", "show", f":{path}"],
                    cwd=root,
                    check=True,
                    capture_output=True,
                ).stdout.decode("utf-8")
            )
        candidate = root / path
        if candidate.is_file():
            contents.add(candidate.read_text(encoding="utf-8"))
        for text in contents:
            for retired_path in RETIRED_PATHS:
                if retired_path in text:
                    failures.add(f"{path}: {retired_path}")
    return sorted(failures)


class RetiredPathCandidateTests(unittest.TestCase):
    def initialize_repository(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=root,
            check=True,
        )

    def commit_file(self, root: Path, path: str, content: str) -> None:
        candidate = root / path
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", path], cwd=root, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "fixture"],
            cwd=root,
            check=True,
        )

    def test_staged_canonical_rename_does_not_scan_removed_index_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_repository(root)
            legacy = ".ai/" + "guardrails.yaml"
            self.commit_file(root, "active.py", f'POLICY = "{legacy}"\n')

            subprocess.run(
                ["git", "mv", "active.py", "canonical.py"],
                cwd=root,
                check=True,
            )
            (root / "canonical.py").write_text(
                'POLICY = ".guardrails/policy.yaml"\n',
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "canonical.py"], cwd=root, check=True)

            self.assertEqual([], retired_path_failures(root))

    def test_unstaged_deletion_scans_tracked_index_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_repository(root)
            legacy = ".ai/" + "guardrails.yaml"
            self.commit_file(root, "active.py", f'POLICY = "{legacy}"\n')

            (root / "active.py").unlink()

            self.assertEqual(
                [f"active.py: {legacy}"],
                retired_path_failures(root),
            )

    def test_untracked_non_ignored_file_is_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_repository(root)
            legacy = ".ai/" + "guardrails.yaml"
            (root / "active.py").write_text(
                f'POLICY = "{legacy}"\n',
                encoding="utf-8",
            )

            self.assertEqual(
                [f"active.py: {legacy}"],
                retired_path_failures(root),
            )

    def test_staged_retired_reference_is_not_hidden_by_clean_worktree_edit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_repository(root)
            legacy = ".ai/" + "guardrails.yaml"
            self.commit_file(root, "active.py", 'POLICY = ".guardrails/policy.yaml"\n')

            (root / "active.py").write_text(
                f'POLICY = "{legacy}"\n',
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "active.py"], cwd=root, check=True)
            (root / "active.py").write_text(
                'POLICY = ".guardrails/policy.yaml"\n',
                encoding="utf-8",
            )

            self.assertEqual(
                [f"active.py: {legacy}"],
                retired_path_failures(root),
            )


class ActionDistributionTests(unittest.TestCase):
    def test_installed_runtimes_match_distribution_sources(self) -> None:
        runtime_copies = {
            ".guardrails/configure.py": "tooling/configure_guardrails.py",
            ".guardrails/scan.py": "tooling/scan_repository.py",
            ".guardrails/github_evidence.py": "tooling/github_evidence.py",
            ".guardrails/validate_ground_truth.py": "tooling/validators/validate_ground_truth.py",
            "examples/python-demo/.guardrails/configure.py": "tooling/configure_guardrails.py",
            "examples/python-demo/.guardrails/scan.py": "tooling/scan_repository.py",
            "examples/python-demo/.guardrails/validate_ground_truth.py": "tooling/validators/validate_ground_truth.py",
        }
        for installed, source in runtime_copies.items():
            with self.subTest(installed=installed):
                self.assertEqual(
                    (ROOT / installed).read_bytes(),
                    (ROOT / source).read_bytes(),
                )

    def test_action_is_a_thin_evaluator_adapter(self) -> None:
        text = (ROOT / "action.yml").read_text(encoding="utf-8")
        self.assertIn("branding:", text)
        self.assertIn("icon: shield", text)
        self.assertIn("title=Missing revision", text)
        self.assertIn("title=Missing evidence", text)
        self.assertIn("title=Missing policy", text)
        self.assertIn("default: .guardrails/policy.yaml", text)
        self.assertIn(
            "Commit a repository-local .guardrails/policy.yaml policy.", text
        )
        self.assertIn("guardrails/evaluate.py", text)
        self.assertNotIn("git diff", text)

    def test_starter_workflow_uses_least_privilege_and_pinned_actions(self) -> None:
        text = (
            ROOT
            / "docs"
            / "examples"
            / "guardrails.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("persist-credentials: false", text)
        action_refs = re.findall(r"uses:\s+[^@\s]+@([^\s]+)", text)
        self.assertTrue(action_refs)
        self.assertTrue(
            all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs)
        )
        self.assertIn("checks: read", text)
        self.assertIn(".guardrails/github_evidence.py", text)
        self.assertIn(".guardrails/producer-manifest.json", text)
        self.assertIn(".guardrails/scan.py", text)
        self.assertIn("--policy .guardrails/policy.yaml", text)
        self.assertIn("--catalog .guardrails/control-catalog.yaml", text)
        workflow = (ROOT / "docs" / "examples" / "guardrails.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("publish-scorecard:", workflow)
        self.assertIn("actions/download-artifact@", workflow)
        self.assertIn("pull-requests: write", workflow)
        self.assertIn("<!-- guardrail-scorecard -->", workflow)
        self.assertIn("<!-- agentic-guardrail-scorecard -->", workflow)
        self.assertNotIn("pull-requests: write\n\nconcurrency:", workflow)
        publisher = workflow.split("  publish-scorecard:", 1)[1]
        self.assertNotIn("actions/checkout@", publisher)

    def test_repository_workflow_checks_ground_truth_docs_and_scope_on_every_push(self) -> None:
        text = (
            ROOT / ".github" / "workflows" / "validate.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("  docs:\n", text)
        self.assertIn("  scope:\n", text)
        self.assertIn("  ground-truth:\n", text)
        self.assertIn("name: Validate / docs", text)
        self.assertIn("name: Validate / scope", text)
        self.assertIn("name: Validate / ground truth", text)
        self.assertIn("name: Validate / repository", text)
        self.assertIn("needs: [docs, scope, ground-truth]", text)
        self.assertIn(".guardrails/validate_ground_truth.py", text)
        self.assertIn("--policy .guardrails/ground-truth-ai.yaml", text)
        self.assertIn("policy-file: .guardrails/policy.yaml", text)
        self.assertIn("tooling/validators/validate_documentation.py", text)
        self.assertIn("tooling/validators/inspect_change_scope.py", text)
        self.assertIn("PUSH_FORCED: ${{ github.event.forced || false }}", text)
        self.assertIn('[[ "$PUSH_FORCED" != "true"', text)
        self.assertNotIn("branches: [main]", text)

        documentation_validator = (
            ROOT / "tooling" / "validators" / "validate_documentation.py"
        ).read_text(encoding="utf-8")
        scope_inspector = (
            ROOT / "tooling" / "validators" / "inspect_change_scope.py"
        ).read_text(encoding="utf-8")
        self.assertIn('".guardrails" / "documentation.yaml"', documentation_validator)
        self.assertIn('".guardrails" / "change-scope.yaml"', scope_inspector)

    def test_scorecard_workflows_use_canonical_configuration(self) -> None:
        workflows = (
            ".github/workflows/guardrail-checks.yml",
            ".github/workflows/dependabot-verification.yml",
            "docs/examples/guardrails.yml",
        )
        for workflow in workflows:
            with self.subTest(workflow=workflow):
                text = (ROOT / workflow).read_text(encoding="utf-8")
                self.assertIn("--policy .guardrails/policy.yaml", text)
                self.assertIn("--catalog .guardrails/control-catalog.yaml", text)

    def test_attestation_workflow_uses_canonical_policy(self) -> None:
        text = (
            ROOT / ".github" / "workflows" / "guardrails-attestation.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("--policy .guardrails/policy.yaml", text)

    def test_active_markdown_python_and_yaml_have_no_retired_paths(self) -> None:
        self.assertEqual([], retired_path_failures(ROOT))

    def test_secret_scan_workflow_verifies_github_platform_settings(self) -> None:
        text = (ROOT / ".github" / "workflows" / "secret-scan.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("Secret Scanning and push protection", text)
        self.assertIn("security_and_analysis.secret_scanning.status", text)
        self.assertIn("security_and_analysis.secret_scanning_push_protection.status", text)
        self.assertIn("secret-scanning/alerts", text)
        self.assertIn("head_sha", text)
        self.assertIn("checks: write", text)
        self.assertIn("no-checkout evidence probe", text)
        self.assertNotIn("actions/checkout@", text)
        org = (ROOT / ".github" / "workflows" / "organization-secret-scan.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("Secret Scan / organization scanner", org)
        self.assertIn("pull_request:", org)
        self.assertNotIn("SECURITY_SETTINGS_TOKEN", org)

    def test_secret_scan_verifier_is_skipped_without_a_credential(self) -> None:
        text = (ROOT / ".github" / "workflows" / "secret-scan.yml").read_text(
            encoding="utf-8"
        )
        configuration, verifier = text.split("  verifier:\n", 1)

        self.assertIn("  configuration:\n", configuration)
        self.assertIn("name: Secret Scan Configuration", configuration)
        self.assertIn(
            "token_configured: ${{ steps.detect.outputs.token_configured }}",
            configuration,
        )
        self.assertIn(
            "if: steps.detect.outputs.token_configured != 'true'",
            configuration,
        )
        self.assertIn('conclusion:"skipped"', configuration)
        self.assertIn("needs: configuration", verifier)
        self.assertIn(
            "if: needs.configuration.outputs.token_configured == 'true'",
            verifier,
        )
        self.assertNotIn(
            'reason="SECURITY_SETTINGS_TOKEN is not configured."',
            verifier,
        )

    def test_secret_scan_job_name_does_not_claim_the_control_passed(self) -> None:
        text = (ROOT / ".github" / "workflows" / "secret-scan.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("name: Secret Scan Evidence Probe", text)
        self.assertNotIn("name: Secret Scan Platform Verifier", text)

    def test_codeql_workflow_publishes_the_manifest_check_name(self) -> None:
        text = (ROOT / ".github" / "workflows" / "codeql.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("name: CodeQL", text)
        self.assertIn("github/codeql-action/init@", text)
        self.assertIn("github/codeql-action/analyze@", text)
        self.assertIn("security-events: write", text)
        self.assertIn("ref: ${{ github.event.pull_request.head.sha || github.sha }}", text)

    def test_default_ruleset_does_not_define_an_empty_required_check_rule(self) -> None:
        ruleset = json.loads(
            (ROOT / "rulesets" / "default-branch-protection.json").read_text(
                encoding="utf-8"
            )
        )
        required_check_rules = [
            rule for rule in ruleset["rules"] if rule["type"] == "required_status_checks"
        ]
        self.assertEqual([], required_check_rules)


if __name__ == "__main__":
    unittest.main()
