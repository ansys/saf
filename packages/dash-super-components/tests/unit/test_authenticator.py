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


"""Unit tests for the Authenticator component."""

# pyright: reportAttributeAccessIssue=false
# pyright: reportOptionalSubscript=false

import copy
from typing import Any

from dash_extensions.enrich import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
import pytest

from ansys.solutions.dash_super_components import Authenticator
from ansys.solutions.dash_super_components.utils._common_colors import _CommonColors as CommonColors
from ansys.solutions.dash_super_components.utils.svg_icons import (
    IconNames,
    create_icon_span,
)

DEFAULT_TEXT_INPUT_ICON = create_icon_span(
    IconNames.MDI_USER,
    size_px=16,
    color=CommonColors.MANTINE_PLACEHOLDER,
)
DEFAULT_PASSWORD_ICON = create_icon_span(
    IconNames.MDI_SECURE,
    size_px=16,
    color=CommonColors.MANTINE_PLACEHOLDER,
)
DEFAULT_BUTTON_ICON = create_icon_span(IconNames.HUGE_ROCKET, size_px=16)


def expected_default_card_props() -> dict[str, Any]:
    """Return the expected default properties for the Authenticator card used in tests."""
    return {
        "w": 500,
        "radius": "md",
        "withBorder": True,
        "shadow": "sm",
    }


def expected_default_items() -> list[dict[str, Any]]:
    """Return the expected default form items for the Authenticator when using defaults."""
    return [
        {
            "type": "TextInput",
            "id": "username",
            "properties": {
                "label": "Username",
                "placeholder": "Enter your username",
                "required": True,
                "leftSection": DEFAULT_TEXT_INPUT_ICON,
            },
        },
        {
            "type": "PasswordInput",
            "id": "password",
            "properties": {
                "label": "Password",
                "placeholder": "Enter your password",
                "required": True,
                "leftSection": DEFAULT_PASSWORD_ICON,
            },
        },
        {
            "type": "Button",
            "id": "connect",
            "properties": {
                "children": "Connect",
                "leftSection": DEFAULT_BUTTON_ICON,
            },
        },
    ]


def get_custom_card_props() -> dict[str, Any]:
    """Return a set of custom card properties used in tests to override defaults."""
    return {"w": 600, "radius": "lg", "withBorder": False, "shadow": "xl"}


def get_custom_items() -> list[dict[str, Any]]:
    """Return a list of custom items (with DashIconify icons) used in tests."""
    return [
        {
            "type": "TextInput",
            "id": "email",
            "properties": {
                "label": "Email",
                "placeholder": "Enter your email",
                "required": False,
                "leftSection": DashIconify(icon="ic:baseline-email"),
            },
        },
        {
            "type": "TextInput",
            "id": "username",
            "properties": {
                "label": "Username",
                "placeholder": "Enter your username",
                "required": True,
                "leftSection": DashIconify(icon="mdi:user"),
            },
        },
        {
            "type": "PasswordInput",
            "id": "password",
            "properties": {
                "label": "Password",
                "placeholder": "Enter your password",
                "required": True,
                "leftSection": DashIconify(icon="mdi:secure"),
            },
        },
    ]


def get_custom_items_with_unsupported_type() -> list[dict[str, Any]]:
    """Return custom items that include an unsupported item type to exercise validation errors."""
    return [
        {
            "type": "TextInput",
            "id": "username",
            "properties": {
                "label": "Username",
                "placeholder": "Enter your username",
                "required": True,
                "leftSection": DashIconify(icon="mdi:user"),
            },
        },
        {
            "type": "Dropdown",  # Unsupported item type
            "id": "role",
            "properties": {
                "label": "Role",
                "options": ["Admin", "User", "Guest"],
                "required": True,
            },
        },
    ]


def test_ids():
    """Verify ID generation for Authenticator subcomponents."""
    aio_id = "dummy-id"

    assert Authenticator.ids.input(aio_id, "username") == {
        "component": "authenticator",
        "subcomponent": "input",
        "aio_id": aio_id,
        "index": "username",
    }
    assert Authenticator.ids.password(aio_id, "password") == {
        "component": "authenticator",
        "subcomponent": "password",
        "aio_id": aio_id,
        "index": "password",
    }
    assert Authenticator.ids.button(aio_id, "connect") == {
        "component": "authenticator",
        "subcomponent": "button",
        "aio_id": aio_id,
        "index": "connect",
    }
    assert Authenticator.ids.input(aio_id, "email") == {
        "component": "authenticator",
        "subcomponent": "input",
        "aio_id": aio_id,
        "index": "email",
    }


def test_authenticator_with_defaults():
    """Test Authenticator with default parameters."""
    authenticator = Authenticator()

    # assert aio_id
    assert authenticator.aio_id
    assert isinstance(authenticator.aio_id, str)

    # Assert rendered structure and merged defaults via public output.
    _assert_default_structure(authenticator)

    another_authenticator = Authenticator()
    assert authenticator.aio_id != another_authenticator.aio_id  # IDs should be unique


def test_authenticator_with_custom_id():
    """Test Authenticator with custom aio_id."""
    aio_id = "custom_aio_id"
    authenticator = Authenticator(aio_id=aio_id)
    assert authenticator.aio_id == aio_id


def test_authenticator_with_custom_card_props():
    """Test Authenticator with custom card_props."""
    card_props = get_custom_card_props()
    authenticator = Authenticator(card_props=card_props)

    # Assert card properties through rendered public output.
    _assert_card_properties(card_props, _rendered_card(authenticator))


def test_authenticator_with_partial_custom_card_props():
    """Test Authenticator with partially custom card_props, partially default card props."""
    card_props = {"withBorder": False, "shadow": "xl"}
    authenticator = Authenticator(card_props=card_props)

    expected_rendered_card_props = {
        **expected_default_card_props(),
        **card_props,
    }
    _assert_card_properties(expected_rendered_card_props, _rendered_card(authenticator))


def test_authenticator_does_not_mutate_input_card_props():
    """Test that Authenticator does not mutate caller-provided card_props in place."""
    card_props = {"withBorder": False, "shadow": "xl"}
    original_card_props = copy.deepcopy(card_props)

    authenticator = Authenticator(card_props=card_props)

    # Input dict must remain unchanged (no defaults injected into caller object).
    assert card_props == original_card_props

    # Rendered output still includes merged defaults.
    expected_rendered_card_props = {
        **expected_default_card_props(),
        **card_props,
    }
    _assert_card_properties(expected_rendered_card_props, _rendered_card(authenticator))


def test_authenticator_with_custom_items_props():
    """Test Authenticator with custom items_props."""
    items = get_custom_items()
    authenticator = Authenticator(items=items)

    _assert_custom_structure(authenticator, items, expected_default_card_props())


def test_authenticator_with_custom_items_unsupported_item_type():
    """Test Authenticator with custom items including an unsupported item type."""
    items = get_custom_items_with_unsupported_type()
    with pytest.raises(ValueError, match="Unsupported item type: Dropdown"):
        _ = Authenticator(items=items)


def test_authenticator_structure_default():
    """Test the structure of the Authenticator component with default parameters."""
    authenticator = Authenticator()

    # assert structure
    _assert_default_structure(authenticator)


def test_authenticator_structure_custom_items():
    """Test the structure of the Authenticator component."""
    items = get_custom_items()
    card_props = get_custom_card_props()
    aio_id = "test_authenticator_aio_id"
    authenticator = Authenticator(items=items, card_props=card_props, aio_id=aio_id)

    # assert structure
    _assert_custom_structure(authenticator, items, card_props)


def test_authenticator_structure_custom_text_item_minimal():
    """Test the structure of the Authenticator component with a minimal custom TextInput item."""
    items: list[dict[str, Any]] = [
        {
            "type": "TextInput",
            "id": "username",
            "properties": {},
        },
    ]
    card_props = get_custom_card_props()
    aio_id = "test_authenticator_aio_id"
    authenticator = Authenticator(items=items, card_props=card_props, aio_id=aio_id)

    # assert structure
    _assert_custom_structure(authenticator, items, card_props)


def test_authenticator_structure_custom_password_item_minimal():
    """Test Authenticator structure with minimal custom PasswordInput item."""
    items: list[dict[str, Any]] = [
        {
            "type": "PasswordInput",
            "id": "password",
            "properties": {},
        },
    ]
    card_props = get_custom_card_props()
    aio_id = "test_authenticator_aio_id"
    authenticator = Authenticator(items=items, card_props=card_props, aio_id=aio_id)

    # assert structure
    _assert_custom_structure(authenticator, items, card_props)


def test_authenticator_structure_custom_button_item_minimal():
    """Test the structure of the Authenticator component with a minimal custom Button item."""
    items: list[dict[str, Any]] = [
        {
            "type": "Button",
            "id": "connect",
            "properties": {},
        },
    ]
    card_props = get_custom_card_props()
    aio_id = "test_authenticator_aio_id"
    authenticator = Authenticator(items=items, card_props=card_props, aio_id=aio_id)

    # assert structure
    _assert_custom_structure(authenticator, items, card_props)


def _expected_item_id(authenticator: Authenticator, item: dict[str, Any]) -> dict[str, Any]:
    """Return the expected dict-style ID for the given item based on its type."""
    if item["type"] == "TextInput":
        return Authenticator.ids.input(authenticator.aio_id, item["id"])
    if item["type"] == "PasswordInput":
        return Authenticator.ids.password(authenticator.aio_id, item["id"])
    if item["type"] == "Button":
        return Authenticator.ids.button(authenticator.aio_id, item["id"])
    raise ValueError(f"Unsupported item type: {item['type']}")


def _rendered_card(authenticator: Authenticator) -> dmc.Card:
    """Return the rendered card from the public Authenticator children tree."""
    inner_div = authenticator.children[0]
    return inner_div.children[0]


def _assert_default_structure(authenticator: Authenticator):
    default_card_props = expected_default_card_props()
    default_items = expected_default_items()
    _assert_generic_structure(authenticator, default_items, default_card_props)


def _assert_custom_structure(authenticator: Authenticator, items: list[dict[str, Any]], card_props: dict[str, Any]):
    _assert_generic_structure(authenticator, items, card_props)


def _assert_generic_structure(
    authenticator: Authenticator,
    items: list[dict[str, Any]],
    card_props: dict[str, Any],
):
    assert isinstance(authenticator, html.Div)
    inner_div = authenticator.children[0]
    assert isinstance(inner_div, html.Div)

    card = inner_div.children[0]
    assert isinstance(card, dmc.Card)
    _assert_card_properties(card_props, card)

    assert card.children is not None
    assert len(card.children) == 2 * len(items)  # items + spacers
    for i, item in enumerate(items):
        div_card_item = card.children[2 * i]
        card_item = div_card_item.children
        spacer = card.children[2 * i + 1]
        assert isinstance(spacer, dmc.Space)
        assert spacer.h == 5

        # assert id and custom properties
        assert card_item.id == _expected_item_id(authenticator, item)
        for prop_key, prop_value in item["properties"].items():
            assert str(getattr(card_item, prop_key)) == str(prop_value)

        # assert common default properties
        if "disabled" not in item["properties"]:
            assert not card_item.disabled
        if "style" not in item["properties"]:
            assert card_item.style == {"width": "100%"}

        # assert type and type-specific default properties
        if item["type"] == "TextInput":
            assert isinstance(card_item, dmc.TextInput)
            _assert_text_input_specific_defaults(item, card_item)

        elif item["type"] == "PasswordInput":
            assert isinstance(card_item, dmc.PasswordInput)
            _assert_password_input_specific_defaults(item, card_item)

        elif item["type"] == "Button":
            assert isinstance(card_item, dmc.Button)
            _assert_button_specific_defaults(item, card_item)


def _assert_card_properties(expected_card_properties: dict[str, Any], card: dmc.Card):
    assert card.w == expected_card_properties["w"]
    assert card.radius == expected_card_properties["radius"]
    assert card.withBorder == expected_card_properties["withBorder"]
    assert card.shadow == expected_card_properties["shadow"]


def _assert_text_input_specific_defaults(item: dict[str, Any], card_item: dmc.TextInput):
    if "label" not in item["properties"]:
        assert card_item.label == "Field"
    if "placeholder" not in item["properties"]:
        assert card_item.placeholder == "Enter your data."
    if "required" not in item["properties"]:
        assert card_item.required


def _assert_password_input_specific_defaults(item: dict[str, Any], card_item: dmc.PasswordInput):
    if "label" not in item["properties"]:
        assert card_item.label == "Password"
    if "placeholder" not in item["properties"]:
        assert card_item.placeholder == "Enter your password."
    if "required" not in item["properties"]:
        assert card_item.required
    if "leftSection" not in item["properties"]:
        icon = card_item.leftSection
        assert isinstance(icon, html.Span)
        assert icon.style is not None
        assert icon.style.get("backgroundColor") == CommonColors.MANTINE_PLACEHOLDER
        assert icon.style.get("width") == "16px"
        assert icon.style.get("height") == "16px"


def _assert_button_specific_defaults(item: dict[str, Any], card_item: dmc.Button):
    if "children" not in item["properties"]:
        assert card_item.children == "Connect"
    if "leftSection" not in item["properties"]:
        icon = card_item.leftSection
        assert isinstance(icon, html.Span)
        assert icon.style is not None
        assert icon.style.get("backgroundColor") == "currentColor"
        assert icon.style.get("width") == "16px"
        assert icon.style.get("height") == "16px"
