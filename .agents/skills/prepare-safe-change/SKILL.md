---
name: prepare-safe-change
description: "Prepare an evidence-backed software change without expanding authority. Use when an agent needs to identify applicable checks, capture truthful producer evidence for an exact revision, evaluate repository guardrails, or report whether a change is ready for a separately authorized commit, merge, or release."
---

# Prepare Safe Change

Use the repository's `.guardrails/policy.yaml` policy. The policy declares evidence
requirements; it does not authorize an operation or tell you which tools to run.

## Workflow

1. Read repository instructions and inspect the exact change or artifact.
2. Select the policy operation that matches the requested boundary.
3. Identify the current immutable revision, such as a commit or Git tree.
4. Obtain results from the repository's existing test, SAST, secret-scanning,
   review, or other evidence producers.
5. Record every relevant result using `references/evidence-example.yaml`.
   Preserve `failed`, `blocked`, and `not_run` outcomes exactly.
6. Resolve the evaluator from `.guardrails/evaluate.py` in an installed
   repository or `guardrails/evaluate.py` in this standards repository, then run:

   ~~~sh
   exact_revision="${EXACT_REVISION:?set EXACT_REVISION to the immutable subject revision}"
   if [ -f .guardrails/evaluate.py ]; then
     evaluator=.guardrails/evaluate.py
   elif [ -f guardrails/evaluate.py ]; then
     evaluator=guardrails/evaluate.py
   else
     echo "Guardrails v2 evaluator not found" >&2
     exit 2
   fi
   skill_reference=references/evidence-example.yaml
   if [ -n "${GUARDRAILS_EVIDENCE:-}" ]; then
     evidence="${GUARDRAILS_EVIDENCE}"
   elif [ -f ".agents/skills/prepare-safe-change/${skill_reference}" ]; then
     evidence=".agents/skills/prepare-safe-change/${skill_reference}"
   else
     evidence="skills/prepare-safe-change/${skill_reference}"
   fi
   python3 "$evaluator" \
     --policy .guardrails/policy.yaml \
     --profiles .guardrails/profiles.yaml \
     --catalog .guardrails/control-catalog.yaml \
     --providers .guardrails/providers.yaml \
     --evidence "$evidence" \
     --operation change \
     --revision "$exact_revision" \
     --subject-type git-commit
   ~~~
7. Resolve required findings or report the block. Report advisories separately.
8. Present the operation, exact revision, evidence status, and decision.
9. Perform a commit, push, merge, release, or deployment only when separately
   authorized.

## Safety Rules

- Do not invent, upgrade, or reinterpret producer results.
- Do not reuse evidence from another revision.
- Do not treat `not_run` as satisfying a required check.
- Do not change policy merely to make the current evaluation pass.
- Do not amend, rebase, force push, or rewrite history unless explicitly requested.
- Never infer authority to commit, push, merge, deploy, publish, delete, or
  change external settings from an `allow` decision.
