from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scan_repository.py"
SPEC = importlib.util.spec_from_file_location("guardrails_v2_scan", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def base_evidence(revision: str = "abc123", subject_type: str = "git-commit") -> dict:
    return {"version": 2, "subject": {"type": subject_type, "revision": revision}, "results": {}}


def result(status: str = "passed", producer: str = "producer") -> dict:
    value = {"producer": producer, "status": status}
    if status in {"passed", "failed"}:
        value["evidence"] = ["run: 42"]
    else:
        value["reason"] = "no result"
    return value


class NestedEvidenceMergeTests(unittest.TestCase):
    def write(self, directory: Path, name: str, document: dict) -> None:
        (directory / name).write_text(json.dumps(document), encoding="utf-8")

    def test_merges_multiple_providers_for_one_control_without_collapsing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fragments = Path(directory)
            first = base_evidence()
            first["results"] = {"deep-sast": {"github-codeql": result()}}
            second = base_evidence()
            second["results"] = {"deep-sast": {"snyk-code": result("failed")}}
            self.write(fragments, "a.json", first)
            self.write(fragments, "b.json", second)
            merged = base_evidence()

            MODULE.merge_external_evidence(merged, fragments)

            self.assertEqual(set(merged["results"]["deep-sast"]), {"github-codeql", "snyk-code"})

    def test_rejects_conflicting_results_for_same_control_and_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fragments = Path(directory)
            for name, status in (("a.json", "passed"), ("b.json", "failed")):
                document = base_evidence()
                document["results"] = {"build": {"repository-build": result(status)}}
                self.write(fragments, name, document)

            with self.assertRaisesRegex(ValueError, "conflicting evidence"):
                MODULE.merge_external_evidence(base_evidence(), fragments)

    def test_stale_revision_or_subject_type_fragments_are_rejected_from_merge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fragments = Path(directory)
            for name, document in (
                ("revision.json", base_evidence("old")),
                ("subject.json", base_evidence(subject_type="artifact")),
            ):
                document["results"] = {"build": {"repository-build": result()}}
                self.write(fragments, name, document)
            merged = base_evidence()

            rejected = MODULE.merge_external_evidence(merged, fragments)

            self.assertEqual(rejected, ["revision.json", "subject.json"])
            self.assertEqual(merged["results"], {})


class LocalEvidenceTests(unittest.TestCase):
    def producer(self) -> mock.Mock:
        producer = mock.Mock()
        producer.repository_command_result.side_effect = [
            result("not_run", "build"),
            result("not_run", "tests"),
            result("not_run", "coverage"),
        ]
        producer.semgrep_result.return_value = result("passed", "semgrep")
        producer.gitleaks_result.return_value = result("passed", "gitleaks")
        return producer

    def commit(self, target: Path, message: str) -> str:
        subprocess.run(["git", "add", "."], cwd=target, check=True)
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=target, check=True)
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=target,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()

    def initialize_documentation_repository(self, target: Path) -> str:
        subprocess.run(["git", "init", "-q"], cwd=target, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=target, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=target, check=True)
        validators = target / "tooling" / "validators"
        validators.mkdir(parents=True)
        (validators / "validate_repository.py").write_text(
            "print('repository ok')\n",
            encoding="utf-8",
        )
        (validators / "validate_documentation.py").write_text(
            (SCRIPT.parent / "validators" / "validate_documentation.py").read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        guardrails = target / ".guardrails"
        guardrails.mkdir()
        (guardrails / "documentation.yaml").write_text(
            json.dumps(
                {
                    "version": 1,
                    "mappings": [
                        {
                            "name": "application-code",
                            "triggers": ["app.py"],
                            "documents": ["README.md"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (target / "README.md").write_text("# Fixture\n", encoding="utf-8")
        return self.commit(target, "base")

    def initialize_repository(self, target: Path) -> str:
        subprocess.run(["git", "init", "-q"], cwd=target, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=target, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=target, check=True)
        validators = target / "tooling" / "validators"
        validators.mkdir(parents=True)
        for filename in ("validate_repository.py", "validate_documentation.py", "inspect_change_scope.py"):
            (validators / filename).write_text("raise SystemExit('local validator must not run')\n", encoding="utf-8")
        guardrails = target / ".guardrails"
        guardrails.mkdir()
        (guardrails / "validate_ground_truth.py").write_text("raise SystemExit('ground truth must not run')\n", encoding="utf-8")
        (guardrails / "ground-truth-ai.yaml").write_text("{}\n", encoding="utf-8")
        (target / "README.md").write_text("clean\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=target, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=target, check=True)
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=target, check=True, text=True, capture_output=True
        ).stdout.strip()

    def test_available_validators_use_canonical_core_provider_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            validators = target / "tooling" / "validators"
            validators.mkdir(parents=True)
            for filename in ("validate_repository.py", "validate_documentation.py", "inspect_change_scope.py"):
                (validators / filename).write_text("# fixture\n", encoding="utf-8")
            ground_truth = target / ".guardrails"
            ground_truth.mkdir()
            (ground_truth / "validate_ground_truth.py").write_text("# fixture\n", encoding="utf-8")
            (ground_truth / "ground-truth-ai.yaml").write_text("{}\n", encoding="utf-8")
            scope_payload = json.dumps({"status": "passed", "metrics": {"files": 1}})
            producer = mock.Mock()
            producer.repository_command_result.side_effect = [
                result("not_run", "build"),
                result("not_run", "tests"),
                result("not_run", "coverage"),
            ]
            producer.semgrep_result.return_value = result("passed", "semgrep")
            producer.gitleaks_result.return_value = result("passed", "gitleaks")

            with mock.patch.object(MODULE, "local_binding", return_value=("abc123", None)), mock.patch.object(MODULE, "exact_local_revision", return_value=("base123", None)), mock.patch.object(MODULE, "run", side_effect=[(0, "repository ok"), (0, "docs ok"), (0, "ground truth ok"), (0, scope_payload)]):
                with mock.patch.object(MODULE, "load", return_value={"status": "passed", "metrics": {"files": 1}}), mock.patch.object(MODULE, "producer_module", return_value=producer):
                    evidence = MODULE.local_evidence(target, "abc123", "HEAD~1")

            for control_id in ("repository-validation", "documentation-validation", "repository-ground-truth", "change-scope"):
                self.assertEqual(set(evidence["results"][control_id]), {"repository-validator"})
            self.assertEqual(set(evidence["results"]["build"]), {"repository-build"})
            self.assertEqual(set(evidence["results"]["unit-tests"]), {"repository-unit-tests"})
            self.assertEqual(set(evidence["results"]["changed-code-coverage"]), {"repository-changed-code-coverage"})
            self.assertEqual(set(evidence["results"]["custom-static-analysis"]), {"semgrep-ce"})
            self.assertEqual(set(evidence["results"]["secret-detection"]), {"gitleaks"})

    def test_app_only_change_without_mapped_documentation_fails_local_scan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            self.initialize_documentation_repository(target)
            (target / "app.py").write_text("print('changed')\n", encoding="utf-8")
            head = self.commit(target, "application change")

            with mock.patch.object(MODULE, "producer_module", return_value=self.producer()):
                evidence = MODULE.local_evidence(target, head, "HEAD~1")

            documentation = evidence["results"]["documentation-validation"]["repository-validator"]
            self.assertEqual(documentation["status"], "failed")
            self.assertIn("application-code", documentation["evidence"][1])

    def test_local_scan_supplies_resolved_base_and_head_to_documentation_validator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            base = self.initialize_documentation_repository(target)
            (target / "app.py").write_text("print('changed')\n", encoding="utf-8")
            (target / "README.md").write_text("# Fixture\n\nChanged.\n", encoding="utf-8")
            head = self.commit(target, "documented application change")

            with mock.patch.object(MODULE, "producer_module", return_value=self.producer()):
                evidence = MODULE.local_evidence(target, head, "HEAD~1")

            documentation = evidence["results"]["documentation-validation"]["repository-validator"]
            self.assertEqual(documentation["status"], "passed")
            self.assertIn(f"--base-ref {base}", documentation["evidence"][0])
            self.assertIn(f"--head-ref {head}", documentation["evidence"][0])

    def test_selected_authority_placeholders_are_not_run_and_unselected_controls_are_absent(self) -> None:
        evidence = base_evidence()
        selected = {"build": {"mode": "advisory", "authoritative": "repository-build", "supplemental": []}}
        providers = {"repository-build": {"display_name": "Repository Build"}}

        MODULE.add_authoritative_placeholders(evidence, selected, providers)

        self.assertEqual(evidence["results"]["build"]["repository-build"]["status"], "not_run")
        self.assertEqual(set(evidence["results"]), {"build"})

    def test_configuration_presence_is_never_passing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            config = target / ".github" / "dependabot.yml"
            config.parent.mkdir()
            config.write_text("version: 2\n", encoding="utf-8")

            evidence = MODULE.configuration_presence_evidence(config, target, "GitHub Dependabot")

            self.assertEqual(evidence["status"], "not_run")
            self.assertIn("configuration", evidence["reason"].lower())

    def test_fake_requested_revision_makes_all_local_provider_results_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            self.initialize_repository(target)

            evidence = MODULE.local_evidence(target, "f" * 40, "HEAD~1")

            statuses = [
                provider_result["status"]
                for control_results in evidence["results"].values()
                for provider_result in control_results.values()
            ]
            self.assertEqual(set(statuses), {"not_run"})
            self.assertIn("exact", next(iter(evidence["results"]["repository-validation"].values()))["reason"])

    def test_dirty_worktree_makes_all_local_provider_results_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            revision = self.initialize_repository(target)
            (target / "README.md").write_text("dirty\n", encoding="utf-8")

            evidence = MODULE.local_evidence(target, revision, "HEAD~1")

            statuses = [
                provider_result["status"]
                for control_results in evidence["results"].values()
                for provider_result in control_results.values()
            ]
            self.assertEqual(set(statuses), {"not_run"})
            self.assertIn("clean worktree", next(iter(evidence["results"]["repository-validation"].values()))["reason"])


class ArtifactPathTests(unittest.TestCase):
    def test_default_markdown_and_json_artifacts_share_one_utc_timestamp(self) -> None:
        timestamp = datetime(2026, 8, 28, 12, 3, 4, tzinfo=timezone.utc)

        evidence, latest, report = MODULE.default_artifact_paths(Path("/repo"), timestamp)

        self.assertEqual(evidence, Path("/repo/.artifacts/guardrails/evidence-20260828-120304Z.json"))
        self.assertEqual(latest, Path("/repo/.artifacts/guardrails/evidence.json"))
        self.assertEqual(report, Path("/repo/.artifacts/guardrails/scorecard-20260828-120304Z.md"))

    def test_json_output_card_identifies_primary_timestamped_artifacts(self) -> None:
        card = {"version": 2, "status": "ORANGE"}
        evidence = Path("/repo/.artifacts/guardrails/evidence-20260828-120304Z.json")
        report = Path("/repo/.artifacts/guardrails/scorecard-20260828-120304Z.md")

        MODULE.add_artifact_locations(card, evidence, report)

        self.assertEqual(card["artifacts"], {"evidence": str(evidence), "report": str(report)})


if __name__ == "__main__":
    unittest.main()
