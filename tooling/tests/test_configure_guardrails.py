from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "configure_guardrails.py"
SPEC = importlib.util.spec_from_file_location("configure_guardrails", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ConfigureGuardrailsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = {
            "version": 1,
            "name": "test",
            "operations": {
                "change": {"required": ["build"], "advisory": []},
                "release": {"required": ["build"], "advisory": []},
            },
        }

    def test_defaults_use_installed_guardrails_configuration(self) -> None:
        self.assertEqual(MODULE.DEFAULT_POLICY, Path(".guardrails/policy.yaml"))
        self.assertEqual(MODULE.DEFAULT_CATALOG, Path(".guardrails/control-catalog.yaml"))

    def test_set_advisory_removes_required(self) -> None:
        MODULE.set_mode(self.policy, "build", "advisory", ["change"])
        self.assertEqual(self.policy["operations"]["change"], {"required": [], "advisory": ["build"]})

    def test_enforced_adds_to_required_policy_list(self) -> None:
        MODULE.set_mode(self.policy, "build", "enforced", ["change", "release"])
        self.assertEqual(self.policy["operations"]["change"], {"required": ["build"], "advisory": []})
        self.assertEqual(self.policy["operations"]["release"], {"required": ["build"], "advisory": []})

    def test_observe_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.set_mode(self.policy, "build", "observe", ["change"])

    def test_invalid_mode_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.set_mode(self.policy, "build", "blocking", ["change"])

    def test_provider_config_can_sync_enabled_controls(self) -> None:
        catalog = {"semgrep": {"id": "semgrep"}}
        providers = {
            "version": 1,
            "providers": {
                "semgrep": {
                    "enabled": True,
                    "controls": {
                        "semgrep": {
                            "check_name": "Semgrep",
                            "workflow": "Semgrep",
                            "wait_for": False,
                            "change": "advisory",
                            "release": "enforced",
                        }
                    },
                }
            },
        }
        MODULE.validate_provider_config(providers, catalog)
        manifest = {"version": 1, "producers": []}
        policy = {
            "version": 1,
            "name": "test",
            "operations": {
                "change": {"required": [], "advisory": []},
                "release": {"required": [], "advisory": []},
            },
        }
        MODULE.sync_provider_configuration(policy, manifest, providers)
        self.assertEqual(policy["operations"]["change"]["advisory"], ["semgrep"])
        self.assertEqual(policy["operations"]["release"]["required"], ["semgrep"])
        self.assertEqual(manifest["producers"][0]["check_name"], "Semgrep")

    def test_provider_config_rejects_unknown_controls(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown control"):
            MODULE.validate_provider_config(
                {
                    "version": 1,
                    "providers": {
                        "tool": {
                            "enabled": False,
                            "controls": {
                                "unknown": {
                                    "check_name": "Tool",
                                    "workflow": "Tool",
                                    "wait_for": False,
                                    "change": "advisory",
                                    "release": "advisory",
                                }
                            },
                        }
                    },
                },
                {},
            )

    def test_provider_sync_preserves_custom_policy_operations(self) -> None:
        catalog = {"semgrep": {"id": "semgrep"}}
        providers = {
            "version": 1,
            "providers": {
                "semgrep": {
                    "enabled": True,
                    "controls": {
                        "semgrep": {
                            "check_name": "Semgrep",
                            "workflow": "Semgrep",
                            "wait_for": False,
                            "change": "advisory",
                            "release": "advisory",
                        }
                    },
                }
            },
        }
        policy = {
            "version": 1,
            "name": "test",
            "operations": {
                "change": {"required": [], "advisory": []},
                "release": {"required": [], "advisory": []},
                "deploy": {"required": ["custom-control"], "advisory": []},
            },
        }
        manifest = {"version": 1, "producers": []}

        MODULE.sync_provider_configuration(policy, manifest, providers)

        self.assertEqual(policy["operations"]["deploy"]["required"], ["custom-control"])


if __name__ == "__main__":
    unittest.main()
