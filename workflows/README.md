# Workflow Templates

See the [architecture diagrams](../docs/architecture.md) and
[control status guide](../docs/control-status.md) for the boundary between
active shared components and consuming-repository configuration.
Use the [control setup guide](../docs/control-setup.md) for the exact variables,
secrets, platform settings, and evidence required for each control.

These files are reusable/template GitHub Actions workflows. GitHub executes
workflow files from `.github/workflows/`, not from this repository's root
`workflows/` directory. A consuming repository should either:

- Copy and configure a template under `.github/workflows/`; or
- Call it from a thin `.github/workflows/` wrapper using `workflow_call`.

The templates also include a `pull_request` trigger so a copied workflow can
run directly. Direct-trigger configuration is read from repository variables;
reusable callers can provide the same values as inputs.

The canonical repository exposes one visible workflow per major producer under
`.github/workflows/`: `Build`, `Unit Tests`, `Dependency Review`, `SonarQube`,
`FOSSA`, `Secret Scan`, `Artifact Provenance`, and each AI review. `Guardrail
Scorecard` remains the aggregate compliance view. A workflow with an
unconfigured producer appears as skipped or has no result; that is **not**
evidence that the producer passed. GitHub platform controls such as secret
scanning and the Dependency Graph must be enabled in repository settings before
their checks can run.

Secret Scanning is a platform capability and does not create a standard PR
check by itself. The shared `Secret Scan` evidence probe is therefore
conditional on the `SECURITY_SETTINGS_TOKEN` Actions secret: use a narrowly
scoped GitHub App or fine-grained token with repository `Administration` read
and `Secret scanning alerts` read access. Without that credential, or when the
credential cannot read the settings, the evidence probe reports `NO RESULT`
and the scorecard remains advisory; this is different from Secret Scanning
being disabled. The evidence probe reads settings with the protected credential
and publishes its PR check with the ordinary Actions token. An optional
organization scanner is a separate check and cannot prove the GitHub platform
setting.

Artifact provenance is an advisory supply-chain control. The
`artifact-provenance.yml` template uses GitHub Artifact Attestations to bind a
release artifact to its build workflow, repository, revision, and digest. For a
pull request, this template intentionally builds the GitHub event revision
(`github.sha`, normally the synthetic merge revision) so the attested source
matches GitHub's provenance record. Code, test, and scorecard workflows use the
exact PR-head revision instead. It does not build an artifact unless the caller
supplies `build-command`, and it does not enforce verification at deployment
time. Move it to enforced only after the release or deployment path verifies
the attestation and the producer meets the shared promotion rule. The three
required steps are: build the final artifact, attest that exact file, and
verify it before release or deployment. An Actions upload is not an
attestation, and a successful attestation job is not deployment enforcement by
itself. See the [Artifact Provenance setup](../docs/control-setup.md#artifact-provenance)
for the caller permissions, expected status names, verification command, and
GREEN/ORANGE/RED/NO RESULT meanings.

New integrations should use `actions/attest@v4`, pinned to an immutable commit.
The older `actions/attest-build-provenance` action remains compatible but is a
wrapper around `actions/attest`. Artifact attestations require `id-token`,
`attestations`, and `artifact-metadata` write permissions. Availability for
private repositories depends on the GitHub plan.

The Semgrep template is token-gated for same-repository pull requests and
skips fork and Dependabot pull requests because those events do not receive
`SEMGREP_APP_TOKEN`. Its container image is pinned by digest; update that
digest only through a reviewed standards change.

The workflow installed by `install.py --github-actions` is
`guardrails-scorecard.yml`. It checks out the pull-request head
revision, collects producer check results through
`.guardrails/github_evidence.py`, and runs the installed scanner.
Evidence is evaluated against the exact revision named by the pull request,
not against GitHub's synthetic merge ref. The installed collector waits up to
600 seconds for selected asynchronous producers such as Semgrep; after that,
an unfinished advisory producer is reported as `NO RESULT`, never as passed.
Existing consumer-owned workflows are preserved during refresh; review and
retire an older attestation workflow separately if one is already present.
Scorecard comments are published only for same-repository, non-Dependabot pull
requests; all other runs use the job summary and artifact path.

## Choose an installation mode

Use a copied workflow when the consuming repository needs to customize steps,
permissions, runners, or language setup. Use a reusable workflow when the
organization wants one centrally maintained implementation and the repository
can provide its commands and configuration through inputs or variables.

If a template is exposed under `.github/workflows/` in the canonical
repository, a consuming repository can call it like this:

```yaml
name: Repository checks

on:
  pull_request:

jobs:
  build:
    uses: ravisingh11/engineering-standards/.github/workflows/build.yml@COMMIT_OR_RELEASE
    with:
      build-command: ./gradlew build
```

This repository currently stores source templates under `workflows/`, not under
`.github/workflows/`. GitHub will not resolve the `uses:` example directly from
this repository until the template is exposed under `.github/workflows/`. For
the current phase, copy and configure the template in the consuming repository
or establish an organization-approved packaging step that mirrors templates
into the supported reusable-workflow location.
Pin the shared-workflow reference to an approved commit or release after the
adoption process defines that convention.

## Contract for every template

Before marking a check required, confirm all of the following in the consuming
repository:

- The workflow has run successfully on a representative pull request.
- Its displayed check name exactly matches the ruleset context.
- Required commands, variables, secrets, permissions, and external services
  are configured.
- The failure behavior is understood and has an owner.
- Third-party Actions are reviewed and pinned according to the repository's
  [Actions security policy](../policies/github-actions-security.md).

## Configuration convention

Where an input is optional, the direct-trigger form looks for a repository
variable with the corresponding uppercase name. Examples include:

- `BUILD_COMMAND`
- `UNIT_TEST_COMMAND`
- `CODEQL_LANGUAGES`
- `SONAR_PROJECT_KEY`
- `AI_REVIEW_COMMAND`

Commands are repository-owned adapters. The shared workflows do not guess a
language, install arbitrary dependencies, call an AI provider, or configure
platform security settings. Missing required configuration fails clearly.

For SonarQube, configure the project’s new-code quality gate in SonarQube
itself. Where the installed SonarQube version supports an AI-oriented quality
gate, the consuming repository may select it there; this workflow only runs
the analysis and waits for the resulting Quality Gate and does not fabricate or
change the server-side gate.

The SonarQube template is triggered for every pull request when copied into a
consuming repository. It is intended to analyze new/changed code on each PR,
not to replace PR analysis with an end-of-week scan.

The unit-test template runs the configured test command and can require a
coverage artifact, but it does not calculate the organization's 90% new-code
coverage target by itself. Configure the language-specific coverage report in
the test command and SonarQube project settings.

The canonical repository's `Unit Tests` check is intentionally broader than
the generic template: it runs `guardrails/tests`, `tooling/tests`,
`tooling/validators/tests`, and `tooling/validate-skills.py`. Consuming
repositories should include their validator and distributed-tool test suites in
the command they provide to the generic template.

The security template always requires CodeQL and dependency review
configuration. Semgrep and a workflow-based secret scanner are optional hooks
because their implementations are organization- or repository-specific.
GitHub secret scanning and push protection remain platform settings. The
trusted `Secret Scan` verifier uses `pull_request_target` without checking out
PR code, then creates a check run against the exact PR head SHA. Any optional
organization scanner runs in a separate `pull_request` workflow with no
credentials; this prevents PR-controlled code from receiving the settings
token.

The AI review template requires a trusted repository-owned adapter command.
It does not call an AI provider, supply credentials, post review comments, or
invent a consolidation service. The adapter must write the documented JSON
result and return failure for an incomplete review or unresolved P0/P1
finding.

The FOSSA hook in `security-scanning.yml` is an adapter boundary for an
organization- or repository-owned FOSSA integration. It does not install FOSSA,
choose a license policy, or fabricate a result. Configure `FOSSA_COMMAND` and
the `FOSSA_API_KEY` secret only where the repository has a real FOSSA project.

The Snyk hook in `security-scanning.yml` is the shared provider boundary for
Snyk Open Source. Set `SNYK_OPEN_SOURCE_COMMAND` and pass the `SNYK_TOKEN`
secret when using it. The canonical repository also contains a concrete
`.github/workflows/snyk.yml` example that runs Snyk Code on source and runs
Snyk Open Source when a supported dependency manifest exists. It uses the
official Snyk setup action pinned to an immutable commit. The consuming
repository owns its Snyk project, severity threshold, ignore policy, and
whether CodeQL or Snyk Code is the primary source-code SAST gate.
Snyk checks are advisory by default; a consuming repository may add the real
check names to its ruleset after the producer meets the shared promotion rule.

GitHub does not support empty Actions secrets. This repository reserves an
inactive `SNYK_TOKEN` name with the exact value `GUARDRAILS_NOT_CONFIGURED`;
the example workflow treats that sentinel as absent and skips both scans.
Replace the value with a real Snyk credential before enabling the provider.
Do not use an arbitrary dummy value because any other non-empty value is
treated as a configured credential.

### Semgrep

`semgrep.yml` is the verified Semgrep provider template. It runs `semgrep ci`
in the official Semgrep container and publishes the `Semgrep` check. Configure
the `SEMGREP_APP_TOKEN` Actions secret before enabling the provider. Keep it
advisory while rules and thresholds are tuned. Move it to enforced only after
the producer meets the shared promotion rule. The template does not define a
fake organization rule set or pass credentials to any other workflow.

The reserved value `GUARDRAILS_NOT_CONFIGURED` keeps the workflow installed but
inactive. Replace it with a real token to run Semgrep; an empty or reserved
value produces configuration evidence and skips the provider scan.

When a workflow produces guardrail evidence, write a check-specific JSON file
under `.artifacts/guardrails/evidence/`. The installed `scan.py` command merges
those files into the repository scorecard. Evidence must identify the exact
revision; a configured workflow without revision-bound output is not a pass.

`soak.yml` is a scheduled and manually dispatchable endurance-test template.
The consuming repository owns the workload, duration, resource thresholds, and
interpretation of degradation. Its evidence must identify the exact revision.
Use a PR wrapper only for soak tests that fit the repository's PR time budget.

## Action pinning

The source templates pin third-party Actions to immutable commit SHAs and keep
the human-readable release tag in a comment. Update a pin only after reviewing
the referenced release, its changelog, permissions, and transitive behavior.
Keep the pin-to-release mapping in the consuming repository's dependency-update
process and retest the workflow before making it required.
