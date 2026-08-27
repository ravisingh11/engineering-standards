#!/usr/bin/env python3
"""Run local guardrail producers and render a repository-specific scorecard."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from guardrails.evaluate import validate_evidence
except ModuleNotFoundError:
    evaluator_path = ROOT / ".guardrails" / "evaluate.py"
    evaluator_spec = importlib.util.spec_from_file_location(
        "installed_guardrails_evaluate", evaluator_path
    )
    if evaluator_spec is None or evaluator_spec.loader is None:
        raise
    evaluator_module = importlib.util.module_from_spec(evaluator_spec)
    evaluator_spec.loader.exec_module(evaluator_module)
    validate_evidence = evaluator_module.validate_evidence


EVIDENCE_LABELS = {
    "passed": "PASSED",
    "failed": "FAILED",
    "blocked": "BLOCKED",
    "not_run": "NO RESULT",
    "missing": "NOT ACTIVATED",
    "no_result": "NO RESULT",
    "not_activated": "NOT ACTIVATED",
}
CONTROL_DOCS = {
    "repository-validation": "https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-setup.md#repository-validation",
    "documentation": "https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-setup.md#documentation-validation",
    "repository-ground-truth": "https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-setup.md#ground-truth",
    "build": "https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-setup.md#build",
    "unit-tests": "https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-setup.md#unit-tests",
    "codeql-sast": "https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-setup.md#codeql--sast",
    "secrets-scan": "https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-setup.md#secrets-scanning",
    "dependency-review": "https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-setup.md#dependency-review",
    "dependabot": "https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-setup.md#dependabot",
    "sonarqube": "https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-setup.md#sonarqube",
    "fossa": "https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-setup.md#fossa",
    "snyk-code": "https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-setup.md#snyk",
    "snyk-open-source": "https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-setup.md#snyk",
    "soak-check": "https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-setup.md#soak-check",
    "ai-engineering-review": "https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-setup.md#ai-reviews",
    "ai-qa-review": "https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-setup.md#ai-reviews",
    "ai-security-review": "https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-setup.md#ai-reviews",
    "ai-repo-standards-review": "https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-setup.md#repository-standards-review",
}


def evidence_label(status: str) -> str:
    return EVIDENCE_LABELS.get(status, status.upper())


def run(command: list[str], cwd: Path) -> tuple[int, str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    output = (result.stdout + result.stderr).strip()
    return result.returncode, output


def dependabot_configuration_evidence(target: Path) -> dict[str, Any] | None:
    """Report configuration presence without claiming GitHub activation."""
    config = target / ".github" / "dependabot.yml"
    if not config.exists():
        config = target / ".github" / "dependabot.yaml"
    if not config.exists():
        return None
    relative = config.relative_to(target)
    return {
        "producer": "repository Dependabot configuration",
        "status": "not_run",
        "evidence": [f"configuration: {relative}"],
        "reason": (
            "Dependabot configuration is present, but GitHub repository settings "
            "and a revision-bound Dependabot producer result were not verified by "
            "this local scan."
        ),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def default_config_path(target: Path, consumer_path: str, shared_path: str) -> Path:
    """Resolve defaults for both consumers and this standards repository."""
    consumer = target / consumer_path
    if consumer.exists():
        return consumer
    if target == ROOT and (target / shared_path).exists():
        return target / shared_path
    return consumer


def local_evidence(target: Path, revision: str, base_ref: str) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    validators = target / "tooling" / "validators"
    for check_id, filename, producer in (
        ("repository-validation", "validate_repository.py", "local repository validation"),
        ("documentation", "validate_documentation.py", "local documentation validation"),
    ):
        validator = validators / filename
        if not validator.exists():
            checks[check_id] = {
                "producer": producer,
                "status": "not_run",
                "reason": f"{validator.relative_to(target)} is not installed in this repository",
            }
            continue
        command = [sys.executable, str(validator)]
        code, output = run(command, target)
        checks[check_id] = {
            "producer": producer,
            "status": "passed" if code == 0 else "failed",
            "evidence": [" ".join(command), output[-1000:]],
        }

    ground_truth_validator = target / ".guardrails" / "validate_ground_truth.py"
    ground_truth_policy = target / ".ai" / "ground-truth.yaml"
    if ground_truth_validator.exists() and ground_truth_policy.exists():
        command = [sys.executable, str(ground_truth_validator), "--policy", str(ground_truth_policy)]
        code, output = run(command, target)
        checks["repository-ground-truth"] = {
            "producer": "repository ground-truth validator",
            "status": "passed" if code == 0 else "failed",
            "evidence": [" ".join(command), output[-1000:]],
        }

    dependabot = dependabot_configuration_evidence(target)
    if dependabot is not None:
        checks["dependabot"] = dependabot

    scope_validator = validators / "inspect_change_scope.py"
    with tempfile.NamedTemporaryFile(suffix=".json") as scope_file:
        if not scope_validator.exists():
            checks["change-scope"] = {
                "producer": "local change-scope inspection",
                "status": "not_run",
                "reason": f"{scope_validator.relative_to(target)} is not installed in this repository",
            }
            return {"version": 1, "subject": {"type": "git-commit", "revision": revision}, "checks": checks}
        command = [
            sys.executable,
            str(scope_validator),
            "--base-ref",
            base_ref,
            "--head-ref",
            revision,
            "--output",
            scope_file.name,
        ]
        code, output = run(command, target)
        if code == 0:
            scope = load(Path(scope_file.name))
            checks["change-scope"] = {
                "producer": "local change-scope inspection",
                "status": scope["status"],
                "evidence": [json.dumps(scope["metrics"], sort_keys=True)],
            }
        else:
            checks["change-scope"] = {
                "producer": "local change-scope inspection",
                "status": "not_run",
                "reason": output[-1000:] or "change scope could not be evaluated",
            }

    return {"version": 1, "subject": {"type": "git-commit", "revision": revision}, "checks": checks}


def merge_external_evidence(evidence: dict[str, Any], directory: Path | None) -> None:
    if directory is None or not directory.exists():
        return
    seen_external: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.json")):
        extra = load(path)
        validate_evidence(extra)
        if extra["subject"] != evidence["subject"]:
            # Reports are intentionally reusable across local reruns. Never use
            # stale evidence, but do not make an old artifact strand the scan.
            continue
        for check_id, result in extra.get("checks", {}).items():
            previous_external = seen_external.get(check_id)
            if previous_external is not None:
                previous_status = previous_external.get("status")
                current_status = result.get("status")
                if previous_status in {"passed", "failed"} and current_status == "not_run":
                    continue
                if previous_status == "not_run" and current_status in {"passed", "failed"}:
                    evidence["checks"][check_id] = result
                    seen_external[check_id] = result
                    continue
                if previous_status == current_status == "not_run":
                    continue
                raise ValueError(f"duplicate evidence for check {check_id!r}")
            existing = evidence["checks"].get(check_id)
            if existing and existing.get("status") in {"passed", "failed"} and result.get("status") == "not_run":
                seen_external[check_id] = result
                continue
            evidence["checks"][check_id] = result
            seen_external[check_id] = result


def add_missing_policy_checks(evidence: dict[str, Any], policy: dict[str, Any], operation: str) -> None:
    selected = [*policy["operations"][operation]["required"], *policy["operations"][operation]["advisory"]]
    for check_id in selected:
        if check_id not in evidence["checks"]:
            evidence["checks"][check_id] = {
                "producer": "not configured for local scan",
                "status": "not_run",
                "reason": "Run the configured workflow or external producer and add its evidence file.",
            }


def detailed_output(card: dict[str, Any], evidence_path: str, report_path: str) -> str:
    required_controls = [
        control for control in card["controls"] if control["enforcement"] == "enforced"
    ]
    advisory_findings = [
        finding for finding in card["findings"] if finding["enforcement"] == "advisory"
    ]
    inactive_controls = [
        control for control in card["controls"]
        if control["enforcement"] == "not_activated"
    ]
    lines = [
        "╔══════════════════════════════════════════════════════════════════════╗",
        "║                            GUARDRAIL SCAN                            ║",
        "╚══════════════════════════════════════════════════════════════════════╝",
        f"  RESULT       {card['status']} — {card['decision'].upper()}",
        f"  ENFORCED     {card['enforced']['passed']}/{card['enforced']['total']} passed ({card['enforced']['percent'] or 0}%)",
        f"  ADVISORY     {card['advisory']['passed']}/{card['advisory']['total']} passed — non-blocking",
        f"  READINESS    {card['readiness_status']} (enforced RED: {card['enforced_readiness_red']})",
        f"  REVISION     {card['subject']['revision']}",
        f"  POLICY       {card['policy']} / {card['operation']}",
        "",
        "What this means",
        "----------------",
        "  Enforced controls passed, so this change is allowed to proceed.",
        "  Orange controls are selected but not fully connected yet.",
        "  Gray controls are available but not activated for this repository.",
        "  Advisory findings are visible and do not block this decision.",
        "",
        "Enforced controls",
        "-----------------",
    ]
    for control in required_controls:
        icon = "✅" if control["readiness"] == "GREEN" else "🛑"
        lines.append(f"  {icon} {control['name']} — {evidence_label(control['evidence_status'])}")
    lines.extend([
        "",
        "Advisory findings",
        "------------------",
    ])
    if advisory_findings:
        for finding in advisory_findings:
            lines.append(f"  ⚠️  {finding['check']}: {finding['message']}")
    else:
        lines.append("  ✅ None")
    lines.extend([
        "",
        "Available but not activated",
        "----------------------------",
    ])
    if inactive_controls:
        for control in inactive_controls:
            lines.append(f"  ⚪ {control['name']} — {control['activation']}")
    else:
        lines.append("  ✅ None")
    lines.extend([
        "",
        "Next actions",
        "------------",
    ])
    actions = []
    if any(finding["check"] == "change-scope" for finding in advisory_findings):
        actions.append("Review the change-scope finding or split the current work.")
    if any(finding["check"].startswith("snyk-") for finding in advisory_findings):
        actions.append("Configure SNYK_TOKEN to activate Snyk advisory scans.")
    if inactive_controls:
        actions.append("Select additional controls with configure.py when ready.")
    for number, action in enumerate(actions, start=1):
        lines.append(f"  {number}. {action}")
    if not advisory_findings and not inactive_controls:
        lines.append("  ✅ No further activation actions are required.")
    lines.extend([
        "",
        "Detailed controls",
        "-----------------",
        "  Evidence: PASSED = producer reported pass | NO RESULT = selected but producer did not report | NOT ACTIVATED = not selected",
        f"{'STATUS':<7} {'ENFORCEMENT':<12} {'ACTIVATION':<14} {'EVIDENCE':<10} CONTROL",
    ])
    for control in card["controls"]:
        lines.append(
            f"{control['readiness']:<7} {control['enforcement']:<9} "
            f"{control['activation']:<14} {evidence_label(control['evidence_status']):<12} "
            f"{control['id']} — {control['name']}"
        )
    lines.extend(["", "Findings", "--------"])
    if card["findings"]:
        for finding in card["findings"]:
            lines.append(
                f"- [{finding['enforcement']}] {finding['check']}: "
                f"{evidence_label(finding['status'])} — {finding['message']}"
            )
    else:
        lines.append("- None")
    lines.extend(["", f"Evidence: {evidence_path}", f"Report: {report_path}"])
    return "\n".join(lines) + "\n"


def detailed_markdown(card: dict[str, Any], evidence_path: str, report_path: str) -> str:
    status_icons = {"GREEN": "🟢", "ORANGE": "🟠", "GRAY": "⚪", "RED": "🔴"}
    lines = [
        "# Guardrail Scan Report",
        "",
        f"- Status: **{card['status']}**",
        f"- Decision: **{card['decision'].upper()}**",
        f"- Policy: `{card['policy']}` ({card['operation']})",
        f"- Revision: `{card['subject']['revision']}`",
        f"- Evidence: `{evidence_path}`",
        f"- Report: `{report_path}`",
        "",
        "## Summary",
        "",
        f"- Enforced: **{card['enforced']['passed']}/{card['enforced']['total']}** ({card['enforced']['percent'] or 0}%)",
        f"- Advisory passed: **{card['advisory']['passed']}/{card['advisory']['total']}** ({card['advisory']['percent'] or 0}%) — non-blocking",
        f"- Readiness: **{card['readiness_status']}** — enforced RED {card['enforced_readiness_red']}; GREEN {card['readiness']['GREEN']}, ORANGE {card['readiness']['ORANGE']}, GRAY {card['readiness']['GRAY']}, RED {card['readiness']['RED']}",
        "",
        "### Status legend",
        "",
        "🟢 GREEN = selected and passed  ·  🟠 ORANGE = selected but no result  ·  ⚪ GRAY = available but not activated  ·  🔴 RED = failed or missing enforced evidence",
        "",
        "Evidence legend: PASSED = producer reported pass  ·  NO RESULT = selected but producer did not report  ·  NOT ACTIVATED = control not selected",
        "",
        "## Controls",
        "",
        "| Status | Enforcement | Activation | Evidence | Control |",
        "| --- | --- | --- | --- | --- |",
    ]
    for control in card["controls"]:
        lines.append(
            f"| {status_icons[control['readiness']]} {control['readiness']} | {control['enforcement']} | "
            f"{control['activation']} | {evidence_label(control['evidence_status'])} | "
            f"[`{control['id']}` — {control['name']}]({CONTROL_DOCS.get(control['id'], 'https://github.com/ravisingh11/engineering-standards/blob/main/docs/control-status.md#control-map')}) |"
        )
    lines.extend(["", "## Findings", ""])
    if card["findings"]:
        lines.extend(
            f"- **{finding['enforcement']}** `{finding['check']}`: {evidence_label(finding['status'])} — {finding['message']}"
            for finding in card["findings"]
        )
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local producers and render a guardrail scorecard")
    parser.add_argument("--target", type=Path, default=Path("."))
    parser.add_argument("--policy", type=Path, default=None)
    parser.add_argument("--catalog", type=Path, default=None)
    parser.add_argument("--evidence", type=Path, default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--operation", default="change")
    parser.add_argument("--revision", default="")
    parser.add_argument("--base-ref", default="HEAD~1")
    parser.add_argument("--all-catalog-controls", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--report",
        type=Path,
        help="Markdown report path; defaults to a UTC timestamped file under .artifacts/guardrails",
    )
    args = parser.parse_args()
    target = args.target.resolve()
    policy_path = (
        (target / args.policy).resolve()
        if args.policy
        else default_config_path(target, ".ai/guardrails.yaml", "guardrails/baseline.yaml")
    )
    catalog_path = (
        (target / args.catalog).resolve()
        if args.catalog
        else default_config_path(target, ".ai/control-catalog.yaml", "policies/control-catalog.yaml")
    )
    evidence_path = (
        (target / args.evidence).resolve()
        if args.evidence
        else target / ".artifacts/guardrails/evidence.json"
    )
    evidence_dir = (
        (target / args.evidence_dir).resolve()
        if args.evidence_dir
        else target / ".artifacts/guardrails/evidence"
    )
    try:
        policy = load(policy_path)
        revision = args.revision or run(["git", "rev-parse", "HEAD"], target)[1]
        evidence = local_evidence(target, revision, args.base_ref)
        merge_external_evidence(evidence, evidence_dir)
        add_missing_policy_checks(evidence, policy, args.operation)
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        scorecard = target / ".guardrails" / "scorecard.py"
        if not scorecard.exists():
            scorecard = ROOT / "tooling" / "guardrail_scorecard.py"
        command = [
            sys.executable,
            str(scorecard),
            "--policy", str(policy_path),
            "--catalog", str(catalog_path),
            "--evidence", str(evidence_path),
            "--operation", args.operation,
            "--revision", revision,
            "--subject-type", "git-commit",
        ]
        if args.all_catalog_controls:
            command.append("--all-catalog-controls")
        command.append("--json")
        result = subprocess.run(command, cwd=target, text=True, capture_output=True)
        card: dict[str, Any] | None = None
        try:
            card = json.loads(result.stdout)
            if args.json:
                screen_output = json.dumps(card, indent=2) + "\n"
            else:
                screen_output = detailed_output(card, str(evidence_path), "<pending>")
        except json.JSONDecodeError:
            screen_output = result.stdout + result.stderr
        timestamp = datetime.now(timezone.utc)
        report_path = (
            (target / args.report).resolve()
            if args.report
            else target
            / ".artifacts"
            / "guardrails"
            / f"scorecard-{timestamp.strftime('%Y%m%d-%H%M%SZ')}.md"
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        def report_location(path: Path) -> str:
            try:
                return str(path.relative_to(target))
            except ValueError:
                return str(path)

        report_location_value = report_location(report_path)
        if isinstance(card, dict) and "controls" in card:
            report = (
                f"# Guardrail Scan Report\n\n"
                f"- Generated (UTC): `{timestamp.isoformat()}`\n"
                + detailed_markdown(card, report_location(evidence_path), report_location_value).split("\n", 2)[2]
            )
        else:
            report = (
            "# Guardrail Scorecard\n\n"
            f"- Generated (UTC): `{timestamp.isoformat()}`\n"
            f"- Revision: `{revision}`\n"
            f"- Operation: `{args.operation}`\n"
            f"- Policy: `{report_location(policy_path)}`\n"
            f"- Evidence: `{report_location(evidence_path)}`\n"
            f"- Report: `{report_location(report_path)}`\n\n"
            "## Result\n\n"
            "```text\n"
            f"{screen_output.rstrip()}\n"
            "```\n"
            )
        report_path.write_text(report, encoding="utf-8")
        if not args.json and isinstance(card, dict):
            screen_output = screen_output.replace(
                "Report: <pending>", f"Report: {report_location_value}"
            )
        print(screen_output, end="")
        if not args.json and isinstance(card, dict):
            print(f"\nMarkdown report: {report_location_value}")
        return result.returncode
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
