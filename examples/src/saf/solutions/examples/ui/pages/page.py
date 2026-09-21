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

# ©2023, ANSYS Inc. Unauthorized use, distribution or duplication is prohibited.

"""Initialization of the frontend layout across all registered pages."""

import importlib
import inspect
import logging
from pathlib import Path
from typing import Any, Literal
import webbrowser

from ansys.saf.glow.client import DashClient, Deployment, NotFoundException, callback
from ansys.solutions.dash_super_components import Tree  # type: ignore
import dash
from dash_extensions.enrich import Input, Output, State, clientside_callback, dcc, html, no_update  # type: ignore
from dash_iconify import DashIconify  # type: ignore
import dash_mantine_components as dmc  # type: ignore

from saf.solutions.examples.solution.definition import ExamplesSolution

logger = logging.getLogger(__name__)
ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"

# Pages with a generic "step" parameter need an explicit mapping.
STEP_BY_PAGE_MODULE: dict[str, str] = {
    "saf.solutions.examples.ui.pages.basic.plot_page": "basic_step",
    "saf.solutions.examples.ui.pages.basic.process_logs_page": "basic_step",
    "saf.solutions.examples.ui.pages.basic.table_page": "basic_step",
    "saf.solutions.examples.ui.pages.game_of_life_page": "game_of_life_step",
}


def get_asset(asset_name: str, relative_path: str = "", theme: str = "dark") -> str:
    """Return asset URL with themed and non-themed fallbacks."""
    relative = relative_path.strip("/")
    if relative:
        themed_path = ASSETS_DIR / relative / theme / asset_name
        if themed_path.is_file():
            return dash.get_asset_url(f"{relative}/{theme}/{asset_name}")

        default_path = ASSETS_DIR / relative / asset_name
        if default_path.is_file():
            return dash.get_asset_url(f"{relative}/{asset_name}")
    else:
        root_path = ASSETS_DIR / asset_name
        if root_path.is_file():
            return dash.get_asset_url(asset_name)

    fallback = ASSETS_DIR / "icons" / "streamline--startup-solid.svg"
    if fallback.is_file():
        return dash.get_asset_url("icons/streamline--startup-solid.svg")

    return dash.get_asset_url(asset_name)


def get_page_list(theme: str, active_index: str | None = None) -> list[dict[str, str | bool]]:
    """Return grouped page list while resolving page IDs from dash.page_registry."""

    def page_id(module_suffix: str) -> str | None:
        for i, page in enumerate(dash.page_registry.values()):
            if page["module"].split(".")[-1] == "not_found_404":
                continue
            if page["module"].split(".")[-1] == module_suffix:
                return str(i)
        return None

    def leaf(module_suffix: str, text: str, prefix_icon: str) -> dict[str, Any] | None:
        id_ = page_id(module_suffix)
        if id_ is None:
            return None
        return {"id": id_, "text": text, "prefixIcon": prefix_icon, "expanded": False}

    def is_group_active(nodes: list[dict[str, Any]]) -> bool:
        if active_index is None:
            return False
        return any(node.get("id") == active_index for node in nodes)

    basic_children = [
        leaf("process_logs_page", "Process logs", "tabler:logs"),
        leaf("table_page", "Dash Table", "tabler:table-filled"),
        leaf("display_images_page", "Display Images", "material-symbols:image"),
        leaf("plot_page", "Plotly graph", "mdi:graph-line"),
    ]
    instance_children = [
        leaf("geometry_instance_page", "Geometry", "mdi:cube"),
        leaf("fluent_instance_page", "Fluent", "ic:baseline-water"),
        leaf("mechanical_instance_page", "Mechanical", "mdi:gear"),
        leaf("mapdl_instance_page", "MAPDL", "mdi:gear"),
        leaf("aedt_instance_page", "AEDT (Maxwell 2D)", "game-icons:wire-coil"),
        leaf("optislang_instance_page", "optiSLang", "ph:dna-fill"),
    ]
    beam_children = [
        leaf("model_page", "Model", "material-symbols:home"),
        leaf("compute_page", "Compute", "fluent:math-formula-16-filled"),
        leaf("report_page", "Report", "mdi:file-chart-outline"),
    ]

    items: list[dict[str, Any]] = [
        {
            "id": "basic_examples",
            "text": "Basic examples",
            "prefixIcon": "ic:baseline-minus",
            "expanded": True,
            "children": [child for child in basic_children if child is not None],
        },
    ]

    for candidate in [
        leaf(
            "file_handling_page",
            "File handling",
            "streamline-ultimate:cloud-data-transfer",
        ),
        leaf("long_transaction_page", "Long transaction", "svg-spinners:3-dots-bounce"),
        leaf(
            "hps_job_submission_page",
            "HPS Job Submission",
            "streamline-ultimate:cloud-data-transfer",
        ),
        leaf("game_of_life_page", "Game of Life", "game-icons:conway-life-glider"),
    ]:
        if candidate is not None:
            items.append(candidate)

    instance_nodes = [child for child in instance_children if child is not None]
    if instance_nodes:
        items.append(
            {
                "id": "instance_management",
                "text": "Instance Management",
                "prefixIcon": "material-symbols:menu",
                "expanded": is_group_active(instance_nodes),
                "children": instance_nodes,
            }
        )

    beam_nodes = [child for child in beam_children if child is not None]
    if beam_nodes:
        items.append(
            {
                "id": "beam_bending_page",
                "text": "Beam Bending",
                "prefixIcon": "hugeicons:bend-tool",
                "expanded": is_group_active(beam_nodes),
                "children": beam_nodes,
            }
        )

    return items


theme_toggle = dmc.Switch(
    offLabel=html.Img(src=get_asset("radix-icons--sun.svg", "icons", "light")),
    onLabel=html.Img(src=get_asset("radix-icons--moon.svg", "icons", "light")),
    id="color-scheme-switch",
    persistence=True,
    color="grey",
    checked=True,
)


header = dmc.AppShellHeader(
    dmc.Flex(
        [
            html.Div(
                dmc.Group(
                    [
                        html.Div(
                            DashIconify(icon="mdi:book-open-variant", width=36),
                            id="solution-title-icon",
                            style={
                                "color": "var(--mantine-color-text)",
                                "display": "flex",
                                "alignItems": "center",
                            },
                        ),
                        html.H1(
                            "Solution Examples",
                            style={
                                "color": "var(--mantine-color-text)",
                                "font-size": "24px",
                                "margin": "0",
                            },
                        ),
                    ],
                    gap="xs",
                ),
                style={
                    "flex": "1",
                    "text-align": "left",
                },
            ),
            html.Div(
                dmc.Group(
                    [
                        dmc.Text(
                            "Project name:",
                            id="project-name",
                            size="sm",
                            style={
                                "font-size": "16px",
                                "color": "var(--mantine-color-text)",
                            },
                        ),
                        theme_toggle,
                        dmc.Tooltip(
                            dmc.ActionIcon(
                                html.Img(src=get_asset("teenyicons--doc-solid.svg", "icons", "dark")),
                                id="access-dev-guide",
                                size=36,  # pyright: ignore[reportArgumentType]
                                variant="transparent",
                                style={"color": "var(--mantine-color-text)"},
                            ),
                            label="Get access to the Solution's Developer Guide.",
                        ),
                        html.Div(id="return-to-portal"),
                    ],
                    gap="xs",
                ),
                style={
                    "display": "flex",
                    "align-items": "center",
                },
            ),
        ],
        justify="space-between",
        align="center",
        direction="row",
        wrap="wrap",
        h="100%",
        px="md",
        style={"height": "100%"},
    ),
    style={
        "borderBottom": "1px solid var(--mantine-color-default-border)",
    },
)


navbar = dmc.AppShellNavbar(
    html.Div(),
    id="navbar-content",
    p="md",
    style={"overflowY": "auto"},
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
            id="alerts-container",
            style={
                "position": "fixed",
                "top": 90,
                "right": 10,
                "width": 350,
                "zIndex": 1000,
            },
        ),
        dcc.Store(id="active-page-index", data=None),
        dcc.Store(id="active-project-id", data=None),
        html.Div(id="aedt-instance-event-listeners-container"),
        html.Div(id="fluent-instance-event-listeners-container"),
        html.Div(id="long-transaction-event-listeners-container"),
        html.Div(id="mapdl-instance-event-listeners-container"),
        html.Div(id="mechanical-instance-event-listeners-container"),
        html.Div(id="optislang-instance-event-listeners-container"),
        html.Div(id="process-logs-event-listeners-container"),
        dcc.Store(id="aedt-logs-store", storage_type="memory"),
        dcc.Store(id="fluent-logs-store", storage_type="memory"),
        dcc.Store(id="mapdl-logs-store", storage_type="memory"),
        dcc.Store(id="mechanical-logs-store", storage_type="memory"),
        dcc.Store(id="optislang-logs-store", storage_type="memory"),
    ],
    id="mantine-provider",
    defaultColorScheme="light",
)


_LEVEL_TO_DMC_COLOR = {
    "success": "green",
    "info": "blue",
    "warning": "yellow",
    "danger": "red",
}


def _get_alert_toast(message: str, level: Literal["success", "info", "warning", "danger"]) -> dmc.Alert:
    """Create an alert with the alert message."""
    return dmc.Alert(
        message,
        title=level.upper(),
        color=_LEVEL_TO_DMC_COLOR[level],
        withCloseButton=True,
        style={"font-size": "small"},
    )


def _get_404_layout() -> Any:
    for module, page in dash.page_registry.items():
        if module.split(".")[-1] == "not_found_404":
            return page["layout"]
    return html.H1("404 - Page not found")


@callback(
    Output("return-to-portal", "children"),
    Input("url", "pathname"),
    Input("color-scheme-switch", "checked"),
)
def return_to_portal(project: ExamplesSolution, switch_on: bool) -> list[html.A]:
    """Display a back-to-portal button when portal URL is available."""
    portal_ui_url = DashClient.get_portal_ui_url()
    icon_color = "#E6EDF5" if switch_on else "#1A1B1E"

    if portal_ui_url is None:
        return []

    popover_text = "Back to Projects" if DashClient.get_deployment_type() == Deployment.Desktop else "Back to Portal"

    return [
        html.A(
            dmc.Tooltip(
                dmc.ActionIcon(
                    DashIconify(icon="carbon:return", width=36, color=icon_color),
                    id="back-to-projects-icon",
                    variant="transparent",
                ),
                label=popover_text,
            ),
            href=portal_ui_url,
        )
    ]


@callback(
    Output("project-name", "children"),
    Input("url", "pathname"),
)
def display_project_name(project: ExamplesSolution) -> str:
    """Display current project name."""
    return f"Project name: {project.project_display_name}"


@callback(
    Output("alerts-container", "children"),
    Input("access-dev-guide", "n_clicks"),
    prevent_initial_call=True,
)
def access_solution_documentation(n_clicks: int) -> list[dmc.Alert] | None:
    """Open the Solution's Documentation home page in the web browser."""
    solution_module = importlib.import_module("saf.solutions.examples")
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
def resolve_active_page_and_project_information(
    pathname: str,
) -> tuple[str | None, str | None]:
    """Resolve active page index and project ID based on current URL."""
    # Remove the GLOW_UI_PATH_PREFIX part from pathname
    relative_pathname = dash.strip_relative_path(pathname) or ""
    path_parts = relative_pathname.split("/") if relative_pathname else []

    # Keep legacy behavior: opening /projects/<project_id> lands on process logs page
    if len(path_parts) == 2 and path_parts[0] == "projects":
        project_id = path_parts[1]
        for i, page in enumerate(dash.page_registry.values()):
            if page["module"].split(".")[-1] == "process_logs_page":
                return str(i), project_id

    for i, page in enumerate(dash.page_registry.values()):
        if page["module"].split(".")[-1] == "not_found_404":
            continue
        template_parts = page["path_template"].strip("/").split("/")
        if len(path_parts) != len(template_parts):
            continue
        project_id = None
        matched = True
        for template_part, path_part in zip(template_parts, path_parts, strict=True):
            if template_part == "<project_id>":
                project_id = path_part
            elif template_part != path_part:
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
def render_nav_tree(active_index: str | None, switch_on: bool) -> Tree:
    """Render nav tree based on page registry and active index."""
    theme = "dark" if switch_on else "light"
    return Tree(
        aio_id="navigation_tree",
        items=get_page_list(theme, active_index),
        active_item_id=active_index,
    )


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
def display_page(project: ExamplesSolution, active_page_index: str | None) -> Any:
    """Return the selected page layout, injecting project or step as needed."""
    if active_page_index is None:
        return no_update

    try:
        _ = project.project_display_name
    except NotFoundException:
        return _get_404_layout()

    pages = list(dash.page_registry.values())
    index = int(active_page_index)
    page = pages[index]
    layout_func = page["layout"]

    if callable(layout_func):
        params = inspect.signature(layout_func).parameters
        kwargs: dict[str, Any] = {}
        if "project" in params:
            kwargs["project"] = project

        if "step" in params:
            step_attr = STEP_BY_PAGE_MODULE.get(page["module"])
            if step_attr:
                kwargs["step"] = getattr(project.steps, step_attr)

        for param_name in params:
            if param_name.endswith("_step") and hasattr(project.steps, param_name):
                kwargs[param_name] = getattr(project.steps, param_name)

        if kwargs:
            return layout_func(**kwargs)
        return layout_func()

    return layout_func


@callback(
    Output("page-content", "children"),
    Input("active-page-index", "data"),
    prevent_initial_call=True,
)
def display_404_page(active_page_index: str | None) -> Any:
    """Return the 404 page layout when the active page index is None."""
    if active_page_index is None:
        return _display_404_page()
    return no_update


@callback(
    Output("access-dev-guide", "children"),
    Input("color-scheme-switch", "checked"),
)
def update_nav_icons(switch_on: bool) -> DashIconify:
    """Update header icon color based on the current theme."""
    icon_color = "dark" if switch_on else "light"
    return html.Img(src=get_asset("teenyicons--doc-solid.svg", "icons", icon_color))


@callback(
    Output("url", "href"),
    Input(Tree.ids.selected_item("navigation_tree"), "data"),
    State("active-project-id", "data"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def open_new_page(value, project_id: str | None, pathname: str) -> str | None:
    """Navigate to the selected page."""
    if project_id is None or not value:
        return no_update

    try:
        item_index = int(Tree.ids.get_index_from_navlink_item_id(value))
    except (ValueError, TypeError):
        return no_update
    pages = list(dash.page_registry.values())
    if item_index >= len(pages):
        return no_update

    page = pages[item_index]
    # Add GLOW_UI_PATH_PREFIX to the path returned to the browser
    target_path = dash.get_relative_path(page["path_template"].replace("<project_id>", project_id))
    if target_path == pathname:
        return no_update
    return target_path


clientside_callback(
    """
    (switchOn) => {
        return switchOn ? 'dark' : 'light';
    }
    """,
    Output("mantine-provider", "forceColorScheme"),
    Input("color-scheme-switch", "checked"),
)


clientside_callback(
    """
    (switchOn) => {
        const host = document.getElementById('navbar-content');
        if (!host) {
            return window.dash_clientside.no_update;
        }
        if (switchOn) {
            host.style.color = '#E6EDF5';
        } else {
            host.style.color = '';
        }
        const svgs = host.querySelectorAll('svg');
        svgs.forEach((svg) => {
            if (switchOn) {
                svg.style.color = '#E6EDF5';
                svg.style.fill = '#E6EDF5';
                svg.style.stroke = '#E6EDF5';
                svg.style.opacity = '1';
            } else {
                svg.style.color = '';
                svg.style.fill = '';
                svg.style.stroke = '';
                svg.style.opacity = '';
            }
        });
        return window.dash_clientside.no_update;
    }
    """,
    Output("navbar-content", "style"),
    Input("color-scheme-switch", "checked"),
)
