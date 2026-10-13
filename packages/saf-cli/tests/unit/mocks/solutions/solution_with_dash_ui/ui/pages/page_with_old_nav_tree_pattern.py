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

"""Initialization of the frontend layout across all the steps."""

import webbrowser

import dash  # pyright: ignore[reportMissingTypeStubs]
from dash.exceptions import PreventUpdate  # pyright: ignore[reportMissingTypeStubs]
import dash_bootstrap_components as dbc  # pyright: ignore[reportMissingTypeStubs]
from dash_extensions.enrich import (  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]
    Input,
    Output,
    State,
    callback_context,
    clientside_callback,  # pyright: ignore[reportUnknownVariableType]
    ctx,
    dcc,
    html,
)
import dash_mantine_components as dmc  # pyright: ignore[reportMissingTypeStubs]

from ansys.saf.glow.client import DashClient, Deployment, callback
from ansys.solutions.dash_super_components import Tree  # pyright: ignore[reportMissingTypeStubs]
from tests.unit.mocks.solutions.solution_with_dash_ui.solution.definition import SolutionWithDashUiSolution
from tests.unit.mocks.solutions.solution_with_dash_ui.ui.pages import about_page, first_page, second_page


def get_asset(asset_name: str, relative_path: str = "", theme: str = "dark") -> str:
    """Return asset URL based on the current theme."""
    path = f"{relative_path.strip('/')}/{theme}/{asset_name}"
    return dash.get_asset_url(path)  # pyright: ignore[reportUnknownMemberType]


def get_page_list(theme: str) -> list[dict[str, str | bool]]:
    """Return the page list with icons based on the current theme."""
    return [
        {
            "id": "about_page",
            "text": "About",
            "icon": get_asset("material-symbols--home.svg", "icons", theme),
            "expanded": True,
        },
        {
            "id": "first_page",
            "text": "First Step",
            "icon": get_asset("game-icons--crossed-air-flows.svg", "icons", theme),
            "expanded": True,
        },
        {
            "id": "second_page",
            "text": "Second Step",
            "icon": get_asset("carbon--ibm-engineering-workflow-mgmt.svg", "icons", theme),
            "expanded": True,
        },
    ]


theme_toggle = dmc.Switch(
    offLabel=html.Img(src=get_asset("radix-icons--sun.svg", "icons", "light")),
    onLabel=html.Img(src=get_asset("radix-icons--moon.svg", "icons", "light")),
    id="color-scheme-switch",
    persistence=True,
    color="grey",
    checked=False,
)


header = dmc.AppShellHeader(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportAttributeAccessIssue]
    dmc.Flex(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportAttributeAccessIssue]
        [
            html.Img(
                id="logo-image",
                src=get_asset("placeholder_logo.png", "logos", "light"),
                height="36px",
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
    ),
)


navbar = dmc.AppShellNavbar(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportAttributeAccessIssue]
    Tree(
        aio_id="navigation_tree",
        items=get_page_list("light"),
        selected_item="about_page",
    ),
    id="navbar-content",
    p="md",
)


main_layout = dmc.AppShellMain(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportAttributeAccessIssue]
    html.Div(
        id="page-content",
        style={
            "padding-right": "0.7%",
            "padding-left": "0.7%",
            "backgroundColor": "var(--mantine-color-body)",
            "color": "var(--mantine-color-text)",
            "minHeight": "100vh",
        },
    ),
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
        dcc.Location(id="url", refresh=False),
        html.Div(
            id="alerts-container",
            style={"position": "fixed", "top": 90, "right": 10, "width": 350, "zIndex": 1000},
        ),
    ],
    id="mantine-provider",
    defaultColorScheme="light",
)


@callback(
    Output("return-to-portal", "children"),
    Input("url", "pathname"),
    Input("color-scheme-switch", "checked"),
)
def return_to_portal(pathname: str, switch_on: bool) -> list[html.A] | list:  # pyright: ignore[reportUnknownVariableType, reportUnknownParameterType, reportMissingTypeArgument]
    """Display Solution Portal when back-to-portal button gets selected."""
    theme = ("dark" if switch_on else "light") if ctx.triggered_id == "color-scheme-switch" else "light"  # type: ignore

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
        ),
    ]


@callback(
    Output("project-name", "children"),
    Input("url", "pathname"),
)
def display_project_name(project: SolutionWithDashUiSolution):
    """Display current project name."""
    return f"Project Name: {project.project_display_name}"


@callback(
    Output("access-dev-guide", "children"),
    Input("access-dev-guide", "n_clicks"),
    prevent_initial_call=True,
)
def access_dev_guide_documentation(n_clicks: int):
    """Open the Developer's Guide home page in the web browser."""
    webbrowser.open_new("https://dev-docs.solutions.ansys.com/index.html")
    raise PreventUpdate


@callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
    Input(Tree.ids.selected_item("navigation_tree"), "data"),  # type: ignore
    prevent_initial_call=True,
)
def display_page(project: SolutionWithDashUiSolution, selected_item: dict[str, str] | None) -> html.Div:
    """Display page content."""
    triggered_id = callback_context.triggered_id  # type: ignore
    if triggered_id == "url" or not selected_item:
        return about_page.layout()
    elif triggered_id == Tree.ids.selected_item("navigation_tree"):  # type: ignore
        page_id = Tree.ids.get_index_from_navlink_item_id(selected_item)
        if page_id == "about_page":
            return about_page.layout()
        elif page_id == "first_page":
            return first_page.layout(project.steps.first_step)  # pyright: ignore
        elif page_id == "second_page":
            return second_page.layout(project.steps.second_step)  # pyright: ignore
        else:
            raise ValueError(f"Unknown page selection: {page_id}")
    raise PreventUpdate


@callback(
    Output("navbar-content", "children"),
    Output("access-solution-doc", "children"),
    Output("logo-image", "src"),
    Input("color-scheme-switch", "checked"),
    State(Tree.ids.selected_item("navigation_tree"), "data"),  # type: ignore
)
def update_nav_icons(switch_on: bool, selected_item: dict[str, str] | None) -> tuple[Tree, html.Img, str]:
    """Update navigation tree icons based on the current theme."""
    theme = "dark" if switch_on else "light"
    current_page_id = Tree.ids.get_index_from_navlink_item_id(selected_item) if selected_item else "about_page"
    return (
        Tree(
            aio_id="navigation_tree",
            items=get_page_list(theme),
            selected_item=current_page_id,
        ),
        html.Img(src=get_asset("teenyicons--doc-solid.svg", "icons", theme)),
        get_asset("placeholder_logo.png", "logos", theme),
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
