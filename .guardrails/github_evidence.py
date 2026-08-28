#!/usr/bin/env python3
"""Collect nested Guardrails v2 evidence from selected GitHub checks."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CONCLUSIONS = {
    "success": "passed",
    "failure": "failed",
    "cancelled": "blocked",
    "timed_out": "blocked",
    "action_required": "blocked",
    "stale": "blocked",
    "neutral": "not_run",
    "skipped": "not_run",
}


def evaluator_module() -> Any:
    path = ROOT / "guardrails" / "evaluate.py"
    if not path.exists():
        path = ROOT / ".guardrails" / "evaluate.py"
    spec = importlib.util.spec_from_file_location("guardrails_v2_evaluator", path)
    if not spec or not spec.loader:
        raise ValueError(f"cannot load evaluator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def check_run_evidence(control_id: str, provider_name: str, check: dict[str, Any]) -> dict[str, Any]:
    conclusion = check.get("conclusion") or "in_progress"
    status = CONCLUSIONS.get(conclusion, "not_run")
    url = check.get("html_url") or check.get("details_url") or "unavailable"
    result: dict[str, Any] = {
        "producer": f"GitHub Check: {check.get('name', provider_name)}",
        "status": status,
    }
    if status in {"passed", "failed"}:
        result["evidence"] = [f"{check.get('name', control_id)}: {conclusion}; {url}"]
    else:
        result["reason"] = f"GitHub check concluded {conclusion}; the provider did not return a passing result."
        if check.get("name"):
            result["evidence"] = [f"{check['name']}: {conclusion}; {url}"]
    return result


def _request(url: str, token: str) -> dict[str, Any]:
    request = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def expected_checks(
    policy: dict[str, Any], profiles: dict[str, Any], catalog: dict[str, Any],
    provider_config: dict[str, Any], operation: str,
) -> dict[str, dict[str, Any]]:
    selected, _, providers = evaluator_module().effective_controls(
        policy, profiles, catalog, provider_config, operation, "git-commit"
    )
    expected: dict[str, dict[str, Any]] = {}
    for control_id, selection in selected.items():
        for provider_id in [selection["authoritative"], *selection["supplemental"]]:
            check = providers[provider_id].get("checks", {}).get(control_id)
            if check:
                check_name = check["check_name"]
                contract = {
                    "check_name": check_name,
                    "workflow": check["workflow"],
                    "provider_id": provider_id,
                    "control_ids": [control_id],
                }
                existing = expected.get(check_name)
                if existing is not None and (
                    existing["provider_id"] != provider_id
                    or existing["workflow"] != check["workflow"]
                ):
                    raise ValueError(
                        f"ambiguous check name {check_name!r} is reused by different workflow/provider contracts"
                    )
                if existing is None:
                    expected[check_name] = contract
                elif control_id not in existing["control_ids"]:
                    existing["control_ids"].append(control_id)
    return expected


def newest_by_name(
    check_runs: list[dict[str, Any]], expected_names: set[str]
) -> dict[str, dict[str, Any]]:
    newest: dict[str, dict[str, Any]] = {}

    def freshness(check: dict[str, Any]) -> tuple[int, Any]:
        check_id = check.get("id")
        if isinstance(check_id, int) and not isinstance(check_id, bool):
            return (1, check_id)
        if isinstance(check_id, str) and check_id.isdigit():
            return (1, int(check_id))
        return (0, check.get("created_at") or "")

    for check in check_runs:
        name = check.get("name")
        if name not in expected_names:
            continue
        current = newest.get(name)
        if current is None or freshness(check) > freshness(current):
            newest[name] = check
    return newest


def not_run(check_name: str, reason: str) -> dict[str, Any]:
    return {
        "producer": f"GitHub Check: {check_name}",
        "status": "not_run",
        "reason": reason,
    }


def proven_check_evidence(
    repo: str,
    revision: str,
    token: str,
    contract: dict[str, Any],
    check: dict[str, Any],
    provider_name: str,
) -> dict[str, Any]:
    check_name = contract["check_name"]
    if check.get("head_sha") != revision:
        return not_run(check_name, "The GitHub check did not bind to the exact revision under evaluation.")
    app = check.get("app")
    if not isinstance(app, dict) or app.get("slug") != "github-actions":
        return not_run(check_name, "The check provenance is not the github-actions application.")
    details_url = check.get("details_url")
    match = re.search(r"/actions/runs/([0-9]+)(?:/|$)", details_url or "")
    if not match:
        return not_run(check_name, "The check details URL does not identify a GitHub Actions workflow run.")
    run_id = int(match.group(1))
    try:
        workflow_run = _request(
            f"https://api.github.com/repos/{repo}/actions/runs/{run_id}", token
        )
    except (HTTPError, URLError, OSError, ValueError):
        return not_run(check_name, "The GitHub Actions workflow provenance could not be verified.")
    if workflow_run.get("name") != contract["workflow"]:
        return not_run(check_name, "The GitHub Actions workflow name does not match the declared provider contract.")
    if workflow_run.get("id") is not None and workflow_run.get("id") != run_id:
        return not_run(check_name, "The GitHub Actions workflow run id does not match the check details URL.")
    return check_run_evidence(check_name, provider_name, check)


def collect_checks(
    repo: str,
    revision: str,
    token: str,
    policy: dict[str, Any],
    profiles: dict[str, Any],
    catalog: dict[str, Any],
    provider_config: dict[str, Any],
    operation: str,
    wait_seconds: int = 0,
    subject_type: str = "git-commit",
) -> dict[str, Any]:
    if subject_type != "git-commit":
        raise ValueError("GitHub check collection is git-commit only")
    expected = expected_checks(policy, profiles, catalog, provider_config, operation)
    providers = provider_config["providers"]
    check_names = set(expected)
    url = f"https://api.github.com/repos/{repo}/commits/{revision}/check-runs?per_page=100"
    deadline = time.monotonic() + max(0, wait_seconds)
    check_runs: list[dict[str, Any]] = []
    while True:
        payload = _request(url, token)
        check_runs = payload.get("check_runs", [])
        newest = newest_by_name(check_runs, check_names)
        complete = check_names.issubset(newest) and all(
            check.get("status") == "completed" for check in newest.values()
        )
        if complete or time.monotonic() >= deadline:
            break
        time.sleep(10)

    newest = newest_by_name(check_runs, check_names)

    results: dict[str, dict[str, dict[str, Any]]] = {}
    for check_name, contract in expected.items():
        provider_id = contract["provider_id"]
        check = newest.get(check_name)
        if check is None:
            result = not_run(check_name, "The selected provider check did not report this revision.")
        else:
            result = proven_check_evidence(
                repo, revision, token, contract, check,
                providers[provider_id]["display_name"],
            )
        for control_id in contract["control_ids"]:
            results.setdefault(control_id, {})[provider_id] = copy.deepcopy(result)
    return {"version": 2, "subject": {"type": "git-commit", "revision": revision}, "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect selected Guardrails v2 GitHub check evidence")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--revision", required=True)
    parser.add_argument("--token", default=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--policy", type=Path, default=Path(".guardrails/policy.yaml"))
    parser.add_argument("--profiles", type=Path, default=Path(".guardrails/profiles.yaml"))
    parser.add_argument("--catalog", type=Path, default=Path(".guardrails/control-catalog.yaml"))
    parser.add_argument("--providers", type=Path, default=Path(".guardrails/providers.yaml"))
    parser.add_argument("--operation", choices=("change", "release"), default="change")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wait-seconds", type=int, default=0)
    args = parser.parse_args()
    if not args.repo or not args.token:
        print("ERROR --repo and --token are required", file=sys.stderr)
        return 2
    try:
        evidence = collect_checks(
            args.repo, args.revision, args.token, load(args.policy), load(args.profiles),
            load(args.catalog), load(args.providers), args.operation,
            wait_seconds=args.wait_seconds,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 0
    except (OSError, ValueError, KeyError, HTTPError, URLError) as error:
        print(f"ERROR collecting GitHub evidence: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
