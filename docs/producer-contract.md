# Producer and evidence contract

The scorecard is an aggregator, not a replacement for a build, test, scanner,
reviewer, or GitHub setting.

## One revision, many producers

Every producer result must identify the exact commit it evaluated:

```json
{
  "version": 1,
  "subject": {"type": "git-commit", "revision": "<full-sha>"},
  "checks": {
    "unit-tests": {
      "producer": "Unit Tests",
      "status": "passed",
      "evidence": ["run URL or artifact reference"]
    }
  }
}
```

`passed` and `failed` require evidence. `blocked` and `not_run` require a
reason. A workflow file, configured secret, or successful setup step is not
producer evidence.

## How aggregation works

`.guardrails/producer-manifest.json` maps each control to the check context that
produces it. The scorecard workflow calls
`tooling/github_evidence.py` to query GitHub Checks for the pull-request head
revision. It then writes that result into `.artifacts/guardrails/evidence/`
before running the deterministic scanner.

Check names must be unique in the repository. Use provider-specific names such
as `GitHub Secret Scan` when another tool may emit a generic `Secret Scan`
context.

Each producer may set `"wait_for": true` when its workflow is activated and
should complete before aggregation. The default is `true` for compatibility.
Set `"wait_for": false` for an optional or platform-managed producer that may
not create a check on every pull request. Such a check is still collected when
present, but its absence does not hold the scorecard open until timeout.

| GitHub outcome | Evidence status | Meaning |
| --- | --- | --- |
| `success`, `neutral` | `passed` | The producer completed successfully. |
| `failure` | `failed` | The producer completed and found a failure. |
| `cancelled`, `timed_out`, `action_required` | `blocked` | The producer could not provide a valid result. |
| `skipped`, missing, in progress | `not_run` | No usable result exists for this revision. |

The collector does not turn a skipped or missing check into a pass. Producer
workflows may also upload detailed JSON artifacts; those artifacts should use
the same revision-bound schema and be retained with the scorecard report.

When a repository-native producer and the GitHub collector both report the
same control, a completed result takes precedence over an external `not_run`
placeholder. Two different completed results for the same control are treated
as a contract error and fail the scan rather than being silently overwritten.
This keeps the terminal report useful when local and workflow producers are
both enabled for the same repository.
The installed scanner is refreshed with the same release so local and CI
invocations use the same reconciliation behavior.

## Consumer safety

Installing or refreshing the runtime never overwrites a consumer-owned
`.guardrails/policy.yaml` or existing GitHub workflow. Use the installer to
refresh the evaluator, collector, and catalog; it preserves an existing
producer manifest. Review workflow changes as a normal pull request in the
consuming repository. See
[Guardrails directories](../README.md#guardrails-directories) for the source
and installation boundary.

The manifest is explicit. If a repository renames a check, it must update the
manifest and the ruleset status context together.

The manifest is a connection map, not an activation switch. `wait_for` describes
workflow scheduling, not policy enforcement. Selecting a control
in `.guardrails/policy.yaml` does not create a producer, enable a GitHub
setting, or authenticate a third-party service. Configure the producer first,
verify its exact check name and revision-bound evidence, then select `advisory`
or `enforced` policy as appropriate.
