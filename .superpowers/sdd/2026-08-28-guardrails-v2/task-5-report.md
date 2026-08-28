# Task 5 report — verification and release readiness

## Result

Guardrails v2 is prepared as exactly three reviewable commits after
`origin/main`. The standalone demo is synchronized on one local commit. Nothing
was pushed or merged.

## Review findings resolved

Whole-branch review found and this task repaired five material issues:

- installed scorecard workflows referenced source-only `tooling/` paths;
- pull-request and local documentation validation omitted exact base/head
  revisions, so mapped documentation changes could be missed;
- installed ground-truth validation accepted absolute, traversing, or escaping
  symlink paths;
- the demo coverage runner ignored its requested base revision; and
- the demo Unit Tests evidence ran only application tests instead of the full
  repository suite.

Focused regressions now cover every repaired boundary. A sixth self-scan issue
was also repaired: generated `.artifacts/` reports no longer cause repository
validation to reject its own machine-local evidence paths.

## Fresh verification

- Guardrails runtime: 16 tests passed.
- Tooling and installation: 150 tests passed.
- Repository validators: 63 tests passed.
- Embedded demo: 5 tests passed.
- Standalone demo: 22 tests passed.
- Skill validation: 20 tests across all skill validator suites passed.
- Repository, documentation, embedded-demo, compile, JSON/YAML, link,
  generated-copy, and diff checks passed.
- Targeted pyright checks for changed documentation/demo surfaces reported zero
  errors; standalone demo pyright reported zero errors.
- The Semgrep rule fixture suite passed with one expected skip because the exact
  pinned Semgrep runtime was unavailable locally.

The shared repository exact-HEAD scan returned `ORANGE` / `ALLOW` with
repository validation, documentation validation, repository ground truth,
build, and the full unit suite passing. Changed-code coverage remained
unconfigured, and the exact pinned Semgrep/Gitleaks runtimes were unavailable
because the local Docker daemon was not running, so those advisory capabilities
truthfully reported `NO RESULT`.

The standalone demo exact-HEAD scan returned `ORANGE` / `ALLOW` with repository
validation, documentation validation, repository ground truth, build, all 22
tests, and changed-code coverage passing. Change scope remained advisory and
failed because this clean-break migration is intentionally large. GitHub-only
and locally unavailable pinned-tool capabilities truthfully reported
`NO RESULT`.

## Prepared commits

1. `ae63c898decaa829c04f794738231c1cbc73fe8f` — contracts and runtime
2. `18888a120e6ed241c227106580bc4911318629c0` — producers, workflows, and installer
3. Final documentation/demo commit — its object ID is read from the final Git
   log because a commit cannot embed its own object ID

Standalone demo commit:
`20f0144282c7a1a926a3733e3a5a6c9250a58a21`.
