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


"""Frontend of the logs supervisor page.

Note: The LogsSupervisor component requires custom JavaScript for rendering log level badges and
no-rows overlays.
This is configured in app.py with:
    1. external_scripts=["/super-components/dashAgGridComponentFunctions.js"]
    2. add_super_components_assets(app)
"""

from ansys.saf.glow.client import DashClient, callback
from ansys.saf.glow.solution import MethodStatus
from ansys.solutions.dash_super_components import LogsSupervisor
from ansys.solutions.dash_super_components.utils.svg_icons import (
    IconNames,
    create_icon_span,
)
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import Input, Output, State, Trigger, ctx, html
import dash_mantine_components as dmc

from ansys.solutions.showcase_dash_super_components.solution.definition import (
    SuperComponentsExamplesSolution,
)
from ansys.solutions.showcase_dash_super_components.solution.simple_step import SimpleStep
from ansys.solutions.showcase_dash_super_components.ui.components.page_template import (
    layout as page_layout,
)
from ansys.solutions.showcase_dash_super_components.ui.utilities.common_classes import (
    CommonCSSClassNames,
)
from ansys.solutions.showcase_dash_super_components.ui.utilities.common_colors import CommonColors

INFO_CARD_TEXT = [
    (
        "Logs Supervisor displays process logs generated with Python's logging module "
        "in a filterable, sortable table powered by AG Grid."
    ),
    (
        "Click Generate Logs to start a long-running transaction that emits random log "
        "messages for 30 seconds. Both supervisors below listen to the same log source "
        "and refresh automatically when new entries are appended. "
        "The built-in switch enables or disables live monitoring independently, and the "
        "grid follows the Mantine light or dark color scheme."
    ),
]

_LOG_FORMAT = "%(asctime)s - %(levelname)s - %(module)s - %(message)s"


def layout(step: SimpleStep) -> html.Div:
    """Layout of the logs supervisor page."""
    main_content = html.Div(
        [
            # ── Shared generate-logs button ───────────────────────────────────────
            dmc.Button(
                "Generate Logs",
                id="generate-logs",
                leftSection=create_icon_span(
                    IconNames.STREAMLINE_STARTUP, size_px=16, color=CommonColors.WHITE
                ),
                radius="xs",
                loading=_method_in_progress(step, "generate_random_logs_with_cleanup"),
                className=CommonCSSClassNames.MANTINE_BUTTON,
            ),
            DashClient.create_event_listener(
                step,
                stream_name="generate-random-logs-with-cleanup",
                id="ws-generate-logs",
            ),
            dmc.Space(h=40),
            # ── Example 1 ────────────────────────────────────────────────────────
            html.Div(
                [
                    dmc.Text("Example 1 - Default Logs Supervisor", fw=700, size="xl"),
                    dmc.Text(
                        "Uses only the required constructor arguments with all defaults. "
                        "The component polls the log file every 3 seconds and displays "
                        "all log levels in the default dark AG Grid theme.",
                        size="sm",
                        c=CommonColors.MANTINE_DIMMED,
                        mb="sm",
                    ),
                    html.Div(
                        children=LogsSupervisor(
                            log_file=step.get_entity_url("logfile"),
                            log_format=_LOG_FORMAT,
                            aio_id="logs-supervisor-basic",
                        ),
                    ),
                ],
            ),
            dmc.Space(h=60),
            # ── Example 2 ────────────────────────────────────────────────────────
            html.Div(
                [
                    dmc.Text("Example 2 - Customized Logs Supervisor", fw=700, size="xl"),
                    dmc.Text(
                        "Demonstrates a faster polling interval of 1 second, a longer but narrower "
                        "grid with a fixed width, the light AG Grid theme, and no error "
                        "notifications.",
                        size="sm",
                        c=CommonColors.MANTINE_DIMMED,
                        mb="sm",
                    ),
                    html.Div(
                        children=LogsSupervisor(
                            log_file=step.get_entity_url("logfile"),
                            log_format=_LOG_FORMAT,
                            aio_id="logs-supervisor-advanced",
                            interval=1000,
                            grid_props={
                                "style": {"height": "400px"},
                                "dashGridOptions": {"theme": "themeBalham"},
                            },
                            width="600px",
                            show_error_notifications=False,
                        ),
                        style={"display": "flex", "justifyContent": "flex-start"},
                    ),
                ],
            ),
        ],
    )
    return page_layout(
        page_title="Logs Supervisor",
        info_card_text=INFO_CARD_TEXT,
        main_content=main_content,
    )


@callback(
    Output(LogsSupervisor.ids.activate_monitoring("logs-supervisor-basic"), "data"),
    Output(LogsSupervisor.ids.activate_monitoring("logs-supervisor-advanced"), "data"),
    Input("generate-logs", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def generate_logs(n_clicks: int, project: SuperComponentsExamplesSolution) -> tuple[bool, bool]:
    """Trigger the generate-logs transaction and activate supervision on both supervisors."""
    if not ctx.triggered_id or not n_clicks:
        raise PreventUpdate
    step = project.steps.simple_step
    step.generate_random_logs_with_cleanup()
    return True, True


@callback(
    Output("generate-logs", "loading", allow_duplicate=True),
    Input("generate-logs", "n_clicks"),
    prevent_initial_call=True,
)
def disable_button_on_click(n_clicks: int) -> bool:
    """Show loading state on the button immediately when clicked."""
    if not ctx.triggered_id or not n_clicks:
        raise PreventUpdate
    return True


@callback(
    Output("generate-logs", "loading", allow_duplicate=True),
    Trigger("ws-generate-logs", "message"),
    prevent_initial_call=True,
)
def enable_button_on_termination() -> bool:
    """Re-enable the button when the generate-logs transaction terminates."""
    return False


def _method_in_progress(step: SimpleStep, method_name: str) -> bool:
    """Return ``True`` if the given long-running method is currently executing."""
    return step.get_method_state(method_name).status == MethodStatus.Running
