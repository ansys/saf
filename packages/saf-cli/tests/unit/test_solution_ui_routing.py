# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the routing callbacks of the Dash UI shipped in the solution template."""

import importlib
import importlib.util
from collections.abc import Iterator
from importlib.machinery import ModuleSpec
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

from ansys.solutions.dash_super_components import Tree  # pyright: ignore[reportMissingTypeStubs]
import dash
import pytest

from ansys.saf.cli._solutions.scaffolding import create_solution

SOLUTION_NAME = "ui_routing_solution"
SOLUTION_NAMESPACE = "saf_cli_tests"  # a dedicated namespace avoids clashing with the installed ansys packages
SOLUTION_PACKAGE = f"{SOLUTION_NAMESPACE}.{SOLUTION_NAME}"
FIRST_PAGE_PATH_TEMPLATE = "/projects/<project_id>/first-step"

PROJECTS_DASHBOARD_MODULE = "ansys_saf_projects_dashboard"
PROJECTS_PAGE_MODULE = "pages.projects_page"  # module name Dash gives to ui/pages/projects_page.py


def get_registered_pages() -> list[dict[str, Any]]:
    """Return the pages registered in Dash, in the order in which the navigation tree displays them."""
    page_registry: dict[str, dict[str, Any]] = dash.page_registry  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
    return list(page_registry.values())  # pyright: ignore[reportUnknownArgumentType]


def get_navigation_tree_item(index: str) -> dict[str, Any]:
    """Return the identifier of the navigation tree item at the given index."""
    return Tree.ids.navlink_item("navigation_tree", index)  # pyright: ignore[reportUnknownMemberType]


@pytest.fixture(scope="module")
def solution_ui_page(tmp_path_factory: pytest.TempPathFactory) -> ModuleType:
    """Scaffold a Dash solution and return the imported page module of its UI."""
    output_dir = tmp_path_factory.mktemp("ui_routing")
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.chdir(output_dir)
        create_solution(SOLUTION_NAME, "UI Routing Solution", "dash", SOLUTION_NAMESPACE)
        monkeypatch.syspath_prepend(str(output_dir / SOLUTION_NAME / "src"))  # pyright: ignore[reportUnknownMemberType]
        # !IMPORTANT: keep this import first. It initializes the Dash config and registers the pages.
        importlib.import_module(f"{SOLUTION_PACKAGE}.ui.app")
        return importlib.import_module(f"{SOLUTION_PACKAGE}.ui.pages.page")


@pytest.fixture(params=["/", "/ui-routing-solution_0-0-0/"], ids=["without_path_prefix", "with_path_prefix"])
def ui_path_prefix(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> str:
    """Serve the UI under the given path prefix, as GLOW_UI_PATH_PREFIX does in distributed deployments."""
    # The config of the app cannot be edited: it becomes read-only once the app is initialized.
    monkeypatch.setattr(
        "dash._get_paths.CONFIG",
        SimpleNamespace(requests_pathname_prefix=request.param, assets_external_path=None, assets_url_path="assets"),
    )
    return str(request.param).rstrip("/")


@pytest.fixture
def first_page_index(solution_ui_page: ModuleType) -> str:  # the page module registers the pages on import
    pages = get_registered_pages()
    return str(next(i for i, page in enumerate(pages) if page["path_template"] == FIRST_PAGE_PATH_TEMPLATE))


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


def test_resolve_active_page_and_project_information(
    solution_ui_page: ModuleType,
    ui_path_prefix: str,
    first_page_index: str,
):
    """Resolve the first page from its URL, whose path prefix must be stripped to match a page template."""
    pathname = f"{ui_path_prefix}/projects/abc123/first-step"
    assert solution_ui_page.resolve_active_page_and_project_information(pathname) == (first_page_index, "abc123")


def test_resolve_active_page_and_project_information_on_ui_root(solution_ui_page: ModuleType, ui_path_prefix: str):
    """Resolve no page on the UI root, where none is registered."""
    assert solution_ui_page.resolve_active_page_and_project_information(f"{ui_path_prefix}/") == (None, None)


def test_resolve_active_page_and_project_information_on_unknown_page(
    solution_ui_page: ModuleType,
    ui_path_prefix: str,
):
    """Resolve no page on an unknown sub-path, which makes the 404 page be displayed."""
    pathname = f"{ui_path_prefix}/projects/abc123/unknown-step"
    assert solution_ui_page.resolve_active_page_and_project_information(pathname) == (None, None)


def test_open_new_page(solution_ui_page: ModuleType, ui_path_prefix: str, first_page_index: str):
    """Select the first page from the about page, which must navigate to the prefixed URL of the first page."""
    selected_item = get_navigation_tree_item(first_page_index)
    current_pathname = f"{ui_path_prefix}/projects/abc123"
    assert solution_ui_page.open_new_page(selected_item, "abc123", current_pathname) == (
        f"{ui_path_prefix}/projects/abc123/first-step"
    )


def test_open_new_page_on_active_page(solution_ui_page: ModuleType, ui_path_prefix: str, first_page_index: str):
    """Select the first page while already on it, which must not navigate."""
    selected_item = get_navigation_tree_item(first_page_index)
    pathname = f"{ui_path_prefix}/projects/abc123/first-step"
    assert solution_ui_page.open_new_page(selected_item, "abc123", pathname) is solution_ui_page.no_update


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
