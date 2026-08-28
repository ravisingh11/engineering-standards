# Control setup

Guardrails selects capabilities through profiles and records the provider that
produced each result. Configure the producer first, verify exact-subject
evidence, then consider enforcement.

## Core profile

Core is selected by default. A normal install deploys its runtime and workflows.

| Capability | Authoritative provider | Check | Repository setup |
| --- | --- | --- | --- |
| Repository validation | Repository Validators | `Validate / repository` | Installed validator; no credential |
| Documentation validation | Repository Validators | `Validate / docs` | Maintain `.guardrails/documentation.yaml` |
| Repository ground truth | Repository Validators | `Validate / ground truth` | Maintain `.guardrails/ground-truth-ai.yaml` |
| Change scope | Repository Validators | `Validate / scope` | Maintain `.guardrails/change-scope.yaml` |
| Build | Repository Build Command | `Build` | Set `GUARDRAILS_BUILD_COMMAND` |
| Unit tests | Repository Unit Test Command | `Unit Tests` | Set `GUARDRAILS_UNIT_TEST_COMMAND` |
| Changed-code coverage | Repository Changed Code Coverage Command | `Changed Code Coverage` | Set `GUARDRAILS_CHANGED_COVERAGE_COMMAND` |
| Custom static analysis | Semgrep Community Edition | `Semgrep CE` | Installed tested rule pack; no token |
| Secret detection | Gitleaks CLI | `Gitleaks` | Complete Git history; no token |

### Repository command variables

Local and Actions producers use the same names:

| Variable | Required for | Behavior when absent |
| --- | --- | --- |
| `GUARDRAILS_SETUP_COMMAND` | Optional setup before build/test/coverage | Setup step is omitted. |
| `GUARDRAILS_BUILD_COMMAND` | Build | Build reports `NO RESULT`. |
| `GUARDRAILS_UNIT_TEST_COMMAND` | Unit tests | Unit tests report `NO RESULT`. |
| `GUARDRAILS_CHANGED_COVERAGE_COMMAND` | Changed-code coverage | Coverage reports `NO RESULT`. |
| `GUARDRAILS_WORKING_DIRECTORY` | All repository commands | Defaults to `.`; must stay inside the repository. |

Use repository variables in GitHub and environment variables locally. Commands
run through `bash -euo pipefail -c` in the selected working directory.

### Semgrep CE

Core runs `semgrep scan --error` with `.guardrails/semgrep-rules.yml`. The
workflow first runs Semgrep's rule tests against the installed positive and
negative fixtures. It does not use cloud-managed rules or require an AppSec
Platform token.

The pinned container is:

```text
semgrep/semgrep@sha256:b94b53d02fd4a022f9eac4e2af1380f5c3c4c21400e79d3336bdff1d1db5e796
```

Local scans prefer Docker with networking disabled. Without Docker they require
host Semgrep `1.175.0` exactly. Missing rules, unavailable Docker, or a host
version mismatch reports `NO RESULT`.

Repository-owned and third-party Semgrep rules can have licenses independent of
the Semgrep engine. Review every rule pack before copying it.

### Gitleaks CLI

Core runs `gitleaks git --redact --no-banner .` from this pinned container:

```text
ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f
```

The workflow checks out full history. Local scans require complete Git history
and either Docker or host Gitleaks `8.30.1` exactly. Guardrails uses the MIT
Gitleaks CLI, not the separately licensed Gitleaks Action.

## GitHub profile

Install or add the profile with:

```sh
python3 /path/to/engineering-standards/tooling/install.py --target /path/to/repo --profile github
```

| Capability | Provider/check | Required repository setup |
| --- | --- | --- |
| Deep SAST | GitHub CodeQL / `CodeQL` | Set `GUARDRAILS_CODEQL_LANGUAGES`; ensure GitHub code-scanning support. |
| Dependency change review | GitHub Dependency Review / `Dependency Review` | Set `GUARDRAILS_DEPENDENCY_REVIEW_ENABLED=true`; ensure the repository is eligible for Dependency Review. |
| Platform secret protection | GitHub Secret Protection / `GitHub Secret Scan` | Enable Secret Scanning and push protection; optional settings token below. |
| Dependency remediation | GitHub Dependabot / `Dependabot Verification` | Enable vulnerability alerts and automated security fixes; optional settings token below. |
| Release attestation helper | GitHub Artifact Attestations / `Artifact Provenance` | Supply a release artifact path and any build command; this is not yet Guardrails scorecard evidence. |

### GitHub variables and token

| Name | Kind | Used by |
| --- | --- | --- |
| `GUARDRAILS_CODEQL_LANGUAGES` | Variable | CodeQL language input |
| `GUARDRAILS_DEPENDENCY_REVIEW_ENABLED` | Variable | Dependency Review activation; exact value `true` |
| `GUARDRAILS_ARTIFACT_BUILD_COMMAND` | Variable | Optional release artifact build |
| `GUARDRAILS_ARTIFACT_PATH` | Variable | Release artifact path when not supplied by dispatch input |
| `SECURITY_SETTINGS_TOKEN` | Secret | GitHub Secret Protection and Dependabot setting probes |

`SECURITY_SETTINGS_TOKEN` is optional. Without it, both setting probes publish
exact-head skipped checks and the scorecard reports `NO RESULT`. When used, give
it only repository Administration read and Secret scanning alerts read access.
The trusted `pull_request_target` workflows do not check out PR code or expose
the protected token to PR-controlled commands.

A configured token proves only that the probe can attempt the API calls. A
passing result still requires the relevant settings and alert state.

### Release attestation boundary

The installed `Artifact Provenance` workflow runs on a published release or
manual dispatch and attests the exact artifact selected by the dispatch input
or `GUARDRAILS_ARTIFACT_PATH`. It is release-attestation-only: it does not run
on pull requests, emit the nested artifact evidence contract, or invoke a
Guardrails release scorecard. Until those paths exist and are tested, artifact
provenance is not a fully runnable Guardrails capability and its workflow/job
name must not be configured as a PR required check.

## Ground-truth paths

`.guardrails/ground-truth-ai.yaml` accepts repository-relative paths to files
that actually exist:

```json
{
  "version": 1,
  "documents": [
    {"path": "README.md"},
    {"path": "docs/design/architecture.md"},
    {"path": "engineering/security/controls.md"}
  ]
}
```

The consuming repository chooses the names and locations. Guardrails does not
copy application ground truth into this standards repository.

## Provider selection

List current modes and provider selections:

```sh
python3 .guardrails/configure.py --list
```

Change the authoritative provider or add a supplemental provider:

```sh
python3 .guardrails/configure.py \
  --select-provider changed-code-coverage=sonarqube \
  --set changed-code-coverage=advisory \
  --dry-run

python3 .guardrails/configure.py \
  --add-supplemental deep-sast=snyk-code \
  --dry-run
```

Supplemental evidence is always advisory. It cannot satisfy or block the
capability. A provider cannot be both authoritative and supplemental for the
same capability.

## Optional vendor providers

These definitions are available but are not runnable profiles and are not
installed as active integrations:

| Provider | Capabilities | Declared credential | Activation responsibility |
| --- | --- | --- | --- |
| SonarQube | Static quality, changed-code coverage | `SONAR_TOKEN` | Configure project/host settings and a workflow or adapter that emits exact-head `SonarQube Quality Gate` evidence. |
| Snyk Code | Deep SAST | `SNYK_TOKEN` | Supply a repository or organization workflow/adapter and exact-head `Snyk Code` evidence. |
| Snyk Open Source | Dependency vulnerability | `SNYK_TOKEN` | Supply a repository or organization workflow/adapter and exact-head `Snyk Open Source` evidence. |
| Semgrep AppSec Platform | Custom static analysis, deep SAST | `SEMGREP_APP_TOKEN` | Supply an organization-approved integration and exact-head `Semgrep` evidence. |
| FOSSA | Dependency vulnerability, license compliance | `FOSSA_API_KEY` | Supply a repository or organization workflow/adapter and exact-head `FOSSA` evidence. |

Do not add a credential until the adapter is ready. Do not select a vendor as
authoritative until its evidence contract and failure behavior are verified.

## Promote to enforcement

1. Run the provider on representative pull requests.
2. Confirm evidence binds to the exact subject.
3. Confirm the exact stable check name and failure behavior.
4. Assign a remediation owner.
5. Set the capability to `enforced`.
6. Add that exact check context to the repository ruleset.

```sh
python3 .guardrails/configure.py --set unit-tests=enforced --dry-run
python3 .guardrails/configure.py --set unit-tests=enforced
```

Policy enforcement without a matching ruleset does not protect merge. A
required status check without a reliable provider can deadlock merge.

## Evidence-only lifecycle controls

Container vulnerability, IaC misconfiguration, artifact SBOM, artifact
vulnerability, deployment policy, dynamic application security, and runtime
assurance are future evidence contracts only. Guardrails does not install or
operate container scanners, SBOM generators, policy engines, DAST tools, or
observability stacks for them.
