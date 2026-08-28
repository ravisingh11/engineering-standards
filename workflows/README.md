# Guardrails v2 workflows

The installer deploys independent producer workflows and an aggregate
scorecard. A workflow file is configuration; only exact-subject provider
evidence can pass a capability.

## Install sets

```sh
python3 /path/to/engineering-standards/tooling/install.py --target /path/to/repo
python3 /path/to/engineering-standards/tooling/install.py --target /path/to/repo --profile github
python3 /path/to/engineering-standards/tooling/install.py --target /path/to/repo --no-actions
```

The default installs Core runtime and Core workflows. `--profile github` adds
the GitHub overlay. `--no-actions` installs no workflows.

### Core workflows

| Installed file | Workflow / check names | Activation |
| --- | --- | --- |
| `guardrails-scorecard.yml` | `Guardrail Scorecard` | Always for supported PR events and manual dispatch |
| `repository-validation.yml` | `Validate / repository`, `Validate / docs`, `Validate / ground truth`, `Validate / scope` | Installed validators and repository configuration |
| `build.yml` | `Build` | `GUARDRAILS_BUILD_COMMAND` |
| `unit-tests.yml` | `Unit Tests` | `GUARDRAILS_UNIT_TEST_COMMAND` |
| `changed-code-coverage.yml` | `Changed Code Coverage` | `GUARDRAILS_CHANGED_COVERAGE_COMMAND` |
| `semgrep-ce.yml` | `Semgrep CE` | Installed tested rules; no secret |
| `gitleaks.yml` | `Gitleaks` | Full Git history; no secret |

Build, test, and coverage workflows use optional
`GUARDRAILS_SETUP_COMMAND` and default `GUARDRAILS_WORKING_DIRECTORY` to `.`.
Unset capability commands skip their jobs and produce `NO RESULT`.

Semgrep CE runs its repository-owned rule tests, then `semgrep scan --error`
from the exact pinned container with networking disabled. Gitleaks runs the MIT
CLI from its exact pinned container against complete Git history. Core does not
use a platform token for Semgrep or the separately licensed Gitleaks Action.

### GitHub profile workflows

| Installed file | Workflow / check | Activation |
| --- | --- | --- |
| `codeql.yml` | `CodeQL` | `GUARDRAILS_CODEQL_LANGUAGES` |
| `dependency-review.yml` | `Dependency Review` | `GUARDRAILS_DEPENDENCY_REVIEW_ENABLED=true` |
| `github-secret-protection.yml` | `Secret Scan` / published `GitHub Secret Scan` | Optional `SECURITY_SETTINGS_TOKEN` and enabled platform settings |
| `dependabot-verification.yml` | `Dependabot Verification` | Optional `SECURITY_SETTINGS_TOKEN` and enabled platform settings |
| `artifact-provenance.yml` | `Artifact Provenance` | Release/dispatch attestation only; not PR or scorecard evidence |

The settings probes use trusted, no-checkout `pull_request_target` workflows.
Give `SECURITY_SETTINGS_TOKEN` only repository Administration read and Secret
scanning alerts read access. Missing or insufficient access publishes skipped
exact-head checks; it never passes the capability.

The release attestation workflow requires an artifact supplied by dispatch
input or `GUARDRAILS_ARTIFACT_PATH`. `GUARDRAILS_ARTIFACT_BUILD_COMMAND` is
optional. The workflow does not emit the nested artifact evidence contract or
invoke a release scorecard, so it is not yet a fully runnable Guardrails
artifact-provenance path.

## Scorecard flow

```text
provider workflows in parallel
        -> selected check contracts
        -> exact-head and workflow-run provenance verification
        -> nested provider evidence
        -> deterministic scorecard
```

`guardrails-scorecard.yml` runs as trusted `pull_request_target` code. It checks
out executable runtime only from the exact base SHA, sparse-checks out the exact
PR-head policy/configuration as fixed-path non-symlink data, and never executes
candidate code with the GitHub token. It waits up to 600 seconds, writes paired
timestamped scorecard JSON and Markdown plus timestamped evidence, appends the
Markdown to the job summary, and uploads `.artifacts/guardrails` as
`guardrail-scorecard-<run-id>`.

The collector requires the exact check name/head/app, workflow run name/path,
pull-request event, and exact PR-head association. Native Actions checks retain
workflow-suite binding. Custom setting checks instead require their configured
external-ID prefix and details run ID; their PR-head check suite is not equated
with the `pull_request_target` workflow's base-SHA suite. Missing, skipped,
stale, ambiguous, or unverifiable checks become `NO RESULT`.

## Local versus PR operation

Local scans run the same Core provider contracts against a clean local `HEAD`.
They are fast feedback, not merge authority. Pull-request workflows run in the
repository's controlled Actions environment and provide the evidence consumed
by branch protection.

Do not treat scorecard job success as a pass for every capability. Inspect the
overall `GREEN`, `ORANGE`, or `RED` status and every capability/provider row.

## Optional providers

SonarQube, Snyk, Semgrep AppSec Platform, FOSSA, AI review adapters, and soak
testing are not installed as runnable profiles. A repository must supply a
workflow or adapter, required credentials/configuration, exact check/evidence
binding, and an explicit provider selection. A credential alone does not
activate or satisfy a capability.

Provider definitions declare these secret names where applicable:

```text
SONAR_TOKEN
SNYK_TOKEN
SEMGREP_APP_TOKEN
FOSSA_API_KEY
```

Keep optional integrations advisory until representative pull requests prove
their availability, exact-subject binding, stable check names, and failure
behavior.

## Required checks

Require only exact observed check names. Core examples are `Validate / repository`,
`Validate / docs`, `Validate / ground truth`, `Validate / scope`, `Build`,
`Unit Tests`, `Changed Code Coverage`, `Semgrep CE`, and `Gitleaks`. GitHub
profile examples are `CodeQL`, `Dependency Review`, `GitHub Secret Scan`,
and `Dependabot Verification`. `Artifact Provenance` is release-only and must
not be configured as a pull-request required check.

See [ruleset guidance](../rulesets/README.md) before adding contexts.
