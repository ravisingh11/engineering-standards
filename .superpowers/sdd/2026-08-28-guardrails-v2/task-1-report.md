# Task 1 report — Guardrails v2 contracts

## Result

Implemented the Guardrails v2 control, profile, provider, policy, and nested
evidence contracts without changing evaluator, scanner, scorecard, collector,
installer, or configuration runtime behavior. Review fixes now cross-validate
evidence against the catalog and provider declarations, reject unknown policy
override controls, require non-empty provider result maps, and keep handwritten
and schema boundary constraints aligned without adding a dependency. The final
P2 review fix rejects whitespace-only evidence records in both validation paths.

Base Task 1 commit before review fixes: `d40a4d88ae301653e95c62da3270dfd0c1d1b193`

## Changed files

- `guardrails/baseline.yaml` — v2 Core-only baseline with empty change/release overrides.
- `guardrails/control-catalog.schema.json` — v2 control catalog JSON Schema with nonblank string boundaries aligned to handwritten validation.
- `guardrails/evidence-example.yaml` — nested control/provider v2 evidence example.
- `guardrails/evidence.schema.json` — v2 subject and nested result schema with non-empty per-control provider maps and aligned string boundaries.
- `guardrails/policy.schema.json` — v2 profiles and per-operation override schema with aligned nonblank names.
- `guardrails/profiles.schema.json` — Core/GitHub profile JSON Schema with aligned nonblank profile metadata.
- `guardrails/providers.schema.json` — provider definition and selection JSON Schema with non-empty capabilities and aligned template/string boundaries.
- `policies/control-catalog.yaml` — 29 vendor-neutral v2 capabilities, including deferred evidence-only lifecycle controls.
- `policies/profiles.yaml` — exact advisory Core and GitHub operation defaults.
- `policies/provider-config.yaml` — Core, GitHub, optional provider definitions and authoritative/supplemental selections.
- `tooling/validators/tests/test_control_catalog.py` — exact catalog/profile/schema/baseline tests, invalid value rejection tests, and schema/handwritten boundary parity tests.
- `tooling/validators/tests/test_guardrails_contracts.py` — provider selection, default provider, evidence cross-validation, policy rejection, and schema/handwritten boundary parity tests.
- `tooling/validators/validate_repository.py` — pure v2 cross-contract validation used by repository validation, including evidence catalog/provider/subject checks and policy override control checks.
- `.superpowers/sdd/2026-08-28-guardrails-v2/task-1-report.md` — Task 1 implementation, TDD, review-fix, and verification evidence.

## TDD evidence

### RED 1

Command:

```sh
python3 -m unittest tooling.validators.tests.test_control_catalog tooling.validators.tests.test_guardrails_contracts -v
```

Output summary before production changes:

```text
Ran 18 tests in 0.005s
FAILED (failures=33, errors=10)
```

The failures showed the v1 catalog/baseline/schemas, missing profiles and
schemas, missing nested results/selections, and absent v2 validators.

### GREEN 1

Command:

```sh
python3 -m unittest tooling.validators.tests.test_control_catalog tooling.validators.tests.test_guardrails_contracts -v
```

Output:

```text
Ran 18 tests in 0.004s
OK
```

### RED 2

Command:

```sh
python3 -m unittest tooling.validators.tests.test_guardrails_contracts.GuardrailsContractValidationTests.test_core_and_github_default_providers_are_exact -v
```

Output:

```text
Ran 1 test in 0.001s
FAILED (failures=1)
```

The failure identified the five GitHub profile providers as not enabled by
default in their provider definitions.

### GREEN 2

Command:

```sh
python3 -m unittest tooling.validators.tests.test_guardrails_contracts.GuardrailsContractValidationTests.test_core_and_github_default_providers_are_exact -v
```

Output:

```text
Ran 1 test in 0.000s
OK
```

### Review RED 1 — cross-contract and empty-map findings

Command:

```sh
python3 -m unittest \
  tooling.validators.tests.test_guardrails_contracts.GuardrailsContractValidationTests.test_evidence_rejects_unknown_control \
  tooling.validators.tests.test_guardrails_contracts.GuardrailsContractValidationTests.test_evidence_rejects_unknown_provider \
  tooling.validators.tests.test_guardrails_contracts.GuardrailsContractValidationTests.test_evidence_rejects_provider_without_control_capability \
  tooling.validators.tests.test_guardrails_contracts.GuardrailsContractValidationTests.test_evidence_rejects_subject_type_mismatch \
  tooling.validators.tests.test_guardrails_contracts.GuardrailsContractValidationTests.test_evidence_provider_map_nonempty_boundary_matches_schema \
  tooling.validators.tests.test_guardrails_contracts.GuardrailsContractValidationTests.test_evidence_optional_field_boundaries_match_schema \
  tooling.validators.tests.test_guardrails_contracts.GuardrailsContractValidationTests.test_policy_rejects_unknown_override_control -v
```

Output summary before review production edits:

```text
Ran 7 tests in 0.003s
FAILED (errors=7)
```

The errors were the expected missing cross-contract validator inputs plus the
missing `minProperties` schema boundary.

### Review GREEN 1

The same seven-test command after the minimal validator and evidence schema
changes:

```text
Ran 7 tests in 0.003s
OK
```

### Review RED 2 — remaining schema/handwritten boundaries

Command:

```sh
python3 -m unittest \
  tooling.validators.tests.test_control_catalog.ControlCatalogPolicyTests.test_catalog_string_boundaries_match_schema \
  tooling.validators.tests.test_control_catalog.ControlCatalogPolicyTests.test_schema_nonempty_strings_match_handwritten_nonblank_rule \
  tooling.validators.tests.test_guardrails_contracts.GuardrailsContractValidationTests.test_provider_schema_boundaries_match_handwritten_validation -v
```

Output summary before the schema parity edits:

```text
Ran 3 tests in 0.003s
FAILED (failures=2, errors=14)
```

The failures exposed the control `name`/`stage` maximum mismatch; the errors
identified missing nonblank patterns, provider capability `minItems`, and
template string bounds.

### Review GREEN 2

The same three-test command after aligning those boundaries:

```text
Ran 3 tests in 0.002s
OK
```

### Review RED 3 / GREEN 3 — optional reason parity

Command:

```sh
python3 -m unittest tooling.validators.tests.test_guardrails_contracts.GuardrailsContractValidationTests.test_evidence_optional_field_boundaries_match_schema -v
```

Before restoring validation for a malformed optional `reason`:

```text
Ran 1 test in 0.001s
FAILED (failures=1)
```

After the minimal fix:

```text
Ran 1 test in 0.001s
OK
```

### Review RED 4 / GREEN 4 — whitespace-only evidence records

Command:

```sh
python3 -m unittest \
  tooling.validators.tests.test_guardrails_contracts.GuardrailsContractValidationTests.test_evidence_rejects_whitespace_only_records \
  tooling.validators.tests.test_guardrails_contracts.GuardrailsContractValidationTests.test_evidence_record_nonblank_boundary_matches_schema -v
```

Before requiring a non-whitespace record in handwritten and schema validation:

```text
Ran 2 tests in 0.001s
FAILED (failures=2)
```

After using `record.strip()` and adding the schema `pattern: "\\S"` boundary:

```text
Ran 2 tests in 0.001s
OK
```

## Final verification

Fresh combined verification command:

```sh
python3 -m unittest tooling.validators.tests.test_control_catalog tooling.validators.tests.test_guardrails_contracts -v &&
python3 -m unittest discover -s guardrails/tests -p 'test_*.py' &&
python3 -m unittest discover -s tooling/tests -p 'test_*.py' &&
python3 -m unittest discover -s tooling/validators/tests -p 'test_*.py' &&
python3 -m unittest discover -s examples/python-demo -p 'test_*.py' &&
python3 examples/python-demo/tools/validate_demo.py --documentation &&
python3 tooling/validate-skills.py &&
python3 tooling/validators/validate_repository.py &&
python3 tooling/validators/validate_documentation.py &&
python3 -m compileall -q tooling/validators tooling/validators/tests &&
git diff --check
```

Output summary:

```text
Focused v2 contracts: 31 tests, OK
Guardrails evaluator regressions: 8 tests, OK
Tooling regressions: 79 tests, OK
Repository validator suite: 49 tests, OK
Demo unit tests: 5 tests, OK
Demo repository validation passed
Validated 31 skills
Validated 31 skills, 29 controls, guardrail schemas, and documentation
Documentation validation passed
Python compile: exit 0
git diff --check: exit 0
```

Staged verification:

```sh
git diff --cached --check
```

Output: exit 0 with no findings. The staged set contained exactly the 14 Task 1
files listed above.

## Concerns

- The evaluator, scanner, scorecard, GitHub collector, configuration CLI, installer,
  producer manifest, and distributed compatibility copies still implement v1 by
  design. Task 2 must consume these v2 contracts before the branch is runtime-ready.
- Existing unrelated worktree changes to `.gitignore` and
  `docs/superpowers/plans/2026-08-28-guardrails-v2.md` were preserved and excluded
  from the Task 1 commit.
