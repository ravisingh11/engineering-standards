# Running the guardrails

See the [sample scorecard output](examples/sample-scorecard.md) before running
the commands below. It shows the relationship between policy enforcement,
producer evidence, and readiness color.

The reliable way to measure compliance is to evaluate evidence for the exact
revision being changed. Do not treat the presence of a workflow file, a green
local build, or a policy document as proof that a control passed.

## The recommended flow

```text
Install the evaluator and policy
        ↓
Configure the controls for this repository
        ↓
Run real producers: build, tests, scanners, reviews
        ↓
Write evidence for the exact commit
        ↓
Run the deterministic evaluator
        ↓
Publish the result as a required GitHub check
```

The evaluator is intentionally separate from the tools. SonarQube, CodeQL,
Snyk, FOSSA, tests, and AI reviewers produce evidence; the evaluator decides whether
that evidence satisfies the selected policy.

The workflow-level aggregation contract is documented in
[Producer and evidence contract](producer-contract.md). Separate producer
workflows remain visible in GitHub Actions, while the scorecard collects their
revision-bound check results into one deterministic evaluation.

## Enforcement profiles

Compliance is evaluated against the repository's selected policy, not against
every capability in the shared catalog. A repository can adopt controls in
stages:

| Profile | Meaning |
| --- | --- |
| Not activated | The repository has not selected the control. It appears as `GRAY` in the full catalog view. |
| Advisory | The control is selected and reported, but findings do not block. |
| Enforced | The control is selected and a failure can block the evaluator decision. |

The scorecard reports the selected enforced and advisory controls. Use the
catalog's `--all-catalog-controls` view to discover additional capabilities
that are cataloged but `not_activated`.

## Install it in an application repository

From the application repository, run the installer in dry-run mode first:

```sh
python3 /path/to/engineering-standards/tooling/install.py \
  --target . \
  --github-actions \
  --dry-run
```

Review the proposed files, then run the same command without `--dry-run`.
The installer adds the repository installation described in
[Guardrails directories](../README.md#guardrails-directories), including:

- `.guardrails/policy.yaml` — repository-selected policy.
- `.guardrails/control-catalog.yaml` — activation metadata for shared controls.
- `.guardrails/documentation.yaml` — implementation-to-documentation mappings.
- `.guardrails/change-scope.yaml` — repository scope thresholds.
- `.guardrails/ground-truth-ai.yaml` — repository ground-truth inventory.
- `.guardrails/evaluate.py` — deterministic evaluator.
- `.guardrails/scorecard.py` — human-readable and JSON scorecard.
- `.guardrails/configure.py` — safe control activation and enforcement configuration.
- `.guardrails/scan.py` — local producer runner and scorecard command.
- `.guardrails/github_evidence.py` — GitHub Checks collector used by the aggregate workflow.
- `.guardrails/producer-manifest.json` — explicit control-to-check connection map.
- `.agents/skills/prepare-safe-change/` — preparation guidance.
- `.github/workflows/guardrails-scorecard.yml` — aggregate scorecard workflow installed into consumer repositories by `--github-actions`.

In this shared repository, the equivalent first-party workflow is
`.github/workflows/guardrail-checks.yml`. Use that workflow URL when viewing
the shared repository's own runs.

The application repository still owns its commands, scanner settings,
credentials, AI adapter, and ground-truth documents.

If the target already has an installed product file, use `--merge-existing`.
It preserves existing files and installs only missing product components. The
default installer mode refuses to overwrite anything.

Before using `--refresh-existing` after upgrading this standards repository,
run it in dry-run mode:

```sh
python3 /path/to/engineering-standards/tooling/install.py \
  --target . \
  --github-actions \
  --refresh-existing \
  --dry-run
```

The installer rejects legacy Guardrails configuration before planning the
refresh. Create the destination directory first:

```sh
mkdir -p .guardrails
```

Then execute every complete `git mv` command it prints, review relative schema
references in moved files, and rerun `--dry-run`. Run only the printed commands
for files the repository has. The installer is the canonical exact path map and
does not move or delete rejected configuration automatically.

After the dry run succeeds, remove `--dry-run`. Refresh updates the evaluator,
configurator, scanner, scorecard, catalog, and installed workflow while
preserving selected repository validation policies, provider configuration,
the producer manifest, copied skill directories, consumer workflows, and
generated reports. It migrates or removes only known installer-owned runtime
artifacts and the former scorecard workflow name. Unknown files remain
untouched; the installer never recursively deletes directories or application
files. Use `--no-cleanup` to skip that known-artifact cleanup.

## Enable a capability

List the available controls and their current enforcement mode:

```sh
python3 .guardrails/configure.py --list
```

Set a control without hand-editing `.guardrails/policy.yaml`:

```sh
python3 .guardrails/configure.py \
  --set snyk-code=advisory \
  --set snyk-open-source=advisory \
  --dry-run
```

Remove `--dry-run` to write the policy. The modes are:

- `advisory`: selected and reported, but non-blocking.
- `enforced`: selected as a blocking evaluator check; add its real GitHub
  status context to the repository ruleset separately.

Use `--all-operations` to apply a selection to both `change` and `release`.
The command validates control IDs against
`.guardrails/control-catalog.yaml`, prevents enforced/advisory overlap, and
refuses unknown modes. Unselected controls are reported as `not_activated`;
there is no separate `observe` mode.

## Run the repository scan

After configuring the policy, run:

```sh
python3 .guardrails/scan.py \
  --all-catalog-controls
```

The scan runs installed local validators, writes revision-bound evidence to
`.artifacts/guardrails/evidence.json`, merges any JSON evidence files in
`.artifacts/guardrails/evidence/`, and renders the scorecard to the terminal.
It also writes a timestamped Markdown report to:

```text
.artifacts/guardrails/scorecard-YYYYMMDD-HHMMSSZ.md
```

The timestamp is UTC. Use `--report path/to/report.md` to override the default
location. A producer JSON file must have this shape:

```json
{
  "checks": {
    "snyk-code": {
      "producer": "Snyk",
      "status": "passed",
      "evidence": ["Snyk result for revision <sha>"]
    }
  }
}
```

Use `status: "failed"` for a completed failing scan and `status: "not_run"`
with a `reason` when a producer is unavailable. Never write `passed` merely
because a workflow or service is configured.

## Run the evaluator directly

Evidence must identify the exact revision under evaluation:

```sh
python3 .guardrails/evaluate.py \
  --policy .guardrails/policy.yaml \
  --evidence .artifacts/guardrails/evidence.json \
  --operation change \
  --revision "$(git rev-parse HEAD)" \
  --subject-type git-commit \
  --json
```

In GitHub Actions, use the pull request head SHA rather than a moving branch
name:

```sh
python3 .guardrails/evaluate.py \
  --policy .guardrails/policy.yaml \
  --evidence "$EVIDENCE_FILE" \
  --operation change \
  --revision "$GITHUB_SHA" \
  --subject-type git-commit \
  --json
```

The process exits `0` for `allow` and `1` for `block`. Any schema or input
error exits `2`.

## Generate the scorecard

Use the scorecard command when you want one concise report for a pull request
or release:

```sh
python3 .guardrails/scorecard.py \
  --policy .guardrails/policy.yaml \
  --catalog .guardrails/control-catalog.yaml \
  --evidence .artifacts/guardrails/evidence.json \
  --operation change \
  --revision "$(git rev-parse HEAD)" \
  --subject-type git-commit
```

Use `--json` for dashboards, pull request comments, or another automation
consumer. The scorecard reports compliance and activation separately:

```text
Guardrail Scorecard: ORANGE
Decision: ALLOW
Enforced compliance: 8/8 (100.0%)
Advisory coverage: 2/3 (66.7%)
Activation: GREEN 5, ORANGE 3, GRAY 1
Controls: GREEN 8, ORANGE 2, GRAY 1, RED 0
```

The status means:

- `GREEN` — enforced checks pass and there are no findings.
- `ORANGE` — enforced checks pass, but advisory findings or activation gaps remain.
- `RED` — an enforced check failed, is missing, was not run, or targets another revision.

Readiness is enforcement-aware. An advisory or `not_activated` control can
appear in the detailed control table as `RED`, `GRAY`, or `ORANGE`, while the
overall readiness remains `ORANGE` and the decision remains `ALLOW`. Only a
red enforced control makes overall readiness `RED`.

For an onboarding view that includes every control in the shared catalog,
including services not yet selected in the repository policy, add:

```sh
--all-catalog-controls
```

A control moves to `GREEN` only after its producer writes `passed` evidence for
the exact revision. Merely adding a SonarQube token, FOSSA project, or AI
adapter does not make it green. Missing external setup appears as `ORANGE`;
missing repository-owned setup appears as `GRAY`; failed evidence appears as
`RED`.

## How to read the result

| Result | Meaning | Action |
| --- | --- | --- |
| `allow`, all enforced checks passed | Enforced guardrails are satisfied for this exact revision. | The check can pass. Review any advisory findings. |
| `allow`, advisory findings present | The change meets enforced policy but has non-blocking gaps. | Resolve or explicitly accept the advisory findings. |
| `block` | An enforced check failed, was missing, was not run, or evidence targeted another revision. | Do not merge until the findings are resolved. |
| Exit `2` | The policy or evidence is malformed. | Fix the configuration or producer output; this is not compliance. |

Compliance is not one universal percentage. Report at least:

- Enforced checks passed: `N/M`.
- Advisory checks passed: `N/M`.
- Enforced findings, including missing and `not_run` checks.
- Subject revision evaluated.
- Controls that are not applicable, if the policy explicitly excludes them.

The strongest statement is specific and revision-bound:

> `change` policy allowed commit `<sha>` with 8/8 enforced checks passed and
> 2/3 advisory checks passed.

Do not say “the repository is compliant” without naming the operation,
revision, policy, and required-check result.

## Make a control a merge gate

1. Start with the control not activated or in Advisory mode.
2. Make the workflow fail on exit code `1` or `2`.
3. Confirm the displayed GitHub check name.
4. Promote it to Enforced in the repository policy and add that exact check
   name to the repository ruleset only when the team is ready.
5. Keep evidence and the evaluator output as workflow artifacts where useful.

The ruleset is the enforcement point. The evaluator is the decision point.
The producer workflows are the evidence point.

## Related documents

- [Control status](control-status.md) — green, orange, and gray activation boundaries.
- [Guardrail implementation](guardrails-implementation.md) — policy and evidence schemas.
- [Control catalog](../policies/control-catalog.yaml) — organization-wide control contracts.
- [Workflow templates](../workflows/README.md) — producer setup and configuration.
