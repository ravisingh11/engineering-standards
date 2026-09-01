# Guardrails v2 quick start

Install Core, configure repository commands, run locally, and then verify the
same capability providers on a pull request.

## 1. Preview and install Core

From the standards repository:

```sh
python3 tooling/install.py --target /path/to/repo --dry-run
python3 tooling/install.py --target /path/to/repo
```

A normal install includes the Core runtime and Core GitHub Actions. To install
only the runtime, use:

```sh
python3 tooling/install.py --target /path/to/repo --no-actions
```

To add validated local pre-commit hooks, first install `pre-commit`, then run:

```sh
python3 tooling/install.py --target /path/to/repo --local-hooks
```

The installer refuses to overwrite an existing pre-commit configuration.

## 2. Add the optional GitHub profile

For a fresh install:

```sh
python3 tooling/install.py --target /path/to/repo --profile github
```

For an existing v2 installation:

```sh
python3 tooling/install.py --target /path/to/repo --profile github --merge-existing --dry-run
python3 tooling/install.py --target /path/to/repo --profile github --merge-existing
```

Core remains selected. The GitHub profile is an additive advisory overlay.

## 3. Configure repository commands

This verified example matches the embedded Python demo:

```sh
export GUARDRAILS_BUILD_COMMAND='python3 -m compileall -q app.py test_app.py tools .guardrails'
export GUARDRAILS_UNIT_TEST_COMMAND="python3 -m unittest discover -s . -p 'test_*.py'"
export GUARDRAILS_WORKING_DIRECTORY='.'
```

Use the same names as GitHub Actions repository variables. Configure
`GUARDRAILS_SETUP_COMMAND`, `GUARDRAILS_CHANGED_COVERAGE_COMMAND`,
`GUARDRAILS_FORMAT_LINT_COMMAND`, and `GUARDRAILS_MIGRATION_VALIDATION_COMMAND`
only when the repository has real commands for those capabilities. Unset build,
test, or coverage commands produce `NO RESULT` rather than pass. The installed
format/lint and migration Actions jobs fail visibly when their command is absent;
local scans represent the same absence as `NO RESULT`.
`GUARDRAILS_WORKING_DIRECTORY` must resolve inside the repository.

Before opening the first pull request, configure real format/lint and migration
commands for any installed workflows you intend to run. Do not use a no-op or
an unrelated validation command: a green check must prove its named capability.

## 4. Declare repository ground truth

Edit `.guardrails/ground-truth-ai.yaml` so each entry names an existing path:

```json
{
  "version": 1,
  "documents": [
    {"path": "README.md"},
    {"path": "docs/architecture/system.md"},
    {"path": "handbook/testing.md"}
  ]
}
```

The paths are repository-relative and configurable. Root-level conventional
filenames are not required.

## 5. Inspect policy and run

```sh
python3 .guardrails/configure.py --list
python3 .guardrails/scan.py --help
python3 .guardrails/configure.py --help
python3 .guardrails/scan.py
```

The scan requires a clean worktree and binds evidence to the resolved full
`HEAD`. It writes:

```text
.artifacts/guardrails/evidence-YYYYMMDD-HHMMSSZ.json
.artifacts/guardrails/evidence.json
.artifacts/guardrails/scorecard-YYYYMMDD-HHMMSSZ.md
```

The default scorecard omits inactive and `evidence-only` controls. Use
`python3 .guardrails/scan.py --all-catalog-controls` to inspect the complete
catalog with those controls shown as `GRAY` / `not_activated`.

Release policy can activate controls for more than one evidence subject. Select
one immutable subject contract per invocation instead of combining commit and
artifact evidence:

```sh
python3 .guardrails/scan.py --operation release --subject-type git-commit
python3 .guardrails/scan.py --operation release --subject-type artifact \
  --revision 'sha256:<artifact-digest>'
```

If more than one subject applies and `--subject-type` is omitted, the scanner
stops with a configuration error rather than silently omitting controls.

Core uses the pinned Semgrep CE and Gitleaks CLI containers when Docker is
available. Otherwise it accepts only host Semgrep `1.175.0` and Gitleaks
`8.30.1`. Missing Docker, unavailable tools, a shallow history, or a version
mismatch produces `NO RESULT`.

## 6. Configure the GitHub overlay

If the GitHub profile is selected, configure only applicable repository
variables:

```text
GUARDRAILS_CODEQL_LANGUAGES
GUARDRAILS_DEPENDENCY_REVIEW_ENABLED=true
GUARDRAILS_ARTIFACT_BUILD_COMMAND
GUARDRAILS_ARTIFACT_PATH
```

`GUARDRAILS_CODEQL_LANGUAGES` is the CodeQL language list. Artifact variables
apply to release/workflow-dispatch provenance, not PR commit evidence.

The optional `SECURITY_SETTINGS_TOKEN` is used only by trusted, no-checkout
`pull_request_target` setting probes for GitHub Secret Protection and
Dependabot. It needs repository Administration read and Secret scanning alerts
read access. Missing or insufficient access publishes `NO RESULT`.
Dependabot's version `2022-11-28` API response must be valid JSON with boolean
`enabled: true` and `paused: false`. Empty, malformed, or incomplete successful
responses publish `NO RESULT`; a `404` means automated security fixes are
disabled.

## 7. Open a pull request

```text
local scan -> push branch -> provider workflows -> exact-head collector
           -> Guardrail Scorecard -> review -> merge
```

Provider workflows run independently. The scorecard collector reads only the
selected authoritative and supplemental check contracts and verifies their
workflow provenance for the exact PR head. Native workflow providers may also
declare `trusted_paths` for validator code, rule packs, and fixtures that define
the result. The workflow definition and every declared path must have the same
Git blob at the PR head and trusted base; otherwise the result is `NO RESULT`.
If a configured repository command delegates to a tracked helper, add that
helper to the check's `trusted_paths`. Refreshes retain repository-specific
trusted-path additions while restoring the canonical provider contract.

Core also installs `PR Change Scope`. Base-owned validator code compares the
exact PR base and head without executing candidate code. The default policy
measures meaningful source changes against 300 added and 500 changed lines,
while still showing excluded documentation, lockfile, generated, and vendor
volume in total metrics. An oversized advisory PR produces a neutral provider
check and `ORANGE / ALLOW`; promotion to `enforced` changes the provider check
to failure.

## 8. Promote one proven capability

Keep all capabilities advisory while tuning. After a provider has a stable
check name, reliable exact-subject evidence, and a remediation owner:

```sh
python3 .guardrails/configure.py --set unit-tests=enforced --dry-run
python3 .guardrails/configure.py --set unit-tests=enforced
```

Then add the observed check context to the repository ruleset. Policy mode and
GitHub branch protection are separate changes; both are required for a merge
gate.

Continue with [control setup](control-setup.md) and [rulesets](../rulesets/README.md).
