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

"""
Transaction Supervisor
======================

A minimal Dash app showing how to use
:class:`~ansys.solutions.dash_super_components.TransactionSupervisor`
to monitor the progress of a SAF transaction method.

See the
`Transaction Supervisor
<https://upgraded-carnival-wn6lkym.pages.github.io/version/stable/api/dash-super-components/user-guide/transaction-supervisor.html#ref_transaction_supervisor>`_
page in the User Guide for the full reference documentation.

In a real SAF solution every step exposes one or more transaction methods
(decorated with ``@transaction``).  The GLOW REST API exposes their status at:

.. code-block:: text

    GET /steps/<step-name>:<method-name>

The :class:`~ansys.solutions.dash_super_components.TransactionSupervisor`
component polls that endpoint at a configurable interval and renders live
status information for the transaction method.
This example embeds a minimal Flask server that mimics the GLOW REST API so
you can explore the component without a running GLOW server.  The mock server
listens on ``http://127.0.0.1:8060``.
For a detailed example of how to set up this component with a full SAF solution, see the
`showcase example
<https://github.com/ansys/saf/blob/main/packages/dash-super-components/examples/showcase_all/src/ansys/solutions/showcase_dash_super_components/ui/pages/transaction_supervisor_page.py>`_
in the repository.

.. note::

   Run this file directly to launch the app:

   .. code-block:: bash

       pip install ansys-solutions-dash-super-components requests
       python example_transaction_supervisor.py

   Then open ``http://localhost:8050``. Use the buttons to trigger a
   successful or failing transaction and watch the transaction supervisor update in
   real time.
"""

# %%
# Set up imports and the Dash application
# ---------------------------------------
#
# :class:`~dash_mantine_components.MantineProvider` must wrap the entire layout
# for Mantine-based components to render correctly.  The React version must also
# be set **before** importing the component library — this is a Dash Mantine
# Components requirement when using Dash 2.x.
#
# A tiny Flask server is embedded in the same process as the Dash app so the
# mock GLOW API is ready before the component starts polling. This requires additional imports
# for the mock server and callbacks.

import threading
import time

from ansys.solutions.dash_super_components import TransactionSupervisor
from dash import _dash_renderer
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import DashProxy, Input, Output, callback, callback_context, dcc, html
import dash_mantine_components as dmc
from flask import Flask, Response, jsonify, request as flask_request
import requests
from werkzeug.serving import make_server

# Required only for Dash 2.x to use Mantine-based components
_dash_renderer._set_react_version("18.2.0")

app = DashProxy(__name__)

# %%
# Embedded mock GLOW API server
# --------------------------------
#
# ``TransactionSupervisor`` polls ``{glow_api_url}/steps/{step-name}:{method-name}``
# and expects a JSON body that contains a ``"status"`` field.  Recognized
# status values are ``"run-required"``, ``"running"``, ``"completed"`` and
# ``"failed"``.
#
# The mock server stores the current status for each ``step:method`` key in a
# plain Python dict that can be updated from Dash callbacks by POSTing to the
# mock server's ``/steps/<step_method>`` endpoint.

MOCK_API_PORT = 8060
MOCK_API_URL = f"http://127.0.0.1:{MOCK_API_PORT}"

# Simple dict owned exclusively by the mock server process/thread. Do not access from Dash callbacks
# as this is not thread-safe and is only intended to be updated via the mock server endpoints.
_statuses: dict[str, str] = {}

mock_server = Flask("mock_glow_api")


@mock_server.route("/steps/<path:step_method>", methods=["GET"])
def get_step_status(step_method: str) -> Response:
    """Get the status for *step_method*."""
    return jsonify({"status": _statuses.get(step_method, "run-required")})


@mock_server.route("/steps/<path:step_method>", methods=["POST"])
def set_step_status(step_method: str) -> Response:
    """Set the status for *step_method* (used by Dash callbacks to mock transaction status)."""
    _statuses[step_method] = flask_request.json["status"]
    return jsonify({"ok": True})


def _run_mock_server() -> None:
    server = make_server("127.0.0.1", MOCK_API_PORT, mock_server)
    server.serve_forever()


threading.Thread(target=_run_mock_server, daemon=True).start()

# %%
# Define steps and methods to monitor
# -----------------------------------
#
# Each ``TransactionSupervisor`` monitors a single *(step, method)* pair. Only one
# pair is defined here, but a real solution could include multiple supervisors monitoring different
# steps and methods.

STEP_NAME = "solver"
METHOD = "run_solution"

# %%
# Build the layout
# ----------------
#
# A :class:`~ansys.solutions.dash_super_components.TransactionSupervisor` can't be added directly to
# the layout because in a real SAF-based solution it needs access to the project URL, which is only
# available through the GLOW ``DashClient`` in a callback.
# Therefore, a placeholder ``html.Div`` is added to the layout and populated with the
# ``TransactionSupervisor`` instance later via a callback.

app.layout = dmc.MantineProvider(
    html.Div(
        [
            dcc.Location("url", refresh=False),
            dmc.Title("Transaction Supervisor", order=2, mb="md"),
            dmc.Text(
                "Use the buttons below to simulate different transaction outcomes "
                "and watch the status information update in real time.",
                c="dimmed",
                mb="xl",
            ),
            dmc.Group(
                [
                    dmc.Button("Simulate success", id="btn-success", color="green"),
                    dmc.Button("Simulate failure", id="btn-failure", color="red"),
                ],
                mb="xl",
            ),
            dmc.Text(f"Method: {METHOD}", fw=500, mb="sm"),
            html.Div(id="transaction_supervisor_placeholder"),
            dmc.Divider(my="xl"),
        ],
        style={"maxWidth": 960, "margin": "40px auto", "padding": "0 16px"},
    )
)

# %%
# Add the ``TransactionSupervisor`` in a callback
# -----------------------------------------------
#
# Add the ``TransactionSupervisor`` to the layout via a callback. The callback is triggered on page
# load and in a real SAF-based solution, the project URL would be injected via the GLOW
# ``DashClient``. In this example, the MOCK_API_URL is used directly.


@callback(
    Output("transaction_supervisor_placeholder", "children"),
    Input("url", "pathname"),
)
def initialize_transaction_supervisor(pathname: str) -> TransactionSupervisor:
    """Add the TransactionSupervisor component to the layout."""
    # In a SAF-based solution, retrieve the project.url:
    # project = DashClient[SuperComponentsExamplesSolution].get_project(pathname)
    # project_url = project.url

    # In this example, the MOCK_API_URL is used:
    project_url = MOCK_API_URL
    return TransactionSupervisor(
        url=project_url,
        step_name=STEP_NAME,
        method_name=METHOD,
        aio_id=f"transaction_supervisor_{METHOD}",
    )


# %%
# Add callbacks to simulate transactions
# ----------------------------------------
#
# The buttons update the mock-server status and then activate the supervisor so it starts polling.
# In a real SAF app the "activate" call would be triggered after calling a transaction method.
# Each ``TransactionSupervisor`` already contains its own ``activate_monitoring``
# store internally — writing ``True`` to it via a callback ``Output`` is sufficient to activate it.


@callback(
    Output(
        TransactionSupervisor.ids.activate_monitoring(f"transaction_supervisor_{METHOD}"), "data"
    ),
    Input("btn-success", "n_clicks"),
    Input("btn-failure", "n_clicks"),
    prevent_initial_call=True,
)
def mock_run_transaction_and_activate_supervison(
    n_success: int, n_failure: int
) -> bool | PreventUpdate:
    """Update mock statuses and activate supervision on all supervisors."""
    if not callback_context.triggered_id:
        raise PreventUpdate

    # Convert step and method names to the format expected by the mock server endpoint (hyphenated)
    step_name_hyphenated = STEP_NAME.replace("_", "-")
    method_hyphenated = METHOD.replace("_", "-")

    requests.post(
        f"{MOCK_API_URL}/steps/{step_name_hyphenated}:{method_hyphenated}",
        json={"status": "running"},
    )

    # Simulate async completion after 5s using a background thread
    def _complete():
        time.sleep(5)
        requests.post(
            f"{MOCK_API_URL}/steps/{step_name_hyphenated}:{method_hyphenated}",
            json={"status": "completed"},
        )

    # Simulate async failure after 4s using a background thread
    def _fail():
        time.sleep(4)
        requests.post(
            f"{MOCK_API_URL}/steps/{step_name_hyphenated}:{method_hyphenated}",
            json={"status": "failed"},
        )

    if callback_context.triggered_id == "btn-success":
        threading_target = _complete
    elif callback_context.triggered_id == "btn-failure":
        threading_target = _fail
    else:
        raise PreventUpdate

    threading.Thread(target=threading_target, daemon=True).start()

    # Returning True activates each supervisor's polling loop
    return True


# %%
# Run the app
# -----------

if __name__ == "__main__":
    app.run()
