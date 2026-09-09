# Scorecard Badge Publishing Design

## Purpose

Expose two different signals without conflating them:

1. The native GitHub workflow badge shows whether the Guardrail Scorecard
   workflow completed successfully.
2. The Guardrails score badge shows the latest evaluated PR result, including
   its color and passed-control count.

The score badge is optional. Installing Guardrails must continue to work
without GitHub Pages or badge publishing.

## User experience

The project README may display both badges:

```text
Scorecard workflow: passing
Latest PR scorecard: GREEN 14/14
```

The workflow badge must not filter on `branch=main`, because PR scorecard runs
are associated with PR head branches. The score badge must be labeled as the
latest PR scorecard rather than the state of the default branch.

Consumers enable score publishing explicitly during installation or refresh.
Documentation provides the GitHub Pages setting, repository variable, badge
URL, and removal path.

## Architecture

```text
Guardrail Scorecard workflow
        |
        | trusted JSON and Markdown artifact
        v
Scorecard Badge Publisher (workflow_run)
        |
        | validate bounded artifact; execute no artifact content
        v
Static Pages artifact
        |
        +-- guardrails-badge.svg
        +-- scorecard.json
        +-- scorecard.md
        +-- index.html
```

The existing scorecard workflow remains read-only. A separate publisher runs
from the default branch after a completed `Guardrail Scorecard` workflow. It
downloads the exact triggering run's artifact, validates the scorecard schema
and subject, renders static files with repository-owned code, and deploys only
those generated files to GitHub Pages.

Only scorecard runs bound to exactly one eligible pull request whose base is the
repository default branch are eligible. GitHub may leave a
`workflow_run.pull_requests` collection empty for `pull_request_target`, so the
publisher does not depend on it. After validating the artifact, it resolves the
scorecard subject through GitHub's commit-to-pull-request API and requires one
associated PR whose head SHA is the subject revision and whose base is the default
branch. It validates separately that the source run's base SHA is an ancestor
of the current default branch because `pull_request_target` attributes the run
to the trusted base commit rather than the proposed head commit. Manual
publisher runs may select an existing run ID, but that selected run must satisfy
the same event, PR association, and trusted-base checks.

## Security boundaries

- The publisher never checks out or executes pull-request code.
- The publisher implementation always comes from the default branch.
- The downloaded archive and selected scorecard member have strict size and
  path limits.
- Exactly one scorecard JSON document for the triggering run is accepted.
- Exactly one pull request associated with the scorecard subject commit is
  accepted; its base must be the repository default branch and its head SHA
  must match the scorecard subject revision.
- The source workflow run's base SHA must be reachable from the current default
  branch, proving that its producer came from trusted repository history.
- Status, decision, counts, and subject values are schema-validated before
  rendering.
- SVG and HTML use only validated enumerations, integers, and escaped text.
- The publisher receives `actions: read`, `contents: read`, `pages: write`, and
  `id-token: write`; the scorecard workflow keeps its current read permissions.
- A valid `RED / block` scorecard is published even though the source scorecard
  workflow reports failure. Canceled runs and failures without valid scorecard
  evidence are not published.
- Publishing is serialized so two completed source runs cannot deploy
  concurrently.
- Publication is monotonic. Before deployment, the publisher compares the
  source run creation time and run ID with the currently published metadata.
  An older source run is validated and reported as stale but cannot replace a
  newer badge. A transient failure reading existing metadata fails closed.

## Published result

The badge color follows the scorecard result:

| Scorecard | Badge color | Message |
| --- | --- | --- |
| `GREEN` | green | `GREEN <passed>/<total>` |
| `ORANGE` | orange | `ORANGE <passed>/<total>` |
| `RED` | red | `RED <passed>/<total>` |

The count uses all active controls: enforced total plus advisory total. A
zero-control or malformed scorecard is rejected rather than presented as a
successful badge.

The published report identifies its source repository, workflow run, exact
subject revision, operation, and generation time. The badge links to the
published report page; the workflow badge links to GitHub Actions.

## Installation and configuration

The installer gains an explicit badge-publishing option. When selected, it
installs the publisher workflow and renderer alongside the normal runtime.
Refresh updates those files; cleanup removes files previously owned by that
option when it is disabled.

Activation requires:

1. GitHub Pages configured with **GitHub Actions** as the build source.
2. The installed publisher workflow present on the default branch.
3. Repository Actions allowed to create Pages deployments.
4. The documented badge URLs added to the consumer README.
5. The repository variable
   `GUARDRAILS_SCORECARD_BADGE_PAGES_MODE=dedicated`, acknowledging that this
   publisher owns the complete Pages deployment for the repository.

The standalone publisher must not be enabled for a repository that already
uses GitHub Pages for documentation or another site. GitHub Pages has one active
deployment per repository, so deploying only the badge output would replace the
existing site. Such repositories should render these files inside their
existing Pages build instead of installing the standalone publisher; that
integration remains repository-owned.

No personal access token, repository secret, Gist, or contents-write
permission is required.

## Failure behavior

- A scorecard workflow failure with a valid `RED / block` artifact publishes
  that red result. A failure without a valid scorecard artifact leaves the
  previously published badge intact and makes the publisher non-passing.
- Canceled or skipped source runs are rejected without deploying.
- Missing or invalid evidence fails the publisher without deploying.
- A Pages configuration error fails only the optional publisher. It does not
  alter the original scorecard decision.
- Re-running the currently published scorecard may republish the same immutable
  subject. Re-running or manually selecting an older scorecard validates it
  without deployment when a newer source run has already been published.

## Documentation changes

Update the README, quickstart, Guardrails guide, implementation guide, workflow
catalog, control setup guide, and example documentation to explain:

- the difference between the workflow and score badges;
- why the native badge has no `branch=main` filter;
- what the latest PR score means;
- how to install, enable, verify, and remove badge publishing;
- the Pages permissions and trust boundary;
- how to construct badge URLs for a consuming repository.

## Verification

The implementation must include:

- renderer unit tests for green, orange, red, malformed, ambiguous, oversized,
  and unsafe input;
- workflow contract tests for trigger, permissions, immutable action pins,
  source-run binding, and no PR-code execution;
- installer and refresh/cleanup distribution tests;
- Markdown link and YAML validation;
- an end-to-end run in this repository that publishes a badge matching the
  exact scorecard artifact;
- a follow-up PR proving the native workflow badge and latest PR score badge
  both render.

## Acceptance criteria

- The native badge no longer displays `no status`.
- The published score badge matches the latest accepted PR scorecard.
- Badge publishing is opt-in for consumers and enabled for this repository.
- The scorecard workflow remains read-only.
- No additional credential is required.
- Existing installations remain compatible until the option is enabled.
