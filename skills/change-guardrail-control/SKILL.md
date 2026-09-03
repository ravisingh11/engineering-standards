---
name: change-guardrail-control
description: "Use when adding, activating, changing, promoting, demoting, replacing, or removing a Guardrails capability, provider, producer workflow, profile, policy override, enforcement mode, evidence contract, or GitHub check."
---

# Change Guardrail Control

Change a guardrail without creating drift between policy, runtime, installed
workflows, evidence, scorecards, and documentation.

## Non-negotiable outcome

Do not call a control active because its configuration, token, or workflow file
exists. Completion requires fresh provider evidence collected for the exact
subject of a representative run. Missing, skipped, stale, or unconfigured work
must never become a pass.

## Workflow

1. Read repository `AGENTS.md`, `docs/architecture.md`,
   `docs/producer-contract.md`, and `docs/control-status.md`. Read
   `docs/control-setup.md` for activation changes.
2. Define the contract before editing: capability ID, catalog stage,
   availability, evidence subject, enforcement policy, authoritative provider,
   supplemental providers, producer/check name, activation requirements, raw
   status mapping, and expected behavior when configuration is absent.
3. Map every affected surface with `rg`: canonical policy, schemas, runtime,
   provider configuration, installer mappings, canonical workflows, installed
   `.guardrails/` and `.github/workflows/` copies, examples/demo, rulesets,
   tests, and documentation. Never fix only an installed/generated copy.
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
8. Open a real pull request. Verify the producer runs for the current head,
   publishes verifiable exact-subject evidence, appears in the scorecard, and
   preserves failure/no-result semantics. Verify the PR comment, job summary,
   and artifact when those outputs are part of the contract.
9. Keep the control advisory until representative runs prove reliability,
   ownership, and remediation. Never promote an `advisory-only` control or make
   AI review the sole merge gate. Add a required check only after its producer
   is active and stable.

## Completion report

Use `references/completion-matrix.md`. Mark unverified rows explicitly; do not
replace evidence with inference. Report changed files, validation commands,
hosted-run links, remaining activation work, and enforcement state.
