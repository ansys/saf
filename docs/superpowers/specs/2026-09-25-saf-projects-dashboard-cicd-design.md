# saf-projects-dashboard — CI/CD onboarding into the SAF monorepo

**Date:** 2026-09-25
**Issue:** #80 — enable CI/CD actions for the saf-projects-dashboard package
**Branch:** `chore/80-enable-cicd-actions-for-saf-projects-dashboard-package`

## Problem

`packages/saf-projects-dashboard` was copied into the monorepo (commits `db21027`, `b43fe89`,
`ee8fab1`) but is registered in **none** of the CI/CD configuration. It has no matrix entry, no
test-groups definition, no change filter, no label, and no certification slot. Nothing in the
monorepo builds, tests, or releases it.

The standalone repository at `ansys/saf-projects-dashboard` carries four workflows — `build.yml`,
`certification.yml`, `ci_cd_pr.yml`, `ci_cd_release.yml` — whose coverage must be preserved.

Two things make this package different from every other package in the monorepo:

1. **It needs Node.** The wheel's payload is a webpack bundle plus Python component wrappers
   generated from TypeScript. It has 12 Jest suites under `src/ts/__tests__/`. A grep of
   `.github/` and `.moon/` for `setup-node`, `npm ci`, `.nvmrc`, and `package.json` returns
   zero hits — no monorepo package has ever needed Node in CI.
2. **Its documentation was not migrated.** The standalone has a 40-file Sphinx site at
   `doc/source/`; `packages/saf-projects-dashboard/doc/` does not exist.

## Approach

Onboard the package as a **Poetry** package by registering its name in the monorepo's
matrix-driven CI, and add **one new reusable workflow** (`_js.yml`) for the Node work.

The monorepo has exactly one `build`, one `certification`, and one `release` workflow, shared by
all packages and fanned out over matrices produced by
`.github/actions/ci-cd-job-matrices/ci_cd_job_matrices.py`. Onboarding is therefore
*registration*, not *duplication*: no per-package copies of the standalone's four files.

### Decisions taken

| Decision | Choice | Rationale |
| --- | --- | --- |
| Dependency manager | **Poetry**, not Moon/uv | Smallest diff to green CI. Moon conversion is a separate follow-up, matching how `saf-iam-oidc` (#139) and `saf-product-configuration` (#144) were each done as standalone PRs. Bundling dependency-manager conversion with first-ever Node support in one PR is two risky changes at once. |
| Node location | **New `_js.yml` reusable workflow** | `_test.yml` is 22 KB of pytest orchestration (runner labels, HPS/Visor install, Minerva secrets, test-report upload) that Jest does not fit. A separate workflow gated on an empty matrix has zero blast radius on the 12 packages that call the shared workflows. |
| Wheel build | **Trust the committed bundle + freshness gate** | `src/ansys_saf_projects_dashboard/*.js` and the generated `*.py` wrappers are tracked in git, so `_build.yml` needs no change. A `git diff --exit-code` after `npm run build` gives the same guarantee as rebuilding, without making every wheel build depend on a clean `npm ci`. |
| Documentation | **Deferred** | `doc/source` was never migrated. This change stays purely CI/CD; doc migration + `_doc.yml` wiring is a follow-up issue. |
| Release target | **Public PyPI via OIDC trusted publishing** | Monorepo convention. The standalone published to the ansys-solutions private feed; diverging for one package would mean a bespoke publish job. |
| Python test matrix | **Monorepo convention: single `vars.PYTHON_VERSION`** | The tests-group JSON schema has no `python-version` key; every package already accepts this. The dashboard gains Windows runners it never had, and certification's `build-wheel` still sweeps 3.11–3.14. |

## Architecture

### Data flow

```text
PR event
  └─> ci_cd_pr.yml : ci-cd-config job
        └─> .github/actions/ci-cd-job-matrices (composite)
              ├─ dorny/paths-filter  <- .github/changes_pr_filters.yaml
              └─ ci_cd_job_matrices.py
                    ├─ packages_matrix        -> vulnerabilities, licenses, sbom,
                    │                            build-wheel, check-wheel, compatibility
                    ├─ code_style_matrix      -> code-style
                    ├─ tests_matrix           -> run-tests (_test.yml)
                    ├─ moon_packages_matrix   -> use-moon switches  (dashboard absent)
                    └─ js_packages_matrix     -> js-checks (_js.yml)   [NEW]
```

`saf-projects-dashboard` appears in `packages_matrix`, `code_style_matrix`, `tests_matrix`, and
the new `js_packages_matrix`. It is deliberately absent from `moon_packages_matrix`.

### Component boundaries

- **`ci_cd_job_matrices.py`** — pure function from "list of changed filter names" to "job
  matrices". Testable in isolation; already has a dedicated test suite run in CI.
- **`_js.yml`** — self-contained Node concern. Takes `library-name` and `python-version`. Knows
  nothing about pytest, Moon, or release flow. Consumers: `ci_cd_pr.yml`, `certification.yml`.
- **`_build.yml` / `_test.yml`** — unchanged. Their contract with all 12 existing packages is
  untouched.

## Changes

### 1. Matrix registration

**`.github/actions/ci-cd-job-matrices/ci_cd_job_matrices.py`**

- Add `"saf-projects-dashboard"` to `SAF_PACKAGES` (after `"saf-product-manager"`, keeping the
  list alphabetical).
- Add `"saf-projects-dashboard": "--with tests,style --all-extras"` to
  `CODE_STYLE_POETRY_ARGS`. **Required:** the package's `pre-commit` dependency lives in the
  `style` group, so the default `--with tests --all-extras` would leave `pre-commit` uninstalled
  and the `code-style` job would fail. This mirrors `dash-super-components`.
- Add `"saf-projects-dashboard": ["saf-projects-dashboard"]` to `TESTS_DEFINITIONS_PER_TARGET`.
- Add a new module-level list and function:

  ```python
  JS_PACKAGES = [
      "saf-projects-dashboard",
  ]


  def get_changed_js_packages(pr_changes: list[str]) -> list[str]:
      """Return the changed packages that carry a Node/npm build."""
      changed_packages = [pkg for pkg in pr_changes if pkg in JS_PACKAGES]
      write_matrix_to_output("js_packages_matrix", [{"library-name": pkg} for pkg in changed_packages])
      return changed_packages
  ```

  and call it from the module-level sequence at the bottom of the file.
- **Do not** add the package to `UV_PACKAGES`.

**`.github/actions/ci-cd-job-matrices/action.yml`**

Add the output:

```yaml
  js-packages-matrix:
    value: ${{ steps.script.outputs.js_packages_matrix }}
```

**`.github/actions/ci-cd-job-matrices/test_ci_cd_job_matrices.py`**

Add coverage for the new behaviour:

- `get_changed_js_packages` returns `["saf-projects-dashboard"]` for a matching input, `[]`
  otherwise, and writes `"{}"` when empty.
- `saf-projects-dashboard` resolves to `--with tests,style --all-extras` in the code-style matrix.
- `saf-projects-dashboard` is **not** in `moon_packages_matrix` (guards against accidental
  addition to `UV_PACKAGES` before the package is actually converted).

Existing tests iterate `SAF_PACKAGES` generically and assert on `glow-engine` / `saf-testing` /
`saf-cli` specifically, so adding a package breaks none of them.

**`.github/workflows/tests_groups_definitions/saf-projects-dashboard.json`** (new)

```json
[
    {
        "test-report-artifact-name-suffix": "saf_projects_dashboard_linux",
        "pytest-additional-arguments": "tests/",
        "pytest-markers": "not e2e and not performance",
        "runner-name": "ubuntu-latest"
    },
    {
        "test-report-artifact-name-suffix": "saf_projects_dashboard_windows",
        "pytest-additional-arguments": "tests/",
        "pytest-markers": "not e2e and not performance",
        "runner-name": "windows-latest"
    }
]
```

`pytest-markers` is combined into `-m "<markers>"` at `_test.yml:481-491`, reproducing the
standalone's `pytest tests/ -m "not e2e and not performance"`.

### 2. Change detection and labels

**`.github/changes_pr_filters.yaml`**

```yaml
saf-projects-dashboard:
  - 'packages/saf-projects-dashboard/**'
  - '!packages/saf-projects-dashboard/doc/**'
  - '.github/workflows/tests_groups_definitions/saf-projects-dashboard.json'
  - '.github/workflows/_js.yml'
```

The `doc/**` exclusion is included ahead of the doc migration so the filter is already correct
when that lands.

**`.github/labeler.yml`** — a `'saf-projects-dashboard'` rule matching
`packages/saf-projects-dashboard/**` and the tests-groups JSON, following the
`saf-product-configuration` entry's shape.

**`.github/labels.yml`** — a new entry following the existing shape:

```yaml
- name: saf-projects-dashboard
  description: Package saf-projects-dashboard
  color: ffffff
```

**`.github/changes_doc_filters.yaml`** — **not** modified. Deferred with the doc migration.

### 3. New reusable workflow: `.github/workflows/_js.yml`

Two jobs, both `ubuntu-latest`, both `permissions: { contents: read }`. Written generically over
`library-name` so a second Node-bearing package can reuse it without edits.

```yaml
name: JS

on:
  workflow_call:
    inputs:
      library-name:
        description: 'Package carrying the Node build'
        required: true
        type: string
      python-version:
        description: 'Python version used for the component-generation step'
        required: true
        type: string

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}-js-${{ inputs.library-name }}
  cancel-in-progress: true

permissions: {}

jobs:
  js-test:
    name: "JavaScript tests"
    runs-on: ubuntu-latest
    permissions:
      contents: read
    defaults:
      run:
        working-directory: packages/${{ inputs.library-name }}
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false

      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
        with:
          node-version-file: packages/${{ inputs.library-name }}/.nvmrc
          cache: npm
          cache-dependency-path: packages/${{ inputs.library-name }}/package-lock.json

      - name: Install npm dependencies
        shell: bash
        run: npm ci

      - name: Run Jest
        shell: bash
        run: npm test

  js-build:
    name: "JavaScript build and freshness"
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false

      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
        with:
          node-version-file: packages/${{ inputs.library-name }}/.nvmrc
          cache: npm
          cache-dependency-path: packages/${{ inputs.library-name }}/package-lock.json

      - name: Prepare Python environment
        uses: ansys/saf-devops/prepare-python-environment@baa22e0dcc7e6598c662b4c003b2aac5b860f466 # v1.0.0
        with:
          python-version: ${{ inputs.python-version }}
          poetry-version: ${{ vars.POETRY_VERSION }}
          python-project-path: packages/${{ inputs.library-name }}
          poetry-install-args: "--with build"

      - name: Install npm dependencies
        working-directory: packages/${{ inputs.library-name }}
        shell: bash
        run: npm ci

      - name: Build bundle and generate component wrappers
        working-directory: packages/${{ inputs.library-name }}
        shell: bash
        run: |
          source .venv/bin/activate
          npm run build

      - name: Fail if the committed build output is stale
        shell: bash
        env:
          GENERATED_PATH: packages/${{ inputs.library-name }}/src
        run: |
          if ! git diff --exit-code -- "${GENERATED_PATH}"; then
            echo "::error::Committed build output is out of date. Run 'npm run build' in packages/${{ inputs.library-name }} and commit the result."
            exit 1
          fi

      - name: Upload bundle
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: js-bundle-${{ inputs.library-name }}
          path: packages/${{ inputs.library-name }}/src/ansys_saf_projects_dashboard/
          if-no-files-found: error
```

Notes on the shape above:

- **`js-build` needs both Node and Python.** `npm run build` runs `node scripts/build.js`, which
  chains `build:js` (webpack) and `build:backends`
  (`python scripts/generate_components.py`, requiring `dash[dev]` and `pyyaml` from the
  package's `build` Poetry group). This is why the standalone invoked
  `poetry run npm run build`. `ansys/saf-devops/prepare-python-environment` creates `.venv`
  inside `python-project-path`, matching how the `code-style` job in `ci_cd_pr.yml` activates it.
- **The freshness gate diffs the whole `src/`**, not just the generated package directory, so it
  stays correct for any package and catches drift in both the bundle and the generated `.py`
  wrappers. `npm ci` does not modify `package-lock.json`, so it cannot produce a false positive.
- **`vars.POETRY_VERSION`** resolves inside called workflows — the same pattern is already used
  at `_test.yml:499`.
- All actions are pinned by commit SHA with a version comment, reusing the SHAs already present
  elsewhere in the repository.

### 4. Caller wiring

**`.github/workflows/ci_cd_pr.yml`**

- Add `js-packages-matrix: ${{ steps.info.outputs.js-packages-matrix }}` to the `ci-cd-config`
  job outputs.
- Add a `js-checks` job:

  ```yaml
  js-checks:
    name: "JavaScript checks"
    needs: ci-cd-config
    if: ${{ needs.ci-cd-config.outputs.js-packages-matrix != '{}' }}
    permissions:
      contents: read
    strategy:
      fail-fast: false
      matrix: ${{ fromJson(needs.ci-cd-config.outputs.js-packages-matrix) }}
    uses: ./.github/workflows/_js.yml
    with:
      library-name: ${{ matrix.library-name }}
      python-version: ${{ vars.PYTHON_VERSION }}
  ```

- Add `js-checks` to the `ci-result` job's `needs` list so a Jest failure blocks the PR.

**`.github/workflows/certification.yml`**

- `run-name` expression: add `github.event.schedule == '0 12 * * 2,4' && 'saf-projects-dashboard' ||`.
- `workflow_dispatch` `library-name` choice list: add `saf-projects-dashboard`.
- `schedule`: add `- cron: '0 12 * * 2,4'` (next free slot; existing slots end at `0 11 * * 2,4`).
- `pre-certification` `library-name` step `case` statement: add the matching `'0 12 * * 2,4')` branch.
- `use-moon` output expression: **unchanged** — the package stays on Poetry.
- Add a `js-checks` job:

  ```yaml
  js-checks:
    name: "JavaScript checks"
    needs: pre-certification
    if: ${{ needs.pre-certification.outputs.library-name == 'saf-projects-dashboard' }}
    permissions:
      contents: read
    uses: ./.github/workflows/_js.yml
    with:
      library-name: ${{ needs.pre-certification.outputs.library-name }}
      python-version: ${{ vars.PYTHON_VERSION }}
  ```

- Add `js-checks` to `certification-report`'s `needs` and to its summary table (a
  `JS_CHECKS_RESULT` env var and a `| JavaScript checks | ... |` row), so a Jest failure blocks
  the certification tag via the existing `OVERALL_CERTIFICATION_RESULT` logic.

**`.github/workflows/ci_cd_release.yml`**

- `library` choice list: add `saf-projects-dashboard`.
- The three `contains('bdm-python-api,bdm-python-shared-volume,saf-iam-oidc,saf-product-configuration', ...)`
  expressions are **unchanged** — the package is not a Moon package, so it correctly takes the
  Poetry branch of each.

**`.github/workflows/_test.yml`**

- `workflow_dispatch` `package-name` choice list: add `saf-projects-dashboard` (debug-run
  convenience only; the `workflow_call` path is name-agnostic).

### 5. Documentation of the change

**`.github/copilot-instructions.md`** — add the package to the repository tree and to the
Poetry-install-args table (`style` group row, alongside `glow-engine`, `saf-testing`,
`dash-super-components`).

## Parity audit

Every job in the four standalone workflows, and where its coverage lands:

| Standalone workflow / job | Monorepo destination |
| --- | --- |
| `build.yml` → `build-wheel` | `_build.yml` (Poetry branch) + `_js.yml` → `js-build` freshness gate |
| `ci_cd_pr.yml` → `code-style` | `ci_cd_pr.yml` → `code-style` (via `code_style_matrix`) |
| `ci_cd_pr.yml` → `tests-python` | `ci_cd_pr.yml` → `run-tests` → `_test.yml` |
| `ci_cd_pr.yml` → `tests-js` | **new** `_js.yml` → `js-test` |
| `ci_cd_pr.yml` → `build` | `ci_cd_pr.yml` → `build-wheel` → `_build.yml` |
| `certification.yml` → `pre-certification` | `pre-certification` + `check-package-changes` + `vulnerabilities` + `dependabot-alerts` |
| `certification.yml` → `run-tests-python` | `certification.yml` → `run-tests` |
| `certification.yml` → `run-tests-js` | **new** `js-checks` leg |
| `certification.yml` → `build-wheel` | `certification.yml` → `build-wheel` (sweeps Python 3.11–3.14) |
| `certification.yml` → `check-wheel-can-be-pip-installed` | same name, already exists |
| `certification.yml` → `post-certification` | same name, already exists |
| `ci_cd_release.yml` → `certification` | same name, already exists |
| `ci_cd_release.yml` → `release-information` | same name, already exists |
| `ci_cd_release.yml` → `generate-release-notes` | same name, already exists |
| `ci_cd_release.yml` → `prepare-release` | same name, already exists |
| `ci_cd_release.yml` → `build-wheel` | same name, already exists |
| `ci_cd_release.yml` → `bump-version` | same name, already exists |
| `ci_cd_release.yml` → `bump-release-branch-version` | same name, already exists |
| `ci_cd_release.yml` → `release-package` (private PyPI) | `release-to-pypi` (public PyPI, OIDC) |
| `ci_cd_release.yml` → `build-doc` / `deploy-doc` | **deferred** — see Out of scope |

### Deliberate differences

**Two standalone jobs have no monorepo counterpart, by pre-existing monorepo convention — not
as a result of this change:**

- `certification.yml` → `code-style`
- `ci_cd_release.yml` → `code-style`

The monorepo enforces code style on every PR and does not repeat it during certification or
release. No existing monorepo package runs it in those workflows. Matching the convention;
revisit only if certification is expected to be self-contained.

**Coverage the standalone had that changes shape:**

- Python test matrix goes from 3.11/3.12/3.13 on Ubuntu to a single `vars.PYTHON_VERSION` on
  Ubuntu **and** Windows. Certification's `build-wheel` and `check-wheel-can-be-pip-installed`
  still sweep 3.11–3.14, so multi-version installability is retained.

**Coverage the standalone never had, gained for free:** `check-dependencies-licenses`, `sbom`,
`compatibility-tests`, Windows pytest runners, `validate-release-branch`,
`certification-report`, `lint-pr-title`, `check-linked-issues-in-pull-request-description`,
`github-workflows-lint`.

## Error handling

- **Jest failure** — `js-test` fails → `js-checks` fails → `ci-result` fails (PR blocked);
  during certification, `certification-report` reports failure and `post-certification` does not
  tag.
- **Stale committed bundle** — `js-build` prints the diff and exits non-zero. The contributor
  reruns `npm run build` locally and commits the regenerated output.
- **Empty `js_packages_matrix`** — `js-checks` is skipped via the `!= '{}'` guard. A skipped job
  reports `skipped`, which neither `contains(needs.*.result, 'failure')` nor
  `contains(needs.*.result, 'cancelled')` matches, so `ci-result` still passes for the other 12
  packages.
- **Missing PyPI trusted publisher** — `release-to-pypi` fails at the publish step on the first
  stable release. Listed below as an external prerequisite.

## Testing and verification

1. `uv run .github/actions/ci-cd-job-matrices/test_ci_cd_job_matrices.py` passes locally,
   including the new cases. This suite also runs in CI via the `run-tests-actions` job, which
   triggers because `.github/actions/ci-cd-job-matrices/**` is in this change.
2. `actionlint` / the repo's `github-workflows-lint` job passes on `_js.yml` and the edited
   workflows. That job is gated on the `devops` label, which this PR will carry.
3. On the PR itself, confirm from the `ci-cd-config` job summary that
   `js_packages_matrix`, `packages_matrix`, `code_style_matrix`, and `tests_matrix` each contain
   `saf-projects-dashboard`, and that `moon_packages_matrix` does **not**.
4. Confirm these jobs run and pass on the PR: `code-style`, `run-tests` (Linux + Windows),
   `js-checks` (both jobs), `build-wheel`, `check-wheel-can-be-pip-installed`, `vulnerabilities`,
   `check-dependencies-licenses`, `sbom`.
5. Confirm the built wheel contains `ansys_saf_projects_dashboard.js`, `proptypes.js`,
   `metadata.json`, `package-info.json`, and `assets/fonts/*.ttf`. The package's `.gitignore`
   influences what Poetry packages, so verify rather than assume.
6. Trigger `certification.yml` manually with `library-name: saf-projects-dashboard` on a branch
   and confirm the `js-checks` leg appears and the certification summary table includes it.

## Out of scope

Tracked as follow-up issues, not part of this change:

1. **Documentation migration** — port `doc/source` (40 files; exclude the committed `doc/build`
   output) into `packages/saf-projects-dashboard/doc/`, rewrite `conf.py` to the monorepo
   pattern used by `saf-iam-oidc`, then register in `_doc.yml` (`doc-api-build` matrix, the
   `gh-pages-saf-projects-dashboard` checkout, and the merge list) and add the package's
   `poetry.lock` to `.github/changes_doc_filters.yaml`.
2. **Moon/uv conversion** — add to `.moon/workspace.yml` projects globs, root `pyproject.toml`
   `[tool.uv.workspace] members` and `[tool.uv.sources]`, drop `poetry.lock`, add to
   `UV_PACKAGES`, and extend the four `contains('bdm-python-api,...')` expressions in
   `certification.yml` and `ci_cd_release.yml`. Also requires deciding how Moon models the Node
   toolchain, which `.moon/tasks/all.yml` currently has no tasks for.
3. **Retiring the standalone repository** — delete or archive
   `ansys/saf-projects-dashboard/.github/workflows` once the monorepo pipeline is green.

### External prerequisites (cannot be satisfied by this code change)

- A **PyPI trusted-publisher entry** for the `ansys-saf-projects-dashboard` project, scoped to
  the `ansys/saf` repository, `ci_cd_release.yml`, and the `saf-release` environment. Required
  before the first stable release, not before merge.
- Repository variables `PYTHON_VERSION`, `POETRY_VERSION`, and `WHITELIST_LICENSE_CHECK` already
  exist and are reused unchanged.

## Observation (not addressed here)

`certification.yml:459` gates the `-artifacts` artifact-name suffix on
`contains('bdm-python-api,bdm-python-shared-volume,saf-iam-oidc', ...)`, while the `use-moon`
output at line 164 gates on
`contains('bdm-python-api,bdm-python-shared-volume,saf-iam-oidc,saf-product-configuration', ...)`.
`saf-product-configuration` is present in one list and absent from the other, which would make
`check-wheel-can-be-pip-installed` look for an artifact name the Moon build path does not
produce. This predates the current change and does not affect `saf-projects-dashboard` (which
takes the Poetry branch of both expressions), but it is worth a separate issue.
