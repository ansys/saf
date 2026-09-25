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

from ansys.saf.glow.client import DashClient, callback
import dash
from dash_extensions.enrich import Input, Output, State, callback_context, dcc, html
from dash_iconify import DashIconify
import dash_mantine_components as dmc

from {{ cookiecutter.__solution_namespace }}.{{ cookiecutter.__solution_module_name }}.solution.definition import {{ cookiecutter.__solution_definition_class_name }}


dash.register_page(__name__, name="{{ cookiecutter.__step_display_name }}", path_template="/projects/<project_id>/{{ cookiecutter.__step_module_name_hyphenated }}", icon_asset_name="game-icons--crossed-air-flows.svg", icon_asset_path="icons")


def layout(project: {{cookiecutter.__solution_definition_class_name}}):
    """Layout of the {{ cookiecutter.__step_name }} page."""
    step = project.steps.{{ cookiecutter.__step_module_name }}
    return html.Div(
        [
            html.H1("{{ cookiecutter.__step_display_name }}", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}),
            html.P(
                "Compute the sum of two numbers.",
                className="lead",
                style={"font-size": "20px"},
            ),
            dmc.Space(h=20),
            dmc.NumberInput(
                label="First Argument",
                id="{{ cookiecutter.__step_name }}-simple-hps-job-first-arg",
                value=step.first_arg,
                placeholder="Enter first argument",
                required=True,
                disabled=step.job_running,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
            dmc.Space(h=20),
            dmc.NumberInput(
                label="Second Argument",
                id="{{ cookiecutter.__step_name }}-simple-hps-job-second-arg",
                value=step.second_arg,
                placeholder="Enter second argument",
                required=True,
                disabled=step.job_running,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
            dmc.Space(h=20),
            dmc.Button(
                "Calculate",
                id="{{ cookiecutter.__step_name }}-simple-hps-calculate",
                leftSection=html.Img(src=dash.get_asset_url("icons/dark/streamline--startup-solid.svg")),
                radius="md",
                disabled=step.job_running,
                loading=False,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
            dmc.Space(h=20),
            dmc.TextInput(
                label="Result",
                id="{{ cookiecutter.__step_name }}-simple-hps-job-result",
                value=str(step.result) if step.has_result else "",
                disabled=True,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
                styles={"input": {"color": "black", "opacity": 1}},
            ),
            dmc.Space(h=20),
            dmc.Textarea(
                label="Job logs",
                id="{{ cookiecutter.__step_name }}-hps-logs-output",
                value=step.logs,
                disabled=True,
                autosize=True,
                minRows=4,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
                styles={"input": {"color": "black", "opacity": 1}},
            ),
            dmc.Space(h=20),
            dmc.Button(
                "Fetch result file",
                id="{{ cookiecutter.__step_name }}-fetch-result-file",
                radius="md",
                disabled=step.job_running or not step.has_result,
                loading=False,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
            ),
            dmc.Space(h=20),
            dmc.Textarea(
                label="Result file contents",
                id="{{ cookiecutter.__step_name }}-file-result-output",
                value=step.file_result or "",
                disabled=True,
                autosize=True,
                minRows=4,
                style={"width": "40%", "display": "inline-block", "marginLeft": "30%"},
                styles={"input": {"color": "black", "opacity": 1}},
            ),
            html.Div(
                [
                    DashClient.create_event_listener(
                        step, stream_name="{{ cookiecutter.__step_module_name_hyphenated }}-hps-simple-logs", id="{{ cookiecutter.__step_name }}-simple-hps-logs_ws"
                    )
                ]
            ),
            dcc.Store(id="{{ cookiecutter.__step_name }}-calculate-complete"),
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
            step, stream_name="{{ cookiecutter.__step_module_name_hyphenated }}-hps-simple-status", id="{{ cookiecutter.__step_name }}-simple-hps-status_ws"
        ),
        DashClient.create_event_listener(
            step, stream_name="{{ cookiecutter.__step_module_name_hyphenated }}-hps-simple-calculate", id="{{ cookiecutter.__step_name }}-simple-hps-termination_ws"
        ),
        DashClient.create_event_listener(
            step, stream_name="{{ cookiecutter.__step_module_name_hyphenated }}-fetch-result-file", id="{{ cookiecutter.__step_name }}-fetch-result-file-termination_ws"
        ),
    ]


@callback(
    Output("{{ cookiecutter.__step_name }}-simple-hps-calculate", "disabled"),
    Output("{{ cookiecutter.__step_name }}-simple-hps-calculate", "loading"),
    Output("{{ cookiecutter.__step_name }}-simple-hps-job-first-arg", "disabled"),
    Output("{{ cookiecutter.__step_name }}-simple-hps-job-second-arg", "disabled"),
    Output("{{ cookiecutter.__step_name }}-simple-hps-job-result", "value"),
    Output("{{ cookiecutter.__step_name }}-fetch-result-file", "disabled", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-hps-logs-output", "value", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-file-result-output", "value", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-simple-hps-calculate", "n_clicks"),
    Input("{{ cookiecutter.__step_name }}-simple-hps-termination_ws", "message"),
    Input("{{ cookiecutter.__step_name }}-fetch-result-file-termination_ws", "message"),
    Input("url", "pathname"),
)
def sync_{{ cookiecutter.__step_module_name }}_controls(n_clicks: int, message, fetch_message, project: {{ cookiecutter.__solution_definition_class_name }}):
    """Synchronize controls from step state and lock immediately when Calculate is clicked."""
    step = project.steps.{{ cookiecutter.__step_module_name }}
    trigger_id = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else None

    # Disable controls immediately when Calculate is clicked, even before the step state updates
    if trigger_id == "{{ cookiecutter.__step_name }}-simple-hps-calculate" and n_clicks and n_clicks > 0:
        return True, True, True, True, "", True, "", ""

    controls_disabled = step.job_running
    fetch_disabled = step.job_running or not step.has_result
    result_value = str(step.result) if step.has_result else ""
    return controls_disabled, controls_disabled, controls_disabled, controls_disabled, result_value, fetch_disabled, dash.no_update, dash.no_update


@callback(
    Output("{{ cookiecutter.__step_name }}-calculate-complete", "data"),
    Input("{{ cookiecutter.__step_name }}-simple-hps-calculate", "n_clicks"),
    State("{{ cookiecutter.__step_name }}-simple-hps-job-first-arg", "value"),
    State("{{ cookiecutter.__step_name }}-simple-hps-job-second-arg", "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def hps_simple_calculate(n_clicks: int, first_arg: int, second_arg: int, project: {{ cookiecutter.__solution_definition_class_name }}):
    """Trigger the computation."""
    step = project.steps.{{ cookiecutter.__step_module_name }}
    step.first_arg = first_arg
    step.second_arg = second_arg
    step.logs = ""
    step.file_result = ""
    step.{{ cookiecutter.__step_module_name }}_hps_simple_calculate()
    return {"status": "done"}


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-simple-hps-calculate", "n_clicks"),
    prevent_initial_call=True,
)
def notify_hps_job_started(n_clicks: int | None):
    """Raise an immediate notification and disable inputs when HPS calculation is triggered."""
    if not n_clicks or n_clicks <= 0:
        return []

    return [
        {
            "id": "{{ cookiecutter.__step_module_name }}-hps-simple-job-status-notification",
            "action": "show",
            "title": "{{ cookiecutter.__step_name }} HPS job",
            "message": "HPS job started.",
            "color": "blue",
            "loading": True,
            "autoClose": False,
        }
    ]


@callback(
    Output("{{ cookiecutter.__step_name }}-file-result-output", "value", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-fetch-result-file", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def fetch_result_file(n_clicks: int, project: {{ cookiecutter.__solution_definition_class_name }}):
    """Download the output file from the HPS project and display its contents."""
    step = project.steps.{{ cookiecutter.__step_module_name }}
    step.{{ cookiecutter.__step_module_name }}_fetch_result_file()
    return step.file_result


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Output("{{ cookiecutter.__step_name }}-fetch-result-file", "disabled", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-fetch-result-file", "n_clicks"),
    prevent_initial_call=True,
)
def notify_result_file_fetch_started(n_clicks: int | None):
    """Raise an immediate notification and disable the fetch button when result file fetching starts."""
    if not n_clicks or n_clicks <= 0:
        return [], dash.no_update

    return (
        [
            {
                "id": "{{ cookiecutter.__step_module_name }}-hps-simple-job-file-notification",
                "action": "show",
                "title": "{{ cookiecutter.__step_name }} result file",
                "message": "Fetching result file...",
                "color": "blue",
                "loading": True,
                "autoClose": False,
            }
        ],
        True,
    )


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-fetch-result-file-termination_ws", "message"),
    prevent_initial_call=True,
)
def notify_result_file_fetch_completed(message):
    """Update the result file notification and re-enable the fetch button when fetching completes."""
    if not message:
        return []

    return [
        {
            "id": "{{ cookiecutter.__step_module_name }}-hps-simple-job-file-notification",
            "action": "update",
            "title": "{{ cookiecutter.__step_name }} result file",
            "message": "Result file fetched.",
            "color": "green",
            "loading": False,
            "autoClose": 5000,
            "icon": DashIconify(icon="ic:round-check-circle", width=20),
        }
    ]


@callback(
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-simple-hps-status_ws", "message"),
    prevent_initial_call=True,
)
def update_status(message):
    """Raise notifications as status events are received from HPS."""
    if not message:
        return []

    status = json.loads(message["data"])

    if status.lower() == "evaluated":
        return [
            {
                "id": "{{ cookiecutter.__step_module_name }}-hps-simple-job-status-notification",
                "action": "update",
                "title": "{{ cookiecutter.__step_name }} HPS job",
                "message": "HPS job completed.",
                "color": "green",
                "loading": False,
                "autoClose": 5000,
                "icon": DashIconify(icon="ic:round-check-circle", width=20),
            }
        ]

    return [
        {
            "id": "{{ cookiecutter.__step_module_name }}-hps-simple-job-status-notification",
            "action": "update",
            "title": "{{ cookiecutter.__step_name }} HPS job status",
            "message": f"Status: {status}",
            "color": "blue",
            "loading": True,
            "autoClose": False,
        }
    ]


@callback(
    Output("{{ cookiecutter.__step_name }}-hps-logs-output", "value", allow_duplicate=True),
    Input("{{ cookiecutter.__step_name }}-simple-hps-logs_ws", "message"),
    prevent_initial_call=True,
)
def update_logs(message):
    """Update the logs text box as log events are received from HPS."""
    if not message:
        return dash.no_update
    return json.loads(message["data"])

