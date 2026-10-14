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


"""Provides a Dash component for displaying and filtering process logs."""

from collections.abc import Hashable
import copy
from hashlib import sha1
from pathlib import Path
import re
from typing import Any, Literal, TypedDict
import uuid

from ansys.solutions.dash_super_components.utils._common_colors import _CommonColors as CommonColors

try:
    # dash >=3.2.0
    from dash import NoUpdate
except ImportError:
    # dash >=2.18.2, <3.2.0
    from dash._callback import NoUpdate  # pyright: ignore[reportPrivateImportUsage]
from dash.exceptions import PreventUpdate

try:
    # dash-extensions < 2.0.5
    from dash_extensions.enrich import _Wildcard  # pyright: ignore[reportAttributeAccessIssue]
except ImportError:
    # dash-extensions >= 2.0.5
    from dash_extensions.enrich import (
        Wildcard as _Wildcard,  # pyright: ignore[reportAttributeAccessIssue]
    )
try:
    from dash_extensions.enrich import set_props
except ImportError:
    from dash import set_props
import dash_ag_grid as dag
from dash_extensions.enrich import (
    MATCH,
    Input,
    Output,
    State,
    callback,
    ctx,
    dcc,
    html,
    no_update,
)
import dash_mantine_components as dmc

from ansys.solutions.dash_super_components.utils import config
from ansys.solutions.dash_super_components.utils.aio_ids import AIOIds
from ansys.solutions.dash_super_components.utils.logs_parser import (
    LogsParser,
    LogsParseResult,
    ParseStatus,
)
from ansys.solutions.dash_super_components.utils.svg_icons import (
    IconNames,
    create_icon_span,
)

SUPPORTED_LOGGING_FORMATTER_OPTIONS_AND_HEADERS = {
    "asctime": "Time",
    "levelname": "Level Name",
    "name": "Logger Name",
    "message": "Message",
    "module": "Module",
    "filename": "Filename",
    "funcName": "Function Name",
    "pathname": "Path Name",
    "processName": "Process Name",
    "threadName": "Thread Name",
    "taskName": "Task Name",
    "created": "Created",
    "levelno": "Level Number",
    "lineno": "Line Number",
    "msecs": "Milliseconds",
    "process": "Process ID",
    "relativeCreated": "Relative Created",
    "thread": "Thread ID",
}


DEFAULT_LOGGING_FORMATTER_REPRESENTATION = {
    "cellStyle": {"textAlign": "left"},
    "flex": 3,
    "minWidth": 120,
}


PARSING_FAILED_NO_ROWS_MESSAGE = "Could not process log. Please check the log file path and format."
SOURCE_MISSING_NO_ROWS_MESSAGE = "Log source is not available."
PLAIN_NO_ROWS_MESSAGE = "No logs to display."


LOGGING_FORMATTER_REPRESENTATION = {
    "levelname": {
        "cellRenderer": "DMC_Badge_Level_Name",
        "filter": "agTextColumnFilter",
        "suppressHeaderMenuButton": True,  # Hide filter menu; use buttons instead
        "filterParams": {
            "maxNumConditions": 5,
            "filterOptions": ["contains", "startsWith", "endsWith"],
            "defaultOption": "contains",
        },
        "cellRendererParams": {
            "variant": "filled",
            "radius": "xl",
            "size": "xs",
            "style": {"width": "60%"},
        },
        "flex": 2,
        "cellStyle": {"textAlign": "center"},
    },
    "message": {
        "flex": 5,
        "minWidth": 200,
    },
    "levelno": {
        "flex": 2,
        "minWidth": 100,
    },
    "lineno": {
        "flex": 2,
        "minWidth": 100,
    },
    "msecs": {
        "flex": 2,
        "minWidth": 100,
    },
    "process": {
        "flex": 2,
        "minWidth": 100,
    },
    "relativeCreated": {
        "flex": 2,
        "minWidth": 100,
    },
    "thread": {
        "flex": 2,
        "minWidth": 100,
    },
    "pathname": {
        "flex": 4,
        "minWidth": 150,
    },
}


ColorLiteral = Literal[
    CommonColors.MANTINE_RED,
    CommonColors.MANTINE_PINK,
    CommonColors.MANTINE_GRAPE,
    CommonColors.MANTINE_BLUE,
    CommonColors.MANTINE_ORANGE,
]


class FilterButtonProps(TypedDict):
    """TypedDict representing properties for a filter button, including color and icon."""

    color: ColorLiteral
    icon: html.Span
    icon_disabled: html.Span


FILTER_BUTTONS_PROPERTIES: dict[str, FilterButtonProps] = {
    "info": {
        "color": CommonColors.MANTINE_BLUE,
        "icon": create_icon_span(IconNames.MATERIAL_INFO, size_px=14),
        "icon_disabled": create_icon_span(IconNames.MATERIAL_INFO, size_px=14, color=CommonColors.MANTINE_BLUE),
    },
    "warning": {
        "color": CommonColors.MANTINE_ORANGE,
        "icon": create_icon_span(IconNames.MATERIAL_WARNING, size_px=14),
        "icon_disabled": create_icon_span(IconNames.MATERIAL_WARNING, size_px=14, color=CommonColors.MANTINE_ORANGE),
    },
    "error": {
        "color": CommonColors.MANTINE_RED,
        "icon": create_icon_span(IconNames.ICON_PARK_ERROR, size_px=14),
        "icon_disabled": create_icon_span(IconNames.ICON_PARK_ERROR, size_px=14, color=CommonColors.MANTINE_RED),
    },
    "critical": {
        "color": CommonColors.MANTINE_PINK,
        "icon": create_icon_span(IconNames.EOS_CRITICAL_BUG, size_px=14),
        "icon_disabled": create_icon_span(IconNames.EOS_CRITICAL_BUG, size_px=14, color=CommonColors.MANTINE_PINK),
    },
    "debug": {
        "color": CommonColors.MANTINE_GRAPE,
        "icon": create_icon_span(IconNames.EOS_CRITICAL_BUG, size_px=14),
        "icon_disabled": create_icon_span(IconNames.EOS_CRITICAL_BUG, size_px=14, color=CommonColors.MANTINE_GRAPE),
    },
}


class LogsSupervisor(html.Div):
    """
    A Dash component for parsing and displaying log files in an interactive AG Grid table.

    LogsSupervisor is based on the Dash All-in-One (AIO) component pattern. It parses log
    files generated with Python's ``logging`` module and renders them in a sortable,
    filterable AG Grid table with per-level filter buttons and an optional real-time
    monitoring toggle.

    The grid shows contextual no-rows messages depending on parsing outcome:

    - missing source (for example, file not found or URL 404),
    - parse failure or no rows matching the provided format,
    - successful parse with no rows to display.

    Optional ``dmc`` notifications can be emitted for parse failures.

    The ``log_format`` must exactly match the formatter used in the logger, for example::

        "%(asctime)s - %(levelname)s - %(module)s - %(message)s"

    To activate real-time monitoring from a callback use::

        LogsSupervisor.ids.activate_monitoring(aio_id)  # Store; set "data" to True

    .. note::

        Custom JavaScript assets must be registered for the log level badges and contextual no-rows
        messages to render correctly. See the Getting Started page for instructions on registering
        component assets (``add_super_components_assets()`` and ``external_scripts``).

        Furthermore, for error notifications to work correctly, a ``dmc.NotificationContainer``
        must be present in the application layout.  By default the container ID is
        ``"notification-container"``; use
        :func:`~ansys.solutions.dash_super_components.configure` to change it.

    Parameters
    ----------
    log_file : str or Path
        Path or URL to the log file. Accepts local file paths and HTTP/HTTPS URLs.
    log_format : str
        Format string matching the logger's formatter. Determines which columns are
        displayed. See `Python logging attributes
        <https://docs.python.org/3/library/logging.html#logrecord-attributes>`_.
    aio_id : str, optional
        Unique identifier for this component instance. A UUID is generated when not
        provided.
    interval : int, optional
        Polling interval in milliseconds when monitoring is active. Default is ``3000``.
    width : str or int, optional
        Width of the component container. CSS string (``"70%"``, ``"800px"``) or integer
        (pixels). Default is ``"100%"``.
    grid_props : dict, optional
        Additional properties forwarded to the AG Grid component.
    show_error_notifications : bool, optional
        Whether to emit ``dmc`` error notifications when parsing fails.
        Default is ``True``.
    """

    class LogsSupervisorIds(AIOIds):
        """Provides IDs for the subcomponents of :class:`LogsSupervisor`."""

        @classmethod
        def _log_file_and_format(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the log file and format component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the log file and format subcomponent.
            """
            return cls.make_id_dict("logs-supervisor", "log-file-and-format", aio_id)

        @classmethod
        def _log_file_and_format_persist(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the log file and format persist component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the log file and format persist subcomponent.
            """
            return cls.make_id_dict("logs-supervisor", "log-file-and-format-persist", aio_id)

        @classmethod
        def _show_error_notifications(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the show error notifications store.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the show error notifications store.
            """
            return cls.make_id_dict("logs-supervisor", "show-error-notifications", aio_id)

        @classmethod
        def _show_levels(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the show levels component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the show levels subcomponent.
            """
            return cls.make_id_dict("logs-supervisor", "show-levels", aio_id)

        @classmethod
        def _filter_model_store(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the filter model store component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the filter model store subcomponent.
            """
            return cls.make_id_dict("logs-supervisor", "filter-model-store", aio_id)

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
            return cls.make_id_dict("logs-supervisor", "interval", aio_id)

        @classmethod
        def _grid(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the grid component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the grid subcomponent.
            """
            return cls.make_id_dict("logs-supervisor", "grid", aio_id)

        @classmethod
        def _supervision_active(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the supervision active store.

            This is the internal store to track the activation status of the supervision. It is
            updated from the external ``activate_monitoring`` store, from the UI switch, or when
            the component is recreated with a different log file.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the supervision active store subcomponent.
            """
            return cls.make_id_dict("logs-supervisor", "supervision-active", aio_id)

        @classmethod
        def info_button(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the info button component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the info button subcomponent.
            """
            return cls.make_id_dict("logs-supervisor", "info-button", aio_id)

        @classmethod
        def warning_button(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the warning button component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the warning button subcomponent.
            """
            return cls.make_id_dict("logs-supervisor", "warning-button", aio_id)

        @classmethod
        def error_button(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the error button component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the error button subcomponent.
            """
            return cls.make_id_dict("logs-supervisor", "error-button", aio_id)

        @classmethod
        def critical_button(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the critical button component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the critical button subcomponent.
            """
            return cls.make_id_dict("logs-supervisor", "critical-button", aio_id)

        @classmethod
        def debug_button(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the debug button component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the debug button subcomponent.
            """
            return cls.make_id_dict("logs-supervisor", "debug-button", aio_id)

        @classmethod
        def _activate_monitoring_switch(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the internal activate monitoring switch component.

            This private ID is used by the UI switch shown in the component header.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the internal activate monitoring switch subcomponent.
            """
            return cls.make_id_dict("logs-supervisor", "activate-monitoring-switch", aio_id)

        @classmethod
        def activate_monitoring(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the activate monitoring store component.

            This component can be used to externally control the activation of the monitoring by
            setting its ``data`` property to ``True`` or ``False``.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the activate monitoring subcomponent.
            """
            return cls.make_id_dict("logs-supervisor", "activate-monitoring", aio_id)

    ids = LogsSupervisorIds

    def __init__(
        self,
        log_file: Path | str,
        log_format: str,
        aio_id: str | None = None,
        interval: int = 3000,
        width: str | int = "100%",
        grid_props: dict[str, Any] | None = None,
        show_error_notifications: bool = True,
    ):
        if aio_id is None:
            aio_id = str(uuid.uuid4())

        grid_props = copy.deepcopy(grid_props) if grid_props is not None else {}

        self._log_file = log_file
        self._log_format = log_format
        self.aio_id = aio_id

        if not log_file:
            raise ValueError("log_file must be provided.")
        if not isinstance(log_file, str | Path):  # type: ignore - check that user input matches expected types
            raise TypeError("log_file must be a string or a Path object.")
        if not log_format:
            raise ValueError("log_format must be provided.")

        log_file_path = str(log_file) if isinstance(log_file, Path) else log_file

        filter_buttons = self._create_filter_buttons()

        column_defs: list[dict[str, dict[str, Any]]] = []
        for attribute in re.findall(r"%\(([^)]+)\)[sfd]", log_format):
            column_def = self.get_logging_formatter_representation(attribute)
            column_defs.append(column_def)

        default_grid_props: dict[str, Any] = {
            "defaultColDef": {
                "resizable": True,
                "sortable": True,
                "editable": False,
            },
            "dashGridOptions": {
                # Prevent column reordering as it looks odd when reloading the page
                "suppressMovableColumns": True,
                "tooltipShowDelay": 500,  # Show tooltip after 500ms hover
                "suppressScrollOnNewData": True,  # Don't scroll to top when new data is loaded
            },
            "className": "ag-theme-balham-dark",
            "persistence": True,
            "persistence_type": "session",
            "persisted_props": ["columnState"],
            "style": {"height": "200px"},
        }

        controlled_grid_props = {
            "columnDefs": column_defs,
            "defaultColDef": {
                "filter": True,
            },
            "filterModel": {},
            "dashGridOptions": {
                "noRowsOverlayComponent": "DMC_NoRows_Overlay",
                "noRowsOverlayComponentParams": {"message": PLAIN_NO_ROWS_MESSAGE},
            },
        }

        self._populate_with_defaults(grid_props, default_grid_props, controlled_grid_props)

        super().__init__(
            [
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(
                                    [
                                        dmc.Text(
                                            "Log Level",
                                            style={"fontSize": "18px"},
                                        ),
                                        dmc.Group(
                                            filter_buttons,
                                            gap="xs",
                                            justify="left",
                                            style={"marginLeft": "10px"},
                                        ),
                                    ],
                                    style={
                                        "display": "flex",
                                        "flexDirection": "row",
                                        "alignItems": "center",
                                    },
                                ),
                                html.Div(
                                    dmc.HoverCard(
                                        children=[
                                            dmc.HoverCardTarget(
                                                dmc.Switch(
                                                    id=self.ids._activate_monitoring_switch(self.aio_id),
                                                    checked=False,
                                                    offLabel=create_icon_span(IconNames.HEALTH_NO, size_px=15),
                                                    onLabel=create_icon_span(IconNames.HEALTH_YES, size_px=15),
                                                    size="sm",
                                                ),
                                            ),
                                            dmc.HoverCardDropdown(
                                                dmc.Text(
                                                    "Enable/Disable logs monitoring.",
                                                    size="sm",
                                                ),
                                            ),
                                        ],
                                        withArrow=True,
                                        shadow="md",
                                    ),
                                    style={
                                        "display": "flex",
                                        "flexDirection": "row",
                                        "alignItems": "center",
                                    },
                                ),
                            ],
                            style={
                                "display": "flex",
                                "flexDirection": "row",
                                "alignItems": "center",
                                "justifyContent": "space-between",
                            },
                        ),
                        dmc.Space(h=5),
                        html.Div(
                            dag.AgGrid(id=self.ids._grid(self.aio_id), **grid_props),
                        ),
                        dcc.Store(
                            id=self.ids._log_file_and_format(self.aio_id),
                            data={
                                "log_file_path": log_file_path,
                                "log_format": self._log_format,
                            },
                            storage_type="memory",
                        ),
                        dcc.Store(
                            id=self.ids._log_file_and_format_persist(self.aio_id),
                            storage_type="session",  # initialized in callback on page load
                        ),
                        dcc.Store(
                            id=self.ids._show_levels(self.aio_id),
                            storage_type="session",  # initialized in callback on page load
                        ),
                        dcc.Store(
                            id=self.ids._filter_model_store(self.aio_id),
                            storage_type="session",  # initialized in callback on page load
                        ),
                        dcc.Store(
                            id=self.ids._supervision_active(self.aio_id),
                            storage_type="session",  # initialized in callback on page load
                        ),
                        dcc.Store(
                            id=self.ids.activate_monitoring(self.aio_id),
                            storage_type="memory",
                        ),
                        dcc.Store(
                            id=self.ids._show_error_notifications(self.aio_id),
                            data=show_error_notifications,
                            storage_type="memory",
                        ),
                        dcc.Interval(
                            id=self.ids._interval(self.aio_id),
                            interval=interval,
                            disabled=True,
                        ),
                    ],
                    style={
                        "width": width,
                        "display": "flex",
                        "margin": "auto",
                        "flexDirection": "column",
                    },
                ),
            ],
        )

    def _create_filter_buttons(self) -> list[dmc.Button]:
        filter_buttons: list[dmc.Button] = []
        for level in list(FILTER_BUTTONS_PROPERTIES.keys()):
            if level == "info":
                component_id = self.ids.info_button(self.aio_id)
            elif level == "warning":
                component_id = self.ids.warning_button(self.aio_id)
            elif level == "error":
                component_id = self.ids.error_button(self.aio_id)
            elif level == "critical":
                component_id = self.ids.critical_button(self.aio_id)
            elif level == "debug":
                component_id = self.ids.debug_button(self.aio_id)
            else:
                continue  # Should not happen
            filter_buttons.append(
                dmc.Button(
                    level.upper(),
                    id=component_id,
                    color=FILTER_BUTTONS_PROPERTIES[level]["color"],
                    leftSection=FILTER_BUTTONS_PROPERTIES[level]["icon"],
                    size="compact-xs",
                    radius="xl",
                    variant="filled",
                    styles={
                        "label": {"fontSize": "12px"},
                        "icon": {"width": "12px", "height": "12px"},
                    },
                ),
            )

        return filter_buttons

    def _populate_with_defaults(
        self,
        grid_props: dict[str, Any],
        default_grid_props: dict[str, Any],
        controlled_grid_props: dict[str, Any],
    ) -> None:
        # First pass: merge defaults into grid_props (grid_props takes precedence over defaults)
        for key, default_val in default_grid_props.items():
            if key not in grid_props:
                grid_props[key] = copy.deepcopy(default_val)
            elif isinstance(default_val, dict) and isinstance(grid_props[key], dict):
                # Merge dicts: defaults first, then user overrides
                merged = copy.deepcopy(default_val)
                merged.update(grid_props[key])
                grid_props[key] = merged

        # Second pass: merge controlled props into grid_props (controlled takes precedence over all)
        for key, controlled_val in controlled_grid_props.items():
            if key not in grid_props or not isinstance(controlled_val, dict) or not isinstance(grid_props[key], dict):
                grid_props[key] = copy.deepcopy(controlled_val)
            else:
                # Merge dicts: existing (default+user merged) first, then controlled overrides
                merged = copy.deepcopy(grid_props[key])
                merged.update(controlled_val)
                grid_props[key] = merged

    @staticmethod
    def _parse_logs_with_status(log_file_path: str, log_format: str) -> LogsParseResult:
        """Parse logs and always return a status object."""
        parser = LogsParser(log_file_path, log_format)
        result = parser.parse_with_status()
        return result

    @staticmethod
    def _error_notification_id(log_file_path: str, log_format: str, parse_result: LogsParseResult) -> str:
        """Build deterministic notification id for an error signature."""
        error_details = str(parse_result.error) if parse_result.error is not None else ""
        error_signature = f"{parse_result.status}|{log_file_path}|{log_format}|{error_details}"
        signature_hash = sha1(error_signature.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]

        return f"logs-supervisor-notify-failure-{signature_hash}"

    @staticmethod
    @callback(
        Output(ids._show_levels(MATCH), "data", allow_duplicate=True),
        Input(ids._grid(MATCH), "id"),  # Dummy input to trigger on page load
        State(ids._show_levels(MATCH), "data"),
    )
    def initialize_show_levels_on_component_initialization(
        dummy_grid_id: str,
        show_levels: dict[str, Any] | None,
    ) -> dict[str, Any] | NoUpdate:
        """Initialize show_levels session store on initial component creation."""
        if show_levels is not None:
            raise PreventUpdate

        # Initialize with all levels shown if not already set
        return {
            "info": True,
            "warning": True,
            "error": True,
            "critical": True,
            "debug": True,
        }

    @staticmethod
    @callback(
        Output(ids._grid(MATCH), "filterModel", allow_duplicate=True),
        Output(ids._log_file_and_format_persist(MATCH), "data"),
        Output(ids._supervision_active(MATCH), "data", allow_duplicate=True),
        Input(ids._grid(MATCH), "id"),  # Dummy input to trigger on page load
        State(ids._filter_model_store(MATCH), "data"),
        State(ids._grid(MATCH), "filterModel"),
        State(ids._log_file_and_format(MATCH), "data"),
        State(ids._log_file_and_format_persist(MATCH), "data"),
    )
    def initialize_grid_filter_model_from_store_and_reset_supervision_active_on_file_change(
        dummy_grid_id: str,
        filter_model_store: dict[str, Any] | None,
        filter_model: dict[str, Any],
        log_file_and_format: dict[str, Any],
        log_file_and_format_persist: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], dict[str, Any] | NoUpdate, bool | NoUpdate]:
        """Initialize grid filter model from store on page load/navigation.

        If the log file or format is unchanged since the last load, initialize the grid filter model
        from the store to restore the previous state.

        If the log file or format has changed since the last load or on initial load of the
        component, reset the filter model, turn off supervision active, and update the persisted log
        file and format.
        """
        if log_file_and_format != log_file_and_format_persist:
            # Log file or format has changed since last load, reset filter model
            # This also handles the initial load case where log_file_and_format_persist is None,
            # since log_file_and_format always has the current log file and format
            filter_model = {}
            if filter_model_store and filter_model_store.get("levelname"):
                filter_model["levelname"] = filter_model_store["levelname"]
            log_file_and_format_persist = log_file_and_format
            supervision_active = False

            return filter_model, log_file_and_format_persist, supervision_active

        # Prevent unnecessary and circular updates:
        if filter_model_store == filter_model:
            raise PreventUpdate

        filter_model = filter_model_store or {}
        return filter_model, no_update, no_update

    @staticmethod
    @callback(
        Output(ids._filter_model_store(MATCH), "data"),
        Input(ids._grid(MATCH), "filterModel"),
        State(ids._filter_model_store(MATCH), "data"),
        prevent_initial_call=True,
    )
    def store_grid_filter_model(
        filter_model: dict[str, Any],
        filter_model_store: dict[str, Any],
    ) -> dict[str, Any] | NoUpdate:
        """Update filter model store when the grid filter model changes."""
        # Prevent unnecessary and circular updates:
        if filter_model == filter_model_store:
            raise PreventUpdate

        return filter_model

    @staticmethod
    @callback(
        Output(ids._show_levels(MATCH), "data", allow_duplicate=True),
        Output(ids._grid(MATCH), "filterModel", allow_duplicate=True),
        Input(ids.info_button(MATCH), "n_clicks"),
        Input(ids.warning_button(MATCH), "n_clicks"),
        Input(ids.error_button(MATCH), "n_clicks"),
        Input(ids.critical_button(MATCH), "n_clicks"),
        Input(ids.debug_button(MATCH), "n_clicks"),
        State(ids._show_levels(MATCH), "data"),
        State(ids._grid(MATCH), "filterModel"),
        State(ids.info_button(MATCH), "id"),
        State(ids.warning_button(MATCH), "id"),
        State(ids.error_button(MATCH), "id"),
        State(ids.critical_button(MATCH), "id"),
        State(ids.debug_button(MATCH), "id"),
        prevent_initial_call=True,
    )
    def filter_data_by_level_name(
        dummy_info_clicks: int,
        dummy_warning_clicks: int,
        dummy_error_clicks: int,
        dummy_critical_clicks: int,
        dummy_debug_clicks: int,
        show_levels: dict[str, Any],
        filter_model: dict[str, Any],
        info_button_id: dict[str, Any],
        warning_button_id: dict[str, Any],
        error_button_id: dict[str, Any],
        critical_button_id: dict[str, Any],
        debug_button_id: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Filter data by level name."""
        triggered_id = ctx.triggered_id  # type: ignore - Dash typing issue
        if triggered_id is None:
            raise PreventUpdate

        if triggered_id == info_button_id:
            show_levels["info"] = not show_levels["info"]
        if triggered_id == warning_button_id:
            show_levels["warning"] = not show_levels["warning"]
        if triggered_id == error_button_id:
            show_levels["error"] = not show_levels["error"]
        if triggered_id == critical_button_id:
            show_levels["critical"] = not show_levels["critical"]
        if triggered_id == debug_button_id:
            show_levels["debug"] = not show_levels["debug"]

        disable_all_levels = not any(show_levels.values())

        filter_model_levelname: dict[str, Any] = {
            "filterType": "text",
            "operator": "AND" if disable_all_levels else "OR",
            "conditions": [],
        }

        # filtering is case-insensitive, so we convert the level names to lowercase
        if disable_all_levels:
            # Add notContains conditions for all levels
            filter_model_levelname["conditions"] = [
                {"filterType": "text", "type": "notContains", "filter": level.lower()} for level in show_levels
            ]
        else:
            # Add contains conditions for all levels that are shown
            filter_model_levelname["conditions"] = [
                {"filterType": "text", "type": "contains", "filter": level.lower()}
                for level, show in show_levels.items()
                if show
            ]

        filter_model["levelname"] = filter_model_levelname

        return (show_levels, filter_model)

    @staticmethod
    @callback(
        Output(ids.info_button(MATCH), "variant"),
        Output(ids.info_button(MATCH), "leftSection"),
        Output(ids.warning_button(MATCH), "variant"),
        Output(ids.warning_button(MATCH), "leftSection"),
        Output(ids.error_button(MATCH), "variant"),
        Output(ids.error_button(MATCH), "leftSection"),
        Output(ids.critical_button(MATCH), "variant"),
        Output(ids.critical_button(MATCH), "leftSection"),
        Output(ids.debug_button(MATCH), "variant"),
        Output(ids.debug_button(MATCH), "leftSection"),
        Input(ids._show_levels(MATCH), "data"),
    )
    def update_button_variants_from_show_levels(
        show_levels: dict[str, Any] | None,
    ) -> tuple[str, html.Span, str, html.Span, str, html.Span, str, html.Span, str, html.Span]:
        """Update button variants based on the selected log levels to show."""
        if show_levels is None:
            raise PreventUpdate
        button_variants = {level: "filled" if show else "outline" for level, show in show_levels.items()}
        button_left_sections = {
            level: FILTER_BUTTONS_PROPERTIES[level]["icon"]
            if show
            else FILTER_BUTTONS_PROPERTIES[level]["icon_disabled"]
            for level, show in show_levels.items()
        }

        return (
            button_variants["info"],
            button_left_sections["info"],
            button_variants["warning"],
            button_left_sections["warning"],
            button_variants["error"],
            button_left_sections["error"],
            button_variants["critical"],
            button_left_sections["critical"],
            button_variants["debug"],
            button_left_sections["debug"],
        )

    @staticmethod
    @callback(
        Output(ids._supervision_active(MATCH), "data", allow_duplicate=True),
        Input(ids.activate_monitoring(MATCH), "data"),
        State(ids._supervision_active(MATCH), "data"),
        prevent_initial_call=True,
    )
    def activate_monitoring_from_external_store(
        activate_monitoring_data: bool | None,
        current_stored_supervision_active: bool,
    ) -> bool | NoUpdate:
        """Update supervision state when external ``activate_monitoring`` store changes."""
        if activate_monitoring_data is None:
            raise PreventUpdate

        return (
            activate_monitoring_data if activate_monitoring_data != current_stored_supervision_active else no_update
        )  # avoid unnecessary updates

    @staticmethod
    @callback(
        Output(ids._supervision_active(MATCH), "data", allow_duplicate=True),
        Input(ids._activate_monitoring_switch(MATCH), "checked"),
        State(ids._supervision_active(MATCH), "data"),
        prevent_initial_call=True,
    )
    def activate_monitoring_from_ui_switch(
        activate_monitoring_checked: bool,
        current_stored_supervision_active: bool,
    ) -> bool | NoUpdate:
        """Update supervision state when the internal activate monitoring switch is toggled."""
        return (
            activate_monitoring_checked
            if activate_monitoring_checked != current_stored_supervision_active
            else no_update
        )  # avoid unnecessary updates

    @staticmethod
    @callback(
        Output(ids._interval(MATCH), "disabled"),
        Output(ids._activate_monitoring_switch(MATCH), "checked", allow_duplicate=True),
        Input(ids._supervision_active(MATCH), "data"),
        State(ids._interval(MATCH), "disabled"),
        State(ids._activate_monitoring_switch(MATCH), "checked"),
        prevent_initial_call=True,
    )
    def start_stop_supervision(
        supervision_active: bool | None,
        current_interval_disabled: bool,
        current_activate_monitoring_checked: bool,
    ) -> tuple[bool | NoUpdate, bool | NoUpdate]:
        """Sync control and interval states when supervision active state changes."""
        if supervision_active is None:
            raise PreventUpdate

        new_interval_disabled = not supervision_active
        new_activate_monitoring_checked = supervision_active
        return (
            new_interval_disabled if current_interval_disabled != new_interval_disabled else no_update,
            new_activate_monitoring_checked
            if current_activate_monitoring_checked != new_activate_monitoring_checked
            else no_update,
        )

    @staticmethod
    @callback(
        Output(ids._grid(MATCH), "rowData"),
        Output(ids._grid(MATCH), "dashGridOptions"),
        Input(ids._interval(MATCH), "n_intervals"),
        State(ids._log_file_and_format(MATCH), "data"),
        State(ids._grid(MATCH), "rowData"),
        State(ids._grid(MATCH), "dashGridOptions"),
        State(ids._show_error_notifications(MATCH), "data"),
    )
    def update_grid(
        dummy_n_intervals: int,
        log_file_and_format: dict[str, Any],
        old_row_data: list[dict[str, Any]],
        old_dash_grid_options: dict[str, Any],
        show_error_notifications: bool,
    ) -> tuple[list[dict[Hashable, Any]] | NoUpdate, dict[str, Any] | NoUpdate]:
        """Update grid rows and no-rows feedback based on parse status.

        On successful parsing, grid rows are populated from parsed records.
        When parsing fails or rows do not match the provided format, the grid is
        cleared and a parse-failure message is shown. When the source is missing,
        a source-missing message is shown. If enabled, parse failures also trigger
        ``dmc`` error notifications.
        """
        if not log_file_and_format:
            raise PreventUpdate

        if not log_file_and_format["log_file_path"] or not log_file_and_format["log_format"]:
            raise PreventUpdate

        new_dash_grid_options = copy.deepcopy(old_dash_grid_options)

        parse_result = LogsSupervisor._parse_logs_with_status(
            log_file_and_format["log_file_path"],
            log_file_and_format["log_format"],
        )

        if parse_result.status in (ParseStatus.FAILURE, ParseStatus.SUCCESS_NO_MATCHING_ROWS):
            new_dash_grid_options["noRowsOverlayComponentParams"] = {"message": PARSING_FAILED_NO_ROWS_MESSAGE}
            new_row_data: list[dict[Hashable, Any]] = []

            if show_error_notifications and (
                new_row_data != old_row_data or new_dash_grid_options != old_dash_grid_options
            ):
                error_notification_id = LogsSupervisor._error_notification_id(
                    log_file_and_format["log_file_path"],
                    log_file_and_format["log_format"],
                    parse_result,
                )

                message = "Failed to process log file."

                if parse_result.error is not None:
                    message += f" Error details: {parse_result.error}"

                message += " Please check the log file path and format."

                notification = {
                    "title": "Error processing log file",
                    "id": error_notification_id,
                    "action": "show",
                    "color": CommonColors.MANTINE_ERROR,
                    "message": message,
                    "autoClose": False,
                }

                set_props(
                    config._config.notification_container_id,
                    {"sendNotifications": [notification]},
                )

        elif parse_result.status == ParseStatus.SOURCE_MISSING:
            new_dash_grid_options["noRowsOverlayComponentParams"] = {"message": SOURCE_MISSING_NO_ROWS_MESSAGE}
            new_row_data: list[dict[Hashable, Any]] = []

        else:
            new_row_data = parse_result.data.to_dict("records")
            new_dash_grid_options["noRowsOverlayComponentParams"] = {"message": PLAIN_NO_ROWS_MESSAGE}

        row_data_changed = new_row_data != old_row_data
        dash_grid_options_changed = new_dash_grid_options != old_dash_grid_options

        return (
            new_row_data if row_data_changed or dash_grid_options_changed else no_update,
            new_dash_grid_options if dash_grid_options_changed else no_update,
        )

    @classmethod
    def get_logging_formatter_representation(cls, format_attribute: str) -> dict[str, dict[str, Any]]:
        """Get the logging formatter representation."""
        if format_attribute not in SUPPORTED_LOGGING_FORMATTER_OPTIONS_AND_HEADERS:
            raise ValueError(f"Unsupported logging formatter option: {format_attribute}")

        formatter_representation: dict[str, Any] = copy.deepcopy(DEFAULT_LOGGING_FORMATTER_REPRESENTATION)

        formatter_representation["headerName"] = SUPPORTED_LOGGING_FORMATTER_OPTIONS_AND_HEADERS[format_attribute]
        formatter_representation["field"] = format_attribute
        formatter_representation["tooltipField"] = format_attribute

        if format_attribute in LOGGING_FORMATTER_REPRESENTATION:
            formatter_representation.update(LOGGING_FORMATTER_REPRESENTATION[format_attribute])

        return formatter_representation
