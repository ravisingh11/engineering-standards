# Task 3 report: Guardrails v2 installation and producers

## Result

Implemented the clean-break Guardrails v2 installer and Core/GitHub producer
distribution from base `76cec2524a437ad87d2f2ccd8db636bc9e713db7`.
A normal install now deploys the Core runtime plus Actions workflows; the
GitHub profile is additive, `--no-actions` remains local-only, and safe local
hooks are opt-in. Recognized v1 runtime/configuration is rejected with clean
reinstall guidance and is never migrated or deleted.

The self repository now uses canonical v2 policy, profiles, catalog, provider
configuration, schemas, runtime, validators, local Semgrep rules, and producer
workflows. Active runtime and workflows do not install or consume a producer
manifest.

## Implementation

- `tooling/install.py` installs canonical v2 runtime/configuration, Core
  workflows by default, the additive GitHub workflow overlay, local-only mode,
  and validated no-overwrite pre-commit hooks. Refresh updates only known
  installer-owned product files and marked workflows, including known files
  nested in fixture and skill directories, while preserving unknown consumer
  files. Every planned destination is rejected before writes when it or a
  parent below the selected repository root is a symlink. `--local-hooks`
  requires `git rev-parse --show-toplevel` to equal the selected target exactly,
  so a nested target cannot alter a parent repository's hooks.
  `--merge-existing --profile github` preserves existing v2 policy content
  while activating the GitHub profile and installing its overlay.
- `action.yml` passes every caller-controlled file input through the step
  environment and quoted Bash variables. No file input is rendered directly
  into the generated shell program.
- `tooling/produce_guardrail_evidence.py` emits nested v2 evidence for generic
  repository commands, Semgrep CE, and Gitleaks. Missing commands and unavailable
  or wrong-version tooling emit `not_run`; raw setup/build/test/coverage and
  scanner command text is replaced by stable capability labels plus SHA-256
  command digests. Every evidence record and reason is centrally bounded to the
  evidence schema's 1,000-character limit after labels and diagnostics are
  composed. Standalone execution now
  rejects an unresolved/non-HEAD revision or dirty worktree before running a
  producer or writing evidence, and successful evidence records the resolved
  full HEAD commit. Semgrep operational scans use `--error` and exclude both
  installed and source rule-test fixtures, so findings fail while intentionally
  unsafe fixtures never become operational findings.
- `tooling/scan_repository.py` runs all nine Core providers after exact clean
  revision binding and falls back to installed validators.
- `security/semgrep/guardrails.yml` contains repository-owned Python and
  JavaScript/TypeScript rules for disabled TLS verification with positive and
  negative fixtures. The installer distributes those fixtures under
  `.guardrails/semgrep-tests/fixtures`, and the installed workflow self-tests
  the rule pack from that path before scanning.
- `workflows/` and `.github/workflows/` contain independent revision-bound Core
  producers, additive GitHub producers, least permissions, immutable action
  references, timeouts, PR-head checkout, no persisted credentials, truthful
  platform-setting checks, and release/artifact-scoped provenance. The
  scorecard has `actions: read` for workflow-run and artifact provenance. The
  Secret Protection and Dependabot trusted-base workflows write a fixed JSON
  evidence member, upload it under an exact run-bound artifact name with an
  immutable `actions/upload-artifact` reference, and only then publish their
  display checks. Their provider contracts declare the artifact name prefix,
  fixed member, and external ID prefix. Collection requires the exact prefix,
  run ID, workflow name, installed workflow path (accepting the live bare path
  or exact `@trusted-ref` form), and `pull_request_target` event before listing
  that run's artifacts. It does not use the run payload's `head_sha` or
  `pull_requests` fields to bind this event. The trusted workflow artifact binds
  repository, run ID, event, trusted base SHA/ref, candidate head SHA, provider,
  and status; the collector validates those fields against the scorecard's
  trusted-base and candidate-head inputs.
  Native Actions checks also require matching workflow-suite identity. Custom
  PR-head checks bind to their trusted `pull_request_target` run through the
  exact external ID and details run ID without claiming the separate base-SHA
  workflow suite is the custom check suite. The collector requires exactly one
  nonexpired artifact bound to that run and revision, safely reads only the
  fixed JSON member, and validates its run, revision, provider, status, and
  bounded summary. Artifact evidence is authoritative; custom-check status is
  display-only. Dependabot verification parses GitHub's `enabled` and `paused`
  response fields and treats the endpoint's documented 404 as disabled/failing,
  while authentication, permission, or unknown responses remain skipped/NO
  RESULT.
- Gitleaks container and pre-commit execution rely on the image ENTRYPOINT and
  pass `git --redact --no-banner .`; only exact-version host execution includes
  the leading `gitleaks` executable.
- The changed-code-coverage provider points to
  `workflows/changed-code-coverage.yml` and declares the matching `Changed Code
  Coverage` workflow identity. Standards validation cross-checks available
  provider templates against their declared workflow names.
- Fresh provider selections contain no default-disabled vendor supplementals.
  Optional provider definitions remain available for explicit later activation
  with `configure.py --add-supplemental`.
- `guardrails/validate_repository.py` is the repository-neutral installed v2
  validator. The self workflow runs it for every consumer and conditionally
  runs `tooling/validators/validate_repository.py` when the engineering
  standards source tree is present.
- `guardrails-scorecard.yml` executes token-bearing Python only from the exact
  trusted base SHA. Only the candidate PR policy is sparse-checked out at a
  fixed path, rejected if any path component is a symlink, parsed only as data,
  and never executed. Profiles, catalog, provider selections, check contracts,
  artifact requirements, and workflow identity remain bound to the trusted
  base. The shared workflow emits
  timestamped evidence plus paired timestamped scorecard JSON/Markdown, writes
  the Markdown to the job summary, and uploads the complete artifact directory.
- `skills/prepare-safe-change` now ships a nested v2 evidence example and an
  executable evaluator command with every required v2 contract argument. Fresh
  installs and refreshes distribute the example with the skill.

## TDD evidence

### Installer RED

```text
python3 -m unittest tooling.tests.test_install -v
Ran 10 tests in 0.065s
FAILED (failures=6, errors=6)
```

Failures identified the absent default Actions install, profiles/no-actions/
local-hooks interfaces, producer runtime, additive GitHub policy, and clean v1
rejection.

### Workflow/distribution RED

```text
python3 -m unittest tooling.tests.test_action_distribution -v
Ran 11 tests in 0.774s
FAILED (failures=26, errors=20)
```

Failures identified v1 self-runtime residue, producer-manifest references,
missing Core/GitHub workflow distribution, old Semgrep execution, missing
timeouts and command-variable contracts, and PR-scoped artifact provenance.

### Producer/scanner GREEN

```text
python3 -m unittest tooling.tests.test_produce_guardrail_evidence -v
Ran 8 tests in 0.005s
OK

python3 -m unittest tooling.tests.test_scan_repository.LocalEvidenceTests.test_available_validators_use_canonical_core_provider_ids -v
Ran 1 test in 0.004s
OK
```

### Focused GREEN

```text
python3 -m unittest tooling.tests.test_install tooling.tests.test_produce_guardrail_evidence tooling.tests.test_scan_repository tooling.tests.test_action_distribution -v
Ran 39 tests in 1.096s
OK
```

### Evidence-schema boundary RED/GREEN

Before limiting output records to the schema boundary:

```text
Ran 1 test in 0.002s
FAILED (failures=2)
```

After the fix:

```text
Ran 1 test in 0.002s
OK
```

### Review-request RED

```text
python3 -m unittest tooling.tests.test_install tooling.tests.test_action_distribution tooling.tests.test_github_evidence tooling.tests.test_produce_guardrail_evidence tooling.validators.tests.test_guardrails_contracts -v
Ran 70 tests in 1.281s
FAILED (failures=16, errors=2)
```

The focused failures proved the six requested gaps: default vendor
supplementals leaked into fresh collection/scorecards, scorecard workflow-run
permission and custom-check provenance fields were absent, installed Semgrep
fixtures and a portable validator were missing, and standalone producers
accepted fake revisions and dirty worktrees.

### Review-request GREEN

```text
python3 -m unittest tooling.tests.test_install tooling.tests.test_action_distribution tooling.tests.test_github_evidence tooling.tests.test_produce_guardrail_evidence tooling.validators.tests.test_guardrails_contracts -v
Ran 70 tests in 1.386s
OK
```

This includes fresh consumer installation tests that execute the installed
collector, scorecard, and portable validator and verify the distributed
Semgrep rule-test fixture paths.

### Final review RED

```text
python3 -m unittest guardrails.tests.test_evaluate tooling.tests.test_produce_guardrail_evidence tooling.tests.test_action_distribution tooling.tests.test_install tooling.tests.test_github_evidence tooling.validators.tests.test_guardrails_contracts -v
Ran 93 tests in 1.857s
FAILED (failures=11, errors=3)
```

The failures proved operational Semgrep omitted failure-on-findings and fixture
exclusions, custom checks accepted forged/unrelated workflow provenance, the
installer followed destination/parent symlinks, and merge-existing installed
GitHub workflows without activating the policy profile.

### Final review GREEN

```text
python3 -m unittest guardrails.tests.test_evaluate tooling.tests.test_produce_guardrail_evidence tooling.tests.test_action_distribution tooling.tests.test_install tooling.tests.test_github_evidence tooling.validators.tests.test_guardrails_contracts -v
Ran 93 tests in 1.511s
OK
```

The integration coverage includes container and exact-host Semgrep command
contracts, generic valid/forged custom-check provenance, unchanged external
files after symlink attacks, and a fresh merge-existing GitHub activation.

### Final Task 3 review RED/GREEN

Each finding was driven independently from a focused failing regression:

```text
Composite action input injection: 1 test, FAILED (failures=1)
Custom check suite/path provenance: 3 tests, FAILED (failures=2, errors=1)
Dependabot response parsing: 5 tests, FAILED (failures=2)
Changed coverage contract/template identity: 2 tests, FAILED (failures=2)
```

After the fixes, the combined focused suite passed:

```text
python3 -m unittest tooling.tests.test_action_inputs tooling.tests.test_dependabot_workflow tooling.tests.test_github_evidence guardrails.tests.test_evaluate tooling.tests.test_produce_guardrail_evidence tooling.tests.test_action_distribution tooling.tests.test_install tooling.validators.tests.test_guardrails_contracts -v
Ran 104 tests in 2.485s
OK
```

### Second Task 3 review RED

The four original follow-up findings failed together before implementation:

```text
python3 -m unittest tooling.tests.test_github_evidence tooling.tests.test_install tooling.tests.test_action_distribution -v
Ran 50 tests in 1.070s
FAILED (failures=8)
```

Those failures covered realistic `path@ref` workflow responses and custom
cross-event suites, trusted-base scorecard execution, nested installer-owned
refresh, and exact Git repository-root hooks.

The two shared-product findings then failed independently:

```text
python3 -m unittest \
  tooling.tests.test_install.InstallerTests.test_installed_prepare_safe_change_skill_executes_v2_evaluator_example \
  tooling.tests.test_action_distribution.ActionDistributionTests.test_demo_scorecard_workflow_is_an_unmodified_canonical_copy \
  tooling.tests.test_action_distribution.ActionDistributionTests.test_scorecard_writes_paired_timestamped_json_markdown_and_job_summary -v
Ran 3 tests in 0.023s
FAILED (failures=2, errors=1)
```

The demo-copy assertion is owned by Task 4 and is not part of the Task 3 commit;
Task 3 retains canonical/self workflow distribution coverage, while Task 4
regenerates and verifies its embedded copy after this commit is rewritten.

### Second Task 3 review focused GREEN

```text
python3 -m unittest tooling.tests.test_github_evidence tooling.tests.test_install tooling.tests.test_action_distribution -v
Ran 52 tests in 1.195s
OK
```

### Final Task 3 repair RED/GREEN

The final review findings were added together before implementation. The
focused run proved the missing artifact authority and validation, incorrect
Gitleaks container/pre-commit argv, absent immutable upload step, missing
provider artifact contract, and Dependabot 404 misclassification:

```text
python3 -m unittest tooling.tests.test_github_evidence tooling.tests.test_produce_guardrail_evidence tooling.tests.test_install tooling.tests.test_action_distribution tooling.tests.test_dependabot_workflow tooling.validators.tests.test_guardrails_contracts -v
Ran 102 tests in 2.948s
FAILED (failures=6, errors=18)
```

After implementation, the same focused command passed:

```text
Ran 102 tests in 2.847s
OK
```

The artifact cases cover a forged display check; missing, wrong-name, expired,
duplicate, and wrong-run artifacts; wrong archive member, revision,
provider, and status; and authoritative artifact pass, fail, and NO RESULT.

### Second Task 3 review validation

The final Task 3-owned validation excluded only the concurrently owned Task 4
embedded-demo regression, which must be regenerated after the rewritten Task 3
commit is available:

```text
Guardrails tests: 14 tests, OK
Tracked Task 3 tooling tests: 110 tests, OK
Validator tests: 54 tests, OK
Skill script tests: 4 + 3 + 13 tests, OK
Validated 31 skills
Repository validation passed for 31 skills, 29 controls, schemas, and documentation
Documentation validation passed
git diff --check: exit 0
```

### Trust-boundary repair RED/GREEN

Three independent regressions were observed failing before their production
changes:

```text
Refresh without repeated --profile: 1 test, FAILED (failures=1)
Artifact-backed pull_request attacker run: 1 test, FAILED (failures=1; forged artifact passed)
Trusted contracts/base/ref workflow boundary: 3 tests, FAILED (failures=2, errors=3)
Artifact contract without external ID: 1 test, FAILED (failures=1; forged check passed)
```

The repair now derives active profiles from the existing v2 policy during
`--refresh-existing`, so installer-owned GitHub workflows are refreshed without
repeating `--profile github`. Token-bearing collection and scorecard rendering
use candidate policy with trusted-base profiles, catalog, and provider
contracts. Removing artifact fields from a candidate provider file therefore
cannot weaken collection: a forged display check without the trusted run-bound
artifact remains `not_run`.

Artifact-backed/external-ID evidence now requires the exact declared workflow
name, a bare exact workflow path or exact `workflow_path@trusted_ref`, and event
`pull_request_target` before artifact lookup. The artifact itself supplies the
trusted base revision/ref and candidate head association. A valid artifact
attached to an attacker-controlled `pull_request` run is `not_run`.

Focused GREEN after the repair:

```text
python3 -m unittest tooling.tests.test_github_evidence tooling.tests.test_action_distribution tooling.tests.test_install -v
Ran 62 tests in 1.235s
OK
```

The complete tooling discovery ran 121 tests and reported only the two expected
Task 4 generated-demo equality failures for the preserved pre-repair copies of
`.guardrails/github_evidence.py` and `guardrails-scorecard.yml`. Per repair
scope, no `examples/python-demo` file was changed or staged. Excluding only that
Task 4 generated-copy module, 115 tooling tests passed; all 54 validator tests,
5 demo tests, skill suites (4, 3, and 13 tests), repository/documentation
validators, Python compilation, and diff checks also passed.

### Final live-API and evidence-safety repair RED/GREEN

The captured live `pull_request_target` response, safe artifact redirect, and
producer evidence regressions failed before implementation:

```text
python3 -m unittest tooling.tests.test_github_evidence tooling.tests.test_produce_guardrail_evidence -v
Ran 48 tests in 0.487s
FAILED (failures=11)

python3 -m unittest tooling.tests.test_action_distribution.ActionDistributionTests.test_github_setting_verifiers_are_truthful_and_token_scoped -v
Ran 1 test in 0.001s
FAILED (failures=2)

python3 -m unittest tooling.tests.test_produce_guardrail_evidence.RepositoryCommandTests.test_long_command_setup_version_and_fallback_records_fit_schema tooling.tests.test_github_evidence.GitHubEvidenceV2Tests.test_artifact_summary_with_result_url_fits_evidence_schema_limit -v
Ran 2 tests in 0.003s
FAILED (failures=2)
```

The first group covered the captured bare-path run with PR-head `head_sha` and
empty `pull_requests`, wrong artifact base SHA/ref/head SHA, explicit HTTPS 302
handling without forwarding the bearer token, raw command disclosure, and
post-prefix schema bounds. The final two-test RED preserved stable reason
prefixes while proving the composed artifact summary plus URL exceeded 1,000
characters.

Focused GREEN after implementation:

```text
python3 -m unittest tooling.tests.test_github_evidence tooling.tests.test_produce_guardrail_evidence tooling.tests.test_action_distribution tooling.tests.test_install tooling.tests.test_dependabot_workflow tooling.validators.tests.test_guardrails_contracts -v
Ran 114 tests in 2.699s
OK
```

Current-branch Task 3-owned tooling GREEN, excluding only the Task 4 embedded
demo-copy module:

```text
Ran 123 tests in 3.539s
OK
```

The complete current-branch tooling discovery ran 129 tests and reported four
expected Task 4 generated-demo equality failures for the intentionally
preserved copies of `.guardrails/github_evidence.py`, `.guardrails/produce.py`,
`dependabot-verification.yml`, and `github-secret-protection.yml`. No Task 4,
documentation, example, `.gitignore`, or plan file was changed for this repair.

Detached Task 3 verification with this repair applied to Task 3 alone:

```text
Guardrails tests: 14 tests, OK
Tooling tests: 122 tests, OK
Validator tests: 54 tests, OK
Demo regression tests: 5 tests, OK
Skill suites: 4 + 3 + 13 tests, OK
Validated 31 skills
Repository validation passed for 31 skills, 29 controls, schemas, and documentation
Documentation validation passed
Python compilation and git diff checks: exit 0
```

### Final two Task 3 findings RED/GREEN

The final evidence-boundary and refresh-profile regressions failed together
before implementation:

```text
python3 -m unittest \
  tooling.tests.test_github_evidence.GitHubEvidenceV2Tests.test_native_check_bounds_fully_composed_result_fields \
  tooling.tests.test_github_evidence.GitHubEvidenceV2Tests.test_artifact_backed_not_run_bounds_fully_composed_long_url \
  guardrails.tests.test_evaluate.EvaluateV2Tests.test_rejects_evidence_fields_over_schema_maximum_lengths \
  tooling.tests.test_install.InstallerTests.test_refresh_unions_explicit_core_with_installed_github_profile -v
Ran 4 tests in 0.038s
FAILED (failures=6)
```

The RED run proved that native and artifact-backed `not_run` results could
exceed schema maxima after check names, conclusions, and details URLs were
composed; the runtime evaluator accepted overlong producer, reason, and
evidence values; and explicit `--profile core` suppressed an already installed
GitHub profile during refresh. A separate passed-result regression confirmed
that the runtime must enforce the optional reason maximum for every status, not
only `blocked` and `not_run`.

All GitHub evidence results now pass through a final field-aware bound of 200
characters for producer and 1,000 characters for reason and each evidence
record. Runtime validation independently enforces the same maxima. Refresh
starts with validated profiles from the installed v2 policy and unions explicit
profiles, preserving installed Core and GitHub workflow ownership.

Focused GREEN after the repair:

```text
python3 -m unittest tooling.tests.test_github_evidence tooling.tests.test_produce_guardrail_evidence tooling.tests.test_install tooling.tests.test_action_distribution tooling.tests.test_dependabot_workflow tooling.validators.tests.test_guardrails_contracts guardrails.tests.test_evaluate
Ran 131 tests in 2.801s
OK
```

The complete current-branch tooling discovery ran 131 tests and reported only
the two expected Task 4 generated-demo equality failures for the intentionally
preserved `examples/python-demo/.guardrails/evaluate.py` and
`examples/python-demo/.guardrails/github_evidence.py`. Excluding only that Task
4 module, 125 Task 3-owned tooling tests passed. All 15 guardrails tests, 54
validator tests, 5 demo tests, skill suites (4, 3, and 13 tests), repository and
documentation validators, Python compilation, workflow parsing, and diff
checks also passed.

Detached Task 3 verification with this final repair applied to Task 3 alone:

```text
Guardrails tests: 15 tests, OK
Tooling tests: 124 tests, OK
Validator tests: 54 tests, OK
Demo regression tests: 5 tests, OK
Skill suites: 4 + 3 + 13 tests, OK
Validated 31 skills
Repository validation passed for 31 skills, 29 controls, schemas, and documentation
Documentation validation passed
Python compilation, workflow parsing, and git diff checks: exit 0
```

### Final native workflow-path provenance repair RED/GREEN

The final native provenance review found that most Actions-backed provider
checks declared only a workflow display name. A duplicate workflow with the
same name could therefore be selected without an exact path contract, and
multiple matching check runs were collapsed to the newest run. The initial
seven-test RED run reported 28 subtest failures and one error across canonical
contracts, schemas/validators, collection behavior, and non-Actions app
extensibility.

Every canonical Actions-backed check now declares its exact installed
`.github/workflows/...` path. The provider schema and both runtime/repository
validators require exactly one provenance identity: `workflow_path` for an
Actions workflow or `app_slug` for a non-Actions GitHub App. Template-backed
checks must use the path derived from their canonical template. The only
canonical app-native check uses the verified `semgrep-app` GitHub App identity;
no fake workflow path was added.

The collector now verifies the Actions run API path before accepting every
native check, allowing only the exact bare path or that exact path with an
`@ref` suffix. Wrong paths, missing path contracts, app mismatches, and any
duplicate matching check name produce `not_run` / NO RESULT. Artifact-backed
trusted-base checks retain their stricter exact trusted-ref requirement.

Focused GREEN after the repair:

```text
python3 -m unittest tooling.tests.test_github_evidence tooling.validators.tests.test_guardrails_contracts guardrails.tests.test_evaluate tooling.tests.test_install tooling.tests.test_action_distribution -q
Ran 118 tests in 1.245s
OK
```

The current branch's complete tooling discovery ran 135 tests and reported
only four expected generated-demo equality failures because Task 4's protected
`examples/python-demo/.guardrails/` copies were intentionally not modified.
All 16 guardrails tests, 57 validator tests, 5 demo regression tests, skill
suites (4, 3, and 13 tests), repository/documentation validators, Python
compilation, and diff checks passed. Final Task 3-only detached verification is
recorded below after autosquash.

Detached Task 3 verification after autosquash:

```text
Guardrails tests: 16 tests, OK
Tooling tests: 128 tests, OK
Validator tests: 57 tests, OK
Demo regression tests: 5 tests, OK
Skill suites: 4 + 3 + 13 tests, OK
Validated 31 skills
Repository validation passed for 31 skills, 29 controls, schemas, and documentation
Documentation validation passed
Python compilation, all workflow parsing, git diff, and detached status checks: exit 0
```

### Final check-run pagination provenance repair RED/GREEN

The final provenance finding was reproduced before implementation with four
focused regressions. They proved that an exact-path page-one check could pass
while a duplicate wrong-path check remained unseen on page two, GitHub's
default-latest filter could hide duplicates, a later-page API failure could be
ignored, and malformed or inconsistent `total_count` values could still lead
to trusted evidence:

```text
python3 -m unittest \
  tooling.tests.test_github_evidence.GitHubEvidenceV2Tests.test_collects_all_pages_for_url_encoded_check_name_before_trusting_exact_path \
  tooling.tests.test_github_evidence.GitHubEvidenceV2Tests.test_filter_all_exposes_duplicates_hidden_by_github_default_latest \
  tooling.tests.test_github_evidence.GitHubEvidenceV2Tests.test_later_check_run_page_failure_is_not_run \
  tooling.tests.test_github_evidence.GitHubEvidenceV2Tests.test_malformed_check_run_total_count_is_not_run -v
Ran 4 tests
FAILED (failures=4)
```

Two mutation-style bounds checks independently failed before their production
guards were restored. Without the up-front safe-page limit, the collector made
20 requests instead of the bounded two per-name first-page requests in the
fixture. Without cross-page count consistency, a changed page-two
`total_count` produced a false pass instead of `not_run`.

The collector now queries each expected check name independently with a
URL-encoded `check_name`, `filter=all`, `per_page=100`, and an explicit page.
It reads every page required by a validated stable `total_count`, requires the
page sizes and item types to prove a complete enumeration, and caps each
per-name snapshot at 10 pages. A missing, failed, malformed, changing, or
over-limit response makes that expected check `not_run`; only a completely
enumerated unique check proceeds to workflow provenance validation. Polling is
also bounded by a finite attempt count derived from the configured wait.

Focused GREEN after implementation:

```text
python3 -m unittest tooling.tests.test_github_evidence -v
Ran 46 tests in 0.031s
OK
```

Current-branch full validation ran all 141 tooling tests. The only failure was
the intentionally preserved Task 4 generated-demo equality assertion for
`examples/python-demo/.guardrails/github_evidence.py`; no Task 4, docs,
example, `.gitignore`, or plan file was changed or staged. Excluding that Task
4 module, all 135 Task 3-owned tooling tests passed. All 16 guardrails tests,
57 validator tests, 5 demo tests, skill suites (4, 3, and 13 tests), repository
and documentation validators, Python compilation, canonical/self collector
equality, and diff checks passed.

Detached Task 3 verification after the first autosquash:

```text
Guardrails tests: 16 tests, OK
Tooling tests: 134 tests, OK
Validator tests: 57 tests, OK
Demo regression tests: 5 tests, OK
Skill suites: 4 + 3 + 13 tests, OK
Validated 31 skills
Repository validation passed for 31 skills, 29 controls, schemas, and documentation
Documentation validation passed
Python compilation, all workflow parsing, git diff, and detached status checks: exit 0
```

## Original Task 3 full verification

The original Task 3 verification before this second review ran under `set -e`:

```text
Guardrails tests: 14 tests, OK
Tooling tests: 97 tests, OK
Validator tests: 54 tests, OK
Existing demo regression tests: 5 tests, OK (not v2 migration acceptance)
Semgrep fixture execution: 1 test skipped (exact host Semgrep 1.175.0 unavailable)
Existing demo validator regression command: exit 0 (not v2 migration acceptance)
Demo v2 migration and acceptance validation are deferred to Task 4
Validated 31 skills
Installed portable repository validation: exit 0
Validated 31 skills, 29 controls, guardrail schemas, and documentation
Documentation validation passed
Python compileall: exit 0
JSON-compatible YAML/JSON parse passed
git diff --check: exit 0
```

All 12 distributed Core/GitHub workflow templates also parsed successfully with
the local Ruby standard-library YAML parser. The pinned Semgrep CE workflow runs
`semgrep --test` against the positive/negative fixtures before scanning the
repository with the installed local rule pack; operational workflow, local,
standalone, and pre-commit scans use `--error` and exclude both fixture trees.

## Activation decisions

- Repository owners must configure only the commands they actually support:
  `GUARDRAILS_SETUP_COMMAND`, `GUARDRAILS_BUILD_COMMAND`,
  `GUARDRAILS_UNIT_TEST_COMMAND`, `GUARDRAILS_CHANGED_COVERAGE_COMMAND`, and
  `GUARDRAILS_WORKING_DIRECTORY`. Missing capability commands intentionally
  produce skipped/NO RESULT evidence.
- GitHub CodeQL and Dependency Review remain skipped until their explicit
  repository variables are configured.
- GitHub Secret Protection and Dependabot setting verification require the
  optional least-privilege `SECURITY_SETTINGS_TOKEN`; without it they publish
  exact-head skipped checks rather than passes. Published checks bind back to
  their exact Actions workflow run for collector provenance verification.
- Artifact provenance runs only for release/workflow-dispatch artifact paths
  and does not represent PR commit provenance.
- Docker was installed locally but its daemon was unavailable, and no exact
  host Semgrep/Gitleaks binaries were installed. Local container scans and the
  executable Semgrep fixture test therefore were not claimed as passed; their
  deterministic unavailable behavior was covered by unit tests.
