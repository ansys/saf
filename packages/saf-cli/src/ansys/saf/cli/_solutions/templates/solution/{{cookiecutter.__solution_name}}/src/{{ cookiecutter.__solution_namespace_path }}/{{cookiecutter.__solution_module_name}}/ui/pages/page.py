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


def get_page_list(theme: str) -> list[dict[str, str | bool]]:
    """Return the page list with icons based on the current theme and registered pages."""
    pages = []
    for i, page in enumerate(dash.page_registry.values()):
        if page["module"].split(".")[-1] == "not_found_404":
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


@callback(
    Output("return-to-portal", "children"),
    Input("url", "pathname"),
    Input("color-scheme-switch", "checked"),
)
def return_to_portal(pathname: str, switch_on: bool) -> list[html.A]:
    """Display Solution Portal when back-to-portal button gets selected."""
    theme = "dark" if switch_on else "light"

    portal_ui_url = DashClient.get_portal_ui_url()

    if portal_ui_url is None:
        return []

    popover_text = "Back to Projects" if DashClient.get_deployment_type() == Deployment.Desktop else "Back to Portal"

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
            href=portal_ui_url,
        )
    ]


@callback(
    Output("project-name", "children"),
    Input("url", "pathname"),
)
def display_project_name(project: {{ cookiecutter.__solution_definition_class_name }}) -> str:
    """Display current project name."""
    return f"Project Name: {project.project_display_name}"


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
    """Resolve the active page index and project ID based on the current URL."""
    # Remove the GLOW_UI_PATH_PREFIX part from pathname
    relative_pathname = dash.strip_relative_path(pathname)
    path_parts = relative_pathname.split("/") if relative_pathname else []
    for i, page in enumerate(dash.page_registry.values()):
        if page["module"].split(".")[-1] == "not_found_404":
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
            return str(i), project_id
    return None, None


@callback(
    Output("navbar-content", "children"),
    Input("active-page-index", "data"),
    Input("color-scheme-switch", "checked"),
    prevent_initial_call=True,
)
def render_nav_tree(active_index: str | None, switch_on: bool):
    """Sync the active tree item based on the active page index."""
    theme = "dark" if switch_on else "light"
    return Tree(aio_id="navigation_tree", items=get_page_list(theme), selected_item=active_index)


def _display_404_page() -> Any:
    for module, page in dash.page_registry.items():
        if module.split(".")[-1] == "not_found_404":
            return page["layout"]
    return html.H1("404 - Page not found")


@callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
    Input("active-page-index", "data"),
    prevent_initial_call=True,
)
def display_page(project: {{ cookiecutter.__solution_definition_class_name }}, active_page_index: str | None):
    """Return the page layout, passing the project instance.

    Using dash.page_container does not allow to inject the project instance as argument to the layout function,
    only supports passing path variables, query parameters or other Inputs/States.
    """
    if active_page_index is None:
        # triggered if pathname with correct project information but incorrect sub-path.
        # anyway, the 404 page will be rendered by another callback
        return no_update
    try:
        # verify that the project information is valid, otherwise return 404.
        # Cannot be done in display_404_page callback because we need that one to succeed if project injection fails.
        _ = project.project_display_name
    except NotFoundException:
        return _display_404_page()

    pages = list(dash.page_registry.values())  # page_registry is an ordered dict
    index = int(active_page_index)
    page = pages[index]
    # support layout module attribute and layout function (with or without project argument)
    layout_func = page["layout"]
    if callable(layout_func):
        params = inspect.signature(layout_func).parameters
        if "project" in params:
            return layout_func(project=project)
        return layout_func()
    return layout_func


@callback(
    Output("page-content", "children"),
    Input("active-page-index", "data"),
    prevent_initial_call=True,
)
def display_404_page(active_page_index: str | None):
    """Return the 404 page layout when the active page index is None."""
    if active_page_index is None:
        return _display_404_page()
    return no_update


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
