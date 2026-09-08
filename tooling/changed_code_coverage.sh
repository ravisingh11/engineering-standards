#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
coverage_file="${repo_root}/.artifacts/guardrails/coverage.xml"
coverage_target="${GUARDRAILS_COVERAGE_TARGET:-90}"
coverage_data_root="$(mktemp -d "${TMPDIR:-/tmp}/engineering-standards-coverage.XXXXXX")"
export COVERAGE_FILE="${coverage_data_root}/coverage.data"
trap 'rm -rf "${coverage_data_root}"' EXIT

if [[ -z "${GUARDRAILS_COVERAGE_BASE_REF:-}" ]]; then
  echo "GUARDRAILS_COVERAGE_BASE_REF must identify the exact comparison commit." >&2
  exit 2
fi
command -v coverage >/dev/null 2>&1 || {
  echo "coverage is required; install tooling/requirements-ci.txt" >&2
  exit 2
}
command -v diff-cover >/dev/null 2>&1 || {
  echo "diff-cover is required; install tooling/requirements-ci.txt" >&2
  exit 2
}

cd "${repo_root}"
mkdir -p "$(dirname "${coverage_file}")"
coverage erase

coverage run --branch --source=guardrails,tooling \
  -m unittest discover -s guardrails/tests -p 'test_*.py'
coverage run --append --branch --source=guardrails,tooling \
  -m unittest discover -s tooling/tests -p 'test_*.py'
coverage run --append --branch --source=guardrails,tooling \
  -m unittest discover -s tooling/validators/tests -p 'test_*.py'
coverage xml -o "${coverage_file}"

diff-cover "${coverage_file}" \
  --compare-branch="${GUARDRAILS_COVERAGE_BASE_REF}" \
  --fail-under="${coverage_target}"
