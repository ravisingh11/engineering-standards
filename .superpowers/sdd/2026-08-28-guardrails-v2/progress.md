# SDD ledger — plan: docs/superpowers/plans/2026-08-28-guardrails-v2.md

## Pre-flight interface scan

| Tasks | Shared interface | Finding | Ruling |
| --- | --- | --- | --- |
| 1 → 2 | Schemas, catalog, profiles, providers | Runtime depends on stable v2 contracts. | Task 1 lands before Task 2; runtime may not invent fields outside the contract. |
| 1 → 3 | Profile/provider definitions | Installer and workflows consume canonical definitions. | Distribution copies are generated from Task 1 sources and equality-tested. |
| 2 → 3 | Evaluator, collector, scanner, configurator | Producers must emit the exact nested evidence shape. | Task 3 uses only Task 2 public interfaces and adds integration tests. |
| 1–3 → 4 | Public behavior and commands | Documentation must not lead implementation. | Documentation follows verified behavior and uses executable examples. |
| 1–4 → 5 | Full branch | Verification must cover every prior task. | Task 5 performs fresh full-suite and end-to-end scans before review. |

Each task is internally consistent with its named tests and write surface.
Ruling: v2 is a clean public break, but implementation may stage v2 artifacts
beside v1 until the cutover commit; no dual-version behavior will be documented
or shipped as the final state.

## Combined Task 1 + Task 2

Status: complete
Base: 54e50b91a9b4204fbbf10a5bf13e37f27128f5b2
Source commits: d6dd9b260b3a2204db46c3647a6fabac2b642943,
1b6270564b62fd7de0daa99a931406a541a6f46a
Commit: ae63c898decaa829c04f794738231c1cbc73fe8f
Count: 1 commit, 31 files changed
Tasks: v2 contracts and runtime
Implementers: 01a04896-c39f-7c42-a186-37f6ae3a04a4,
01a048af-e0e4-7a71-b100-d00d8565504d,
01a048f0-441b-7de3-bdbd-0575cd211696
Reviews: both tasks approved after two repair passes; final reviewers
01a048ec-3017-70c1-a978-451593648b49,
01a04923-5a14-7c71-9862-2b13f92ee045

## Task 3

Status: complete
Source commit: 5fd36224d744bacf685a17c59fa4a63d030d9f79
Base: ae63c898decaa829c04f794738231c1cbc73fe8f
Commit: 18888a120e6ed241c227106580bc4911318629c0
Count: 1 commit, 92 files changed

## Task 4

Status: complete
Source commit: 8b24333ee1c4da845f1f6803bac2d4e733e9e578
Base: 18888a120e6ed241c227106580bc4911318629c0
Commit: this final documentation and example commit; its object ID is reported
from the final Git log because a commit cannot embed its own object ID
Count: 1 commit, 66 files changed; third of 3 commits after origin/main
Workflow: docs-sync; wording derived from current v2 contracts and generated
demo copies refreshed from canonical distribution sources.
Verification: 16 guardrails tests, 150 tooling tests, 63 validator tests, 5
demo tests, demo/documentation/repository/skill validators, all three README
commands in an archived standalone demo, JSON/YAML parsing, full generated-copy
equality, pyright, active-guidance drift search, and diff checks passed.

## Task 5

Status: complete
Branch: `feat/guardrails-v2`, exactly 3 commits after `origin/main`
Standalone demo: `feat/guardrails-v2-demo`, commit
`20f0144282c7a1a926a3733e3a5a6c9250a58a21`
Verification: full unit, validator, demo, skill, documentation, compile,
JSON/YAML, link, generated-copy, type-check, diff, and exact-HEAD scan checks
passed. Whole-branch review findings were reproduced, fixed, and protected by
focused regressions. Neither branch was pushed or merged.
