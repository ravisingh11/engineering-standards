# Guardrails v2 implementation map

Guardrails uses JSON-compatible YAML and Python's standard library for its core
contracts and evaluator.

| Source | Installed consumer path | Purpose |
| --- | --- | --- |
| `guardrails/baseline.yaml` | `.guardrails/policy.yaml` | Core-selected starter policy |
| `policies/profiles.yaml` | `.guardrails/profiles.yaml` | Core and GitHub profile defaults |
| `policies/control-catalog.yaml` | `.guardrails/control-catalog.yaml` | Capability catalog |
| `policies/provider-config.yaml` | `.guardrails/providers.yaml` | Provider definitions and selections |
| `guardrails/*.schema.json` | `.guardrails/*.schema.json` | Policy, profile, provider, catalog, and evidence validation |
| `guardrails/evaluate.py` | `.guardrails/evaluate.py` | Effective-policy and evidence evaluation |
| `tooling/configure_guardrails.py` | `.guardrails/configure.py` | Atomic policy/provider mutation |
| `tooling/scan_repository.py` | `.guardrails/scan.py` | Local producer execution, evidence merge, and report writing |
| `tooling/guardrail_scorecard.py` | `.guardrails/scorecard.py` | Public scorecard rendering |
| `tooling/github_evidence.py` | `.guardrails/github_evidence.py` | Exact-head GitHub check collection and provenance validation |
| `tooling/produce_guardrail_evidence.py` | `.guardrails/produce.py` | Repository command, Semgrep CE, and Gitleaks evidence |

## Installed configuration

The installer also adds repository-owned documentation mappings, change-scope
thresholds, ground-truth inventory, validators, Semgrep rules, rule fixtures,
and selected workflow templates. Refresh preserves repository-owned policy,
provider selection, documentation, scope, and ground-truth files.

## Runtime sequence

1. Resolve and validate policy, profiles, catalog, and providers.
2. Resolve the operation and exact subject.
3. Run local providers or collect selected GitHub checks.
4. Merge only nested v2 evidence with an identical subject.
5. Add honest `not_run` placeholders for missing authoritative providers.
6. Validate evidence shape and provider capability mappings.
7. Evaluate authoritative evidence; retain supplemental evidence as advisory.
8. Write JSON evidence and a timestamped Markdown scorecard.

Invalid configuration or evidence exits `2`. An allowed decision exits `0`; a
blocked decision exits `1`.

Future lifecycle capabilities remain catalog/evidence definitions and have no
runtime producers. See [architecture](architecture.md) and
[producer contract](producer-contract.md).
