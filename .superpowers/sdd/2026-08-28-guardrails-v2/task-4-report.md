# Task 4 report: Guardrails v2 documentation and examples

## Result

Updated the public documentation, workflow/ruleset guidance, examples, and
embedded Python demo to the current Guardrails v2 contracts from base
`673d403c993abea1a902c04112627ba11c4fa989`.

The personal README preamble remains intact. Canonical implementation code,
canonical workflow YAML, and policy contracts were not modified by Task 4. The
final history-shaping pass adds the approved implementation plan and repository
ignore entry alongside this documentation/demo slice. Generated workflow/runtime
copies under `examples/python-demo/` were refreshed byte-for-byte from the
already-committed canonical distribution.

## Drift fixed

- Replaced active legacy manifest, retired installer flag, and token-gated Core
  Semgrep guidance with the v2 profile/provider/evidence model.
- Documented Core as the portable default and GitHub as the only optional
  additive runnable profile; all profile defaults remain advisory.
- Separated vendor-neutral capabilities from providers and documented exactly
  one authoritative provider plus advisory supplemental providers.
- Documented exact-subject evidence, workflow name/path (including `@ref`),
  pull-request event/head association, native workflow-suite binding, and
  custom-check external-ID/run provenance boundaries.
- Standardized readiness as `GREEN`, `ORANGE`, `RED`, and `GRAY`; standardized
  public evidence as `passed`, `failed`, `blocked`, `no_result`, and
  `not_activated`.
- Clarified that default scorecards omit inactive and `evidence-only` controls;
  only `--all-catalog-controls` shows them as `GRAY` / `not_activated` rows.
- Removed `Artifact Provenance` from pull-request required-check and ruleset
  examples. The installed workflow is documented as release-attestation-only,
  not a nested artifact-evidence producer or release-scorecard path.
- Documented exact install, help, scan, configuration, refresh, variable, token,
  local, pull-request, and enforcement-promotion commands.
- Documented tokenless Semgrep CE with tested repository rules and the pinned
  image; documented the MIT Gitleaks CLI and the separately licensed Gitleaks
  Action boundary.
- Documented SonarQube, Snyk, Semgrep AppSec Platform, and FOSSA as optional
  providers requiring repository/organization adapters and explicit selection,
  not runnable profiles.
- Documented configurable repository-relative ground-truth paths.
- Marked future container, IaC, SBOM, artifact vulnerability, deploy, DAST, and
  runtime assurance capabilities as catalog/evidence contracts only.
- Refreshed the embedded demo to nested v2 policy/profile/provider/evidence
  contracts and every installer-owned runtime, workflow, skill, evidence,
  schema, rule, and fixture copy from final Task 3. This includes the run-bound
  custom-check artifact contracts/workflows and corrected Gitleaks container
  argv.
- Removed the demo's false changed-code coverage substitution; coverage now
  remains `NO RESULT` until a real coverage command is configured.
- Made the demo documentation links valid when copied into a standalone
  repository.
- Made `tools/validate_demo.py` standalone by removing all standards-repository
  path dereferences. Canonical/generated equality now belongs exclusively to
  standards-repository tests.
- Made `--documentation` execute the installed documentation and ground-truth
  validators, so broken internal links and malformed documentation mappings
  fail in copied standalone demos.
- Required every demo ground-truth declaration to name a repository-relative
  file whose resolved path remains inside the repository, including across
  symlinks, and converted missing required-document reads to structured
  `ERROR:` output.
- Extended active-guidance validation to every tracked UTF-8 text/configuration
  file, including JSON, with explicit binary-format exclusions, and rejected
  the retired `.agentic-guardrails/` root.
- Narrowed nested policy, profile, catalog, provider, and ground-truth shapes
  before use so malformed demo configuration produces structured `ERROR:`
  output instead of a traceback.
- Removed pyright optional-value and nested-fixture diagnostics from the demo
  and scorecard regression tests.

## Deterministic RED

The repair regressions were written before the repaired demo behavior.

```text
python3 -m unittest tooling.tests.test_python_demo tooling.tests.test_scorecard -v
Ran 8 tests
FAILED (failures=2)
```

The first failure reproduced the archived demo validator crashing while reading
a nonexistent standards-repository canonical path. The second proved the
normal demo wrapper exposed `GRAY Artifact SBOM` because it silently forced
`--all-catalog-controls`.

The active-document regression then failed because the validator accepted a
retired `.agentic-guardrails/` path injected into every tracked Markdown and
ground-truth document. A follow-up RED proved a tracked non-Markdown
ground-truth document was also outside the scan.

The final review regressions independently proved the remaining defects:

```text
Tracked JSON mutation: validator returned 0 instead of rejecting the file
Malformed profiles/providers/catalog: 3 subtests emitted Python tracebacks
Generated-copy equality during the original Task 4 repair: 8 stale
runtime/configuration/workflow copies failed
Final Task 3 parent refresh equality: 1 stale copy failed
  (`.guardrails/github_evidence.py`)
```

The final Task 4 validator finding added four copied-standalone regressions.
Before the repair, broken links, malformed documentation mappings, absolute
ground-truth paths, parent escapes, and symlink escapes all returned success;
removing `README.md` produced a traceback instead of a structured error.

## Deterministic GREEN

```text
python3 -m unittest tooling.tests.test_python_demo tooling.tests.test_scorecard -v
Ran 16 tests — OK

npx --no-install pyright tooling/tests/test_python_demo.py tooling/tests/test_scorecard.py examples/python-demo/tools/validate_demo.py
0 errors, 0 warnings, 0 informations
```

The validator now proves v2 policy/profile/provider selection, required
runtime/workflow presence and path contracts, schemas/rules, existing
ground-truth paths, standalone-safe documentation, and absence of retired
active guidance without requiring the standards repository. Standards tests
separately prove full byte equality for generated runtime/configuration,
profiles, catalog, providers, schemas, rules, fixtures, workflows, and the
complete installed skill tree.

## Command and example verification

Verified in isolated temporary consumers:

- default install selected `core` and installed 7 Core workflows;
- `--profile github` selected `core, github` and installed 12 workflows;
- `--no-actions` installed runtime without `.github`;
- `--local-hooks --dry-run` produced the validated generated hook plan;
- `--enable-profile github`, `--set unit-tests=enforced`,
  `--select-provider changed-code-coverage=sonarqube`, and
  `--add-supplemental deep-sast=snyk-code` all passed in dry-run mode;
- `docs/examples/guardrails.yml` evaluated successfully against the v2 schemas
  and example evidence.

The environment did not contain `pre-commit`, so a non-dry `--local-hooks`
install was not executed. Installer unit tests cover its executable, Git
repository, validation, no-overwrite, and rollback boundaries.

## Standalone demo verification

Archived the embedded demo, unpacked it into an isolated temporary Git
repository, committed a clean subject, and executed all three commands from its
README:

```text
python3 -m unittest discover -s . -p 'test_*.py'
python3 tools/validate_demo.py --documentation
python3 tools/run_guardrails.py
```

The default wrapper omitted inactive/evidence-only rows. A separate explicit
`python3 .guardrails/scan.py --all-catalog-controls` run included `GRAY Artifact
SBOM — Not activated: not_activated`.

```text
Repository Validation: passed
Documentation Validation: passed
Repository Ground Truth: passed
Build: passed
Unit Tests: passed
Changed Code Coverage: not_run
Overall: ORANGE / ALLOW
```

The run wrote timestamped nested JSON evidence and a timestamped Markdown
scorecard. Change scope remained `NO RESULT` because the one-commit fixture had
no parent. Semgrep CE, Gitleaks, and GitHub-profile providers remained honest
`NO RESULT` where their local/runtime prerequisites were unavailable.

## Final verification

```text
python3 -m unittest discover -s guardrails/tests -p 'test_*.py'
Ran 16 tests — OK

python3 -m unittest discover -s tooling/tests -p 'test_*.py'
Ran 145 tests — OK

python3 -m unittest discover -s tooling/validators/tests -p 'test_*.py'
Ran 57 tests — OK

python3 -m unittest discover -s examples/python-demo -p 'test_*.py'
Ran 5 tests — OK

python3 examples/python-demo/tools/validate_demo.py --documentation
Demo repository validation passed

python3 tooling/validate-skills.py
Validated 31 skills

python3 tooling/validators/validate_repository.py
Validated 31 skills, 29 controls, guardrail schemas, and documentation

python3 tooling/validators/validate_documentation.py
Documentation validation passed

python3 -m unittest tooling.tests.test_python_demo -v
Ran 10 tests — OK

python3 -m unittest tooling.tests.test_python_demo.PythonDemoTests.test_generated_demo_distribution_matches_canonical_sources -v
Ran 1 test — OK

python3 -m unittest discover -s security/semgrep/tests -p 'test_*.py'
Ran 1 test — OK (skipped=1: exact Semgrep 1.175.0 unavailable)

python3 -m compileall -q guardrails tooling examples/python-demo
passed

git diff --check
passed

git diff --cached --check
passed
```

Additional deterministic checks parsed 17 JSON and 117 YAML files, including
rulesets, documentation examples, installed demo contracts, and all
canonical/generated workflows. Documentation validation checked internal
links. The active-guidance search found no obsolete manifest, retired installer
flag, `.agentic-guardrails/` path, cloud Semgrep execution command, or old
capability identifiers outside validator negative assertions and preserved
plan/spec history.

Mermaid source blocks were inspected as Markdown, but no browser/rendering
engine was available for visual Mermaid rendering; that remains a validation
limitation.

## Remaining owner actions

- Configure only real repository command variables and supported GitHub profile
  variables/tokens in consuming repositories.
- Promote capabilities and add exact ruleset contexts only after representative
  exact-subject evidence is reliable.
- Publish only after the three prepared commits receive the repository owner's
  normal pull-request review.

## Standalone demo synchronization

The separate `agentic_engineering_guardrails_demo` repository was synchronized
from the verified embedded demo on branch `feat/guardrails-v2-demo` at commit
`20f0144282c7a1a926a3733e3a5a6c9250a58a21`. Its 22 tests passed, pyright
reported no findings, all 39 installer-owned files matched the canonical shared
tree, and an exact-HEAD scan returned `ALLOW` with truthful `NO RESULT` outcomes
for providers unavailable outside GitHub or Docker. No push was performed.
