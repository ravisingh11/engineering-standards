#!/usr/bin/env python3
# Guardrails v2 installer-owned runtime.
"""Validate a Guardrails scorecard and render a bounded public status site."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


VALID_STATUSES = {"GREEN": "#2da44e", "ORANGE": "#bf8700", "RED": "#cf222e"}
VALID_DECISIONS = {"allow", "block"}
MAX_MEMBER_BYTES = 64_000
MAX_SOURCE_BYTES = 1_000_000
REVISION_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
RFC3339_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\Z"
)


def _integer(value: Any, field: str, *, positive: bool = False) -> int:
    if type(value) is not int:  # bool is intentionally excluded
        raise ValueError(f"{field} must be an integer")
    if value < (1 if positive else 0):
        qualifier = "positive" if positive else "nonnegative"
        raise ValueError(f"{field} must be {qualifier}")
    return value


def _timestamp(value: str, field: str) -> str:
    if not isinstance(value, str) or not RFC3339_PATTERN.fullmatch(value):
        raise ValueError(f"{field} must be an RFC 3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError(f"{field} must include a timezone")
        normalized = parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError) as error:
        raise ValueError(f"{field} must be an RFC 3339 timestamp") from error
    rendered = normalized.isoformat(
        timespec="microseconds" if normalized.microsecond else "seconds"
    )
    return rendered.replace("+00:00", "Z")


def _repository(value: str) -> tuple[str, str]:
    if not isinstance(value, str) or not REPOSITORY_PATTERN.fullmatch(value):
        raise ValueError("repository must use OWNER/REPOSITORY format")
    owner, name = value.split("/", 1)
    if owner in {".", ".."} or name in {".", ".."}:
        raise ValueError("repository must use OWNER/REPOSITORY format")
    return owner, name


def pages_base_url(repository: str) -> str:
    owner, name = _repository(repository)
    owner_domain = owner.lower()
    if name.lower() == f"{owner_domain}.github.io":
        return f"https://{owner_domain}.github.io/"
    return f"https://{owner_domain}.github.io/{name}/"


def _validate_run_url(
    repository: str, run_id: int, run_attempt: int, run_url: str
) -> str:
    _repository(repository)
    if not isinstance(run_url, str):
        raise ValueError("run_url must be an HTTPS GitHub Actions run-attempt URL")
    parsed = urlsplit(run_url)
    expected_path = f"/{repository}/actions/runs/{run_id}/attempts/{run_attempt}"
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != expected_path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("run_url must match the repository, run ID, and run attempt")
    return run_url


def _bounded_source(source_dir: Path) -> tuple[Path, Path]:
    if source_dir.is_symlink() or not source_dir.is_dir():
        raise ValueError("source directory must be a real directory")
    entries = list(source_dir.iterdir())
    total_bytes = 0
    for entry in entries:
        if entry.is_symlink() or not entry.is_file():
            raise ValueError(
                f"source contains a nested, special, or symlinked entry: {entry.name}"
            )
        size = entry.stat().st_size
        if size > MAX_MEMBER_BYTES:
            raise ValueError(
                f"source member exceeds {MAX_MEMBER_BYTES} bytes: {entry.name}"
            )
        total_bytes += size
        if total_bytes > MAX_SOURCE_BYTES:
            raise ValueError(f"source exceeds {MAX_SOURCE_BYTES} aggregate bytes")
    json_files = sorted(source_dir.glob("scorecard-*.json"))
    if len(json_files) != 1:
        raise ValueError("source must contain exactly one scorecard JSON file")
    json_path = json_files[0]
    markdown_path = json_path.with_suffix(".md")
    if not markdown_path.is_file() or markdown_path.is_symlink():
        raise ValueError("scorecard JSON must have one paired Markdown report")
    if {entry.name for entry in entries} != {json_path.name, markdown_path.name}:
        raise ValueError(
            "source must contain only the paired scorecard JSON and Markdown files"
        )
    return json_path, markdown_path


def _counts(document: dict[str, Any], mode: str) -> dict[str, int]:
    value = document.get(mode)
    if not isinstance(value, dict):
        raise ValueError(f"{mode} must be an object")
    passed = _integer(value.get("passed"), f"{mode}.passed")
    total = _integer(value.get("total"), f"{mode}.total")
    if passed > total:
        raise ValueError(f"{mode}.passed cannot exceed {mode}.total")
    return {"passed": passed, "total": total}


def _validated_scorecard(source_dir: Path) -> dict[str, Any]:
    json_path, _ = _bounded_source(source_dir)
    try:
        document = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError(f"invalid scorecard JSON: {error}") from error
    if not isinstance(document, dict):
        raise ValueError("scorecard JSON must contain an object")
    if document.get("version") != 2 or type(document.get("version")) is not int:
        raise ValueError("scorecard version must be 2")
    if document.get("operation") != "change":
        raise ValueError("scorecard operation must be change")
    status = document.get("status")
    decision = document.get("decision")
    if not isinstance(status, str) or status not in VALID_STATUSES:
        raise ValueError("scorecard status must be GREEN, ORANGE, or RED")
    if not isinstance(decision, str) or decision not in VALID_DECISIONS:
        raise ValueError("scorecard decision must be allow or block")
    subject = document.get("subject")
    if not isinstance(subject, dict) or subject.get("type") != "git-commit":
        raise ValueError("scorecard subject must be a git commit")
    revision = subject.get("revision")
    if not isinstance(revision, str) or not REVISION_PATTERN.fullmatch(revision):
        raise ValueError(
            "scorecard revision must be an exact lowercase 40-character SHA"
        )
    enforced = _counts(document, "enforced")
    advisory = _counts(document, "advisory")
    passed = enforced["passed"] + advisory["passed"]
    total = enforced["total"] + advisory["total"]
    if total == 0:
        raise ValueError("scorecard must contain at least one active control")
    enforced_miss = enforced["passed"] < enforced["total"]
    advisory_miss = advisory["passed"] < advisory["total"]
    expected_status = "RED" if enforced_miss else "ORANGE" if advisory_miss else "GREEN"
    expected_decision = "block" if expected_status == "RED" else "allow"
    if status != expected_status or decision != expected_decision:
        raise ValueError(
            "scorecard status and decision are inconsistent with aggregate counts"
        )
    return {
        "status": status,
        "decision": decision,
        "enforced": enforced,
        "advisory": advisory,
        "passed": passed,
        "total": total,
        "subject_revision": revision,
    }


def inspect_scorecard(source_dir: Path) -> dict[str, object]:
    """Return the normalized trusted fields needed to validate a source artifact."""
    return dict(_validated_scorecard(Path(source_dir)))


def _write_atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _public_metadata(
    inspected: dict[str, Any],
    repository: str,
    run_id: int,
    run_attempt: int,
    run_url: str,
    source_run_created_at: str,
    expected_revision: str,
) -> dict[str, Any]:
    published_at = (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    passed = inspected["passed"]
    total = inspected["total"]
    return {
        "version": 1,
        "operation": "change",
        "label": "Latest PR Scorecard",
        "status": inspected["status"],
        "decision": inspected["decision"],
        "message": f"{inspected['status']} {passed}/{total}",
        "repository": repository,
        "source_run_id": run_id,
        "source_run_attempt": run_attempt,
        "source_run_url": run_url,
        "source_run_created_at": source_run_created_at,
        "published_at": published_at,
        "subject_digest": f"sha256:{hashlib.sha256(expected_revision.encode()).hexdigest()}",
        "passed": passed,
        "total": total,
        "enforced": inspected["enforced"],
        "advisory": inspected["advisory"],
        "pages_url": pages_base_url(repository),
    }


def _svg(metadata: dict[str, Any]) -> str:
    label = str(metadata["label"])
    message = str(metadata["message"])
    label_width = 128
    message_width = max(88, len(message) * 8 + 20)
    total_width = label_width + message_width
    description = html.escape(
        json.dumps(metadata, sort_keys=True, separators=(",", ":")), quote=True
    )
    safe_label = html.escape(label)
    safe_message = html.escape(message)
    color = VALID_STATUSES[str(metadata["status"])]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" aria-label="{safe_label}: {safe_message}">
  <title>{safe_label}: {safe_message}</title>
  <desc>{description}</desc>
  <linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>
  <clipPath id="r"><rect width="{total_width}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)"><rect width="{label_width}" height="20" fill="#555"/><rect x="{label_width}" width="{message_width}" height="20" fill="{color}"/><rect width="{total_width}" height="20" fill="url(#s)"/></g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11"><text x="{label_width / 2}" y="15" fill="#010101" fill-opacity=".3">{safe_label}</text><text x="{label_width / 2}" y="14">{safe_label}</text><text x="{label_width + message_width / 2}" y="15" fill="#010101" fill-opacity=".3">{safe_message}</text><text x="{label_width + message_width / 2}" y="14">{safe_message}</text></g>
</svg>
"""


def _markdown(metadata: dict[str, Any]) -> str:
    return f"""# Latest PR Scorecard

![{metadata["message"]}](guardrails-badge.svg)

| Field | Value |
| --- | --- |
| Repository | {metadata["repository"]} |
| Operation | {metadata["operation"]} |
| Status | {metadata["status"]} |
| Active controls | {metadata["passed"]}/{metadata["total"]} passed |
| Enforced | {metadata["enforced"]["passed"]}/{metadata["enforced"]["total"]} passed |
| Advisory | {metadata["advisory"]["passed"]}/{metadata["advisory"]["total"]} passed |
| Source run | [{metadata["source_run_id"]} attempt {metadata["source_run_attempt"]}]({metadata["source_run_url"]}) |
| Source created | {metadata["source_run_created_at"]} |
| Published | {metadata["published_at"]} |
| Subject digest | {metadata["subject_digest"]} |
"""


def _html(metadata: dict[str, Any]) -> str:
    safe = {key: html.escape(str(value), quote=True) for key, value in metadata.items()}
    enforced = metadata["enforced"]
    advisory = metadata["advisory"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Latest PR Scorecard</title></head>
<body><main><h1>Latest PR Scorecard</h1><img src="guardrails-badge.svg" alt="{safe["message"]}"><dl>
<dt>Repository</dt><dd>{safe["repository"]}</dd><dt>Operation</dt><dd>{safe["operation"]}</dd><dt>Status</dt><dd>{safe["status"]}</dd>
<dt>Active controls</dt><dd>{safe["passed"]}/{safe["total"]} passed</dd>
<dt>Enforced</dt><dd>{enforced["passed"]}/{enforced["total"]} passed</dd>
<dt>Advisory</dt><dd>{advisory["passed"]}/{advisory["total"]} passed</dd>
<dt>Source run</dt><dd><a href="{safe["source_run_url"]}">{safe["source_run_id"]} attempt {safe["source_run_attempt"]}</a></dd>
<dt>Source created</dt><dd>{safe["source_run_created_at"]}</dd><dt>Published</dt><dd>{safe["published_at"]}</dd>
<dt>Subject digest</dt><dd>{safe["subject_digest"]}</dd></dl></main></body></html>
"""


def _replace_directory(temporary: Path, output_dir: Path) -> None:
    if output_dir.is_symlink():
        raise OSError("output directory cannot be a symlink")
    if output_dir.exists() and not output_dir.is_dir():
        raise OSError("output path must be a directory")
    backup: Path | None = None
    if output_dir.exists():
        backup = (
            output_dir.parent
            / f".{output_dir.name}.backup-{next(tempfile._get_candidate_names())}"
        )
        os.replace(output_dir, backup)
    try:
        os.replace(temporary, output_dir)
    except Exception:
        if backup is not None and not output_dir.exists():
            os.replace(backup, output_dir)
        raise
    if backup is not None:
        try:
            shutil.rmtree(backup)
        except OSError:
            # The second rename is the publication commit point. Cleanup must
            # never turn a successfully installed output into a failed run.
            pass


def render_badge(
    source_dir: Path,
    output_dir: Path,
    repository: str,
    run_id: int,
    run_attempt: int,
    run_url: str,
    source_run_created_at: str,
    expected_revision: str,
) -> dict[str, object]:
    """Render a validated scorecard into a bounded, static public projection."""
    inspected = _validated_scorecard(Path(source_dir))
    _repository(repository)
    run_id = _integer(run_id, "run_id", positive=True)
    run_attempt = _integer(run_attempt, "run_attempt", positive=True)
    run_url = _validate_run_url(repository, run_id, run_attempt, run_url)
    source_run_created_at = _timestamp(source_run_created_at, "source_run_created_at")
    if not isinstance(expected_revision, str) or not REVISION_PATTERN.fullmatch(
        expected_revision
    ):
        raise ValueError(
            "expected_revision must be an exact lowercase 40-character SHA"
        )
    if inspected["subject_revision"] != expected_revision:
        raise ValueError("scorecard revision does not match expected revision")

    output_dir = Path(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=output_dir.parent)
    )
    try:
        metadata = _public_metadata(
            inspected,
            repository,
            run_id,
            run_attempt,
            run_url,
            source_run_created_at,
            expected_revision,
        )
        (temporary / "guardrails-badge.svg").write_text(
            _svg(metadata), encoding="utf-8"
        )
        (temporary / "scorecard.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (temporary / "scorecard.md").write_text(_markdown(metadata), encoding="utf-8")
        (temporary / "index.html").write_text(_html(metadata), encoding="utf-8")
        _replace_directory(temporary, output_dir)
        return metadata
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a bounded public Guardrails scorecard badge"
    )
    parser.add_argument("--source-dir", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect-output", type=Path)
    mode.add_argument("--output-dir", type=Path)
    parser.add_argument("--repository")
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--run-attempt", type=int)
    parser.add_argument("--run-url")
    parser.add_argument("--source-run-created-at")
    parser.add_argument("--expected-revision")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.inspect_output is not None:
            inspected = inspect_scorecard(args.source_dir)
            _write_atomic_text(
                args.inspect_output,
                json.dumps(inspected, indent=2, sort_keys=True) + "\n",
            )
            return 0
        required = {
            "repository": args.repository,
            "run_id": args.run_id,
            "run_attempt": args.run_attempt,
            "run_url": args.run_url,
            "source_run_created_at": args.source_run_created_at,
            "expected_revision": args.expected_revision,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise ValueError(f"rendering requires: {', '.join(missing)}")
        metadata = render_badge(args.source_dir, args.output_dir, **required)
        print(
            f"Published badge input: {metadata['status']} {metadata['passed']}/{metadata['total']}"
        )
        return 0
    except (UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"ERROR runtime: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
