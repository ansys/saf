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


"""Provides a Dash component for creating nested hierarchical tree structures."""

import copy
from enum import StrEnum
import re
from typing import Any, cast
import uuid
import warnings

from dash import get_relative_path
from dash.exceptions import PreventUpdate

from ansys.solutions.dash_super_components.utils._common_colors import _CommonColors as CommonColors

try:
    # dash-extensions < 2.0.5
    from dash_extensions.enrich import _Wildcard  # pyright: ignore[reportAttributeAccessIssue]
except ImportError:
    # dash-extensions >= 2.0.5
    from dash_extensions.enrich import (
        Wildcard as _Wildcard,  # pyright: ignore[reportAttributeAccessIssue]
    )
from dash_extensions.enrich import (
    ALL,
    MATCH,
    Input,
    Output,
    State,
    callback,
    clientside_callback,
    ctx,
    dcc,
    html,
)
from dash_iconify import DashIconify
import dash_mantine_components as dmc

from ansys.solutions.dash_super_components.utils.aio_ids import AIOIds
from ansys.solutions.dash_super_components.utils.svg_icons import create_image_icon_span

_UNSET = object()
_IMAGE_FILE_EXTENSIONS = (".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico")


class TreeIconType(StrEnum):
    """Valid icon rendering modes for Tree items."""

    AUTO = "auto"
    LOCAL = "local"
    ICONIFY = "iconify"


class Tree(html.Div):
    """
    A Dash component for creating nested hierarchical tree structures.

    Tree is based on the Dash All-in-One (AIO) component pattern. It renders a
    multi-level ``dmc.NavLink`` tree and is commonly used as a navigation sidebar.

    Interaction behavior is intentionally decoupled for parent nodes:

    - Clicking a row selects the node.
    - Clicking the dedicated expander control toggles open/closed state.

    Each item dict supports the following keys:

    - ``"id"`` *(required)*: unique string identifier for the node.
    - ``"text"`` *(required)*: display label.
    - ``"icon"`` *(optional)*: icon value for the item. Supports local image/data-URI/path values
        (rendered as a CSS-mask icon span) and Iconify names like ``"mdi:user"`` (rendered with
        ``DashIconify``).
    - ``"icon_color"`` *(optional)*: CSS color value applied to the icon. When omitted,
        icons inherit ``currentColor`` from the NavLink and follow active/dark-mode colors.
    - ``"icon_type"`` *(optional)*: one of ``"auto"`` (default), ``"local"``, or
        ``"iconify"``. Use this to override auto-detection when needed.
    - ``"children"`` *(optional)*: list of child item dicts (same structure).
    - ``"expanded"`` *(optional)*: bool — whether the node is expanded on load.
    - ``"disabled"`` *(optional)*: bool — whether the node is non-interactive.
    - ``"description"`` *(optional)*: secondary text shown below the label.
    - ``"styles"`` *(optional)*: dict forwarded to ``dmc.NavLink`` for per-item styling.

    To access the currently selected item in a callback use::

        Tree.ids.selected_item(aio_id)  # Store; value is a dict with key "index" = item id

    To resolve the item ``id`` string from the store value use::

        Tree.ids.get_index_from_navlink_item_id(selected_item)

    Parameters
    ----------
    items : list of dict
        List of tree node definitions (see structure above).
    selected_item : str, optional
        The ``id`` of the node that is highlighted on initial render.
    default_icon : str, optional
        Fallback icon value for nodes that do not specify an ``icon``.
        Supports both local image/data-URI and Iconify values.
    aio_id : str, optional
        Unique identifier for this component instance. A UUID is generated when
        not provided.
    """

    class TreeIds(AIOIds):
        """Provides IDs for the subcomponents of :class:`Tree`."""

        @classmethod
        def _make_id_dict_with_index(
            cls, subcomponent: str, aio_id: str | _Wildcard, index: str | None | _Wildcard
        ) -> dict[str, Any]:
            id_dict = cls.make_id_dict("tree", subcomponent, aio_id)
            id_dict["index"] = index
            return id_dict

        @classmethod
        def _old_selected_item(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the old selected item store.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the old selected item store subcomponent.
            """
            return cls.make_id_dict("tree", "old-selected-item", aio_id)

        @classmethod
        def _opened_items(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the opened-items store.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the opened-items store subcomponent.
            """
            return cls.make_id_dict("tree", "opened-items", aio_id)

        @classmethod
        def _behavior_installed(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the behavior-installed marker store.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the behavior-installed marker store.
            """
            return cls.make_id_dict("tree", "behavior-installed", aio_id)

        @classmethod
        def selected_item(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the selected item store.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the selected item store subcomponent.
            """
            return cls.make_id_dict("tree", "selected-item", aio_id)

        @classmethod
        def navlink_item(cls, aio_id: str | _Wildcard, index: str | None | _Wildcard) -> dict[str, Any]:
            """Return the ID for a navlink item.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.
            index : str, None, or _Wildcard
                The unique index of the navlink item within the tree.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for a navlink item subcomponent.
            """
            return cls._make_id_dict_with_index("navlink-item", aio_id, index)

        @classmethod
        def _expander(cls, aio_id: str | _Wildcard, index: str | None | _Wildcard) -> dict[str, Any]:
            """Return the ID for a tree expander control.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.
            index : str, None, or _Wildcard
                The unique index of the navlink item within the tree.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for an expander subcomponent.
            """
            return cls._make_id_dict_with_index("expander", aio_id, index)

        @classmethod
        def _row_selector(cls, aio_id: str | _Wildcard, index: str | None | _Wildcard) -> dict[str, Any]:
            """Return the ID for a hidden row-selector proxy control.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.
            index : str, None, or _Wildcard
                The unique index of the navlink item within the tree.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for a row-selector proxy subcomponent.
            """
            return cls._make_id_dict_with_index("row-selector", aio_id, index)

        @classmethod
        def _expander_proxy(cls, aio_id: str | _Wildcard, index: str | None | _Wildcard) -> dict[str, Any]:
            """Return the ID for a hidden expander-proxy control.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.
            index : str, None, or _Wildcard
                The unique index of the navlink item within the tree.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for an expander-proxy subcomponent.
            """
            return cls._make_id_dict_with_index("expander-proxy", aio_id, index)

        @classmethod
        def get_index_from_navlink_item_id(cls, navlink_item_id: dict[str, Any]) -> str:
            """Extract the index from a navlink item ID dictionary.

            Parameters
            ----------
            navlink_item_id : dict[str, Any]
                The ID dictionary from which to extract the index.

            Returns
            -------
            str
                The extracted index.

            Raises
            ------
            ValueError
                If the index is not found in the navlink item ID or if the ID is invalid.
            """
            cls._validate_navlink_item_id(navlink_item_id)

            _sentinel_idx = "__sentinel_idx__"
            reference = cls.navlink_item("__sentinel_aio__", _sentinel_idx)

            # The index key is whichever key holds the index sentinel in the reference.
            index_key = next(k for k, v in reference.items() if v == _sentinel_idx)
            index = navlink_item_id.get(index_key)
            if not index:
                raise ValueError(f"Index not found in navlink item ID: {navlink_item_id}")

            return index

        @classmethod
        def get_aio_id_from_navlink_item_id(cls, navlink_item_id: dict[str, Any]) -> str:
            """Extract the aio_id from a navlink item ID dictionary.

            Parameters
            ----------
            navlink_item_id : dict[str, Any]
                The ID dictionary from which to extract the aio_id.

            Returns
            -------
            str
                The extracted aio_id.

            Raises
            ------
            ValueError
                If the aio_id is not found in the navlink item ID or if the ID is invalid.
            """
            cls._validate_navlink_item_id(navlink_item_id)

            _sentinel_aio_id = "__sentinel_aio__"
            reference = cls.navlink_item(_sentinel_aio_id, "__sentinel_idx__")

            # The aio_id key is whichever key holds the aio_id sentinel in the reference.
            aio_id_key = next(k for k, v in reference.items() if v == _sentinel_aio_id)
            aio_id = navlink_item_id.get(aio_id_key)
            if not aio_id:
                raise ValueError(f"aio_id not found in navlink item ID: {navlink_item_id}")

            return aio_id

        @classmethod
        def _validate_navlink_item_id(cls, navlink_item_id: dict[str, Any]):
            _sentinel_aio = "__sentinel_aio__"
            _sentinel_idx = "__sentinel_idx__"
            reference = cls.navlink_item(_sentinel_aio, _sentinel_idx)

            # Validate required keys are present in the provided navlink_item_id:
            missing = [k for k in reference if k not in navlink_item_id]
            if missing:
                raise ValueError(f"Invalid navlink item ID: missing keys {','.join(missing)}")

            # Validate key/value pairs whose values are fixed (i.e. no sentinel):
            for key, expected in reference.items():
                if expected not in (_sentinel_aio, _sentinel_idx) and navlink_item_id.get(key) != expected:
                    raise ValueError(
                        f"Invalid navlink item ID: expected {key}={expected!r}, got {navlink_item_id.get(key)!r}"
                    )

        @classmethod
        def _generate_data_index_for_navlink_item(cls, aio_id: str, index: str) -> str:
            """Generate a data-index string for a navlink item.

            This is used to uniquely identify navlink items in the DOM for clientside updates.

            Parameters
            ----------
            aio_id : str
                The component's unique identifier.
            index : str
                The unique index of the navlink item within the tree.

            Returns
            -------
            str
                The generated data-index string.
            """
            return f"tree_navlink-item_{aio_id}_{index}"

        @classmethod
        def _generate_data_index_for_row_selector(cls, aio_id: str, index: str) -> str:
            """Generate a lookup key string for a row-selector proxy control."""
            return f"tree_row-selector_{aio_id}_{index}"

        @classmethod
        def _generate_data_index_for_expander_proxy(cls, aio_id: str, index: str) -> str:
            """Generate a lookup key string for an expander-proxy control."""
            return f"tree_expander-proxy_{aio_id}_{index}"

    ids = TreeIds

    def __init__(
        self,
        items: list[dict[str, Any]],
        selected_item: str | None = None,
        default_icon: str | None = None,
        aio_id: str | None = None,
    ):
        self._check_items_validity(items)

        self._items = items
        self._active_item_id = selected_item
        if aio_id is None:
            aio_id = str(uuid.uuid4())
        self.aio_id = aio_id
        self.default_icon = default_icon if default_icon else None

        (
            self._opened_item_ids,
            self._all_item_ids,
            self._parent_item_ids,
        ) = self._collect_tree_item_metadata(items)

        super().__init__(
            [
                html.Link(rel="stylesheet", href=get_relative_path("/super-components/tree-styles.css")),
                dcc.Store(
                    id=self.ids.selected_item(aio_id),
                    storage_type="memory",
                    data=self.ids.navlink_item(aio_id, selected_item),
                ),
                dcc.Store(
                    id=self.ids._old_selected_item(aio_id),
                    storage_type="memory",
                    data=self.ids.navlink_item(aio_id, selected_item),
                ),
                dcc.Store(
                    id=self.ids._opened_items(aio_id),
                    storage_type="memory",
                    data=sorted(self._opened_item_ids),
                ),
                dcc.Store(
                    id=self.ids._behavior_installed(aio_id),
                    storage_type="memory",
                    data=False,
                ),
                self._build_hidden_proxy_container(aio_id),
                html.Div(
                    self._make_tree(),
                ),
            ],
        )

    def _build_hidden_proxy_container(self, aio_id: str) -> html.Div:
        """Build the hidden proxy controls used by clientside click interception."""
        row_selector_buttons = [
            html.Button(
                id=self.ids._row_selector(aio_id, item_id),
                className="tree-row-selector-proxy",
                n_clicks=0,
                title=self.ids._generate_data_index_for_row_selector(aio_id, item_id),
            )
            for item_id in self._all_item_ids
        ]

        expander_proxy_buttons = [
            html.Button(
                id=self.ids._expander_proxy(aio_id, item_id),
                className="tree-expander-proxy",
                n_clicks=0,
                title=self.ids._generate_data_index_for_expander_proxy(aio_id, item_id),
            )
            for item_id in self._parent_item_ids
        ]

        return html.Div(
            row_selector_buttons + expander_proxy_buttons,
            className="tree-row-selector-container",
            style={"display": "none"},
        )

    def _create_navlink(self, step: dict[str, Any]) -> dmc.NavLink:
        """Create each NavLink component recursively."""
        styles = copy.deepcopy(step.get("styles", {}))
        if styles.get("label", {}).get("color", None) is None:
            styles.setdefault("label", {})["color"] = CommonColors.MANTINE_TEXT

        left_section = self._build_left_section(step)
        has_children = bool(step.get("children"))
        is_opened = step["id"] in self._opened_item_ids
        right_section = (
            html.Span(
                "",
                id=self.ids._expander(self.aio_id, step["id"]),
                className=("tree-expander-control tree-expander-open" if is_opened else "tree-expander-control"),
                n_clicks=0,
            )
            if has_children
            else None
        )

        nav_link = dmc.NavLink(
            id=self.ids.navlink_item(self.aio_id, step["id"]),
            attributes={
                "root": {
                    "data-index": self.ids._generate_data_index_for_navlink_item(self.aio_id, step["id"]),
                    "data-aio-id": self.aio_id,
                    "data-item-index": step["id"],
                }
            },
            label=step["text"],
            leftSection=left_section,
            rightSection=right_section,
            disableRightSectionRotation=True,
            active=(step["id"] == self._active_item_id),
            disabled=step.get("disabled", False),
            description=step.get("description", ""),
            opened=is_opened,
            childrenOffset=28,
            styles=styles,
        )
        if "children" in step:
            nav_link.children = [self._create_navlink(child) for child in step["children"]]

        return nav_link

    def _build_left_section(self, step: dict[str, Any]) -> html.Span | DashIconify | None:
        """Build the icon component for one tree item.

        Icons render as a single component and inherit ``currentColor`` by default.
        """
        icon_value = self._resolve_item_icon_value(step)
        return self._build_left_section_single(icon_value, step)

    def _resolve_item_icon_value(
        self,
        step: dict[str, Any],
    ) -> str | None:
        """Resolve one icon value for an item.

        Resolution order prefers ``icon`` and falls back to ``default_icon`` if ``icon`` is not set.
        """
        icon_value = step.get("icon", _UNSET)

        if icon_value not in (_UNSET, None, ""):
            return icon_value

        return self.default_icon

    def _build_left_section_single(
        self, icon_value: str | None, step: dict[str, Any]
    ) -> html.Span | DashIconify | None:
        """Build a single icon using currentColor behavior by default."""
        if icon_value is None:
            return None

        icon_type = self._resolve_icon_type_for_value(step, icon_value)
        return self._build_icon_component(icon_value, icon_type, step.get("icon_color"))

    def _resolve_icon_type_for_value(self, step: dict[str, Any], icon_value: str) -> TreeIconType:
        """Resolve the concrete icon type for one resolved icon value."""
        icon_type = self._resolve_icon_type(step)
        if icon_type != TreeIconType.AUTO:
            return icon_type

        if self._is_local_icon_value(icon_value):
            return TreeIconType.LOCAL
        return TreeIconType.ICONIFY

    def _resolve_icon_type(self, step: dict[str, Any]) -> TreeIconType:
        """Resolve icon type override, defaulting to auto-detection."""
        icon_type = step.get("icon_type", TreeIconType.AUTO)
        if isinstance(icon_type, TreeIconType):
            return icon_type

        try:
            return TreeIconType(icon_type)
        except ValueError:
            warnings.warn(
                f"Unknown icon_type={icon_type!r}. Falling back to {TreeIconType.AUTO.value!r}.",
                UserWarning,
                stacklevel=4,
            )
            return TreeIconType.AUTO

    def _build_icon_component(
        self,
        icon_value: str,
        icon_type: TreeIconType,
        icon_color: str | None = None,
    ) -> html.Span | DashIconify:
        """Build an icon component from an icon value and rendering mode.

        ``TreeIconType.LOCAL`` renders a masked ``html.Span`` that can inherit text color.
        ``TreeIconType.ICONIFY`` renders a ``DashIconify`` component.
        """
        if icon_type == TreeIconType.LOCAL:
            return create_image_icon_span(
                mask_image=icon_value,
                size_px=16,
                color=icon_color,
                class_name="tree-icon-mask",
            )
        if icon_type == TreeIconType.ICONIFY:
            style = {"color": icon_color} if icon_color else None
            return DashIconify(icon=icon_value, height=16, style=style)
        raise ValueError(f"Unexpected icon_type: {icon_type!r}")

    @staticmethod
    def _check_items_validity(items: list[dict[str, Any]]) -> None:
        """Check that all items have valid 'id' and 'text' properties."""
        for item in items:
            if "id" not in item or not isinstance(item["id"], str):
                raise ValueError(f"Each tree item must have a unique string 'id'. Invalid item: {item}")
            if "text" not in item or not isinstance(item["text"], str):
                raise ValueError(f"Each tree item must have a string 'text'. Invalid item: {item}")
            children = item.get("children")
            if isinstance(children, list):
                Tree._check_items_validity(children)

    @staticmethod
    def _collect_tree_item_metadata(
        items: list[dict[str, Any]],
    ) -> tuple[set[str], list[str], list[str]]:
        """Collect opened, all-item, and parent-item ids from nested tree items."""
        opened_ids: set[str] = set()
        all_item_ids: list[str] = []
        parent_item_ids: list[str] = []

        for item in items:
            item_id = cast("str", item.get("id"))
            all_item_ids.append(item_id)

            if item.get("expanded"):
                opened_ids.add(item_id)

            children = item.get("children")
            has_children = isinstance(children, list) and bool(children)
            if has_children:
                parent_item_ids.append(item_id)

            if has_children:
                child_items = cast("list[dict[str, Any]]", children)
                child_opened, child_all, child_parents = Tree._collect_tree_item_metadata(child_items)
                opened_ids.update(child_opened)
                all_item_ids.extend(child_all)
                parent_item_ids.extend(child_parents)

        return opened_ids, all_item_ids, parent_item_ids

    @staticmethod
    def _is_local_icon_value(icon_value: str) -> bool:
        """Determine if an icon value should use LOCAL rendering.

        LOCAL values are rendered by ``_build_icon_component`` as a CSS-mask icon span
        (not an ``html.Img`` element).
        """
        if not isinstance(icon_value, str):
            return False

        normalized_value = icon_value.strip()
        normalized_value_lower = normalized_value.lower()

        if normalized_value_lower.startswith("data:image/"):
            return True

        if normalized_value_lower.startswith(("http://", "https://", "/", "./", "../", "assets/")):
            return True

        if re.match(r"^[a-zA-Z]:[\\/]", normalized_value):
            return True

        if normalized_value.startswith("\\\\"):
            return True

        return normalized_value_lower.endswith(_IMAGE_FILE_EXTENSIONS)

    def _make_tree(self) -> list[dmc.NavLink]:
        """Create the tree based on the items provided."""
        return [self._create_navlink(step) for step in self._items]

    @staticmethod
    def _build_opened_flags(
        all_item_ids: list[dict[str, Any]],
        opened_items: list[str] | None,
    ) -> list[bool]:
        """Build ordered opened flags aligned with the navlink ALL id list."""
        opened_set = set(opened_items or [])
        return [id_dict.get("index") in opened_set for id_dict in all_item_ids]

    @staticmethod
    @callback(
        Output(ids.selected_item(MATCH), "data", allow_duplicate=True),
        Input(ids.navlink_item(MATCH, ALL), "n_clicks"),
        Input(ids._row_selector(MATCH, ALL), "n_clicks"),
        State(ids.selected_item(MATCH), "data"),
        State(ids._row_selector(MATCH, ALL), "id"),
        prevent_initial_call=True,
    )
    def save_clicked_item(
        _navlink_dummy_n_clicks: list[int],
        _row_selector_dummy_n_clicks: list[int],
        current_selected_item: dict[str, Any],
        all_row_selector_ids: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Store the newly clicked navlink ID dictionary in the selected-item store."""
        triggered_id = ctx.triggered_id
        if not triggered_id:
            raise PreventUpdate

        is_row_selector_trigger = triggered_id in all_row_selector_ids
        if is_row_selector_trigger:
            # Need to construct the navlink item ID from the row-selector proxy ID.
            aio_id = triggered_id.get("aio_id")
            item_id = triggered_id.get("index")
            if not aio_id or not item_id:
                raise PreventUpdate
            new_selected_item = Tree.ids.navlink_item(aio_id, item_id)

        else:
            new_selected_item = triggered_id

        if new_selected_item == current_selected_item:
            raise PreventUpdate
        return new_selected_item

    @staticmethod
    @callback(
        Output(ids._opened_items(MATCH), "data"),
        Input(ids._expander_proxy(MATCH, ALL), "n_clicks"),
        State(ids._opened_items(MATCH), "data"),
        prevent_initial_call=True,
    )
    def toggle_opened_item(
        _expander_proxy_dummy_n_clicks: list[int],
        opened_items: list[str] | None,
    ) -> list[str]:
        """Toggle opened state only when the dedicated expander proxy control is clicked."""
        triggered_id = ctx.triggered_id
        if not triggered_id:
            raise PreventUpdate

        item_id = triggered_id.get("index")
        if not item_id:
            raise PreventUpdate

        opened_set = set(opened_items or [])
        if item_id in opened_set:
            opened_set.remove(item_id)
        else:
            opened_set.add(item_id)
        return sorted(opened_set)

    @staticmethod
    @callback(
        Output(ids.navlink_item(MATCH, ALL), "opened", allow_duplicate=True),
        Output(ids._expander(MATCH, ALL), "className", allow_duplicate=True),
        Input(ids._opened_items(MATCH), "data"),
        State(ids.navlink_item(MATCH, ALL), "id"),
        State(ids._expander(MATCH, ALL), "id"),
        prevent_initial_call=True,
    )
    def sync_opened_items(
        opened_items: list[str] | None,
        all_navlink_ids: list[dict[str, Any]],
        all_expander_ids: list[dict[str, Any]],
    ) -> tuple[list[bool], list[str]]:
        """Apply controlled opened state to navlinks and expander class state."""
        opened_set = set(opened_items or [])
        opened_flags = Tree._build_opened_flags(all_navlink_ids, opened_items)
        expander_classes = [
            (
                "tree-expander-control tree-expander-open"
                if expander_id.get("index") in opened_set
                else "tree-expander-control"
            )
            for expander_id in all_expander_ids
        ]
        return opened_flags, expander_classes

    # Install Tree click interception clientside for stable select vs expand behavior.
    clientside_callback(
        """function(_dummy_navlink_ids) {
            const proxyButtonCache =
                window.__dashSuperComponentsTreeProxyButtonCache ||
                (window.__dashSuperComponentsTreeProxyButtonCache = {
                    "tree-row-selector-proxy": Object.create(null),
                    "tree-expander-proxy": Object.create(null),
                });

            function rebuildProxyButtonCache(className) {
                const nextCache = Object.create(null);
                const nodes = document.getElementsByClassName(className);
                for (let i = 0; i < nodes.length; i += 1) {
                    const node = nodes[i];
                    const key = node.getAttribute("title");
                    if (key) {
                        nextCache[key] = node;
                    }
                }
                proxyButtonCache[className] = nextCache;
            }

            function findProxyButton(className, key) {

                let button = proxyButtonCache[className]?.[key];
                if (button && document.contains(button)) {
                    return button;
                }

                rebuildProxyButtonCache(className);
                return proxyButtonCache[className]?.[key] ?? null;
            }

            // Keep proxy cache in sync with Tree rebuilds that retrigger this callback.
            rebuildProxyButtonCache("tree-row-selector-proxy");
            rebuildProxyButtonCache("tree-expander-proxy");

            // Install this global click handler only once per page.
            if (window.__dashSuperComponentsTreeBehaviorInstalled) {
                return true;
            }
            window.__dashSuperComponentsTreeBehaviorInstalled = true;

            window.addEventListener(
                "click",
                function (event) {
                    const target = event.target;
                    if (!target || typeof target.closest !== "function") {
                        return;
                    }

                    // Let synthetic proxy clicks bubble to Dash untouched.
                    if (target.closest(".tree-row-selector-proxy, .tree-expander-proxy")) {
                        return;
                    }

                    const expander = target.closest(".tree-expander-control");
                    if (!expander) {
                        const navlinkRoot = target.closest("[data-index^='tree_navlink-item_']");
                        if (!navlinkRoot) {
                            return;
                        }

                        // Clicking a parent row (outside the arrow) should select only.
                        const hasExpander =
                            navlinkRoot.querySelector(".tree-expander-control") !== null;
                        if (hasExpander) {
                            const aioId = navlinkRoot.getAttribute("data-aio-id");
                            const itemIndex = navlinkRoot.getAttribute("data-item-index");

                            if (aioId && itemIndex) {
                                const selectorKey = "tree_row-selector_" + aioId + "_" + itemIndex;
                                const selectorButton = findProxyButton(
                                    "tree-row-selector-proxy",
                                    selectorKey
                                );
                                if (selectorButton && typeof selectorButton.click === "function") {
                                    selectorButton.click();
                                }
                            }

                            // Intentionally prevent other click handlers from treating this as
                            // a regular row click, so parent rows do not toggle open/closed.
                            event.stopPropagation();
                        }
                        return;
                    }

                    // Clicking the arrow should toggle open/closed state only.
                    const navlinkRoot = expander.closest("[data-index^='tree_navlink-item_']");
                    if (navlinkRoot) {
                        const aioId = navlinkRoot.getAttribute("data-aio-id");
                        const itemIndex = navlinkRoot.getAttribute("data-item-index");

                        if (aioId && itemIndex) {
                            const proxyKey = "tree_expander-proxy_" + aioId + "_" + itemIndex;
                            const proxyButton = findProxyButton("tree-expander-proxy", proxyKey);
                            if (proxyButton && typeof proxyButton.click === "function") {
                                proxyButton.click();
                            }
                        }
                    }

                    // This callback listens in capture phase; stopping propagation here is
                    // intentional so external bubble/capture listeners do not trigger competing
                    // behavior for the same expander click.
                    event.stopPropagation();
                },
                true
            );

            return true;
        }""",
        Output(ids._behavior_installed(MATCH), "data"),
        Input(ids.navlink_item(MATCH, ALL), "id"),
    )

    # Update "active" state of navlink items when the selected item changes.
    # Done as a clientside callback as this allows querying the DOM to find the navlink elements
    # and update their "active" state without storing the entire tree structure in memory on
    # the server side.
    clientside_callback(
        """function(selected_item, old_selected_item) {
            const noUpdate = window.dash_clientside.no_update;

            if (!selected_item || typeof selected_item !== "object") {
                return noUpdate;
            }

            const new_element_id = "tree_navlink-item_"
                + selected_item["aio_id"] + "_" + selected_item["index"];
            const old_element_id = "tree_navlink-item_"
                + old_selected_item["aio_id"] + "_" + old_selected_item["index"];

            // The callback may fire before React has finished rendering the new element.
            // Instead of returning no_update (which loses the update), we schedule the DOM
            // manipulation to retry via requestAnimationFrame until the element appears,
            // and return new_element_id immediately so the store is always kept up to date.
            const MAX_ATTEMPTS = 10;
            function applyActiveState(attempt) {
                const newElement = document.querySelector(`[data-index="${new_element_id}"]`);
                if (!newElement) {
                    if (attempt >= MAX_ATTEMPTS) {
                        return;
                    }
                    requestAnimationFrame(() => applyActiveState(attempt + 1));
                    return;
                }

                const oldElement = document.querySelector(`[data-index="${old_element_id}"]`);

                if (oldElement && oldElement.dataset) {
                    delete oldElement.dataset.active;
                }

                if (newElement && newElement.dataset) {
                    newElement.dataset.active = "true";
                }
            }

            applyActiveState(0);
            return selected_item;
        }""",
        Output(ids._old_selected_item(MATCH), "data"),
        Input(ids.selected_item(MATCH), "data"),
        State(ids._old_selected_item(MATCH), "data"),
        prevent_initial_call=True,
    )
