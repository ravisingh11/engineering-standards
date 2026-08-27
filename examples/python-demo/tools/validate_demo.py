#!/usr/bin/env python3
"""Validate the sample repository's local contracts."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STANDARDS_ROOT = ROOT.parents[1]
MACHINE_PATH = re.compile(
    rf"(/{'Users'}/|/{'private'}/|\\\\{'Users'}\\\\)"
)
CONFIG_PATHS = {
    "policy": ".guardrails/policy.yaml",
    "catalog": ".guardrails/control-catalog.yaml",
    "ground_truth": ".guardrails/ground-truth-ai.yaml",
    "documentation": ".guardrails/documentation.yaml",
    "change_scope": ".guardrails/change-scope.yaml",
}
RETIRED_CONFIG_PATHS = tuple(
    ".ai" + suffix
    for suffix in (
        "/guardrails.yaml",
        "/control-catalog.yaml",
        "/ground-truth.yaml",
        "/documentation.yaml",
        "/change-scope.yaml",
    )
)
RUNTIME_CONTRACTS = {
    ".guardrails/configure.py": (
        "tooling/configure_guardrails.py",
        (CONFIG_PATHS["policy"], CONFIG_PATHS["catalog"]),
    ),
    ".guardrails/scan.py": (
        "tooling/scan_repository.py",
        (CONFIG_PATHS["policy"], CONFIG_PATHS["catalog"]),
    ),
    ".guardrails/validate_ground_truth.py": (
        "tooling/validators/validate_ground_truth.py",
        (CONFIG_PATHS["ground_truth"],),
    ),
}
WORKFLOW_CONTRACTS = {
    ".github/workflows/validate.yml": (CONFIG_PATHS["ground_truth"],),
    ".github/workflows/guardrails-scorecard.yml": (
        CONFIG_PATHS["policy"],
        CONFIG_PATHS["catalog"],
    ),
    ".github/workflows/dependabot-verification.yml": (
        CONFIG_PATHS["policy"],
        CONFIG_PATHS["catalog"],
    ),
}


def fail_if(condition: bool, message: str, failures: list[str]) -> None:
    if condition:
        failures.append(message)


def load_configs(failures: list[str]) -> dict[str, dict[str, object]]:
    configs: dict[str, dict[str, object]] = {}
    for name, relative in CONFIG_PATHS.items():
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"missing required file: {relative}")
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            failures.append(f"{relative} is not valid JSON-compatible YAML: {error}")
            continue
        if not isinstance(value, dict):
            failures.append(f"{relative} must contain an object")
            continue
        configs[name] = value
    return configs


def validate_path_contracts(
    contracts: dict[str, tuple[str, ...]], failures: list[str]
) -> None:
    for relative, canonical_paths in contracts.items():
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"missing required file: {relative}")
            continue
        content = path.read_text(encoding="utf-8")
        for canonical_path in canonical_paths:
            fail_if(
                canonical_path not in content,
                f"{relative} does not invoke canonical path: {canonical_path}",
                failures,
            )
        for retired_path in RETIRED_CONFIG_PATHS:
            fail_if(
                retired_path in content,
                f"{relative} contains retired path: {retired_path}",
                failures,
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--documentation", action="store_true")
    args = parser.parse_args()
    failures: list[str] = []

    required = ("README.md", "AGENTS.md", "app.py", "test_app.py")
    for relative in required:
        fail_if(not (ROOT / relative).is_file(), f"missing required file: {relative}", failures)

    fail_if((ROOT / ".ai").exists(), "retired configuration directory exists: .ai", failures)
    configs = load_configs(failures)
    policy = configs.get("policy", {})
    catalog = configs.get("catalog", {})
    ground_truth = configs.get("ground_truth", {})

    control_ids = {
        control.get("id")
        for control in catalog.get("controls", [])
        if isinstance(control, dict)
    }
    selected = {
        control_id
        for operation in policy.get("operations", {}).values()
        for enforcement in ("required", "advisory")
        for control_id in operation.get(enforcement, [])
    }
    fail_if(not selected <= control_ids, "policy selects controls absent from catalog", failures)

    documents = ground_truth.get("documents", [])
    if not isinstance(documents, list):
        failures.append("ground-truth policy documents must be a list")
    else:
        for item in documents:
            relative = item.get("path") if isinstance(item, dict) else None
            fail_if(
                not isinstance(relative, str) or not (ROOT / relative).is_file(),
                f"ground-truth path does not exist: {relative}",
                failures,
            )

    runtime_paths = {
        relative: canonical_paths
        for relative, (_, canonical_paths) in RUNTIME_CONTRACTS.items()
    }
    validate_path_contracts(runtime_paths, failures)
    for installed, (source, _) in RUNTIME_CONTRACTS.items():
        fail_if(
            (ROOT / installed).read_bytes() != (STANDARDS_ROOT / source).read_bytes(),
            f"runtime copy differs from distribution source: {installed}",
            failures,
        )
    validate_path_contracts(WORKFLOW_CONTRACTS, failures)

    tracked_text = subprocess.run(
        ["git", "ls-files", "*.md", "*.py", "*.yaml", "*.yml"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    for relative in tracked_text:
        if relative == "tools/validate_demo.py":
            continue
        # A removed tracked file is intentionally absent from the working tree;
        # validate the files that will actually be shipped.
        if not (ROOT / relative).is_file():
            continue
        content = (ROOT / relative).read_text(encoding="utf-8")
        fail_if(bool(MACHINE_PATH.search(content)), f"machine-local path found in {relative}", failures)

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT)
    fail_if(diff_check.returncode != 0, "git diff --check failed", failures)

    if args.documentation:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        fail_if("## Run the example" not in readme, "README is missing the run instructions", failures)
        fail_if("repository-specific ground truth" not in readme, "README does not explain repository ground truth", failures)
        fail_if(not agents.strip(), "AGENTS.md is empty", failures)

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("Demo repository validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
