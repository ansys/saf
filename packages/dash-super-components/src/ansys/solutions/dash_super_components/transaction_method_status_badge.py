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


"""``dmc.Badge`` that displays and updates SAF transaction method status."""

import copy
from typing import Any
import uuid

from ansys.solutions.dash_super_components.utils._common_colors import _CommonColors as CommonColors

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
)
import dash_mantine_components as dmc

from ansys.solutions.dash_super_components.utils.aio_ids import AIOIds
from ansys.solutions.dash_super_components.utils.api_requests import GlowAPIRequest
from ansys.solutions.dash_super_components.utils.status_badge_properties import (
    TRANSACTION_STATUS_BADGE_PROPERTIES,
)
from ansys.solutions.dash_super_components.utils.svg_icons import (
    IconNames,
    create_base64_svg_src,
)


class TransactionMethodStatusBadge(html.Div):
    """
    A Dash component that displays and updates the status of a SAF transaction method.

    TransactionMethodStatusBadge is based on the Dash All-in-One (AIO) component pattern.
    It renders a compact status badge that periodically polls the GLOW API and reflects the
    current status of the specified method with color-coded states.

    .. warning::

        This component requires a SAF-based solution with access to the GLOW API. It must
        be instantiated inside a callback (not directly in the layout) because it needs the
        project URL from ``DashClient``.

    To activate monitoring from a callback use::

        TransactionMethodStatusBadge.ids.activate_monitoring(aio_id)  # Store
        # set "data" to True to activate, False to deactivate

    Parameters
    ----------
    url : str
        The URL of the GLOW API server.
    step_name : str
        The name of the GLOW step (StepModel) that contains the method.
    method_name : str
        The name of the GLOW transaction method to monitor.
    auto_mode : bool, optional
        If ``True``, monitoring stops automatically when the method reaches a terminal
        state (completed, failed) and starts automatically when the method is found running when
        the component is loaded. Default is ``True``.
    badge_props : dict, optional
        Additional properties forwarded to the status badge :class:`dmc.Badge`.
    label_props : dict, optional
        Additional properties forwarded to the label :class:`html.Div` component.
    interval_props : dict, optional
        Additional properties forwarded to the :class:`dcc.Interval` polling component.
    aio_id : str, optional
        Unique identifier for this component instance. A UUID is generated if not provided.
    """

    class TransactionMethodStatusBadgeIds(AIOIds):
        """Provides IDs for the subcomponents of :class:`TransactionMethodStatusBadge`."""

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
            return cls.make_id_dict("transaction-method-status-badge", "method-info", aio_id)

        @classmethod
        def _auto_mode(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the auto mode store.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the auto mode store subcomponent.
            """
            return cls.make_id_dict("transaction-method-status-badge", "auto-mode", aio_id)

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
            return cls.make_id_dict("transaction-method-status-badge", "method-status", aio_id)

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
            return cls.make_id_dict("transaction-method-status-badge", "interval", aio_id)

        @classmethod
        def _monitoring_active(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the monitoring active store.

            This is the internal store to track the activation status of the monitoring. It is
            updated when the external trigger for monitoring activation is changed or when the
            method status changes (in auto-mode).

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the monitoring active store subcomponent.
            """
            return cls.make_id_dict("transaction-method-status-badge", "monitoring-active", aio_id)

        @classmethod
        def activate_monitoring(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the activate monitoring component.

            This component can be used to externally control the activation of the monitoring.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the activate monitoring subcomponent.
            """
            return cls.make_id_dict("transaction-method-status-badge", "activate-monitoring", aio_id)

        @classmethod
        def label(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the label component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the label subcomponent.
            """
            return cls.make_id_dict("transaction-method-status-badge", "label", aio_id)

        @classmethod
        def status_badge(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the status badge component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the status badge subcomponent.
            """
            return cls.make_id_dict("transaction-method-status-badge", "status-badge", aio_id)

    ids = TransactionMethodStatusBadgeIds

    def __init__(
        self,
        url: str,
        step_name: str,
        method_name: str,
        auto_mode: bool = True,
        badge_props: dict[str, Any] | None = None,
        label_props: dict[str, Any] | None = None,
        interval_props: dict[str, Any] | None = None,
        aio_id: str | None = None,
    ):
        badge_properties = {} if badge_props is None else copy.deepcopy(badge_props)
        label_properties = {} if label_props is None else copy.deepcopy(label_props)
        interval_properties = {} if interval_props is None else copy.deepcopy(interval_props)

        if aio_id is None:
            aio_id = str(uuid.uuid4())

        self.aio_id = aio_id

        default_label_properties = {
            "style": {
                "fontSize": "15px",
                "textAlign": "left",
                "display": "block" if label_properties else "none",
            },
        }

        default_badge_properties = {
            "size": "lg",
            "radius": "xl",
            "fullWidth": True,
        }

        default_interval_properties = {
            "interval": 5000,
        }

        # Merge label properties, handling the style dict specially
        for key, value in default_label_properties.items():
            if key not in label_properties:
                label_properties[key] = value
            elif key == "style" and isinstance(label_properties[key], dict):
                # Merge style dicts: defaults first, then user overrides
                merged_style = copy.deepcopy(value)
                merged_style.update(label_properties[key])
                label_properties[key] = merged_style

        # properties in default_badge_properties can be overwritten:
        for key, value in default_badge_properties.items():
            if key not in badge_properties:
                badge_properties[key] = value

        # badge properties "children", "color", "variant" and "leftSection" are fully controlled by
        # the component - will be overwritten by correct values in the callbacks:
        badge_properties["children"] = ""
        badge_properties["color"] = CommonColors.MANTINE_BODY
        badge_properties["variant"] = "filled"
        badge_properties["leftSection"] = None

        # properties in default_interval_properties can be overwritten:
        for key, value in default_interval_properties.items():
            if key not in interval_properties:
                interval_properties[key] = value

        # interval property "disabled" is fully controlled by the component:
        interval_properties["disabled"] = True

        super().__init__(
            [
                html.Div(
                    [
                        html.Div(id=self.ids.label(aio_id), **label_properties),
                        dmc.Badge(id=self.ids.status_badge(aio_id), **badge_properties),
                    ],
                    style={
                        "display": "flex",
                        "flexDirection": "column",
                        "alignItems": "left",
                    },
                ),
                dcc.Interval(id=self.ids._interval(aio_id), **interval_properties),
                dcc.Store(
                    id=self.ids._method_info(self.aio_id),
                    storage_type="memory",  # updates on project change
                    data={
                        "url": url,
                        "step_name": step_name,
                        "method_name": method_name,
                    },
                ),
                dcc.Store(
                    id=self.ids._method_status(self.aio_id),
                    storage_type="memory",
                ),
                dcc.Store(
                    id=self.ids._monitoring_active(self.aio_id),  # internal status
                    storage_type="memory",
                ),
                dcc.Store(
                    id=self.ids.activate_monitoring(self.aio_id),  # external control
                    storage_type="memory",
                ),
                dcc.Store(
                    id=self.ids._auto_mode(self.aio_id),
                    storage_type="memory",
                    data=auto_mode,
                ),
            ],
        )

    @staticmethod
    @callback(
        Output(ids._interval(MATCH), "disabled"),
        Input(ids._monitoring_active(MATCH), "data"),
        prevent_initial_call=True,
    )
    def start_stop_monitoring(
        monitoring_active: bool,
    ) -> bool:
        """Start/stop the monitoring of the transaction method."""
        return not monitoring_active

    @staticmethod
    @callback(
        Output(ids._monitoring_active(MATCH), "data", allow_duplicate=True),
        Input(ids.activate_monitoring(MATCH), "data"),
    )
    def activate_deactivate_monitoring_from_external_trigger(activate: bool) -> bool:
        """Activate/deactivate monitoring when external monitoring activation is changed."""
        return activate

    @staticmethod
    @callback(
        Output(ids._method_status(MATCH), "data"),
        Input(ids._interval(MATCH), "n_intervals"),
        State(ids._method_info(MATCH), "data"),
        State(ids._method_status(MATCH), "data"),
    )
    def retrieve_method_status(
        dummy_n_intervals: int,
        method_info: dict[str, str],
        current_method_status: str,
    ) -> str | NoUpdate:
        """Retrieve and store the method status."""
        glow_api_request = GlowAPIRequest(method_info["url"])
        new_method_status = glow_api_request.get_transaction_method_status(
            method_info["step_name"],
            method_info["method_name"],
        )

        if new_method_status != current_method_status:
            return new_method_status

        raise PreventUpdate

    @staticmethod
    @callback(
        Output(ids.status_badge(MATCH), "children"),
        Output(ids.status_badge(MATCH), "color"),
        Output(ids.status_badge(MATCH), "variant"),
        Output(ids.status_badge(MATCH), "leftSection"),
        Input(ids._method_status(MATCH), "data"),
        Input(ids._monitoring_active(MATCH), "data"),
        prevent_initial_call=True,
    )
    def update_badge(
        method_status: str,
        monitoring_active: bool,
    ) -> tuple[str, str, str, Any]:
        """Update badge properties upon method status or monitoring active change."""
        if not method_status:
            raise PreventUpdate

        badge_children = method_status.upper()
        color = TRANSACTION_STATUS_BADGE_PROPERTIES[method_status.lower()]["color"]

        if not monitoring_active:
            variant = "outline"
            left_section = None
        else:
            variant = "filled"
            left_section = html.Img(
                src=create_base64_svg_src(IconNames.EOS_LOADING),
                style={"height": "2em", "width": "auto"},
            )

        return (
            badge_children,
            color,
            variant,
            left_section,
        )

    @staticmethod
    @callback(
        Output(ids._monitoring_active(MATCH), "data", allow_duplicate=True),
        Input(ids._method_status(MATCH), "data"),
        State(ids._monitoring_active(MATCH), "data"),
        State(ids._auto_mode(MATCH), "data"),
    )
    def control_monitoring_based_on_method_status(
        method_status: str,
        current_monitoring_active: bool,
        auto_mode: bool,
    ) -> bool:
        """Control monitoring based on method status and update method info."""
        if not auto_mode:
            raise PreventUpdate

        if not current_monitoring_active:
            # page load: activate monitoring if method is found running
            if method_status == "running":
                new_monitoring_active = True

                return new_monitoring_active

            raise PreventUpdate

        # monitoring is active
        if method_status in ["completed", "failed"]:
            # deactivate monitoring if method has finished or failed
            new_monitoring_active = False

            return new_monitoring_active

        raise PreventUpdate
