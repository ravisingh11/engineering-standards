---
name: change-guardrail-control
description: "Use when adding, activating, changing, promoting, demoting, replacing, or removing a Guardrails capability, provider, producer workflow, profile, policy override, enforcement mode, evidence contract, or GitHub check."
---

# Change Guardrail Control

Change a guardrail without creating drift between policy, runtime, installed
workflows, evidence, scorecards, and documentation.

## Non-negotiable outcome

Do not call a control active because its configuration, token, or workflow file
exists. Activation and behavior changes require fresh provider evidence for the
exact subject of a representative run. Decommissioning requires fresh PR-head
evidence that the producer contract and distributed copies are absent and the
scorecard reports the intended `not_activated` state. Missing, skipped, stale,
or unconfigured work must never become a pass.

## Workflow

1. Read repository `AGENTS.md`. In this standards source, also read
   `docs/architecture.md`, `docs/producer-contract.md`,
   `docs/control-status.md`, and `docs/control-setup.md` when relevant. In a
   consumer, inspect `.guardrails/` and its declared ground-truth inventory,
   then locate applicable repository documentation with `rg`; do not require
   fixed lifecycle-document paths.
2. Define the contract before editing: capability ID, catalog stage,
   availability, evidence subject, enforcement policy, authoritative provider,
   supplemental providers, producer/check name, activation requirements, raw
   status mapping, and expected behavior when configuration is absent.
3. Map every affected surface with `rg`: canonical policy, schemas, runtime,
   provider configuration, installer mappings, canonical workflows, installed
   runtime and workflow copies, examples/demo, rulesets, tests, and docs.
   Separate shared/installer-owned artifacts from consumer-owned configuration,
   including `.guardrails/policy.yaml`, `.guardrails/providers.yaml`, mappings,
   thresholds, and ground-truth paths. Edit consumer-owned choices directly;
   never fix only an installer-owned/generated copy.
4. Add a failing regression test for the contract or previously missed drift.
   Include success, failure, missing configuration, stale/wrong-subject
   evidence, and distribution behavior when relevant.
5. Make the smallest canonical change. Refresh installer-owned copies through
   the installer or the repository's documented distribution mechanism.
6. Run targeted tests, then the complete validation required by `AGENTS.md`.
   Check workflow syntax, schema consistency, internal links, and
   `git diff --check`.
7. Configure GitHub variables, secrets, platform settings, and provider-side
   projects only when required. Never commit credentials or print their values.
8. Open a real pull request. For active controls, verify the producer runs for
   the current head, publishes verifiable exact-subject evidence, appears in
   the scorecard, and preserves failure/no-result semantics. For removals,
   verify absence from canonical and distributed contracts and the expected
   inactive scorecard state. Verify comments, summaries, and artifacts when
   those outputs are part of the contract.
9. Keep the control advisory until representative runs prove reliability,
   ownership, and remediation. Never promote an `advisory-only` control or make
   AI review the sole merge gate. Add a required check only after its producer
   is active and stable.

## Completion report

Use `references/completion-matrix.md`. Mark unverified rows explicitly; do not
replace evidence with inference. Report changed files, validation commands,
hosted-run links, remaining activation work, and enforcement state.
