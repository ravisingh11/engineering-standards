# Quick start

Install the shared guardrails into an application repository, run the local
scorecard, then open a pull request to exercise the GitHub checks.

## Scan this repository itself

From the root of this standards repository, no installation is needed:

```sh
python3 tooling/scan_repository.py --all-catalog-controls
```

The scanner uses the checked-in `.guardrails/` configuration. If those files
are absent in a standards source checkout, it falls back to
`guardrails/baseline.yaml` and `policies/control-catalog.yaml`. When pointed at
an installed application repository, it uses that repository's `.guardrails/`
files. See [Guardrails directories](../README.md#guardrails-directories) for
the source, installation, and AI-owned configuration boundary.

## 1. Install

Clone this repository once beside the application repository:

```sh
git clone https://github.com/ravisingh11/engineering-standards.git \
  ../engineering-standards
python3 ../engineering-standards/tooling/install.py \
  --target . --github-actions
```

Use `--refresh-existing` when updating an installation. Follow the
[refresh steps](#updating-an-installation) so the installer can report any
required configuration moves before it plans the refresh.

## 2. Choose controls

The installer creates `.guardrails/policy.yaml`, the repository validation
policies, and `.guardrails/providers.yaml`. List controls before changing
anything:

```sh
python3 .guardrails/configure.py --list
```

Keep controls advisory while their producers are being connected:

```sh
python3 .guardrails/configure.py \
  --set snyk-code=advisory \
  --set snyk-open-source=advisory
```

Enable a supported provider with its repository-owned workflow template:

```sh
python3 ../engineering-standards/tooling/install.py \
  --target . --provider snyk --refresh-existing
python3 .guardrails/configure.py \
  --enable-provider snyk --sync-providers
```

Install or refresh the provider workflow first, then synchronize the provider
configuration. The synchronization updates the producer manifest; refreshing
the shared runtime afterward would replace that manifest with the default one.

Add provider credentials only as GitHub Actions secrets. Never put tokens in
the repository or in a workflow file. Use the
[secrets and variables checklist](control-setup.md#secrets-and-variables-checklist)
for exact names, minimum permissions, secure `gh` commands, and platform
settings. Create credentials only for providers you activate.

## 3. Run locally

Run the repository's real tests and validators, then render a scorecard:

```sh
python3 .guardrails/scan.py --all-catalog-controls
```

The command prints the report and writes:

```text
.artifacts/guardrails/evidence.json
.artifacts/guardrails/scorecard-YYYYMMDD-HHMMSSZ.md
```

`GREEN` means a real producer passed for the exact revision. `ORANGE` means
the selected control has no passing result yet. `GRAY` means it is not
selected. `RED` means the producer failed or required evidence is missing.
Advisory findings are reported without blocking; enforced findings can block.

## 4. Run in GitHub

Commit the installed files and open a pull request. Producer workflows run in
parallel, and the scorecard collects results for the exact pull-request head.
The Actions job summary, artifact, and—when GitHub permits write access—the PR
comment contain the detailed report.

Only add a check to branch protection after it has produced reliable results
on representative pull requests. External services such as SonarQube, FOSSA,
Snyk, Semgrep, and AI reviewers require their own credentials and adapters;
the shared installer does not pretend to configure them automatically.

## Updating an installation

```sh
git -C ../engineering-standards pull --ff-only
python3 ../engineering-standards/tooling/install.py \
  --target . --github-actions --refresh-existing --dry-run
```

If the dry run rejects legacy Guardrails configuration, create the destination
directory first:

```sh
mkdir -p .guardrails
```

Then execute every complete `git mv` command it prints, review relative schema
references in the moved files, and rerun `--dry-run`. Run only the printed
commands for files the repository has. The installer owns the exact path map
and does not move or delete rejected configuration automatically.

After the dry run succeeds, rerun the installer command without `--dry-run`.
Review the diff, run the local scan, and commit the refresh through the normal
application pull request.

Refresh migrates installations that still use `.agentic-guardrails/` or
`agentic-guardrails-scorecard.yml` to `.guardrails/` and
`guardrails-scorecard.yml`. This known runtime cleanup is separate from the
configuration moves above.
