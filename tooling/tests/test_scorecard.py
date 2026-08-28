from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "guardrail_scorecard.py"
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("guardrail_scorecard", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def fixture(authority: str | None = "passed", supplemental: str | None = "failed", mode: str = "advisory") -> tuple:
    profiles = json.loads((ROOT / "policies" / "profiles.yaml").read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / "policies" / "control-catalog.yaml").read_text(encoding="utf-8"))
    providers = json.loads((ROOT / "policies" / "provider-config.yaml").read_text(encoding="utf-8"))
    policy = {
        "version": 2,
        "name": "test",
        "profiles": ["github"],
        "overrides": {
            "change": {
                "deep-sast": mode,
                "dependency-change-review": "not_activated",
                "platform-secret-protection": "not_activated",
                "dependency-remediation": "not_activated",
            },
            "release": {},
        },
    }
    providers["selections"]["deep-sast"]["supplemental"] = ["snyk-code"]
    results = {}
    for provider_id, status in (("github-codeql", authority), ("snyk-code", supplemental)):
        if status is None:
            continue
        result = {"producer": provider_id, "status": status}
        if status in {"passed", "failed"}:
            result["evidence"] = [f"run: {provider_id}"]
        else:
            result["reason"] = "no result"
        results[provider_id] = result
    evidence = {"version": 2, "subject": {"type": "git-commit", "revision": "abc123"}, "results": {"deep-sast": results}}
    return policy, profiles, catalog, providers, evidence


class ScorecardV2Tests(unittest.TestCase):
    def card(self, authority: str | None = "passed", supplemental: str | None = "failed", mode: str = "advisory", all_controls: bool = False) -> dict:
        policy, profiles, catalog, providers, evidence = fixture(authority, supplemental, mode)
        return MODULE.scorecard(policy, profiles, catalog, providers, evidence, "change", "abc123", subject_type="git-commit", all_catalog_controls=all_controls)

    def test_authoritative_pass_stays_green_despite_supplemental_failure(self) -> None:
        card = self.card()

        self.assertEqual(card["version"], 2)
        self.assertEqual(card["status"], "GREEN")
        self.assertEqual(card["decision"], "allow")
        self.assertEqual(card["controls"][0]["evidence_status"], "passed")
        self.assertEqual(card["controls"][0]["supplemental"][0]["status"], "failed")

    def test_missing_authority_is_orange_advisory_and_red_enforced(self) -> None:
        advisory = self.card(None, "passed", "advisory")
        enforced = self.card(None, "passed", "enforced")

        self.assertEqual((advisory["status"], advisory["decision"]), ("ORANGE", "allow"))
        self.assertEqual((enforced["status"], enforced["decision"]), ("RED", "block"))
        self.assertEqual(advisory["controls"][0]["evidence_status"], "no_result")

    def test_full_catalog_marks_unselected_control_gray(self) -> None:
        card = self.card(all_controls=True)
        row = next(control for control in card["controls"] if control["id"] == "static-quality")

        self.assertEqual(row["readiness"], "GRAY")
        self.assertEqual(row["evidence_status"], "not_activated")

    def test_human_output_renders_capability_and_authoritative_provider_names(self) -> None:
        output = MODULE.render(self.card())

        self.assertIn("Deep SAST — GitHub CodeQL", output)
        self.assertIn("supplemental: Snyk Code=failed", output)
        self.assertNotIn("Activation:", output)

    def test_public_json_recursively_excludes_raw_producer_statuses(self) -> None:
        card = self.card("not_run", None)

        encoded = json.dumps(card, sort_keys=True)
        self.assertNotIn('"not_run"', encoded)
        self.assertNotIn('"missing"', encoded)
        self.assertIn('"no_result"', encoded)


if __name__ == "__main__":
    unittest.main()
