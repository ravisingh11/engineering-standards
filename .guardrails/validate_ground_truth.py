#!/usr/bin/env python3
"""Validate repository-declared ground-truth documents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate repository ground-truth documents")
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path(".guardrails/ground-truth-ai.yaml"),
    )
    args = parser.parse_args()
    try:
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"ERROR: cannot read ground-truth policy: {error}")
        return 1
    if policy.get("version") != 1 or not isinstance(policy.get("documents"), list):
        print("ERROR: ground-truth policy requires version 1 and documents")
        return 1
    missing = [
        item["path"]
        for item in policy["documents"]
        if isinstance(item, dict)
        and isinstance(item.get("path"), str)
        and not Path(item["path"]).is_file()
    ]
    if missing:
        print("Missing repository ground-truth documents:")
        for path in missing:
            print(f"- {path}")
        return 1
    print(f"Repository ground truth passed ({len(policy['documents'])} documents)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
