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

"""Frontend of {{ cookiecutter.__step_name }}."""

import json
import logging

from ansys.saf.glow.client import DashClient, callback
import dash
from dash_extensions.enrich import Input, Output, State, callback_context, dcc, html
from dash_iconify import DashIconify
import dash_mantine_components as dmc

from ansys.saf.glow.solution import NO_ENTITY

from {{ cookiecutter.__solution_namespace }}.{{ cookiecutter.__solution_module_name }}.solution.definition import {{ cookiecutter.__solution_definition_class_name }}
from {{ cookiecutter.__solution_namespace }}.{{ cookiecutter.__solution_module_name }}.solution.{{ cookiecutter.__step_module_name }} import NUMBER_OF_DESIGN_POINTS, TERMINAL_STATUSES


dash.register_page(__name__, name="{{ cookiecutter.__step_display_name }}", path_template="/projects/<project_id>/{{ cookiecutter.__step_module_name_hyphenated }}", icon_asset_name="game-icons--crossed-air-flows.svg", icon_asset_path="icons")
logger = logging.getLogger(__name__)


def _result_text(value: float | None) -> str:
    return "" if value is None else str(value)


def _decode_ws_payload(message) -> str | list[str] | None:
    """Decode websocket payloads that are JSON-encoded twice by the event bridge."""
    if not message or "data" not in message:
        return None
    try:
        return json.loads(json.loads(message["data"]))
    except (TypeError, ValueError, KeyError):
        logger.exception("Failed to decode websocket payload.")
        return None


def _status_list_from_message(message) -> list[str] | None:
    """Decode and normalize design point statuses from a status websocket payload."""
    decoded = _decode_ws_payload(message)
    if not isinstance(decoded, list) or len(decoded) != NUMBER_OF_DESIGN_POINTS:
        return None
    return [str(status).lower() for status in decoded]


def layout(project: {{cookiecutter.__solution_definition_class_name}}):
    """Layout of the {{ cookiecutter.__step_name }} page."""
    step = project.steps.{{ cookiecutter.__step_module_name }}
    rows = []
    for index in range(NUMBER_OF_DESIGN_POINTS):
        rows.extend(
            [
                dmc.GridCol(
                    dmc.NumberInput(
                        id=f"{{ cookiecutter.__step_name }}-first-arg-{index}",
                        value=step.first_args[index],
                        required=True,
                        disabled=False,
                        hideControls=True,
                        style={"width": "140px"},
                    ),
                    span=3,
                ),
                dmc.GridCol(
                    dmc.NumberInput(
                        id=f"{{ cookiecutter.__step_name }}-second-arg-{index}",
                        value=step.second_args[index],
                        required=True,
                        disabled=False,
                        hideControls=True,
                        style={"width": "140px"},
                    ),
                    span=3,
                ),
                dmc.GridCol(html.Span("", id=f"{{ cookiecutter.__step_name }}-result-{index}"), span=3),
                dmc.GridCol(html.Span("No Job Created", id=f"{{ cookiecutter.__step_name }}-status-{index}"), span=3),
            ]
        )

    return html.Div(
        [
            html.H1("HPS {{ cookiecutter.__step_display_name }}", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}),
            html.P(
                "Run a 4-point parametric study for sum(A, B).",
                className="lead",
                style={"font-size": "20px"},
            ),
            dmc.Space(h=20),
            html.Div(
                dmc.Grid(
                    [
                        dmc.GridCol(html.Strong("A"), span=3),
                        dmc.GridCol(html.Strong("B"), span=3),
                        dmc.GridCol(html.Strong("A + B = C"), span=3),
                        dmc.GridCol(html.Strong("Execution Status"), span=3),
                        *rows,
                    ],
                    gutter="md",
                ),
                style={"width": "80%", "marginLeft": "10%"},
            ),
            dmc.Space(h=20),
            dmc.Button(
                "Run Parametric Study",
                id="{{ cookiecutter.__step_name }}-parametric-study-calculate",
                leftSection=html.Img(src=dash.get_asset_url("icons/dark/streamline--startup-solid.svg")),
                radius="md",
                disabled=step.job_running,
                loading=step.job_running,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
            dmc.Space(h=20),
            dmc.Textarea(
                label="Job logs",
                id="{{ cookiecutter.__step_name }}-hps-logs-output",
                value=step.logs,
                disabled=True,
                autosize=False,
                minRows=12,
                style={"width": "80%", "display": "inline-block", "marginLeft": "10%"},
                styles={
                    "input": {
                        "color": "black",
                        "opacity": 1,
                        "height": "280px",
                        "overflowY": "auto",
                        "whiteSpace": "pre-wrap",
                    }
                },
            ),
            dmc.Space(h=20),
            dmc.Select(
                label="Select design point",
                id="{{ cookiecutter.__step_name }}-file-result-selector",
                data=[{"value": str(i), "label": f"Design point {i + 1}"} for i in range(NUMBER_OF_DESIGN_POINTS)],
                value="0",
                disabled=True,
                clearable=False,
                allowDeselect=False,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
            dmc.Space(h=20),
            html.Div(
                [
                    dmc.Textarea(
                        label="Result file contents",
                        id="{{ cookiecutter.__step_name }}-file-result-output",
                        value="",
                        disabled=True,
                        autosize=True,
                        minRows=3,
                        styles={"input": {"color": "black", "opacity": 1}},
                    ),
                    dmc.LoadingOverlay(
                        id="{{ cookiecutter.__step_name }}-file-result-loading",
                        visible=False,
                        overlayProps={"radius": "sm", "blur": 2},
                    ),
                ],
                style={"position": "relative", "width": "80%", "marginLeft": "10%"},
            ),
            dcc.Store(id="{{ cookiecutter.__step_name }}-file-result-selected", data=None),
        ]
    )


@callback(
    Output("{{ cookiecutter.__step_name }}-event-listeners-container", "children"),
    Input("url", "pathname"),
)
def mount_{{ cookiecutter.__step_module_name }}_event_listeners(project: {{ cookiecutter.__solution_definition_class_name }}) -> list:
    """Mount {{ cookiecutter.__step_name }} event listeners in the persistent main layout."""
    step = project.steps.{{ cookiecutter.__step_module_name }}
    return [
        DashClient.create_event_listener(
            step, stream_name="{{ cookiecutter.__step_name_hyphenated }}-hps-parametric-status", id="{{ cookiecutter.__step_name }}-parametric-study-status_ws"
        ),
        DashClient.create_event_listener(
            step, stream_name="{{ cookiecutter.__step_name_hyphenated }}-hps-parametric-results", id="{{ cookiecutter.__step_name }}-parametric-study-results_ws"
        ),
        DashClient.create_event_listener(
            step, stream_name="{{ cookiecutter.__step_name_hyphenated }}-hps-parametric-logs", id="{{ cookiecutter.__step_name }}-parametric-study-logs_ws"
        ),
    ]


@callback(
    Output("{{ cookiecutter.__step_name }}-parametric-study-calculate", "disabled"),
    Output("{{ cookiecutter.__step_name }}-parametric-study-calculate", "loading"),
    Output("{{ cookiecutter.__step_name }}-first-arg-0", "disabled"),
    Output("{{ cookiecutter.__step_name }}-first-arg-1", "disabled"),
    Output("{{ cookiecutter.__step_name }}-first-arg-2", "disabled"),
    Output("{{ cookiecutter.__step_name }}-first-arg-3", "disabled"),
    Output("{{ cookiecutter.__step_name }}-second-arg-0", "disabled"),
    Output("{{ cookiecutter.__step_name }}-second-arg-1", "disabled"),
    Output("{{ cookiecutter.__step_name }}-second-arg-2", "disabled"),
    Output("{{ cookiecutter.__step_name }}-second-arg-3", "disabled"),
    Output("{{ cookiecutter.__step_name }}-file-result-selector", "disabled", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-file-result-selector", "value", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-parametric-study-calculate", "n_clicks"),
    Input("{{ cookiecutter.__step_name }}-parametric-study-status_ws", "message"),
)
def sync_input_controls(n_clicks: int, status_message):
    """Disable all input controls while the study is running; re-enable on termination."""
    trigger_id = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else None
    if trigger_id == "{{ cookiecutter.__step_name }}-parametric-study-calculate" and n_clicks and n_clicks > 0:
        return (True,) * 10 + (True, dash.no_update)

    statuses = _status_list_from_message(status_message)
    if statuses is None:
        return (dash.no_update,) * 12
    if all(status in TERMINAL_STATUSES for status in statuses):
        has_evaluated = any(status == "evaluated" for status in statuses)
        return (False,) * 10 + (not has_evaluated, "0")
    return (True,) * 10 + (True, dash.no_update)


@callback(
    Output("{{ cookiecutter.__step_name }}-result-0", "children"),
    Output("{{ cookiecutter.__step_name }}-result-1", "children"),
    Output("{{ cookiecutter.__step_name }}-result-2", "children"),
    Output("{{ cookiecutter.__step_name }}-result-3", "children"),
    Input("{{ cookiecutter.__step_name }}-parametric-study-calculate", "n_clicks"),
)
def sync_results(n_clicks: int):
    """Clear result cells when a new study is submitted."""
    trigger_id = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else None
    if trigger_id == "{{ cookiecutter.__step_name }}-parametric-study-calculate" and n_clicks and n_clicks > 0:
        return ("",) * NUMBER_OF_DESIGN_POINTS
    return (dash.no_update,) * NUMBER_OF_DESIGN_POINTS


@callback(
    Output("{{ cookiecutter.__step_name }}-result-0", "children", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-result-1", "children", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-result-2", "children", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-result-3", "children", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-parametric-study-results_ws", "message"),
    prevent_initial_call=True,
)
def update_result_cells(message):
    """Update result cells from the backend final-results event stream."""
    decoded = _decode_ws_payload(message)
    if not isinstance(decoded, list) or len(decoded) != NUMBER_OF_DESIGN_POINTS:
        return (dash.no_update,) * NUMBER_OF_DESIGN_POINTS
    return tuple(_result_text(value) for value in decoded)


@callback(
    Output("{{ cookiecutter.__step_name }}-hps-logs-output", "value", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-file-result-output", "value", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-file-result-selector", "disabled", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-status-0", "children", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-status-1", "children", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-status-2", "children", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-status-3", "children", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-parametric-study-calculate", "n_clicks"),
    prevent_initial_call=True,
)
def reset_on_submit(n_clicks: int | None):
    """Clear logs, file results, and statuses the moment the study is submitted."""
    if not n_clicks or n_clicks <= 0:
        return (dash.no_update,) * 7
    return ("", "", True, "submitting", "submitting", "submitting", "submitting")


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-parametric-study-calculate", "n_clicks"),
    State("{{ cookiecutter.__step_name }}-first-arg-0", "value"),
    State("{{ cookiecutter.__step_name }}-first-arg-1", "value"),
    State("{{ cookiecutter.__step_name }}-first-arg-2", "value"),
    State("{{ cookiecutter.__step_name }}-first-arg-3", "value"),
    State("{{ cookiecutter.__step_name }}-second-arg-0", "value"),
    State("{{ cookiecutter.__step_name }}-second-arg-1", "value"),
    State("{{ cookiecutter.__step_name }}-second-arg-2", "value"),
    State("{{ cookiecutter.__step_name }}-second-arg-3", "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def run_parametric_study(
    n_clicks: int,
    first_arg_0: float,
    first_arg_1: float,
    first_arg_2: float,
    first_arg_3: float,
    second_arg_0: float,
    second_arg_1: float,
    second_arg_2: float,
    second_arg_3: float,
    project: {{ cookiecutter.__solution_definition_class_name }},
):
    """Trigger the parametric study run and raise a start notification."""
    if not n_clicks:
        return []

    step = project.steps.{{ cookiecutter.__step_module_name }}
    step.first_args = [float(first_arg_0 or 0), float(first_arg_1 or 0), float(first_arg_2 or 0), float(first_arg_3 or 0)]
    step.second_args = [float(second_arg_0 or 0), float(second_arg_1 or 0), float(second_arg_2 or 0), float(second_arg_3 or 0)]
    step.hps_parametric_calculate()

    return [
        {
            "id": "{{ cookiecutter.__step_module_name }}-hps-parametric-status-notification",
            "action": "show",
            "title": "{{ cookiecutter.__step_name }} parametric study",
            "message": "Study started.",
            "color": "blue",
            "loading": True,
            "autoClose": False,
        }
    ]


@callback(
    Output("{{ cookiecutter.__step_name }}-file-result-selected", "data"),
    Output("{{ cookiecutter.__step_name }}-file-result-loading", "visible"),
    Input("{{ cookiecutter.__step_name }}-file-result-selector", "value"),
    prevent_initial_call=True,
)
def on_selector_change(selected: str | None):
    """Show the loading overlay immediately when the selector changes."""
    return selected, True


@callback(
    Output("{{ cookiecutter.__step_name }}-file-result-output", "value", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-file-result-loading", "visible", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-file-result-selected", "data"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def update_result_viewer(selected: str | None, project: {{ cookiecutter.__solution_definition_class_name }}):
    """Fetch the selected design point file content and hide the loading overlay."""
    if selected is None:
        return dash.no_update, False
    index = int(selected)
    handles = project.steps.{{ cookiecutter.__step_module_name }}.output_file_handles
    if index < 0 or index >= len(handles):
        return dash.no_update, False
    handle = handles[index]
    if not handle or handle == NO_ENTITY:
        return dash.no_update, False
    return project.storage_scope.get_text(handle), False


@callback(
    Output("{{ cookiecutter.__step_name }}-file-result-output", "value", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-parametric-study-status_ws", "message"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def populate_result_on_completion(message, project: {{ cookiecutter.__solution_definition_class_name }}):
    """Load DP 0 result file content when the study reaches a terminal state."""
    statuses = _status_list_from_message(message)
    if statuses is None or not all(status in TERMINAL_STATUSES for status in statuses):
        return dash.no_update
    step = project.steps.{{ cookiecutter.__step_module_name }}
    handle = step.output_file_handles[0]
    if handle and handle != NO_ENTITY:
        return project.storage_scope.get_text(handle)
    return dash.no_update


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-parametric-study-status_ws", "message"),
    prevent_initial_call=True,
)
def update_status_notification(message):
    """Update study notification from persistent parametric status events."""
    statuses = _status_list_from_message(message)
    if statuses is None:
        return []
    completed = sum(status in TERMINAL_STATUSES for status in statuses)

    if all(status == "timeout" for status in statuses):
        return [
            {
                "id": "{{ cookiecutter.__step_module_name }}-hps-parametric-status-notification",
                "action": "update",
                "title": "{{ cookiecutter.__step_name }} parametric study",
                "message": "Study timed out.",
                "color": "red",
                "loading": False,
                "autoClose": False,
                "icon": DashIconify(icon="ic:round-error", width=20),
            }
        ]

    if completed == NUMBER_OF_DESIGN_POINTS:
        notification = [
            {
                "id": "{{ cookiecutter.__step_module_name }}-hps-parametric-status-notification",
                "action": "update",
                "title": "{{ cookiecutter.__step_name }} parametric study",
                "message": "Study completed.",
                "color": "green",
                "loading": False,
                "autoClose": 5000,
                "icon": DashIconify(icon="ic:round-check-circle", width=20),
            }
        ]
    else:
        notification = [
            {
                "id": "{{ cookiecutter.__step_module_name }}-hps-parametric-status-notification",
                "action": "update",
                "title": "{{ cookiecutter.__step_name }} parametric study",
                "message": f"Design points completed: {completed}/{NUMBER_OF_DESIGN_POINTS}",
                "color": "blue",
                "loading": True,
                "autoClose": False,
            }
        ]

    return notification


@callback(
    Output("{{ cookiecutter.__step_name }}-status-0", "children"),
    Output("{{ cookiecutter.__step_name }}-status-1", "children"),
    Output("{{ cookiecutter.__step_name }}-status-2", "children"),
    Output("{{ cookiecutter.__step_name }}-status-3", "children"),
    Input("{{ cookiecutter.__step_name }}-parametric-study-status_ws", "message"),
    prevent_initial_call=True,
)
def update_status_cells(message):
    """Update status cells from page-scoped status events."""
    statuses = _status_list_from_message(message)
    if statuses is None:
        return (dash.no_update,) * NUMBER_OF_DESIGN_POINTS
    return statuses[0], statuses[1], statuses[2], statuses[3]


@callback(
    Output("{{ cookiecutter.__step_name }}-hps-logs-output", "value", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-parametric-study-logs_ws", "message"),
    State("{{ cookiecutter.__step_name }}-hps-logs-output", "value"),
    prevent_initial_call=True,
)
def update_logs(message, current_value):
    """Append new log delta to the logs text box as events are received from HPS."""
    decoded = _decode_ws_payload(message)
    if not isinstance(decoded, str):
        return dash.no_update
    return (current_value or "") + decoded
