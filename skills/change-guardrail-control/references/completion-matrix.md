# Guardrail change completion matrix

Copy this table into the implementation notes or final report. A row is complete
only when its evidence is current and directly supports the claim.

| Surface | Status | Exact evidence or link | Owner / next action |
| --- | --- | --- | --- |
| Capability contract | Pending | Catalog entry, stage, availability, evidence subject, and enforcement policy agree. | |
| Provider contract | Pending | Authoritative/supplemental selection, producer name, check/review contract, secrets, and failure mapping validate. | |
| Canonical implementation | Pending | Runtime, schema, adapter, and canonical workflow changes are covered by focused tests. | |
| Distribution | Pending | Installer mapping and installed self/demo copies match canonical sources. | |
| Local behavior | Pending | Clean exact-revision scan shows expected pass, fail, blocked, and no-result behavior. | |
| GitHub activation | Pending | Required variables, secrets, settings, and provider-side configuration are present without exposing values. | |
| Hosted lifecycle proof | Pending | Active: a representative hosted operation executes for the declared subject and reports the expected producer result. Control removed: the change proves contract/copy absence and the intended inactive-or-absent state. Provider replaced: the capability remains active through the replacement provider. | |
| Evidence provenance | Pending | Active: the collector accepts the expected provider, workflow, event, run ID, check suite where applicable, and exact subject/revision. Control removed: no stale provider evidence is accepted. Provider replaced: only the replacement provider is authoritative and accepted. | |
| Scorecard outputs | Pending | Every output promised by the workflow contract shows the provider result and correct readiness/decision; require a PR comment only when implemented. | |
| Enforcement | Pending | Advisory/enforced mode matches policy; required-check rules reference only active, stable producer contexts. | |
| Documentation | Pending | Setup, status, troubleshooting, provider extension, and migration guidance use the public vocabulary. | |

## Required negative proofs

- Remove or invalidate required configuration: the producer must not pass.
- Supply stale or wrong-subject evidence: the collector must reject it.
- Fail the underlying tool: evidence and the scorecard must retain the failure.
- Remove a distributed runtime dependency: repository validation must fail.
- Select an operation-inapplicable or advisory-only enforcement mode: policy
  validation must reject it.
- Remove a control: installed copies must drop it and the scorecard must show
  inactivity or omit it according to the declared removal contract.
- Replace a provider: installed copies must drop the retired provider, reject
  its evidence, and keep the capability active through the replacement.

## Stop conditions

Do not merge while any applicable row lacks evidence, an active required
producer is skipped, a generated copy differs from its canonical source, stale
evidence survives a removal, or unresolved P0/P1 findings remain. Leave optional
provider activation work clearly marked instead of manufacturing a green result.
