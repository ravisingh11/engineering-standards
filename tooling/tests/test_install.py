from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "install.py"
SPEC = importlib.util.spec_from_file_location("agent_safe_install", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

EXPECTED_CONFIGURATION = {
    Path(".guardrails/policy.yaml"),
    Path(".guardrails/control-catalog.yaml"),
    Path(".guardrails/documentation.yaml"),
    Path(".guardrails/change-scope.yaml"),
    Path(".guardrails/ground-truth-ai.yaml"),
}
LEGACY_CONFIG_PATHS = {
    ".ai/guardrails.yaml": ".guardrails/policy.yaml",
    ".ai/control-catalog.yaml": ".guardrails/control-catalog.yaml",
    ".ai/documentation.yaml": ".guardrails/documentation.yaml",
    ".ai/change-scope.yaml": ".guardrails/change-scope.yaml",
    ".ai/ground-truth.yaml": ".guardrails/ground-truth-ai.yaml",
}


class InstallerTests(unittest.TestCase):
    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve()
            plan = MODULE.install(target, dry_run=True)
            self.assertEqual(len(plan), 14)
            self.assertTrue(
                EXPECTED_CONFIGURATION
                <= {item.destination.relative_to(target) for item in plan}
            )
            self.assertFalse((target / ".ai").exists())
            self.assertFalse((target / ".guardrails").exists())
            self.assertFalse((target / ".agents").exists())

    def test_installs_small_core(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve()
            plan = MODULE.install(target, dry_run=False)
            self.assertTrue(
                EXPECTED_CONFIGURATION
                <= {item.destination.relative_to(target) for item in plan}
            )
            self.assertFalse((target / ".ai").exists())
            self.assertEqual(
                (target / ".guardrails" / "policy.yaml").read_bytes(),
                MODULE.POLICY.read_bytes(),
            )
            self.assertEqual(
                (target / ".guardrails" / "control-catalog.yaml").read_bytes(),
                MODULE.CONTROL_CATALOG.read_bytes(),
            )
            for filename in (
                "documentation.yaml",
                "change-scope.yaml",
                "ground-truth-ai.yaml",
            ):
                with self.subTest(filename=filename):
                    value = json.loads(
                        (target / ".guardrails" / filename).read_text(encoding="utf-8")
                    )
                    self.assertEqual(value["version"], 1)
            self.assertTrue((target / ".guardrails" / "evaluate.py").exists())
            self.assertTrue((target / ".guardrails" / "scorecard.py").exists())
            self.assertTrue((target / ".guardrails" / "configure.py").exists())
            self.assertTrue((target / ".guardrails" / "scan.py").exists())
            self.assertTrue((target / ".guardrails" / "github_evidence.py").exists())
            self.assertTrue((target / ".guardrails" / "producer-manifest.json").exists())
            self.assertTrue((target / ".guardrails" / "providers.yaml").exists())
            self.assertTrue(
                (
                    target
                    / ".agents"
                    / "skills"
                    / "prepare-safe-change"
                    / "SKILL.md"
                ).exists()
            )

    def test_refuses_to_overwrite_existing_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            policy = target / ".guardrails" / "policy.yaml"
            policy.parent.mkdir(parents=True)
            policy.write_text("existing\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                MODULE.install(target, dry_run=False)

    def test_merge_existing_preserves_policy_and_installs_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            policy = target / ".guardrails" / "policy.yaml"
            policy.parent.mkdir(parents=True)
            policy.write_text("existing\n", encoding="utf-8")
            plan = MODULE.install(target, dry_run=False, merge_existing=True)
            self.assertFalse(any(item.destination == policy for item in plan))
            self.assertEqual(policy.read_text(encoding="utf-8"), "existing\n")
            self.assertTrue((target / ".guardrails" / "scan.py").exists())

    def test_refresh_existing_updates_product_without_overwriting_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            MODULE.install(target, dry_run=False)
            selected_configuration = {
                target / ".guardrails" / "policy.yaml": "custom-policy\n",
                target / ".guardrails" / "documentation.yaml": "custom-docs\n",
                target / ".guardrails" / "change-scope.yaml": "custom-scope\n",
                target / ".guardrails" / "ground-truth-ai.yaml": "custom-truth\n",
            }
            for path, content in selected_configuration.items():
                path.write_text(content, encoding="utf-8")
            scan = target / ".guardrails" / "scan.py"
            scan.write_text("stale\n", encoding="utf-8")
            MODULE.install(target, dry_run=False, refresh_existing=True)
            for path, content in selected_configuration.items():
                with self.subTest(path=path):
                    self.assertEqual(path.read_text(encoding="utf-8"), content)
            self.assertNotEqual(scan.read_text(encoding="utf-8"), "stale\n")
            self.assertTrue((target / ".guardrails" / "providers.yaml").exists())

    def test_rejects_each_legacy_configuration_path(self) -> None:
        for old_path, new_path in LEGACY_CONFIG_PATHS.items():
            with self.subTest(old_path=old_path), tempfile.TemporaryDirectory() as directory:
                target = Path(directory)
                legacy = target / old_path
                legacy.parent.mkdir(parents=True)
                legacy.write_text("legacy\n", encoding="utf-8")

                with self.assertRaises(ValueError) as context:
                    MODULE.install(target, dry_run=False)

                message = str(context.exception)
                self.assertIn(f"git mv {old_path} {new_path}", message)
                self.assertFalse((target / ".guardrails").exists())

    def test_rejects_legacy_configuration_in_every_installer_mode(self) -> None:
        modes = {
            "dry-run": {"dry_run": True},
            "merge-existing": {"dry_run": False, "merge_existing": True},
            "refresh-existing": {"dry_run": False, "refresh_existing": True},
        }
        for mode, options in modes.items():
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                target = Path(directory)
                legacy = target / ".ai" / "guardrails.yaml"
                legacy.parent.mkdir(parents=True)
                legacy.write_text("legacy\n", encoding="utf-8")

                with self.assertRaisesRegex(
                    ValueError,
                    r"git mv \.ai/guardrails\.yaml \.guardrails/policy\.yaml",
                ):
                    MODULE.install(target, **options)

                self.assertFalse((target / ".guardrails").exists())

    def test_rejects_legacy_configuration_entry_types(self) -> None:
        for entry_type in ("file", "symlink", "directory"):
            with self.subTest(entry_type=entry_type), tempfile.TemporaryDirectory() as directory:
                target = Path(directory)
                legacy = target / ".ai" / "guardrails.yaml"
                legacy.parent.mkdir(parents=True)
                if entry_type == "file":
                    legacy.write_text("legacy\n", encoding="utf-8")
                elif entry_type == "symlink":
                    legacy.symlink_to(target / "missing-policy.yaml")
                else:
                    legacy.mkdir()

                with self.assertRaisesRegex(ValueError, "git mv"):
                    MODULE.install(target, dry_run=False)

                self.assertFalse((target / ".guardrails").exists())

    def test_reports_all_legacy_configuration_paths_in_one_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            for old_path in LEGACY_CONFIG_PATHS:
                legacy = target / old_path
                legacy.parent.mkdir(parents=True, exist_ok=True)
                legacy.write_text("legacy\n", encoding="utf-8")

            with self.assertRaises(ValueError) as context:
                MODULE.install(target, dry_run=False)

            message = str(context.exception)
            for old_path, new_path in LEGACY_CONFIG_PATHS.items():
                with self.subTest(old_path=old_path):
                    self.assertIn(f"git mv {old_path} {new_path}", message)
            self.assertFalse((target / ".guardrails").exists())

    def test_unrelated_ai_configuration_does_not_block_installation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            application_config = target / ".ai" / "application-config.yaml"
            application_config.parent.mkdir(parents=True)
            application_config.write_text("application-owned\n", encoding="utf-8")

            MODULE.install(target, dry_run=False)

            self.assertEqual(
                application_config.read_text(encoding="utf-8"),
                "application-owned\n",
            )
            self.assertTrue((target / ".guardrails" / "policy.yaml").exists())

    def test_refresh_existing_removes_only_known_legacy_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            legacy = target / ".ai" / "providers.yaml"
            legacy_manifest = target / ".ai" / "producer-manifest.json"
            other = target / ".ai" / "application-config.yaml"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("legacy\n", encoding="utf-8")
            legacy_manifest.write_text("legacy manifest\n", encoding="utf-8")
            other.write_text("keep\n", encoding="utf-8")

            plan = MODULE.install(target, dry_run=False, refresh_existing=True)

            self.assertFalse(legacy.exists())
            self.assertFalse(legacy_manifest.exists())
            self.assertEqual(other.read_text(encoding="utf-8"), "keep\n")
            self.assertTrue(
                any(item.kind == "remove" and item.destination == legacy.resolve() for item in plan)
            )
            self.assertTrue(
                any(item.kind == "remove" and item.destination == legacy_manifest.resolve() for item in plan)
            )

    def test_refresh_existing_migrates_agentic_guardrails_configuration_and_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            legacy_runtime = target / ".agentic-guardrails"
            legacy_runtime.mkdir(parents=True)
            (legacy_runtime / "providers.yaml").write_text("custom providers\n", encoding="utf-8")
            (legacy_runtime / "producer-manifest.json").write_text(
                '{"custom": true}\n', encoding="utf-8"
            )
            (legacy_runtime / "scan.py").write_text("stale runtime\n", encoding="utf-8")
            (legacy_runtime / "consumer-notes.md").write_text("keep me\n", encoding="utf-8")
            legacy_workflow = (
                target / ".github" / "workflows" / "agentic-guardrails-scorecard.yml"
            )
            legacy_workflow.parent.mkdir(parents=True)
            legacy_workflow.write_text(
                "name: Agentic Guardrail Scorecard\nrun: python3 .agentic-guardrails/scan.py\n",
                encoding="utf-8",
            )

            MODULE.install(
                target,
                dry_run=False,
                github_actions=True,
                refresh_existing=True,
            )

            self.assertEqual(
                (target / ".guardrails" / "providers.yaml").read_text(encoding="utf-8"),
                "custom providers\n",
            )
            self.assertEqual(
                (target / ".guardrails" / "producer-manifest.json").read_text(encoding="utf-8"),
                '{"custom": true}\n',
            )
            migrated_workflow = target / ".github" / "workflows" / "guardrails-scorecard.yml"
            self.assertIn("name: Guardrail Scorecard", migrated_workflow.read_text(encoding="utf-8"))
            self.assertIn(".guardrails/scan.py", migrated_workflow.read_text(encoding="utf-8"))
            self.assertFalse((legacy_runtime / "providers.yaml").exists())
            self.assertFalse((legacy_runtime / "producer-manifest.json").exists())
            self.assertFalse((legacy_runtime / "scan.py").exists())
            self.assertFalse(legacy_workflow.exists())
            self.assertEqual(
                (legacy_runtime / "consumer-notes.md").read_text(encoding="utf-8"),
                "keep me\n",
            )

    def test_refresh_existing_preserves_consumer_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            manifest = target / ".guardrails" / "producer-manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("consumer manifest\n", encoding="utf-8")

            MODULE.install(target, dry_run=False, refresh_existing=True)

            self.assertEqual(manifest.read_text(encoding="utf-8"), "consumer manifest\n")

    def test_refresh_dry_run_reports_cleanup_without_removing_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            legacy = target / ".ai" / "providers.yaml"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("legacy\n", encoding="utf-8")

            plan = MODULE.install(target, dry_run=True, refresh_existing=True)

            self.assertTrue(legacy.exists())
            self.assertTrue(any(item.kind == "remove" for item in plan))

    def test_cleanup_refuses_unexpected_legacy_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / ".ai" / "providers.yaml").mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "directory"):
                MODULE.install(target, dry_run=False, refresh_existing=True)

    def test_refresh_existing_preserves_consumer_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            workflow = target / ".github" / "workflows" / "guardrails-attestation.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("consumer-owned\n", encoding="utf-8")

            MODULE.install(target, dry_run=False, github_actions=True, refresh_existing=True)

            self.assertEqual(workflow.read_text(encoding="utf-8"), "consumer-owned\n")
            self.assertTrue(
                (target / ".github" / "workflows" / "guardrails-scorecard.yml").exists()
            )

            scorecard = target / ".github" / "workflows" / "guardrails-scorecard.yml"
            scorecard.write_text("custom-scorecard\n", encoding="utf-8")
            MODULE.install(target, dry_run=False, github_actions=True, refresh_existing=True)
            self.assertEqual(scorecard.read_text(encoding="utf-8"), "custom-scorecard\n")

    def test_refresh_existing_preserves_provider_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            workflow = target / ".github" / "workflows" / "semgrep.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("consumer-customized\n", encoding="utf-8")

            MODULE.install(target, dry_run=False, providers=["semgrep"], refresh_existing=True)

            self.assertEqual(workflow.read_text(encoding="utf-8"), "consumer-customized\n")

    def test_installs_optional_github_actions_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            plan = MODULE.install(
                target,
                dry_run=False,
                github_actions=True,
            )
            workflow = target / ".github" / "workflows" / "guardrails-scorecard.yml"
            self.assertEqual(len(plan), 15)
            self.assertTrue(workflow.exists())
            text = workflow.read_text(encoding="utf-8")
            self.assertIn("permissions:\n  contents: read", text)
            self.assertIn("persist-credentials: false", text)
            self.assertIn(".guardrails/github_evidence.py", text)
            self.assertIn(".guardrails/producer-manifest.json", text)
            self.assertIn(".guardrails/scan.py", text)
            self.assertIn("checks: read", text)

    def test_fresh_install_does_not_wait_for_optional_provider_checks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            MODULE.install(target, dry_run=False)

            manifest = json.loads(
                (target / ".guardrails" / "producer-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            controls = {item["control_id"] for item in manifest["producers"]}

            self.assertNotIn("snyk-code", controls)
            self.assertNotIn("snyk-open-source", controls)
            self.assertNotIn("semgrep", controls)

    def test_installs_verified_provider_template(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            plan = MODULE.install(target, dry_run=False, providers=["semgrep"])
            self.assertEqual(len(plan), 15)
            self.assertTrue((target / ".github" / "workflows" / "semgrep.yml").exists())


if __name__ == "__main__":
    unittest.main()
