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
from types import ModuleType, SimpleNamespace
from typing import Any

import dash
import pytest

from ansys.saf.cli._solutions.scaffolding import create_solution
from ansys.solutions.dash_super_components import Tree  # pyright: ignore[reportMissingImports]

SOLUTION_NAME = "ui_routing_solution"
SOLUTION_NAMESPACE = "saf_cli_tests"  # a dedicated namespace avoids clashing with the installed ansys packages
SOLUTION_PACKAGE = f"{SOLUTION_NAMESPACE}.{SOLUTION_NAME}"
FIRST_PAGE_PATH_TEMPLATE = "/projects/<project_id>/first-step"


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
    monkeypatch.setattr("dash._get_paths.CONFIG", SimpleNamespace(requests_pathname_prefix=request.param))
    return str(request.param).rstrip("/")


@pytest.fixture
def first_page_index(solution_ui_page: ModuleType) -> str:  # the page module registers the pages on import
    pages = get_registered_pages()
    return str(next(i for i, page in enumerate(pages) if page["path_template"] == FIRST_PAGE_PATH_TEMPLATE))


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
