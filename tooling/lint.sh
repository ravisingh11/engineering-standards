#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "${repo_root}"

command -v ruff >/dev/null 2>&1 || {
  echo "ruff is required; install tooling/requirements-lint.txt" >&2
  exit 2
}
command -v yamllint >/dev/null 2>&1 || {
  echo "yamllint is required; install tooling/requirements-lint.txt" >&2
  exit 2
}

empty_tree="$(git hash-object -t tree /dev/null)"
git diff --check "${empty_tree}" HEAD
git diff --cached --check
git diff --check
ruff check .
yamllint --strict .
