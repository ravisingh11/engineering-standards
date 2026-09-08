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

## Security boundaries

- The publisher never checks out or executes pull-request code.
- The publisher implementation always comes from the default branch.
- The downloaded archive and selected scorecard member have strict size and
  path limits.
- Exactly one scorecard JSON document for the triggering run is accepted.
- Status, decision, counts, and subject values are schema-validated before
  rendering.
- SVG and HTML use only validated enumerations, integers, and escaped text.
- The publisher receives `actions: read`, `contents: read`, `pages: write`, and
  `id-token: write`; the scorecard workflow keeps its current read permissions.
- A failed, canceled, missing, malformed, or ambiguous source result is not
  published as green.
- Publishing is serialized so two completed source runs cannot deploy
  concurrently.

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

No personal access token, repository secret, Gist, or contents-write
permission is required.

## Failure behavior

- A scorecard workflow failure leaves the previously published badge intact
  and makes the publisher run non-passing with a clear explanation.
- Missing or invalid evidence fails the publisher without deploying.
- A Pages configuration error fails only the optional publisher. It does not
  alter the original scorecard decision.
- Re-running a valid scorecard run may republish the same immutable subject.

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
