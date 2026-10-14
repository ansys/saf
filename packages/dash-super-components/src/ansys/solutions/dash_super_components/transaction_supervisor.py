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


"""Provides a Dash component for tracking the status of SAF transaction method."""

from datetime import datetime, timedelta
import time
from typing import Any
import uuid

try:
    # dash >=3.2.0
    from dash import NoUpdate
except ImportError:
    # dash >=2.18.2, <3.2.0
    from dash._callback import NoUpdate  # pyright: ignore[reportPrivateImportUsage]

try:
    # dash-extensions < 2.0.5
    from dash_extensions.enrich import _Wildcard  # pyright: ignore[reportAttributeAccessIssue]
except ImportError:
    # dash-extensions >= 2.0.5
    from dash_extensions.enrich import (
        Wildcard as _Wildcard,  # pyright: ignore[reportAttributeAccessIssue]
    )
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import (
    MATCH,
    Input,
    Output,
    State,
    callback,
    dcc,
    html,
    no_update,
)
import dash_mantine_components as dmc

from ansys.solutions.dash_super_components.utils._common_colors import _CommonColors as CommonColors
from ansys.solutions.dash_super_components.utils.aio_ids import AIOIds
from ansys.solutions.dash_super_components.utils.api_requests import GlowAPIRequest
from ansys.solutions.dash_super_components.utils.status_badge_properties import (
    TRANSACTION_STATUS_BADGE_PROPERTIES,
)
from ansys.solutions.dash_super_components.utils.svg_icons import (
    IconNames,
    create_icon_span,
)


class TransactionSupervisor(html.Div):
    """
    A Dash component for monitoring the status of a SAF GLOW transaction method.

    TransactionSupervisor is based on the Dash All-in-One (AIO) component pattern. It polls
    the GLOW API to track method status in real time and displays elapsed time, started time,
    and a color-coded status badge.

    .. warning::

        This component requires a SAF-based solution with access to the GLOW API. It must
        be instantiated inside a callback (not directly in the layout) because it needs the
        project URL from ``DashClient``.

    To activate monitoring from a callback use::

        TransactionSupervisor.ids.activate_monitoring(aio_id)  # Store; set "data" to True

    Parameters
    ----------
    url : str
        The URL of the GLOW API server.
    step_name : str
        The name of the GLOW step (StepModel) that contains the method.
    method_name : str
        The name of the GLOW transaction method whose status is being monitored.
    title : str, optional
        Title displayed in the monitoring card.
    show : bool, optional
        Whether to show the monitoring card. Default is ``True``.
    aio_id : str, optional
        Unique identifier for this component instance. A UUID is generated when
        not provided.
    width : str or int, optional
        Width of the monitoring card. Default is ``400``.
    font_size : str, optional
        Font size of the text in the card. Default is ``'14px'``.
    title_font_size : str, optional
        Font size of the title in the card. Default is ``'16px'``.
    orientation : str, optional
        Layout orientation of the card (``'horizontal'`` or ``'vertical'``).
        Default is ``'horizontal'``.
    """

    class TransactionSupervisorIds(AIOIds):
        """Provides IDs for the subcomponents of :class:`TransactionSupervisor`."""

        @classmethod
        def _method_info(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the method info store.

            The method info store holds the URL, step name and method name for the monitored
            transaction method. It is held in "memory" storage and gets immediately updated on
            project or transaction method change (when the component is recreated with new props).

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the method info store subcomponent.
            """
            return cls.make_id_dict("transaction-supervisor", "method-info", aio_id)

        @classmethod
        def _method_info_persist(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the method info persist store.

            The method info persist store holds the URL, step name and method name for the monitored
            transaction method. It is held in "session" storage and keeps its value across page
            reloads. It allows to determine if the project or transaction method has changed and
            handle the monitoring activation accordingly in the callbacks. When a project or
            transaction method change is detected, this store gets updated with the new method info.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the method info persist store subcomponent.
            """
            return cls.make_id_dict("transaction-supervisor", "method-info-persist", aio_id)

        @classmethod
        def _started_time(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the started time store.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the started time store subcomponent.
            """
            return cls.make_id_dict("transaction-supervisor", "started-time", aio_id)

        @classmethod
        def _stopped_time(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the stopped time store.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the stopped time store subcomponent.
            """
            return cls.make_id_dict("transaction-supervisor", "stopped-time", aio_id)

        @classmethod
        def _elapsed_time_calculable(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the elapsed time calculable store.

            The elapsed time calculable store holds a boolean value indicating whether the stored
            started time can be trusted to calculate elapsed time or not, and whether a status
            change to "completed" or "failed" can be trusted to mark the correct stopped time or
            not. This is needed to not yield incorrect elapsed time values in cases where the
            component is loaded while the transaction method is or has already been running.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the elapsed time calculable store subcomponent.
            """
            return cls.make_id_dict("transaction-supervisor", "elapsed-time-calculable", aio_id)

        @classmethod
        def _method_status(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the method status store.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the method status store subcomponent.
            """
            return cls.make_id_dict("transaction-supervisor", "method-status", aio_id)

        @classmethod
        def _loader(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the loader store.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the loader store subcomponent.
            """
            return cls.make_id_dict("transaction-supervisor", "loader", aio_id)

        @classmethod
        def _interval(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the interval component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the interval subcomponent.
            """
            return cls.make_id_dict("transaction-supervisor", "interval", aio_id)

        @classmethod
        def _container(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the container component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the container subcomponent.
            """
            return cls.make_id_dict("transaction-supervisor", "container", aio_id)

        @classmethod
        def _supervision_active(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the supervision active store.

            This is the internal store to track the activation status of the supervision. It is
            updated when the external trigger for supervision activation is changed or when the
            method status changes.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the supervision active store subcomponent.
            """
            return cls.make_id_dict("transaction-supervisor", "supervision-active", aio_id)

        @classmethod
        def activate_monitoring(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the activate monitoring store.

            This component can be used to externally control the activation of the monitoring.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the activate monitoring store subcomponent.
            """
            return cls.make_id_dict("transaction-supervisor", "activate-monitoring", aio_id)

        @classmethod
        def transaction_status_badge(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the transaction status badge.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the transaction status badge subcomponent.
            """
            return cls.make_id_dict("transaction-supervisor", "transaction-status-badge", aio_id)

        @classmethod
        def started_time_label(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the started time label.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the started time label subcomponent.
            """
            return cls.make_id_dict("transaction-supervisor", "started-time-label", aio_id)

        @classmethod
        def elapsed_time_label(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the elapsed time label.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the elapsed time label subcomponent.
            """
            return cls.make_id_dict("transaction-supervisor", "elapsed-time-label", aio_id)

        @classmethod
        def switch(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the switch component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the switch subcomponent.
            """
            return cls.make_id_dict("transaction-supervisor", "switch", aio_id)

    ids = TransactionSupervisorIds

    def __init__(
        self,
        url: str,
        step_name: str,
        method_name: str,
        title: str = "Transaction Supervisor",
        show: bool = True,
        aio_id: str | None = None,
        width: str | int = 400,
        font_size: str = "14px",
        title_font_size: str = "16px",
        orientation: str = "horizontal",
    ):
        self._url = url
        self._step_name = step_name
        self._method_name = method_name
        self._title = title
        self._show = show
        self._width = width
        self._font_size = font_size
        self._orientation = orientation
        self._title_font_size = title_font_size
        self.aio_id = aio_id if aio_id is not None else str(uuid.uuid4())

        super().__init__(
            [
                html.Div(
                    [
                        dcc.Store(
                            id=self.ids._method_info(self.aio_id),
                            storage_type="memory",  # updates on project change
                            data={
                                "url": url,
                                "step_name": self._step_name,
                                "method_name": self._method_name,
                            },
                        ),
                        dcc.Store(
                            id=self.ids._method_info_persist(self.aio_id),
                            storage_type="session",  # persists across page reloads
                        ),
                        dcc.Store(
                            id=self.ids._started_time(self.aio_id),
                            storage_type="session",  # persists across page reloads
                        ),
                        dcc.Store(
                            id=self.ids._stopped_time(self.aio_id),
                            storage_type="session",  # persists across page reloads
                        ),
                        dcc.Store(
                            id=self.ids._elapsed_time_calculable(self.aio_id),
                            storage_type="memory",
                        ),
                        dcc.Store(
                            id=self.ids._method_status(self.aio_id),
                            storage_type="memory",
                        ),
                        dcc.Store(
                            id=self.ids._supervision_active(self.aio_id),
                            storage_type="memory",
                        ),
                        dcc.Store(
                            id=self.ids.activate_monitoring(self.aio_id),
                            storage_type="memory",
                        ),
                        dcc.Interval(
                            id=self.ids._interval(self.aio_id),
                            interval=1000,
                            n_intervals=0,
                            disabled=True,
                        ),
                        dmc.Card(
                            children=[
                                dmc.CardSection(
                                    dmc.Group(
                                        children=[
                                            html.Div(
                                                self._title,
                                                style={
                                                    "display": "inline-block",
                                                    "fontSize": self._title_font_size,
                                                },
                                            ),
                                            dcc.Loading(
                                                id=self.ids._loader(self.aio_id),
                                                display="hide",
                                                color=CommonColors.MANTINE_PRIMARY_COLOR,
                                            ),
                                            dmc.HoverCard(
                                                children=[
                                                    dmc.HoverCardTarget(
                                                        dmc.Switch(
                                                            id=self.ids.switch(
                                                                self.aio_id,
                                                            ),
                                                            checked=self._show,
                                                            offLabel=create_icon_span(
                                                                IconNames.MDI_HIDE,
                                                                size_px=16,
                                                            ),
                                                            onLabel=create_icon_span(
                                                                IconNames.MDI_SHOW,
                                                                size_px=16,
                                                            ),
                                                            size="sm",
                                                        ),
                                                    ),
                                                    dmc.HoverCardDropdown(
                                                        dmc.Text(
                                                            "Show/Hide monitoring panel.",
                                                            size="sm",
                                                            c=CommonColors.MANTINE_TEXT,
                                                        ),
                                                    ),
                                                ],
                                                withArrow=True,
                                                shadow="md",
                                            ),
                                        ],
                                        justify="space-around",
                                    ),
                                    withBorder=True,
                                    inheritPadding=True,
                                    py="xs",
                                ),
                                html.Div(
                                    dmc.Grid(
                                        children=[
                                            dmc.GridCol(
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            "Transaction method status :",
                                                            style={
                                                                "display": "inline-block",
                                                                "fontSize": self._font_size,
                                                                "marginTop": "5px",
                                                            },
                                                        ),
                                                        html.Div(
                                                            dmc.Badge(
                                                                id=self.ids.transaction_status_badge(
                                                                    self.aio_id,
                                                                ),
                                                                style={
                                                                    "fontSize": self._font_size,
                                                                },
                                                            ),
                                                            style={
                                                                "marginLeft": "5px",
                                                                "display": "inline-block",
                                                            },
                                                        ),
                                                    ],
                                                    style={"display": "inline-block"},
                                                ),
                                                span=("content" if self._orientation == "horizontal" else 12),
                                            ),
                                            dmc.GridCol(
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            "Started time :",
                                                            style={
                                                                "display": "inline-block",
                                                                "fontSize": self._font_size,
                                                                "marginTop": "5px",
                                                            },
                                                        ),
                                                        html.Div(
                                                            id=self.ids.started_time_label(
                                                                self.aio_id,
                                                            ),
                                                            style={
                                                                "display": "inline-block",
                                                                "fontSize": self._font_size,
                                                                "marginTop": "5px",
                                                                "marginLeft": "5px",
                                                            },
                                                        ),
                                                    ],
                                                    style={"display": "inline-block"},
                                                ),
                                                span=("content" if self._orientation == "horizontal" else 12),
                                            ),
                                            dmc.GridCol(
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            "Elapsed time :",
                                                            style={
                                                                "display": "inline-block",
                                                                "fontSize": self._font_size,
                                                                "marginTop": "5px",
                                                            },
                                                        ),
                                                        html.Div(
                                                            id=self.ids.elapsed_time_label(
                                                                self.aio_id,
                                                            ),
                                                            style={
                                                                "display": "inline-block",
                                                                "fontSize": self._font_size,
                                                                "marginTop": "5px",
                                                                "marginLeft": "5px",
                                                            },
                                                        ),
                                                    ],
                                                    style={"display": "inline-block"},
                                                ),
                                                span=("content" if self._orientation == "horizontal" else 12),
                                            ),
                                        ],
                                        gutter="xs",
                                    ),
                                    id=self.ids._container(self.aio_id),
                                    style={
                                        "display": "inline-block",
                                    },
                                ),
                            ],
                            withBorder=True,
                            shadow="sm",
                            radius="md",
                            w=self._width,
                        ),
                    ],
                ),
            ],
        )

    @staticmethod
    @callback(
        Output(ids._container(MATCH), "style"),
        Input(ids.switch(MATCH), "checked"),
    )
    def show_supervision_card(
        checked: bool,
    ) -> dict[str, Any]:
        """Hide or show the content of the supervision card."""
        return {"display": "inline-block"} if checked else {"display": "none"}

    @staticmethod
    @callback(
        Output(ids._interval(MATCH), "disabled"),
        Output(ids._loader(MATCH), "display"),
        Input(ids._supervision_active(MATCH), "data"),
        prevent_initial_call=True,
    )
    def start_stop_supervision(
        new_monitoring_active: bool,
    ) -> tuple[bool, str]:
        """Start/stop the monitoring of the transaction method."""
        if new_monitoring_active:
            return False, "show"

        # else: deactivate monitoring
        return True, "hide"

    @staticmethod
    @callback(
        Output(ids.started_time_label(MATCH), "children"),
        Input(ids._started_time(MATCH), "data"),
    )
    def update_started_time_label(
        started_time: float | None,
    ) -> str:
        """Update the started time label."""
        if started_time is None:
            return "n/a"

        return datetime.fromtimestamp(started_time).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    @callback(
        Output(ids.elapsed_time_label(MATCH), "children"),
        Input(ids._interval(MATCH), "n_intervals"),
        Input(ids._stopped_time(MATCH), "data"),
        State(ids._started_time(MATCH), "data"),
        State(ids._elapsed_time_calculable(MATCH), "data"),
        prevent_initial_call=True,
    )
    def update_elapsed_time_label(
        dummy_n_intervals: int,
        stopped_time: float | None,
        started_time: float | None,
        elapsed_time_calculable: bool,
    ) -> str:
        """Update the elapsed time label."""
        if started_time is not None and stopped_time is not None:
            elapsed_seconds = max(0, stopped_time - started_time)
            return str(timedelta(seconds=round(elapsed_seconds)))

        if started_time is not None and elapsed_time_calculable:
            elapsed_seconds = max(0, time.time() - started_time)
            return str(timedelta(seconds=round(elapsed_seconds)))

        return "n/a"

    @staticmethod
    @callback(
        Output(ids.transaction_status_badge(MATCH), "children"),
        Output(ids.transaction_status_badge(MATCH), "color"),
        Input(ids._method_status(MATCH), "data"),
        prevent_initial_call=True,
    )
    def display_method_status_in_badge(
        method_status: str,
    ) -> tuple[str, str]:
        """Display the method status in the badge."""
        color = TRANSACTION_STATUS_BADGE_PROPERTIES[method_status]["color"]
        return (
            method_status,
            color,
        )

    @staticmethod
    @callback(
        Output(ids._supervision_active(MATCH), "data", allow_duplicate=True),
        Output(ids._started_time(MATCH), "data", allow_duplicate=True),
        Output(ids._stopped_time(MATCH), "data", allow_duplicate=True),
        Output(ids._elapsed_time_calculable(MATCH), "data", allow_duplicate=True),
        Input(ids.activate_monitoring(MATCH), "data"),
        State(ids._supervision_active(MATCH), "data"),
        prevent_initial_call=True,
    )
    def activate_monitoring_from_external_trigger(
        activate_monitoring: bool,
        current_monitoring_active: bool,
    ) -> tuple[bool, float, None, bool]:
        """Activate monitoring when external monitoring activation trigger is received."""
        if current_monitoring_active or not activate_monitoring:
            raise PreventUpdate

        new_monitoring_active = True
        started_time = time.time()
        stopped_time = None
        elapsed_time_calculable = True

        return new_monitoring_active, started_time, stopped_time, elapsed_time_calculable

    @staticmethod
    @callback(
        Output(ids._method_status(MATCH), "data"),
        Output(ids._elapsed_time_calculable(MATCH), "data"),
        Input(ids._interval(MATCH), "n_intervals"),
        State(ids._method_info(MATCH), "data"),
        State(ids._method_status(MATCH), "data"),
        State(ids._elapsed_time_calculable(MATCH), "data"),
    )
    def retrieve_method_status_and_update_elapsed_time_calculable(
        dummy_n_intervals: int,
        method_info: dict[str, str],
        current_stored_method_status: str,
        current_stored_elapsed_time_calculable: bool,
    ) -> tuple[str | NoUpdate, bool | NoUpdate]:
        """Retrieve and store the method status and update elapsed time calculable store."""
        glow_api_request = GlowAPIRequest(method_info["url"])
        method_status = glow_api_request.get_transaction_method_status(
            method_info["step_name"],
            method_info["method_name"],
        )

        new_method_status = no_update
        new_elapsed_time_calculable = no_update

        if method_status != current_stored_method_status:
            new_method_status = method_status

        if not current_stored_elapsed_time_calculable and method_status == "running":
            new_elapsed_time_calculable = True

        return new_method_status, new_elapsed_time_calculable

    @staticmethod
    @callback(
        Output(ids._supervision_active(MATCH), "data", allow_duplicate=True),
        Output(ids._started_time(MATCH), "data", allow_duplicate=True),
        Output(ids._stopped_time(MATCH), "data", allow_duplicate=True),
        Output(ids._method_info_persist(MATCH), "data"),
        Input(ids._method_status(MATCH), "data"),
        Input(ids._method_info(MATCH), "data"),
        State(ids._elapsed_time_calculable(MATCH), "data"),
        State(ids._supervision_active(MATCH), "data"),
        State(ids._method_info_persist(MATCH), "data"),
    )
    def control_supervision_based_on_method_status(
        method_status: str,
        method_info: dict[str, str],
        elapsed_time_calculable: bool,
        current_stored_supervision_active: bool,
        method_info_persist: dict[str, Any],
    ) -> tuple[bool, float | None | NoUpdate, float | None | NoUpdate, dict[str, Any] | NoUpdate]:
        """Control supervision based on method status and update stored times and method info."""
        method_info_persist = method_info_persist or {}
        started_time_no_update = no_update
        stopped_time_no_update = no_update
        method_info_persist_no_update = no_update

        if (
            method_info["step_name"] != method_info_persist.get("step_name")
            or method_info["method_name"] != method_info_persist.get("method_name")
            or method_info["url"] != method_info_persist.get("url")
        ):
            # project or transaction has changed - reset supervision and update stored method info
            method_info_persist["step_name"] = method_info["step_name"]
            method_info_persist["method_name"] = method_info["method_name"]
            method_info_persist["url"] = method_info["url"]

            new_supervision_active = method_status == "running"
            started_time_reset = None
            stopped_time_reset = None

            return (
                new_supervision_active,
                started_time_reset,
                stopped_time_reset,
                method_info_persist,
            )

        if not current_stored_supervision_active:
            # page load: activate supervision if method is found running
            if method_status == "running":
                new_supervision_active = True

                return (
                    new_supervision_active,
                    started_time_no_update,
                    stopped_time_no_update,
                    method_info_persist_no_update,
                )

            raise PreventUpdate

        # monitoring is active
        if method_status in ["completed", "failed"]:
            # deactivate supervision if method has finished or failed
            new_supervision_active = False
            stopped_time = time.time()

            return (
                new_supervision_active,
                started_time_no_update,
                stopped_time if elapsed_time_calculable else stopped_time_no_update,
                method_info_persist_no_update,
            )

        raise PreventUpdate
