# Scorecard Badge Publishing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish both an accurate native workflow badge and an optional static badge that reports the latest accepted PR Guardrails score.

**Architecture:** Keep `Guardrail Scorecard` read-only. A separate default-branch `workflow_run` publisher downloads the exact completed scorecard artifact, validates it with repository-owned Python, renders a static report and SVG, and deploys that bounded output to GitHub Pages. The installer treats badge publishing as an explicit optional feature with symmetric install, refresh, and removal behavior.

**Tech Stack:** Python 3 standard library, GitHub Actions, GitHub Pages, SVG, HTML, JSON, `unittest`

**Spec:** `docs/superpowers/specs/2026-09-08-scorecard-badge-publishing-design.md`

## Global Constraints

- The existing scorecard workflow remains read-only.
- Badge publishing is optional and requires no PAT, Gist, repository secret, or `contents: write` permission.
- The publisher executes only default-branch code and never executes downloaded artifact content.
- A source run is eligible only when it is associated with exactly one pull request targeting the repository default branch. The publisher validates the source base SHA separately and derives the expected scorecard revision from the associated pull request head SHA.
- A valid `RED / block` artifact is publishable even when the source workflow conclusion is `failure`; canceled, skipped, or artifact-less failures are not.
- The standalone publisher requires `GUARDRAILS_SCORECARD_BADGE_PAGES_MODE=dedicated` and must not replace an existing repository Pages site.
- Exactly one bounded, non-symlink scorecard JSON and its paired Markdown report are accepted.
- The score badge is labeled as the latest PR scorecard, not default-branch state.
- Every external action is pinned to a full commit SHA.
- Current approved action pins are:
  - `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`
  - `actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c` (`v8.0.1`)
  - `actions/configure-pages@45bfe0192ca1faeb007ade9deae92b16b8254a0d` (`v6.0.0`)
  - `actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9` (`v5.0.0`)
  - `actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346` (`v5.0.1`)

---

### Task 1: Build the bounded scorecard badge renderer

**Files:**
- Create: `tooling/render_scorecard_badge.py`
- Create: `tooling/tests/test_render_scorecard_badge.py`
- Create after tests pass: `.guardrails/render_scorecard_badge.py`

**Interfaces:**
- Consumes: `render_badge(source_dir: Path, output_dir: Path, repository: str, run_id: int, run_url: str, expected_revision: str) -> dict[str, object]`
- Produces: `guardrails-badge.svg`, `scorecard.json`, `scorecard.md`, and `index.html` under `output_dir`
- CLI: `python3 .guardrails/render_scorecard_badge.py --source-dir PATH --output-dir PATH --repository OWNER/REPO --run-id INTEGER --run-url HTTPS_URL --expected-revision 40_HEX_SHA`

- [ ] **Step 1: Write failing happy-path renderer tests**

Create a minimal valid GREEN scorecard fixture in a temporary source directory with one `scorecard-20260908-120000Z.json` and paired Markdown file. Assert that the returned metadata and all four output files contain `GREEN`, `14/14`, the exact revision, repository, and run URL.

```python
metadata = MODULE.render_badge(
    source,
    output,
    "owner/repo",
    12345,
    "https://github.com/owner/repo/actions/runs/12345",
    "a" * 40,
)
self.assertEqual(metadata["message"], "GREEN 14/14")
self.assertIn("GREEN 14/14", (output / "guardrails-badge.svg").read_text())
self.assertEqual(json.loads((output / "scorecard.json").read_text())["source_run_id"], 12345)
```

- [ ] **Step 2: Write failing color and validation tests**

Cover ORANGE and RED rendering, invalid status/decision, booleans masquerading as integers, passed counts greater than totals, zero active controls, mismatched revision, non-HTTPS or cross-repository run URL, missing/duplicate JSON, missing paired Markdown, files over 64 KiB, aggregate input over 1 MiB, nested files, and symlinks. Assert every invalid case raises `ValueError` and leaves no published output.

- [ ] **Step 3: Run the focused tests and verify failure**

Run:

```sh
python3 -m unittest tooling.tests.test_render_scorecard_badge
```

Expected: import or missing-interface failures because the renderer does not exist.

- [ ] **Step 4: Implement strict input validation and rendering**

Implement only with the standard library. Require the scorecard document to contain:

```python
VALID_STATUSES = {"GREEN": "#2da44e", "ORANGE": "#bf8700", "RED": "#cf222e"}
VALID_DECISIONS = {"allow", "block"}
MAX_MEMBER_BYTES = 64_000
MAX_SOURCE_BYTES = 1_000_000
```

Validate `subject.type == "git-commit"`, `subject.revision == expected_revision`, exact 40-character lowercase hexadecimal revisions, integer nonnegative `passed`/`total` values with `passed <= total`, and `enforced.total + advisory.total > 0`. Derive the badge count from both modes. Escape all SVG and HTML text with `html.escape`. Write into a temporary sibling directory and replace `output_dir` only after every file has been rendered successfully.

- [ ] **Step 5: Add the CLI and prove invalid invocations fail closed**

Use `argparse`; validate `run_id > 0`, repository format `owner/name`, and an exact GitHub Actions run URL for that repository and run ID. Print a one-line `Published badge input: STATUS passed/total` message on success and `ERROR ...` to stderr with exit code `2` on validation failure.

- [ ] **Step 6: Run focused tests and synchronize the installed source**

Run:

```sh
python3 -m unittest tooling.tests.test_render_scorecard_badge
```

Expected: all renderer tests pass. Copy the exact canonical bytes to `.guardrails/render_scorecard_badge.py` and assert byte equality in the distribution tests added in Task 2.

- [ ] **Step 7: Commit the renderer**

```sh
git add tooling/render_scorecard_badge.py tooling/tests/test_render_scorecard_badge.py .guardrails/render_scorecard_badge.py
git commit -m "feat(badge): render validated scorecard status"
```

### Task 2: Add optional installer lifecycle support

**Files:**
- Modify: `tooling/install.py`
- Modify: `tooling/tests/test_install.py`
- Modify: `tooling/tests/test_action_distribution.py`

**Interfaces:**
- Extends: `install(..., scorecard_badge: bool = False, remove_scorecard_badge: bool = False) -> list[InstallItem]`
- Adds CLI: `--scorecard-badge` and `--remove-scorecard-badge`
- Installs: `.guardrails/render_scorecard_badge.py` and `.github/workflows/guardrails-scorecard-badge.yml`

- [ ] **Step 1: Write failing default and opt-in installation tests**

Assert a default install contains neither badge file. Assert `scorecard_badge=True` installs both exact canonical files while preserving the existing Core/GitHub workflow sets.

- [ ] **Step 2: Write failing refresh and removal tests**

Assert refresh detects an existing installer-owned badge workflow and refreshes both files without requiring the option again. Assert `remove_scorecard_badge=True` removes only the two installer-owned files, appears as `kind == "remove"` in dry-run output, rejects simultaneous `scorecard_badge=True`, and refuses to remove an unmarked consumer workflow or symlink.

- [ ] **Step 3: Run installer tests and verify failure**

Run:

```sh
python3 -m unittest tooling.tests.test_install tooling.tests.test_action_distribution
```

Expected: failures for missing arguments, workflow map, runtime source, and removal behavior.

- [ ] **Step 4: Implement the optional install set**

Add:

```python
BADGE_WORKFLOWS = {
    "guardrails-scorecard-badge.yml": ROOT / "workflows" / "guardrails-scorecard-badge.yml",
}
BADGE_RUNTIME = InstallItem(
    ROOT / "tooling" / "render_scorecard_badge.py",
    target / ".guardrails/render_scorecard_badge.py",
)
```

Include both only for explicit opt-in or refresh detection. Keep `--no-actions --scorecard-badge` invalid because the feature requires an Actions publisher.

- [ ] **Step 5: Implement fail-safe removal**

Represent removals as exact `InstallItem` destinations with `kind="remove"`. Before changing state, reject symlinks and require the workflow to begin with `INSTALLER_MARKER`; require the renderer bytes or a repository-owned marker header. Apply removal with `Path.unlink()` only to those exact files and prune no directories. Print `- remove:` for removal plan entries.

- [ ] **Step 6: Run installer and distribution tests**

Run:

```sh
python3 -m unittest tooling.tests.test_install tooling.tests.test_action_distribution
```

Expected: all tests pass and default consumers remain unchanged.

- [ ] **Step 7: Commit installer support**

```sh
git add tooling/install.py tooling/tests/test_install.py tooling/tests/test_action_distribution.py
git commit -m "feat(installer): manage scorecard badge publishing"
```

### Task 3: Add the trusted Pages publisher workflow

**Files:**
- Create: `workflows/guardrails-scorecard-badge.yml`
- Create after contract tests pass: `.github/workflows/guardrails-scorecard-badge.yml`
- Create: `tooling/tests/test_scorecard_badge_workflow.py`
- Modify: `tooling/tests/test_repository_commands.py`

**Interfaces:**
- Trigger: `workflow_run` for `Guardrail Scorecard` completion and manual `workflow_dispatch` with required `run_id`
- Feature flag: repository variable `GUARDRAILS_SCORECARD_BADGE_ENABLED == 'true'`
- Pages ownership acknowledgement: repository variable `GUARDRAILS_SCORECARD_BADGE_PAGES_MODE == 'dedicated'`
- Deploys: renderer output through the `github-pages` environment

- [ ] **Step 1: Write failing workflow contract tests**

Parse both canonical and self-installed workflow text. Require:

```yaml
on:
  workflow_run:
    workflows: [Guardrail Scorecard]
    types: [completed]
  workflow_dispatch:
    inputs:
      run_id:
        required: true
```

Assert only `actions: read`, `contents: read`, `pages: write`, and `id-token: write` permissions; `concurrency.group: guardrails-scorecard-pages`; `cancel-in-progress: false`; the `github-pages` environment; the exact action pins; exact source run ID binding; no checkout of a PR repository/ref; and invocation of `.guardrails/render_scorecard_badge.py` from a default-branch checkout.

Require both feature variables before deployment. Document and test that this
standalone workflow owns the repository's complete Pages deployment and is not
safe to enable alongside an existing Pages site.

- [ ] **Step 2: Write failing source-run validation assertions**

Require the workflow to reject source runs unless all are true:

```text
repository.full_name == github.repository
name == Guardrail Scorecard
path == .github/workflows/guardrails-scorecard.yml
conclusion in {success, failure}
event in {pull_request_target, pull_request_review}
exactly one pull_requests entry is present
pull_requests[0].base.ref == repository.default_branch
head_sha == pull_requests[0].base.sha
pull_requests[0].head.sha is exactly 40 hexadecimal characters
```

Manual dispatch must fetch the requested run through the GitHub API and apply the same checks before artifact download.

- [ ] **Step 3: Run focused tests and verify failure**

Run:

```sh
python3 -m unittest tooling.tests.test_scorecard_badge_workflow
```

Expected: failure because the publisher workflow does not exist.

- [ ] **Step 4: Implement the workflow**

Use the verified run ID to download `guardrail-scorecard-<run-id>` into a fresh directory. Invoke the renderer with the source run's exact repository, run ID, URL, and associated pull request head SHA. Configure Pages, upload only the generated output directory, and deploy it. A `failure` conclusion is accepted only when the downloaded artifact validates as a `RED / block` scorecard; a `success` conclusion must contain an `allow` scorecard. Append a job summary containing the resulting Pages URL and source run URL.

Do not use source-controlled shell from the artifact, `pull_request` checkout values, `contents: write`, or any secret other than the automatic `GITHUB_TOKEN` consumed by official actions.

- [ ] **Step 5: Synchronize canonical and self-installed workflows**

Copy the exact canonical workflow bytes to `.github/workflows/guardrails-scorecard-badge.yml`. Add byte-equality assertions so future installer refreshes cannot diverge from the self-hosting repository.

- [ ] **Step 6: Run workflow and repository contract tests**

Run:

```sh
python3 -m unittest tooling.tests.test_scorecard_badge_workflow tooling.tests.test_action_distribution tooling.tests.test_repository_commands
```

Expected: all tests pass and YAML validation accepts both copies.

- [ ] **Step 7: Commit the publisher**

```sh
git add workflows/guardrails-scorecard-badge.yml .github/workflows/guardrails-scorecard-badge.yml tooling/tests/test_scorecard_badge_workflow.py tooling/tests/test_repository_commands.py
git commit -m "feat(actions): publish latest guardrail score badge"
```

### Task 4: Document both badge contracts and installation

**Files:**
- Modify: `README.md`
- Modify: `docs/quickstart.md`
- Modify: `docs/guardrails.md`
- Modify: `docs/architecture.md`
- Modify: `docs/guardrails-implementation.md`
- Modify: `docs/control-setup.md`
- Modify: `workflows/README.md`
- Modify: `examples/python-demo/README.md`

**Interfaces:**
- Native badge URL: `https://github.com/OWNER/REPOSITORY/actions/workflows/guardrails-scorecard.yml/badge.svg`
- Score badge URL: `https://OWNER.github.io/REPOSITORY/guardrails-badge.svg`
- Report URL: `https://OWNER.github.io/REPOSITORY/`

- [ ] **Step 1: Fix the native workflow badge**

Remove `?branch=main` from the README badge source and call it `Scorecard Workflow`. Explain that PR scorecard runs are associated with PR head branches, so a `main` branch filter has no qualifying run.

- [ ] **Step 2: Add concise installation and removal commands**

Document:

```sh
python3 tooling/install.py --target /path/to/repo --scorecard-badge --dry-run
python3 tooling/install.py --target /path/to/repo --scorecard-badge
python3 tooling/install.py --target /path/to/repo --remove-scorecard-badge --dry-run
python3 tooling/install.py --target /path/to/repo --remove-scorecard-badge
```

State that GitHub Pages must use GitHub Actions as its source and that both
`GUARDRAILS_SCORECARD_BADGE_ENABLED=true` and
`GUARDRAILS_SCORECARD_BADGE_PAGES_MODE=dedicated` activate publication. Warn
that the standalone workflow owns the complete Pages deployment; repositories
with an existing Pages site must integrate the renderer output into that site's
workflow instead.

- [ ] **Step 3: Explain semantics and trust boundaries consistently**

Every relevant document must distinguish:

```text
Scorecard Workflow = GitHub workflow execution conclusion
Latest PR Scorecard = validated Guardrails readiness and passed/active count
```

State that a successful workflow may still contain an advisory ORANGE score, the latest PR badge does not attest current `main`, and the published report links to its immutable source revision and workflow run.

- [ ] **Step 4: Update diagrams and workflow inventory**

Add the publisher as an optional post-scorecard path, not a provider or control. Keep it out of required status-check lists and explain that Pages publication never influences `allow`/`block`.

- [ ] **Step 5: Run documentation and link validation**

Run:

```sh
python3 tooling/validators/validate_documentation.py
python3 tooling/validators/validate_repository.py
tooling/lint.sh
git diff --check
```

Expected: all validation passes with no broken internal links or stale badge guidance.

- [ ] **Step 6: Commit documentation**

```sh
git add README.md docs workflows/README.md examples/python-demo/README.md
git commit -m "docs(badges): explain workflow and score signals"
```

### Task 5: Verify, merge, activate Pages, and prove publication

**Files:**
- Modify after successful Pages deployment: `README.md`

**Interfaces:**
- Repository variable: `GUARDRAILS_SCORECARD_BADGE_ENABLED=true`
- Pages mode variable: `GUARDRAILS_SCORECARD_BADGE_PAGES_MODE=dedicated`
- Pages build type: `workflow`
- Proof: published SVG and scorecard JSON bind the same source run and revision

- [ ] **Step 1: Run complete local validation**

Run:

```sh
tooling/build.sh
tooling/test.sh
GUARDRAILS_COVERAGE_BASE_REF=origin/main tooling/changed_code_coverage.sh
python3 examples/python-demo/tools/validate_demo.py --documentation
python3 tooling/validate-skills.py
python3 tooling/validators/validate_repository.py
python3 tooling/validators/validate_documentation.py
python3 tooling/validators/validate_no_migrations.py
tooling/lint.sh
git diff --check
```

Expected: all commands exit zero and changed Python coverage is at least 90%.

- [ ] **Step 2: Open and review the implementation PR**

Push the implementation branch, open a PR, wait for every selected producer and the scorecard, inspect the timestamped scorecard artifact, run Codex review on the exact head, resolve valid findings, and repeat validation after changes.

- [ ] **Step 3: Merge the implementation PR**

Merge only with no blocking check failures or unresolved review threads. Delete the merged feature branch and update local `main`.

- [ ] **Step 4: Configure this repository's Pages publisher**

Set the repository variable and Pages build type:

```sh
gh variable set GUARDRAILS_SCORECARD_BADGE_ENABLED --body true
gh variable set GUARDRAILS_SCORECARD_BADGE_PAGES_MODE --body dedicated
gh api --method POST repos/ravisingh11/engineering-standards/pages -f build_type=workflow
```

If Pages already exists, use the corresponding update endpoint with
`build_type=workflow`. Verify the API reports the expected Pages URL and build
type before triggering publication.

- [ ] **Step 5: Open a minimal proof PR**

Add the live score badge to `README.md` only after Pages is configured:

```markdown
[![Latest PR Scorecard](https://ravisingh11.github.io/engineering-standards/guardrails-badge.svg)](https://ravisingh11.github.io/engineering-standards/)
```

Push the proof branch and open a PR. Wait for its `Guardrail Scorecard`, then
wait for the publisher triggered by that exact run.

- [ ] **Step 6: Verify the deployed result end to end**

Fetch the deployed JSON and SVG without authentication. Assert that:

```text
status == source scorecard status
passed/total == source scorecard passed/total
subject revision == proof PR head SHA
source_run_id == triggering Guardrail Scorecard run ID
SVG title and visible message match the JSON
```

Verify the native workflow badge no longer returns `no status` and the score
badge returns HTTP 200 with the expected GREEN/ORANGE/RED message.

- [ ] **Step 7: Merge the proof PR and perform the final audit**

Require a clean exact-head review and scorecard, merge the proof PR, remove
merged branches, confirm `main == origin/main`, and verify that only explicitly
excluded Dependabot PRs remain open.
