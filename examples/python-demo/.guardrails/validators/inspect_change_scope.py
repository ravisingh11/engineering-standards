#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / ".guardrails" / "change-scope.yaml"
LIMIT_KEYS = (
    "max_files",
    "max_added_lines",
    "max_changed_lines",
    "max_added_lines_per_file",
)


def load_policy(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path} must use JSON-compatible YAML: {error}") from error
    if not isinstance(value, dict) or set(value) != {"version", "limits", "exclude"}:
        raise ValueError("change-scope policy requires version, limits, and exclude")
    if value["version"] != 1:
        raise ValueError("change-scope policy version must be 1")
    limits = value["limits"]
    if not isinstance(limits, dict) or set(limits) != set(LIMIT_KEYS):
        raise ValueError(
            "change-scope limits must define " + ", ".join(LIMIT_KEYS)
        )
    if any(type(limits[key]) is not int or limits[key] < 1 for key in LIMIT_KEYS):
        raise ValueError("change-scope limits must be positive integers")
    exclude = value["exclude"]
    if not isinstance(exclude, list) or not all(
        isinstance(pattern, str) and pattern for pattern in exclude
    ):
        raise ValueError("change-scope exclude must be a list of path patterns")
    return value


def glob_regex(pattern: str) -> re.Pattern[str]:
    index = 0
    output = ""
    while index < len(pattern):
        if pattern[index : index + 3] == "**/":
            output += "(?:.*/)?"
            index += 3
        elif pattern[index : index + 2] == "**":
            output += ".*"
            index += 2
        elif pattern[index] == "*":
            output += "[^/]*"
            index += 1
        else:
            output += re.escape(pattern[index])
            index += 1
    return re.compile(f"^{output}$")


def excluded(path: str, patterns: list[str]) -> bool:
    return any(glob_regex(pattern).fullmatch(path) for pattern in patterns)


def git_bytes(root: Path, arguments: list[str]) -> bytes:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout


def git_text(root: Path, arguments: list[str]) -> str:
    return git_bytes(root, arguments).decode().strip()


def resolve_commit(root: Path, reference: str) -> str:
    if (
        not reference
        or reference.startswith("-")
        or any(character.isspace() for character in reference)
    ):
        raise ValueError(f"unsafe Git reference: {reference!r}")
    value = git_text(
        root,
        [
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{reference}^{{commit}}",
        ],
    )
    if not re.fullmatch(r"[0-9a-f]{40,64}", value):
        raise ValueError(f"Git returned an invalid commit for {reference!r}")
    return value


def decode(value: bytes) -> str:
    return value.decode("utf-8", errors="surrogateescape")


def parse_numstat(raw: bytes) -> list[dict[str, Any]]:
    tokens = raw.split(b"\0")
    if tokens and tokens[-1] == b"":
        tokens.pop()
    records: list[dict[str, Any]] = []
    index = 0
    while index < len(tokens):
        fields = tokens[index].split(b"\t", 2)
        index += 1
        if len(fields) != 3:
            raise ValueError("Git returned an invalid numstat record")
        added_raw, deleted_raw, path_raw = fields
        if not path_raw:
            if index + 1 >= len(tokens):
                raise ValueError("Git returned an incomplete renamed numstat record")
            index += 1
            path_raw = tokens[index]
            index += 1
        records.append(
            {
                "path": decode(path_raw),
                "added": None if added_raw == b"-" else int(added_raw),
                "deleted": None if deleted_raw == b"-" else int(deleted_raw),
            }
        )
    return records


def inspect(
    revision_type: str,
    revision: str,
    records: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    included = [
        record
        for record in records
        if not excluded(record["path"], policy["exclude"])
    ]
    text_records = [
        record
        for record in included
        if record["added"] is not None and record["deleted"] is not None
    ]
    metrics = {
        "files": len(included),
        "added_lines": sum(record["added"] for record in text_records),
        "changed_lines": sum(
            record["added"] + record["deleted"] for record in text_records
        ),
        "max_added_lines_per_file": max(
            (record["added"] for record in text_records),
            default=0,
        ),
        "binary_files": sum(
            1
            for record in included
            if record["added"] is None or record["deleted"] is None
        ),
    }
    metric_limits = {
        "files": "max_files",
        "added_lines": "max_added_lines",
        "changed_lines": "max_changed_lines",
        "max_added_lines_per_file": "max_added_lines_per_file",
    }
    findings = [
        {
            "metric": metric,
            "actual": metrics[metric],
            "threshold": policy["limits"][limit],
            "message": (
                f"{metric} is {metrics[metric]}, above advisory threshold "
                f"{policy['limits'][limit]}"
            ),
        }
        for metric, limit in metric_limits.items()
        if metrics[metric] > policy["limits"][limit]
    ]
    return {
        "version": 1,
        "status": "failed" if findings else "passed",
        "subject": {
            "type": revision_type,
            "revision": revision,
        },
        "metrics": metrics,
        "thresholds": policy["limits"],
        "findings": findings,
    }


def staged(root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    revision = git_text(root, ["write-tree"])
    records = parse_numstat(
        git_bytes(
            root,
            ["diff", "--cached", "--numstat", "--diff-filter=ACMRD", "-z"],
        )
    )
    return inspect("git-tree", revision, records, policy)


def between(
    root: Path,
    policy: dict[str, Any],
    base_ref: str,
    head_ref: str,
    fallback_base: str | None,
) -> dict[str, Any]:
    base = base_ref
    if set(base_ref) == {"0"}:
        if not fallback_base:
            raise ValueError("a zero base revision requires --fallback-base")
        base = fallback_base
    resolved_base = resolve_commit(root, base)
    resolved_head = resolve_commit(root, head_ref)
    records = parse_numstat(
        git_bytes(
            root,
            [
                "diff",
                "--numstat",
                "--diff-filter=ACMRD",
                "-z",
                f"{resolved_base}...{resolved_head}",
            ],
        )
    )
    return inspect("git-commit", resolved_head, records, policy)


def render(result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    lines = [
        f"CHANGE SCOPE {result['status'].upper()} "
        f"{result['subject']['type']}@{result['subject']['revision']}",
        (
            f"Files: {metrics['files']}; added lines: {metrics['added_lines']}; "
            f"changed lines: {metrics['changed_lines']}; largest addition: "
            f"{metrics['max_added_lines_per_file']}; binary files: "
            f"{metrics['binary_files']}"
        ),
    ]
    lines.extend(f"- advisory: {finding['message']}" for finding in result["findings"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect file and line scope for a staged change or Git range"
    )
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--base-ref")
    parser.add_argument("--head-ref")
    parser.add_argument("--fallback-base")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        if bool(args.base_ref) != bool(args.head_ref):
            raise ValueError("--base-ref and --head-ref must be used together")
        policy = load_policy(args.policy)
        result = (
            between(
                ROOT,
                policy,
                args.base_ref,
                args.head_ref,
                args.fallback_base,
            )
            if args.base_ref
            else staged(ROOT, policy)
        )
        if args.output:
            args.output.write_text(
                json.dumps(result, indent=2) + "\n",
                encoding="utf-8",
            )
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2) if args.json else render(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
