from __future__ import annotations

import importlib.util
import io
import json
import stat
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from typing import Any
from unittest import mock
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tooling" / "reconcile_scorecard_badge.py"
SPEC = importlib.util.spec_from_file_location("reconcile_scorecard_badge", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise AssertionError(f"cannot load module spec: {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


REPOSITORY = "owner/repo"
DEFAULT_BRANCH = "main"
HEAD_SHA = "a" * 40
BASE_SHA = "b" * 40


def run(run_id: int = 123, attempt: int = 2, **overrides: Any) -> dict[str, Any]:
    value = {
        "id": run_id,
        "run_attempt": attempt,
        "name": "Guardrail Scorecard",
        "path": ".github/workflows/guardrails-scorecard.yml@refs/heads/main",
        "event": "pull_request_target",
        "conclusion": "success",
        "created_at": "2026-09-08T12:00:00Z",
        "repository": {"full_name": REPOSITORY},
    }
    value.update(overrides)
    return value


def source_binding(**overrides: Any) -> dict[str, Any]:
    value = {
        "version": 1,
        "run_id": 123,
        "run_attempt": 2,
        "event": "pull_request_target",
        "repository": REPOSITORY,
        "pull_request_number": 7,
        "head_sha": HEAD_SHA,
        "base_repository": REPOSITORY,
        "base_branch": DEFAULT_BRANCH,
        "base_sha": BASE_SHA,
    }
    value.update(overrides)
    return value


def pull_request(**overrides: Any) -> dict[str, Any]:
    value = {
        "number": 7,
        "head": {"sha": HEAD_SHA},
        "base": {"ref": DEFAULT_BRANCH, "repo": {"full_name": REPOSITORY}},
    }
    value.update(overrides)
    return value


def archive(entries: list[tuple[str, bytes, int | None]]) -> bytes:
    stream = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(stream, "w") as output:
            for name, content, mode in entries:
                info = zipfile.ZipInfo(name)
                if mode is not None:
                    info.external_attr = mode << 16
                output.writestr(info, content)
    return stream.getvalue()


def valid_archive() -> bytes:
    card = {
        "version": 2,
        "operation": "change",
        "status": "GREEN",
        "decision": "allow",
        "subject": {"type": "git-commit", "revision": HEAD_SHA},
        "enforced": {"passed": 2, "total": 2},
        "advisory": {"passed": 1, "total": 1},
    }
    return archive(
        [
            (
                "scorecard-20260908-120000Z.json",
                json.dumps(card).encode(),
                stat.S_IFREG | 0o644,
            ),
            ("scorecard-20260908-120000Z.md", b"report", stat.S_IFREG | 0o644),
            (
                "source.json",
                json.dumps(source_binding()).encode(),
                stat.S_IFREG | 0o644,
            ),
        ]
    )


class ReconcilerTests(unittest.TestCase):
    def test_workflow_path_allowlist_is_exact(self) -> None:
        accepted = (
            ".github/workflows/guardrails-scorecard.yml",
            ".github/workflows/guardrails-scorecard.yml@main",
            ".github/workflows/guardrails-scorecard.yml@refs/heads/main",
        )
        for value in accepted:
            self.assertTrue(MODULE.workflow_path_allowed(value, DEFAULT_BRANCH))
        for value in (
            ".github/workflows/guardrails-scorecard.yml@feature",
            ".github/workflows/guardrails-scorecard.yml@refs/pull/7/merge",
            ".github/workflows/guardrails-scorecard.yml@refs/heads/main/evil",
            ".github/workflows/other.yml",
            None,
        ):
            self.assertFalse(MODULE.workflow_path_allowed(value, DEFAULT_BRANCH))

    def test_run_and_source_binding_require_exact_current_pr_state(self) -> None:
        normalized = MODULE.validate_run(run(), REPOSITORY, DEFAULT_BRANCH)
        MODULE.validate_source_binding(
            source_binding(),
            normalized,
            pull_request(),
            REPOSITORY,
            DEFAULT_BRANCH,
            HEAD_SHA,
            lambda revision: revision == BASE_SHA,
        )
        invalid_runs = (
            run(name="Other"),
            run(path=".github/workflows/guardrails-scorecard.yml@feature"),
            run(event="push"),
            run(conclusion="cancelled"),
            run(repository={"full_name": "other/repo"}),
            run(run_attempt=True),
        )
        for invalid in invalid_runs:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                MODULE.validate_run(invalid, REPOSITORY, DEFAULT_BRANCH)
        invalid_sources = (
            source_binding(run_attempt=1),
            source_binding(repository="other/repo"),
            source_binding(head_sha="c" * 40),
            source_binding(base_repository="other/repo"),
            source_binding(base_branch="develop"),
            source_binding(base_sha="short"),
        )
        for invalid in invalid_sources:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                MODULE.validate_source_binding(
                    invalid,
                    normalized,
                    pull_request(),
                    REPOSITORY,
                    DEFAULT_BRANCH,
                    HEAD_SHA,
                    lambda _: True,
                )

    def test_archive_extraction_is_bounded_and_attempt_specific(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            extracted = MODULE.extract_artifact(valid_archive(), Path(directory))
            self.assertEqual(
                {path.name for path in extracted.iterdir()},
                {
                    "scorecard-20260908-120000Z.json",
                    "scorecard-20260908-120000Z.md",
                    "source.json",
                },
            )
        unsafe_archives = (
            archive([("../source.json", b"{}", stat.S_IFREG | 0o644)]),
            archive([("nested/source.json", b"{}", stat.S_IFREG | 0o644)]),
            archive([("source.json", b"{}", stat.S_IFLNK | 0o777)]),
            archive(
                [
                    (
                        "source.json",
                        b"x" * (MODULE.MAX_MEMBER_BYTES + 1),
                        stat.S_IFREG | 0o644,
                    )
                ]
            ),
            archive(
                [
                    ("source.json", b"{}", stat.S_IFREG | 0o644),
                    ("source.json", b"{}", stat.S_IFREG | 0o644),
                ]
            ),
        )
        for payload in unsafe_archives:
            with (
                self.subTest(size=len(payload)),
                tempfile.TemporaryDirectory() as directory,
            ):
                with self.assertRaises(ValueError):
                    MODULE.extract_artifact(payload, Path(directory))

    def test_artifact_download_drops_authorization_after_redirect(self) -> None:
        requests = []

        class RedirectingOpener:
            def open(self, request: Any, timeout: int) -> None:
                requests.append(request)
                raise HTTPError(
                    request.full_url,
                    302,
                    "Found",
                    {"Location": "https://signed.example/archive.zip"},
                    None,
                )

        class Response:
            def __enter__(self) -> "Response":
                return self

            def __exit__(self, *args: Any) -> None:
                return None

            def read(self, amount: int) -> bytes:
                return b"zip"

        def unsigned_open(request: Any, timeout: int) -> Response:
            requests.append(request)
            return Response()

        payload = MODULE.download_artifact(
            "https://api.github.com/repos/owner/repo/actions/artifacts/9/zip",
            "secret-token",
            opener=RedirectingOpener(),
            unsigned_open=unsigned_open,
        )
        self.assertEqual(payload, b"zip")
        self.assertIn("Authorization", requests[0].headers)
        self.assertNotIn("Authorization", requests[1].headers)
        self.assertEqual(requests[1].full_url, "https://signed.example/archive.zip")

    def test_candidate_selection_crosses_more_than_twenty_rejections(self) -> None:
        runs = [run(run_id=200 - index, attempt=1) for index in range(25)]
        runs.append(run(run_id=175, attempt=3, created_at="2026-09-07T12:00:00Z"))

        def validate(candidate: dict[str, Any]) -> dict[str, Any]:
            if candidate["id"] != 175:
                raise MODULE.CandidateRejected("missing or malformed artifact")
            return {"run": candidate}

        selected, rejected = MODULE.select_candidate(runs, None, validate)
        self.assertEqual(selected["run"]["id"], 175)
        self.assertEqual(len(rejected), 25)

    def test_candidate_selection_is_monotonic_and_attempt_aware(self) -> None:
        published = ("2026-09-08T12:00:00Z", 123, 2)
        same_attempt = run()
        older_attempt = run(attempt=1)
        selected, _ = MODULE.select_candidate(
            [same_attempt, older_attempt],
            published,
            lambda candidate: {"run": candidate},
        )
        self.assertEqual(selected["run"]["run_attempt"], 2)
        with self.assertRaises(ValueError):
            MODULE.select_candidate(
                [older_attempt], published, lambda candidate: {"run": candidate}
            )

    def test_published_scorecard_metadata_is_validated_before_use(self) -> None:
        document = {
            "version": 1,
            "operation": "change",
            "repository": REPOSITORY,
            "status": "GREEN",
            "decision": "allow",
            "passed": 3,
            "total": 3,
            "enforced": {"passed": 2, "total": 2},
            "advisory": {"passed": 1, "total": 1},
            "subject_digest": "sha256:" + "c" * 64,
            "source_run_created_at": "2026-09-08T12:00:00Z",
            "source_run_id": 123,
            "source_run_attempt": 2,
        }
        self.assertEqual(
            MODULE.validate_published_scorecard(document, REPOSITORY), document
        )
        for field, value in (
            ("version", 2),
            ("repository", "other/repo"),
            ("status", []),
            ("passed", True),
            ("total", 0),
            ("advisory", {"passed": 0, "total": 1}),
            ("subject_digest", HEAD_SHA),
        ):
            invalid = {**document, field: value}
            with self.subTest(field=field), self.assertRaises(ValueError):
                MODULE.validate_published_scorecard(invalid, REPOSITORY)

    def test_completed_run_pagination_is_lazy_and_crosses_a_full_page(self) -> None:
        class Client:
            def __init__(self) -> None:
                self.pages: list[int] = []

            def json(self, url: str) -> dict[str, Any]:
                page = int(url.rsplit("page=", 1)[1])
                self.pages.append(page)
                if page == 1:
                    return {
                        "workflow_runs": [
                            run(run_id=300 - index, attempt=1)
                            for index in range(MODULE.RUNS_PER_PAGE)
                        ]
                    }
                return {"workflow_runs": [run(run_id=200, attempt=1)]}

        client = Client()
        candidates = MODULE.completed_runs(client, REPOSITORY)

        selected, rejected = MODULE.select_candidate(
            candidates,
            None,
            lambda candidate: (
                {"run": candidate}
                if candidate["id"] == 200
                else (_ for _ in ()).throw(MODULE.CandidateRejected("rejected"))
            ),
        )

        self.assertEqual(selected["run"]["id"], 200)
        self.assertEqual(len(rejected), MODULE.RUNS_PER_PAGE)
        self.assertEqual(client.pages, [1, 2])

    def test_api_failures_are_not_downgraded_to_rejected_candidates(self) -> None:
        failure = HTTPError("https://api.github.com", 500, "error", {}, None)
        with self.assertRaises(HTTPError):
            MODULE.select_candidate(
                [run()], None, lambda _: (_ for _ in ()).throw(failure)
            )

    def test_artifact_name_is_exact_for_run_attempt(self) -> None:
        listing = {
            "total_count": 3,
            "artifacts": [
                {"id": 1, "name": "guardrail-scorecard-123-1", "expired": False},
                {"id": 2, "name": "guardrail-scorecard-123-2", "expired": False},
                {"id": 3, "name": "guardrail-scorecard-123-2-extra", "expired": False},
            ],
        }
        self.assertEqual(MODULE.exact_artifact(listing, run())["id"], 2)
        duplicate = {
            **listing,
            "artifacts": [
                *listing["artifacts"],
                {"id": 4, "name": "guardrail-scorecard-123-2", "expired": False},
            ],
        }
        with self.assertRaises(ValueError):
            MODULE.exact_artifact(duplicate, run())


if __name__ == "__main__":
    unittest.main()
