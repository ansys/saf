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


"""Provide a Dash component for crafting an authentication form."""

import copy
from typing import Any, TypeVar
import uuid

from ansys.solutions.dash_super_components.utils._common_colors import _CommonColors as CommonColors

try:
    # dash-extensions < 2.0.5
    from dash_extensions.enrich import _Wildcard  # pyright: ignore[reportAttributeAccessIssue]
except ImportError:
    # dash-extensions >= 2.0.5
    from dash_extensions.enrich import (
        Wildcard as _Wildcard,  # pyright: ignore[reportAttributeAccessIssue]
    )
from dash_extensions.enrich import html
import dash_mantine_components as dmc

from ansys.solutions.dash_super_components.utils.aio_ids import AIOIds
from ansys.solutions.dash_super_components.utils.svg_icons import (
    IconNames,
    create_icon_span,
)

T = TypeVar("T", dmc.TextInput, dmc.PasswordInput, dmc.Button)


class Authenticator(html.Div):
    """
    A Dash component for crafting an authentication form.

    Authenticator is based on the Dash All-in-One (AIO) component pattern. It
    renders a vertical stack of ``TextInput``, ``PasswordInput``, and ``Button``
    items inside a :class:`dmc.Card`.

    When ``items`` is omitted or empty, a default form is rendered with a
    username text input (id ``"username"``), a password input (id ``"password"``),
    and a "Connect" button (id ``"connect"``).

    Each item dict must contain the following keys:

    - ``"type"`` *(required)*: ``"TextInput"``, ``"PasswordInput"``, or ``"Button"``.
    - ``"id"`` *(required)*: unique string identifier for the item.
    - ``"properties"`` *(required)*: dict of dash mantine component properties.

    Parameters
    ----------
    items : list of dict, optional
        Items to render in the form. Each dict must contain ``"type"``, ``"id"``,
        and ``"properties"`` keys. When omitted or empty, the default form
        (username, password, connect button) is rendered.
    card_props : dict, optional
        Properties forwarded to the wrapping :class:`dmc.Card`.
    aio_id : str, optional
        Unique identifier for this component instance. A UUID is generated when
        not provided.
    """

    class AuthenticatorIds(AIOIds):
        """Provides IDs for the subcomponents of :class:`Authenticator`."""

        @classmethod
        def _make_id_dict_with_index(
            cls, subcomponent: str, aio_id: str | _Wildcard, index: str | _Wildcard
        ) -> dict[str, Any]:
            id_dict = cls.make_id_dict("authenticator", subcomponent, aio_id)
            id_dict["index"] = index
            return id_dict

        @classmethod
        def input(cls, aio_id: str | _Wildcard, item_id: str | _Wildcard) -> dict[str, Any]:
            """
            Return the id for an input item.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.
            item_id : str or _Wildcard
                The unique identifier of the input item (item["id"]).

            Returns
            -------
            dict[str, Any]
                The unique id dictionary for an input item of the Authenticator
            """
            return cls._make_id_dict_with_index("input", aio_id, item_id)

        @classmethod
        def password(cls, aio_id: str | _Wildcard, item_id: str | _Wildcard) -> dict[str, Any]:
            """
            Return the id for a password item.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.
            item_id : str or _Wildcard
                The unique identifier of the password item (item["id"]).

            Returns
            -------
            dict[str, Any]
                The unique id dictionary for a password item of the Authenticator
            """
            return cls._make_id_dict_with_index("password", aio_id, item_id)

        @classmethod
        def button(cls, aio_id: str | _Wildcard, item_id: str | _Wildcard) -> dict[str, Any]:
            """
            Return the id for a button item.

            Parameters
            ----------
            aio_id : str or _Wildcard
                The component's unique identifier.
            item_id : str or _Wildcard
                The unique identifier of the button item (item["id"]).

            Returns
            -------
            dict[str, Any]
                The unique id dictionary for a button item of the Authenticator
            """
            return cls._make_id_dict_with_index("button", aio_id, item_id)

    ids = AuthenticatorIds

    def __init__(
        self,
        items: list[dict[str, Any]] | None = None,
        card_props: dict[str, Any] | None = None,
        aio_id: str | None = None,
    ):
        if card_props is None:
            card_props = {}
        if items is None:
            items = []

        self.items = items
        self._card_props = copy.deepcopy(card_props)
        self.aio_id = aio_id if aio_id is not None else str(uuid.uuid4())
        self._default_card_props = {
            "withBorder": True,
            "shadow": "sm",
            "radius": "md",
            "w": 500,
        }
        self._default_button_props = {
            "children": "Connect",
            "disabled": False,
            "leftSection": create_icon_span(IconNames.HUGE_ROCKET, size_px=16),
            "style": {"width": "100%"},
        }
        self._default_text_input_props = {
            "label": "Field",
            "placeholder": "Enter your data.",
            "required": True,
            "disabled": False,
            "style": {"width": "100%"},
        }
        self._default_password_input_props = {
            "label": "Password",
            "placeholder": "Enter your password.",
            "required": True,
            "disabled": False,
            "leftSection": create_icon_span(IconNames.MDI_SECURE, size_px=16, color=CommonColors.MANTINE_PLACEHOLDER),
            "style": {"width": "100%"},
        }

        if not len(self.items):
            self.items = [
                {
                    "type": "TextInput",
                    "id": "username",
                    "properties": {
                        "label": "Username",
                        "placeholder": "Enter your username",
                        "required": True,
                        "leftSection": create_icon_span(
                            IconNames.MDI_USER, size_px=16, color=CommonColors.MANTINE_PLACEHOLDER
                        ),
                    },
                },
                {
                    "type": "PasswordInput",
                    "id": "password",
                    "properties": {
                        "label": "Password",
                        "placeholder": "Enter your password",
                        "required": True,
                        "leftSection": create_icon_span(
                            IconNames.MDI_SECURE, size_px=16, color=CommonColors.MANTINE_PLACEHOLDER
                        ),
                    },
                },
                {
                    "type": "Button",
                    "id": "connect",
                    "properties": {
                        "children": "Connect",
                        "leftSection": create_icon_span(IconNames.HUGE_ROCKET, size_px=16),
                    },
                    "variant": "filled",
                },
            ]

        for prop, value in self._default_card_props.items():
            if prop not in self._card_props:
                self._card_props[prop] = value

        super().__init__(
            [
                html.Div(
                    [
                        dmc.Card(self._generate_form(), **self._card_props),
                    ],
                ),
            ],
        )

    def _generate_form(self) -> list[html.Div | dmc.Space]:
        """Generate the components of the form."""
        children: list[html.Div | dmc.Space] = []
        for item in self.items:
            children.append(
                html.Div(
                    self._create_component(item),
                    style={
                        "display": "flex",
                        "justifyContent": "center",
                        "align-items": "center",
                    },
                ),
            )
            children.append(dmc.Space(h=5))
        return children

    def _create_component(self, item: dict[str, Any]) -> dmc.TextInput | dmc.PasswordInput | dmc.Button:
        if item["type"] == "TextInput":
            component = dmc.TextInput(
                id=self.ids.input(self.aio_id, item["id"]),
                **{**self._default_text_input_props, **item["properties"]},
            )
        elif item["type"] == "PasswordInput":
            component = dmc.PasswordInput(
                id=self.ids.password(self.aio_id, item["id"]),
                **{**self._default_password_input_props, **item["properties"]},
            )
        elif item["type"] == "Button":
            component = dmc.Button(
                id=self.ids.button(self.aio_id, item["id"]),
                **{**self._default_button_props, **item["properties"]},
            )
        else:
            raise ValueError(f"Unsupported item type: {item['type']}")
        return component
