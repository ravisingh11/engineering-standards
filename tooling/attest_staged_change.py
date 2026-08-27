#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

POLICY_PATH = Path(".guardrails/policy.yaml")
SCOPE_POLICY_PATH = Path(".guardrails/change-scope.yaml")


def git_output(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def git_paths(root: Path, *arguments: str) -> list[str]:
    raw = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in raw.split(b"\0")
        if item
    ]


def build_evidence(
    revision: str,
    repository_validation: int,
    staged_diff_check: int,
    documentation_validation: int,
    change_scope: dict[str, Any],
) -> dict[str, Any]:
    passed = repository_validation == 0 and staged_diff_check == 0
    return {
        "version": 1,
        "subject": {
            "type": "git-tree",
            "revision": revision,
        },
        "checks": {
            "repository-validation": {
                "producer": "local pre-commit validation",
                "status": "passed" if passed else "failed",
                "evidence": [
                    "command: python3 tooling/validators/validate_repository.py "
                    f"(exit {repository_validation})",
                    "command: git diff --cached --check "
                    f"(exit {staged_diff_check})",
                ],
            },
            "documentation": {
                "producer": "local documentation validation",
                "status": "passed" if documentation_validation == 0 else "failed",
                "evidence": [
                    "command: python3 tooling/validators/validate_documentation.py "
                    f"(exit {documentation_validation})"
                ],
            },
            "change-scope": {
                "producer": "local file and line scope inspection",
                "status": change_scope["status"],
                "evidence": [
                    "metrics: "
                    + json.dumps(
                        change_scope["metrics"],
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    f"advisory findings: {len(change_scope['findings'])}",
                ],
            },
        },
    }


def load_module(path: Path, name: str) -> Any:
    specification = importlib.util.spec_from_file_location(
        name,
        path,
    )
    if not specification or not specification.loader:
        raise ValueError(f"cannot load staged module from {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def create_staged_snapshot(root: Path, destination: Path) -> None:
    prefix = f"{destination}{os.sep}"
    subprocess.run(
        [
            "git",
            "checkout-index",
            "--all",
            "--force",
            f"--prefix={prefix}",
        ],
        cwd=root,
        check=True,
    )


def run(root: Path) -> int:
    revision = git_output(root, "write-tree")
    with tempfile.TemporaryDirectory(prefix="guardrails-staged-") as directory:
        snapshot = Path(directory)
        create_staged_snapshot(root, snapshot)
        changed_files = git_paths(
            root,
            "diff",
            "--cached",
            "--name-only",
            "--diff-filter=ACMRD",
            "-z",
        )

        print(f"Guardrails: validating staged tree {revision}")
        documentation_validation = subprocess.run(
            [
                sys.executable,
                "tooling/validators/validate_documentation.py",
                *[f"--changed-file={path}" for path in changed_files],
            ],
            cwd=snapshot,
            check=False,
        ).returncode
        repository_validation = subprocess.run(
            [sys.executable, "tooling/validators/validate_repository.py"],
            cwd=snapshot,
            check=False,
        ).returncode
        staged_diff_check = subprocess.run(
            ["git", "diff", "--cached", "--check"],
            cwd=root,
            check=False,
        ).returncode

        scope = load_module(
            snapshot / "validators" / "inspect_change_scope.py",
            "staged_change_scope",
        )
        scope_policy = scope.load_policy(snapshot / SCOPE_POLICY_PATH)
        scope_result = scope.staged(root, scope_policy)
        print(scope.render(scope_result), end="")

        evaluator = load_module(
            snapshot / "attest" / "evaluate.py",
            "staged_agent_safe_evaluator",
        )
        policy = evaluator.load_document(snapshot / POLICY_PATH)
        evidence = build_evidence(
            revision,
            repository_validation,
            staged_diff_check,
            documentation_validation,
            scope_result,
        )
        result = evaluator.evaluate(
            policy,
            evidence,
            "change",
            revision,
            "git-tree",
        )
        print(evaluator.render(result), end="")
        return 0 if result["decision"] == "allow" else 1


def main() -> int:
    try:
        root = Path(git_output(Path.cwd(), "rev-parse", "--show-toplevel"))
        return run(root)
    except (OSError, subprocess.CalledProcessError, ValueError, json.JSONDecodeError) as error:
        print(f"Guardrails configuration error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
