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

from collections.abc import Callable
from functools import wraps
import importlib
import inspect
import logging
import os
from typing import Any, Generic, TypeVar

from fastapi.security.utils import get_authorization_scheme_param
from opentelemetry import trace

from ansys.iam.oidc import DEFAULT_SUBPROTOCOL_PREFIX, encode_base64_token
from ansys.saf.glow._client.client import Client
from ansys.saf.glow._config.const import (
    GLOW_API_URL,
    GLOW_DEPLOYMENT,
    GLOW_EXTERNAL_API_URL,
    GLOW_PORTAL_URL,
    GLOW_SOLUTION_DEFINITION,
    GLOW_WS_EVENTS_ADDR,
    Deployment,
)
from ansys.saf.glow._core.solution import Solution
from ansys.saf.glow._core.step_model import StepModel
from ansys.saf.glow._utilities.conversion import python_identifier_to_url_part
from ansys.saf.glow._utilities.solution_modules import find_solution

T = TypeVar("T", bound=Solution)
logger = logging.getLogger(__name__)


class DashClient(Generic[T]):
    """Client for use in the Dash UI framework that enables access to remote GLOW Solution."""

    @staticmethod
    def _auth_header_from_ctx() -> str | None:
        # ctx.headers was added in Dash 2.18.2
        # See: https://github.com/plotly/dash/blob/dev/CHANGELOG.md#2182---2024-11-04, PR#3051
        # keep dash an optional dependency
        from dash import ctx  # pyright: ignore[reportMissingTypeStubs]

        if ctx and hasattr(ctx, "headers"):
            return ctx.headers.get("Authorization")  # type: ignore

    @staticmethod
    def _get_project_name_from_pathname(pathname: str) -> str:
        # Strip query parameters and ensure pathname starts and ends with /
        normalized = "/" + pathname.split("?")[0].strip("/") + "/"

        # we support other "projects" appearances in the pathname, but we assume the last one is the relevant
        # one for the project to load.
        parts = normalized.rsplit("/projects/", 1)
        if len(parts) == 1:
            raise RuntimeError(f"Invalid {pathname=}. It should contain ``projects/<project_id>``.")
        project_id = parts[1].split("/")[0]
        if not project_id:
            raise RuntimeError(f"Invalid {pathname=}. It should contain ``projects/<project_id>``.")
        return f"projects/{project_id}"

    @staticmethod
    def get_portal_ui_url() -> str | None:
        """Return the URL of the SAF Portal UI. This URL is typically
        exposed as a link that enables the user to return to the
        Portal UI after using the Solution UI for a specific project.

        Returns
        -------

        str
            The URL of the SAF Portal UI.
        """
        return os.environ.get(GLOW_PORTAL_URL)

    @staticmethod
    def get_deployment_type() -> Deployment:
        """Return the deployment type derived from the value of the ``GLOW_DEPLOYMENT`` environment variable
        which corresponds to how the server in which the client is running is deployed.
        Normally this will be the UI server of the solution.

        Returns
        -------
        Deployment
            The deployment type derived from the value of the ``GLOW_DEPLOYMENT`` environment variable
            which corresponds to how the server in which the client is running is deployed.
            Normally this will be the UI server of the solution.
        """
        return Deployment(os.environ.get(GLOW_DEPLOYMENT, Deployment.Desktop.value))

    @staticmethod
    def create_event_listener(  # pyright: ignore[reportUnknownParameterType]
        step: StepModel,
        stream_name: str,
        id: str,  # noqa: A002
    ) -> "WebSocket":  # noqa: F821  # pyright: ignore[reportUndefinedVariable]
        """Return a WebSocket configured to receive data from transaction events
        on the ``stream_name`` channel.

        Parameters
        ----------
        step: StepModel
            The instance of the step used on the UI layout.
        stream_name: str
            The name of the stream that the WebSocket will try to connect to.
            A step may have multiple streams.
        id : str
            The identifier used on the HTML element that contains the WebSocket.

        Returns
        -------
        WebSocket
            A WebSocket configured to receive events data on the ``stream_name`` channel.

        Examples
        --------

         >>> layout = html.Div([
         >>>    html.Button("Trigger Event", id="trigger_event", n_clicks=0),
         >>>    html.Div(id="event_message", children="Not triggered yet"),
         >>>    html.Div(id="ws_container"),
         >>> ])
         >>>
         >>> @callback(
         >>>   Input("trigger_event", "n_clicks"),
         >>>   State("url", "pathname"),
         >>>   prevent_initial_call=True,
         >>> )
         >>> def trigger_transaction_event(n_clicks, project: MySolution):
         >>>    if n_clicks > 0:
         >>>        step = project.steps.my_step
         >>>        step.trigger_event()
         >>>
         >>> @callback(
         >>>     Output("event_message", "children"),
         >>>     Input("my_ws", "message"),
         >>>     prevent_initial_call=True,
         >>> )
         >>> def message(message):
         >>>     if message:
         >>>         return f"Received message: {message['data']}"
         >>>     else:
         >>>         return "No message received yet."
        """
        # keep flask and dash_extensions an optional dependency
        from dash_extensions import WebSocket  # pyright: ignore[reportMissingTypeStubs]
        import flask

        step_id = python_identifier_to_url_part(step._step_name)  # type: ignore
        project_id = step._project_url.rstrip("/").split("/")[-1]  # type: ignore
        project_name = f"projects/{project_id}"

        api_url = os.environ.get(GLOW_WS_EVENTS_ADDR)
        if not api_url:
            raise RuntimeError(
                f"The {GLOW_WS_EVENTS_ADDR} environment variable must be configured to use websockets on the UI.",
            )
        api_url_with_ws = f"{os.environ[GLOW_WS_EVENTS_ADDR]}"
        if not api_url_with_ws.startswith("ws://") and not api_url_with_ws.startswith("wss://"):
            api_url_with_ws = f"ws://{api_url_with_ws}"
        logger.info(f"Creating websocket with url={api_url_with_ws} and id={id}")

        websocket_args: Any = {
            "id": id,
            "url": f"{api_url_with_ws}/events/{project_name}/steps/{step_id}/streams/{stream_name}",
        }

        if flask.has_request_context():
            scheme, token = get_authorization_scheme_param(flask.request.headers.get("Authorization"))
            if scheme.lower() == "bearer":
                logger.debug("Bearer token injected into the WebSocket for authorization.")
                encoded_token = encode_base64_token(token)
                websocket_args["protocols"] = [f"{DEFAULT_SUBPROTOCOL_PREFIX}{encoded_token}"]

        return WebSocket(**websocket_args)


class callback:  # noqa: N801
    """A decorator of `Dash callback functions <https://dash.plotly.com/basic-callbacks>`_ that replaces the
    `Dash callback decorator <https://dash.plotly.com/reference#dash.callback>`_.

    This decorator ensures that:
    - project can be injected into a callback argument.

    - Open Telemetry trace spans are generated for callback executions;

    - The start and end of callback executions are logged ensuring that the module name,
      callback name, trace id and span id are visible in the log; and

    - The DashClient class is initialized also in the new process that is spawn when a
      callback is run in the background.

    This class expects the ``dash_extensions.enrich`` package to be installed.

    The parameters of this decorator are identical to the
    `Dash callback decorator <https://dash.plotly.com/reference#dash.callback>`_.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._args = args
        self._kwargs = kwargs

    def __call__(self, function: Callable[..., Any]) -> Callable[..., Any]:
        # soft dependency on Dash, will simply fail if dash_extensions is not installed
        from dash_extensions.enrich import callback as dash_callback  # type: ignore

        def _get_project_parameter_index(function: Callable[..., Any]) -> int:
            # (in the following call, eval_str=True is needed to get the actual type hints
            # instead of string annotations in case of 'from __future__ import annotations')
            parameters = inspect.signature(function, eval_str=True).parameters
            for i, parameter in enumerate(parameters.values()):
                try:
                    if parameter.annotation and issubclass(parameter.annotation, Solution):
                        return i
                except TypeError:
                    pass
            return -1

        @wraps(function)
        def function_with_logging(*args: Any, **kwargs: Any):
            name = f"{function.__name__} in {function.__module__}"
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span(f"callback {name}"):  # type: ignore
                logger.info(f"started callback {name}")
                if self._kwargs.get("background", False):
                    logger.info(f"callback {name} will run in the background")

                project_param_index = _get_project_parameter_index(function)
                if project_param_index >= 0:
                    solution_module = importlib.import_module(os.environ[GLOW_SOLUTION_DEFINITION])
                    solution_type = find_solution(solution_module)
                    api_url = os.environ[GLOW_API_URL].rstrip("/")
                    external_api_url = os.environ[GLOW_EXTERNAL_API_URL].rstrip("/")
                    access_token = None
                    scheme, token = get_authorization_scheme_param(
                        DashClient._auth_header_from_ctx(),  # pyright: ignore[reportPrivateUsage]
                    )
                    if scheme.lower() == "bearer":
                        logger.debug("Bearer token injected into the client for authorization.")
                        access_token = token

                    with Client(
                        solution_type=solution_type,
                        url=api_url,
                        external_url=external_api_url,
                        access_token=access_token,
                    ) as client:
                        pathname = args[project_param_index]
                        project_name = DashClient._get_project_name_from_pathname(  # pyright: ignore[reportPrivateUsage]
                            pathname,
                        )
                        modified_args = list(args)
                        modified_args[project_param_index] = client.get_project(project_name)
                        result = function(*modified_args, **kwargs)
                        logger.info(f"completed callback {name}")
                        return result

                result = function(*args, **kwargs)
                logger.info(f"completed callback {name}")
                return result

        output = dash_callback(*self._args, **self._kwargs)(function_with_logging)  # type: ignore
        return output
