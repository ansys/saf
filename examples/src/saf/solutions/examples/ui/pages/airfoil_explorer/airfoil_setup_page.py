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

"""Frontend of airfoil setup."""

from __future__ import annotations

from ansys.saf.glow.client import callback
from ansys.saf.glow.solution import NO_ENTITY, MethodStatus
from ansys.solutions.dash_super_components import LogsSupervisor
import dash
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from dash_extensions.enrich import Input, Output, State, callback_context, dcc, html, no_update
import dash_mantine_components as dmc

from saf.solutions.examples.solution.airfoil_explorer.airfoil_setup_step import AirfoilSetupStep
from saf.solutions.examples.solution.airfoil_explorer.utils.invalidation import (
    invalidate_mesh,
    invalidate_simulation_results,
)
from saf.solutions.examples.solution.airfoil_explorer.utils.logging import LOG_FORMAT
from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.ui.airfoil_explorer.components.airfoil_parameters_panel import (
    AIRFOIL_CAMBER_MAX_ID,
    AIRFOIL_CAMBER_POS_ID,
    AIRFOIL_HELP_ICON_ID,
    AIRFOIL_HELP_MODAL_ID,
    AIRFOIL_PRESET_ID,
    AIRFOIL_RESET_BUTTON_ID,
    AIRFOIL_THICKNESS_MAX_ID,
    airfoil_parameters_panel,
    get_preset_defaults,
)
from saf.solutions.examples.ui.airfoil_explorer.components.airfoil_tabs import (
    AIRFOIL_3D_CONTAINER_ID,
    AIRFOIL_3D_LOADING_OVERLAY_ID,
    AIRFOIL_SHAPE_FIGURE_ID,
    AIRFOIL_TABS_ID,
    airfoil_tabs,
)
from saf.solutions.examples.ui.airfoil_explorer.components.viewer import visor_dash_viewer as tdv
from saf.solutions.examples.ui.airfoil_explorer.settings import settings
from saf.solutions.examples.ui.airfoil_explorer.utils.images import get_image_url_with_cache_bust
from saf.solutions.examples.ui.airfoil_explorer.utils.paths import LOG_FILE_NAMES, get_step_log_file_path

dash.register_page(
    __name__,
    name="Airfoil Setup",
    path_template="/projects/<project_id>/airfoil-explorer/airfoil-setup",
)


AIRFOIL_GENERATE_BUTTON_ID = "airfoil-setup-generate"
AIRFOIL_LOGFILE_STORE_ID = "airfoil-logfile-store"
AIRFOIL_MONITOR_STORE_ID = "airfoil-monitor-store"
AIRFOIL_LOGS_SUPERVISOR_ID = "airfoil-logs-supervisor"
AIRFOIL_TITLE_ID = "airfoil-setup-title"
AIRFOIL_3D_LOADING_ID = "airfoil-3d-loading"


def _alert_hide() -> tuple[str, dict]:
    return "", {"display": "none"}


def _alert_show(message: str) -> tuple[str, dict]:
    return message, {"display": "block"}


def layout(project: ExamplesSolution) -> html.Div:
    """Layout of the airfoil setup page.

    Args:
        step: The AirfoilSetupStep instance with current state

    Returns:
        Dash HTML Div containing the page layout
    """
    step = project.steps.airfoil_setup_step

    log_file = get_step_log_file_path(step, project, LOG_FILE_NAMES["airfoil_setup"])

    image_url = None
    if step.airfoil_shape_png_handle != NO_ENTITY:
        try:
            image_url = step.get_entity_url("airfoil_shape_png_handle")
        except Exception:
            image_url = None

    return html.Div(
        [
            dmc.Alert(
                id="airfoil-error-alert",
                c="red",
                variant="light",
                withCloseButton=True,
                style={"display": "none"},
            ),
            dcc.Store(id=AIRFOIL_LOGFILE_STORE_ID, data=log_file),
            dmc.Stack(
                gap="sm",
                children=[
                    dmc.Text(
                        f"NACA 4-digit airfoil {step.naca_preset}",
                        id=AIRFOIL_TITLE_ID,
                        size="xl",
                        fw=700,
                    ),
                    dmc.Text(
                        (
                            "Define airfoil geometry parameters and preview the resulting shape "
                            "before generating the model."
                        ),
                        c="dimmed",
                    ),
                ],
            ),
            dmc.Space(h=20),
            dbc.Row(
                [
                    dbc.Col(
                        dmc.Card(
                            withBorder=True,
                            shadow="sm",
                            p="lg",
                            children=dmc.Stack(
                                gap="lg",
                                children=[
                                    airfoil_parameters_panel(
                                        naca_preset=step.naca_preset,
                                        camber_max_percent=step.camber_max_percent,
                                        camber_pos_percent=step.camber_pos_percent,
                                        thickness_max_percent=step.thickness_max_percent,
                                    ),
                                    dmc.Button("Generate Geometry", id=AIRFOIL_GENERATE_BUTTON_ID),
                                ],
                            ),
                        ),
                        width=4,
                    ),
                    dbc.Col(
                        dmc.Card(
                            withBorder=True,
                            shadow="sm",
                            p="lg",
                            children=airfoil_tabs(
                                log_file=log_file,
                                figure=step.airfoil_shape_figure or {},
                                image_url=image_url,
                                logs_supervisor_id=AIRFOIL_LOGS_SUPERVISOR_ID,
                            ),
                        ),
                        width=8,
                    ),
                ],
            ),
        ]
    )


def _build_tab_visor_viewer(
    service_launch_step,
    sim_step: AirfoilSetupStep,
    visor_message: dict,
    visor_restart_message: dict,
):
    if not visor_message and not visor_restart_message:
        return html.Div()

    viewer = tdv.get_visor_dash_component(
        id="visor_geom_viewer",
        host=service_launch_step.visor_host,
        port=service_launch_step.visor_port,
    )
    if sim_step.vtp_2D_foil != NO_ENTITY:
        service_launch_step.update_visor(
            vtp_handle=sim_step.vtp_2D_foil,
            model_name="2D_Airfoil_Model",
        )
    return viewer


def _build_tab_geometry_status(project: ExamplesSolution, sim_step: AirfoilSetupStep):
    geometry_generated = sim_step.vtp_2D_foil != NO_ENTITY
    status = "Generated" if geometry_generated else "Not Generated"
    path_info = f"File saved at: {project.storage_scope.get_cached(sim_step.vtp_2D_foil)}" if geometry_generated else ""

    return html.Div(
        dmc.Alert(
            title=f"Geometry Status: {status}",
            color="green" if geometry_generated else "yellow",
            children=[
                dmc.Text(
                    "The 3D geometry is ready."
                    if geometry_generated
                    else "Click 'Generate Geometry' to create the 3D model."
                ),
                dmc.Code(path_info, block=True, style={"marginTop": "10px"}) if path_info else None,
            ],
            variant="light",
        ),
        style={"padding": "20px"},
    )


@callback(
    Output(f"{AIRFOIL_SHAPE_FIGURE_ID}-graph", "style"),
    Output(f"{AIRFOIL_SHAPE_FIGURE_ID}-image", "style"),
    Input(f"{AIRFOIL_SHAPE_FIGURE_ID}-toggle", "checked"),
)
def toggle_airfoil_view(is_interactive: bool) -> tuple[dict, dict]:
    """Toggle between interactive (graph) and fast (image) views."""
    graph_style = {"display": "block", "width": "100%", "height": "auto"} if is_interactive else {"display": "none"}
    image_style = {"display": "none"} if is_interactive else {"display": "block", "width": "100%", "height": "auto"}
    return graph_style, image_style


@callback(
    Output(AIRFOIL_HELP_MODAL_ID, "opened"),
    Input(AIRFOIL_HELP_ICON_ID, "n_clicks"),
    prevent_initial_call=True,
)
def open_airfoil_help_modal(n_clicks: int) -> bool:
    """Open the airfoil parameters help modal when the icon is clicked."""
    if not n_clicks:
        raise PreventUpdate
    return True


@callback(
    Output(AIRFOIL_GENERATE_BUTTON_ID, "disabled"),
    Input(AIRFOIL_GENERATE_BUTTON_ID, "n_clicks"),
    State(AIRFOIL_GENERATE_BUTTON_ID, "disabled"),
    prevent_initial_call=True,
)
def disable_button_on_click(n_clicks: int | None, currently_disabled: bool) -> bool | type[no_update]:
    """Disable the button immediately when clicked."""
    if n_clicks and not currently_disabled:
        return True
    return no_update


@callback(
    Output(AIRFOIL_GENERATE_BUTTON_ID, "disabled"),
    Input(f"{AIRFOIL_SHAPE_FIGURE_ID}-graph", "figure"),
    Input(f"{AIRFOIL_SHAPE_FIGURE_ID}-graph", "loading_state"),
    State(AIRFOIL_GENERATE_BUTTON_ID, "disabled"),
)
def re_enable_button_on_completion(
    _figure: dict,
    loading_state: dict | None,
    currently_disabled: bool,
) -> bool | type[no_update]:
    """Re-enable the button when the transaction completes."""
    if currently_disabled:
        if loading_state and loading_state.get("is_loading"):
            return True
        return False
    return no_update


@callback(
    Output(AIRFOIL_CAMBER_MAX_ID, "value"),
    Output(AIRFOIL_CAMBER_POS_ID, "value"),
    Output(AIRFOIL_THICKNESS_MAX_ID, "value"),
    Output(AIRFOIL_CAMBER_MAX_ID, "disabled"),
    Output(AIRFOIL_CAMBER_POS_ID, "disabled"),
    Output(AIRFOIL_THICKNESS_MAX_ID, "disabled"),
    Input(AIRFOIL_PRESET_ID, "value"),
    prevent_initial_call=True,
)
def sync_with_preset(preset: str) -> tuple[float, float, float, bool, bool, bool]:
    """Auto-fill percentage inputs when a preset is selected and lock fields unless custom.

    Args:
        preset: Selected NACA preset value

    Returns:
        Tuple of (camber_max, camber_pos, thickness_max, disabled*, disabled*, disabled*)
    """
    if preset == "custom":
        return no_update, no_update, no_update, False, False, False
    defaults = get_preset_defaults(preset)
    return defaults["camber"], defaults["pos"], defaults["thickness"], True, True, True


@callback(
    Output(AIRFOIL_PRESET_ID, "value"),
    Input(AIRFOIL_RESET_BUTTON_ID, "n_clicks"),
    prevent_initial_call=True,
)
def reset_to_default(n_clicks: int) -> str:
    """Reset the UI controls to the default preset.

    Args:
        n_clicks: Number of reset button clicks

    Returns:
        Default preset value
    """
    del n_clicks
    return "2412"


@callback(
    Output(AIRFOIL_TITLE_ID, "children"),
    Input(AIRFOIL_PRESET_ID, "value"),
)
def update_title(preset: str) -> str:
    """Update the page title when preset changes.

    Args:
        preset: Selected NACA preset value

    Returns:
        Formatted title string
    """
    return f"NACA 4-digit airfoil {preset}"


@callback(
    Output(AIRFOIL_LOGFILE_STORE_ID, "data", allow_duplicate=True),
    Input(AIRFOIL_PRESET_ID, "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def clear_vtp_on_preset_change(preset: str, project: ExamplesSolution) -> str | type[no_update]:
    """Call backend transaction to clear stored VTP handle when preset changes."""
    service_launch_step = project.steps.service_launch_step
    if preset is None:
        raise PreventUpdate
    step = project.steps.airfoil_setup_step
    step.reset_vtp_handle()
    return step.logfile


@callback(
    Output(AIRFOIL_LOGS_SUPERVISOR_ID, "log_file"),
    Input(AIRFOIL_LOGFILE_STORE_ID, "data"),
)
def update_airfoil_logs_supervisor(log_file: str | None) -> str | type[no_update]:
    """Keep the airfoil LogsSupervisor pointed to the latest logfile."""
    if not log_file:
        raise PreventUpdate
    return log_file


@callback(
    Output(LogsSupervisor.ids._log_file_and_format(AIRFOIL_LOGS_SUPERVISOR_ID), "data"),
    Input(AIRFOIL_LOGFILE_STORE_ID, "data"),
)
def sync_airfoil_logs_storage(log_file: str | None) -> dict | type[no_update]:
    """Keep LogsSupervisor storage in sync with the latest logfile path/format."""
    if not log_file:
        raise PreventUpdate
    return {"log_file_path": log_file, "log_format": LOG_FORMAT}


@callback(
    Output(f"{AIRFOIL_SHAPE_FIGURE_ID}-graph", "figure"),
    Output(f"{AIRFOIL_SHAPE_FIGURE_ID}-image", "src"),
    Output(f"{AIRFOIL_SHAPE_FIGURE_ID}-toggle", "checked"),  # Sync toggle state
    Output("airfoil-error-alert", "children"),
    Output("airfoil-error-alert", "style"),
    Output(AIRFOIL_LOGFILE_STORE_ID, "data", allow_duplicate=True),
    Input(AIRFOIL_PRESET_ID, "value"),
    Input(AIRFOIL_CAMBER_MAX_ID, "value"),
    Input(AIRFOIL_CAMBER_POS_ID, "value"),
    Input(AIRFOIL_THICKNESS_MAX_ID, "value"),
    State("url", "pathname"),
)
def generate_geometry(
    preset: str,
    camber_max: float,
    camber_pos: float,
    thickness_max: float,
    project: ExamplesSolution,
) -> tuple[dict, str, bool, str, dict, str | None]:
    """Persist parameters and regenerate the airfoil shape on input changes."""
    if preset is None or camber_max is None or camber_pos is None or thickness_max is None:
        raise PreventUpdate

    step = project.steps.airfoil_setup_step

    # Check if parameters actually changed
    params_unchanged = (
        preset == step.naca_preset
        and float(camber_max) == step.camber_max_percent
        and float(camber_pos) == step.camber_pos_percent
        and float(thickness_max) == step.thickness_max_percent
    )

    # If params unchanged AND figure exists, skip regeneration (e.g., navigation back)
    if params_unchanged and step.airfoil_shape_figure:
        # Return existing data without regenerating or invalidating mesh
        figure = step.airfoil_shape_figure
        image_url = get_image_url_with_cache_bust(step, "airfoil_shape_png_handle")
        toggle_checked = bool(figure and figure.get("data"))
        msg, style = _alert_hide()
        return figure, image_url, toggle_checked, msg, style, step.logfile

    # Parameters changed - update step and regenerate
    step.naca_preset = preset
    step.camber_max_percent = float(camber_max)
    step.camber_pos_percent = float(camber_pos)
    step.thickness_max_percent = float(thickness_max)

    try:
        step.generate_geometry()
        # Invalidate mesh and simulation results - airfoil changed
        sim_step = project.steps.simulation_step
        invalidate_mesh(sim_step, reason="Airfoil Changed")
        invalidate_simulation_results(sim_step, reason="Airfoil Changed")

        # Get results - both JSON and PNG now exist
        figure = step.airfoil_shape_figure or {}

        # Get PNG URL with cache-busting to force browser reload
        image_url = get_image_url_with_cache_bust(step, "airfoil_shape_png_handle")

        # Set toggle: ON (interactive) since we have both now
        toggle_checked = bool(figure and figure.get("data"))

        msg, style = _alert_hide()
        return figure, image_url, toggle_checked, msg, style, step.logfile
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-except
        msg, style = _alert_show(f"Airfoil generation failed: {exc}")
        return no_update, no_update, no_update, msg, style, step.logfile


@callback(
    Output(AIRFOIL_TABS_ID, "value"),
    Input(AIRFOIL_GENERATE_BUTTON_ID, "n_clicks"),
    Input(AIRFOIL_PRESET_ID, "value"),
    prevent_initial_call=True,
)
def switch_tab_on_generate_or_preset(n_clicks: int | None, preset: str | None) -> str:
    """Switch tabs based on user actions.

    - Generate clicked -> switch to `3d`
    - Preset changed -> switch to `shape`
    """
    ctx = callback_context
    if not getattr(ctx, "triggered", None):
        raise PreventUpdate
    triggered = ctx.triggered[0].get("prop_id", "")
    if triggered.startswith(AIRFOIL_GENERATE_BUTTON_ID):
        if not n_clicks:
            raise PreventUpdate
        return "3d"
    if triggered.startswith(AIRFOIL_PRESET_ID):
        if preset is None:
            raise PreventUpdate
        return "shape"
    raise PreventUpdate


@callback(
    Output(AIRFOIL_3D_LOADING_OVERLAY_ID, "children"),
    Output(AIRFOIL_3D_LOADING_OVERLAY_ID, "style"),
    Input(AIRFOIL_GENERATE_BUTTON_ID, "n_clicks"),
    Input(AIRFOIL_TABS_ID, "value"),
    Input(AIRFOIL_3D_CONTAINER_ID, "children"),
    State("url", "pathname"),
    State(AIRFOIL_GENERATE_BUTTON_ID, "disabled"),
    Input("visor_termination_listener", "message"),
    Input("visor_restart_listener", "message"),
    prevent_initial_call=True,
)
def message_controller(
    n_clicks: int | None,
    tab_value: str | None,
    viewer_children: html.Div | None,
    project: ExamplesSolution,
    gen_button_disabled: bool,
    visor_message: dict,
    visor_restart_message: dict,
) -> tuple[html.Div | type[no_update], dict]:
    """Single writer for the 3D loading message."""
    is_visor_enabled = settings.visor_enabled

    if tab_value == "3d" and n_clicks and gen_button_disabled:
        if is_visor_enabled:
            alert = dmc.Alert(
                title="Generating Geometry",
                color="red",
                children=(
                    "This involves the geometry service STC, where the airfoil parameters are used "
                    "and the 3D geometry is generated. The generated Ansys geometry is then "
                    "tessellated into a VTK mesh object, for Visor visualization. This may take a moment."
                ),
                variant="light",
            )
            # temporarily not displaying the alert, until we decide the standard of feedback
            style = {"display": "none"}
            return alert, style
        else:
            return no_update, {"display": "none"}

    # Contextual messages when 3D tab is selected
    if tab_value == "3d":
        if not is_visor_enabled:
            return no_update, {"display": "none"}

        sim_step = project.steps.airfoil_setup_step
        style = {"display": "block"}
        if not visor_message and not visor_restart_message:
            alert = dmc.Alert(
                title="Visor launching",
                color="yellow",
                children="Visor service is launching — viewer will load shortly",
                variant="light",
            )
            return alert, style
        if sim_step.vtp_2D_foil == NO_ENTITY:
            alert = dmc.Alert(
                title="Geometry required",
                color="yellow",
                children=(
                    "The geometry file is missing or out of date for the current parameters. "
                    "Click Generate Geometry to create or update it."
                ),
                variant="light",
            )
            return alert, style

    return no_update, {"display": "none"}


def _apply_airfoil_form_to_step(
    step: AirfoilSetupStep,
    *,
    preset: str | None,
    camber_max: float | None,
    camber_pos: float | None,
    thickness_max: float | None,
) -> None:
    if preset is not None:
        step.naca_preset = preset
    if camber_max is not None:
        step.camber_max_percent = float(camber_max)
    if camber_pos is not None:
        step.camber_pos_percent = float(camber_pos)
    if thickness_max is not None:
        step.thickness_max_percent = float(thickness_max)


def _ensure_geom_service_running(service_launch_step) -> None:
    geom_status = service_launch_step.get_method_state("launch_geom_service").status
    if geom_status in (MethodStatus.RunRequired, MethodStatus.Failed):
        long_running_obj = service_launch_step.launch_geom_service()
        long_running_obj.wait(timeout=300)


def _ensure_visor_running(service_launch_step) -> None:
    visor_status = service_launch_step.get_method_state("launch_visor").status
    if visor_status in (MethodStatus.RunRequired, MethodStatus.Failed):
        long_running_obj = service_launch_step.launch_visor()
        long_running_obj.wait(timeout=300)


def _sync_visor_geometry_view(service_launch_step, step: AirfoilSetupStep) -> None:
    if step.vtp_2D_foil == NO_ENTITY or not settings.visor_enabled:
        return

    _ensure_visor_running(service_launch_step)
    service_launch_step.update_visor(vtp_handle=step.vtp_2D_foil, model_name="2D_Airfoil_Model")


def _build_3d_geometry_viewer(project: ExamplesSolution, step: AirfoilSetupStep, service_launch_step):
    if settings.visor_enabled:
        return tdv.get_visor_dash_component(
            id="visor_geom_viewer",
            host=service_launch_step.visor_host,
            port=service_launch_step.visor_port,
        )

    status = "Generated" if step.vtp_2D_foil != NO_ENTITY else "Failed"
    path_info = ""
    if step.vtp_2D_foil != NO_ENTITY:
        path_info = f"File saved at: {project.storage_scope.get_cached(step.vtp_2D_foil)}"

    return html.Div(
        dmc.Alert(
            title=f"Geometry Status: {status}",
            color="green" if status == "Generated" else "red",
            children=[
                dmc.Text(f"The 3D geometry has been {status.lower()}."),
                dmc.Code(path_info, block=True, style={"marginTop": "10px"}) if path_info else None,
            ],
            variant="light",
        ),
        style={"padding": "3px"},
    )


@callback(
    Output(AIRFOIL_LOGFILE_STORE_ID, "data", allow_duplicate=True),
    Output(AIRFOIL_3D_CONTAINER_ID, "children", allow_duplicate=True),
    Output(AIRFOIL_3D_LOADING_OVERLAY_ID, "children", allow_duplicate=True),
    Output(AIRFOIL_3D_LOADING_OVERLAY_ID, "style", allow_duplicate=True),
    Input(AIRFOIL_GENERATE_BUTTON_ID, "n_clicks"),
    State(AIRFOIL_PRESET_ID, "value"),
    State(AIRFOIL_CAMBER_MAX_ID, "value"),
    State(AIRFOIL_CAMBER_POS_ID, "value"),
    State(AIRFOIL_THICKNESS_MAX_ID, "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def request_3d_geometry(
    n_clicks: int | None,
    preset: str | None,
    camber_max: float | None,
    camber_pos: float | None,
    thickness_max: float | None,
    project: ExamplesSolution,
) -> tuple[str | None, html.Div | str | dict, html.Div | str | dict, dict]:
    """Handle 3D geometry generation and update viewer."""
    if not n_clicks:
        raise PreventUpdate
    step = project.steps.airfoil_setup_step
    _apply_airfoil_form_to_step(
        step,
        preset=preset,
        camber_max=camber_max,
        camber_pos=camber_pos,
        thickness_max=thickness_max,
    )

    service_launch_step = project.steps.service_launch_step
    _ensure_geom_service_running(service_launch_step)
    step.generate_3d()
    _sync_visor_geometry_view(service_launch_step, step)

    viewer = _build_3d_geometry_viewer(project, step, service_launch_step)
    return step.logfile, viewer, "", {"display": "none"}


@callback(
    Output(AIRFOIL_GENERATE_BUTTON_ID, "disabled"),
    Input(AIRFOIL_3D_CONTAINER_ID, "children"),
    State(AIRFOIL_GENERATE_BUTTON_ID, "disabled"),
)
def re_enable_button_on_3d_completion(
    _children: html.Div | dmc.Alert | None,
    currently_disabled: bool,
) -> bool | type[no_update]:
    """Re-enable the button when the 3D geometry request completes."""
    if currently_disabled:
        return False
    return no_update


@callback(
    Output(AIRFOIL_3D_CONTAINER_ID, "children", allow_duplicate=True),
    Input(AIRFOIL_TABS_ID, "value"),
    Input("visor_termination_listener", "message"),
    Input("visor_restart_listener", "message"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def on_tab_selected(tab_value: str, visor_message: dict, visor_restart_message: dict, project: ExamplesSolution):
    """Load Visor viewer when 3D tab is selected or Visor service completes.

    When the user switches to the 3D visualization tab or when Visor finishes launching,
    we return the visor viewer component. For other tabs we only update the
    monitor store and leave the 3D container unchanged.
    """
    if tab_value != "3d":
        raise PreventUpdate

    sim_step = project.steps.airfoil_setup_step
    if settings.visor_enabled:
        return _build_tab_visor_viewer(
            project.steps.service_launch_step,
            sim_step,
            visor_message,
            visor_restart_message,
        )
    return _build_tab_geometry_status(project, sim_step)
