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


"""Provides a Dash component for browsing and selecting a folder."""

from collections.abc import Iterator
import copy
from enum import StrEnum
import os
from pathlib import Path
import re
from typing import Any, cast
import uuid

try:
    import tkinter
    from tkinter import filedialog

    TKINTER_AVAILABLE = True
except Exception:  # ImportError or other import-related exception
    tkinter = None  # type: ignore[assignment]
    filedialog = None  # type: ignore[assignment]
    TKINTER_AVAILABLE = False

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

from ansys.solutions.dash_super_components.tree import Tree
from ansys.solutions.dash_super_components.utils import config
from ansys.solutions.dash_super_components.utils._common_colors import _CommonColors as CommonColors
from ansys.solutions.dash_super_components.utils.aio_ids import AIOIds
from ansys.solutions.dash_super_components.utils.path_validator import PathValidator
from ansys.solutions.dash_super_components.utils.svg_icons import (
    IconNames,
    create_base64_svg_src,
    create_icon_span,
)

_DEFAULT_MAX_TREE_DEPTH = 10
_DEFAULT_MAX_CHILDREN_PER_NODE = 100


class FolderSelectorMode(StrEnum):
    """Enumeration representing the desired technology for generating the folder selector."""

    TKINTER = "tkinter"
    BOOTSTRAP = "bootstrap"


class FolderSelector(html.Div):
    """
    A Dash component for browsing and selecting a directory.

    FolderSelector is based on the Dash All-in-One (AIO) component pattern. It
    supports two operating modes:

    - **Tkinter** (``FolderSelectorMode.TKINTER``): native OS dialog; requires the
      ``tkinter`` package.
    - **Bootstrap** (``FolderSelectorMode.BOOTSTRAP``): browser-based modal with a
      tree view of the file system; works in headless or remote environments.

    Bootstrap mode is a beta feature and is disabled by default. Applications can
    opt in by calling
    :func:`~ansys.solutions.dash_super_components.configure` with
    ``enable_beta_features=True``.

    When ``mode`` is not specified, and bootstrap beta is enabled, bootstrap is used
    when ``tkinter`` is unavailable or when the environment variable
    ``FOLDER_SELECTOR_REMOTE_DEPLOYMENT`` is set to ``true``, ``1``, or ``yes``;
    otherwise tkinter is used.

    .. note::

        The component must be placed inside a ``MantineProvider``. For error
        notifications to work correctly, a ``dmc.NotificationContainer`` must also be
        present in the application layout.  By default the container ID is
        ``"notification-container"``; use
        :func:`~ansys.solutions.dash_super_components.configure` to change it.

    Parameters
    ----------
    mode : FolderSelectorMode, optional
        Operating mode. Use ``FolderSelectorMode.TKINTER`` for a native OS dialog or
        ``FolderSelectorMode.BOOTSTRAP`` for a browser-based modal. Bootstrap mode is
        available only when
        :func:`~ansys.solutions.dash_super_components.configure` was called with
        ``enable_beta_features=True``. When omitted, the mode is
        selected automatically (see above).
    aio_id : str, optional
        Unique identifier for this component instance. A UUID is generated when not
        provided.
    browse_button_props : dict, optional
        Properties forwarded to the browse :class:`dmc.Button`.
    clear_button_props : dict, optional
        Properties forwarded to the clear :class:`dmc.ActionIcon`.
    style : dict, optional
        CSS style properties applied to the component container.
    options : dict, optional
        Additional configuration options:

        - ``default_path`` (str or pathlib.Path, optional): Path used as the default selected
          folder when nothing has been selected or the selection is cleared.
        - ``browse_from`` (str, optional): Root path for the file tree in Bootstrap
            mode. In Bootstrap mode, this value must be provided either via this
            option or via the ``FOLDER_SELECTOR_BROWSE_FROM`` environment variable.
        - ``topmost`` (bool, optional): If ``True``, the tkinter dialog appears in
          the foreground. Default is ``True``.
        - ``max_path_length`` (int, optional): Maximum allowed path length.
          Defaults to the system limit.
        - ``max_tree_depth`` (int, optional): Maximum folder depth to include in
          bootstrap mode. Default is ``10``.
        - ``max_children_per_node`` (int, optional): Maximum number of child
            folders included per tree node in Bootstrap mode. Default is ``100``.
        - ``display_field`` (dict, optional): Dict with an ``enabled`` key (``bool``)
          controlling whether the selected path is shown below the buttons, and an
          optional ``max_display_lines`` key (``int``) controlling how many lines the
          path text may span before being truncated with an ellipsis. When the path is
          truncated, hovering over the display field shows the full path in a tooltip.
          Default is ``{"enabled": True, "max_display_lines": 2}``.
    value : str, optional
        Preselected folder path. Populates the selected folder store upon component
        instantiation.
    """

    class FolderSelectorIds(AIOIds):
        """Provides IDs for the subcomponents of :class:`FolderSelector`."""

        @classmethod
        def _settings(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the settings store.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the settings store subcomponent.
            """
            return cls.make_id_dict("folder-selector", "settings", aio_id)

        @classmethod
        def _folder_selector_is_open(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the folder selector is open store.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the folder selector is open store subcomponent.
            """
            return cls.make_id_dict("folder-selector", "folder-selector-is-open", aio_id)

        @classmethod
        def _folder_selector_modal(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the folder selector modal.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the folder selector modal subcomponent.
            """
            return cls.make_id_dict("folder-selector", "folder-selector-modal", aio_id)

        @classmethod
        def _folder_selector_modal_done_button(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the modal done button.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the modal done button subcomponent.
            """
            return cls.make_id_dict("folder-selector", "folder-selector-modal-done-button", aio_id)

        @classmethod
        def _folders_structure(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the folders structure component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the folders structure component.
            """
            return cls.make_id_dict("folder-selector", "folders-structure", aio_id)

        @classmethod
        def browse_button(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the browse button.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the browse button subcomponent.
            """
            return cls.make_id_dict("folder-selector", "browse-button", aio_id)

        @classmethod
        def clear_button(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the clear button.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the clear button subcomponent.
            """
            return cls.make_id_dict("folder-selector", "clear-button", aio_id)

        @classmethod
        def _display_field(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the display field component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the display field subcomponent.
            """
            return cls.make_id_dict("folder-selector", "display-field", aio_id)

        @classmethod
        def _display_field_tooltip(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the display field tooltip.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the display field tooltip subcomponent.
            """
            return cls.make_id_dict("folder-selector", "display-field-tooltip", aio_id)

        @classmethod
        def selected_folder(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the selected folder store.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the selected folder store subcomponent.
            """
            return cls.make_id_dict("folder-selector", "selected-folder", aio_id)

    ids = FolderSelectorIds

    def __init__(
        self,
        mode: FolderSelectorMode | None = None,
        aio_id: str | None = None,
        browse_button_props: dict[str, Any] | None = None,
        clear_button_props: dict[str, Any] | None = None,
        style: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
        value: str | None = None,
    ):
        # set basic defaults
        if aio_id is None:
            aio_id = str(uuid.uuid4())
        if browse_button_props is None:
            browse_button_props = {}
        if clear_button_props is None:
            clear_button_props = {}
        if style is None:
            style = {}
        if options is None:
            options = {}

        # check inputs
        if mode and not isinstance(mode, FolderSelectorMode):  # type: ignore - user input check
            raise TypeError(f"mode must be an instance of FolderSelectorMode, got {type(mode)}")

        # extract and populate settings
        self.aio_id = aio_id
        self.mode = self._determine_final_mode(mode)

        self.browse_from = self._get_browse_from(options)
        if self.mode == FolderSelectorMode.BOOTSTRAP and self.browse_from is None:
            raise ValueError(
                "browse_from is required in BOOTSTRAP mode. Provide it via "
                "options['browse_from'] or FOLDER_SELECTOR_BROWSE_FROM."
            )

        default_path = options.get("default_path")
        default_path_str = None if default_path is None else str(default_path)

        display_field_enabled = options.get("display_field", {}).get("enabled", True)
        display_field_max_lines = options.get("display_field", {}).get("max_display_lines", 2)
        settings = {
            "topmost": options.get("topmost", True),
            "max_path_length": options.get("max_path_length", PathValidator.max_path_length()),
            "default_path": default_path_str,
            "mode": self.mode,
            "browse_from": self.browse_from,
            "max_tree_depth": options.get("max_tree_depth", _DEFAULT_MAX_TREE_DEPTH),
            "max_children_per_node": options.get("max_children_per_node", _DEFAULT_MAX_CHILDREN_PER_NODE),
        }

        folders_structure = (
            self.get_folders_structure(
                self.browse_from,
                max_depth=settings["max_tree_depth"],
                max_children_per_node=settings["max_children_per_node"],
            )
            if self.mode == FolderSelectorMode.BOOTSTRAP
            else None
        )

        browse_button_default_props = {
            "children": "Browse",
            "leftSection": create_icon_span(IconNames.MDI_FOLDER_SEARCH, 16),
            "radius": "xl",
            "className": "mantine-button",
            "variant": "outline",
            "style": {"width": "80%"},
        }
        self._browse_button_props = copy.deepcopy(browse_button_props)
        self._populate_with_defaults(self._browse_button_props, browse_button_default_props)

        clear_button_default_props = {
            "children": create_icon_span(IconNames.MATERIAL_DELETE, 20),
            "size": "md",
            "radius": "sm",
            "variant": "outline",
        }
        self._clear_button_props = copy.deepcopy(clear_button_props)
        self._populate_with_defaults(self._clear_button_props, clear_button_default_props)

        super().__init__(
            [
                html.Div(
                    [
                        dmc.Group(
                            [
                                dmc.Button(
                                    id=self.ids.browse_button(self.aio_id),
                                    **self._browse_button_props,
                                ),
                                dmc.ActionIcon(
                                    id=self.ids.clear_button(self.aio_id),
                                    **self._clear_button_props,
                                ),
                            ],
                        ),
                        dmc.Tooltip(
                            id=self.ids._display_field_tooltip(self.aio_id),
                            label="",
                            multiline=True,
                            maw=500,
                            withArrow=True,
                            children=dmc.Text(
                                id=self.ids._display_field(self.aio_id),
                                style={
                                    **({} if display_field_enabled else {"display": "none"}),
                                    "maxWidth": "100%",
                                },
                                lineClamp=display_field_max_lines,
                            ),
                        ),
                        dcc.Store(
                            id=self.ids.selected_folder(self.aio_id),
                            storage_type="memory",
                            data=value,
                        ),
                        dcc.Store(
                            id=self.ids._settings(self.aio_id),
                            storage_type="memory",
                            data=settings,
                        ),
                        dcc.Store(
                            id=self.ids._folder_selector_is_open(self.aio_id),
                            data=False,
                            storage_type="memory",
                        ),
                        dcc.Store(
                            id=self.ids._folders_structure(self.aio_id),
                            data=folders_structure,
                            storage_type="memory",
                        ),
                        dmc.Modal(
                            title="Pick a folder from the server",
                            id=self.ids._folder_selector_modal(self.aio_id),
                            zIndex=10000,
                            children=[
                                self.generate_tree(self.aio_id, folders_structure),
                                dmc.Group(
                                    children=[
                                        dmc.Button(
                                            "Done",
                                            id=self.ids._folder_selector_modal_done_button(
                                                self.aio_id,
                                            ),
                                        ),
                                    ],
                                    justify="center",
                                ),
                            ],
                            closeOnClickOutside=False,
                            closeOnEscape=False,
                            withCloseButton=False,
                            size="xl",
                        ),
                    ],
                    style=style,
                ),
            ],
        )

    def _get_browse_from(self, options: dict[str, Any]) -> str | None:
        browse_from = (
            os.environ.get(
                "FOLDER_SELECTOR_BROWSE_FROM",
                None,
            )
            if "browse_from" not in options
            else options["browse_from"]
        )  # this option restricts the FS visibility when mode == BOOTSTRAP
        # normalize the path - strip trailing slashes and resolve .. and .
        if browse_from is not None:
            browse_from = os.path.normpath(browse_from)
        return browse_from

    def _determine_final_mode(self, mode: FolderSelectorMode | None) -> FolderSelectorMode:
        bootstrap_enabled = config._config.enable_beta_features
        bootstrap_disabled_message = (
            "BOOTSTRAP mode is a beta feature and is disabled by default. "
            "Enable it via configure(enable_beta_features=True)."
        )

        def fallback_mode() -> FolderSelectorMode:
            if TKINTER_AVAILABLE:
                return FolderSelectorMode.TKINTER
            return FolderSelectorMode.BOOTSTRAP if bootstrap_enabled else FolderSelectorMode.TKINTER

        if mode:
            if mode == FolderSelectorMode.BOOTSTRAP:
                if not bootstrap_enabled:
                    raise ValueError(bootstrap_disabled_message)
                return FolderSelectorMode.BOOTSTRAP
            return fallback_mode()

        folder_selector_remote_deployment = str(
            os.environ.get("FOLDER_SELECTOR_REMOTE_DEPLOYMENT", "false"),
        ).lower() in {"true", "1", "yes"}

        if folder_selector_remote_deployment:
            if not bootstrap_enabled:
                raise ValueError(bootstrap_disabled_message)
            return FolderSelectorMode.BOOTSTRAP

        return fallback_mode()

    def _populate_with_defaults(self, properties: dict[str, Any], default_properties: dict[str, Any]) -> None:
        for key, val in default_properties.items():
            if key not in properties:
                properties[key] = val

    @staticmethod
    @callback(
        Output(ids.selected_folder(MATCH), "data"),
        Input(ids.selected_folder(MATCH), "data"),
        State(ids._settings(MATCH), "data"),
    )
    def populate_selected_folder_with_default_path(
        selected_folder: str | None,
        settings: dict[str, str | int | None],
    ) -> str | NoUpdate:
        """Populate the selected_folder store with default_path upon component instantiation."""
        default_path = settings["default_path"]
        if default_path and not selected_folder:
            return cast("str", default_path)
        else:
            return no_update

    @staticmethod
    @callback(
        Output(ids.browse_button(MATCH), "disabled", allow_duplicate=True),
        Input(ids.browse_button(MATCH), "n_clicks"),
        prevent_initial_call=True,
    )
    def disable_browse_button(n_clicks: int) -> bool | NoUpdate:
        """Disable browse button."""
        return True if n_clicks else no_update

    @staticmethod
    @callback(
        Output(ids.browse_button(MATCH), "disabled", allow_duplicate=True),
        Input(ids._folder_selector_is_open(MATCH), "data"),
        prevent_initial_call=True,
    )
    def enable_browse_button(folder_selector_is_open: bool) -> bool:
        """Enable browse button."""
        if not folder_selector_is_open:
            return False
        else:
            raise PreventUpdate

    @staticmethod
    @callback(
        Output(ids._folder_selector_is_open(MATCH), "data", allow_duplicate=True),
        Input(ids.browse_button(MATCH), "n_clicks"),
        prevent_initial_call=True,
    )
    def browse(
        n_clicks: int,
    ) -> bool:
        """Browse and enable folder selection."""
        if n_clicks:
            return True
        else:
            raise PreventUpdate

    @staticmethod
    @callback(
        Output(ids._folder_selector_is_open(MATCH), "data", allow_duplicate=True),
        Output(ids.selected_folder(MATCH), "data", allow_duplicate=True),
        Output(ids._folder_selector_modal(MATCH), "opened", allow_duplicate=True),
        Output(Tree.ids.selected_item(MATCH), "data", allow_duplicate=True),
        Input(ids._folder_selector_is_open(MATCH), "data"),
        State(ids._settings(MATCH), "data"),
        State(ids.browse_button(MATCH), "n_clicks"),
        State(ids.selected_folder(MATCH), "data"),
        State(ids._folders_structure(MATCH), "data"),
        State(ids._folder_selector_is_open(MATCH), "id"),
        prevent_initial_call=True,
    )
    def open_folder_selector(
        folder_selector_is_open: bool,
        settings: dict[str, str | int | None],
        n_clicks: int,
        current_selected_folder: str | None,
        folders_structure: dict[str, Any],
        component_id: dict[str, str],
    ) -> tuple[bool | NoUpdate, str | NoUpdate | None, bool | NoUpdate, dict[str, Any] | NoUpdate | None]:
        """
        Open a OS-provided or a browser-generated popup.

        The choice is ruled by `FolderSelectorMode`.
        The final goal is to select a folder from the server's file-system.
        """
        if not folder_selector_is_open:
            raise PreventUpdate

        topmost = cast("bool", settings["topmost"])
        max_path_length = cast("int", settings["max_path_length"])
        folder_selector_mode = cast("FolderSelectorMode", settings["mode"])
        notification = no_update
        selected_directory = None

        if folder_selector_mode == FolderSelectorMode.TKINTER:
            try:
                selected_directory = FolderSelector.ask_directory_with_tkinter(
                    topmost,
                )

                if selected_directory:
                    validation = PathValidator(selected_directory).validate(
                        max_path_length,
                    )
                    if isinstance(validation, Exception):
                        selected_directory = None
                        notification = {
                            "title": "Error during folder selection",
                            "id": "folder-selector-notify-failure" + "-" + str(n_clicks),
                            "action": "show",
                            "color": CommonColors.MANTINE_ERROR,
                            "message": f"{str(validation)}.",
                            "autoClose": False,
                        }
                        set_props(
                            config._config.notification_container_id,
                            {"sendNotifications": [notification]},
                        )
                else:
                    selected_directory = no_update  # user canceled the dialog

                return (
                    False,
                    selected_directory,
                    no_update,
                    no_update,
                )
            except Exception as exc:
                if not (
                    isinstance(exc, RuntimeError) or (TKINTER_AVAILABLE and isinstance(exc, tkinter.TclError))  # type: ignore[reportOptionalMemberAccess]
                ):
                    raise  # re-raise unexpected exceptions

                # Any error related to tkinter availability/operation will be handled here
                if config._config.enable_beta_features:
                    message = "The server either does not support tkinter "
                    message += "or the tkinter package is not installed "
                    message += "or it is running in a headless mode. "
                    message += "Please switch to BOOTSTRAP mode."
                else:
                    message = "The server does not support tkinter and BOOTSTRAP mode "
                    message += "is disabled because it is a beta feature. "
                    message += "Enable it via configure("
                    message += "enable_beta_features=True)."
                notification = {
                    "title": "Error during folder selection",
                    "id": "folder-selector-notify-failure" + "-" + str(n_clicks),
                    "action": "show",
                    "color": CommonColors.MANTINE_ERROR,
                    "message": message,
                    "autoClose": False,
                }
                set_props(
                    config._config.notification_container_id,
                    {"sendNotifications": [notification]},
                )
                return (
                    False,
                    None,
                    False,
                    no_update,
                )
        else:
            # open the modal

            # compute the index of the previously selected folder in the tree structure
            # this is required to highlight it correctly in the tree when the modal opens
            previous_selected_item_index = (
                FolderSelector.get_folder_id(current_selected_folder, folders_structure)
                if current_selected_folder
                else None
            )
            aio_id = component_id.get("aio_id") if component_id else None
            previous_selected_item = (
                Tree.ids.navlink_item(aio_id, previous_selected_item_index)
                if aio_id and previous_selected_item_index is not None
                else None
            )
            return no_update, no_update, True, previous_selected_item

    @staticmethod
    @callback(
        Output(ids._folder_selector_is_open(MATCH), "data", allow_duplicate=True),
        Output(ids._folder_selector_modal(MATCH), "opened", allow_duplicate=True),
        Output(ids.selected_folder(MATCH), "data", allow_duplicate=True),
        Input(ids._folder_selector_modal_done_button(MATCH), "n_clicks"),
        State(Tree.ids.selected_item(MATCH), "data"),
        State(ids._folders_structure(MATCH), "data"),
        State(ids._settings(MATCH), "data"),
        prevent_initial_call=True,
    )
    def dismiss_modal_and_update_selected_folder(
        n_clicks: int | None,
        selected_item_id: dict[str, str] | None,
        folders_structure: dict[str, Any] | None,
        settings: dict[str, str | int | None],
    ) -> tuple[bool | NoUpdate, bool | NoUpdate, str | None | NoUpdate]:
        """Close the modal and update data storage."""
        if not n_clicks:
            raise PreventUpdate

        if not folders_structure:
            message = "The folder structure could not be retrieved. Please try again or select another folder."
            notification = {
                "title": "Error during folder selection",
                "id": "folder-selector-notify-failure" + "-" + str(n_clicks),
                "action": "show",
                "color": CommonColors.MANTINE_ERROR,
                "message": message,
                "autoClose": True,
            }
            set_props(
                config._config.notification_container_id,
                {"sendNotifications": [notification]},
            )
            return False, False, no_update

        selected_folder = no_update
        if selected_item_id:
            # translate the navlink id to its corresponding path
            try:
                folder_id = Tree.ids.get_index_from_navlink_item_id(selected_item_id)
                resolved_folder = FolderSelector.resolve_folder(
                    folder_id,
                    folders_structure,
                )
                if resolved_folder is None:
                    raise ValueError()

                validation = FolderSelector._validate_bootstrap_selected_path(
                    resolved_folder,
                    cast("int", settings["max_path_length"]),
                )
                if isinstance(validation, Exception):
                    message = "The selected folder path is invalid. Please try again or select another folder."
                    notification = {
                        "title": "Error during folder selection",
                        "id": "folder-selector-notify-failure" + "-" + str(n_clicks),
                        "action": "show",
                        "color": CommonColors.MANTINE_ERROR,
                        "message": message,
                        "autoClose": True,
                    }
                    set_props(
                        config._config.notification_container_id,
                        {"sendNotifications": [notification]},
                    )
                else:
                    selected_folder = str(validation)
            except ValueError:
                # In case the selected nav item id is not found in the tree structure
                # we consider it as an invalid selection:
                message = "The selected folder path could not be resolved. Please try again or select another folder."
                notification = {
                    "title": "Error during folder selection",
                    "id": "folder-selector-notify-failure" + "-" + str(n_clicks),
                    "action": "show",
                    "color": CommonColors.MANTINE_ERROR,
                    "message": message,
                    "autoClose": True,
                }
                set_props(
                    config._config.notification_container_id,
                    {"sendNotifications": [notification]},
                )

        return (
            False,
            False,
            selected_folder,
        )

    @staticmethod
    @callback(
        Output(ids._display_field(MATCH), "children"),
        Output(ids._display_field_tooltip(MATCH), "label"),
        Input(ids.selected_folder(MATCH), "data"),
    )
    def update_display_field(
        selected_folder: str | None,
    ) -> tuple[str, str]:
        """Update the display text and tooltip label when a new folder is selected."""
        if selected_folder:
            # Insert zero-width spaces after common path delimiters so the
            # tooltip prefers breaking at those positions rather than mid-word.
            breakable = re.sub(r"([/\\._\-])", "\\1\u200b", selected_folder)
            return f"Selected folder: {breakable}", breakable
        return "No folder selected", ""

    @staticmethod
    @callback(
        Output(ids.selected_folder(MATCH), "clear_data", allow_duplicate=True),
        Output(Tree.ids.selected_item(MATCH), "clear_data", allow_duplicate=True),
        Input(ids.clear_button(MATCH), "n_clicks"),
        prevent_initial_call=True,
    )
    def clear_selected_folder(n_clicks: int) -> tuple[bool, bool]:
        """Clear previously selected folder."""
        if n_clicks > 0:
            return True, True
        raise PreventUpdate

    @classmethod
    def generate_tree(cls, aio_id: str, folders_structure: dict[str, Any] | None) -> Tree:
        """Create a tree to browse and select a folder from the server file system."""
        return Tree(
            aio_id=aio_id,
            items=[folders_structure] if isinstance(folders_structure, dict) else [],
            default_icon=create_base64_svg_src(IconNames.MATERIAL_FOLDER),
        )

    @classmethod
    def get_folders_structure(
        cls,
        browse_from: str | None,
        _as_absolute_path: bool = True,
        *,
        max_depth: int = _DEFAULT_MAX_TREE_DEPTH,
        max_children_per_node: int = _DEFAULT_MAX_CHILDREN_PER_NODE,
        _current_depth: int = 0,
    ) -> dict[str, Any]:
        """
        Recursively generate the file-system tree starting from `browse_from`.

        Parameters
        ----------
        browse_from : str | None
            The path from which to start browsing. When None, an empty dictionary is returned.
        max_depth : int, optional
            Maximum depth of the tree to generate. Default is 10.
        max_children_per_node : int, optional
            Maximum number of child folders to include per tree node. Default is 100.
        _as_absolute_path : bool, optional
            Internal parameter used for recursion. Do not use externally.

        Returns
        -------
        dict[str, Any]
            A dictionary representing the folder structure.
        """
        if browse_from is None:
            return {}

        if _current_depth >= max_depth:
            # Count excluded children for the description
            try:
                excluded_count = len(list(cls._iter_allowed_folders(browse_from)))
            except (OSError, PermissionError):
                excluded_count = 0

            result = {
                "id": str(uuid.uuid3(uuid.NAMESPACE_URL, browse_from)),
                "text": (browse_from if _as_absolute_path else Path(browse_from).name),
                "children": [],
            }
            if excluded_count > 0:
                result["description"] = f"⚠ subfolders not shown (maximum depth of {max_depth} reached)"
            return result

        children = sorted(
            [
                os.path.normpath(Path(browse_from) / folder.name)
                for folder in FolderSelector._iter_allowed_folders(browse_from)
            ],
        )

        truncated = len(children) > max_children_per_node
        excluded_count = len(children) - max_children_per_node if truncated else 0
        children = children[:max_children_per_node]

        result = {
            "id": str(
                uuid.uuid3(uuid.NAMESPACE_URL, browse_from),
            ),  # idempotent hash value
            "text": (browse_from if _as_absolute_path else Path(browse_from).name),  # folder name
            "children": (
                [
                    cls.get_folders_structure(
                        child,
                        _as_absolute_path=False,
                        max_depth=max_depth,
                        max_children_per_node=max_children_per_node,
                        _current_depth=_current_depth + 1,
                    )
                    for child in children
                ]
            ),
        }
        if truncated and excluded_count > 0:
            subfolders_text = "subfolders" if excluded_count > 1 else "subfolder"
            result["description"] = (
                f"⚠ {excluded_count} more {subfolders_text} not shown "
                f"(maximum of {max_children_per_node} subfolders reached)"
            )
        return result

    @staticmethod
    def _iter_allowed_folders(browse_from: str) -> Iterator[Path]:
        """Iterate over allowed folders in a given directory."""
        for folder in Path(browse_from).glob("*"):
            if FolderSelector._folder_is_allowed(folder):
                yield folder

    @staticmethod
    def _folder_is_allowed(folder: Path) -> bool:
        """Check if a folder is allowed to be included in the tree structure."""
        return folder.is_dir() and not folder.is_symlink() and not folder.name.startswith(".")

    @staticmethod
    def _validate_bootstrap_selected_path(
        resolved_path: str,
        max_path_length: int,
    ) -> Path | Exception:
        """Validate a Bootstrap-selected folder path using stateless filesystem checks."""
        if os.pardir in Path(resolved_path).parts:
            return ValueError("The selected folder path contains traversal sequences.")

        normalized_path = os.path.normpath(resolved_path)
        canonical_path = os.path.realpath(resolved_path)
        if normalized_path != resolved_path or normalized_path != canonical_path:
            return ValueError("The selected folder path contains traversal sequences.")

        validation = PathValidator(canonical_path).validate(max_path_length, check_existence=True)
        if isinstance(validation, Exception):
            return validation
        if not validation.is_dir():
            return ValueError("The selected folder path is not a directory.")
        return validation

    @classmethod
    def resolve_folder(
        cls,
        folder_id: str,
        tree_structure: dict[str, Any],
        _prefix: str = "",
    ) -> str | None:
        """
        Traverse the tree to find a path corresponding to the `folder_id`.

        Parameters
        ----------
        folder_id : str
            The unique identifier of the folder to find in the tree.
        tree_structure : dict[str, Any]
            The tree structure dictionary to search through.
        _prefix : str, optional
            Internal parameter used for recursion. Do not use externally.

        Returns
        -------
        str or None
            The full path to the folder if found, ``None`` otherwise.
        """
        if len(_prefix) > 0 and not _prefix.endswith(os.path.sep):
            _prefix += os.path.sep
        if tree_structure["id"] == folder_id:
            return _prefix + tree_structure["text"]
        for child in tree_structure.get("children", []):
            found = cls.resolve_folder(folder_id, child, _prefix + tree_structure["text"])
            if found:
                return found
        return None

    @classmethod
    def get_folder_id(
        cls,
        folder_path: str,
        tree_structure: dict[str, Any],
        _prefix: str = "",
    ) -> str | None:
        """
        Traverse the tree to find a folder_id corresponding to the given `folder_path`.

        Parameters
        ----------
        folder_path : str
            The full path of the folder to find in the tree.
        tree_structure : dict[str, Any]
            The tree structure dictionary to search through.
        _prefix : str, optional
            Internal parameter used for recursion. Do not use externally.

        Returns
        -------
        str or None
            The unique identifier of the folder if found, ``None`` otherwise.
        """
        if len(_prefix) > 0 and not _prefix.endswith(os.path.sep):
            _prefix += os.path.sep
        current_path = _prefix + tree_structure["text"]
        if os.path.normpath(current_path) == os.path.normpath(folder_path):
            return tree_structure["id"]
        for child in tree_structure.get("children", []):
            found = cls.get_folder_id(folder_path, child, current_path)
            if found:
                return found
        return None

    @classmethod
    def ask_directory_with_tkinter(cls, topmost: bool) -> str | None:
        """Open a tkinter popup and return the selected directory or None if the user cancels."""
        if not TKINTER_AVAILABLE:
            raise RuntimeError("tkinter is not available in this environment")

        root = tkinter.Tk()  # type: ignore reportOptionalMemberAccess - tkinter availability is checked before
        try:
            root.withdraw()
            if topmost:
                root.wm_attributes("-topmost", 1)
            selected_directory = filedialog.askdirectory()  # type: ignore reportOptionalMemberAccess - tkinter availability is checked before
            if selected_directory == "":  # user canceled the dialog
                selected_directory = None
            return selected_directory
        finally:
            root.destroy()
