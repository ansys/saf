# Solution Application Framework (SAF)

**Build and deploy powerful simulation web apps at scale.**

## What is SAF?

The Solution Application Framework is a Python-based toolkit for creating production-ready simulation web applications. It gives method developers and engineers the building blocks to turn complex, multi-domain Ansys simulation workflows into guided, shareable web apps — without needing to become full-stack software engineers.

Whether you're packaging enterprise simulation expertise into a repeatable workflow or democratizing advanced physics modeling for non-expert users, SAF provides the architecture, tooling, and integrations to get you there.

---

## Value Proposition

<table>
  <tr>
    <td>🚀</td>
    <td><strong>Templated, Production-Ready Apps</strong></td>
    <td>Hit the ground running with app templates that come batteries-included: project structure, dependency management, database setup, containerization, observability, and more. Spend less time on scaffolding and more time on what matters — your simulation logic.</td>
  </tr>
  <tr>
    <td>💻</td>
    <td><strong>Desktop-Ready</strong></td>
    <td>Deliver desktop-class experiences with built-in support for code encryption and obfuscation, standalone executable installers, and fully offline installation — protecting your IP while keeping deployment frictionless.</td>
  </tr>
  <tr>
    <td>🔗</td>
    <td><strong>Native Ansys Ecosystem Integration</strong></td>
    <td>Out-of-the-box integration with Ansys products and Shared Technology Components, PyAnsys SDKs, job submission via HPC Platform Services (HPS), and enterprise data management via Ansys Minerva and the Data Repository STC. Leverage the full power of the Ansys ecosystem from within your app.</td>
  </tr>
  <tr>
    <td>🏗️</td>
    <td><strong>Open Architecture</strong></td>
    <td>Built on a modern microservices architecture, SAF imposes no lock-in. Use any frontend framework — React, Angular, Dash, or your own. Connect to third-party software via REST APIs. Every app is generated from well-defined templates, ensuring a consistent and extensible architecture from day one.</td>
  </tr>
  <tr>
    <td>☁️</td>
    <td><strong>Flexible Deployment</strong></td>
    <td>Write your app once and deploy it anywhere — desktop, on-premises, or cloud — without changing a single line of source code. SAF abstracts away the infrastructure so you can focus on the simulation logic.</td>
  </tr>
</table>

---

## Components Overview

| **Category** | **Component** | **Description** |
| --------------------------| ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **Runtime Engine**        | GLOW Engine               | The central application runtime |
| **Product Integration**   | Product Manager           | Provides managers for interacting with Ansys products |
|                           | Product Configuration     | Provides configurations and wrappers for launching Ansys products |
| **Developer Experience**  | CLI                       | Command line interface to manage solution applications |
|                           | Solutions Manager         | VS Code extension to ease the developer's experience |
|                           | Testing                   | Provides fixtures to test a solution application |
|                           | Templates                 | Step templates for solution customization |
| **UI components**         | Super Components for Dash | Pre-assembled, high-level UI components for simulation web apps |
| **Infrastructure**        | BDM Python API            | Set of Python abstract base classes and models that comprise the interface between application code and services implementing BDM. |
|                           | BDM Shared Volume         | Provides a blob management service. |
|                           | IAM OIDC                  | Provides oauth2 and openid connect features.  |
| **Desktop**               | Desktop Orchestrator      | Orchestrates the startup of the services in desktop. |
|                           | Desktop Installer         | Generates a distributable desktop installer of a solution application. |

## Contribute

### Prerequisites

#### Enable long paths

In order to clone this repository you need to enable long paths on git:

```bash
git config --global core.longpaths true
git clone https://github.com/ansys/saf.git
```

You probably also need to enable long paths on Windows: [see](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation?tabs=registry#enable-long-paths-in-windows-10-version-1607-and-later)

#### Install `uv`

Root-level tasks (pre-commit, documentation) use [`uv`](https://docs.astral.sh/uv/). Install it once globally:

```bash
pip install uv
```

#### Install `Poetry`

Package-level tasks (dependency management, tests, code style) use [Poetry](https://python-poetry.org/). Install it once globally. See the official [installation instructions](https://python-poetry.org/docs/#installing-with-the-official-installer).

---

### Root-level tasks

The following commands run from the **repository root** and use `uv`.

#### Run pre-commit checks

```bash
uv venv .venv --python 3.12
.venv\Scripts\activate
uv pip install pre-commit==4.6.0
uv run pre-commit run --all-files
```

### Pre-commit strategy (root vs package)

This monorepo intentionally uses two pre-commit scopes:

1. Root pre-commit (`/.pre-commit-config.yaml`) for repository-wide governance.
2. Package pre-commit (`/packages/*/.pre-commit-config.yaml`) for package-specific quality gates.

#### Why both are needed

- Root hooks validate files that are shared across the whole repository (for example, GitHub workflows, YAML formatting, secrets, and license policy).
- Package hooks validate Python quality/security with each package's own tool configuration and dependencies.
- Putting every package hook at root would make one large, slow, and brittle environment for 12 independent packages.

#### Hook ownership matrix

| Scope | Purpose | Typical hooks |
|---|---|---|
| Root | Repository policy and governance | `gitleaks`, `zizmor`, `trailing-whitespace`, `yamlfmt`, `add-license-headers` |
| Package | Package runtime/code quality | `ruff-check`, `ruff-format`, `pyright`, `bandit`, `poetry-check`, package-scoped `codespell`/`blacken-docs` |

#### When to run pre-commit

- Run root pre-commit when you modify root-level files (for example `.github/**`, root docs, shared configs).
- Run package pre-commit when you modify code/config in a package under `packages/<component>/`.
- Before opening a PR that touches both scopes, run both root and affected package checks.

#### How to run pre-commit

Root scope: use the same command sequence shown in "Run pre-commit checks" above.

Package scope:

```bash
cd packages/<component>
poetry install --all-extras
poetry run pre-commit run --all-files
```

If a package environment does not include `pre-commit`, install it in that package venv:

```bash
cd packages/<component>
poetry install --all-extras
poetry run python -m pip install pre-commit
poetry run pre-commit run --all-files
```

#### Automation model

- Local automation: install Git hooks so checks run before commit.

```bash
# From repository root
uv run pre-commit install
```

- CI automation: root and package pre-commit checks are enforced by workflows; CI remains the source of truth.
- Recommended practice: still run local checks first to reduce CI turnaround time.

#### Build the documentation

```bash
uv sync --group doc
uv run sphinx-build doc/source doc/build/html
```

---

### Package-level tasks

Individual components live under `packages/<component>/`. Use `Poetry` to work on them.

#### Set up a component

```bash
cd packages/<component>
poetry install --all-extras
```

#### Run tests

```bash
cd packages/<component>
poetry run pytest
```

#### Run code style checks

Not all packages include `pre-commit` in their `pyproject.toml`. The dependency group varies by package:

| Group | Packages |
|-------|----------|
| `style` | glow-engine, saf-testing, dash-super-components |
| `dev` | saf-cli, saf-desktop-orchestrator, saf-product-manager, saf-product-configuration |
| *(not included)* | bdm-python-api, bdm-python-shared-volume, saf-iam-oidc, saf-desktop-installer, saf-templates |

For packages that include `pre-commit`:

```bash
cd packages/<component>

# Install the group that contains pre-commit (style or dev, see table above)
poetry install --with <style|dev> --all-extras
poetry run pre-commit run --all-files
```

For packages that do not include `pre-commit`, install it in the venv first:

```bash
cd packages/<component>
poetry install --all-extras
poetry run python -m pip install pre-commit
poetry run pre-commit run --all-files
```
