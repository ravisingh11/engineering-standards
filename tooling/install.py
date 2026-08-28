#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "guardrails" / "baseline.yaml"
CONTROL_CATALOG = ROOT / "policies" / "control-catalog.yaml"
DOCUMENTATION_POLICY = ROOT / "guardrails" / "defaults" / "documentation.yaml"
CHANGE_SCOPE_POLICY = ROOT / "guardrails" / "defaults" / "change-scope.yaml"
GROUND_TRUTH_POLICY = ROOT / "guardrails" / "defaults" / "ground-truth-ai.yaml"
EVALUATOR = ROOT / "guardrails" / "evaluate.py"
SCORECARD = ROOT / "tooling" / "guardrail_scorecard.py"
CONFIGURE = ROOT / "tooling" / "configure_guardrails.py"
SCAN = ROOT / "tooling" / "scan_repository.py"
GITHUB_EVIDENCE = ROOT / "tooling" / "github_evidence.py"
GROUND_TRUTH = ROOT / "tooling" / "validators" / "validate_ground_truth.py"
PRODUCER_MANIFEST = ROOT / "guardrails" / "default-producer-manifest.json"
PROVIDER_CONFIG = ROOT / "policies" / "provider-config.yaml"
SKILL = ROOT / "skills" / "prepare-safe-change"
GITHUB_WORKFLOW = ROOT / "docs" / "examples" / "guardrails.yml"
PROVIDER_TEMPLATES = {
    "snyk": ROOT / ".github" / "workflows" / "snyk.yml",
    "semgrep": ROOT / "workflows" / "semgrep.yml",
    "sonarqube": ROOT / "workflows" / "sonar.yml",
    "fossa": ROOT / ".github" / "workflows" / "fossa.yml",
}
VERSION = "1.0.0"
# Older installer-owned paths that may be removed during a refresh. Keep this
# allowlist narrow: consumer files, workflows, and reports are never inferred.
LEGACY_RUNTIME_DIR = Path(".agentic-guardrails")
LEGACY_SCORECARD_WORKFLOW = Path(".github") / "workflows" / "agentic-guardrails-scorecard.yml"
LEGACY_RUNTIME_FILES = tuple(
    LEGACY_RUNTIME_DIR / filename
    for filename in (
        "configure.py",
        "evaluate.py",
        "github_evidence.py",
        "producer-manifest.json",
        "providers.yaml",
        "scan.py",
        "scorecard.py",
        "validate_ground_truth.py",
    )
)
LEGACY_FILES = (
    Path(".ai") / "providers.yaml",
    Path(".ai") / "producer-manifest.json",
    *LEGACY_RUNTIME_FILES,
    LEGACY_SCORECARD_WORKFLOW,
)
LEGACY_CONFIG_PATHS = {
    Path(".ai/guardrails.yaml"): Path(".guardrails/policy.yaml"),
    Path(".ai/control-catalog.yaml"): Path(".guardrails/control-catalog.yaml"),
    Path(".ai/documentation.yaml"): Path(".guardrails/documentation.yaml"),
    Path(".ai/change-scope.yaml"): Path(".guardrails/change-scope.yaml"),
    Path(".ai/ground-truth.yaml"): Path(".guardrails/ground-truth-ai.yaml"),
}


class InstallItem(NamedTuple):
    source: Path
    destination: Path
    kind: str


def reject_legacy_configuration(target: Path) -> None:
    conflicts = [
        (old_path, new_path)
        for old_path, new_path in LEGACY_CONFIG_PATHS.items()
        if (target / old_path).exists() or (target / old_path).is_symlink()
    ]
    if not conflicts:
        return
    instructions = "\n".join(
        f"- git mv {old_path} {new_path}" for old_path, new_path in conflicts
    )
    raise ValueError(
        "legacy Guardrails configuration must be moved before installation:\n"
        f"{instructions}"
    )


def legacy_cleanup_items(target: Path) -> list[InstallItem]:
    """Return safe, file-only migration removals for a consumer repository."""
    items: list[InstallItem] = []
    for relative_path in LEGACY_FILES:
        path = target / relative_path
        if path.is_dir() and not path.is_symlink():
            raise ValueError(f"refusing to clean legacy path because it is a directory: {path}")
        if path.is_file() or path.is_symlink():
            items.append(InstallItem(path, path, "remove"))
    return items


def apply_legacy_migrations(
    plan: list[InstallItem], target: Path, *, github_actions: bool
) -> list[InstallItem]:
    """Preserve consumer-owned configuration while adopting canonical names."""
    migration_sources = {
        target / ".guardrails" / "providers.yaml": (
            target / ".agentic-guardrails" / "providers.yaml",
            target / ".ai" / "providers.yaml",
        ),
        target / ".guardrails" / "producer-manifest.json": (
            target / ".agentic-guardrails" / "producer-manifest.json",
            target / ".ai" / "producer-manifest.json",
        ),
    }
    if github_actions:
        migration_sources[target / ".github" / "workflows" / "guardrails-scorecard.yml"] = (
            target / LEGACY_SCORECARD_WORKFLOW,
        )

    migrated: list[InstallItem] = []
    for item in plan:
        if item.destination.exists() or item.destination not in migration_sources:
            migrated.append(item)
            continue
        source = next(
            (candidate for candidate in migration_sources[item.destination] if candidate.is_file()),
            None,
        )
        if source is None:
            migrated.append(item)
            continue
        kind = "migrate-text" if item.destination.suffix in {".yml", ".yaml"} else "file"
        migrated.append(InstallItem(source, item.destination, kind))
    return migrated


def build_plan(target: Path, *, github_actions: bool = False, providers: list[str] | None = None) -> list[InstallItem]:
    plan = [
        InstallItem(POLICY, target / ".guardrails" / "policy.yaml", "file"),
        InstallItem(CONTROL_CATALOG, target / ".guardrails" / "control-catalog.yaml", "file"),
        InstallItem(DOCUMENTATION_POLICY, target / ".guardrails" / "documentation.yaml", "file"),
        InstallItem(CHANGE_SCOPE_POLICY, target / ".guardrails" / "change-scope.yaml", "file"),
        InstallItem(GROUND_TRUTH_POLICY, target / ".guardrails" / "ground-truth-ai.yaml", "file"),
        InstallItem(EVALUATOR, target / ".guardrails" / "evaluate.py", "file"),
        InstallItem(SCORECARD, target / ".guardrails" / "scorecard.py", "file"),
        InstallItem(CONFIGURE, target / ".guardrails" / "configure.py", "file"),
        InstallItem(SCAN, target / ".guardrails" / "scan.py", "file"),
        InstallItem(GITHUB_EVIDENCE, target / ".guardrails" / "github_evidence.py", "file"),
        InstallItem(PRODUCER_MANIFEST, target / ".guardrails" / "producer-manifest.json", "file"),
        InstallItem(PROVIDER_CONFIG, target / ".guardrails" / "providers.yaml", "file"),
        InstallItem(GROUND_TRUTH, target / ".guardrails" / "validate_ground_truth.py", "file"),
        InstallItem(
            SKILL,
            target / ".agents" / "skills" / "prepare-safe-change",
            "directory",
        ),
    ]
    if github_actions:
        plan.append(
            InstallItem(
                GITHUB_WORKFLOW,
                target / ".github" / "workflows" / "guardrails-scorecard.yml",
                "file",
            )
        )
    for provider_id in providers or []:
        source = PROVIDER_TEMPLATES.get(provider_id)
        if source is None or not source.exists():
            raise ValueError(f"provider template is not available: {provider_id}")
        destination_name = "semgrep.yml" if provider_id == "semgrep" else f"{provider_id}.yml"
        plan.append(InstallItem(source, target / ".github" / "workflows" / destination_name, "file"))
    return plan


def install(
    target: Path,
    *,
    dry_run: bool,
    github_actions: bool = False,
    merge_existing: bool = False,
    refresh_existing: bool = False,
    providers: list[str] | None = None,
    cleanup: bool | None = None,
) -> list[InstallItem]:
    target = target.resolve()
    if not target.is_dir():
        raise ValueError(f"target is not a directory: {target}")
    reject_legacy_configuration(target)

    plan = build_plan(target, github_actions=github_actions, providers=providers)
    plan = [
        item for item in plan
        if item.source.resolve() != item.destination.resolve()
    ]
    if merge_existing and refresh_existing:
        raise ValueError("--merge-existing and --refresh-existing cannot be combined")
    should_cleanup = refresh_existing if cleanup is None else cleanup
    if should_cleanup and not refresh_existing:
        raise ValueError("cleanup is available only with --refresh-existing")
    existing = [item.destination for item in plan if item.destination.exists()]
    if existing and not merge_existing and not refresh_existing:
        paths = ", ".join(str(path) for path in existing)
        raise ValueError(f"refusing to overwrite existing paths: {paths}")
    if merge_existing:
        plan = [item for item in plan if not item.destination.exists()]
    elif refresh_existing:
        plan = apply_legacy_migrations(plan, target, github_actions=github_actions)
        selected_configuration = {
            target / ".guardrails" / "policy.yaml",
            target / ".guardrails" / "documentation.yaml",
            target / ".guardrails" / "change-scope.yaml",
            target / ".guardrails" / "ground-truth-ai.yaml",
        }
        provider_path = target / ".guardrails" / "providers.yaml"
        manifest_path = target / ".guardrails" / "producer-manifest.json"
        scorecard_workflow = target / ".github" / "workflows" / "guardrails-scorecard.yml"
        plan = [
            item for item in plan
            if not (
                item.destination in selected_configuration
                and item.destination.exists()
            )
            and not (item.destination == provider_path and item.destination.exists())
            and not (item.destination == manifest_path and item.destination.exists())
            and not (item.destination == scorecard_workflow and item.destination.exists())
            and not (
                item.source in PROVIDER_TEMPLATES.values()
                and item.destination.exists()
            )
            and not (item.kind == "directory" and item.destination.exists())
        ]
        plan.extend(legacy_cleanup_items(target) if should_cleanup else [])
    if dry_run:
        return plan

    for item in plan:
        if item.kind == "remove":
            # Unlink only. Never recursively delete consumer directories or
            # generated scorecards/evidence.
            item.destination.unlink()
            continue
        item.destination.parent.mkdir(parents=True, exist_ok=True)
        if item.kind == "directory":
            shutil.copytree(item.source, item.destination)
        elif item.kind == "migrate-text":
            text = item.source.read_text(encoding="utf-8")
            text = text.replace(".agentic-guardrails", ".guardrails")
            text = text.replace("Agentic Guardrails", "Guardrails")
            text = text.replace("Agentic Guardrail", "Guardrail")
            text = text.replace("agentic-guardrails", "guardrails")
            item.destination.write_text(text, encoding="utf-8")
        else:
            shutil.copy2(item.source, item.destination)
    if should_cleanup:
        try:
            (target / LEGACY_RUNTIME_DIR).rmdir()
        except OSError:
            # Preserve the directory when it contains consumer-owned files.
            pass
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install the guardrail evaluator and preparation skill"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--github-actions",
        action="store_true",
        help="install the aggregate pull-request guardrail scorecard workflow",
    )
    parser.add_argument(
        "--merge-existing",
        action="store_true",
        help="preserve existing files and install only missing product files",
    )
    parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help="refresh product files, preserve consumer files, and remove known legacy installer files",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="during --refresh-existing, skip known legacy installer cleanup",
    )
    parser.add_argument(
        "--provider",
        action="append",
        default=[],
        help="install a verified provider workflow template; repeatable",
    )
    args = parser.parse_args()

    try:
        plan = install(
            args.target,
            dry_run=args.dry_run,
            github_actions=args.github_actions,
            merge_existing=args.merge_existing,
            refresh_existing=args.refresh_existing,
            providers=args.provider,
            cleanup=False if args.no_cleanup else None,
        )
        verb = "Would apply" if args.dry_run else "Applied"
        print(f"{verb} guardrails:")
        for item in plan:
            action = "remove" if item.kind == "remove" else "install"
            print(f"- {action}: {item.destination}")
        return 0
    except (OSError, ValueError) as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
