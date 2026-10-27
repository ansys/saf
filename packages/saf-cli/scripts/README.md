<!--
Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# Solution-template lockfile maintenance

[upgrade_solution_template_poetry_lock.py](upgrade_solution_template_poetry_lock.py)
runs locally with `uv`.

## Prerequisites

Install `uv` and, for Dependabot mode, the GitHub CLI. Authenticate with
`gh auth login` and check access with `gh auth status`. Your credentials need
permission to read the repository's Dependabot alerts; fine-grained credentials
require **Dependabot alerts: read**. Access failures are errors, not empty
alert lists. Configure private registry credentials locally, never in source.

## Commands

From the repository root on Windows, preview open alerts and planned updates:

```powershell
uv run --script packages\saf-cli\scripts\upgrade_solution_template_poetry_lock.py --dependabot --dry-run
```

Apply targeted transitive updates for those alerts:

```powershell
uv run --script packages\saf-cli\scripts\upgrade_solution_template_poetry_lock.py --dependabot
```

Restrict alert processing to a particular package:

```powershell
uv run --script packages\saf-cli\scripts\upgrade_solution_template_poetry_lock.py --dependabot --packages nbconvert
```

The existing manual mode is also supported:

```powershell
uv run --script packages\saf-cli\scripts\upgrade_solution_template_poetry_lock.py --packages nbconvert
```

From `packages\saf-cli`, use `scripts\upgrade_solution_template_poetry_lock.py`
instead. Use native path separators on other operating systems.
`--repository owner/repo` selects an alternative GitHub repository for alerts.

## Behavior and verification

- Retrieves all pages of open Python Dependabot alerts and filters their exact
  manifest paths to the solution template's `lock_files` directory.
- Uses current-checkout templates through an editable local CLI dependency.
- In Dependabot mode, skips already-safe packages and reports direct dependencies,
  unsupported variants, and advisories without a patched version as blocked.
  All Poetry dependency groups are considered when identifying direct dependencies.
- Targets eligible packages per UI variant, using `poetry update --lock`, and
  checks every locked version against each advisory's vulnerable version range.
- Validates staged lockfiles in temporary generated solutions with
  `poetry check --lock` before copying them to the repository. No solution
  dependencies are installed. Temporary solutions are cleaned up automatically.
- Does not copy any staged lockfiles if a command fails or a targeted alert is
  still vulnerable. Blocked alerts are reported with a nonzero exit status;
  independent eligible updates can still be saved when validation succeeds.
- Saves alert URLs, advisories, before/after versions, and outcomes to
  `dist/solution-template-dependabot-report.md` at the repository root, in UTF-8.
  Each Dependabot inventory run that successfully fetches alerts replaces the
  previous report, including dry runs, runs with no matching alerts, and Poetry
  resolution or validation failures. Failed remediation statuses are recorded;
  repository lockfiles remain unchanged on command failure. Alert retrieval
  failures do not replace the report. The terminal shows the report path,
  progress, and errors rather than the full alert results. GitHub alerts remain
  open until the default branch is updated and rescanned.

Dry runs generate temporary manifests to classify dependencies but do not run
Poetry or write repository lockfiles; they still save the Markdown report.
Review `git diff` before committing; the
script does not commit, push, dismiss alerts, or open pull requests.

## Focused tests

From the repository root:

```powershell
uv run --script packages\saf-cli\scripts\test_upgrade_solution_template_poetry_lock.py
```

The test file uses pytest fixtures and `monkeypatch` and declares its own
dependencies in inline script metadata. Extra pytest options such as `-q` or
`-k dry_run` can be passed after the script path. From
`packages\saf-cli`, use `scripts\test_upgrade_solution_template_poetry_lock.py`.
These tests mock GitHub and dependency resolution; they do not require alert
permissions or modify repository lockfiles.
