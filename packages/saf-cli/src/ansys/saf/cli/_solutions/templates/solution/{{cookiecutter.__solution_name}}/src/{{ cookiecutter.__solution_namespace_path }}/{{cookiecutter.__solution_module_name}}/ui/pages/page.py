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
