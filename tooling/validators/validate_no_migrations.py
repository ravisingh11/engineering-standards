#!/usr/bin/env python3
"""Enforce this repository's ground truth that it has no database migrations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


MIGRATION_PATHS = (
    Path("migrations"),
    Path("db/migrate"),
    Path("alembic/versions"),
    Path("prisma/migrations"),
    Path("src/main/resources/db/migration"),
)


def migration_paths(root: Path) -> list[Path]:
    return [relative for relative in MIGRATION_PATHS if (root / relative).exists()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail if a database migration surface is introduced without a real validator."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()

    found = migration_paths(args.root.resolve())
    if found:
        rendered = ", ".join(path.as_posix() for path in found)
        print(
            "Database migration paths were introduced but this repository declares no "
            f"migration surface: {rendered}. Replace this check with the migration "
            "framework's real validation command before merging.",
            file=sys.stderr,
        )
        return 1
    print("No database migration surface is present, matching repository ground truth.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
