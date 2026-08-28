from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tooling" / "validators" / "validate_repository.py"
SPEC = importlib.util.spec_from_file_location("validate_repository", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def load(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


class GuardrailsContractValidationTests(unittest.TestCase):
    def validator(self, name: str):
        validator = getattr(MODULE, name, None)
        self.assertIsNotNone(validator, f"missing contract validator: {name}")
        return validator

    def catalog(self) -> dict[str, dict]:
        return {
            control["id"]: control
            for control in load("policies/control-catalog.yaml")["controls"]
        }

    def providers(self) -> dict:
        return load("policies/provider-config.yaml")["providers"]

    def test_canonical_provider_contract_is_valid(self) -> None:
        self.validator("validate_provider_document")(
            load("policies/provider-config.yaml"), self.catalog()
        )

    def test_core_and_github_default_providers_are_exact(self) -> None:
        providers = load("policies/provider-config.yaml")["providers"]
        enabled = {
            provider_id
            for provider_id, definition in providers.items()
            if definition["enabled_by_default"]
        }

        self.assertEqual(
            enabled,
            {
                "repository-validator",
                "repository-build",
                "repository-unit-tests",
                "repository-changed-code-coverage",
                "semgrep-ce",
                "gitleaks",
                "github-codeql",
                "github-dependency-review",
                "github-secret-protection",
                "github-dependabot",
                "github-artifact-attestations",
            },
        )

    def test_rejects_unknown_authoritative_provider(self) -> None:
        providers = load("policies/provider-config.yaml")
        providers["selections"]["build"]["authoritative"] = "unknown"

        with self.assertRaisesRegex(ValueError, "unknown provider"):
            self.validator("validate_provider_document")(providers, self.catalog())

    def test_rejects_empty_or_multiple_authoritative_providers(self) -> None:
        for invalid in ("", ["repository-build", "repository-unit-tests"]):
            with self.subTest(authoritative=invalid):
                providers = load("policies/provider-config.yaml")
                providers["selections"]["build"]["authoritative"] = invalid
                with self.assertRaisesRegex(ValueError, "authoritative"):
                    self.validator("validate_provider_document")(providers, self.catalog())

    def test_rejects_authority_without_selected_capability(self) -> None:
        providers = load("policies/provider-config.yaml")
        providers["selections"]["build"]["authoritative"] = "repository-unit-tests"

        with self.assertRaisesRegex(ValueError, "does not provide build"):
            self.validator("validate_provider_document")(providers, self.catalog())

    def test_rejects_duplicate_supplemental_providers(self) -> None:
        providers = load("policies/provider-config.yaml")
        providers["selections"]["deep-sast"]["supplemental"] = ["snyk-code", "snyk-code"]

        with self.assertRaisesRegex(ValueError, "duplicate supplemental"):
            self.validator("validate_provider_document")(providers, self.catalog())

    def test_rejects_authority_reused_as_supplemental(self) -> None:
        providers = load("policies/provider-config.yaml")
        providers["selections"]["deep-sast"]["supplemental"] = ["github-codeql"]

        with self.assertRaisesRegex(ValueError, "also supplemental"):
            self.validator("validate_provider_document")(providers, self.catalog())

    def test_provider_schema_boundaries_match_handwritten_validation(self) -> None:
        schema = load("guardrails/providers.schema.json")
        properties = schema["$defs"]["provider"]["properties"]
        self.assertEqual(properties["capabilities"]["minItems"], 1)
        self.assertEqual(properties["template"]["minLength"], 1)
        self.assertEqual(properties["template"]["maxLength"], 200)

        providers = load("policies/provider-config.yaml")
        providers["providers"]["repository-build"]["capabilities"] = []
        with self.assertRaisesRegex(ValueError, "capabilities"):
            self.validator("validate_provider_document")(providers, self.catalog())

        providers = load("policies/provider-config.yaml")
        providers["providers"]["repository-build"]["template"] = "x" * 201
        with self.assertRaisesRegex(ValueError, "template"):
            self.validator("validate_provider_document")(providers, self.catalog())

    def test_nested_evidence_contract_is_valid(self) -> None:
        self.validator("validate_evidence_document")(
            load("guardrails/evidence-example.yaml"), self.catalog(), self.providers()
        )

    def test_rejects_malformed_nested_evidence(self) -> None:
        evidence = load("guardrails/evidence-example.yaml")
        result = next(iter(next(iter(evidence["results"].values())).values()))
        del result["producer"]

        with self.assertRaisesRegex(ValueError, "producer"):
            self.validator("validate_evidence_document")(
                evidence, self.catalog(), self.providers()
            )

    def test_rejects_flat_evidence_results(self) -> None:
        evidence = load("guardrails/evidence-example.yaml")
        evidence["results"] = {
            "unit-tests": {
                "producer": "repository test suite",
                "status": "passed",
                "evidence": ["command: python3 -m unittest"],
            }
        }

        with self.assertRaisesRegex(ValueError, "provider"):
            self.validator("validate_evidence_document")(
                evidence, self.catalog(), self.providers()
            )

    def test_evidence_rejects_unknown_control(self) -> None:
        evidence = load("guardrails/evidence-example.yaml")
        result = evidence["results"].pop("unit-tests")
        evidence["results"]["unknown-control"] = result

        with self.assertRaisesRegex(ValueError, "unknown control"):
            self.validator("validate_evidence_document")(
                evidence, self.catalog(), self.providers()
            )

    def test_evidence_rejects_unknown_provider(self) -> None:
        evidence = load("guardrails/evidence-example.yaml")
        result = evidence["results"]["unit-tests"].pop("repository-unit-tests")
        evidence["results"]["unit-tests"]["unknown-provider"] = result

        with self.assertRaisesRegex(ValueError, "unknown provider"):
            self.validator("validate_evidence_document")(
                evidence, self.catalog(), self.providers()
            )

    def test_evidence_rejects_provider_without_control_capability(self) -> None:
        evidence = load("guardrails/evidence-example.yaml")
        result = evidence["results"]["unit-tests"].pop("repository-unit-tests")
        evidence["results"]["unit-tests"]["repository-build"] = result

        with self.assertRaisesRegex(ValueError, "does not provide unit-tests"):
            self.validator("validate_evidence_document")(
                evidence, self.catalog(), self.providers()
            )

    def test_evidence_rejects_subject_type_mismatch(self) -> None:
        evidence = load("guardrails/evidence-example.yaml")
        evidence["subject"]["type"] = "artifact"

        with self.assertRaisesRegex(ValueError, "requires git-commit subject"):
            self.validator("validate_evidence_document")(
                evidence, self.catalog(), self.providers()
            )

    def test_evidence_provider_map_nonempty_boundary_matches_schema(self) -> None:
        schema = load("guardrails/evidence.schema.json")
        self.assertEqual(schema["$defs"]["providerResults"]["minProperties"], 1)

        evidence = load("guardrails/evidence-example.yaml")
        evidence["results"]["unit-tests"] = {}
        with self.assertRaisesRegex(ValueError, "at least one provider"):
            self.validator("validate_evidence_document")(
                evidence, self.catalog(), self.providers()
            )

    def test_evidence_optional_field_boundaries_match_schema(self) -> None:
        evidence = load("guardrails/evidence-example.yaml")
        result = evidence["results"]["unit-tests"]["repository-unit-tests"]
        result["status"] = "blocked"
        result["reason"] = "provider unavailable"
        result["evidence"] = []

        with self.assertRaisesRegex(ValueError, "evidence records"):
            self.validator("validate_evidence_document")(
                evidence, self.catalog(), self.providers()
            )

        evidence = load("guardrails/evidence-example.yaml")
        result = evidence["results"]["unit-tests"]["repository-unit-tests"]
        result["reason"] = ""
        with self.assertRaisesRegex(ValueError, "reason"):
            self.validator("validate_evidence_document")(
                evidence, self.catalog(), self.providers()
            )

    def test_evidence_rejects_whitespace_only_records(self) -> None:
        evidence = load("guardrails/evidence-example.yaml")
        result = evidence["results"]["unit-tests"]["repository-unit-tests"]
        result["evidence"] = ["   "]

        with self.assertRaisesRegex(ValueError, "evidence records"):
            self.validator("validate_evidence_document")(
                evidence, self.catalog(), self.providers()
            )

    def test_evidence_record_nonblank_boundary_matches_schema(self) -> None:
        schema = load("guardrails/evidence.schema.json")
        record_schema = schema["$defs"]["result"]["properties"]["evidence"]["items"]

        self.assertEqual(record_schema.get("pattern"), "\\S")

    def test_policy_rejects_invalid_override_mode(self) -> None:
        policy = load("guardrails/baseline.yaml")
        policy["overrides"]["change"]["build"] = "required"

        with self.assertRaisesRegex(ValueError, "override"):
            self.validator("validate_policy_document")(
                policy, {"core", "github"}, set(self.catalog())
            )

    def test_policy_rejects_unknown_override_control(self) -> None:
        policy = load("guardrails/baseline.yaml")
        policy["overrides"]["change"]["unknown-control"] = "advisory"

        with self.assertRaisesRegex(ValueError, "unknown control"):
            self.validator("validate_policy_document")(
                policy, {"core", "github"}, set(self.catalog())
            )


if __name__ == "__main__":
    unittest.main()
