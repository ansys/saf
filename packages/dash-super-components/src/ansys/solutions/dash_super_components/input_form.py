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


"""Provide a Dash component for quickly crafting input forms."""

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
from dash.exceptions import PreventUpdate

try:
    # dash-extensions < 2.0.5
    from dash_extensions.enrich import _Wildcard  # pyright: ignore[reportAttributeAccessIssue]
except ImportError:
    # dash-extensions >= 2.0.5
    from dash_extensions.enrich import (
        Wildcard as _Wildcard,  # pyright: ignore[reportAttributeAccessIssue]
    )
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

from ansys.solutions.dash_super_components.utils.aio_ids import AIOIds
from ansys.solutions.dash_super_components.utils.svg_icons import (
    IconNames,
    create_icon_span,
)

DEFAULT_COLUMNS_AND_WIDTHS = {
    "label": 2,
    "fields": 5,
    "unit": 1,
    "description": 3,
    "help": 1,
}

COLUMN_STYLES = {
    "label": {
        "display": "flex",
        "alignItems": "center",
    },
    "unit": {
        "display": "flex",
        "alignItems": "center",
        "justifyContent": "center",
    },
    "description": {
        "display": "flex",
        "alignItems": "center",
    },
    "help": {
        "display": "flex",
        "alignItems": "center",
        "justifyContent": "center",
    },
    "fields": {},
}

SUPPORTED_FIELD_TYPES = [
    "NumberInput",
    "TextInput",
    "PasswordInput",
    "Checkbox",
    "Select",
    "MultiSelect",
    "Switch",
    "Slider",
]


def make_form(
    aio_id: str,
    items: list[dict[str, Any]],
    columns: list[str],
    column_names: list[str],
    custom_column_widths: dict[str, int],
    persistence: bool,
    persistence_type: str,
) -> html.Div:
    """Create the form layout for an :class:`InputForm` component.

    Parameters
    ----------
    aio_id : str
        The unique identifier for the parent ``InputForm`` instance.
    items : list of dict
        Row definitions passed to the ``InputForm``.
    columns : list of str
        Ordered list of column names to include in each row.
    column_names : list of str
        Header labels for each column; pass an empty list to omit headers.
    custom_column_widths : dict[str, int]
        Mapping of column names to custom widths. Columns not present use
        the default widths from :data:`DEFAULT_COLUMNS_AND_WIDTHS`.
    persistence : bool
        Whether to enable persistence for the form fields.
    persistence_type : str
        The type of persistence to use.

    Returns
    -------
    html.Div
        A ``Div`` containing the assembled grid and any help modals.
    """
    column_widths = compute_final_column_widths(columns, custom_column_widths)
    total_column_width = sum(column_widths.values())

    cells: list[dmc.GridCol] = []
    modals: list[dmc.Modal] = []

    # add header row if column names are provided
    if column_names:
        cells.extend(_create_header_cells(columns, column_names, column_widths))

    for row_counter, item in enumerate(items):
        # if the row has an explicit ID, use it as row_index, otherwise use the row_counter:
        row_index = item.get("id", row_counter)
        row_cells, modal = make_row(
            aio_id,
            item,
            columns,
            column_widths,
            row_index,
            persistence,
            persistence_type,
        )
        cells.extend(row_cells)
        modals.append(modal)

    grid = dmc.Grid(cells, gutter="xs", grow=False, columns=total_column_width)

    content = [grid, *modals]

    return html.Div(content)


def _create_header_cells(
    columns: list[str],
    column_names: list[str],
    column_widths: dict[str, int],
) -> list[dmc.GridCol]:
    _validate_column_names(column_names, columns)

    header_cells: list[dmc.GridCol] = []
    for column, column_name in zip(columns, column_names, strict=False):
        header_cells.append(
            dmc.GridCol(
                dmc.Text(column_name, fw=700),  # type: ignore - Dash Mantine Components typing issue
                span=column_widths[column],
            ),
        )

    return header_cells


def make_row(
    aio_id: str,
    item: dict[str, Any],
    columns: list[str],
    column_widths: dict[str, int],
    row_index: int | str,
    persistence: bool,
    persistence_type: str,
) -> tuple[list[dmc.GridCol], dmc.Modal]:
    """Create the grid cells and help modal for a single form row.

    Parameters
    ----------
    aio_id : str
        The unique identifier for the parent ``InputForm`` instance.
    item : dict
        Row definition dictionary with optional keys: ``label``, ``unit``,
        ``description``, ``help``, and required key ``fields``.
    columns : list of str
        Ordered list of column names to render for this row.
    column_widths : dict[str, int]
        Mapping of column names to grid span widths.
    row_index : int or str
        Index used to generate unique subcomponent IDs for this row.
    persistence : bool
        Whether to enable persistence for the form fields in this row.
    persistence_type : str
        The type of persistence to use for the form fields in this row.

    Returns
    -------
    tuple[list of dmc.GridCol, dmc.Modal]
        A tuple of ``(cells, modal)`` where *cells* is the list of grid
        columns for the row and *modal* is the associated help modal.
    """
    cells: list[dmc.GridCol] = []
    for column in columns:
        if column == "label":
            column_content = _create_label_column(aio_id, item, row_index)
        elif column == "unit":
            column_content = _create_unit_column(aio_id, item, row_index)
        elif column == "description":
            column_content = _create_description_column(aio_id, item, row_index)
        elif column == "help":
            column_content = _create_help_column(aio_id, item, row_index)
        elif column == "fields":
            column_content = _create_input_fields_column(aio_id, item, row_index, persistence, persistence_type)
        else:
            raise ValueError(f"Unknown column: {column}")

        cells.append(
            dmc.GridCol(
                column_content,
                span=column_widths[column],
                style=COLUMN_STYLES[column],
            ),
        )

    modal = _create_modal(aio_id, item, row_index)

    return cells, modal


def _create_label_column(
    aio_id: str,
    item: dict[str, Any],
    row_index: str | int,
) -> dmc.Text:
    return dmc.Text(item.get("label"), id=InputForm.ids.label(aio_id, row_index))


def _create_unit_column(
    aio_id: str,
    item: dict[str, Any],
    row_index: str | int,
) -> dmc.Text:
    return dmc.Text(
        (
            dcc.Markdown(
                f"${item['unit']}$",
                mathjax=True,
            )
            if "unit" in item
            else None
        ),
        id=InputForm.ids.unit(aio_id, row_index),
        style={
            "display": "flex",
            "justifyContent": "center",
            "alignItems": "center",
        },
    )


def _create_description_column(
    aio_id: str,
    item: dict[str, Any],
    row_index: str | int,
) -> dmc.Text:
    return dmc.Text(item.get("description"), id=InputForm.ids.description(aio_id, row_index))


def _create_help_column(
    aio_id: str,
    item: dict[str, Any],
    row_index: int | str,
) -> dmc.ActionIcon:
    return dmc.ActionIcon(
        create_icon_span(IconNames.MATERIAL_HELP, size_px=16, color=CommonColors.MANTINE_PRIMARY_COLOR),
        size="xl",
        variant="subtle",
        id=InputForm.ids.help(aio_id, row_index),
        style={
            "display": "flex",
            "visibility": "visible" if item.get("help") else "hidden",
            "textAlign": "center",
        },
    )


def _create_modal(aio_id: str, item: dict[str, Any], row_index: int | str) -> dmc.Modal:
    return dmc.Modal(
        id=InputForm.ids.modal(aio_id, row_index),
        title=item.get("label"),
        zIndex=10000,
        children=item.get("help"),
        size="50%",  # type: ignore - Dash Mantine Components typing issue
        centered=True,
    )


def _create_input_fields_column(
    aio_id: str,
    item: dict[str, Any],
    row_index: int | str,
    persistence: bool,
    persistence_type: str,
) -> html.Div:
    input_fields: list[html.Div] = []

    for field in item["fields"]:
        field_type = field["type"]
        identifier = field["id"]
        div_id = InputForm.ids.field_div(aio_id, field_type, identifier, row_index)
        field_id = InputForm.ids.field(aio_id, field_type, identifier, row_index)

        div_style = {"width": "100%"}
        if "hidden" in field and field["hidden"]:
            div_style["display"] = "none"

        field_properties = {k: copy.deepcopy(v) for k, v in field.items() if k not in ["hidden", "type", "id"]}

        if "persistence" not in field_properties:
            field_properties["persistence"] = persistence
        if "persistence_type" not in field_properties:
            field_properties["persistence_type"] = persistence_type

        if "style" in field_properties:
            if "width" not in field_properties["style"]:
                field_properties["style"]["width"] = "100%"
        else:
            field_properties["style"] = {"width": "100%"}

        input_fields.append(_create_field(field_id, field_type, field_properties, div_id, div_style))

    return html.Div(
        input_fields,
        style={
            "display": "flex",
            "flexDirection": "row",
            "justifyContent": "space-between",
            "alignItems": "center",
            "gap": "10px",
        },
    )


def _create_field(
    field_id: dict[str, Any],
    field_type: str,
    field_properties: dict[str, Any],
    div_id: dict[str, Any],
    div_style: dict[str, Any],
) -> html.Div:
    if field_type == "NumberInput":
        field_content = dmc.NumberInput(id=field_id, **field_properties)
    elif field_type == "TextInput":
        field_content = dmc.TextInput(id=field_id, **field_properties)
    elif field_type == "Checkbox":
        field_content = dmc.Checkbox(id=field_id, **field_properties)
    elif field_type == "Select":
        field_content = dmc.Select(id=field_id, **field_properties)
    elif field_type == "MultiSelect":
        field_content = dmc.MultiSelect(id=field_id, **field_properties)
    elif field_type == "PasswordInput":
        field_content = dmc.PasswordInput(id=field_id, **field_properties)
    elif field_type == "Slider":
        field_content = dmc.Slider(id=field_id, **field_properties)
    elif field_type == "Switch":
        field_content = dmc.Switch(id=field_id, **field_properties)
    else:
        raise ValueError(f"Unsupported field type: {field_type}")

    return html.Div(
        id=div_id,
        children=field_content,
        style=div_style,
    )


class InputForm(html.Div):
    """
    All-in-one component based on Dash Mantine Components to create input forms.

    Each row of the form is defined by a dictionary with the following keys:

    - ``fields`` *(required)*: list of field dicts.  Each field dict must contain
      ``"type"`` and ``"id"`` keys plus any additional properties accepted by the
      underlying Dash Mantine component.  Supported types: ``NumberInput``,
      ``TextInput``, ``PasswordInput``, ``Checkbox``, ``Select``, ``MultiSelect``,
      ``Slider``, ``Switch``.
    - ``label`` *(optional)*: str — label text shown in the label column.
    - ``unit`` *(optional)*: str — LaTeX-rendered unit shown in the unit column.
    - ``description`` *(optional)*: str — description text shown in the description column.
    - ``help`` *(optional)*: Dash component(s), str, or number — content shown in a
      modal when the help icon is clicked.
    - ``id`` *(optional)*: str — explicit row identifier used as the ``row_index`` in
      component IDs.  When omitted, the zero-based row position is used instead.

    UI-side value persistence is disabled by default.  It can be enabled globally for
    all fields via the ``persistence`` and ``persistence_type`` constructor parameters.
    Individual fields can override the global setting by including a ``"persistence"``
    key in their field dict.

    Parameters
    ----------
    items : list of dict
        A list of row definitions.  Each dict must contain a ``"fields"`` key whose
        value is a list of field dicts (each requiring ``"type"`` and ``"id"``).
        Optional row keys: ``"label"``, ``"unit"``, ``"description"``, ``"help"``,
        ``"id"``.  Fields also accept a ``"hidden": True`` key to hide the field on
        initialization.  To override the global persistence setting for an individual
        field, pass ``"persistence": True`` or ``"persistence": False`` in the field
        dict.
    title : str, optional
        Title displayed above the form.
    with_card : bool, optional
        Whether to wrap the form in a :class:`dmc.Card`. Default is ``True``.
    card_props : dict, optional
        Additional properties forwarded to :class:`dmc.Card`.
    title_props : dict, optional
        Additional properties forwarded to the title :class:`html.P` element.
    column_names : list of str, optional
        Header labels for each column, in the same order as ``columns``.  Pass an
        empty list (default) to omit column headers.
    column_widths : dict, optional
        Mapping of column names to integer grid-span widths.  Columns omitted here
        use built-in defaults.
    aio_id : str, optional
        Unique identifier for this component instance.  A UUID is generated when
        not provided.
    columns : list of str, optional
        Ordered list of column names to display.  Supported values: ``"label"``,
        ``"fields"``, ``"unit"``, ``"description"``, ``"help"``.  Defaults to all
        five columns in the order listed.
    persistence : bool, optional
        Whether to enable UI-side persistence for all form fields.  When ``True``,
        user-entered values survive page navigation within the same browser tab.
        Individual fields can override this setting via ``"persistence"`` in the
        field dict.  Default is ``False``.
    persistence_type : str, optional
        The Dash persistence storage type to use when ``persistence`` is ``True``.
        Accepted values: ``"memory"`` (cleared on page reload), ``"session"``
        (cleared when the browser tab is closed), ``"local"`` (persists across
        reloads and browser restarts).  Default is ``"memory"``.
    """

    class InputFormIds(AIOIds):
        """Provides IDs for the subcomponents of :class:`InputForm`."""

        @classmethod
        def _make_id_dict_with_row_index(
            cls, subcomponent: str, aio_id: str | _Wildcard, row_index: str | int | _Wildcard
        ) -> dict[str, Any]:
            id_dict = cls.make_id_dict("input-form", subcomponent, aio_id)
            id_dict["row_index"] = row_index
            return id_dict

        @classmethod
        def _make_id_dict_with_field_type_and_identifier_and_row_index(
            cls,
            subcomponent: str,
            aio_id: str | _Wildcard,
            field_type: str | _Wildcard,
            identifier: str | _Wildcard,
            row_index: str | int | _Wildcard,
        ) -> dict[str, Any]:
            id_dict = cls.make_id_dict("input-form", subcomponent, aio_id)
            id_dict["row_index"] = row_index
            id_dict["field_type"] = field_type
            id_dict["identifier"] = identifier
            return id_dict

        @classmethod
        def label(cls, aio_id: str | _Wildcard, row_index: str | int | _Wildcard) -> dict[str, Any]:
            """
            Return the id for an input form label.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.
            row_index : str, int, or _Wildcard
                The unique row index of the label (row["id"] or row number if
                row["id"] is not present).

            Returns
            -------
            dict[str, Any]
                The unique id dictionary for a label subcomponent of the input form
            """
            return cls._make_id_dict_with_row_index("label", aio_id, row_index)

        @classmethod
        def help(cls, aio_id: str | _Wildcard, row_index: str | int | _Wildcard) -> dict[str, Any]:
            """
            Return the id for an input form help text.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.
            row_index : str, int, or _Wildcard
                The unique row index of the help text (row["id"] or row number if
                row["id"] is not present).

            Returns
            -------
            dict[str, Any]
                The unique id dictionary for a help subcomponent of the input form
            """
            return cls._make_id_dict_with_row_index("help", aio_id, row_index)

        @classmethod
        def unit(cls, aio_id: str | _Wildcard, row_index: str | int | _Wildcard) -> dict[str, Any]:
            """
            Return the id for an input form unit.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.
            row_index : str, int, or _Wildcard
                The unique row index of the unit (row["id"] or row number if
                row["id"] is not present).

            Returns
            -------
            dict[str, Any]
                The unique id dictionary for a unit subcomponent of the input form
            """
            return cls._make_id_dict_with_row_index("unit", aio_id, row_index)

        @classmethod
        def description(cls, aio_id: str | _Wildcard, row_index: str | int | _Wildcard) -> dict[str, Any]:
            """
            Return the id for an input form description.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.
            row_index : str, int, or _Wildcard
                The unique row index of the description (row["id"] or row number if
                row["id"] is not present).

            Returns
            -------
            dict[str, Any]
                The unique id dictionary for a description subcomponent of the input form
            """
            return cls._make_id_dict_with_row_index("description", aio_id, row_index)

        @classmethod
        def modal(cls, aio_id: str | _Wildcard, row_index: str | int | _Wildcard) -> dict[str, Any]:
            """
            Return the id for an input form modal.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.
            row_index : str, int, or _Wildcard
                The unique row index of the modal (row["id"] or row number if
                row["id"] is not present).

            Returns
            -------
            dict[str, Any]
                The unique id dictionary for a modal subcomponent of the input form
            """
            return cls._make_id_dict_with_row_index("modal", aio_id, row_index)

        @classmethod
        def field(
            cls,
            aio_id: str | _Wildcard,
            field_type: str | _Wildcard,
            field_id: str | _Wildcard,
            row_index: str | int | _Wildcard,
        ) -> dict[str, Any]:
            """
            Return the id for an input form field.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.
            field_type : str, or _Wildcard
                The unique type of the field within the form (field["type"]).
            field_id : str, or _Wildcard
                The unique identifier of the field within the form (field["id"]).
            row_index : str, int, or _Wildcard
                The unique row index of the field within the form (row["id"] or row number if
                row["id"] is not present).

            Returns
            -------
            dict[str, Any]
                The unique id dictionary for a field subcomponent of the input form
            """
            return cls._make_id_dict_with_field_type_and_identifier_and_row_index(
                "field", aio_id, field_type, field_id, row_index
            )

        @classmethod
        def field_div(
            cls,
            aio_id: str | _Wildcard,
            field_type: str | _Wildcard,
            field_id: str | _Wildcard,
            row_index: str | int | _Wildcard,
        ) -> dict[str, Any]:
            """
            Return the id for an input form field div.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.
            field_type : str, or _Wildcard
                The unique type of the field within the form (field["type"]).
            field_id : str, or _Wildcard
                The unique identifier of the field within the form (field["id"]).
            row_index : str, int, or _Wildcard
                The unique row index of the field within the form (row["id"] or row number if
                row["id"] is not present).

            Returns
            -------
            dict[str, Any]
                The unique id dictionary for a field div subcomponent of the input form
            """
            return cls._make_id_dict_with_field_type_and_identifier_and_row_index(
                "field-div", aio_id, field_type, field_id, row_index
            )

    ids = InputFormIds

    def __init__(
        self,
        items: list[dict[str, Any]],
        title: str | None = None,
        with_card: bool = True,
        card_props: dict[str, Any] | None = None,
        title_props: dict[str, Any] | None = None,
        column_names: list[str] | None = None,
        column_widths: dict[str, int] | None = None,
        aio_id: str | None = None,
        columns: list[str] | None = None,
        persistence: bool = False,
        persistence_type: str | None = None,
    ):
        # Set default properties
        if card_props is None:
            card_props = {}
        if title_props is None:
            title_props = {}
        if column_names is None:
            column_names = []
        if column_widths is None:
            column_widths = {}
        if aio_id is None:
            aio_id = str(uuid.uuid4())
        if columns is None:
            columns = list(DEFAULT_COLUMNS_AND_WIDTHS.keys())
        if persistence_type is None:
            persistence_type = "memory"

        self.aio_id = aio_id
        self.items = items  # Store reference as-is (items are not mutated in this class)
        self.title = title
        self.column_widths = column_widths  # Store reference as-is (not mutated)
        self.columns = columns  # Store reference as-is (not mutated)
        self.column_names = column_names  # Store reference as-is (not mutated)
        self.persistence = persistence
        self.persistence_type = persistence_type

        default_card_props = {
            "withBorder": True,
            "shadow": "sm",
            "radius": "md",
        }
        card_props = self._populate_with_defaults(card_props, default_card_props)

        default_title_props = {
            "style": {"fontSize": "18px", "fontWeight": "bold"},
        }
        title_props = self._populate_with_defaults(title_props, default_title_props)

        _validate_columns(columns)
        _validate_items(self.items)

        layout = self._make_layout(title, with_card, card_props, title_props)

        super().__init__(
            layout,
        )

    def _populate_with_defaults(
        self, properties_input: dict[str, Any], default_properties: dict[str, Any]
    ) -> dict[str, Any]:
        # make a copy to avoid modifying the original dict
        properties_final = properties_input.copy()
        for key, val in default_properties.items():
            if key not in properties_final:
                properties_final[key] = val
        return properties_final

    def _make_layout(
        self,
        title: str | None,
        with_card: bool,
        card_props: dict[str, Any],
        title_props: dict[str, Any],
    ) -> dmc.Card | html.Div:
        form = make_form(
            self.aio_id,
            self.items,
            self.columns,
            self.column_names,
            self.column_widths,
            self.persistence,
            self.persistence_type,
        )

        content = (
            html.Div(
                [
                    html.P(title, **title_props),
                    html.Hr(className="my-2"),
                    html.Br(),
                    form,
                ],
            )
            if title
            else form
        )

        layout = dmc.Card(content, **card_props) if with_card else content

        return layout

    @staticmethod
    @callback(
        Output(ids.modal(aio_id=MATCH, row_index=MATCH), "opened"),
        Input(ids.help(aio_id=MATCH, row_index=MATCH), "n_clicks"),
        State(ids.modal(aio_id=MATCH, row_index=MATCH), "opened"),
        prevent_initial_call=True,
    )
    def display_help(
        n_clicks: int,
        opened: bool,
    ) -> bool:
        """Display help modal."""
        if not n_clicks:
            raise PreventUpdate

        return not opened

    @staticmethod
    @callback(
        Output(
            ids.field(aio_id=MATCH, field_type="NumberInput", field_id=MATCH, row_index=MATCH),
            "error",
        ),
        Input(
            ids.field(aio_id=MATCH, field_type="NumberInput", field_id=MATCH, row_index=MATCH),
            "value",
        ),
        State(
            ids.field(aio_id=MATCH, field_type="NumberInput", field_id=MATCH, row_index=MATCH),
            "max",
        ),
        State(
            ids.field(aio_id=MATCH, field_type="NumberInput", field_id=MATCH, row_index=MATCH),
            "min",
        ),
        prevent_initial_call=True,
    )
    def validate_input(
        value: float,
        vmax: float | None,
        vmin: float | None,
    ) -> str | NoUpdate | None:
        """Validate number input entry."""
        try:
            float(value)
        except Exception:
            return no_update

        if vmax is not None and float(value) > vmax:
            return f"Expect value to be less than {vmax}."
        if vmin is not None and float(value) < vmin:
            return f"Expect value to be greater than {vmin}."

        return None


def compute_final_column_widths(
    columns: list[str],
    column_widths: dict[str, int],
) -> dict[str, int]:
    """
    Calculate column widths from given and default column widths.

    Parameters
    ----------
    columns : list[str]
        List of column names to be used in the form.
    column_widths : dict[str, int]
        Dictionary mapping column names to their desired widths.
        Missing columns will use default widths.

    Returns
    -------
    dict
        Dictionary containing only the used columns with their calculated widths
    """
    _validate_column_widths(column_widths)

    # Get the width for each used column (custom or default)
    result: dict[str, int] = {}
    for column in columns:
        if column in column_widths:
            result[column] = column_widths[column]
        else:
            result[column] = DEFAULT_COLUMNS_AND_WIDTHS[column]

    return result


def _validate_items(items: list[dict[str, Any]]) -> None:
    """Validate the items definition."""
    for item in items:
        fields = item.get("fields")
        if not fields:
            raise ValueError("Each item must have a fields key.")

        for field in fields:
            field_type = field.get("type", None)

            if field_type is None:
                raise ValueError(
                    f"Each field must have a type key. Supported types are: {', '.join(SUPPORTED_FIELD_TYPES)}.",
                )

            if field_type not in SUPPORTED_FIELD_TYPES:
                raise ValueError(
                    f"Unsupported field type: {field_type}. Supported types are: {', '.join(SUPPORTED_FIELD_TYPES)}.",
                )

            field_id = field.get("id", None)
            if field_id is None:
                raise ValueError("Each field must have an id key.")

            field_id_is_string = isinstance(field_id, str)
            if not field_id_is_string or not field_id:
                raise ValueError("Field id must be a non-empty string.")


def _validate_columns(columns: list[str]) -> None:
    """Validate the columns definition."""
    if not columns:
        raise ValueError("Columns list cannot be empty.")

    if len(set(columns)) != len(columns):
        raise ValueError("Duplicate column names are not allowed in columns list.")

    for column in columns:
        if column not in DEFAULT_COLUMNS_AND_WIDTHS:
            raise ValueError(f"Unsupported column name: {column}")


def _validate_column_names(column_names: list[str], columns: list[str]) -> None:
    """Validate the column names definition."""
    if column_names and len(column_names) != len(columns):
        raise ValueError("Length of column_names must match length of columns.")


def _validate_column_widths(column_widths: dict[str, int]) -> None:
    """Validate the column widths definition."""
    for column in column_widths:
        if column not in DEFAULT_COLUMNS_AND_WIDTHS:
            raise ValueError(f"Unsupported column name: {column}")
    for width in column_widths.values():
        if not isinstance(width, int) or width <= 0:  # type: ignore - explicit type check here
            raise ValueError("Column widths must be positive integers.")
