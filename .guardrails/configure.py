#!/usr/bin/env python3
"""Select guardrail controls and enforcement levels for a repository policy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


MODES = ("advisory", "enforced")
OPERATIONS = ("change", "release")
DEFAULT_POLICY = Path(".guardrails/policy.yaml")
DEFAULT_CATALOG = Path(".guardrails/control-catalog.yaml")


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read JSON-compatible YAML {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def catalog_controls(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    controls = catalog.get("controls")
    if not isinstance(controls, list):
        raise ValueError("catalog must contain a controls list")
    result: dict[str, dict[str, Any]] = {}
    for control in controls:
        if not isinstance(control, dict) or not isinstance(control.get("id"), str):
            raise ValueError("every catalog control must have a string id")
        result[control["id"]] = control
    return result


def validate_policy(policy: dict[str, Any]) -> None:
    operations = policy.get("operations")
    if not isinstance(operations, dict) or not operations:
        raise ValueError("policy must contain at least one operation")
    for operation, rules in operations.items():
        if not isinstance(rules, dict):
            raise ValueError(f"policy operation {operation} must be an object")
        for key in ("required", "advisory"):
            if not isinstance(rules.get(key), list) or not all(
                isinstance(value, str) for value in rules[key]
            ):
                raise ValueError(f"policy operation {operation}.{key} must be a list of ids")
        overlap = set(rules["required"]) & set(rules["advisory"])
        if overlap:
            raise ValueError(
                f"policy operation {operation} lists controls in both modes: "
                + ", ".join(sorted(overlap))
            )


def set_mode(policy: dict[str, Any], control_id: str, mode: str, operations: list[str]) -> None:
    if mode not in MODES:
        raise ValueError(f"mode must be one of: {', '.join(MODES)}")
    for operation in operations:
        if operation not in policy["operations"]:
            raise ValueError(f"policy does not define operation: {operation}")
        rules = policy["operations"][operation]
        rules["required"] = [item for item in rules["required"] if item != control_id]
        rules["advisory"] = [item for item in rules["advisory"] if item != control_id]
        if mode == "enforced":
            rules["required"].append(control_id)
        elif mode == "advisory":
            rules["advisory"].append(control_id)


def current_mode(policy: dict[str, Any], control_id: str, operation: str) -> str:
    rules = policy["operations"].get(operation, {})
    if control_id in rules.get("required", []):
        return "enforced"
    if control_id in rules.get("advisory", []):
        return "advisory"
    return "not_activated"


def validate_provider_config(config: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> None:
    if config.get("version") != 1 or not isinstance(config.get("providers"), dict):
        raise ValueError("provider config must contain version 1 and a providers object")
    for provider_id, provider in config["providers"].items():
        if not isinstance(provider_id, str) or not isinstance(provider, dict):
            raise ValueError("provider entries must be objects")
        if not isinstance(provider.get("enabled"), bool):
            raise ValueError(f"provider {provider_id} enabled must be boolean")
        controls = provider.get("controls")
        if not isinstance(controls, dict) or not controls:
            raise ValueError(f"provider {provider_id} must define controls")
        for control_id, definition in controls.items():
            if control_id not in catalog:
                raise ValueError(f"provider {provider_id} references unknown control: {control_id}")
            if not isinstance(definition, dict):
                raise ValueError(f"provider {provider_id} control {control_id} must be an object")
            for operation in OPERATIONS:
                if definition.get(operation) not in MODES:
                    raise ValueError(
                        f"provider {provider_id} control {control_id} {operation} must be advisory or enforced"
                    )
            for field in ("check_name", "workflow"):
                if not isinstance(definition.get(field), str) or not definition[field].strip():
                    raise ValueError(f"provider {provider_id} control {control_id} requires {field}")
            if not isinstance(definition.get("wait_for"), bool):
                raise ValueError(f"provider {provider_id} control {control_id} wait_for must be boolean")


def sync_provider_configuration(
    policy: dict[str, Any], manifest: dict[str, Any], config: dict[str, Any]
) -> None:
    """Synchronize enabled providers into the existing runtime policy files."""
    producers = manifest.get("producers")
    if not isinstance(producers, list):
        raise ValueError("producer manifest must contain a producers list")
    configured_controls = {
        control_id: (provider, definition)
        for provider in config["providers"].values()
        if isinstance(provider, dict)
        for control_id, definition in provider["controls"].items()
    }
    for control_id, (provider, definition) in configured_controls.items():
        for operation in policy["operations"]:
            if operation not in OPERATIONS:
                continue
            rules = policy["operations"][operation]
            rules["required"] = [item for item in rules["required"] if item != control_id]
            rules["advisory"] = [item for item in rules["advisory"] if item != control_id]
            if provider["enabled"]:
                target_list = "required" if definition[operation] == "enforced" else "advisory"
                rules[target_list].append(control_id)
        producers[:] = [item for item in producers if item.get("control_id") != control_id]
        if provider["enabled"]:
            # The workflow/check contract is provider-owned and stays stable in
            # the manifest even while enforcement mode changes independently.
            producers.append(
                {
                    "control_id": control_id,
                    "check_name": definition["check_name"],
                    "workflow": definition["workflow"],
                    "wait_for": definition["wait_for"],
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure guardrail controls as advisory or enforced"
    )
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--providers", type=Path, default=Path(".guardrails/providers.yaml"))
    parser.add_argument("--manifest", type=Path, default=Path(".guardrails/producer-manifest.json"))
    parser.add_argument("--operation", choices=OPERATIONS, default="change")
    parser.add_argument(
        "--all-operations",
        action="store_true",
        help="apply each --set choice to every operation in the policy",
    )
    parser.add_argument(
        "--set",
        action="append",
        metavar="CONTROL=MODE",
        help="set a control to advisory or enforced; repeatable",
    )
    parser.add_argument("--enable-provider", action="append", default=[])
    parser.add_argument("--disable-provider", action="append", default=[])
    parser.add_argument(
        "--set-provider-mode",
        action="append",
        metavar="CONTROL=MODE",
        help="set a provider control to advisory or enforced in both operations",
    )
    parser.add_argument(
        "--sync-providers",
        action="store_true",
        help="synchronize .guardrails/providers.yaml into policy and producer manifest",
    )
    parser.add_argument("--list", action="store_true", help="list catalog controls and current modes")
    parser.add_argument("--dry-run", action="store_true", help="show changes without writing the policy")
    args = parser.parse_args()

    try:
        policy = load_object(args.policy)
        catalog = catalog_controls(load_object(args.catalog))
        validate_policy(policy)
        provider_config = None
        provider_changed = bool(
            args.enable_provider
            or args.disable_provider
            or args.set_provider_mode
            or args.sync_providers
        )
        if provider_changed or args.list:
            provider_config = load_object(args.providers)
            validate_provider_config(provider_config, catalog)
        operations = list(policy["operations"]) if args.all_operations else [args.operation]
        if args.list:
            if provider_config is not None:
                for provider_id, provider in provider_config["providers"].items():
                    state = "enabled" if provider["enabled"] else "disabled"
                    print(f"{state:9} {provider_id:28} {provider.get('name', provider_id)}")
            for control_id, control in catalog.items():
                mode = current_mode(policy, control_id, args.operation)
                print(
                    f"{mode:9} {control_id:28} {control.get('name', control_id)} "
                    f"[{control.get('activation', 'unknown')}]"
                )
            return 0
        for provider_id in args.enable_provider:
            if provider_id not in provider_config["providers"]:
                raise ValueError(f"unknown provider: {provider_id}")
            provider_config["providers"][provider_id]["enabled"] = True
        for provider_id in args.disable_provider:
            if provider_id not in provider_config["providers"]:
                raise ValueError(f"unknown provider: {provider_id}")
            provider_config["providers"][provider_id]["enabled"] = False
        for choice in args.set_provider_mode or []:
            if "=" not in choice:
                raise ValueError(f"invalid provider mode {choice!r}; expected CONTROL=MODE")
            control_id, mode = choice.split("=", 1)
            found = False
            for provider in provider_config["providers"].values():
                if control_id in provider["controls"]:
                    for operation in OPERATIONS:
                        provider["controls"][control_id][operation] = mode
                    found = True
            if not found:
                raise ValueError(f"unknown provider control: {control_id}")
            if mode not in MODES:
                raise ValueError(f"mode must be one of: {', '.join(MODES)}")
        if not args.set and not provider_changed:
            raise ValueError("provide --set CONTROL=MODE, a provider operation, or use --list")
        for choice in args.set or []:
            if "=" not in choice:
                raise ValueError(f"invalid selection {choice!r}; expected CONTROL=MODE")
            control_id, mode = choice.split("=", 1)
            if control_id not in catalog:
                raise ValueError(f"unknown catalog control: {control_id}")
            set_mode(policy, control_id, mode, operations)
        if provider_changed:
            manifest = load_object(args.manifest)
            sync_provider_configuration(policy, manifest, provider_config)
        validate_policy(policy)
        rendered = json.dumps(policy, indent=2) + "\n"
        if args.dry_run:
            print(rendered, end="")
        else:
            args.policy.write_text(rendered, encoding="utf-8")
            if provider_changed:
                args.providers.write_text(json.dumps(provider_config, indent=2) + "\n", encoding="utf-8")
                args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(f"Updated {args.policy}")
            for choice in args.set or []:
                print(f"- {choice} for {', '.join(operations)}")
            for provider_id in args.enable_provider:
                print(f"- enabled provider {provider_id}")
            for provider_id in args.disable_provider:
                print(f"- disabled provider {provider_id}")
        return 0
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
