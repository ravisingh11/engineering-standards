# Control setup guide

This guide connects each control to the configuration required in an
application repository. A control is GREEN only after its real producer runs
against the exact revision and writes `passed` evidence.

## Before adding controls

Install the shared evaluator, catalog, producer manifest, GitHub Checks
collector, and aggregate scorecard workflow:

```sh
python3 /path/to/engineering-standards/tooling/install.py \
  --target . \
  --github-actions
```

Then:

1. Keep application ground truth in the application repository.
2. Copy the relevant templates from `workflows/` into `.github/workflows/`.
3. Set repository variables and secrets listed below.
4. Run a representative pull request.
5. Confirm the real GitHub check name.
6. Add the check to the repository ruleset only after it passes reliably.

Do not add a check to the policy until its producer is real. Do not describe a
missing or `not_run` result as a pass. `--refresh-existing` preserves an
existing consumer workflow and removes only known guardrail-owned migration
files; update workflow files through the consuming repository's normal
pull-request process. Use `--dry-run` to inspect cleanup before applying it.

## Repository Validation — GREEN ✅

**Protects:** the repository contracts that make the standards and Guardrails
safe to consume. The canonical producer is `.github/workflows/validate.yml`;
its GitHub check name is `Validate / repository`.

In this repository, `tooling/validators/validate_repository.py` verifies:

- skill frontmatter and required agent definitions;
- control-catalog fields, identifiers, and allowed values;
- guardrail policy, evidence, and JSON Schema contracts;
- documentation integrity;
- the absence of accidentally committed machine-local paths; and
- commit whitespace through `git show --check` in CI.

`Validate / repository` runs only after documentation, change-scope, and
ground-truth jobs complete. GREEN means those dependencies and the repository
validator passed for the exact revision under review.

It does not compile application code, run application tests, judge architecture,
or perform security analysis. Those belong to separate controls. A consuming
repository should provide an equivalent repository-owned validator instead of
copying checks for standards-specific directories it does not have.

Troubleshoot locally with:

```sh
python3 tooling/validators/validate_repository.py
git show --check --format= HEAD
```

## Documentation Validation — GREEN ✅

**Protects:** documentation navigation and explicit change-to-documentation
contracts. The canonical producer is `.github/workflows/validate.yml`; its
GitHub check name is `Validate / docs`.

Configure `.ai/documentation.yaml` with mappings from implementation paths to
the documentation paths that must change with them. The validator checks:

- that the policy uses the supported version and mapping structure;
- that configured paths are relative, repository-contained POSIX patterns;
- that every configured documentation pattern matches a real file;
- that local Markdown links resolve inside the repository; and
- on a PR or Git range, that triggered implementation changes include a mapped
  documentation change.

GREEN means those checks passed for the exact revision or change range. The
validator does not fetch external links, judge writing quality, or decide
whether application-specific architecture is correct. Declared repository
ground truth is handled separately below.

Troubleshoot locally with:

```sh
python3 tooling/validators/validate_documentation.py
```

## Ground Truth — advisory until configured

**Protects:** the application-owned documents that define architecture,
engineering constraints, testing, security, deployment, and contribution
expectations. The producer is `.guardrails/validate_ground_truth.py`; the
GitHub check name is `Validate / ground truth`.

This control is separate from generic documentation validation. Each
application repository declares only the documents it treats as local truth in
`.ai/ground-truth.yaml`:

```json
{
  "version": 1,
  "documents": [
    {"path": "AGENTS.md"},
    {"path": "ARCHITECTURE.md"},
    {"path": "STANDARDS.md"},
    {"path": "TESTING.md"},
    {"path": "SECURITY.md"},
    {"path": "DEPLOYMENT.md"},
    {"path": "CONTRIBUTING.md"}
  ]
}
```

The validator parses the policy and confirms that every declared path exists as
a file. GREEN means all declared documents are present at the revision under
review. A missing file makes the producer fail; keeping the control advisory
means that failure remains visible without blocking merge unless the repository
explicitly adds the check to its ruleset.

The validator does not judge whether a document is accurate, complete, or
internally consistent. AI Repo Standards Review and human domain review use the
documents' content. The control does not invent application standards or
require every repository to use the same document set.

Troubleshoot locally with:

```sh
python3 .guardrails/validate_ground_truth.py \
  --policy .ai/ground-truth.yaml
```

Promote this control to enforced only after the repository has declared and
maintained its own ground truth.

## Change Scope — advisory by default

**Protects:** review quality and cycle time by identifying unexpectedly broad
or oversized changes. The producer is
`tooling/validators/inspect_change_scope.py`; the GitHub check name is
`Validate / scope`.

Configure `.ai/change-scope.yaml` with repository-appropriate limits for:

- included files;
- added lines;
- total changed lines; and
- added lines in the largest file.

The validator also reports binary-file count and supports exclusions for
generated, vendored, lock, documentation, or other low-signal paths. It writes
the measured values, configured thresholds, and one finding for every exceeded
threshold.

Thresholds are advisory: exceeding one records `failed` scope evidence but does
not make the inspection command fail. A successful `Validate / scope` workflow
therefore means the inspection executed; reviewers must still read its metrics
and findings. Do not interpret it as proof that the PR is small.

The control measures review surface, not correctness or risk. It should prompt
a split or explicit reviewer judgment, not block legitimate generated changes,
migrations, or other justified work automatically.

Inspect the staged change locally with:

```sh
python3 tooling/validators/inspect_change_scope.py
```

## Build — GREEN ✅

Use `workflows/build.yml`.

Configure either workflow-call inputs or repository variables:

```text
BUILD_COMMAND=your repository build command
SETUP_COMMAND=optional dependency/toolchain setup
WORKING_DIRECTORY=optional subdirectory
```

The command must return non-zero on a build failure. The resulting check name
should be `Build`.

## Unit Tests — GREEN ✅

Use `workflows/unit-tests.yml`.

Configure:

```text
UNIT_TEST_COMMAND=your unit test command, including coverage flags when needed
SETUP_COMMAND=optional dependency/toolchain setup
WORKING_DIRECTORY=optional subdirectory
COVERAGE_PATH=coverage output path
COVERAGE_REQUIRED=true when coverage is required for this repository
```

Tests must contain meaningful assertions. Coverage is evidence for new or
changed code; it is not a reason to force unrelated historical cleanup.

## CodeQL / SAST — GREEN ✅

Use the `codeql` job in `workflows/security-scanning.yml`.

Configure:

```text
CODEQL_LANGUAGES=javascript-typescript,python
CODEQL_BUILD_MODE=none or autobuild
```

Use the language identifiers supported by CodeQL. Compiled languages may need
`autobuild` or a repository-specific build adapter. The workflow requests
`security-events: write` only for the CodeQL job.

For a Python repository, `CODEQL_LANGUAGES=python` with
`CODEQL_BUILD_MODE=none` is sufficient. The producer must publish the check
context as `CodeQL` for the scorecard to report `codeql-sast` as GREEN.

## Secrets scanning — GREEN ✅

Enable GitHub secret scanning and push protection in the organization or
repository Security settings. These are platform controls; the Actions
workflow cannot enable them.

The repository API exposes these settings only to an administrator. To have
the PR scorecard verify them as a `GitHub Secret Scan` check, add a narrowly scoped
fine-grained GitHub token or GitHub App token as the `SECURITY_SETTINGS_TOKEN`
Actions secret. The trusted `pull_request_target` verifier does not check out
PR code; it publishes the result explicitly against the PR head SHA. Without
that credential the verifier publishes `NO RESULT`; it never treats an
unprivileged token or a workflow's existence as proof of activation. The
optional organization scanner runs separately on `pull_request`, without
credentials, and its result is included when configured.

If the organization also requires a scanner command, configure
`SECRET_SCAN_COMMAND` and use the organization scanner workflow. Keep the
command scanner-specific and do not give it repository secrets.

## Dependency Review — GREEN ✅

Use the `dependency-review` job in `workflows/security-scanning.yml`.

First enable **Dependency Graph** in the repository’s Settings → Security →
Advanced Security. Set the repository variable below only after that platform
setting is enabled; the canonical check workflow uses it to avoid presenting a
disabled GitHub producer as a failed scan:

```text
DEPENDENCY_GRAPH_ENABLED=true
```

Configure the severity threshold through the workflow input or repository
variable:

```text
DEPENDENCY_FAIL_ON_SEVERITY=high
```

Set the repository’s license and vulnerability policy before making the check
required. The displayed check name should be `Dependency Review`.

Dependency Review is not Dependabot. Dependabot proposes dependency update or
security pull requests; Dependency Review evaluates dependency changes already
present in the current pull request. The `.ai/control-catalog.yaml` and
`.ai/guardrails.yaml` files only declare and configure the control. The actual
scan runs in GitHub Actions through `actions/dependency-review-action`.

## Dependabot — advisory until configured

Add `.github/dependabot.yml` to configure scheduled dependency update pull
requests. The file activates Dependabot version updates, but GitHub’s
Dependabot security-update capability is a separate repository setting. The
local scorecard reports configuration presence as `NO RESULT`; it does not
pretend that a local file proves GitHub activation. Verify the GitHub setting
and provide revision-bound producer evidence before treating Dependabot as fully
operational or enforcing it.

The canonical `Dependabot Verification` workflow performs this verification in
GitHub using the repository API, writes revision-bound evidence, and runs the
scorecard with that evidence. Copy it into a consuming repository when you want
the Dependabot control to become GREEN after the platform settings pass.

## SonarQube — ORANGE 🟠 until configured, then GREEN ✅

Use `workflows/sonar.yml` for every pull request.

Configure the repository or organization variables:

```text
SONAR_HOST_URL=https://your-sonarqube-instance
SONAR_PROJECT_KEY=your-project-key
SONAR_PROJECT_BASE_DIRECTORY=.
SONAR_ARGS=optional scanner arguments
```

Add the `SONAR_TOKEN` secret. Configure the SonarQube Quality Gate on the
SonarQube server, targeting new and changed code. Select an AI-oriented gate
there when the installed SonarQube version supports and the organization has
approved it.

The GitHub check should be named `SonarQube Quality Gate`. The workflow runs on
every pull request; it is not an end-of-week scan.

## FOSSA — ORANGE 🟠 until configured, then GREEN ✅

FOSSA requires an external project and policy.

1. Create or select the FOSSA project for the application.
2. Define the approved license and vulnerability policy.
3. Store `FOSSA_API_KEY` as an organization or repository secret.
4. Provide the organization-approved `FOSSA_COMMAND` adapter.
5. Use the `fossa` job in `workflows/security-scanning.yml`.
6. Confirm the result is bound to the exact revision and the check is named `FOSSA`.

The shared repository does not install FOSSA, choose a license policy, or
fabricate a result.

## Artifact Provenance — ORANGE 🟠 until configured, then GREEN ✅

Artifact provenance creates a signed, revision-bound statement about how a
release artifact was built. The attestation binds the artifact digest to the
repository, workflow, source revision, and builder identity. It complements
dependency and source scanning; it does not replace CodeQL, Dependency Review,
Snyk, or FOSSA.

This control has three separate parts:

1. **Build** — produce the exact file that will be released or deployed.
2. **Attest** — use GitHub Artifact Attestations to sign that file.
3. **Verify** — make the release or deployment path reject a file whose
   attestation is missing or invalid.

An upload to Actions artifacts alone is not an attestation. A successful build
alone is not evidence of provenance. The control is GREEN only when the
attestation step succeeds for the artifact that will actually be promoted and
the verification step is exercised.

Call the reusable template from a workflow that produces a real artifact:

```yaml
jobs:
  artifact-provenance:
    # Copy workflows/artifact-provenance.yml into .github/workflows first.
    uses: ./.github/workflows/artifact-provenance.yml
    with:
      build-command: ./scripts/build-release.sh
      artifact-path: dist/my-app-*.tar.gz
```

The calling job should use the catalog context so the scorecard can collect it
consistently:

```yaml
jobs:
  artifact-provenance:
    name: Artifact Provenance
    uses: ./.github/workflows/artifact-provenance.yml
    permissions:
      contents: read
      id-token: write
      attestations: write
      artifact-metadata: write
    with:
      build-command: ./scripts/build-release.sh
      artifact-path: dist/my-app.tar.gz
```

The caller must grant `id-token: write`, `attestations: write`, and
`artifact-metadata: write`. Keep those permissions on this job rather than
granting them to unrelated jobs. The template checks out `github.sha`: on a
pull request this is normally GitHub's synthetic merge revision, which is
intentional because the artifact was built from the tested merge tree. For a
release workflow, trigger from the immutable tag or commit that produced the
release artifact.

Verify the result during release or deployment, before promotion:

```bash
gh attestation verify dist/my-app.tar.gz --repo OWNER/REPOSITORY
```

The verification command must run against the same artifact bytes that will be
released. If the artifact is rebuilt, repackaged, copied, or signed by another
system, verify the final artifact again. Record the verification result in the
release evidence used by the scorecard where release evidence is enabled.

Expected outcomes:

- **GREEN** — the `Artifact Provenance` producer check passed and the exact
  artifact verifies successfully.
- **ORANGE** — the workflow, permissions, artifact, or deployment verification
  is not configured; this is advisory and does not block by default.
- **RED** — the producer ran and attestation or verification failed. Treat this
  as a release defect even while the control remains advisory.
- **NO RESULT** — the workflow did not run for the revision under review. Do
  not treat a skipped job or an uploaded Actions artifact as proof.

Do not promote this control to enforced until the deployment path rejects
artifacts without a valid attestation. For public repositories, GitHub makes
artifact attestations available on current plans; private or internal
repositories require the supported GitHub Enterprise Cloud plan. Confirm plan
availability and organization policy before rollout.

## Snyk — ORANGE 🟠 until configured, then GREEN ✅ (advisory by default)

Snyk is an external provider and an important recommended gate, not a required
organization-wide merge control yet. Use Snyk Open Source for dependency and
supply-chain vulnerabilities. Use Snyk Code for source-code security analysis when
the repository selects it instead of, or in addition to, CodeQL. Do not create
two blocking checks for the same finding without an explicit defense-in-depth
decision.

For this repository, `.github/workflows/snyk.yml` is the working example. It
runs Snyk Code on source and runs Snyk Open Source only when a supported
dependency manifest exists. This repository currently has no dependency
manifest, so the Open Source job reports not applicable rather than pretending
that an empty dependency scan is a real result.

To activate Snyk in a consuming repository:

1. Create or connect the repository project in Snyk.
2. Add `SNYK_TOKEN` as an organization or repository secret.
3. Copy the example workflow or call the shared security workflow.
4. Set a severity threshold, initially `high`, and define approved
   ignore/expiry policy in Snyk.
5. Run the workflow on every pull request and the default branch.
6. Confirm the actual check names: `Snyk Code` and/or `Snyk Open Source`.
7. Leave the checks advisory while the team learns the findings, tunes
   thresholds, and establishes ownership.
8. Add those names to the GitHub ruleset only when the team explicitly
   promotes Snyk to an enforced gate.
9. Record revision-bound evidence for the scorecard.

Fork pull requests do not receive repository secrets. The example therefore
does not attempt a token-backed scan on an untrusted fork; use a trusted
organization-level integration or a separate unprivileged validation path if
fork coverage is required.

Snyk CLI exit code `1` means vulnerabilities were found and should fail the
Snyk scan check; because the policy is advisory by default, that failure does
not automatically block merge. Exit code `3` means no supported project was detected and must
be treated as not applicable only when the repository has no supported
manifest. See the [Snyk CLI test documentation](https://docs.snyk.io/developer-tools/snyk-cli/commands/test).

Adoption path:

```text
Not connected
      ↓
Advisory scan
      ↓
Findings tuned and owned
      ↓
Required Snyk check for selected repositories
```

## Semgrep — ORANGE 🟠 until configured, then GREEN ✅

Semgrep requires an organization-owned rule set and execution path.

Semgrep is a supported advisory control in the catalog. The shared repository
does not invent a universal rule set or scanner command. Configure the
repository secret `SEMGREP_APP_TOKEN` and an organization-approved workflow or
adapter that publishes a check named `Semgrep`; until then it remains not
activated.

For the shared template, install and enable it with:

```sh
python3 /path/to/engineering-standards/tooling/install.py \
  --target . --provider semgrep --refresh-existing
python3 .guardrails/configure.py \
  --enable-provider semgrep --sync-providers
```

The template runs `semgrep ci` in the official Semgrep container on pull
requests and the default branch. It requires `SEMGREP_APP_TOKEN`; it does not
invent or embed organization-specific rules. Semgrep is advisory until the
consumer changes its mode to `enforced` and adds the exact `Semgrep` check to
its ruleset. Semgrep's documented GitHub Actions setup requires a repository
workflow and `SEMGREP_APP_TOKEN` secret. [Semgrep GitHub reusable workflow
documentation](https://semgrep.dev/docs/kb/semgrep-ci/github-reusable-workflows-semgrep)
is the provider reference.

1. Agree on executable rules, starting with tenant isolation, SQL injection,
   token logging, TLS validation, and unauthenticated admin endpoints.
2. Store the approved `SEMGREP_COMMAND` as a repository variable or workflow
   input.
3. Use the `semgrep` job in `workflows/security-scanning.yml`.
4. Confirm the real check name and revision-bound evidence.

Do not add a placeholder Semgrep command just to make the status green.

## Soak Check — GRAY ⚪ until repository setup, then GREEN ✅

Use `workflows/soak.yml` for scheduled or manually triggered endurance checks.

Configure:

```text
SOAK_COMMAND=repository-owned endurance test command
SOAK_WORKING_DIRECTORY=optional subdirectory
```

The producer must record workload, duration, resource observations,
thresholds, degradation findings, and the exact revision. The application
repository owns the definition of acceptable runtime behavior.

## AI reviews — ORANGE 🟠 until configured, then GREEN ✅

Use `workflows/ai-pr-review.yml` with a trusted repository-owned or
organization-owned adapter.

Configure:

```text
AI_REVIEW_COMMAND=approved adapter command
AI_REVIEW_WORKING_DIRECTORY=optional subdirectory
```

The adapter runs once for each role—engineering, QA, security, and repository
standards—and writes:

```text
.ai-review/results/engineering.json
.ai-review/results/qa.json
.ai-review/results/security.json
.ai-review/results/repo-standards.json
```

Each result must contain a `findings` array. The consolidation job blocks
unresolved `P0` and `P1` findings and fails when any reviewer does not finish.
The shared workflow does not choose an AI provider or handle credentials.

## Repository standards review — ORANGE 🟠 until adapter is configured

The adapter should read these files when they exist:

```text
AGENTS.md
ARCHITECTURE.md
STANDARDS.md
TESTING.md
SECURITY.md
DEPLOYMENT.md
CONTRIBUTING.md
```

It must distinguish organization policy from repository ground truth and must
not invent standards where documentation is absent.

## Branch protection — GREEN ✅ after activation

Use `rulesets/default-branch-protection.json` as the starting point.

1. Require pull requests and resolved conversations.
2. Block direct pushes, force pushes, and branch deletion.
3. Require the actual check names produced by the installed workflows.
4. Start with zero required approvals for a single-developer repository. Raise
   `required_approving_review_count` to `1` or more when multiple engineers or
   higher-risk review requires it.
5. Enable CODEOWNER approval only after the application repository has a valid
   `.github/CODEOWNERS` file.

Do not copy placeholder check names into a ruleset before observing the real
GitHub check contexts.

## Verify progress to all greens

Policy-scoped scorecard:

```sh
python3 .guardrails/scorecard.py \
  --policy .ai/guardrails.yaml \
  --catalog .ai/control-catalog.yaml \
  --evidence .artifacts/guardrails/evidence.json \
  --operation change \
  --revision "$(git rev-parse HEAD)" \
  --subject-type git-commit
```

Full onboarding view, including controls not yet selected in policy:

```sh
python3 .guardrails/scorecard.py \
  --policy .ai/guardrails.yaml \
  --catalog .ai/control-catalog.yaml \
  --evidence .artifacts/guardrails/evidence.json \
  --operation change \
  --revision "$(git rev-parse HEAD)" \
  --subject-type git-commit \
  --all-catalog-controls
```

Keep adding and configuring controls until the full onboarding view reports:

```text
Service readiness: GREEN
Controls: GREEN N, ORANGE 0, GRAY 0, RED 0
```

That is the evidence-backed definition of “all green.”
