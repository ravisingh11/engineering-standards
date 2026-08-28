# Task 2 report: Guardrails v2 runtime

## Scope

- Base commit: `d6dd9b260b3a2204db46c3647a6fabac2b642943`
- Implemented only the Task 2 evaluator, scorecard, local scanner, GitHub evidence collector, configuration CLI, focused tests, and runtime copies established by the existing distribution test.
- Preserved the unrelated `.gitignore` edit and untracked implementation plan.
- Did not implement Task 3 producer, workflow, or installer behavior.

## Changed files

- `guardrails/evaluate.py`
  - Replaced the v1 check-list evaluator with v2 profile, override, catalog, provider-selection, nested-evidence, exact-subject, authority-only, supplemental, and readiness semantics. Runtime profile definitions are exactly Core/GitHub, require the exact Task 1 control set for every operation, and have advisory-only defaults; mismatched subjects make all supplied provider results unusable and record expected/observed subjects.
- `guardrails/tests/test_evaluate.py`
  - Added focused v2 precedence, additive-profile, authority, supplemental, subject-binding, malformed-evidence, and full-catalog behavior tests.
- `tooling/guardrail_scorecard.py`
  - Emits scorecard version 2, recursively normalized public evidence vocabulary, provider-aware rows, and `Capability — Provider` human output without activation/configuration scoring.
- `tooling/tests/test_scorecard.py`
  - Covers colors, advisory/enforced gaps, supplemental failures, unselected controls, and provider display names.
- `tooling/scan_repository.py`
  - Emits and merges nested v2 evidence, runs local validators under canonical Core provider IDs only after proving full requested revision equals HEAD and the worktree is clean, rejects conflicting provider results, excludes stale-subject fragments, adds selected authority placeholders, and writes same-timestamp Markdown/JSON artifacts plus an explicit latest JSON copy.
- `tooling/tests/test_scan_repository.py`
  - Covers nested multi-provider merge behavior, conflicts, stale fragments, canonical local provider IDs, authority placeholders, and non-passing configuration-presence evidence.
- `tooling/github_evidence.py`
  - Removes producer-manifest input, derives selected authority/supplemental checks from v2 contracts, fans one proven check out to every capability when provider/workflow/name are identical, rejects conflicting mappings, waits/evaluates only the newest numeric check-run ID per name, and requires exact head SHA, `github-actions` app provenance, details-URL run ID, and declared workflow-name verification before emitting git-commit evidence.
- `tooling/tests/test_github_evidence.py`
  - Covers manifest-free collection, selected-provider waiting, duplicate check freshness, missing/skipped checks, exact revision binding, canonical Core+GitHub Semgrep App fan-out, and conflicting shared-name mappings.
- `tooling/configure_guardrails.py`
  - Implements the exact Task 2 profile/provider/supplemental/mode/list/dry-run interfaces and mutates only v2 policy/provider configuration using serialized, permission-preserving, same-directory temporary files with atomic replacement and pair rollback.
- `tooling/tests/test_configure_guardrails.py`
  - Covers every mutation family and required invalid combinations, effective listing, and removal of retired CLI options.
- `.guardrails/configure.py`, `.guardrails/scan.py`, `.guardrails/github_evidence.py`
  - Synchronized runtime copies explicitly established by `tooling/tests/test_action_distribution.py`.
- `examples/python-demo/.guardrails/configure.py`, `examples/python-demo/.guardrails/scan.py`
  - Synchronized demo runtime copies explicitly established by `tooling/tests/test_action_distribution.py`.

## TDD evidence

### RED

Command:

```text
python3 -m unittest guardrails.tests.test_evaluate tooling.tests.test_scorecard tooling.tests.test_scan_repository tooling.tests.test_github_evidence tooling.tests.test_configure_guardrails
```

Result before production edits:

```text
Ran 33 tests in 0.049s
FAILED (failures=2, errors=41)
```

The failures were expected v1/v2 contract breaks: the evaluator and scorecard rejected v2 call shapes, the scanner expected flat `checks`, the GitHub collector required a manifest, and the configurator lacked the v2 mutation functions/options.

### GREEN

Same focused command after implementation:

```text
Ran 33 tests in 0.058s
OK
```

Focused suites plus distribution-copy verification:

```text
Ran 54 tests in 4.125s
OK
```

### Review RED

Command:

```text
python3 -m unittest guardrails.tests.test_evaluate tooling.tests.test_scorecard tooling.tests.test_scan_repository tooling.tests.test_github_evidence tooling.tests.test_configure_guardrails
```

Result after adding all requested review regressions and before review production edits:

```text
Ran 47 tests in 1.425s
FAILED (failures=9, errors=6)
```

The failures proved arbitrary/dirty local binding, stale mismatch rows, mutable duplicate selection, missing GitHub provenance validation, permissive runtime profiles, non-transactional configuration writes, raw public statuses, and non-timestamped default JSON behavior. Two additional focused RED→GREEN cycles covered workflow-provenance lookup failure and JSON-mode artifact locations.

### Review GREEN

```text
Ran 49 tests in 0.352s
OK

Focused suites plus distribution-copy verification:
Ran 70 tests in 4.430s
OK
```

### Final P1 review RED

Command:

```text
python3 -m unittest guardrails.tests.test_evaluate tooling.tests.test_github_evidence
```

Result after adding the missing/extra profile-set regressions and canonical shared Semgrep regression, before runtime edits:

```text
Ran 24 tests in 0.017s
FAILED (failures=2, errors=1)
```

The two failures proved that missing and extra per-operation controls were accepted. The error proved that the canonical Semgrep App check shared by Core `custom-static-analysis` and GitHub `deep-sast` was rejected as ambiguous.

### Final P1 review GREEN

```text
Ran 24 tests in 0.015s
OK

Broader Task 2 suites:
Ran 13 evaluator tests in 0.007s — OK
Ran 85 tooling tests in 3.981s — OK
```

The existing conflicting mapping regression remains green and rejects a shared check name when provider or workflow provenance differs.

## Full repository verification

```text
python3 -m unittest discover -s guardrails/tests -p 'test_*.py'
Ran 13 tests in 0.007s — OK

python3 -m unittest discover -s tooling/tests -p 'test_*.py'
Ran 85 tests in 4.031s — OK

python3 -m unittest discover -s tooling/validators/tests -p 'test_*.py'
Ran 49 tests in 0.463s — OK

python3 -m unittest discover -s examples/python-demo -p 'test_*.py'
Ran 5 tests in 0.000s — OK

python3 examples/python-demo/tools/validate_demo.py --documentation
Demo repository validation passed

python3 tooling/validate-skills.py
Validated 31 skills

python3 tooling/validators/validate_repository.py
Validated 31 skills, 29 controls, guardrail schemas, and documentation

python3 tooling/validators/validate_documentation.py
Documentation validation passed.

git diff --check
exit 0
```

Additional runtime evidence:

- Python compilation completed with exit 0 for all changed source and proven distributed runtime modules.
- Canonical v2 evaluator/scorecard smoke returned public JSON with no raw `not_run` or `missing` statuses.
- A clean temporary Git repository scanner smoke returned version 2, `allow`, ORANGE and exposed/wrote `evidence-20260828-155507Z.json`, `evidence.json`, and `scorecard-20260828-155507Z.md`; the primary JSON and Markdown shared one UTC timestamp.
- Canonical configuration `--list` and combined profile/mode/authority/supplemental `--dry-run` completed with exit 0.
- Search across every Task 2-owned runtime/test file and proven distributed copy found no `producer-manifest`, producer-manifest prose, v1 version literal, flat policy operation access, or flat evidence check access.

## Concerns and boundaries

- Task 3 remains responsible for producer implementations, workflow and installer changes, and distribution of v2 configuration/contracts. Build, unit-test, changed-code-coverage, Semgrep CE, and Gitleaks authorities correctly remain `not_run` when no revision-bound producer evidence exists.
- Repository-local `.guardrails/evaluate.py`, `.guardrails/scorecard.py`, and v1 configuration files were not changed because the existing distribution test does not establish them as generated Task 2 runtime copies. No v1 execution path remains in the Task 2-owned runtime; Task 3 must complete the installed-runtime/configuration cutover.
- The active Task 2 worktree is intentionally dirty while implementing and also contains unrelated `.gitignore`/plan work. The hardened scanner therefore reports local providers as `not_run` there; passing local evidence was verified in isolated clean-repository tests instead.
