#!/usr/bin/env python3
"""Validate the canonical guardrails repository."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ABSOLUTE_PATH_PATTERN = re.compile(r"(/Users/|/private/|\\\\Users\\\\)")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json_object(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"{path.relative_to(ROOT)} is not JSON-compatible YAML: {error}")
    if not isinstance(value, dict):
        fail(f"{path.relative_to(ROOT)} must contain an object")
    return value


def evaluator_module():
    path = ROOT / "guardrails" / "evaluate.py"
    spec = importlib.util.spec_from_file_location("guardrails_evaluator", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def validate_skills() -> int:
    count = 0
    for skill in sorted((ROOT / "skills").glob("*/SKILL.md")):
        lines = skill.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0].strip() != "---" or not any(
            line.lstrip().startswith("description:") for line in lines
        ):
            fail(f"{skill.relative_to(ROOT)} is missing valid frontmatter")
        if not (skill.parent / "agents" / "openai.yaml").exists():
            fail(f"{skill.parent.relative_to(ROOT)} is missing agents/openai.yaml")
        count += 1
    if count == 0:
        fail("skills/ must contain at least one skill")
    return count


def validate_control_catalog() -> int:
    catalog = load_json_object(ROOT / "policies" / "control-catalog.yaml")
    if catalog.get("version") != 1 or not isinstance(catalog.get("controls"), list):
        fail("control catalog must contain version 1 and a controls list")
    required_fields = {
        "id", "name", "purpose", "producer", "stage", "requiredness",
        "activation",
        "blocking", "status_context", "evidence",
    }
    seen: set[str] = set()
    for control in catalog["controls"]:
        if not isinstance(control, dict) or not required_fields <= set(control):
            fail("every control must define its policy-to-evidence contract")
        if control["id"] in seen:
            fail(f"duplicate control id: {control['id']}")
        seen.add(control["id"])
        if control["requiredness"] not in {
            "required", "required_when_configured", "advisory", "not_applicable"
        }:
            fail(f"invalid requiredness for {control['id']}")
        if control["activation"] not in {"github-native", "external", "repository"}:
            fail(f"invalid activation for {control['id']}")
    return len(catalog["controls"])


def validate_guardrail_contract() -> None:
    evaluator = evaluator_module()
    policy = load_json_object(ROOT / "guardrails" / "baseline.yaml")
    evaluator.validate_policy(policy)
    evidence = load_json_object(ROOT / "guardrails" / "evidence-example.yaml")
    evaluator.validate_evidence(evidence)
    for name in ("policy.schema.json", "evidence.schema.json"):
        schema = load_json_object(ROOT / "guardrails" / name)
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            fail(f"{name} must use JSON Schema 2020-12")


def validate_links_and_docs() -> None:
    subprocess.run(
        [sys.executable, "tooling/validators/validate_documentation.py"],
        cwd=ROOT,
        check=True,
    )


def validate_no_machine_paths() -> None:
    for path in ROOT.rglob("*"):
        relative_path = path.relative_to(ROOT)
        if not path.is_file() or ".git" in path.parts:
            continue
        if relative_path.parts[0] == ".superpowers":
            continue
        if path.name in {"validate_repository.py", "validate-skills.py"}:
            continue
        if path.suffix not in {".md", ".py", ".yaml", ".yml", ".sh"}:
            continue
        if ABSOLUTE_PATH_PATTERN.search(path.read_text(encoding="utf-8")):
            fail(f"{relative_path} contains a machine-local path")


def main() -> int:
    skills = validate_skills()
    controls = validate_control_catalog()
    validate_guardrail_contract()
    validate_links_and_docs()
    validate_no_machine_paths()
    print(f"Validated {skills} skills, {controls} controls, guardrail schemas, and documentation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
