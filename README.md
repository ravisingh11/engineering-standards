# Engineering Standards

Executable engineering standards for faster, safer software delivery.

[![Guardrail Scorecard](https://github.com/ravisingh11/engineering-standards/actions/workflows/guardrail-checks.yml/badge.svg?branch=main)](https://github.com/ravisingh11/engineering-standards/actions/workflows/guardrail-checks.yml)

This repository combines policy, review guidance, reusable workflows, GitHub
rulesets, and shared agent skills. **Guardrails** is the executable layer: it
connects those standards to revision-bound evidence and produces a scorecard
that can run locally or on every pull request.

Application repositories keep their own architecture and operating details.
This project supplies the common engineering backbone without inventing
repository-specific ground truth.

> The goal is to replace slow, manual process with automated guardrails so
> good code reaches production faster and with more confidence.

## How it fits together

```text
Engineer + AI
    ↓
Change code and tests
    ↓
Open a pull request
    ↓
    Build · tests · SonarQube · SAST · secrets · dependencies · Snyk · FOSSA · AI review
    ↓
Collect evidence for the exact revision
    ↓
Evaluate the guardrail policy
    ↓
Resolve blocking findings
    ↓
Human or CODEOWNER review where needed
    ↓
Merge
```

Checks that do not depend on one another should run in parallel. A check is
only a real guardrail when it has a working producer, clear evidence, a known
status name, and a rule that says what happens when it fails.

The installed `.guardrails/producer-manifest.json` is the connection map between
controls and visible GitHub check contexts. The aggregate scorecard queries
those contexts for the exact pull-request commit using
`.guardrails/github_evidence.py`, writes revision-bound evidence, and
then evaluates policy. A missing or skipped producer is `not_run` / `NO RESULT`,
never an implicit pass. See the [producer contract](docs/producer-contract.md)
for the schema and outcome mapping.

## Start here

- See the [architecture diagrams](docs/architecture.md) and
  [control status guide](docs/control-status.md) to understand what is active
  versus what each application repository must configure.
- Follow the [compliance runbook](docs/compliance.md) to install, run, and read
  the guardrail evaluator and scorecard.
- For the shortest install-and-run path, use the [quick start](docs/quickstart.md).
- See the [sample scorecard output](docs/examples/sample-scorecard.md) for a
  concrete report with GREEN, ORANGE, and RED controls.
- Follow the [control setup guide](docs/control-setup.md) to configure every
  service and move controls from ORANGE/GRAY to GREEN.
- Read [policies/pull-request.md](policies/pull-request.md) for the default PR
  workflow and expectations.
- Read [policies/testing.md](policies/testing.md) and
  [policies/security.md](policies/security.md) for quality and risk controls.
- Use [policies/control-catalog.yaml](policies/control-catalog.yaml) to see how
  each control connects to its producer, evidence, and status check.
- Use [workflows/README.md](workflows/README.md) to install checks in an
  application repository.
- Use [rulesets/README.md](rulesets/README.md) to turn stable checks into merge
  protections.
- Use [docs/licensing.md](docs/licensing.md) for reuse and attribution rules.
- See [CONTRIBUTORS.md](CONTRIBUTORS.md) for project attribution and
  [docs/social-preview.md](docs/social-preview.md) for repository branding.

For a runnable consumer example, see the embedded
[Python demo](examples/python-demo/).

## What each part does

| Part | Plain-English purpose |
| --- | --- |
| `policies/` | The engineering rules teams are expected to follow. |
| `pr-review/` | The questions AI reviewers answer about a proposed change. |
| `workflows/` | The templates that run builds, tests, scanners, and reviews. |
| `guardrails/` | The schemas and evaluator that decide whether evidence meets policy. |
| `rulesets/` | The GitHub settings that protect the default branch. |
| `skills/` | Reusable instructions that help agents do engineering work. |
| `prompts/` | Reusable review and release prompts. |
| `templates/` | Starting points for `AGENTS.md`, `CODEX.md`, hooks, and repository setup. |
| `tooling/` | Installers and deterministic validation tools. |
| `examples/` | Small applications that demonstrate installation and evidence collection. |

Application repositories remain the source of truth for:

```text
AGENTS.md · ARCHITECTURE.md · STANDARDS.md · TESTING.md
SECURITY.md · DEPLOYMENT.md · CONTRIBUTING.md
```

The repository-standards review reads those files when they exist. It never
invents application-specific rules.

## Controls

The control catalog is the connection between policy and automation. It records
what a check finds, how it runs, what evidence it produces, when it runs, and
whether it can block a change.

### Enforcement vocabulary

Controls are capabilities, not automatic bureaucracy. Each application
repository chooses how strongly to enforce the controls it adopts:

| User-facing mode | Behavior |
| --- | --- |
| **Not activated** | The repository has not selected the control. It is cataloged but does not run. |
| **Advisory** | The repository selected the control. Findings and failures are visible, but it does not block merge. |
| **Enforced** | The repository selected the control and added its exact check to the ruleset. It can block merge. |

The shared repository provides the catalog and templates. Application teams
may add Snyk, FOSSA, Semgrep, soak checks, additional AI review depth, or other
approved capabilities as they see fit. Promote a capability only after its
results are reliable, thresholds are understood, and an owner is accountable
for remediation.

### Activation categories

Activation category answers **where the producer comes from**. It is separate
from enforcement mode and scan readiness. A GREEN activation category does not
mean that the current revision passed.

| Label | Meaning |
| --- | --- |
| **GREEN ✅** | GitHub-native control. GitHub policy, settings, rulesets, or Actions can enforce it. |
| **ORANGE 🟠** | External integration required. A third-party service or organization-owned adapter must be connected. |
| **GRAY ⚪** | Application repository configuration required. The shared repository provides a template or contract. |

| Check | Primarily finds | Runs | Activation | Policy |
| --- | --- | --- | --- | --- |
| [SonarQube](docs/control-setup.md#sonarqube--orange-until-configured-then-green-) | Code quality, bugs, maintainability, and new-code regressions | Every PR | **ORANGE 🟠** | Advisory; promote when configured |
| [CodeQL / SAST](docs/control-setup.md#codeql--sast--green-) | Vulnerabilities in application code | Every PR | **GREEN ✅** | Advisory by default; promote when mature |
| [Secrets scan](docs/control-setup.md#secrets-scanning--green-) | Credentials, tokens, and authentication material in code | Push and PR | **GREEN ✅** | Advisory by default; promote when mature |
| [FOSSA](docs/control-setup.md#fossa--orange-until-configured-then-green-) | Open-source dependency, license, and supply-chain risk | Every PR | **ORANGE 🟠** | Advisory; promote when configured |
| [Snyk Open Source](docs/control-setup.md#snyk--orange-until-configured-then-green-advisory-by-default) | Dependency vulnerabilities and supply-chain risk | Every PR when connected | **ORANGE 🟠** | Advisory; promote when mature |
| [Snyk Code](docs/control-setup.md#snyk--orange-until-configured-then-green-advisory-by-default) | Vulnerabilities in application source code | Every PR when connected | **ORANGE 🟠** | Advisory; promote when mature |
| [Semgrep](docs/control-setup.md#semgrep--orange-until-configured-then-green-) | Organization-specific static-analysis and security rules | Every PR when connected | **ORANGE 🟠** | Advisory; promote when mature |
| [Dependency Review](docs/control-setup.md#dependency-review--green-) | Risk introduced by changed dependencies | Every PR | **GREEN ✅** | Advisory by default; promote when mature |
| [Dependabot](docs/control-setup.md#dependabot--advisory-until-configured) | Automated dependency update and security-update pull requests | Scheduled and event-driven | **GREEN ✅** | Configuration is visible locally; activation and producer evidence must be verified |
| [Artifact Provenance](docs/control-setup.md#artifact-provenance--orange-until-configured-then-green-) | Signed evidence of how a release artifact was built | Build and release | **ORANGE 🟠** until configured | Build, attest, and verify the exact promoted artifact; advisory until the release path is verified |
| [Unit Tests](docs/control-setup.md#unit-tests--green-) | Functional regressions and changed behavior | Every PR | **GREEN ✅** | Advisory by default; promote when mature |
| [Soak Check](docs/control-setup.md#soak-check--gray-until-repository-setup-then-green-) | Runtime degradation, memory growth, leaks, and performance drift | Pre-release and scheduled | **GRAY ⚪** | Advisory; promote when configured |
| [AI reviews](docs/control-setup.md#ai-reviews--orange-until-configured-then-green) | Engineering, QA, security, and repository-standard findings | Every PR | **ORANGE 🟠** | Advisory; promote when configured |

`required_when_configured` is catalog metadata, not a user-facing enforcement
mode. It means a repository must provide a real producer before that control
can become an enforced merge gate. A repository may leave the control
`not_activated` or keep it `advisory`. Missing evidence is reported as
`no_result` or `blocked`; it is never treated as a pass.

## Repository architecture

The public contract is intentionally small:

```text
policies/       What Engineering requires
pr-review/      What AI evaluates
workflows/      What executes checks
rulesets/       What GitHub enforces
skills/         How agents perform repeatable work
```

Supporting implementation is kept separate:

```text
guardrails/     Policy and evidence schemas plus evaluator
tooling/        Installer, configurator, scorecard, and validators
docs/           Setup, compliance, architecture, and operating guidance
```

Application-specific architecture and ground truth never move into this
repository.

## Run a scan and get a scorecard

To scan this standards repository directly from its root:

```sh
python3 tooling/scan_repository.py --all-catalog-controls
```

For an application repository, install the runtime first as shown below.

### Local feedback or GitHub enforcement?

Use both, for different jobs:

| Where | Best for | Authority |
| --- | --- | --- |
| Local scan | Fast feedback before opening a PR | Informational; depends on the local environment and available provider credentials |
| GitHub Actions | The final PR result | Authoritative; runs configured producers and publishes checks, artifacts, and the scorecard. Most PR checks target the PR head; artifact provenance may intentionally attest the GitHub merge revision. |

Do not download a generated artifact as the primary installation method. Clone
or update this repository, install its runtime into the application repository,
and commit the workflow through the application's normal PR process:

```sh
git clone https://github.com/ravisingh11/engineering-standards.git \
  ../engineering-standards
python3 ../engineering-standards/tooling/install.py \
  --target . --github-actions
python3 .guardrails/scan.py --all-catalog-controls
```

The local scan helps engineers fix issues quickly. After the PR opens, GitHub
Actions reruns the checks in a clean runner and records revision-bound results.
Most checks use the PR head revision. Artifact provenance is an explicit
exception when its workflow attests GitHub's merge revision; read that
workflow's evidence before treating provenance as source-head evidence. Branch
rulesets should rely on the stable GitHub status checks, not on the local report.

Install the evaluator, control catalog, scorecard, producer manifest, GitHub
Checks collector, and aggregate scorecard workflow in an application repository:

```sh
python3 /path/to/engineering-standards/tooling/install.py \
  --target . \
  --github-actions
```

If the repository already contains a policy, preserve it and install only
missing product files:

```sh
python3 /path/to/engineering-standards/tooling/install.py \
  --target . \
  --github-actions \
  --merge-existing
```

Use `--refresh-existing` after upgrading this standards repository to refresh
installed product files while preserving `.ai/guardrails.yaml`, the producer
manifest, copied skill directories, consumer workflows, and generated reports.
Refresh also removes
only known guardrail-owned migration files, such as the retired
`.ai/providers.yaml` and known files under the former
`.agentic-guardrails/` runtime. Consumer configuration and customized
scorecard workflows are migrated to `.guardrails/` and
`guardrails-scorecard.yml`. Unknown files are preserved, and the installer
never recursively deletes directories or application files. Use `--dry-run`
to review the install and cleanup plan, or
`--no-cleanup` when a refresh must skip that migration cleanup.

List and configure controls through the installed policy tool:

```sh
python3 .guardrails/configure.py --list
python3 .guardrails/configure.py \
  --set snyk-code=advisory \
  --set snyk-open-source=advisory \
  --dry-run
```

Provider activation is managed through `.guardrails/providers.yaml`. Enable or disable
a provider and synchronize its controls, producer checks, and policy modes:

```sh
python3 .guardrails/configure.py --list
python3 .guardrails/configure.py --enable-provider semgrep --sync-providers
python3 .guardrails/configure.py --set-provider-mode semgrep=enforced --sync-providers
python3 .guardrails/configure.py --disable-provider semgrep --sync-providers
```

Install a verified provider workflow template when one is available:

```sh
python3 /path/to/engineering-standards/tooling/install.py \
  --target . --provider semgrep --refresh-existing
```

The command never copies credentials. Add `SEMGREP_APP_TOKEN` as a GitHub
Actions secret, keep the provider advisory while tuning it, and promote it to
`enforced` only after the real `Semgrep` check passes on representative PRs.

Use `advisory` or `enforced`. Remove `--dry-run` to write the policy; use
`--all-operations` to configure both change and release. An `enforced` control
still needs its actual GitHub status context added to the repository ruleset.

Run a repository-specific scan and write its evidence and scorecard:

```sh
python3 .guardrails/scan.py \
  --all-catalog-controls
```

The evidence is written to `.artifacts/guardrails/evidence.json`. External
producers may contribute revision-bound JSON files under
`.artifacts/guardrails/evidence/`; the scan merges those files before
rendering the scorecard. The scorecard is printed to the terminal and written
to `.artifacts/guardrails/scorecard-YYYYMMDD-HHMMSSZ.md`. Missing producers
stay `not_run` and are never treated as passes.

For a representative terminal and Markdown result, see the
[sample scorecard output](docs/examples/sample-scorecard.md). An `ALLOW`
decision can coexist with advisory RED or ORANGE controls; only an `enforced`
control failure blocks the decision.

After the repository's real producers write revision-bound evidence, run:

```sh
python3 .guardrails/scorecard.py \
  --policy .ai/guardrails.yaml \
  --catalog .ai/control-catalog.yaml \
  --evidence .artifacts/guardrails/evidence.json \
  --operation change \
  --revision "$(git rev-parse HEAD)" \
  --subject-type git-commit
```

Use `--json` for dashboards or pull request comments. The command reports
`GREEN`, `ORANGE`, or `RED`, enforced/advisory percentages, activation and
readiness counts, and every failing, `no_result`, or `not_activated` check. Activation
describes how the control connects; readiness becomes **GREEN** only after the producer
passes for the exact revision. It exits `0` for an allowed change, `1`
for a blocked change, and `2` for invalid policy or evidence.

### What runs in CI

Producer workflows run independently and may finish in parallel. The guardrail
scorecard then uses the installed producer manifest to collect visible GitHub
check contexts for the pull-request head commit. It records `passed`, `failed`,
`blocked`, or `not_run` evidence before evaluating the selected policy.
For same-repository, non-Dependabot pull requests it also publishes or updates
one marked scorecard comment; fork and Dependabot pull requests use the job
summary and artifact because GitHub does not expose repository write permissions
or secrets to them.

This is why an Actions job can be green while an individual control is ORANGE:
the job completed successfully, but that control did not produce a passing result
for the revision. For a local scan, run the repository's real producers first,
then run the installed scanner. Generated evidence and Markdown reports are
local artifacts and are intentionally not committed.

## Adopt it in an application repository

1. Keep the application’s own ground-truth documents in that repository.
2. Select the controls that apply from the control catalog.
3. Configure the repository’s commands, languages, coverage, service accounts,
   and secrets.
4. Copy or call the workflow templates.
5. Produce evidence for the exact revision under review.
6. Run the guardrail evaluator and publish its result.
7. Confirm the actual GitHub check names.
8. Add stable checks to the repository ruleset and document any exception.

The templates do not guess a language, call a specific AI provider, configure
GitHub platform secret scanning, or fabricate FOSSA and soak-test results.

## What is ready and what needs setup

Ready to use:

- Policies and four PR review contracts.
- Build, unit-test, SonarQube, security, soak, and AI workflow interfaces.
- CodeQL and dependency-review support.
- Revision-bound policy/evidence schemas and evaluator.
- Reusable skills, prompts, templates, installers, and validators.
- A default-branch ruleset template.

Each application repository still needs to configure its own commands,
credentials, external services, CODEOWNERS, scanner projects, and actual check
names. Snyk, FOSSA, soak testing, Semgrep rules, and AI review adapters can be
adopted incrementally; they become blocking only when a repository explicitly
promotes the connected producer into its ruleset.

## License

This repository uses the MIT License. See [docs/licensing.md](docs/licensing.md)
for attribution, contributions, third-party integrations, and package metadata.

## Validate changes here

```sh
python3 tooling/validators/validate_repository.py
python3 tooling/validators/validate_documentation.py
python3 tooling/validate-skills.py
python3 -m unittest discover -s guardrails/tests -p 'test_*.py'
git diff --check
```
