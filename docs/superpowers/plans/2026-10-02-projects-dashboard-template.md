# Projects Dashboard in the Minimal Solution Template — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `saf new` (Dash UI) generates a solution that renders `ProjectsDashboard` at `/projects`; `saf run --portal` opens there and the navbar "Back to projects" button goes there, with fallback to `ansys-saf-desktop-portal` then `ansys-saf-portal` when the dashboard is not installed.

**Architecture:** The orchestrator already picks dashboard → desktop portal → portal at runtime and sets `GLOW_PORTAL_URL` and CORS (no orchestrator changes). This plan renames the dashboard distribution to `saf-projects-dashboard`, adds a template page that registers `/projects` only when `ansys_saf_projects_dashboard` is importable, and ports the routing from ansys/saf-cli#286 into the template's `page.py` so pages registered with `project_scoped=False` render without a project.

**Tech Stack:** Python 3.11+, Dash 3 pages + `dash-extensions` (`DashProxy`, `MultiplexerTransform`), `dash-mantine-components`, GLOW `DashClient`/`callback`, cookiecutter, Poetry, pytest + Selenium (e2e).

**Spec:** `docs/superpowers/specs/2026-10-01-projects-dashboard-template-design.md`

## Global Constraints

- Runtime fallback order: `saf-projects-dashboard` → `ansys-saf-desktop-portal` → `ansys-saf-portal`. Do not remove or replace either portal.
- Distribution name: `saf-projects-dashboard`. Import name stays `ansys_saf_projects_dashboard` (the orchestrator's `PROJECTS_DASHBOARD_MODULE`).
- Projects page path: `os.getenv("SAF_DESKTOP_PROJECTS_DASHBOARD_PATH", "/projects")` — same env var and default as the orchestrator.
- A generated solution without the dashboard installed must import and behave exactly as today (`/projects` → 404, back button hidden when `GLOW_PORTAL_URL` is unset).
- Template `.env` must **not** get `GLOW_CORS_ORIGINS` (the orchestrator sets the exact UI origin).
- Private feed: `solutions-private-pypi`, `https://pkgs.dev.azure.com/ansys-solutions/_packaging/ansys-solutions/pypi/simple/`.
- Prerequisite: ansys/saf#171 (`has_portal_dependency` detects `saf-projects-dashboard`). No installer changes here.
- Every routing helper must keep `GLOW_UI_PATH_PREFIX` support: strip with `dash.strip_relative_path`, build with `dash.get_relative_path`.
- `page.py` must **never import** `projects_page`. Dash's pages-folder loader imports every `ui/pages/*.py` containing `register_page` under its own module name (`pages.projects_page`); a second import by package path would register `/projects` twice. `page.py` finds the dashboard page through `dash.page_registry` (`projects_dashboard=True`).
- Run saf-cli tests from `packages/saf-cli` with its Poetry env: `poetry install --with tests` once, then `poetry run pytest ...`.

## Deviations from the spec (found while planning)

- **No `ui/app.py` change.** Dash already imports `projects_page.py` from the pages folder; importing it again in `app.py` (as #286 did) would double-register the page.
- **No change to `tests/unit/mocks/solutions/solution_with_dash_ui`.** That mock is only used by add-step/backup/archiver tests, which never touch page routing. Routing is tested against the real scaffolded template in `tests/unit/test_solution_ui_routing.py`.
- **Private source priority is `explicit`, not `supplemental`.** Only `saf-projects-dashboard` is resolved from the private feed, so no other dependency can be shadowed by it.
- **Fixes a #286 bug:** after visiting `/projects`, returning to the *same* project URL did not re-render it (the stored pathname was never reset). `resolve_project_scoped_pathname` now resets it on non-solution pages.

## File Map

| File | Change | Responsibility |
|---|---|---|
| `packages/saf-projects-dashboard/pyproject.toml` | Modify | Distribution name |
| `packages/saf-projects-dashboard/README.rst` | Modify | Install/PyPI references |
| `doc/source/user_guide/components.rst` | Modify | Package name references |
| `packages/saf-cli/src/ansys/saf/cli/_solutions/templates/solution/{{cookiecutter.__solution_name}}/pyproject.toml` | Modify | Private source + dashboard dependency (Dash only) |
| `.../{{cookiecutter.__solution_name}}/lock_files/dash/poetry.lock` | Regenerate | Locked dashboard |
| `.../ui/pages/projects_page.py` (template) | Create | Conditional `/projects` page |
| `.../ui/pages/page.py` (template) | Modify | Routing split, back button, theme sync |
| `packages/saf-cli/tests/unit/test_solution_ui_routing.py` | Modify | Routing + page unit tests |
| `packages/saf-cli/tests/unit/test_scaffolding.py` | Modify | Template dependency tests |
| `packages/saf-cli/tests/outcome_checks.py` | Modify | Expected scaffolded files |
| `packages/saf-cli/tests/e2e/saf_process.py`, `tests/e2e/conftest.py`, `tests/e2e/test_run_solution.py` | Modify | `--portal` with dashboard |

`.../` = `packages/saf-cli/src/ansys/saf/cli/_solutions/templates/solution/{{cookiecutter.__solution_name}}/src/{{ cookiecutter.__solution_namespace_path }}/{{cookiecutter.__solution_module_name}}`

---

### Task 1: Rename the dashboard distribution to `saf-projects-dashboard`

**Files:**
- Modify: `packages/saf-projects-dashboard/pyproject.toml:6`
- Modify: `packages/saf-projects-dashboard/README.rst:9-14,47`
- Modify: `doc/source/user_guide/components.rst:228,390`

**Interfaces:**
- Produces: a wheel `saf_projects_dashboard-<version>-py3-none-any.whl` that installs the module `ansys_saf_projects_dashboard` (Task 4 depends on it being published to the private feed).

Do **not** change `package.json`, `package-lock.json`, or `src/ansys_saf_projects_dashboard/package-info.json`: they are npm metadata and the Dash namespace is hardcoded (`_dash_namespace = "ansys_saf_projects_dashboard"` in `__init__.py`).

- [ ] **Step 1: Change the distribution name**

In `packages/saf-projects-dashboard/pyproject.toml`, replace:

```toml
name = "ansys-saf-projects-dashboard"
```

with:

```toml
name = "saf-projects-dashboard"
```

Leave `packages = [ { include = "ansys_saf_projects_dashboard", from = "src" } ]` unchanged.

- [ ] **Step 2: Update the README**

In `packages/saf-projects-dashboard/README.rst`, replace every `ansys-saf-projects-dashboard` with `saf-projects-dashboard` in lines 9–14 (badge image and target URLs) and line 47 (`pip install saf-projects-dashboard`).

- [ ] **Step 3: Update the docs**

In `doc/source/user_guide/components.rst`:
- line 228: `- **Package name**: ``saf-projects-dashboard```
- line 390: `* ``saf-projects-dashboard`` (see :ref:`components_projects_dashboard`)`

- [ ] **Step 4: Verify the lock file is still valid and build the wheel**

Run from `packages/saf-projects-dashboard`:

```bash
poetry check --lock
poetry build -f wheel
python -m zipfile -l dist/saf_projects_dashboard-0.1.dev0-py3-none-any.whl | grep "ansys_saf_projects_dashboard/__init__.py"
```

Expected: `poetry check` prints `All set!` (if it reports the lock is outdated, run `poetry lock` and re-check); the wheel `dist/saf_projects_dashboard-0.1.dev0-py3-none-any.whl` exists; the `zipfile` listing shows `ansys_saf_projects_dashboard/__init__.py`.

- [ ] **Step 5: Run the dashboard unit tests**

Run from `packages/saf-projects-dashboard`: `poetry install --with tests && poetry run pytest tests/unit -v`
Expected: PASS (same results as before the rename).

- [ ] **Step 6: Commit**

```bash
git add packages/saf-projects-dashboard/pyproject.toml packages/saf-projects-dashboard/README.rst doc/source/user_guide/components.rst
git commit -m "build(projects-dashboard): rename distribution to saf-projects-dashboard"
```

- [ ] **Step 7: Publish (manual, owner: maintainer)**

Publish `saf-projects-dashboard` to the `solutions-private-pypi` feed. Task 4 Step 4 cannot run until `pip download --no-deps --pre --index-url <feed> saf-projects-dashboard` succeeds.

---

### Task 2: Conditional projects page in the template

**Files:**
- Create: `.../ui/pages/projects_page.py`
- Modify: `packages/saf-cli/tests/unit/test_solution_ui_routing.py`
- Modify: `packages/saf-cli/tests/outcome_checks.py:197`

**Interfaces:**
- Produces: when `ansys_saf_projects_dashboard` is importable, a `dash.page_registry` entry with `path == PROJECTS_DASHBOARD_PATH`, `project_scoped is False`, `projects_dashboard is True`, `name == "Projects"`, `order == -1`, and `layout(theme: str = "light")` returning `ProjectsDashboard(id="projects-dashboard", apiBaseUrl=..., solutionDescription=..., themeMode=theme)`. When not importable, no registry entry.
- Produces (tests): fixture `projects_dashboard_installed` (params `True`/`False`) reused by Task 3.

- [ ] **Step 1: Write the failing tests**

Add to the imports of `packages/saf-cli/tests/unit/test_solution_ui_routing.py`:

```python
from collections.abc import Iterator
from importlib.machinery import ModuleSpec
import importlib.util
from pathlib import Path
import sys
```

Add after `FIRST_PAGE_PATH_TEMPLATE`:

```python
PROJECTS_DASHBOARD_MODULE = "ansys_saf_projects_dashboard"
PROJECTS_PAGE_MODULE = "pages.projects_page"  # module name Dash gives to ui/pages/projects_page.py
```

Add after the `first_page_index` fixture:

```python
def get_projects_dashboard_modules() -> list[str]:
    """Return the registry keys of the projects dashboard pages."""
    page_registry: dict[str, dict[str, Any]] = dash.page_registry  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
    return [module for module, page in page_registry.items() if page.get("projects_dashboard", False)]


@pytest.fixture(params=[True, False], ids=["with_projects_dashboard", "without_projects_dashboard"])
def projects_dashboard_installed(
    request: pytest.FixtureRequest,
    solution_ui_page: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[bool]:
    """Register the projects page as Dash does, as if saf-projects-dashboard were installed or not."""
    installed = bool(request.param)
    real_find_spec = importlib.util.find_spec

    def find_spec(name: str, package: str | None = None) -> ModuleSpec | None:
        if name == PROJECTS_DASHBOARD_MODULE:
            return ModuleSpec(name, None) if installed else None
        return real_find_spec(name, package)

    page_registry: dict[str, dict[str, Any]] = dash.page_registry  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
    saved_registry = dict(page_registry)
    for module in get_projects_dashboard_modules():
        del page_registry[module]

    monkeypatch.setattr(importlib.util, "find_spec", find_spec)
    page_path = Path(str(solution_ui_page.__file__)).parent / "projects_page.py"
    spec = importlib.util.spec_from_file_location(PROJECTS_PAGE_MODULE, page_path)
    assert spec is not None and spec.loader is not None
    projects_page = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(projects_page)
    if installed:
        # Dash sets the layout of the pages it imports from the pages folder.
        page_registry[PROJECTS_PAGE_MODULE]["layout"] = projects_page.layout

    yield installed

    page_registry.clear()
    page_registry.update(saved_registry)


@pytest.fixture
def fake_projects_dashboard(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Provide a fake ansys_saf_projects_dashboard module whose component returns its arguments."""
    module = ModuleType(PROJECTS_DASHBOARD_MODULE)
    module.ProjectsDashboard = lambda **kwargs: kwargs  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, PROJECTS_DASHBOARD_MODULE, module)
    return module


def test_projects_page_registration(projects_dashboard_installed: bool):
    """Register the projects page at /projects, outside the project, only if the dashboard is installed."""
    modules = get_projects_dashboard_modules()
    if not projects_dashboard_installed:
        assert modules == []
        return
    assert modules == [PROJECTS_PAGE_MODULE]
    page = dash.page_registry[PROJECTS_PAGE_MODULE]  # pyright: ignore[reportUnknownMemberType]
    assert page["path"] == "/projects"
    assert page["name"] == "Projects"
    assert page["project_scoped"] is False


@pytest.mark.parametrize("projects_dashboard_installed", [True], indirect=True)
def test_projects_page_layout(
    projects_dashboard_installed: bool,
    fake_projects_dashboard: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
):
    """Render the dashboard with the API URL of the solution and the requested theme."""
    monkeypatch.delenv("GLOW_EXTERNAL_API_URL", raising=False)
    monkeypatch.setenv("GLOW_API_URL", "http://127.0.0.1:8000")
    layout = dash.page_registry[PROJECTS_PAGE_MODULE]["layout"]  # pyright: ignore[reportUnknownMemberType]
    kwargs = layout(theme="dark")
    assert kwargs["id"] == "projects-dashboard"
    assert kwargs["apiBaseUrl"] == "http://127.0.0.1:8000"
    assert kwargs["themeMode"] == "dark"


@pytest.mark.parametrize("projects_dashboard_installed", [True], indirect=True)
def test_projects_page_layout_prefers_external_api_url(
    projects_dashboard_installed: bool,
    fake_projects_dashboard: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
):
    """Use the external API URL when the UI is served behind a reverse proxy."""
    monkeypatch.setenv("GLOW_EXTERNAL_API_URL", "https://api.example.com")
    monkeypatch.setenv("GLOW_API_URL", "http://127.0.0.1:8000")
    layout = dash.page_registry[PROJECTS_PAGE_MODULE]["layout"]  # pyright: ignore[reportUnknownMemberType]
    assert layout()["apiBaseUrl"] == "https://api.example.com"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `poetry run pytest tests/unit/test_solution_ui_routing.py -k projects_page -v`
Expected: FAIL — `FileNotFoundError` / `No such file` for `projects_page.py` in the fixture.

- [ ] **Step 3: Create the projects page**

Create `.../ui/pages/projects_page.py`:

```python
# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Frontend of the projects dashboard page.

The page is only registered when saf-projects-dashboard is installed. Otherwise, ``saf run --portal`` falls back to
the SAF Desktop Portal, then to the SAF Portal.
"""

import importlib.util
import os

import dash

PROJECTS_DASHBOARD_MODULE = "ansys_saf_projects_dashboard"
# Keep in sync with the desktop orchestrator, which opens this path when ``--portal`` uses the projects dashboard.
PROJECTS_DASHBOARD_PATH = os.getenv("SAF_DESKTOP_PROJECTS_DASHBOARD_PATH", "/projects")

if importlib.util.find_spec(PROJECTS_DASHBOARD_MODULE) is not None:
    dash.register_page(
        __name__,
        name="Projects",
        path=PROJECTS_DASHBOARD_PATH,
        order=-1,
        project_scoped=False,  # displayed without a project, outside the navigation tree of the steps
        projects_dashboard=True,  # used by page.py to find this page without importing this module
    )


def layout(theme: str = "light"):
    """Layout of the projects dashboard page, whose theme follows the color scheme of the app."""
    from ansys_saf_projects_dashboard import ProjectsDashboard

    return ProjectsDashboard(
        id="projects-dashboard",
        apiBaseUrl=os.getenv("GLOW_EXTERNAL_API_URL") or os.getenv("GLOW_API_URL"),
        solutionDescription="{{ cookiecutter.__solution_display_name }}: view and manage your projects.",
        themeMode=theme,
    )
```

- [ ] **Step 4: Add the file to the expected scaffolded files**

In `packages/saf-cli/tests/outcome_checks.py`, after the `.../ui/pages/page.py` line (line 197), add:

```python
    f"src/{_NAMESPACE_PLACEHOLDER}/{_MODULE_PLACEHOLDER}/ui/pages/projects_page.py",
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `poetry run pytest tests/unit/test_solution_ui_routing.py tests/unit/test_scaffolding.py -v`
Expected: PASS, including the existing `test_resolve_active_page_*` and `test_open_new_page*` tests.

- [ ] **Step 6: Commit**

```bash
git add "packages/saf-cli/src/ansys/saf/cli/_solutions/templates/solution/{{cookiecutter.__solution_name}}/src" packages/saf-cli/tests/unit/test_solution_ui_routing.py packages/saf-cli/tests/outcome_checks.py
git commit -m "feat(saf-cli): add projects dashboard page to the solution template"
```

---

### Task 3: Route project-scoped and non-project pages in the template

**Files:**
- Modify: `.../ui/pages/page.py` (full replacement below)
- Modify: `packages/saf-cli/tests/unit/test_solution_ui_routing.py`

**Interfaces:**
- Consumes: registry entry from Task 2 (`project_scoped`, `projects_dashboard`, `path`, `layout(theme)`); fixture `projects_dashboard_installed`.
- Produces (callbacks in `page.py`, tested directly):
  - `resolve_active_page_and_project_information(pathname: str) -> tuple[str | None, str | None]` (unchanged signature)
  - `resolve_active_non_solution_page(pathname: str) -> str | None`
  - `resolve_project_scoped_pathname(pathname: str, current_pathname: str | None, generation: int) -> tuple[Any, Any]`
  - `render_nav_tree(active_index, active_non_solution_page_index, switch_on, navbar) -> tuple[Any, dict]`
  - `return_to_portal(pathname: str, switch_on: bool) -> list[html.A]`
  - `get_page_list(theme: str) -> list[dict[str, str | bool]]`

- [ ] **Step 1: Write the failing tests**

Add to the end of `packages/saf-cli/tests/unit/test_solution_ui_routing.py`:

```python
def get_projects_page_index() -> str:
    """Return the registry index of the projects dashboard page."""
    return str(next(i for i, page in enumerate(get_registered_pages()) if page.get("projects_dashboard", False)))


@pytest.mark.parametrize("projects_dashboard_installed", [True], indirect=True)
def test_resolve_active_non_solution_page(
    solution_ui_page: ModuleType,
    ui_path_prefix: str,
    projects_dashboard_installed: bool,
):
    """Resolve the projects page from its prefixed URL."""
    assert solution_ui_page.resolve_active_non_solution_page(f"{ui_path_prefix}/projects") == get_projects_page_index()


@pytest.mark.parametrize("projects_dashboard_installed", [True], indirect=True)
def test_resolve_active_non_solution_page_on_solution_page(
    solution_ui_page: ModuleType,
    ui_path_prefix: str,
    projects_dashboard_installed: bool,
):
    """Resolve no non-solution page on a page of a project."""
    assert solution_ui_page.resolve_active_non_solution_page(f"{ui_path_prefix}/projects/abc123/first-step") is None


def test_resolve_active_non_solution_page_without_dashboard(
    solution_ui_page: ModuleType,
    ui_path_prefix: str,
    projects_dashboard_installed: bool,
):
    """Resolve the projects page only when it is registered; otherwise /projects shows the 404 page."""
    index = solution_ui_page.resolve_active_non_solution_page(f"{ui_path_prefix}/projects")
    assert (index is not None) is projects_dashboard_installed


@pytest.mark.parametrize("projects_dashboard_installed", [True], indirect=True)
def test_resolve_active_page_and_project_information_on_projects_page(
    solution_ui_page: ModuleType,
    ui_path_prefix: str,
    projects_dashboard_installed: bool,
):
    """Resolve no solution page and no project on the projects page."""
    pathname = f"{ui_path_prefix}/projects"
    assert solution_ui_page.resolve_active_page_and_project_information(pathname) == (None, None)


def test_resolve_project_scoped_pathname_on_new_solution_page(solution_ui_page: ModuleType, ui_path_prefix: str):
    """Store the pathname and bump the generation that renders the solution page."""
    pathname = f"{ui_path_prefix}/projects/abc123/first-step"
    assert solution_ui_page.resolve_project_scoped_pathname(pathname, None, 3) == (pathname, 4)


def test_resolve_project_scoped_pathname_on_same_solution_page(solution_ui_page: ModuleType, ui_path_prefix: str):
    """Do not render the solution page again when the pathname did not change."""
    pathname = f"{ui_path_prefix}/projects/abc123/first-step"
    no_update = solution_ui_page.no_update
    assert solution_ui_page.resolve_project_scoped_pathname(pathname, pathname, 3) == (no_update, no_update)


@pytest.mark.parametrize("projects_dashboard_installed", [True], indirect=True)
def test_resolve_project_scoped_pathname_resets_on_projects_page(
    solution_ui_page: ModuleType,
    ui_path_prefix: str,
    projects_dashboard_installed: bool,
):
    """Reset the pathname on the projects page so that opening the same project again renders it."""
    previous_pathname = f"{ui_path_prefix}/projects/abc123/first-step"
    no_update = solution_ui_page.no_update
    assert solution_ui_page.resolve_project_scoped_pathname(f"{ui_path_prefix}/projects", previous_pathname, 3) == (
        None,
        no_update,
    )
    assert solution_ui_page.resolve_project_scoped_pathname(previous_pathname, None, 3) == (previous_pathname, 4)


@pytest.mark.parametrize("projects_dashboard_installed", [True], indirect=True)
def test_get_page_list_excludes_projects_page(solution_ui_page: ModuleType, projects_dashboard_installed: bool):
    """Do not list the projects page in the navigation tree of the steps."""
    item_ids = [item["id"] for item in solution_ui_page.get_page_list("light")]
    assert get_projects_page_index() not in item_ids
    assert item_ids  # the step pages are still listed


NAVBAR = {"width": 300, "breakpoint": "sm", "collapsed": {"mobile": True}}


def test_render_nav_tree_on_solution_page(solution_ui_page: ModuleType, first_page_index: str):
    """Display the navigation tree and expand the navbar on a page of a project."""
    tree, navbar = solution_ui_page.render_nav_tree(first_page_index, None, False, NAVBAR)
    assert isinstance(tree, Tree)
    assert navbar["collapsed"] == {"mobile": True, "desktop": False}
    assert navbar["width"] == 300


@pytest.mark.parametrize("projects_dashboard_installed", [True], indirect=True)
def test_render_nav_tree_on_projects_page(solution_ui_page: ModuleType, projects_dashboard_installed: bool):
    """Hide the navigation tree and collapse the navbar on the projects page."""
    tree, navbar = solution_ui_page.render_nav_tree(None, get_projects_page_index(), False, NAVBAR)
    assert not isinstance(tree, Tree)
    assert navbar["collapsed"] == {"mobile": True, "desktop": True}


def _get_back_button(children: list[Any]) -> tuple[str, str] | None:
    """Return the href and the popover text of the back-to-projects button, or None if it is hidden."""
    if not children:
        return None
    link = children[0]
    popover = link.children[1]
    return link.href, popover.children


@pytest.mark.parametrize(
    ("deployment", "expected_text"),
    [("Desktop", "Back to Projects"), ("DockerCompose", "Back to Portal")],
)
def test_return_to_portal_uses_portal_url(
    solution_ui_page: ModuleType,
    projects_dashboard_installed: bool,
    monkeypatch: pytest.MonkeyPatch,
    deployment: str,
    expected_text: str,
):
    """Link to the URL set by the orchestrator first, whichever of the dashboard and the portals it points to."""
    deployment_type = getattr(solution_ui_page.Deployment, deployment)
    monkeypatch.setattr(solution_ui_page.DashClient, "get_portal_ui_url", staticmethod(lambda: "http://portal"))
    monkeypatch.setattr(solution_ui_page.DashClient, "get_deployment_type", staticmethod(lambda: deployment_type))
    button = _get_back_button(solution_ui_page.return_to_portal("/projects/abc123", False))
    assert button == ("http://portal", expected_text)


def test_return_to_portal_without_portal_url(
    solution_ui_page: ModuleType,
    ui_path_prefix: str,
    projects_dashboard_installed: bool,
    monkeypatch: pytest.MonkeyPatch,
):
    """Link to the projects page when it is registered, otherwise hide the button."""
    monkeypatch.setattr(solution_ui_page.DashClient, "get_portal_ui_url", staticmethod(lambda: None))
    button = _get_back_button(solution_ui_page.return_to_portal(f"{ui_path_prefix}/projects/abc123", False))
    if projects_dashboard_installed:
        assert button == (f"{ui_path_prefix}/projects", "Back to Projects")
    else:
        assert button is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `poetry run pytest tests/unit/test_solution_ui_routing.py -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'resolve_active_non_solution_page'` (and `resolve_project_scoped_pathname`), `render_nav_tree` `TypeError` (wrong arg count), `test_return_to_portal_without_portal_url[with_projects_dashboard-*]` asserting `None == (...)`.

- [ ] **Step 3: Replace the template `page.py`**

Replace the full content of `.../ui/pages/page.py` with:

```python
# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Initialization of the frontend layout across all the steps."""


import importlib
import inspect
import logging
from pathlib import Path
from typing import Any, Literal
import webbrowser

from ansys.saf.glow.client import DashClient, Deployment, NotFoundException, callback
from ansys.solutions.dash_super_components import Tree
import dash
import dash_bootstrap_components as dbc
from dash_extensions.enrich import Input, Output, State, clientside_callback, dcc, html, no_update
import dash_mantine_components as dmc

from {{ cookiecutter.__solution_namespace }}.{{ cookiecutter.__solution_module_name }}.solution.definition import {{ cookiecutter.__solution_definition_class_name }}

logger = logging.getLogger(__name__)


def get_asset(asset_name: str, relative_path: str = "", theme: str = "dark") -> str:
    """Return asset URL based on the current theme."""
    path = f"{relative_path.strip('/')}/{theme}/{asset_name}"
    return dash.get_asset_url(path)


def _is_404_page(page: dict[str, Any]) -> bool:
    """Return whether the page is the custom 404 page."""
    return page["module"].split(".")[-1] == "not_found_404"


def _is_project_scoped(page: dict[str, Any]) -> bool:
    """Return whether the page belongs to a project, which is the default for the step pages.

    Pages registered with ``project_scoped=False``, such as the projects dashboard, are displayed without a project.
    """
    return page.get("project_scoped", True)


def _get_relative_pathname(pathname: str | None) -> str:
    """Return the pathname without the GLOW_UI_PATH_PREFIX part and the surrounding slashes."""
    if not pathname:
        return ""
    return dash.strip_relative_path(pathname) or ""


def _match_solution_page(pathname: str | None) -> tuple[str, dict[str, Any], str | None] | None:
    """Return the index, the page, and the project ID of the project-scoped page matching the pathname."""
    relative_pathname = _get_relative_pathname(pathname)
    path_parts = relative_pathname.split("/") if relative_pathname else []
    for i, page in enumerate(dash.page_registry.values()):
        if _is_404_page(page) or not _is_project_scoped(page) or not page.get("path_template"):
            continue
        template_parts = page["path_template"].strip("/").split("/")
        # look for same parts, excluding <project_id> variable
        if len(path_parts) != len(template_parts):
            continue
        project_id = None
        matched = True
        for tp, pp in zip(template_parts, path_parts, strict=True):
            if tp == "<project_id>":
                project_id = pp
            elif tp != pp:
                matched = False
                break
        if matched:
            return str(i), page, project_id
    return None


def _match_non_solution_page(pathname: str | None) -> str | None:
    """Return the index of the page displayed without a project that matches the pathname."""
    relative_pathname = _get_relative_pathname(pathname)
    for i, page in enumerate(dash.page_registry.values()):
        if _is_404_page(page) or _is_project_scoped(page):
            continue
        if relative_pathname == page["path"].strip("/"):
            return str(i)
    return None


def _get_projects_dashboard_page() -> dict[str, Any] | None:
    """Return the projects dashboard page, which is only registered when saf-projects-dashboard is installed."""
    for page in dash.page_registry.values():
        if page.get("projects_dashboard", False):
            return page
    return None


def get_page_list(theme: str) -> list[dict[str, str | bool]]:
    """Return the page list with icons based on the current theme and registered pages."""
    pages = []
    for i, page in enumerate(dash.page_registry.values()):
        if _is_404_page(page) or not _is_project_scoped(page):
            continue
        page_id = str(i)
        page_name = page["name"]
        icon_name = page.get("icon_asset_name", "carbon--ibm-engineering-workflow-mgmt.svg")
        icon_path = page.get("icon_asset_path", "icons")
        icon_url = get_asset(icon_name, icon_path, theme)
        pages.append({"id": page_id, "text": page_name, "icon": icon_url, "expanded": True})
    return pages


theme_toggle = dmc.Switch(
    offLabel=html.Img(src=get_asset("radix-icons--sun.svg", "icons", "light")),
    onLabel=html.Img(src=get_asset("radix-icons--moon.svg", "icons", "light")),
    id="color-scheme-switch",
    persistence=True,
    color="grey",
    checked=False,
)


header = dmc.AppShellHeader(
    dmc.Flex(
        [
            html.Img(
                id="logo-image",
                src=get_asset("placeholder_logo.png", "logos", "light"),
                height="64px",
                alt="Solution logo placeholder.",
                title="Customize this logo by modifying /ui/assets/logos/light/placeholder_logo.png",
            ),
            dmc.Group(
                [
                    dmc.Text(
                        "Project name:",
                        id="project-name",
                        size="sm",
                        style={"font-size": "16px", "color": "var(--mantine-color-text)"},
                    ),
                    theme_toggle,
                    dmc.ActionIcon(
                        html.Img(src=get_asset("teenyicons--doc-solid.svg", "icons", "light")),
                        id="access-solution-doc",
                        variant="transparent",
                        style={"color": "var(--mantine-color-text)"},
                    ),
                    dbc.Popover(
                        "Get access to the Solution's Documentation.",
                        target="access-solution-doc",
                        body=True,
                        trigger="hover",
                    ),
                    html.Div(id="return-to-portal"),
                ],
                gap=10,
            ),
        ],
        justify="space-between",
        align="center",
        direction="row",
        wrap="wrap",
        h="100%",
        px="md",
    )
)


navbar = dmc.AppShellNavbar(
    html.Div(),
    id="navbar-content",
    p="md",
)


main_layout = dmc.AppShellMain(
    html.Div(
        id="page-content",
        style={
            "padding-right": "0.7%",
            "padding-left": "0.7%",
            "backgroundColor": "var(--mantine-color-body)",
            "color": "var(--mantine-color-text)",
            "minHeight": "100vh",
        },
    )
)


layout = dmc.MantineProvider(
    [
        dmc.NotificationContainer(
            id="notification-container",
            position="bottom-left",
            notificationMaxHeight=400,
        ),
        dmc.AppShell(
            [
                header,
                navbar,
                main_layout,
            ],
            id="app-shell",
            header={"height": 70},
            navbar={
                "width": 300,
                "breakpoint": "sm",
                "collapsed": {"mobile": True},
            },
        ),
        dcc.Location(id="url", refresh="callback-nav"),
        html.Div(
            id="alerts-container", style={"position": "fixed", "top": 90, "right": 10, "width": 350, "zIndex": 1000}
        ),
        dcc.Store(id="active-page-index", data=None),
        dcc.Store(id="active-project-id", data=None),
        dcc.Store(id="active-non-solution-page-index", data=None),
        dcc.Store(id="project-scoped-pathname", data=None),
        dcc.Store(id="project-layout-generation", data=0),
    ],
    id="mantine-provider",
    defaultColorScheme="light",
)


def _get_alert_toast(message: str, level: Literal["success", "info", "warning", "danger"]) -> dbc.Toast:
    """Create a toast with the alert message."""
    content = html.Div([message], style={"font-size": "small"})
    toast = dbc.Toast(
        content,
        header=level.upper(),
        is_open=True,
        dismissable=True,
        icon=level,
        color=level,
        duration=20000,
    )

    return toast


def _get_back_to_projects_link() -> tuple[str, str] | None:
    """Return the URL and the text of the back-to-projects button, or None to hide it.

    The portal URL set by the orchestrator comes first. It points to the projects dashboard, the SAF Desktop Portal,
    or the SAF Portal, whichever is installed. Without it, the button points to the projects dashboard page if any.
    """
    portal_ui_url = DashClient.get_portal_ui_url()
    if portal_ui_url is not None:
        text = "Back to Projects" if DashClient.get_deployment_type() == Deployment.Desktop else "Back to Portal"
        return portal_ui_url, text
    projects_dashboard_page = _get_projects_dashboard_page()
    if projects_dashboard_page is not None:
        # Add GLOW_UI_PATH_PREFIX to the path returned to the browser
        return dash.get_relative_path(projects_dashboard_page["path"]), "Back to Projects"
    return None


@callback(
    Output("return-to-portal", "children"),
    Input("url", "pathname"),
    Input("color-scheme-switch", "checked"),
)
def return_to_portal(pathname: str, switch_on: bool) -> list[html.A]:
    """Display the button that returns to the projects, if any."""
    theme = "dark" if switch_on else "light"

    back_to_projects_link = _get_back_to_projects_link()
    if back_to_projects_link is None:
        return []
    href, popover_text = back_to_projects_link

    return [
        html.A(
            [
                dmc.ActionIcon(
                    html.Img(src=get_asset("carbon--return.svg", "icons", theme)),
                    id="back-to-projects-icon",
                    variant="transparent",
                ),
                dbc.Popover(
                    popover_text,
                    target="back-to-projects-icon",
                    body=True,
                    trigger="hover",
                ),
            ],
            href=href,
        )
    ]


@callback(
    Output("alerts-container", "children"),
    Input("access-solution-doc", "n_clicks"),
    prevent_initial_call=True,
)
def access_solution_documentation(n_clicks: int) -> list[dbc.Toast] | None:
    """Open the Solution's Documentation home page in the web browser."""
    solution_module = importlib.import_module("{{ cookiecutter.__solution_namespace }}.{{ cookiecutter.__solution_module_name }}")
    doc_index_path = Path(solution_module.__path__[0]) / "html-doc" / "index.html"
    if not doc_index_path.is_file():
        doc_index_path = Path.cwd() / "doc" / "build" / "html" / "index.html"
    if not doc_index_path.is_file():
        return _get_alert_toast("Solution documentation is not available.", "warning")
    logger.info(f"Opening documentation at {doc_index_path}")
    webbrowser.open_new(doc_index_path.as_posix())
    return no_update


@callback(
    Output("active-page-index", "data"),
    Output("active-project-id", "data"),
    Input("url", "pathname"),
)
def resolve_active_page_and_project_information(pathname: str) -> tuple[str | None, str | None]:
    """Resolve the active solution page index and project ID based on the current URL."""
    solution_page = _match_solution_page(pathname)
    if solution_page is None:
        return None, None
    index, _, project_id = solution_page
    return index, project_id


@callback(
    Output("active-non-solution-page-index", "data"),
    Input("url", "pathname"),
)
def resolve_active_non_solution_page(pathname: str) -> str | None:
    """Resolve the index of the active page displayed without a project based on the current URL."""
    return _match_non_solution_page(pathname)


@callback(
    Output("project-scoped-pathname", "data"),
    Output("project-layout-generation", "data"),
    Input("url", "pathname"),
    State("project-scoped-pathname", "data"),
    State("project-layout-generation", "data"),
)
def resolve_project_scoped_pathname(pathname: str, current_pathname: str | None, generation: int) -> tuple[Any, Any]:
    """Store the pathname of the solution page and bump the generation that triggers its rendering.

    The pathname is reset on the other pages so that coming back to the same solution page renders it again.
    """
    if _match_solution_page(pathname) is None:
        return (None if current_pathname is not None else no_update), no_update
    if pathname == current_pathname:
        return no_update, no_update
    return pathname, generation + 1


@callback(
    Output("navbar-content", "children"),
    Output("app-shell", "navbar"),
    Input("active-page-index", "data"),
    Input("active-non-solution-page-index", "data"),
    Input("color-scheme-switch", "checked"),
    State("app-shell", "navbar"),
    prevent_initial_call=True,
)
def render_nav_tree(
    active_index: str | None,
    active_non_solution_page_index: str | None,
    switch_on: bool,
    navbar: dict[str, Any],
) -> tuple[Any, dict[str, Any]]:
    """Display the navigation tree of the steps on solution pages and collapse the navbar on the other pages."""
    show_navbar = active_index is not None and active_non_solution_page_index is None
    navbar = {**navbar, "collapsed": {"mobile": True, "desktop": not show_navbar}}
    if not show_navbar:
        return html.Div(), navbar
    theme = "dark" if switch_on else "light"
    return Tree(aio_id="navigation_tree", items=get_page_list(theme), selected_item=active_index), navbar


def _display_404_page() -> Any:
    for module, page in dash.page_registry.items():
        if module.split(".")[-1] == "not_found_404":
            return page["layout"]
    return html.H1("404 - Page not found")


@callback(
    Output("page-content", "children"),
    Output("project-name", "children"),
    Input("project-layout-generation", "data"),
    State("project-scoped-pathname", "data"),
    State("project-scoped-pathname", "data"),
    prevent_initial_call=True,
)
def display_solution_page(
    _generation: int,
    project: {{ cookiecutter.__solution_definition_class_name }},
    project_scoped_pathname: str | None,
):
    """Return the page layout and the project name, passing the project instance.

    Using dash.page_container does not allow to inject the project instance as argument to the layout function,
    only supports passing path variables, query parameters or other Inputs/States.

    ``project-scoped-pathname`` is passed twice: GLOW injects the project from the first one, and the second one gives
    the raw pathname that selects the page. Both are set by the callback that bumps the generation triggering this
    one, so the project and the page always match.
    """
    solution_page = _match_solution_page(project_scoped_pathname)
    if solution_page is None:
        return no_update, no_update
    try:
        # verify that the project information is valid, otherwise return 404.
        # Cannot be done in display_404_page callback because we need that one to succeed if project injection fails.
        project_display_name = project.project_display_name
    except NotFoundException:
        return _display_404_page(), ""

    _, page, _ = solution_page
    # support layout module attribute and layout function (with or without project argument)
    layout_func = page["layout"]
    if callable(layout_func):
        params = inspect.signature(layout_func).parameters
        page_layout = layout_func(project=project) if "project" in params else layout_func()
    else:
        page_layout = layout_func
    return page_layout, f"Project Name: {project_display_name}"


@callback(
    Output("page-content", "children"),
    Output("project-name", "children"),
    Input("active-non-solution-page-index", "data"),
    State("color-scheme-switch", "checked"),
    prevent_initial_call=True,
)
def display_non_solution_page(active_non_solution_page_index: str | None, switch_on: bool):
    """Return the layout of a page displayed without a project, such as the projects dashboard.

    The theme is a State: toggling it must not render the page again, which would reload the projects dashboard.
    The theme of the projects dashboard is updated in place by a clientside callback instead.
    """
    if active_non_solution_page_index is None:
        return no_update, no_update
    page = list(dash.page_registry.values())[int(active_non_solution_page_index)]
    layout_func = page["layout"]
    if not callable(layout_func):
        return layout_func, ""
    theme = "dark" if switch_on else "light"
    kwargs = {"theme": theme} if "theme" in inspect.signature(layout_func).parameters else {}
    return layout_func(**kwargs), ""


@callback(
    Output("page-content", "children"),
    Output("project-name", "children"),
    Input("active-page-index", "data"),
    Input("active-non-solution-page-index", "data"),
    prevent_initial_call=True,
)
def display_404_page(active_page_index: str | None, active_non_solution_page_index: str | None):
    """Return the 404 page layout when the URL matches no registered page."""
    if active_page_index is None and active_non_solution_page_index is None:
        return _display_404_page(), ""
    return no_update, no_update


@callback(
    Output("url", "href"),
    Input(Tree.ids.selected_item("navigation_tree"), "data"),
    State("active-project-id", "data"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def open_new_page(value, project_id: str | None, pathname: str):
    """Navigate to the selected page."""
    if project_id is None or not value:
        return no_update
    item_index = int(Tree.ids.get_index_from_navlink_item_id(value))
    pages = list(dash.page_registry.values())
    if item_index >= len(pages):
        return no_update
    page = pages[item_index]
    if not page.get("path_template"):
        return no_update
    # Add GLOW_UI_PATH_PREFIX to the path returned to the browser
    target_path = dash.get_relative_path(page["path_template"].replace("<project_id>", project_id))
    if target_path == pathname:
        return no_update
    return target_path


@callback(
    Output("access-solution-doc", "children"),
    Output("logo-image", "src"),
    Output("logo-image", "title"),
    Input("color-scheme-switch", "checked"),
)
def update_nav_icons(switch_on: bool) -> tuple[html.Img, str, str]:
    """Update navigation tree icons based on the current theme."""
    theme = "dark" if switch_on else "light"
    return (
        html.Img(src=get_asset("teenyicons--doc-solid.svg", "icons", theme)),
        get_asset("placeholder_logo.png", "logos", theme),
        f"Customize this logo by modifying /ui/assets/logos/{theme}/placeholder_logo.png",
    )


clientside_callback(
    """
    (switchOn) => {
        return switchOn ? 'dark' : 'light';
    }
    """,
    Output("mantine-provider", "forceColorScheme"),
    Input("color-scheme-switch", "checked"),
)


# Update the theme of the projects dashboard in place: rendering it again would reload its project list.
# No update when the projects dashboard is not displayed, so that the output component always exists.
clientside_callback(
    """
    (switchOn) => {
        if (!document.getElementById('projects-dashboard')) {
            return window.dash_clientside.no_update;
        }
        return switchOn ? 'dark' : 'light';
    }
    """,
    Output("projects-dashboard", "themeMode"),
    Input("color-scheme-switch", "checked"),
    prevent_initial_call=True,
)
```

Notes for the implementer:
- `display_project_name` is removed on purpose: it injected the project from the URL on every page and fails on `/projects`. The project name is now returned by `display_solution_page`.
- Duplicate `page-content` / `project-name` outputs rely on `MultiplexerTransform` (already enabled in `ui/app.py`), as `page-content` already did. Do not add `allow_duplicate`.

- [ ] **Step 4: Run the routing tests to verify they pass**

Run: `poetry run pytest tests/unit/test_solution_ui_routing.py -v`
Expected: PASS — all new tests and the pre-existing `test_resolve_active_page_*` / `test_open_new_page*` tests.

- [ ] **Step 5: Run the whole saf-cli unit suite**

Run: `poetry run pytest tests/unit -v -p no:faulthandler`
Expected: PASS (scaffolding, add-step, and conversion tests are unaffected).

- [ ] **Step 6: Commit**

```bash
git add "packages/saf-cli/src/ansys/saf/cli/_solutions/templates/solution/{{cookiecutter.__solution_name}}/src" packages/saf-cli/tests/unit/test_solution_ui_routing.py
git commit -m "feat(saf-cli): route pages without project and link back to the projects dashboard"
```

---

### Task 4: Template dependency on `saf-projects-dashboard`

**Files:**
- Modify: `packages/saf-cli/src/ansys/saf/cli/_solutions/templates/solution/{{cookiecutter.__solution_name}}/pyproject.toml:48-70`
- Regenerate: `.../{{cookiecutter.__solution_name}}/lock_files/dash/poetry.lock`
- Modify: `packages/saf-cli/tests/unit/test_scaffolding.py`

**Interfaces:**
- Consumes: `saf-projects-dashboard` published to `solutions-private-pypi` (Task 1 Step 7).
- Produces: Dash solutions install `ansys_saf_projects_dashboard` with `poetry install --with ui`, which the orchestrator detects.

- [ ] **Step 1: Write the failing tests**

Add `import tomllib` and `from typing import Any` to the imports of `packages/saf-cli/tests/unit/test_scaffolding.py` (`Path`, `pytest`, and `create_solution` are already imported), then add:

```python
def _scaffold_pyproject(tmp_path: Path, ui_framework: str) -> dict[str, Any]:
    """Scaffold a solution in the working directory and return its parsed pyproject.toml."""
    create_solution("dashboard_dependency_solution", "Dashboard Dependency Solution", ui_framework, "saf_cli_tests")
    return tomllib.loads((tmp_path / "dashboard_dependency_solution" / "pyproject.toml").read_text(encoding="utf-8"))


@pytest.mark.usefixtures("tmp_path_as_working_dir", "mock_appdata")
def test_dash_solution_depends_on_projects_dashboard(tmp_path: Path):
    """Install the projects dashboard with the UI of a Dash solution, from the private feed only."""
    poetry = _scaffold_pyproject(tmp_path, "dash")["tool"]["poetry"]
    dependency = poetry["group"]["ui"]["dependencies"]["saf-projects-dashboard"]
    assert dependency["source"] == "solutions-private-pypi"
    assert dependency["allow-prereleases"] is True
    sources = {source["name"]: source for source in poetry["source"]}
    assert sources["solutions-private-pypi"]["priority"] == "explicit"
    assert sources["solutions-private-pypi"]["url"] == (
        "https://pkgs.dev.azure.com/ansys-solutions/_packaging/ansys-solutions/pypi/simple/"
    )


@pytest.mark.usefixtures("tmp_path_as_working_dir", "mock_appdata")
def test_solution_without_ui_does_not_depend_on_projects_dashboard(tmp_path: Path):
    """Do not add the projects dashboard nor the private feed to a solution without UI."""
    poetry = _scaffold_pyproject(tmp_path, "none")["tool"]["poetry"]
    assert "ui" not in poetry.get("group", {})
    assert "solutions-private-pypi" not in {source["name"] for source in poetry["source"]}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `poetry run pytest tests/unit/test_scaffolding.py -k projects_dashboard -v`
Expected: `test_dash_solution_depends_on_projects_dashboard` FAILS with `KeyError: 'saf-projects-dashboard'`; the no-UI test PASSES.

- [ ] **Step 3: Add the source and the dependency**

In the template `pyproject.toml`, replace:

```toml
[[tool.poetry.source]]
name = "PyPI"
priority = "primary"

```

with:

```toml
[[tool.poetry.source]]
name = "PyPI"
priority = "primary"

{% if cookiecutter.__ui_framework == "dash" %}
# Only used by the packages that explicitly name it, until saf-projects-dashboard is published on PyPI.
[[tool.poetry.source]]
name = "solutions-private-pypi"
url = "https://pkgs.dev.azure.com/ansys-solutions/_packaging/ansys-solutions/pypi/simple/"
priority = "explicit"
{% endif %}

```

and in the Dash `ui` group, after `dash-mantine-components = "^2.6.0"`, add:

```toml
saf-projects-dashboard = { version = ">=0.1.0.dev0,<1.0.0", allow-prereleases = true, source = "solutions-private-pypi" }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poetry run pytest tests/unit/test_scaffolding.py -v`
Expected: PASS.

- [ ] **Step 5: Regenerate the Dash lock file**

Requires the published package (Task 1 Step 7) and feed credentials. From `packages/saf-cli` (the script expects an in-project `.venv` with the `saf` executable):

```bash
poetry config virtualenvs.in-project true --local
poetry install
export POETRY_HTTP_BASIC_SOLUTIONS_PRIVATE_PYPI_USERNAME=<user>
export POETRY_HTTP_BASIC_SOLUTIONS_PRIVATE_PYPI_PASSWORD=<azure-devops-pat>
poetry run python scripts/upgrade_solution_template_poetry_lock.py
```

Expected: `lock_files/dash/poetry.lock` gains a `[[package]] name = "saf-projects-dashboard"` entry whose `[package.source]` is `solutions-private-pypi`; `lock_files/no_ui/poetry.lock` has no such entry. Review `git diff --stat` — revert unrelated version bumps in `no_ui/poetry.lock` with `git checkout -- <path>` if the script touched it without reason.

- [ ] **Step 6: Check the fastapi / OpenTelemetry mismatch from #286**

```bash
grep -A1 'name = "fastapi"' "src/ansys/saf/cli/_solutions/templates/solution/{{cookiecutter.__solution_name}}/lock_files/dash/poetry.lock"
grep -A1 'name = "opentelemetry-instrumentation-fastapi"' "src/ansys/saf/cli/_solutions/templates/solution/{{cookiecutter.__solution_name}}/lock_files/dash/poetry.lock"
```

If `fastapi >= 0.137` **and** `opentelemetry-instrumentation-fastapi < 0.64b0`, add `opentelemetry-instrumentation-fastapi = ">=0.64b0"` to `[tool.poetry.dependencies]` of the template `pyproject.toml`, re-run Step 5, and mention it in the commit message. Otherwise do nothing.

- [ ] **Step 7: Commit**

```bash
git add "packages/saf-cli/src/ansys/saf/cli/_solutions/templates/solution/{{cookiecutter.__solution_name}}/pyproject.toml" "packages/saf-cli/src/ansys/saf/cli/_solutions/templates/solution/{{cookiecutter.__solution_name}}/lock_files" packages/saf-cli/tests/unit/test_scaffolding.py
git commit -m "build(saf-cli): add saf-projects-dashboard to the Dash solution template"
```

---

### Task 5: End-to-end coverage of `saf run --portal` with the dashboard

**Files:**
- Modify: `packages/saf-cli/tests/e2e/saf_process.py:72-76`
- Modify: `packages/saf-cli/tests/e2e/conftest.py:300-301`
- Modify: `packages/saf-cli/tests/e2e/test_run_solution.py:153-176,581-586`

**Interfaces:**
- Consumes: orchestrator log lines `Projects Dashboard: <solution_ui_url>/projects` and `SAF Portal: not launched` (`run_solution_stack.py:346-349`); the Dash session solution with the lock from Task 4.
- Produces: `SAFProcess.get_projects_dashboard_url() -> str | None`.

- [ ] **Step 1: Add the URL helper**

In `packages/saf-cli/tests/e2e/saf_process.py`, after `get_portal_url`, add:

```python
    def get_projects_dashboard_url(self) -> str | None:
        """Return the URL of the projects dashboard, or None if the solution does not use it."""
        projects_dashboard_url = self.find_msg_in_output(r"Projects Dashboard: http://127\.0\.0\.1:\d+/\S*", regex=True)
        if not projects_dashboard_url:
            return None
        return projects_dashboard_url.removeprefix("INFO - Projects Dashboard: ")
```

- [ ] **Step 2: Accept the projects dashboard in the expected messages**

In `packages/saf-cli/tests/e2e/conftest.py`, `check_expected_messages`, replace:

```python
    portal_url = p.get_portal_url() if with_portal else "not launched"
    assert p.find_msg_in_output(f"SAF Portal: {portal_url}")
```

with:

```python
    # With --portal, the orchestrator uses the projects dashboard if installed, instead of starting a portal.
    uses_projects_dashboard = with_portal and p.get_projects_dashboard_url() is not None
    portal_url = p.get_portal_url() if with_portal and not uses_projects_dashboard else "not launched"
    assert p.find_msg_in_output(f"SAF Portal: {portal_url}")
```

- [ ] **Step 3: Write the e2e test**

In `packages/saf-cli/tests/e2e/test_run_solution.py`, after `test_saf_run_with_portal`, add:

```python
@pytest.mark.use_session_solution
@pytest.mark.parametrize("session_solution_ui_framework", ["dash"], indirect=True)
def test_saf_run_with_portal_opens_projects_dashboard(
    session_solution: SolutionRegistry,
    run_solution: RunSolution,
    session_selenium_webdriver: WebDriver,
):
    """
    Test ``saf run --portal`` opens the projects dashboard of the solution UI instead of starting a portal.
    """
    p = run_solution([session_solution.name, "--portal"])

    projects_dashboard_url = p.get_projects_dashboard_url()
    assert projects_dashboard_url == f"{p.get_solution_ui_url(no_project=True)}/projects"
    assert p.find_msg_in_output("SAF Portal: not launched")

    session_selenium_webdriver.get(projects_dashboard_url)
    wait_for_element(session_selenium_webdriver, "projects-dashboard", element_type=By.ID)
```

- [ ] **Step 4: Stop expecting a 404 on `/projects`**

In `test_404_page_on_invalid_urls`, remove this line from `invalid_urls`:

```python
        f"{solution_ui_url_no_project}/projects",  # no project
```

- [ ] **Step 5: Run the e2e tests**

Requires network access to PyPI and the private feed (session solution install). From `packages/saf-cli`:

```bash
poetry run pytest tests/e2e/test_run_solution.py -k "portal or 404" -v -p no:faulthandler
```

Expected: `test_saf_run_with_portal`, `test_saf_run_with_portal_opens_projects_dashboard`, and `test_404_page_on_invalid_urls` PASS (`test_theme_is_preserved_on_return_to_portal` stays `xfail`).

- [ ] **Step 6: Manual check of the dashboard interactions (acceptance criterion 4)**

```bash
saf new --solution-name dashboard-check --solution-display-name "Dashboard Check" --ui-framework dash --namespace my_check
saf install dashboard-check
saf run dashboard-check --portal
```

In the window that opens on `/projects`: create a project, open it (the step navbar appears and the header shows its name), click the back button (returns to `/projects`, navbar collapsed), open the **same** project again (it renders), toggle dark/light on `/projects` (the list does not reload), then export, import, and delete a project.

- [ ] **Step 7: Commit**

```bash
git add packages/saf-cli/tests/e2e/saf_process.py packages/saf-cli/tests/e2e/conftest.py packages/saf-cli/tests/e2e/test_run_solution.py
git commit -m "test(saf-cli): cover saf run --portal with the projects dashboard"
```

---

## Self-Review

- **Spec coverage:** rename (Task 1), template dependency + lock + fastapi check (Task 4), conditional page (Task 2), routing port + back-button fallback + double-State doc + no unrelated #286 files (Task 3), tests incl. fallback (Tasks 2–5), installer via #171 (prerequisite), CORS untouched (Global Constraints). Spec items intentionally dropped are listed under "Deviations".
- **Placeholders:** credentials in Task 4 Step 5 are user secrets, not plan gaps. `Deployment` members (`Desktop`, `DockerCompose`, `Unknown`) and the `tmp_path_as_working_dir` / `mock_appdata` fixtures were checked against the code.
- **Names:** `projects_dashboard_installed`, `PROJECTS_PAGE_MODULE`, `resolve_active_non_solution_page`, `resolve_project_scoped_pathname`, `render_nav_tree(active_index, active_non_solution_page_index, switch_on, navbar)`, `_get_projects_dashboard_page`, `get_projects_dashboard_url` are used consistently across tasks.
