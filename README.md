# Engineering Standards

**Engineering standards for an AI world.**

[![Guardrail Scorecard](https://github.com/ravisingh11/engineering-standards/actions/workflows/guardrails-scorecard.yml/badge.svg?branch=main)](https://github.com/ravisingh11/engineering-standards/actions/workflows/guardrails-scorecard.yml)

AI changed the economics of software.

We can create more code, touch more files, and ship more change than ever
before. That is a huge unlock. It also creates a new problem: **velocity without
discipline becomes chaos.**

The answer is not more meetings, more process, or a handbook nobody reads. It
is lightweight guardrails that run with the work.

This repository turns practical engineering habits into executable checks:

- Keep changes small enough to understand.
- Test what you change.
- Review the code, including the code AI writes.
- Do not ship known security problems.
- Keep the repository's ground truth current.
- Make the build tell you whether a change is ready.

The philosophy is simple:

> **Move fast. Prove it works.**

Guardrails, not gates. The tools that do the work remain the source of their
own findings; this repository connects those results to the exact change being
shipped and makes the state visible. A missing check is not a pass.

Make the safe path the easy path. Application repositories keep their own
architecture and operating details; this project supplies a common engineering
backbone without inventing repository-specific ground truth.

## Guardrails model

A **capability** is a vendor-neutral engineering outcome such as unit testing or
secret detection. A **provider** is the tool that produces evidence for that
capability. Each selected capability has exactly one authoritative provider.
Supplemental providers remain visible and advisory; they cannot satisfy or
block the capability.

```text
profile -> capability -> authoritative provider -> exact-subject evidence
                  \---- supplemental providers ----> advisory evidence
```

Configuration expresses intent. Only fresh evidence for the exact commit,
pull-request state, artifact, or environment proves that a provider ran.

## Start here

- Use the [quick start](docs/quickstart.md) for installation and the first scan.
- Read [architecture](docs/architecture.md) for the contract and evidence flow.
- Use [control setup](docs/control-setup.md) for variables, tokens, profiles,
  providers, and promotion to enforcement.
- Use [control status](docs/control-status.md) to interpret colors and outcomes.
- Read the [producer contract](docs/producer-contract.md) before adding an
  adapter or external evidence.
- Use [workflow guidance](workflows/README.md) and [ruleset guidance](rulesets/README.md)
  before making any check required.
- Run the embedded [Python demo](examples/python-demo/) for a complete consumer.

## Profiles

| Profile | Selection | Capabilities |
| --- | --- | --- |
| `core` | Default | Repository and documentation validation, repository ground truth, change scope, PR metadata, format/lint, migration validation, build, unit tests, changed-code coverage, Semgrep CE, and Gitleaks CLI |
| `github` | Optional additive overlay | CodeQL, Dependency Review, GitHub Secret Protection, Dependabot verification, plus a release-attestation workflow that is not yet scorecard evidence |

Both profiles are advisory by default. Other vendors are providers, not
runnable profiles.

Core includes `PR Change Scope`, with repository-configurable thresholds in
`.guardrails/change-scope.yaml`. It reports total, meaningful, and excluded
change volume. The default 300-added-line and 500-changed-line thresholds are
advisory: oversized PRs stay visible without blocking until a repository
deliberately promotes the capability to `enforced`.

Core also includes mutable `PR Metadata` evidence. Configure title and body
requirements in `.guardrails/pr-metadata.yaml`; editing either field creates a
new pull-request fingerprint even when the head commit does not change. This
control runs only in the trusted GitHub pull-request workflow, not in a local
repository scan. The trusted workflow publishes a separate `PR Metadata` check
against the exact candidate head SHA, so repositories may promote that context
after observing it on representative pull requests.

## Install

Install Core runtime and Core GitHub Actions:

```sh
python3 /path/to/engineering-standards/tooling/install.py --target /path/to/repo
```

Add the GitHub profile:

```sh
python3 /path/to/engineering-standards/tooling/install.py --target /path/to/repo --profile github
```

Install without Actions, or add local pre-commit hooks:

```sh
python3 /path/to/engineering-standards/tooling/install.py --target /path/to/repo --no-actions
python3 /path/to/engineering-standards/tooling/install.py --target /path/to/repo --local-hooks
```

`--local-hooks` requires `pre-commit` and refuses to overwrite an existing
`.pre-commit-config.yaml`. Use `--dry-run`, `--merge-existing`, or
`--refresh-existing` when adopting or updating an existing clean install.
The installer never copies credentials.

## Configure and run

```sh
python3 .guardrails/scan.py --help
python3 .guardrails/configure.py --help
python3 .guardrails/configure.py --list
python3 .guardrails/scan.py
```

The scanner writes nested JSON evidence and a timestamped Markdown scorecard to
`.artifacts/guardrails/`. It binds local evidence to a clean, exact `HEAD`.
Unavailable tools and unconfigured commands report `not_run` / `NO RESULT`.

For the embedded Python demo, these are real repository commands:

```sh
export GUARDRAILS_BUILD_COMMAND='python3 -m compileall -q app.py test_app.py tools .guardrails'
export GUARDRAILS_UNIT_TEST_COMMAND="python3 -m unittest discover -s . -p 'test_*.py'"
export GUARDRAILS_WORKING_DIRECTORY='.'
python3 .guardrails/scan.py
```

The same names are GitHub Actions repository variables. Set command variables
only when the repository has real commands for those capabilities. An unset
build, test, coverage, format/lint, or migration command skips that producer
and cannot create a pass.

Core runs Semgrep Community Edition with repository-owned tested rules via
`semgrep scan`, and runs the Gitleaks CLI against complete Git history. Local
execution uses the pinned containers or exactly matching host versions.

## Modes and providers

```sh
python3 .guardrails/configure.py --enable-profile github --dry-run
python3 .guardrails/configure.py --set unit-tests=enforced --dry-run
python3 .guardrails/configure.py --select-provider changed-code-coverage=sonarqube --dry-run
python3 .guardrails/configure.py --add-supplemental deep-sast=snyk-code --dry-run
```

Remove `--dry-run` after reviewing the policy and provider changes. Use
`--operation release` for release policy or `--all-operations` when the
capability applies to both operations. The configurator rejects a capability
whose catalog stage does not apply to every selected operation, without writing
the invalid override.

Optional providers include SonarQube, Snyk, Semgrep AppSec Platform, FOSSA, and
Codex Code Review.
Each requires its own workflow or adapter, configuration, credentials, exact
evidence binding, and explicit authoritative or supplemental selection. A token
alone does not activate or pass a capability.

AI review controls are contractually `advisory-only`: configuration rejects
attempts to promote them to `enforced`. They may add review evidence, but they
must not become the sole merge gate. For Codex, enable native automatic reviews
in Codex settings (recommended) or request one with `@codex review`, then enable
`ai-engineering-review=advisory`. No repository secret is required.

## Status vocabulary

| Readiness | Meaning |
| --- | --- |
| **GREEN** | The authoritative provider passed for the exact subject. |
| **ORANGE** | An advisory capability lacks a passing authoritative result. The operation may still be allowed. |
| **RED** | An enforced capability lacks a passing authoritative result, or evidence targets the wrong subject. The operation is blocked. |
| **GRAY** | The capability is not activated for this operation and subject type. |

Raw producer statuses are `passed`, `failed`, `blocked`, and `not_run`. Public
scorecards display `not_run` or missing evidence as `no_result`. Supplemental
results never change the decision. Default scorecards omit inactive and
`evidence-only` catalog controls. Pass `--all-catalog-controls` to include them
as `GRAY` / `not_activated` rows.

## Local and pull-request flow

```text
local scan -> fix findings -> open PR -> independent provider checks
           -> exact-head evidence collection -> scorecard -> ruleset decision
```

Local scans provide feedback from the current machine. Pull-request checks are
the authoritative merge evidence because they run in the repository's trusted
workflow environment and bind results to the PR head. The installed
`Artifact Provenance` workflow is release-attestation-only and never runs as a
PR check. It does not emit nested artifact evidence for a Guardrails release
scorecard, so artifact provenance is not yet a fully runnable Guardrails
capability and must not be added to PR required checks.

Do not require a status check until it has produced reliable, revision-bound
results with a stable name and a remediation owner. See [rulesets/README.md](rulesets/README.md).

## Ground truth and future capabilities

Consuming repositories own their architecture, standards, testing, security,
deployment, and contribution documents. List any existing relative paths in
`.guardrails/ground-truth-ai.yaml`; filenames and directories are configurable
and do not have to be repository-root conventions.

Container vulnerability, IaC misconfiguration, SBOM, artifact vulnerability,
deployment policy, dynamic application security, and runtime assurance are
catalog and evidence contracts only. Guardrails does not install or operate
tools for those future lifecycle capabilities.

## Repository map

| Path | Purpose |
| --- | --- |
| `policies/` | Capability catalog, profiles, provider definitions, and engineering policy |
| `guardrails/` | Schemas, evaluator, baseline, and repository-neutral validator |
| `tooling/` | Installer, configurator, producers, scanner, scorecard, and validators |
| `workflows/` | Core, GitHub-profile, and optional provider templates |
| `rulesets/` | GitHub default-branch protection template and activation guidance |
| `skills/` | Reusable agent workflows |
| `examples/` | Runnable consumer examples |
| `.guardrails/` | Installed runtime and repository-owned configuration in a consumer |

## License and validation

This repository is MIT licensed. Third-party tools, Actions, services, and rule
packs retain their own terms; see [licensing](docs/licensing.md).

```sh
python3 -m unittest discover -s guardrails/tests -p 'test_*.py'
python3 -m unittest discover -s tooling/tests -p 'test_*.py'
python3 -m unittest discover -s tooling/validators/tests -p 'test_*.py'
python3 -m unittest discover -s examples/python-demo -p 'test_*.py'
python3 examples/python-demo/tools/validate_demo.py --documentation
python3 tooling/validate-skills.py
python3 tooling/validators/validate_repository.py
python3 tooling/validators/validate_documentation.py
git diff --check
```
