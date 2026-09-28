# saf-projects-dashboard CI/CD Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register `packages/saf-projects-dashboard` in the SAF monorepo's CI/CD so it is built, linted, tested, certified and released like every other package, plus add Node/npm support that no existing package needs.

**Architecture:** The monorepo has one `build`, one `certification` and one `release` workflow, fanned out over job matrices produced by `.github/actions/ci-cd-job-matrices/ci_cd_job_matrices.py`. Onboarding is therefore *registration* (adding the package name to matrices, filters and choice lists), not *duplication*. The one genuinely new piece is `.github/workflows/_js.yml`, a reusable workflow for the webpack build and Jest suites, gated on a new `js_packages_matrix` output so it stays inert for the other 12 packages.

**Tech Stack:** GitHub Actions reusable workflows, Python 3.11+ (PEP 723 single-file scripts run via `uv run`), pytest, Poetry 2.3.2, Node 20.19.0 + npm, Jest, webpack.

**Spec:** [2026-09-25-saf-projects-dashboard-cicd-design.md](../specs/2026-09-25-saf-projects-dashboard-cicd-design.md)

## Global Constraints

- **Package is Poetry-managed, not Moon/uv.** Never add `saf-projects-dashboard` to `UV_PACKAGES` in `ci_cd_job_matrices.py`, to `.moon/workspace.yml`, to the root `pyproject.toml` `[tool.uv.workspace] members`, or to any of the four `contains('bdm-python-api,bdm-python-shared-volume,saf-iam-oidc,saf-product-configuration', ...)` expressions in `certification.yml` and `ci_cd_release.yml`.
- **Do not modify** `.github/workflows/_build.yml`, `.github/workflows/_test.yml` job logic, or `.github/workflows/_doc.yml`. The only permitted `_test.yml` edit is appending to its `workflow_dispatch` `package-name` choice list.
- **Documentation is out of scope.** Do not touch `.github/changes_doc_filters.yaml`, do not create `packages/saf-projects-dashboard/doc/`, do not register the package in `_doc.yml`.
- **All GitHub Actions must be pinned by full commit SHA** with a trailing `# vX.Y.Z` comment. Reuse SHAs already present in this repository — do not look up new ones:
  - `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`
  - `actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0`
  - `ansys/saf-devops/prepare-python-environment@baa22e0dcc7e6598c662b4c003b2aac5b860f466 # v1.0.0`
- **Local environment note.** This machine exports `VIRTUAL_ENV` pointing at an unrelated checkout, so `uv run` prints a warning about a mismatched environment path. The warning is harmless and is not a finding. Local `node` is v22 while `.nvmrc` pins v20.19.0 — CI honours `.nvmrc`; local Jest runs on v22 are still valid evidence.
- **Every workflow declares `permissions: {}` at the top level** and the narrowest `permissions:` per job. Every `actions/checkout` sets `persist-credentials: false`.
- **Never interpolate `${{ ... }}` directly inside a `run:` block.** Pass the value through `env:` and reference the shell variable. The repo runs `zizmor --pedantic` in pre-commit, which fails on template injection.
- **YAML formatting is enforced by `yamlfmt`** with `max_line_length=80,retain_line_breaks=true,retain_line_breaks_single=true`. Do not hand-wrap long lines. Write natural YAML, then run pre-commit and commit whatever it reformats.
- **Package name spellings** (exact, do not vary): directory and label `saf-projects-dashboard`; Python distribution `ansys-saf-projects-dashboard`; Python import package `ansys_saf_projects_dashboard`; test-report suffixes `saf_projects_dashboard_linux` / `saf_projects_dashboard_windows`.
- **Node version** comes from `packages/saf-projects-dashboard/.nvmrc` (currently `20.19.0`). Never hardcode it.
- **Commit message prefixes** follow the repo's semantic-PR convention: `ci(feat):`, `ci(fix):`, `docs:`, `test:`.

## File Structure

| File | Responsibility | Action |
| --- | --- | --- |
| `.github/actions/ci-cd-job-matrices/ci_cd_job_matrices.py` | Pure mapping from changed-filter names to job matrices | Modify |
| `.github/actions/ci-cd-job-matrices/test_ci_cd_job_matrices.py` | Test suite for the above | Modify |
| `.github/actions/ci-cd-job-matrices/action.yml` | Composite action exposing matrices as outputs | Modify |
| `.github/workflows/tests_groups_definitions/saf-projects-dashboard.json` | pytest session config (runner OS, args, markers) | Create |
| `.github/changes_pr_filters.yaml` | Path globs → changed-package names | Modify |
| `.github/labeler.yml` | Path globs → PR labels | Modify |
| `.github/labels.yml` | Canonical label definitions | Modify |
| `.github/workflows/_js.yml` | Node concern: Jest + webpack build + freshness gate | Create |
| `.github/workflows/ci_cd_pr.yml` | PR orchestration | Modify |
| `.github/workflows/certification.yml` | Per-package certification | Modify |
| `.github/workflows/ci_cd_release.yml` | Per-package release | Modify |
| `.github/workflows/_test.yml` | Shared pytest workflow | Modify (dispatch choice list only) |
| `.github/copilot-instructions.md` | Repo orientation doc | Modify |

---

## Task 1: Register the package in the existing matrices

Adds `saf-projects-dashboard` to `SAF_PACKAGES`, `CODE_STYLE_POETRY_ARGS` and `TESTS_DEFINITIONS_PER_TARGET`, creates its tests-group definition, and updates the orientation doc.

The test suite already contains two guard tests that give a real red-green cycle here, so no new tests are needed for this task:

- `test_all_packages_have_test_definitions` — fails if a package is in `SAF_PACKAGES` but absent from `TESTS_DEFINITIONS_PER_TARGET`.
- `test_tests_definitions_files_exist` — fails if `TESTS_DEFINITIONS_PER_TARGET` references a JSON file that does not exist on disk.

**Files:**
- Modify: `.github/actions/ci-cd-job-matrices/ci_cd_job_matrices.py:28-41` (`SAF_PACKAGES`), `:56-61` (`CODE_STYLE_POETRY_ARGS`), `:65-82` (`TESTS_DEFINITIONS_PER_TARGET`)
- Create: `.github/workflows/tests_groups_definitions/saf-projects-dashboard.json`
- Modify: `.github/copilot-instructions.md:41-53` and `:101-105`
- Test: `.github/actions/ci-cd-job-matrices/test_ci_cd_job_matrices.py` (existing guard tests, not modified)

**Interfaces:**
- Consumes: nothing.
- Produces: `saf-projects-dashboard` present in `SAF_PACKAGES`, which makes it appear in the `packages_matrix`, `poetry_packages_matrix`, `code_style_matrix`, `compatibility_matrix` and `tests_matrix` outputs whenever the `saf-projects-dashboard` change filter fires. Task 3 creates that filter.

- [ ] **Step 1: Add the package to `SAF_PACKAGES` only, to trigger the guard test**

In `.github/actions/ci-cd-job-matrices/ci_cd_job_matrices.py`, add one line to the `SAF_PACKAGES` list so it reads:

```python
SAF_PACKAGES = [
    "bdm-python-api",
    "bdm-python-shared-volume",
    "dash-super-components",
    "glow-engine",
    "saf-cli",
    "saf-desktop-installer",
    "saf-desktop-orchestrator",
    "saf-iam-oidc",
    "saf-product-configuration",
    "saf-product-manager",
    "saf-projects-dashboard",
    "saf-templates",
    "saf-testing",
]
```

- [ ] **Step 2: Run the guard test to verify it fails**

Run:

```bash
uv run .github/actions/ci-cd-job-matrices/test_ci_cd_job_matrices.py -k test_all_packages_have_test_definitions -v
```

Expected: FAIL with `AssertionError: assert 'saf-projects-dashboard' in {...}`

- [ ] **Step 3: Add the tests-definitions mapping**

In the same file, add one entry to `TESTS_DEFINITIONS_PER_TARGET` so the `saf-product-manager` / `saf-templates` region reads:

```text
    "saf-product-manager": ["saf-product-manager"],
    "saf-projects-dashboard": ["saf-projects-dashboard"],
    "saf-templates": ["saf-templates"],
```

- [ ] **Step 4: Run both guard tests — the first now passes, the second now fails**

Run:

```bash
uv run .github/actions/ci-cd-job-matrices/test_ci_cd_job_matrices.py -k "test_all_packages_have_test_definitions or test_tests_definitions_files_exist" -v
```

Expected: `test_all_packages_have_test_definitions` PASS, `test_tests_definitions_files_exist` FAIL with `Test definition file not found: .../tests_groups_definitions/saf-projects-dashboard.json`

- [ ] **Step 5: Create the tests-group definition file**

Create `.github/workflows/tests_groups_definitions/saf-projects-dashboard.json`:

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

`pytest-markers` is concatenated into `-m "<markers>"` by `_test.yml:481-491`, reproducing the standalone repo's `pytest tests/ -m "not e2e and not performance"`.

- [ ] **Step 6: Run both guard tests to verify they pass**

Run:

```bash
uv run .github/actions/ci-cd-job-matrices/test_ci_cd_job_matrices.py -k "test_all_packages_have_test_definitions or test_tests_definitions_files_exist" -v
```

Expected: 2 passed

- [ ] **Step 7: Add the code-style Poetry arguments**

The package declares `pre-commit` in its `style` group (`packages/saf-projects-dashboard/pyproject.toml:39-42`), so the default `--with tests --all-extras` would leave `pre-commit` uninstalled and the `code-style` job would fail at `pre-commit run --all-files`. Add one entry to `CODE_STYLE_POETRY_ARGS`:

```python
CODE_STYLE_POETRY_ARGS = {
    "glow-engine": "--with tests,style --all-extras",
    "saf-desktop-installer": "--with tests,style --all-extras",
    "saf-desktop-orchestrator": "--with tests,dev --all-extras",
    "dash-super-components": "--with tests,style --all-extras",
    "saf-projects-dashboard": "--with tests,style --all-extras",
}
```

- [ ] **Step 8: Run the whole suite to verify nothing regressed**

Run:

```bash
uv run .github/actions/ci-cd-job-matrices/test_ci_cd_job_matrices.py
```

Expected: all tests pass, 0 failures. The existing tests assert on `glow-engine`, `saf-testing` and `saf-cli` specifically, or iterate `SAF_PACKAGES` generically, so adding a package breaks none of them.

- [ ] **Step 9: Update the orientation document**

In `.github/copilot-instructions.md`, change the packages tree comment and add the directory entry:

```text
└── packages/                         # All 13 Python packages
    ├── bdm-python-api/
    ├── bdm-python-shared-volume/
    ├── dash-super-components/
    ├── glow-engine/
    ├── saf-cli/
    ├── saf-desktop-installer/
    ├── saf-desktop-orchestrator/
    ├── saf-iam-oidc/
    ├── saf-product-configuration/
    ├── saf-product-manager/
    ├── saf-projects-dashboard/
    ├── saf-templates/
    └── saf-testing/
```

Then in the pre-commit dependency-group table, add the package to the `style` row:

```markdown
| Group | Packages |
|-------|----------|
| `style` | glow-engine, saf-testing, dash-super-components, saf-projects-dashboard |
```

And add a line to the package-level install-groups comment block:

```bash
#   saf-projects-dashboard:   poetry install --with tests,style --all-extras
```

- [ ] **Step 10: Commit**

```bash
git add .github/actions/ci-cd-job-matrices/ci_cd_job_matrices.py \
        .github/workflows/tests_groups_definitions/saf-projects-dashboard.json \
        .github/copilot-instructions.md
git commit -m "ci(feat): register saf-projects-dashboard in CI job matrices

Refs #80"
```

---

## Task 2: Add the `js_packages_matrix` output

Introduces a new matrix listing changed packages that carry a Node/npm build. This is what keeps `_js.yml` inert for the other 12 packages.

**Files:**
- Modify: `.github/actions/ci-cd-job-matrices/ci_cd_job_matrices.py` — locate by text anchor, not line number: after the `UV_PACKAGES` list, after the `get_changed_moon_packages` function, and the module-level call sequence at the end of the file. Task 1 already shifted this file's line numbers.
- Modify: `.github/actions/ci-cd-job-matrices/action.yml` — the `outputs:` block
- Test: `.github/actions/ci-cd-job-matrices/test_ci_cd_job_matrices.py` (new `TestGetChangedJsPackages` class)

**Interfaces:**
- Consumes: `SAF_PACKAGES` containing `saf-projects-dashboard` (Task 1).
- Produces:
  - `JS_PACKAGES: list[str]` — module-level constant, currently `["saf-projects-dashboard"]`.
  - `get_changed_js_packages(pr_changes: list[str]) -> list[str]` — returns the subset of `pr_changes` present in `JS_PACKAGES`, and writes a `js_packages_matrix` GitHub output whose value is `{"include": [{"library-name": "<pkg>"}, ...]}` as indented JSON, or the literal string `{}` when the subset is empty.
  - Composite-action output `js-packages-matrix`, consumed by Task 5.

- [ ] **Step 1: Write the failing tests**

Append this class to `.github/actions/ci-cd-job-matrices/test_ci_cd_job_matrices.py`, immediately after the existing `TestGetChangedMoonPackages` class (which ends at line 404, just before `class TestGetCodeStyleMatrixEntries:`):

```python
class TestGetChangedJsPackages:
    """Test the get_changed_js_packages function."""

    def test_get_changed_js_packages_empty_input(self, github_env: tuple[Path, Path]):
        """Empty input returns no JS packages and writes an empty matrix."""
        output_file, _ = github_env

        result = get_changed_js_packages([])

        assert result == []
        outputs = parse_outputs(output_file)
        assert outputs["js_packages_matrix"] == "{}"

    def test_get_changed_js_packages_returns_js_packages(self, github_env: tuple[Path, Path]):
        """Node-bearing packages are returned and written to their matrix."""
        output_file, _ = github_env

        result = get_changed_js_packages(["glow-engine", "saf-projects-dashboard"])

        assert result == ["saf-projects-dashboard"]
        outputs = parse_outputs(output_file)
        assert json.loads(outputs["js_packages_matrix"]) == {
            "include": [{"library-name": "saf-projects-dashboard"}],
        }

    def test_get_changed_js_packages_filters_non_js_packages(self, github_env: tuple[Path, Path]):
        """Packages without a Node build, and unknown names, are filtered out."""
        result = get_changed_js_packages(["invalid-pkg", "saf-testing", "examples"])

        assert result == []

    def test_js_packages_are_registered_saf_packages(self) -> None:
        """Every Node-bearing package is also a regular SAF package."""
        for package in JS_PACKAGES:
            assert package in SAF_PACKAGES

    def test_js_packages_are_not_moon_packages(self) -> None:
        """Node-bearing packages stay on Poetry until Moon grows a Node toolchain."""
        for package in JS_PACKAGES:
            assert package not in UV_PACKAGES
```

Then extend the import block at lines 42-57 so it includes the three new names. The block is alphabetised with constants first; the result must read:

```text
    from ci_cd_job_matrices import (
        JS_PACKAGES,
        SAF_PACKAGES,
        TESTS_DEFINITIONS_DIR,
        TESTS_DEFINITIONS_PER_TARGET,
        UV_PACKAGES,
        get_changed_js_packages,
        get_changed_moon_packages,
        get_changed_packages,
        get_changed_poetry_packages,
        get_code_style_matrix_entries,
        get_compatibility_matrix_entries,
        get_pr_changes,
        get_tests_generated_solution_flag,
        get_tests_matrix_entries,
        write_matrix_to_output,
        write_output,
        write_to_github_step_summary,
    )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
uv run .github/actions/ci-cd-job-matrices/test_ci_cd_job_matrices.py -k TestGetChangedJsPackages -v
```

Expected: collection error — `ImportError: cannot import name 'JS_PACKAGES' from 'ci_cd_job_matrices'`

- [ ] **Step 3: Add the constant and the function**

In `.github/actions/ci-cd-job-matrices/ci_cd_job_matrices.py`, add `JS_PACKAGES` immediately after the existing `UV_PACKAGES` list (which ends at line 89):

```python
JS_PACKAGES = [
    "saf-projects-dashboard",
]
```

Then add the function immediately after `get_changed_moon_packages` (which ends at line 125):

```python
def get_changed_js_packages(pr_changes: list[str]) -> list[str]:
    """Return the changed packages that carry a Node/npm build."""
    changed_packages = [pkg for pkg in pr_changes if pkg in JS_PACKAGES]
    write_matrix_to_output("js_packages_matrix", [{"library-name": pkg} for pkg in changed_packages])
    return changed_packages
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
uv run .github/actions/ci-cd-job-matrices/test_ci_cd_job_matrices.py -k TestGetChangedJsPackages -v
```

Expected: 5 passed

- [ ] **Step 5: Wire the function into the module-level call sequence**

At the bottom of `ci_cd_job_matrices.py`, the call sequence must read:

```python
pr_changes = get_pr_changes()
changed_packages = get_changed_packages(pr_changes)
get_changed_poetry_packages(pr_changes)
get_changed_moon_packages(pr_changes)
get_changed_js_packages(pr_changes)
get_code_style_matrix_entries(changed_packages, pr_changes)
get_compatibility_matrix_entries(changed_packages)
get_tests_matrix_entries(pr_changes, changed_packages)
get_tests_generated_solution_flag(changed_packages)
```

- [ ] **Step 6: Expose the matrix as a composite-action output**

In `.github/actions/ci-cd-job-matrices/action.yml`, add the output after `moon-packages-matrix` (lines 29-30) so that region reads:

```yaml
  moon-packages-matrix:
    value: ${{ steps.script.outputs.moon_packages_matrix }}
  js-packages-matrix:
    value: ${{ steps.script.outputs.js_packages_matrix }}
```

- [ ] **Step 7: Run the whole suite to verify nothing regressed**

Run:

```bash
uv run .github/actions/ci-cd-job-matrices/test_ci_cd_job_matrices.py
```

Expected: all tests pass, 0 failures.

- [ ] **Step 8: Commit**

```bash
git add .github/actions/ci-cd-job-matrices/ci_cd_job_matrices.py \
        .github/actions/ci-cd-job-matrices/test_ci_cd_job_matrices.py \
        .github/actions/ci-cd-job-matrices/action.yml
git commit -m "ci(feat): add js-packages-matrix output for Node-bearing packages

Refs #80"
```

---

## Task 3: Change detection and labels

Without a change filter the package never appears in `pr_changes`, so every matrix stays empty and none of the jobs from Tasks 1, 2 and 5 ever fire.

**Files:**
- Modify: `.github/changes_pr_filters.yaml` (insert between the `saf-product-manager-visor` and `saf-templates` entries)
- Modify: `.github/labeler.yml` (insert between the `saf-product-manager` and `saf-templates` entries)
- Modify: `.github/labels.yml` (append a package entry)

**Interfaces:**
- Consumes: the `js_packages_matrix` name (Task 2) and the tests-group JSON path (Task 1).
- Produces: the changed-filter name `saf-projects-dashboard`, which `dorny/paths-filter` emits into `PR_CHANGES_JSON` and which every matrix function in `ci_cd_job_matrices.py` keys off.

- [ ] **Step 1: Add the change filter**

In `.github/changes_pr_filters.yaml`, add this block. `_js.yml` is listed so that editing the reusable workflow re-runs the package's jobs:

```yaml
saf-projects-dashboard:
  - 'packages/saf-projects-dashboard/**'
  - '!packages/saf-projects-dashboard/doc/**'
  - '.github/workflows/tests_groups_definitions/saf-projects-dashboard.json'
  - '.github/workflows/_js.yml'
```

The `doc/**` exclusion is included now, ahead of the deferred documentation migration, so the filter is already correct when that lands. It matches the pattern used by `dash-super-components`, `glow-engine` and `saf-product-configuration`.

- [ ] **Step 2: Add the labeler rule**

In `.github/labeler.yml`, add:

```yaml
'saf-projects-dashboard':
  - any:
      - changed-files:
          - any-glob-to-any-file: ['packages/saf-projects-dashboard/**']
          - any-glob-to-any-file: ['.github/workflows/tests_groups_definitions/saf-projects-dashboard.json']
```

- [ ] **Step 3: Add the label definition**

In `.github/labels.yml`, add an entry after the `saf-product-manager` entry (lines 19-21):

```yaml
- name: saf-projects-dashboard
  description: Package saf-projects-dashboard
  color: ffffff
```

- [ ] **Step 4: Verify the YAML parses and the filter name matches the matrix key**

Run:

```bash
uv run --with pyyaml==6.0.3 python -c "
import yaml, pathlib
filters = yaml.safe_load(pathlib.Path('.github/changes_pr_filters.yaml').read_text(encoding='utf-8'))
labeler = yaml.safe_load(pathlib.Path('.github/labeler.yml').read_text(encoding='utf-8'))
labels = {e['name'] for e in yaml.safe_load(pathlib.Path('.github/labels.yml').read_text(encoding='utf-8'))}
assert 'saf-projects-dashboard' in filters, 'missing change filter'
assert 'saf-projects-dashboard' in labeler, 'missing labeler rule'
assert 'saf-projects-dashboard' in labels, 'missing label definition'
print('all three registrations present')
"
```

Expected: `all three registrations present`

- [ ] **Step 5: Verify the label is consistent with the labeler rule**

The repo has a CI job, `validate-issue-template-labels`, that only checks issue templates — it will not catch a labeler rule with no matching label definition. The check in Step 4 covers that gap. Confirm the `devops` label will also be applied to this PR, since `.github/labeler.yml:22-25` matches any `.github/workflows/**` change, which gates the `github-workflows-lint` job used in Task 8.

Run:

```bash
uv run --with pyyaml==6.0.3 python -c "
import yaml, pathlib
labeler = yaml.safe_load(pathlib.Path('.github/labeler.yml').read_text(encoding='utf-8'))
labels = {e['name'] for e in yaml.safe_load(pathlib.Path('.github/labels.yml').read_text(encoding='utf-8'))}
missing = sorted(set(labeler) - labels)
assert not missing, f'labeler rules with no label definition: {missing}'
print('every labeler rule has a label definition')
"
```

Expected: `every labeler rule has a label definition`

- [ ] **Step 6: Commit**

```bash
git add .github/changes_pr_filters.yaml .github/labeler.yml .github/labels.yml
git commit -m "ci(feat): add change filter and label for saf-projects-dashboard

Refs #80"
```

---

## Task 4: Create the `_js.yml` reusable workflow

The one new workflow. Two jobs: Jest, and a webpack build that doubles as a staleness gate on the committed bundle.

Background the implementer needs: the wheel's payload is a webpack bundle (`src/ansys_saf_projects_dashboard/ansys_saf_projects_dashboard.js`) plus Dash component wrappers (`ProjectsDashboard.py` and siblings) generated from TypeScript. Both are **committed to git**, so `_build.yml` can package a correct wheel with no Node at all. What Node buys is (a) running the 12 Jest suites in `src/ts/__tests__/`, and (b) proving the committed output still matches `src/ts/`.

`npm run build` runs `node scripts/build.js`, which chains `npm run build:js` (webpack) and `npm run build:backends` (`python scripts/generate_components.py`). It therefore needs **both** Node and a Python environment with the package's `build` Poetry group installed — this is why the standalone repo invoked `poetry run npm run build`.

**Files:**
- Create: `.github/workflows/_js.yml`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: a reusable workflow callable as `uses: ./.github/workflows/_js.yml`, with required string inputs `library-name` and `python-version`, no secrets, and two jobs named `js-test` and `js-build`. Consumed by Tasks 5 and 6.

- [ ] **Step 1: Create the workflow**

Create `.github/workflows/_js.yml`:

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

# Apply the principle of least privilege to state at job level the right
# permissions. More information about workflow permissions in the page
# https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions
permissions: {}

jobs:
  js-test:
    name: "JavaScript tests"
    runs-on: ubuntu-latest
    permissions:
      contents: read # Read the source code of the package
    defaults:
      run:
        working-directory: packages/${{ inputs.library-name }}
    steps:
      - name: Checkout repository
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false

      - name: Setup Node
        uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
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
      contents: read # Read the source code of the package
    steps:
      - name: Checkout repository
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false

      - name: Setup Node
        uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
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
          LIBRARY_NAME: ${{ inputs.library-name }}
        run: |
          if [[ -n "$(git status --porcelain -- "packages/${LIBRARY_NAME}/src")" ]]; then
            echo "::error::Committed build output is out of date. Run 'npm run build' in packages/${LIBRARY_NAME} and commit the result."
            git diff --stat -- "packages/${LIBRARY_NAME}/src"
            exit 1
          fi
```

Also add a comment block above `jobs:` stating the contract this workflow assumes of any
package it is invoked for: `.nvmrc` and `package-lock.json` must exist, `package.json` must
define `test` and `build` scripts, and the Poetry `build` group must supply the component
generator's dependencies. Do **not** use `npm run test --if-present` — that would silently turn
a missing test script into a pass.

Note: the spec sketched a final "Upload bundle" step. It is deliberately **not** in the
workflow above. Nothing downstream consumes a `js-bundle-*` artifact — `_build.yml` packages the
committed files, and a freshness failure already prints the offending diff via
`git diff --exit-code`. Keeping it would also have forced a hardcoded
`src/ansys_saf_projects_dashboard/` path into a workflow that is otherwise generic over
`library-name`. Do not add it back.

Six things in the above are deliberate and must not be "simplified":

1. **`prepare-python-environment` creates `.venv` inside `python-project-path`**, which is why the build step does `source .venv/bin/activate` with `working-directory` set to the package. This mirrors how the `code-style` job in `ci_cd_pr.yml:325-332` activates the environment.
2. **The freshness gate inspects all of `packages/<pkg>/src`**, not just the generated directory, so it stays correct for any package and catches drift in both the bundle and the generated `.py` wrappers. `npm ci` never rewrites `package-lock.json`, so it cannot cause a false positive.
3. **Detection uses `git status --porcelain`, not `git diff --exit-code`.** `git diff` only compares *tracked* files against `HEAD` and is blind to newly created ones. `webpack.config.js` emits fonts via `type: "asset/resource"` into `src/`, so a newly referenced asset would appear as an untracked file — `git diff` would report nothing and the gate would pass green while the packaged wheel silently lacked the asset. Scoped `status` is safe here because `node_modules/` is gitignored and lives outside `src/`. Do not revert this to `git diff`.
4. **`LIBRARY_NAME` goes through `env:`** rather than being interpolated into the `run:` block. `zizmor --pedantic` fails the build on template injection.
5. **The default fetch depth of 1 is sufficient** because the check compares the working tree against `HEAD`, which is present. Do not add `fetch-depth: 0`.
6. **No `run-name:` key.** A `workflow_call`-only workflow never produces its own run — its jobs appear inside the caller's run and the caller's name is displayed — so `run-name` has no effect. Sibling `_build.yml` (also `workflow_call`-only) correctly omits it; `_test.yml` has one only because it also declares `workflow_dispatch`. It is also the folded scalar `yamlfmt` is known to corrupt in this repo.

- [ ] **Step 2: Run the repo's pre-commit hooks on the new file and commit whatever they reformat**

`yamlfmt` will rewrap lines to 80 columns and `zizmor --pedantic` will audit permissions and injection. Do not preempt either by hand.

Run:

```bash
uv run --with pre-commit==4.6.0 pre-commit run --files .github/workflows/_js.yml
```

Expected: `yamlfmt` may report `Failed` with files modified on the first run (that is the reformat); `gitleaks`, `zizmor`, `trailing-whitespace` and `codespell` report `Passed`. Known trap: `retain_line_breaks=true` mishandles a blank line placed immediately after multi-line folded-scalar content, silently injecting a literal `#magic___^_^___line` string and converting the file to CRLF. After any yamlfmt run, confirm that `grep -c "magic___" .github/workflows/_js.yml` returns 0. Line endings need care on Windows. `.gitattributes` declares `*.yml text eol=lf`, which overrides `core.autocrlf`, so the canonical form on disk and in the repo is LF. yamlfmt nonetheless writes CRLF, which leaves the working tree dirty in `git status` while `git diff` shows nothing — the stored blob is already normalized to LF. The remedy is `git checkout -- .github/workflows/_js.yml`, which restores LF on disk and clears the stale index entry. Verify the committed blob with `git cat-file -p HEAD:.github/workflows/_js.yml` rather than inspecting the working-tree file. If `zizmor` reports a finding, fix it rather than adding an ignore comment.

- [ ] **Step 3: Re-run pre-commit to confirm a clean pass**

Run:

```bash
uv run --with pre-commit==4.6.0 pre-commit run --files .github/workflows/_js.yml
```

Expected: every hook `Passed`.

- [ ] **Step 4: Verify the workflow is syntactically valid GitHub Actions YAML**

Run:

```bash
uv run --with pyyaml==6.0.3 python -c "
import yaml, pathlib
wf = yaml.safe_load(pathlib.Path('.github/workflows/_js.yml').read_text(encoding='utf-8'))
assert set(wf['jobs']) == {'js-test', 'js-build'}, wf['jobs'].keys()
call_inputs = wf[True]['workflow_call']['inputs']
assert set(call_inputs) == {'library-name', 'python-version'}, call_inputs.keys()
assert all(v['required'] for v in call_inputs.values())
assert wf['permissions'] == {}
print('_js.yml structure is valid')
"
```

Expected: `_js.yml structure is valid`

Note: `yaml.safe_load` parses the YAML key `on:` as the boolean `True`, which is why the check indexes `wf[True]`. That is a quirk of YAML 1.1, not a mistake.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/_js.yml
git commit -m "ci(feat): add _js.yml reusable workflow for Node builds and Jest

Refs #80"
```

---

## Task 5: Wire `js-checks` into the PR workflow

**Files:**
- Modify: `.github/workflows/ci_cd_pr.yml:98-107` (`ci-cd-config` outputs), `:332-334` (insert the new job between `code-style` and `doc`), `:544-565` (`ci-result` needs)

**Interfaces:**
- Consumes: the `js-packages-matrix` composite-action output (Task 2) and `_js.yml`'s `library-name` / `python-version` inputs (Task 4).
- Produces: a `js-checks` job in `ci_cd_pr.yml` whose failure propagates through `ci-result`.

- [ ] **Step 1: Expose the matrix from the `ci-cd-config` job**

In the `ci-cd-config` job's `outputs:` block, add the line after `moon-packages-matrix` so the region reads:

```yaml
      moon-packages-matrix: ${{ steps.info.outputs.moon-packages-matrix }}
      js-packages-matrix: ${{ steps.info.outputs.js-packages-matrix }}
      code-style-matrix: ${{ steps.info.outputs.code-style-matrix }}
```

- [ ] **Step 2: Add the `js-checks` job**

Insert this job immediately after the `code-style` job (which ends with the `pre-commit run --all-files --show-diff-on-failure` step) and immediately before `doc:`:

```yaml
  js-checks:
    name: "JavaScript checks"
    needs: ci-cd-config
    if: ${{ needs.ci-cd-config.outputs.js-packages-matrix != '{}' }}
    permissions:
      contents: read # Read the source code of the package
    strategy:
      fail-fast: false
      matrix: ${{ fromJson(needs.ci-cd-config.outputs.js-packages-matrix) }}
    uses: ./.github/workflows/_js.yml
    with:
      library-name: ${{ matrix.library-name }}
      python-version: ${{ vars.PYTHON_VERSION }}
```

The `!= '{}'` guard is the same idiom used by `vulnerabilities`, `code-style`, `build-wheel`, `sbom` and `run-tests` in this file. When the matrix is empty the job is skipped, and `skipped` matches neither `contains(needs.*.result, 'failure')` nor `contains(needs.*.result, 'cancelled')`, so `ci-result` still passes for the other 12 packages.

- [ ] **Step 3: Add `js-checks` to the `ci-result` gate**

In the `ci-result` job's `needs:` list, add the entry after `- code-style`:

```yaml
      - code-style-moon
      - code-style
      - js-checks
      - check-dependencies-licenses
```

- [ ] **Step 4: Verify the wiring parses and the job graph is consistent**

Run:

```bash
uv run --with pyyaml==6.0.3 python -c "
import yaml, pathlib
wf = yaml.safe_load(pathlib.Path('.github/workflows/ci_cd_pr.yml').read_text(encoding='utf-8'))
jobs = wf['jobs']
assert 'js-checks' in jobs, 'js-checks job missing'
assert jobs['js-checks']['uses'] == './.github/workflows/_js.yml'
assert 'js-packages-matrix' in jobs['ci-cd-config']['outputs']
assert 'js-checks' in jobs['ci-result']['needs'], 'js-checks not gating ci-result'
for job in jobs['ci-result']['needs']:
    assert job in jobs, f'ci-result needs unknown job: {job}'
print('ci_cd_pr.yml wiring is consistent')
"
```

Expected: `ci_cd_pr.yml wiring is consistent`

- [ ] **Step 5: Run pre-commit and commit the reformat**

Run:

```bash
uv run --with pre-commit==4.6.0 pre-commit run --files .github/workflows/ci_cd_pr.yml
```

Expected: `yamlfmt` may reformat on the first run; re-run until every hook `Passed`.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci_cd_pr.yml
git commit -m "ci(feat): run JavaScript checks for Node-bearing packages on PRs

Refs #80"
```

---

## Task 6: Wire the certification workflow

Five coordinated edits plus a new job. The schedule map appears **twice** — once in the `run-name` expression and once as a shell `case` in `pre-certification` — and both must agree or the run label will disagree with the package actually certified.

**Files:**
- Modify: `.github/workflows/certification.yml:2-21` (`run-name`), `:30-42` (dispatch choices), `:70-82` (`schedule`), `:113-159` (`case` statement), `:486-546` (`certification-report`), and a new `js-checks` job

**Interfaces:**
- Consumes: `_js.yml` (Task 4), and the tests-group JSON from Task 1 — `certification.yml:308-309` resolves the tests-group path from `library-name`, so no edit is needed for `run-tests` to pick the package up.
- Produces: `certified-saf-projects-dashboard` tag applied by `post-certification` when the whole certification passes.

- [ ] **Step 1: Add the package to the `run-name` schedule map**

In the `run-name` expression, add a line after the `saf-testing` entry so the tail of the map reads:

```yaml
      github.event.schedule == '0 11 * * 2,4' && 'saf-testing' ||
      github.event.schedule == '0 12 * * 2,4' && 'saf-projects-dashboard' ||
      'unknown-schedule'
```

- [ ] **Step 2: Add the package to the `workflow_dispatch` choice list**

Append to the `library-name` `options:` list:

```yaml
          - saf-testing
          - saf-projects-dashboard
```

- [ ] **Step 3: Add the cron slot**

`0 12 * * 2,4` is the next free slot — existing slots run hourly from `0 0` to `0 11`. Append to the `schedule:` list:

```yaml
    - cron: '0 11 * * 2,4'
    - cron: '0 12 * * 2,4'
```

- [ ] **Step 4: Add the matching `case` branch**

In the `pre-certification` job's `library-name` step, add a branch after the `saf-testing` branch and before the `*)` catch-all:

```bash
              '0 11 * * 2,4')
                echo "library-name=saf-testing" >> "$GITHUB_OUTPUT"
                ;;
              '0 12 * * 2,4')
                echo "library-name=saf-projects-dashboard" >> "$GITHUB_OUTPUT"
                ;;
              *)
                echo "Unsupported schedule '${SCHEDULE}'" >&2
                exit 1
                ;;
```

Do **not** touch the `use-moon` output expression on lines 164-165. The package stays on Poetry, so `contains(...)` correctly returns `false` for it.

- [ ] **Step 5: Add the `js-checks` job**

Insert immediately after the `run-github-workflows-of-generated-solution` job and before `build-wheel:`:

```yaml
  js-checks:
    name: "JavaScript checks"
    needs:
      - pre-certification
      - check-package-changes
    if: ${{ needs.check-package-changes.outputs.package-has-changes == 'true' &&
      needs.pre-certification.outputs.library-name == 'saf-projects-dashboard' }}
    permissions:
      contents: read # Read the source code of the package
    uses: ./.github/workflows/_js.yml
    with:
      library-name: ${{ needs.pre-certification.outputs.library-name }}
      python-version: ${{ vars.PYTHON_VERSION }}
```

The `package-has-changes` guard matches how `run-tests` (line 296) and `run-tests-extended` (line 330) avoid re-running work for an unchanged package.

- [ ] **Step 6: Make the certification report gate on `js-checks`**

Without this, a Jest failure would not stop `post-certification` from applying the `certified-saf-projects-dashboard` tag, because `post-certification`'s condition is `needs.certification-report.result == 'success'`.

Three edits inside the `certification-report` job. First, in `needs:`, add the entry after `run-github-workflows-of-generated-solution`:

```yaml
      - run-github-workflows-of-generated-solution
      - js-checks
      - build-wheel
```

Second, in the step's `env:` block, add after `RUN_TESTS_GENERATED_SOLUTION_RESULT`:

```yaml
          JS_CHECKS_RESULT: ${{ needs.js-checks.result }}
```

Third, in the summary heredoc, add a row after the generated-solution row:

```bash
            echo "| Tests (generated solution) | ${RUN_TESTS_GENERATED_SOLUTION_RESULT} |"
            echo "| JavaScript checks | ${JS_CHECKS_RESULT} |"
            echo "| Wheel build | ${BUILD_WHEEL_RESULT} |"
```

`OVERALL_CERTIFICATION_RESULT` is computed from `needs.*.result`, so adding `js-checks` to `needs` is what actually makes it blocking; the env var and table row exist so the failure is legible in the summary.

- [ ] **Step 7: Verify the two schedule maps agree and the job graph is consistent**

This check is the whole point of the task — a mismatch between the `run-name` map and the `case` statement is silent at runtime and mislabels certification runs.

This check uses a quoted heredoc (`<<'PY'`) rather than `python -c "..."` so the regex
backslashes and nested quotes reach Python untouched by the shell. Do not convert it to `-c`.

Run:

```bash
uv run --with pyyaml==6.0.3 python - <<'PY'
import pathlib
import re

import yaml

text = pathlib.Path(".github/workflows/certification.yml").read_text(encoding="utf-8")
wf = yaml.safe_load(text)
jobs = wf["jobs"]

# 1. js-checks exists and gates the certification report.
assert "js-checks" in jobs, "js-checks job missing"
assert jobs["js-checks"]["uses"] == "./.github/workflows/_js.yml"
assert "js-checks" in jobs["certification-report"]["needs"], "js-checks not gating the report"

# 2. The cron list, the run-name map and the shell case statement must agree.
#    `wf[True]` is the `on:` key -- YAML 1.1 parses bare `on` as the boolean True.
crons = {entry["cron"] for entry in wf[True]["schedule"]}
run_name_map = dict(re.findall(r"github\.event\.schedule == '([^']+)' && '([^']+)'", text))
case_map = dict(re.findall(r"'(\d+ \d+ \* \* [\d,]+)'\)\s*\n\s*echo \"library-name=([a-z0-9-]+)\"", text))

assert crons == set(run_name_map), f"cron vs run-name mismatch: {crons ^ set(run_name_map)}"
assert crons == set(case_map), f"cron vs case mismatch: {crons ^ set(case_map)}"
assert run_name_map == case_map, f"run-name and case disagree: {set(run_name_map.items()) ^ set(case_map.items())}"

# 3. The new package is reachable from the schedule and from manual dispatch.
assert run_name_map["0 12 * * 2,4"] == "saf-projects-dashboard"
choices = wf[True]["workflow_dispatch"]["inputs"]["library-name"]["options"]
assert "saf-projects-dashboard" in choices, "missing from dispatch choices"

print(f"certification.yml consistent across {len(crons)} schedule slots")
PY
```

Expected: `certification.yml consistent across 13 schedule slots`

There were 12 slots before this change (`0 0`–`0 3` on days `1,3,5`, and `0 4`–`0 11` on days
`2,4`). A count other than 13 means a cron, a `run-name` line or a `case` branch was missed.

- [ ] **Step 8: Confirm the package is not treated as a Moon package**

Run:

```bash
grep -n "saf-projects-dashboard" .github/workflows/certification.yml | grep -i "contains(" || echo "PASS: not in any contains() Moon list"
```

Expected: `PASS: not in any contains() Moon list`

- [ ] **Step 9: Run pre-commit and commit the reformat**

Run:

```bash
uv run --with pre-commit==4.6.0 pre-commit run --files .github/workflows/certification.yml
```

Expected: re-run until every hook `Passed`.

- [ ] **Step 10: Commit**

```bash
git add .github/workflows/certification.yml
git commit -m "ci(feat): certify saf-projects-dashboard on a scheduled slot

Refs #80"
```

---

## Task 7: Wire the release workflow and the test-workflow dispatch list

Two small choice-list additions. They are grouped because neither has a test cycle of its own and both are pure `workflow_dispatch` ergonomics.

**Files:**
- Modify: `.github/workflows/ci_cd_release.yml:19-31` (`library` choices)
- Modify: `.github/workflows/_test.yml:19-32` (`package-name` choices)

**Interfaces:**
- Consumes: nothing.
- Produces: `saf-projects-dashboard` selectable in both workflows' manual-dispatch dropdowns. The release workflow's `workflow_call`-driven jobs are already name-agnostic.

- [ ] **Step 1: Add the package to the release workflow's library choices**

In `.github/workflows/ci_cd_release.yml`, append to the `library` `options:` list:

```yaml
          - saf-testing
          - saf-projects-dashboard
```

Do **not** modify the three `contains('bdm-python-api,bdm-python-shared-volume,saf-iam-oidc,saf-product-configuration', inputs.library)` expressions at lines 265, 269 and 272. Leaving them alone is what routes the package down the Poetry branch of `_build.yml` and gives its wheel artifact the correct `-artifacts` suffix.

- [ ] **Step 2: Add the package to the shared test workflow's dispatch choices**

In `.github/workflows/_test.yml`, add to the `package-name` `options:` list, keeping `examples` last:

```yaml
          - saf-testing
          - saf-projects-dashboard
          - examples
```

- [ ] **Step 3: Verify both choice lists and that the release workflow still treats the package as Poetry**

Run:

```bash
uv run --with pyyaml==6.0.3 python -c "
import yaml, pathlib
rel = yaml.safe_load(pathlib.Path('.github/workflows/ci_cd_release.yml').read_text(encoding='utf-8'))
tst = yaml.safe_load(pathlib.Path('.github/workflows/_test.yml').read_text(encoding='utf-8'))
assert 'saf-projects-dashboard' in rel[True]['workflow_dispatch']['inputs']['library']['options']
assert 'saf-projects-dashboard' in tst[True]['workflow_dispatch']['inputs']['package-name']['options']
print('release and test dispatch lists updated')
"
```

Expected: `release and test dispatch lists updated`

Then confirm no Moon list picked the package up:

```bash
grep -n "saf-projects-dashboard" .github/workflows/ci_cd_release.yml | grep -i "contains(" || echo "PASS: not in any contains() Moon list"
```

Expected: `PASS: not in any contains() Moon list`

- [ ] **Step 4: Run pre-commit and commit the reformat**

Run:

```bash
uv run --with pre-commit==4.6.0 pre-commit run --files .github/workflows/ci_cd_release.yml .github/workflows/_test.yml
```

Expected: re-run until every hook `Passed`.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci_cd_release.yml .github/workflows/_test.yml
git commit -m "ci(feat): allow releasing and test-dispatching saf-projects-dashboard

Refs #80"
```

---

## Task 8: Whole-change verification

A final gate before opening the PR. Nothing here changes behaviour; it proves the previous seven tasks compose.

**Files:**
- No production changes. Only fixes to defects this task surfaces.

**Interfaces:**
- Consumes: everything from Tasks 1-7.
- Produces: a verified branch ready for PR.

- [ ] **Step 1: Run the full matrices test suite**

Run:

```bash
uv run .github/actions/ci-cd-job-matrices/test_ci_cd_job_matrices.py
```

Expected: all tests pass, 0 failures. This is the same command the `run-tests-actions` job runs in CI, and that job will fire on this PR because `.github/actions/ci-cd-job-matrices/**` changed.

- [ ] **Step 2: Simulate the matrices the CI will actually produce**

This is the highest-value check in the plan: it proves the package lands in exactly the matrices it should, and in none that it should not.

Run:

```bash
uv run --with pytest==8.3.4 python -c "
import json, os, subprocess, sys, tempfile, pathlib

with tempfile.TemporaryDirectory() as d:
    out = pathlib.Path(d) / 'out.txt'
    summary = pathlib.Path(d) / 'summary.md'
    out.touch()
    summary.touch()
    env = {
        **os.environ,
        'GITHUB_OUTPUT': str(out),
        'GITHUB_STEP_SUMMARY': str(summary),
        'PR_CHANGES_JSON': json.dumps(['saf-projects-dashboard']),
    }
    subprocess.run(
        [sys.executable, '.github/actions/ci-cd-job-matrices/ci_cd_job_matrices.py'],
        env=env, check=True,
    )

    outputs, lines, i = {}, out.read_text(encoding='utf-8').splitlines(), 0
    while i < len(lines):
        name = lines[i].split('<<')[0]
        i += 1
        start = i
        while lines[i] != 'EOF':
            i += 1
        outputs[name] = '\n'.join(lines[start:i])
        i += 1

expected_present = [
    'packages_matrix', 'poetry_packages_matrix', 'js_packages_matrix',
    'code_style_matrix', 'compatibility_matrix', 'tests_matrix',
]
for key in expected_present:
    assert 'saf-projects-dashboard' in outputs[key], f'missing from {key}'

assert outputs['moon_packages_matrix'] == '{}', 'must not be a Moon package'
assert outputs['tests_generated_solution_flag'] == 'false'

style = json.loads(outputs['code_style_matrix'])['include'][0]
assert style['poetry-install-args'] == '--with tests,style --all-extras', style
assert style['target-directory'] == 'packages/saf-projects-dashboard', style

tests = json.loads(outputs['tests_matrix'])['include']
assert len(tests) == 1, tests
assert tests[0]['tests-groups-file-path'] == (
    '.github/workflows/tests_groups_definitions/saf-projects-dashboard.json'
), tests
assert tests[0]['working-directory'] == 'packages/saf-projects-dashboard', tests

print('all matrices correct for a saf-projects-dashboard-only change')
"
```

Expected: `all matrices correct for a saf-projects-dashboard-only change`

- [ ] **Step 3: Confirm an unrelated change leaves the JS matrix empty**

Proves `_js.yml` stays inert for the other 12 packages, which is the core promise of the design.

Run:

```bash
uv run python -c "
import json, os, subprocess, sys, tempfile, pathlib

with tempfile.TemporaryDirectory() as d:
    out = pathlib.Path(d) / 'out.txt'
    summary = pathlib.Path(d) / 'summary.md'
    out.touch()
    summary.touch()
    subprocess.run(
        [sys.executable, '.github/actions/ci-cd-job-matrices/ci_cd_job_matrices.py'],
        env={
            **os.environ,
            'GITHUB_OUTPUT': str(out),
            'GITHUB_STEP_SUMMARY': str(summary),
            'PR_CHANGES_JSON': json.dumps(['glow-engine', 'saf-cli']),
        },
        check=True,
    )
    text = out.read_text(encoding='utf-8')

assert 'js_packages_matrix<<EOF\n{}\nEOF' in text, 'js matrix should be empty'
assert 'saf-projects-dashboard' not in text, 'dashboard leaked into an unrelated change'
print('js_packages_matrix is empty for non-Node packages')
"
```

Expected: `js_packages_matrix is empty for non-Node packages`

- [ ] **Step 4: Run pre-commit across every file this branch touched**

Run:

```bash
uv run --with pre-commit==4.6.0 pre-commit run --files $(git diff --name-only origin/main...HEAD)
```

Expected: every hook `Passed`. If `yamlfmt` reformats anything, commit the result and re-run.

- [ ] **Step 5: Verify the Jest and build commands actually work locally**

CI is the first place these run otherwise. From the package directory:

```bash
cd packages/saf-projects-dashboard
npm ci
npm test
```

Expected: Jest runs the 12 suites under `src/ts/__tests__/` and reports all passing.

Then verify the freshness gate would pass on a clean checkout:

```bash
poetry install --with build
poetry run npm run build
cd ../..
git diff --exit-code -- packages/saf-projects-dashboard/src
```

Expected: `git diff` exits 0 with no output. **If it reports changes, the committed bundle is already stale** — regenerate it, commit the regenerated output as a separate `ci(fix):` commit, and note it in the PR description. Do not weaken the gate in `_js.yml` to make it pass.

- [ ] **Step 6: Confirm the wheel contains the JS payload**

The design relies on Poetry packaging committed, non-Python files. Verify rather than assume — the package's `.gitignore` influences what Poetry includes.

```bash
cd packages/saf-projects-dashboard
poetry build --format wheel
uv run --with wheel python -c "
import glob, zipfile
wheel = sorted(glob.glob('dist/*.whl'))[-1]
names = set(zipfile.ZipFile(wheel).namelist())
required = [
    'ansys_saf_projects_dashboard/ansys_saf_projects_dashboard.js',
    'ansys_saf_projects_dashboard/proptypes.js',
    'ansys_saf_projects_dashboard/metadata.json',
    'ansys_saf_projects_dashboard/package-info.json',
    'ansys_saf_projects_dashboard/ProjectsDashboard.py',
]
missing = [r for r in required if r not in names]
assert not missing, f'wheel is missing: {missing}'
assert any(n.endswith('.ttf') for n in names), 'wheel is missing the bundled fonts'
print(f'{wheel} contains the full JS payload')
"
cd ../..
```

Expected: a line confirming the wheel contains the full JS payload.

If any file is missing, the fix belongs in `packages/saf-projects-dashboard/pyproject.toml` (an explicit `include` under `[tool.poetry]`), not in the workflows.

- [ ] **Step 7: Clean up build artifacts and confirm the tree is clean**

```bash
rm -rf packages/saf-projects-dashboard/dist
git status --short
```

Expected: no output from `git status --short`. `node_modules/` and `dist/` are already covered by `packages/saf-projects-dashboard/.gitignore`.

- [ ] **Step 8: Push and open the pull request**

```bash
git push -u origin chore/80-enable-cicd-actions-for-saf-projects-dashboard-package
```

Then open the PR with a title matching the semantic-PR convention enforced by `lint-pr-title`, for example `ci(feat): enable CI/CD for saf-projects-dashboard`, and a description that closes #80.

The PR description must record these three items, because they are deliberate scope decisions a reviewer will otherwise flag as gaps:

1. Documentation is deferred — `doc/source` was never migrated into `packages/saf-projects-dashboard/`, so the package is intentionally absent from `_doc.yml` and `.github/changes_doc_filters.yaml`. Follow-up issue required.
2. Moon/uv conversion is deferred — the package stays on Poetry. Follow-up issue required.
3. A **PyPI trusted-publisher entry for `ansys-saf-projects-dashboard`** must be configured (scoped to `ansys/saf`, workflow `ci_cd_release.yml`, environment `saf-release`) before the first stable release. Not needed before merge, but `release-to-pypi` will fail without it.

- [ ] **Step 9: Confirm the expected jobs ran green on the PR**

Check the PR's checks list and the `ci-cd-config` job summary. The summary prints every matrix as JSON; confirm `saf-projects-dashboard` appears in `packages_matrix`, `code_style_matrix`, `tests_matrix` and `js_packages_matrix`, and does **not** appear in `moon_packages_matrix`.

These jobs must all be present and passing:

| Job | Why it matters |
| --- | --- |
| `code-style` | Proves the `--with tests,style` argument from Task 1 was necessary and correct |
| `run-tests` (Linux and Windows) | Proves the tests-group JSON and marker filter work |
| `js-checks / js-test` | Jest suites |
| `js-checks / js-build` | webpack build and freshness gate |
| `build-wheel` | Poetry branch of `_build.yml` |
| `check-wheel-can-be-pip-installed` | Artifact name resolves to `saf-projects-dashboard-<pyver>-artifacts` |
| `vulnerabilities` | `pip-audit` over the Poetry lock |
| `check-dependencies-licenses` | License allowlist |
| `sbom` | CycloneDX export |
| `run-tests-actions` | The matrices test suite from Tasks 1-2 |
| `github-workflows-lint` | `actionlint` over the new and edited workflows; gated on the `devops` label, which this PR earns automatically |
| `ci-result` | Aggregate gate, must include `js-checks` |

- [ ] **Step 10: Smoke-test certification on the branch**

The certification path is not exercised by the PR checks, so trigger it manually once before merge.

Run `certification.yml` via `workflow_dispatch` on this branch with `library-name: saf-projects-dashboard`.

Expected: the run label reads `Certify: saf-projects-dashboard`; a `js-checks` leg appears; the certification summary table contains a `| JavaScript checks | success |` row. `post-certification` will skip because the branch is neither `main` nor `release/**` — that is correct, not a failure.
