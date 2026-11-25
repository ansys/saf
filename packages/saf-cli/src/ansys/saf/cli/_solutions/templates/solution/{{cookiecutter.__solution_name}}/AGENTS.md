# AGENTS guidelines for this repository

## Project overview

This repository contains **{{ cookiecutter.__solution_display_name }}**, a Solution Application Framework (SAF) *solution*.

A SAF solution is a simulation-driven application built on top of the Solution Application Framework. It couples a
Python backend (built with the **GLOW** engine) that defines the solution's data model, transaction methods, and
step orchestration, with an optional frontend that renders the solution's graphical user interface.
{%- if cookiecutter.__ui_framework == "dash" %}
The user interface of this solution is implemented with **Dash** and served by the Solution UI server, letting the UI
be authored in Python.
{%- else %}
This solution was generated without a bundled UI framework (`--ui-framework none`). Only the backend
(the GLOW API server and its transaction methods) is provided; any UI is expected to be integrated separately or the
solution is intended to be consumed exclusively through its REST API.
{%- endif %}

A solution is composed of:

- A **solution definition** (the top-level `{{ cookiecutter.__solution_definition_class_name }}` class, a subclass of
  `ansys.saf.glow.solution.Solution`) that declares the projects, steps, and shared data model.
- One or more **steps**, each with its own data model and transaction methods.
{%- if cookiecutter.__ui_framework == "dash" %}
- **UI code** that consumes the GLOW REST API exposed by the solution.
{%- endif %}

This solution is managed with **SAF CLI** (`saf`). SAF CLI automatically activates the solution's virtual environment
and sets the solution root as the working directory when it runs commands. You typically don't need to activate the
virtual environment manually or invoke Python/UV directly — prefer running tasks via `saf`.

## Folder structure

- `src/{{ cookiecutter.__solution_namespace_path }}/{{ cookiecutter.__solution_module_name }}/`: Solution source code
  (solution definition, steps, and, when applicable, UI code).
- `tests/`: pytest tests.
- `doc/`: Sphinx documentation sources.
- `examples/`: Example scripts and usage snippets.
- `deployments/`: Deployment recipes (Docker Compose files for standalone, HPS, Minerva, and distributed setups).
- `pyproject.toml`, `uv.lock`: Dependency and build configuration (UV). Never edit `uv.lock` by hand;
  regenerate it via `saf execute {{ cookiecutter.__solution_name }} "uv lock"`.
- `.pre-commit-config.yaml`, `tox.ini`, `.flake8`: Code quality configuration.

## Key technologies and tools

- **Python {{ cookiecutter.__python_version }}**, **UV** for dependencies.
- **GLOW** (`ansys-saf-glow-engine`): backend engine that powers the solution.
{%- if cookiecutter.__ui_framework == "dash" %}
- **Dash**: Python UI framework used by this solution.
{%- endif %}
- **pytest** for tests, **Sphinx** for docs.
- **tox**, **pre-commit**, **black**, **isort**, **flake8**, **pydocstyle**, **codespell** for style and quality.

## Working with SAF CLI

Target this solution by its name (`{{ cookiecutter.__solution_name }}`), or omit the name when the current working
directory is the solution root. For any command, `saf <command> --help` lists the supported options.

### Install / reinstall the solution environment

```bash
saf install {{ cookiecutter.__solution_name }} -d all       # install with all dependency groups
saf install {{ cookiecutter.__solution_name }} -d <group>   # single group: doc, build, tests, style
saf install {{ cookiecutter.__solution_name }} -d all -f    # force a clean reinstall
```

### Run commands in the solution environment

Any command that must run inside the solution's virtual environment (uv, pytest, sphinx-build, tox, ...) **must**
be wrapped with `saf execute`:

```bash
saf execute {{ cookiecutter.__solution_name }} "<command>"
```

Common tasks:

```bash
saf execute {{ cookiecutter.__solution_name }} "pytest tests"
saf execute {{ cookiecutter.__solution_name }} "sphinx-build doc/source doc/build/html --color -vW -bhtml"
saf execute {{ cookiecutter.__solution_name }} "tox -e style"
saf execute {{ cookiecutter.__solution_name }} "uv add <package>"
saf execute {{ cookiecutter.__solution_name }} "uv add --group <group> <package>"
saf execute {{ cookiecutter.__solution_name }} "uv add --index <index> <package>"
saf execute {{ cookiecutter.__solution_name }} "uv lock"
```

### Run the solution

```bash
saf run {{ cookiecutter.__solution_name }}           # default run
saf run {{ cookiecutter.__solution_name }} --debug   # debug mode
saf run {{ cookiecutter.__solution_name }} --no-ui   # backend only (useful for API-level checks)
```

Additional flags (`--portal`, `--browser`, `--project`, `--env-file`) exist for interactive use; see
`saf run --help`.

### Adding a step

Steps are scaffolded from templates managed by the SAF Templates package (built-in templates plus any installed
plugins). List every template available in the current environment with:

```bash
saf templates
```

{%- if cookiecutter.__ui_framework == "dash" %}
The step's `--ui-framework` must match this solution's (`dash`), or be `none`. Pass `--template <template-name>` to
pick a specific template (from `saf templates`); omit it to be prompted interactively:

```bash
saf add-step {{ cookiecutter.__solution_name }} --step-name <step-name> --ui-framework dash --template <template-name>
saf add-step {{ cookiecutter.__solution_name }} --step-name <step-name> --ui-framework none --template <template-name>
```
{%- else %}
This solution was created with `--ui-framework none`, so all steps must use the same value. Pass
`--template <template-name>` to pick a specific template (from `saf templates`); omit it to be prompted interactively:

```bash
saf add-step {{ cookiecutter.__solution_name }} --step-name <step-name> --ui-framework none --template <template-name>
```
{%- endif %}

### Build / archive

Producing installers (`saf build`, with `--offline-package`, `--python-version`, `--encrypt`) and archives
(`saf archive`) is typically part of a release workflow. See `saf build --help` and `saf archive --help`.

## Coding standards

- Follow **PEP 8**. Line length is **120** characters; use the full width when it improves readability.
- Use **type hints** on all public functions, methods, and class attributes.
- Write docstrings in **numpydoc** format for all public APIs.
- Add or update **pytest tests** together with any code change that affects behavior. If tests are not added,
  proactively list the use cases (inputs, expected outcomes, edge cases) that should be covered — not the test
  implementation — so the user can decide what to test next.
- Never bypass pre-commit hooks (do not use `--no-verify`). Fix the underlying issue instead.

## Adding dependencies

When introducing a new dependency:

- **Never edit `pyproject.toml` directly** to add, remove, or change a dependency, its version, or its group. Do not
  edit `uv.lock` by hand either.
- Always add, remove, or update dependencies through `saf execute {{ cookiecutter.__solution_name }} "uv <cmd> ..."`
  (for example `uv add`, `uv remove`, `uv lock`) so `pyproject.toml` and `uv.lock` stay consistent.

When there are several candidates that solve the same problem, flag maintenance status (recent releases, active issue
tracker) and known security advisories (PyPI / OSV) to the user so they can pick informed. Do not silently reject a
package on these grounds.

## Git and contribution workflow

- Branch naming: `feature/`, `bugfix/`, `hotfix/`, `refactor/`.
- Commit messages: conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`).
- Pull requests: focused, reasonably sized, with descriptive titles and links to related issues.
- All code must pass pre-commit hooks and CI before merging.

## Troubleshooting

- Inspect any command's options with `saf <command> --help`.
- If the environment appears broken, force a clean reinstall:
  `saf install {{ cookiecutter.__solution_name }} -d all -f`.
- For private PyPI access issues, verify UV's index and credentials configuration for the relevant private source.
