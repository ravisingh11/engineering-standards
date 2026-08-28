# Guardrails standard

## Purpose

Guardrails is a deterministic evidence layer around engineering operations.
Profiles select vendor-neutral capabilities, providers produce evidence, and a
repository policy decides whether missing authoritative evidence is advisory or
blocking.

Guardrails does not replace builds, tests, scanners, code review, deployment
policy, or repository protection. It records their outcomes for one exact
subject and evaluates those outcomes without inventing success.

## Public model

- A **capability** is the engineering outcome being evaluated.
- A **provider** is a tool or adapter that produces evidence for a capability.
- A **profile** is a runnable set of capabilities with advisory defaults.
- An **authoritative provider** is the only provider that can satisfy or block
  its capability.
- A **supplemental provider** is visible and always advisory.

The only runnable profiles are `core` and `github`. Core is selected by default;
GitHub is optional and additive. A repository may activate other runnable
catalog capabilities through explicit overrides, but vendor names do not become
profiles.

## Principles

### Missing is not passing

A workflow file, secret, variable, configured project, successful setup step,
skipped job, or old result is not passing evidence. Missing and unavailable
producers report `not_run` / `NO RESULT`.

### Evidence belongs to one subject

Every evaluation names a subject type and immutable revision:

- `git-commit` for change evidence;
- `artifact` for release artifacts;
- `environment` for deployment or runtime evidence.

Evidence must match both values exactly. A result for another commit or subject
type cannot satisfy policy.

### One authority, visible alternatives

Exactly one provider is authoritative for each runnable capability. This keeps
the decision deterministic. Supplemental providers support comparison,
migration, and defense in depth without creating ambiguous OR semantics.

### Enforcement follows reliability

All profile defaults are advisory. Promote a capability only after its provider
is reliable, exact-subject evidence is proven, the check name and failure
behavior are stable, and a remediation owner exists.

### Configuration grants no authority

An `allow` decision means the declared evidence satisfies the declared policy.
It does not grant permission to stage, commit, push, merge, deploy, publish,
delete, spend money, change settings, or contact people.

## Modes, evidence, and readiness

| Concept | Values |
| --- | --- |
| Effective mode | `advisory`, `enforced`, `not_activated` |
| Raw provider status | `passed`, `failed`, `blocked`, `not_run` |
| Public evidence status | `passed`, `failed`, `blocked`, `no_result`, `not_activated` |
| Readiness | `GREEN`, `ORANGE`, `RED`, `GRAY` |
| Decision | `allow`, `block` |

`GREEN` requires an exact-subject authoritative pass. An unresolved advisory
capability is `ORANGE`; an unresolved enforced capability is `RED`; an inactive
capability is `GRAY`. Default output omits inactive and `evidence-only`
controls; `--all-catalog-controls` includes them as `GRAY` / `not_activated`
rows. Supplemental results never alter readiness or decision.

## Operations

Profiles define defaults separately for `change` and `release`. Repository
policy overrides can set a runnable capability to `advisory`, `enforced`, or
`not_activated` per operation. The capability's catalog stage and evidence
subject must also apply to the requested operation.

## Future lifecycle contracts

Catalog entries marked `evidence-only` describe future subject and evidence
boundaries. They are not selectable and have no installed providers. A future
change must add a runnable contract, provider mapping, evidence production, and
tests before documentation may describe execution.

See [architecture](architecture.md), [implementation](guardrails-implementation.md),
and [producer contract](producer-contract.md).
