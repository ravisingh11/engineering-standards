from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scan_repository.py"
SPEC = importlib.util.spec_from_file_location("agentic_scan_repository", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ControlDocumentationLinkTests(unittest.TestCase):
    def test_control_links_use_stable_heading_anchors(self) -> None:
        expected = {
            "repository-validation": "repository-validation",
            "documentation": "documentation-validation",
            "repository-ground-truth": "ground-truth",
            "build": "build",
            "unit-tests": "unit-tests",
            "codeql-sast": "codeql--sast",
            "secrets-scan": "secrets-scanning",
            "dependency-review": "dependency-review",
            "dependabot": "dependabot",
            "sonarqube": "sonarqube",
            "fossa": "fossa",
            "snyk-code": "snyk",
            "snyk-open-source": "snyk",
            "soak-check": "soak-check",
            "ai-engineering-review": "ai-reviews",
            "ai-qa-review": "ai-reviews",
            "ai-security-review": "ai-reviews",
            "ai-repo-standards-review": "repository-standards-review",
        }

        self.assertEqual(set(MODULE.CONTROL_DOCS), set(expected))
        for control_id, anchor in expected.items():
            with self.subTest(control_id=control_id):
                self.assertEqual(
                    MODULE.CONTROL_DOCS[control_id].rsplit("#", 1)[1],
                    anchor,
                )


class DependabotEvidenceTests(unittest.TestCase):
    def test_configuration_is_not_claimed_as_a_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            config = target / ".github" / "dependabot.yml"
            config.parent.mkdir()
            config.write_text("version: 2\n", encoding="utf-8")

            evidence = MODULE.dependabot_configuration_evidence(target)

            self.assertIsNotNone(evidence)
            assert evidence is not None
            self.assertEqual(evidence["status"], "not_run")
            self.assertIn("configuration: .github/dependabot.yml", evidence["evidence"])
            self.assertIn("settings", evidence["reason"])

    def test_missing_configuration_has_no_local_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(MODULE.dependabot_configuration_evidence(Path(directory)))


class DefaultConfigurationTests(unittest.TestCase):
    def test_shared_repository_uses_checked_in_configuration_paths(self) -> None:
        self.assertEqual(
            MODULE.default_config_path(MODULE.ROOT, ".ai/guardrails.yaml", "guardrails/baseline.yaml"),
            MODULE.ROOT / ".ai/guardrails.yaml",
        )
        self.assertEqual(
            MODULE.default_config_path(MODULE.ROOT, ".ai/control-catalog.yaml", "policies/control-catalog.yaml"),
            MODULE.ROOT / ".ai/control-catalog.yaml",
        )

    def test_installed_repository_prefers_consumer_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            policy = target / ".ai" / "guardrails.yaml"
            policy.parent.mkdir()
            policy.write_text("{}", encoding="utf-8")

            self.assertEqual(
                MODULE.default_config_path(target, ".ai/guardrails.yaml", "guardrails/baseline.yaml"),
                policy,
            )


class ExternalEvidenceTests(unittest.TestCase):
    def _base_evidence(self) -> dict:
        return {
            "version": 1,
            "subject": {"type": "git-commit", "revision": "abc123"},
            "checks": {},
        }

    def _write_fragment(self, directory: Path, name: str, evidence: dict) -> None:
        (directory / name).write_text(json.dumps(evidence), encoding="utf-8")

    def test_ignores_evidence_for_a_different_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence_dir = Path(directory)
            fragment = self._base_evidence()
            fragment["subject"]["revision"] = "wrong-revision"
            fragment["checks"] = {
                "build": {
                    "producer": "build workflow",
                    "status": "passed",
                    "evidence": ["run: 42"],
                }
            }
            self._write_fragment(evidence_dir, "build.json", fragment)

            merged = self._base_evidence()
            MODULE.merge_external_evidence(merged, evidence_dir)

            self.assertNotIn("build", merged["checks"])

    def test_rejects_conflicting_duplicate_check_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence_dir = Path(directory)
            first = self._base_evidence()
            first["checks"] = {
                "build": {
                    "producer": "build workflow",
                    "status": "passed",
                    "evidence": ["run: 42"],
                }
            }
            second = self._base_evidence()
            second["checks"] = {
                "build": {
                    "producer": "another build workflow",
                    "status": "failed",
                    "evidence": ["run: 43"],
                }
            }
            self._write_fragment(evidence_dir, "a.json", first)
            self._write_fragment(evidence_dir, "b.json", second)

            with self.assertRaisesRegex(ValueError, "duplicate evidence"):
                MODULE.merge_external_evidence(self._base_evidence(), evidence_dir)

    def test_merges_valid_revision_bound_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence_dir = Path(directory)
            fragment = self._base_evidence()
            fragment["checks"] = {
                "build": {
                    "producer": "build workflow",
                    "status": "passed",
                    "evidence": ["run: 42"],
                }
            }
            self._write_fragment(evidence_dir, "build.json", fragment)

            merged = self._base_evidence()
            MODULE.merge_external_evidence(merged, evidence_dir)

            self.assertEqual(merged["checks"]["build"]["status"], "passed")

    def test_does_not_replace_local_pass_with_missing_external_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence_dir = Path(directory)
            fragment = self._base_evidence()
            fragment["checks"] = {
                "build": {
                    "producer": "GitHub Check: Build",
                    "status": "not_run",
                    "reason": "The configured producer check did not report this revision.",
                }
            }
            self._write_fragment(evidence_dir, "github.json", fragment)

            merged = self._base_evidence()
            merged["checks"]["build"] = {
                "producer": "local build",
                "status": "passed",
                "evidence": ["compile succeeded"],
            }
            MODULE.merge_external_evidence(merged, evidence_dir)

            self.assertEqual(merged["checks"]["build"]["status"], "passed")

    def test_reconciles_local_pass_and_external_no_result_fragments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence_dir = Path(directory)
            local = self._base_evidence()
            local["checks"] = {
                "documentation": {
                    "producer": "local documentation validation",
                    "status": "passed",
                    "evidence": ["local validation"],
                }
            }
            external = self._base_evidence()
            external["checks"] = {
                "documentation": {
                    "producer": "GitHub Check: Validate / docs",
                    "status": "not_run",
                    "reason": "The configured producer check did not report this revision.",
                }
            }
            self._write_fragment(evidence_dir, "a-local.json", local)
            self._write_fragment(evidence_dir, "z-github.json", external)

            merged = self._base_evidence()
            MODULE.merge_external_evidence(merged, evidence_dir)

            self.assertEqual(merged["checks"]["documentation"]["status"], "passed")

    def test_reconciles_duplicate_no_result_fragments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence_dir = Path(directory)
            for name, producer in (("a.json", "local AI review"), ("b.json", "GitHub Check: AI Engineering Review")):
                fragment = self._base_evidence()
                fragment["checks"] = {
                    "ai-engineering-review": {
                        "producer": producer,
                        "status": "not_run",
                        "reason": "No review was found for this revision.",
                    }
                }
                self._write_fragment(evidence_dir, name, fragment)

            merged = self._base_evidence()
            MODULE.merge_external_evidence(merged, evidence_dir)

            self.assertEqual(merged["checks"]["ai-engineering-review"]["status"], "not_run")


if __name__ == "__main__":
    unittest.main()
