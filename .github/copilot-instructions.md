# Overview

The **Solution Application Framework (SAF)** is a Python-based toolkit for creating production-ready simulation web applications. It gives method developers and engineers the building blocks to turn complex, multi-domain simulation workflows into guided, shareable web apps — without needing to become full-stack software engineers.

At its core, SAF provides the **Guided Low-Code Workflow (GLOW)** engine — a Python framework that abstracts complex backend operations, orchestrates Ansys product integrations, and exposes a unified API for building, running, and managing solution applications.

# Key capabilities

- **Templated, production-ready apps** with batteries-included project structure, dependency management, and observability
- **Desktop-ready** with code encryption, standalone executable installers, and fully offline installation
- **Native Ansys ecosystem integration** with PyAnsys SDKs, HPC Platform Services (HPS), Minerva, and the Data Repository STC
- **Open architecture** — use any frontend framework (Dash, React, Angular) and connect to third-party software via REST APIs
- **Flexible deployment** — write once, deploy anywhere (desktop, on-premises, or cloud) without changing source code

# Repository model

- SAF is a Python monorepo. Thirteen packages under `packages/` are members of the root uv workspace; `packages/saf-sdk/` is a separate meta-package and is not a workspace member.
- The root project is a workspace/tooling configuration, not a publishable package. Package behavior, dependencies, supported Python versions, and task definitions can differ; check the affected package's `pyproject.toml` and `moon.yml`.
- The root workspace supports Python 3.11 and newer, below Python 4. CI exercises Python 3.11–3.14, but check an individual package's declared support before relying on a version.

# Repository layout

```
saf/
├── .github/
│   ├── actions/                      # Composite actions and helper scripts
│   ├── ISSUE_TEMPLATE/
│   ├── scripts/
│   └── workflows/
│       ├── tests_groups_definitions/ # JSON configs that split package tests into CI matrix groups
│       ├── ci_cd_pr.yml
│       ├── ci_cd_release.yml
│       ├── ci_cd_meta_package.yml    # SAF SDK meta-package workflow
│       ├── certification.yml
│       ├── _build.yml
│       ├── _doc.yml
│       ├── _test.yml
│       ├── _test_generated_solution.yml
│       └── build-release.yml         # Placeholder required by generated-solution tests; keep the filename unchanged
├── .moon/                            # Moon workspace and shared tasks
├── benchmarks/
├── doc/                              # Root Sphinx docs and Vale configuration
│   ├── source/
│   └── styles/config/vocabularies/ANSYS/accept.txt
├── examples/                         # Standalone example solution project
├── LICENSES/
├── packages/                         # 14 package directories
│   ├── bdm-python-api/
│   ├── bdm-python-shared-volume/
│   ├── dash-super-components/
│   ├── glow-engine/
│   ├── saf-cli/
│   ├── saf-desktop-installer/
│   ├── saf-desktop-orchestrator/
│   ├── saf-iam-oidc/
│   ├── saf-product-configuration/
│   ├── saf-product-manager/
│   ├── saf-projects-dashboard/
│   ├── saf-sdk/                      # Separate meta-package, outside root uv workspace
│   ├── saf-templates/
│   └── saf-testing/
├── scripts/
├── .gitleaks.toml                    # Gitleaks custom rules and narrow test-fixture allowlists
├── .pre-commit-config.yaml           # Repository-wide governance hooks
├── pyproject.toml                    # Root uv workspace and shared tooling
├── README.md
├── SECURITY.md
└── uv.lock
```

The 13 packages other than `saf-sdk` are members of the root uv workspace. Package contents vary; most have their own `src/`, `tests/`, `pyproject.toml`, and `moon.yml`, but do not assume every package has the same files or layout.

The JSON files in `.github/workflows/tests_groups_definitions/` define the test matrix for the reusable `.github/workflows/_test.yml` workflow. Each entry describes a test group, including pytest arguments and markers, runner selection, and any required runner setup or optional integrations. Package-specific variants (such as `-extended` or product-integration configs) let CI run different test subsets and environments independently. Update the appropriate configuration when changing how a package's CI tests are partitioned or provisioned.

# Development and validation

## Prerequisites

- **Long paths** must be enabled (`git config --global core.longpaths true`; also enable in Windows registry).
- **Moon**: [Moon Documentation](https://moonrepo.dev/docs/install#windows)

- Use uv for the workspace and Moon for the repository's CI-aligned tasks. Do not assume Poetry-based instructions apply to workspace packages. The separate `saf-sdk` meta-package has its own workflow and packaging configuration.
- From the repository root, use the relevant Moon task rather than reproducing CI commands manually:

  ```text
  moon run root:uv-sync -- --all-groups
  moon run root:pre-commit
  moon run <package>:test -- [pytest arguments]
  moon run <package>:pre-commit
  moon run root:build-doc
  ```

- Run checks for the package and files you changed. Root pre-commit covers repository-level files; package pre-commit covers that package. CI definitions and shared task implementations are in `.github/workflows/` and `.moon/`.
- Some tasks require `UV_PYTHON` and `MOON_PYTHON_VERSION`; use the Python version configured by the task or CI.

## Code conventions

- Follow the affected package's configuration first. Root Ruff defaults to a 120-character line length and Python 3.12 syntax; package configurations may add or override rules.
- Use the project's configured type checker, security checks, and tests rather than assuming every package shares identical strictness or dependencies.
- Public Python APIs use numpydoc-style documentation where the package follows that convention. Preserve established package naming, exports, and test patterns.
- Use `pathlib.Path` for filesystem paths where practical.
- The project is Apache-2.0 licensed. The root license-header hook applies to `.py`, `.bat`, `.html`, `.css`, and `.proto` files and uses `start_year=2026`; follow the applicable package and hook configuration.

## Where to look

- `pyproject.toml` and `uv.lock`: workspace dependencies and shared tooling.
- `.moon/` and `packages/<package>/moon.yml`: shared and package-specific tasks.
- `packages/<package>/pyproject.toml`: package metadata, dependencies, and tool settings.
- `.github/workflows/`: CI, release, test, documentation, and SDK meta-package workflows.
