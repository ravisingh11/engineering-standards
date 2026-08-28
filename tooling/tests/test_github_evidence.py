from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from urllib.error import URLError
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "github_evidence.py"
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("guardrails_v2_github_evidence", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def contracts() -> tuple[dict, dict, dict, dict]:
    profiles = json.loads((ROOT / "policies" / "profiles.yaml").read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / "policies" / "control-catalog.yaml").read_text(encoding="utf-8"))
    providers = json.loads((ROOT / "policies" / "provider-config.yaml").read_text(encoding="utf-8"))
    selected_change_controls = {
        control_id
        for profile in profiles["profiles"].values()
        for control_id in profile["defaults"]["change"]
    }
    policy = {
        "version": 2,
        "name": "test",
        "profiles": ["core"],
        "overrides": {
            "change": {
                control_id: "not_activated"
                for control_id in selected_change_controls - {"build", "deep-sast"}
            },
            "release": {},
        },
    }
    base = {"activation": "github", "template": None, "template_available": True, "secrets": [], "enabled_by_default": True}
    providers["providers"]["github-build"] = {**base, "display_name": "GitHub Build", "capabilities": ["build"], "checks": {"build": {"check_name": "Build", "workflow": "Build"}}}
    providers["providers"]["external-build"] = {**base, "display_name": "External Build", "activation": "external", "capabilities": ["build"], "checks": {"build": {"check_name": "External Build", "workflow": "External"}}, "enabled_by_default": False}
    providers["selections"]["build"] = {"authoritative": "github-build", "supplemental": ["external-build"]}
    return policy, profiles, catalog, providers


def check_run(
    name: str,
    run_id: int,
    *,
    check_id: int | None = None,
    status: str = "completed",
    conclusion: str | None = "success",
    head_sha: str | None = "abc123",
    app_slug: str | None = "github-actions",
    created_at: str = "2026-08-28T12:00:00Z",
) -> dict:
    check = {
        "id": check_id if check_id is not None else run_id,
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "created_at": created_at,
        "details_url": f"https://github.com/owner/repo/actions/runs/{run_id}/job/1",
        "html_url": f"https://github.com/owner/repo/runs/{run_id}",
    }
    if head_sha is not None:
        check["head_sha"] = head_sha
    if app_slug is not None:
        check["app"] = {"slug": app_slug}
    return check


def request_for(payload: dict, workflows: dict[int, str] | None = None):
    workflows = workflows or {}

    def request(url: str, token: str) -> dict:
        if "check-runs" in url:
            return payload
        run_id = int(url.rsplit("/", 1)[1])
        return {"id": run_id, "name": workflows.get(run_id, "Wrong Workflow")}

    return request


class GitHubEvidenceV2Tests(unittest.TestCase):
    def collect(self, payload: dict, workflows: dict[int, str] | None = None) -> dict:
        policy, profiles, catalog, providers = contracts()
        with patch.object(MODULE, "_request", side_effect=request_for(payload, workflows)):
            return MODULE.collect_checks("owner/repo", "abc123", "token", policy, profiles, catalog, providers, "change")

    def test_collects_only_proven_authoritative_and_supplemental_git_commit_checks(self) -> None:
        payload = {"check_runs": [check_run("Build", 101), check_run("External Build", 102)]}

        evidence = self.collect(payload, {101: "Build", 102: "External"})

        self.assertEqual(evidence["subject"], {"type": "git-commit", "revision": "abc123"})
        self.assertEqual(evidence["results"]["build"]["github-build"]["status"], "passed")
        self.assertEqual(evidence["results"]["build"]["external-build"]["status"], "passed")
        self.assertNotIn("deep-sast", evidence["results"])

    def test_waits_only_for_newest_selected_provider_check_runs(self) -> None:
        policy, profiles, catalog, providers = contracts()
        queued = {"check_runs": [
            check_run("Build", 201, check_id=1, status="completed", conclusion="success"),
            check_run("Build", 202, check_id=2, status="in_progress", conclusion=None),
            check_run("External Build", 203, status="completed", conclusion="success"),
        ]}
        completed = {"check_runs": [
            check_run("Build", 201, check_id=1, status="completed", conclusion="success"),
            check_run("Build", 202, check_id=2, status="completed", conclusion="success"),
            check_run("External Build", 203, status="completed", conclusion="success"),
        ]}
        responses = [queued, completed, {"id": 202, "name": "Build"}, {"id": 203, "name": "External"}]

        with patch.object(MODULE, "_request", side_effect=responses) as request:
            with patch.object(MODULE.time, "monotonic", side_effect=[0, 1, 2]):
                with patch.object(MODULE.time, "sleep"):
                    evidence = MODULE.collect_checks(
                        "owner/repo", "abc123", "token", policy, profiles, catalog, providers, "change", wait_seconds=30
                    )

        check_requests = [call.args[0] for call in request.call_args_list if "check-runs" in call.args[0]]
        self.assertEqual(len(check_requests), 2)
        self.assertIn("runs/202", evidence["results"]["build"]["github-build"]["evidence"][0])

    def test_newest_duplicate_is_selected_by_numeric_id_not_mutable_timestamps(self) -> None:
        payload = {"check_runs": [
            check_run("Build", 301, check_id=9, conclusion="failure", created_at="2026-08-28T13:00:00Z"),
            check_run("Build", 302, check_id=10, conclusion="success", created_at="2026-08-28T12:00:00Z"),
        ]}

        evidence = self.collect(payload, {302: "Build"})

        result = evidence["results"]["build"]["github-build"]
        self.assertEqual(result["status"], "passed")
        self.assertIn("runs/302", result["evidence"][0])

    def test_missing_or_skipped_check_is_not_run(self) -> None:
        for payload, reason in (
            ({"check_runs": []}, "did not report"),
            ({"check_runs": [check_run("Build", 401, conclusion="skipped")]}, "skipped"),
        ):
            with self.subTest(reason=reason):
                evidence = self.collect(payload, {401: "Build"})
                result = evidence["results"]["build"]["github-build"]
                self.assertEqual(result["status"], "not_run")
                self.assertIn(reason, result["reason"])

    def test_wrong_or_missing_head_sha_is_untrusted(self) -> None:
        for head_sha in ("different", None):
            with self.subTest(head_sha=head_sha):
                evidence = self.collect({"check_runs": [check_run("Build", 501, head_sha=head_sha)]})
                result = evidence["results"]["build"]["github-build"]
                self.assertEqual(result["status"], "not_run")
                self.assertIn("exact revision", result["reason"])

    def test_non_github_actions_app_is_untrusted(self) -> None:
        evidence = self.collect({"check_runs": [check_run("Build", 601, app_slug="codecov")]})

        result = evidence["results"]["build"]["github-build"]
        self.assertEqual(result["status"], "not_run")
        self.assertIn("github-actions", result["reason"])

    def test_declared_workflow_name_must_match_actions_run(self) -> None:
        evidence = self.collect({"check_runs": [check_run("Build", 701)]}, {701: "Different Workflow"})

        result = evidence["results"]["build"]["github-build"]
        self.assertEqual(result["status"], "not_run")
        self.assertIn("workflow", result["reason"].lower())

    def test_workflow_provenance_lookup_failure_is_not_run(self) -> None:
        policy, profiles, catalog, providers = contracts()

        def request(url: str, token: str) -> dict:
            if "check-runs" in url:
                return {"check_runs": [check_run("Build", 702)]}
            raise URLError("workflow lookup unavailable")

        with patch.object(MODULE, "_request", side_effect=request):
            evidence = MODULE.collect_checks(
                "owner/repo", "abc123", "token", policy, profiles, catalog,
                providers, "change",
            )

        result = evidence["results"]["build"]["github-build"]
        self.assertEqual(result["status"], "not_run")
        self.assertIn("provenance", result["reason"].lower())

    def test_canonical_semgrep_check_fans_out_to_core_and_github_capabilities(self) -> None:
        policy, profiles, catalog, providers = contracts()
        policy["profiles"].append("github")
        policy["overrides"]["change"]["build"] = "not_activated"
        policy["overrides"]["change"]["custom-static-analysis"] = "advisory"
        policy["overrides"]["change"]["deep-sast"] = "advisory"

        with patch.object(MODULE, "_request", side_effect=request_for(
            {"check_runs": [check_run("Semgrep", 801)]}, {801: "Semgrep"},
        )):
            evidence = MODULE.collect_checks(
                "owner/repo", "abc123", "token", policy, profiles, catalog,
                providers, "change",
            )

        core_result = evidence["results"]["custom-static-analysis"]["semgrep-app"]
        github_result = evidence["results"]["deep-sast"]["semgrep-app"]
        self.assertEqual(core_result["status"], "passed")
        self.assertEqual(github_result, core_result)
        self.assertIsNot(github_result, core_result)

    def test_conflicting_check_name_mapping_is_rejected_before_collection(self) -> None:
        policy, profiles, catalog, providers = contracts()
        providers["providers"]["external-build"]["checks"]["build"]["check_name"] = "Build"

        with self.assertRaisesRegex(ValueError, "ambiguous check name"):
            MODULE.expected_checks(policy, profiles, catalog, providers, "change")

    def test_collector_rejects_non_git_commit_subjects(self) -> None:
        policy, profiles, catalog, providers = contracts()

        with self.assertRaisesRegex(ValueError, "git-commit only"):
            MODULE.collect_checks(
                "owner/repo", "abc123", "token", policy, profiles, catalog,
                providers, "change", subject_type="artifact",
            )


if __name__ == "__main__":
    unittest.main()
