---
name: change-guardrail-control
description: "Use when adding, activating, changing, promoting, demoting, replacing, or removing a Guardrails capability, provider, producer workflow, profile, policy override, enforcement mode, evidence contract, or GitHub check."
---

# Change Guardrail Control

Change a guardrail without creating drift between policy, runtime, installed
workflows, evidence, scorecards, and documentation.

## Non-negotiable outcome

Configuration, a token, or a workflow file does not prove activation. Require
fresh provider evidence for the declared operation and subject. Catalog
decommissioning requires proof that its contract and distributed copies are
absent. Scoped deactivation must preserve shared contracts used elsewhere.
Provider replacement must keep the capability active. Missing, skipped, stale,
or unconfigured work must never become a pass.

## Workflow

1. Read repository `AGENTS.md`. In this source, read the relevant architecture,
   producer-contract, status, and setup docs. In a consumer, inspect
   `.guardrails/`, its ground-truth inventory, and docs discovered with `rg`;
   do not assume fixed paths.
2. Define the contract before editing: capability ID, catalog stage,
   availability, evidence subject, enforcement policy, authoritative provider,
   supplemental providers, producer/check name, activation requirements, raw
   status mapping, and expected behavior when configuration is absent.
3. Map affected policy, schemas, runtime, provider configuration, installer
   mappings, workflows and installed copies, examples, rulesets, tests, and docs.
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
7. Change GitHub variables, secrets, platform settings, or provider projects
   only with explicit authorization and under consumer security/contribution
   rules; otherwise mark hosted activation pending. Never expose credentials.
8. When explicitly authorized, follow the contribution process, open a PR, and
   run the hosted operation matching the subject: change/PR for `git-commit` or
   `pull-request`, release for `artifact`, and the applicable stage for
   `environment`. Verify contract-promised evidence, outputs, scorecard state,
   and failure/no-result behavior. For catalog removal, prove contract/copy
   absence and stale-evidence rejection. For scoped deactivation, prove the
   operation or profile is inactive while preserving shared contracts and
   producers. For provider replacement, prove the former provider cannot
   satisfy the affected selection and the replacement keeps it active. Require
   global absence only when the provider itself is decommissioned.
9. Keep the control advisory until representative runs prove reliability,
   ownership, and remediation. Never promote an `advisory-only` control or make
   AI review the sole merge gate. On promotion, add a required check only after
   its producer is stable. On demotion, remove or replace that exact required
   context. Without hosted-change authorization, report enforcement pending and
   do not claim the control is advisory.

## Completion report

Use `references/completion-matrix.md`. Mark unverified rows explicitly; do not
replace evidence with inference. Report changed files, validation commands,
hosted-run links, remaining activation work, and enforcement state.
