# Guardrails Standard

## Purpose

Agentic guardrails are a lightweight evidence layer around automated
change. Existing tools produce evidence; a small policy says which evidence is
required; a deterministic evaluator reports whether the evidence supports the
operation.

The layer does not replace SAST, regression tests, secret scanners, CI, code
review, or repository protection. It makes their outcomes explicit and binds
them to the exact revision being considered.

## Principles

### Humans read the change; machines read the contract

Code, tests, and review notes should remain understandable without the agent
conversation. Policy and evidence should be structured, strict, and
deterministically evaluable.

### Evidence producers stay independent

The attestation layer does not execute or reinterpret producer tools. It accepts
their recorded outcome: `passed`, `failed`, `blocked`, or `not_run`.

The evaluator validates structure and policy satisfaction, not producer
identity or cryptographic provenance. Repositories that need stronger evidence
integrity should protect the producing workflow and attach signed or
independently verifiable artifacts.

The public scorecard uses this vocabulary:

| Field | Values |
| --- | --- |
| Field | Values | Meaning |
| --- | --- | --- |
| `enforcement` | `enforced`, `advisory`, `not_activated` | Whether this repository selected the control and whether it can block merge. |
| producer `status` | `passed`, `failed`, `blocked`, `not_run` | The raw result reported by the producer. |
| scorecard `evidence_status` | `passed`, `failed`, `blocked`, `no_result`, `not_activated` | The normalized result shown to users. |
| `readiness` | `GREEN`, `ORANGE`, `GRAY`, `RED` | Whether the control is ready and healthy for this revision. |

Producer evidence retains the lower-level input value `not_run`. The scorecard
presents it as `no_result`; a control absent from policy is presented as
`not_activated`.

The policy JSON schema currently stores enforced controls in the `required`
list for compatibility. User-facing reports call that mode `enforced`.

### Enforced means objective and dependable

Make a check required only when it is deterministic, reliably available, and
important enough to block the operation. Keep semantic judgments advisory.

### Missing is not passing

Missing, failed, blocked, and `not_run` evidence never satisfies an enforced
check. Recording an honest limitation is useful, but it is not an approval.

### Documentation is evidence, not proof

A deterministic documentation producer may validate links, declared targets,
and whether mapped implementation changes include documentation changes. That
evidence confirms documentation was included; human review still determines
whether the explanation is correct and sufficient.

### Change size is advisory

File counts and line counts are useful review-scope signals, not measures of
quality. Record them consistently and keep thresholds advisory unless an
adopting repository has measured false positives and deliberately chooses a
blocking boundary.

### Evidence belongs to one revision

An evaluation must compare evidence with the exact commit, tree, artifact, or
other immutable revision being acted on. Evidence from another revision blocks
the decision.

### Attestation grants no authority

An `allow` decision means the declared evidence meets the declared policy. It
does not grant permission to stage, commit, push, merge, deploy, publish,
delete, spend money, change settings, or contact people.

## Decision Model

Each operation contains two policy lists:

- `required`: every named check is user-facing `enforced` and must have `passed` evidence
- `advisory`: missing or non-passing evidence is reported but does not block

The evaluator has only three outcomes:

- `allow`: revision matches and every required check passed
- `block`: revision differs or at least one required check did not pass
- configuration error: policy or evidence is malformed

No implicit defaults, waivers, inheritance, scoring, or prose interpretation
participate in the decision.

## Promotion Rule

By default, selected controls start in `advisory` mode. Move a control to
`enforced` only after its producer is activated, returns reliable evidence for
the exact revision, has a stable check name, and has a clear remediation
owner. Change policy through normal review.

Configuration shows intent. Producer evidence proves the control ran.
