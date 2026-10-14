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


"""Input Row Array component."""

from typing import Any, TypeVar
import uuid

from dash.exceptions import PreventUpdate

try:
    # dash-extensions < 2.0.5
    from dash_extensions.enrich import _Wildcard  # pyright: ignore[reportAttributeAccessIssue]
except ImportError:
    # dash-extensions >= 2.0.5
    from dash_extensions.enrich import (
        Wildcard as _Wildcard,  # pyright: ignore[reportAttributeAccessIssue]
    )
from dash_extensions.enrich import MATCH, Input, Output, State, callback, dcc, html
import dash_mantine_components as dmc

from ansys.solutions.dash_super_components.utils.aio_ids import AIOIds
from ansys.solutions.dash_super_components.utils.svg_icons import (
    IconNames,
    create_icon_span,
)

T = TypeVar("T", dmc.TextInput, dmc.NumberInput, dmc.Select)

default_text_input_props = {
    "label": "Field",
    "placeholder": "Enter your data.",
    "required": True,
    "disabled": False,
    "style": {"width": "100%"},
}


default_number_input_props = {
    "label": "Field",
    "placeholder": "Enter your data.",
    "required": True,
    "disabled": False,
    "style": {"width": "100%"},
}


default_select_props = {
    "label": "Field",
    "placeholder": "Enter your data.",
    "required": True,
    "disabled": False,
    "style": {"width": "100%"},
}


class InputRowArray(html.Div):
    """
    A Dash component to create an array of inputs.

    InputRowArray is based on the Dash All-in-One (AIO) component pattern.
    It renders a set of input fields as a single row, and optionally allows
    users to add or remove additional rows dynamically.

    Each field is defined by a dict with the following keys:

    - ``"type"`` *(required)*: ``"TextInput"``, ``"NumberInput"``, or ``"Select"``.
    - ``"id"`` *(required)*: unique string identifier for the field.
    - ``"properties"`` *(required)*: dict of dash mantine component properties.

    Parameters
    ----------
    items : list of dict
        A list of dictionaries defining each input field in a row. Each dict
        must contain ``"type"``, ``"id"``, and ``"properties"`` keys.
        Supported types: ``"TextInput"``, ``"NumberInput"``, ``"Select"``.
    enable_multiple_rows : bool, optional
        If ``True``, add and delete buttons are displayed so that users can
        create or remove extra rows at runtime. Default is ``False``.
    aio_id : str, optional
        The unique identifier for the component. A UUID is generated if not
        provided.
    full_width : bool, optional
        If ``True``, the input row container expands to 100% of the available
        parent width so fields can spread across the row. If ``False``, the
        container keeps its base inline-block width behavior. Default is ``False``.
    """

    class InputRowArrayIds(AIOIds):
        """Provides IDs for the subcomponents of :class:`InputRowArray`."""

        @classmethod
        def _make_id_dict_with_identifier_and_row_index(
            cls,
            subcomponent: str,
            aio_id: str | _Wildcard,
            identifier: str | _Wildcard,
            row_index: int | None | _Wildcard,
        ) -> dict[str, Any]:
            id_dict = cls.make_id_dict("input-row-array", subcomponent, aio_id)
            id_dict["identifier"] = identifier
            id_dict["row_index"] = row_index
            return id_dict

        @classmethod
        def _storage(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the storage component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the storage subcomponent.
            """
            return cls.make_id_dict("input-row-array", "storage", aio_id)

        @classmethod
        def add_button(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the add button component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the add button subcomponent.
            """
            return cls.make_id_dict("input-row-array", "add-button", aio_id)

        @classmethod
        def delete_button(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the delete button component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the delete button subcomponent.
            """
            return cls.make_id_dict("input-row-array", "delete-button", aio_id)

        @classmethod
        def rows(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
            """Return the ID for the rows component.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for the rows subcomponent.
            """
            return cls.make_id_dict("input-row-array", "rows", aio_id)

        @classmethod
        def input(
            cls,
            aio_id: str | _Wildcard,
            item_id: str | _Wildcard,
            row_index: int | None | _Wildcard = None,
        ) -> dict[str, Any]:
            """Return the ID for an input item.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.
            item_id : str or _Wildcard
                The unique identifier of the input item (item["id"]).
            row_index : int, None, or _Wildcard, default: None
                The unique row index. If ``None``, defaults to 0.

            Returns
            -------
            dict[str, Any]
                The unique ID dictionary for an input item subcomponent.
            """
            if row_index is None:
                row_index = 0

            return cls._make_id_dict_with_identifier_and_row_index("input", aio_id, item_id, row_index)

    ids = InputRowArrayIds

    def __init__(
        self,
        items: list[dict[str, Any]],
        enable_multiple_rows: bool = False,
        aio_id: str | None = None,
        full_width: bool = False,
    ):
        self.aio_id = aio_id if aio_id is not None else str(uuid.uuid4())
        rows_style = {"width": "100%"} if full_width else {"display": "inline-block"}

        layout: list[dmc.Group | html.Div | dcc.Store] = []

        if enable_multiple_rows:
            layout.append(
                dmc.Group(
                    [
                        dmc.ActionIcon(
                            create_icon_span(IconNames.MATERIAL_ADD, size_px=20),
                            size="md",
                            variant="filled",
                            id=self.ids.add_button(self.aio_id),
                        ),
                        dmc.ActionIcon(
                            create_icon_span(IconNames.MATERIAL_REMOVE, size_px=20),
                            size="md",
                            variant="filled",
                            id=self.ids.delete_button(self.aio_id),
                        ),
                    ],
                    grow=False,
                    gap="xs",
                    justify="right",
                    align="center",
                ),
            )

        layout.extend(
            [
                html.Div(
                    [
                        dmc.Group(
                            self.generate_components(items, self.aio_id, row_index=0),
                            grow=True,
                            gap="xs",
                            justify="center",
                            align="center",
                        ),
                    ],
                    id=self.ids.rows(self.aio_id),
                    style=rows_style,
                ),
                dcc.Store(
                    id=self.ids._storage(self.aio_id),
                    data={
                        "aio_id": self.aio_id,
                        "enable_multiple_rows": enable_multiple_rows,
                        "items": items,
                    },
                    storage_type="memory",
                ),
            ],
        )

        super().__init__(layout)

    @staticmethod
    @callback(
        Output(ids.delete_button(MATCH), "disabled"),
        Input(ids.rows(MATCH), "children"),
        State(ids._storage(MATCH), "data"),
    )
    def toggle_delete_button(
        rows: list[dmc.Group],
        storage: dict[str, Any],
    ) -> bool:
        """Enable or disable the delete button based on the number of rows."""
        if not storage["enable_multiple_rows"]:
            raise PreventUpdate

        return len(rows) <= 1

    @staticmethod
    @callback(
        Output(ids.rows(MATCH), "children", allow_duplicate=True),
        Input(ids.add_button(MATCH), "n_clicks"),
        State(ids.rows(MATCH), "children"),
        State(ids._storage(MATCH), "data"),
    )
    def add_row(
        clicked: int,
        rows: list[dmc.Group],
        storage: dict[str, Any],
    ) -> list[dmc.Group]:
        """Add a new row to the array."""
        if storage["enable_multiple_rows"] and clicked:
            number_of_rows = len(rows)
            aio_id = storage["aio_id"]
            rows.append(
                dmc.Group(
                    InputRowArray.generate_components(
                        storage["items"],
                        aio_id,
                        row_index=number_of_rows,
                    ),
                    grow=True,
                    gap="xs",
                    justify="center",
                    align="center",
                ),
            )
            return rows
        raise PreventUpdate

    @staticmethod
    @callback(
        Output(ids.rows(MATCH), "children", allow_duplicate=True),
        Input(ids.delete_button(MATCH), "n_clicks"),
        State(ids.rows(MATCH), "children"),
        State(ids._storage(MATCH), "data"),
    )
    def delete_row(
        clicked: int,
        rows: list[dmc.Group],
        storage: dict[str, Any],
    ) -> list[dmc.Group]:
        """Delete the last row from the array."""
        if len(rows) <= 1:
            raise PreventUpdate

        if not storage["enable_multiple_rows"] or not clicked:
            raise PreventUpdate

        del rows[-1]
        return rows

    @classmethod
    def generate_components(
        cls, items: list[dict[str, Any]], aio_id: str, row_index: int = 0
    ) -> list[dmc.TextInput | dmc.NumberInput | dmc.Select]:
        """Generate the components for the InputRowArray."""
        components: list[dmc.TextInput | dmc.NumberInput | dmc.Select] = []
        for item in items:
            component = cls._create_component(aio_id, row_index, item)
            components.append(component)
        return components

    @classmethod
    def _create_component(
        cls, aio_id: str, row_index: int, item: dict[str, Any]
    ) -> dmc.TextInput | dmc.NumberInput | dmc.Select:
        if item["type"] == "TextInput":
            component = dmc.TextInput(
                id=cls.ids.input(aio_id, item["id"], row_index),
                **{**default_text_input_props, **item["properties"]},
            )
        elif item["type"] == "NumberInput":
            component = dmc.NumberInput(
                id=cls.ids.input(aio_id, item["id"], row_index),
                **{**default_number_input_props, **item["properties"]},
            )
        elif item["type"] == "Select":
            component = dmc.Select(
                id=cls.ids.input(aio_id, item["id"], row_index),
                **{**default_select_props, **item["properties"]},
            )
        else:
            raise ValueError(f"Unsupported item type: {item['type']}")
        return component
