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


"""Unit tests for the Tree component."""

# pyright: reportAttributeAccessIssue=false
# pyright: reportOptionalSubscript=false

import copy
from typing import Any
from unittest import mock

from dash.exceptions import PreventUpdate
from dash_extensions.enrich import dcc, html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
import pytest

from ansys.solutions.dash_super_components.tree import Tree, TreeIconType
from ansys.solutions.dash_super_components.utils.svg_icons import IconNames, create_base64_svg_src


def test_ids():
    """Verify id generation methods on Tree.ids."""
    tree = Tree(
        items=[],
        aio_id="dummy-id",
    )
    assert tree.aio_id == "dummy-id"

    assert tree.ids.selected_item("dummy-id") == {
        "component": "tree",
        "subcomponent": "selected-item",
        "aio_id": "dummy-id",
    }

    assert tree.ids._old_selected_item("dummy-id") == {
        "component": "tree",
        "subcomponent": "old-selected-item",
        "aio_id": "dummy-id",
    }

    assert tree.ids.navlink_item("dummy-id", "dummy_index") == {
        "component": "tree",
        "subcomponent": "navlink-item",
        "aio_id": "dummy-id",
        "index": "dummy_index",
    }

    assert (
        tree.ids._generate_data_index_for_navlink_item("dummy-id", "dummy_index")
        == "tree_navlink-item_dummy-id_dummy_index"
    )

    assert tree.ids._opened_items("dummy-id") == {
        "component": "tree",
        "subcomponent": "opened-items",
        "aio_id": "dummy-id",
    }

    assert tree.ids._behavior_installed("dummy-id") == {
        "component": "tree",
        "subcomponent": "behavior-installed",
        "aio_id": "dummy-id",
    }

    assert tree.ids._row_selector("dummy-id", "dummy_index") == {
        "component": "tree",
        "subcomponent": "row-selector",
        "aio_id": "dummy-id",
        "index": "dummy_index",
    }

    assert tree.ids._expander_proxy("dummy-id", "dummy_index") == {
        "component": "tree",
        "subcomponent": "expander-proxy",
        "aio_id": "dummy-id",
        "index": "dummy_index",
    }


def test_tree_with_defaults():
    """Test Tree with default parameters."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
        },
    ]

    tree = Tree(items=items)

    assert tree.aio_id
    current_aio_id = tree.aio_id
    assert isinstance(current_aio_id, str)
    assert tree.default_icon is None

    _assert_tree(items, tree, current_aio_id, None, None)


def test_tree_with_custom_id():
    """Test Tree with custom aio_id."""
    aio_id = "custom_aio_id"
    items = [
        {
            "id": "item1",
            "text": "Item 1",
        },
    ]

    tree = Tree(items=items, aio_id=aio_id)

    assert tree.aio_id == aio_id

    _assert_tree(items, tree, aio_id, None, None)


def test_tree_with_custom_default_icon():
    """Test Tree with custom default icon."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
        },
    ]
    custom_default_icon = "material-symbols:house"

    tree = Tree(items=items, default_icon=custom_default_icon)
    current_aio_id = tree.aio_id

    assert tree.default_icon == custom_default_icon

    _assert_tree(items, tree, current_aio_id, custom_default_icon, None)


def test_tree_with_active_item():
    """Test Tree with two items, one selected, flat structure."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
        },
        {
            "id": "item2",
            "text": "Item 2",
        },
    ]
    selected_item = "item2"

    tree = Tree(items=items, selected_item=selected_item)

    _assert_tree(items, tree, tree.aio_id, None, selected_item)


def test_tree_with_full_properties():
    """Test Tree with all properties set."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
            "icon": "material-symbols:folder",
            "expanded": True,
            "disabled": False,
            "description": "This is item 1",
        },
        {
            "id": "item2",
            "text": "Item 2",
            "icon": "material-symbols:file",
            "expanded": False,
            "disabled": True,
            "description": "This is item 2",
        },
    ]

    tree = Tree(
        items=items,
    )

    _assert_tree(
        items,
        tree,
        tree.aio_id,
        None,
        None,
    )


def test_tree_with_nested_items():
    """Test Tree with nested items."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
            "icon": "material-symbols:folder",
            "expanded": True,
            "disabled": False,
            "description": "This is item 1",
            "children": [
                {
                    "id": "item1_1",
                    "text": "Item 1.1",
                    "icon": "material-symbols:file",
                    "expanded": False,
                    "disabled": False,
                    "description": "This is item 1.1",
                    "children": [
                        {
                            "id": "item_1_1_1",
                            "text": "Item 1.1.1",
                            "icon": "material-symbols:check",
                            "expanded": True,
                            "disabled": True,
                            "description": "This is item 1.1.1",
                        },
                    ],
                },
                {
                    "id": "item_1_2",
                    "text": "Item 1.2",
                    "icon": "material-symbols:close",
                    "expanded": False,
                    "disabled": False,
                    "description": "This is item 1.2",
                },
            ],
        },
        {
            "id": "item2",
            "text": "Item 2",
            "icon": "material-symbols:folder",
            "expanded": False,
            "disabled": False,
            "description": "This is item 2",
        },
    ]
    selected_item = "item_1_1_1"
    aio_id = "test_tree_with_nested_items"

    tree = Tree(items=items, selected_item=selected_item, aio_id=aio_id)

    _assert_tree(items, tree, aio_id, None, selected_item)


def test_tree_with_offline_icon_in_asset():
    """Test Tree with offline icon."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
            "icon": "/assets/icons/test.png",
        },
    ]
    tree = Tree(items=items)

    inner_div = _get_tree_content_div(tree)
    nav_link = inner_div.children[0]
    assert isinstance(nav_link, dmc.NavLink)
    icon = nav_link.leftSection
    assert isinstance(icon, html.Span)
    assert icon.className == "tree-icon-mask"
    _assert_mask_image_uses_icon_value(icon, "/assets/icons/test.png")

    _assert_tree(items, tree, tree.aio_id, None, None)


def test_tree_with_offline_icon_base64():
    """Test Tree with offline icon."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
            "icon": create_base64_svg_src(IconNames.CARBON_RETURN),
        },
    ]
    tree = Tree(items=items)

    inner_div = _get_tree_content_div(tree)
    nav_link = inner_div.children[0]
    assert isinstance(nav_link, dmc.NavLink)
    icon = nav_link.leftSection
    assert isinstance(icon, html.Span)
    assert icon.className == "tree-icon-mask"
    _assert_mask_image_uses_icon_value(icon, items[0]["icon"])

    _assert_tree(items, tree, tree.aio_id, None, None)


def test_tree_default_icon_can_be_local_asset_path():
    """Test default_icon supports local image values."""
    items = [{"id": "item1", "text": "Item 1"}]
    tree = Tree(items=items, default_icon="/assets/icons/default.svg")

    inner_div = _get_tree_content_div(tree)
    nav_link = inner_div.children[0]
    assert isinstance(nav_link, dmc.NavLink)
    icon = nav_link.leftSection
    assert isinstance(icon, html.Span)
    assert icon.className == "tree-icon-mask"
    _assert_mask_image_uses_icon_value(icon, "/assets/icons/default.svg")


def test_tree_without_item_icons_and_without_default_icon_renders_no_icons():
    """Tree items render without icons when neither item icons nor default_icon are set."""
    items = [{"id": "item1", "text": "Item 1"}]
    tree = Tree(items=items)

    inner_div = _get_tree_content_div(tree)
    nav_link = inner_div.children[0]
    assert isinstance(nav_link, dmc.NavLink)
    assert nav_link.leftSection is None


def test_tree_with_icon_type_override_iconify():
    """Test icon_type='iconify' forces DashIconify rendering."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
            "icon": "/assets/icons/custom.svg",
            "icon_type": "iconify",
        },
    ]
    tree = Tree(items=items)

    inner_div = _get_tree_content_div(tree)
    nav_link = inner_div.children[0]
    assert isinstance(nav_link, dmc.NavLink)
    icon = nav_link.leftSection
    assert isinstance(icon, DashIconify)
    assert icon.icon == "/assets/icons/custom.svg"
    assert icon.height == 16


def test_tree_with_icon_type_override_local():
    """Test icon_type='local' forces CSS-mask local icon rendering."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
            "icon": "material-symbols:home",
            "icon_type": "local",
        },
    ]
    tree = Tree(items=items)

    inner_div = _get_tree_content_div(tree)
    nav_link = inner_div.children[0]
    assert isinstance(nav_link, dmc.NavLink)
    icon = nav_link.leftSection
    assert isinstance(icon, html.Span)
    assert icon.className == "tree-icon-mask"
    _assert_mask_image_uses_icon_value(icon, "material-symbols:home")


def test_tree_with_icon_type_enum_value():
    """Test Tree accepts TreeIconType enum values for icon_type."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
            "icon": "material-symbols:home",
            "icon_type": TreeIconType.ICONIFY,
        },
    ]
    tree = Tree(items=items)

    inner_div = _get_tree_content_div(tree)
    nav_link = inner_div.children[0]
    assert isinstance(nav_link, dmc.NavLink)
    icon = nav_link.leftSection
    assert isinstance(icon, DashIconify)
    assert icon.icon == "material-symbols:home"
    assert icon.height == 16


def test_tree_with_invalid_icon_type_falls_back_to_auto_with_warning():
    """Unknown icon_type emits warning and uses auto-detection behavior."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
            "icon": "/assets/icons/custom.svg",
            "icon_type": "invalid",
        },
    ]

    with pytest.warns(UserWarning, match="Unknown icon_type=.*Falling back to 'auto'"):
        tree = Tree(items=items)

    inner_div = _get_tree_content_div(tree)
    nav_link = inner_div.children[0]
    assert isinstance(nav_link, dmc.NavLink)
    icon = nav_link.leftSection
    assert isinstance(icon, html.Span)
    assert icon.className == "tree-icon-mask"
    _assert_mask_image_uses_icon_value(icon, "/assets/icons/custom.svg")


def test_tree_with_windows_local_icon_path():
    """Test Windows-style paths are detected as local image values."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
            "icon": r"C:\icons\my_icon.svg",
        },
    ]
    tree = Tree(items=items)

    inner_div = _get_tree_content_div(tree)
    nav_link = inner_div.children[0]
    assert isinstance(nav_link, dmc.NavLink)
    icon = nav_link.leftSection
    assert isinstance(icon, html.Span)
    assert icon.className == "tree-icon-mask"
    _assert_mask_image_uses_icon_value(icon, r"C:\icons\my_icon.svg")


def test_tree_local_icon_renders_mask_icon():
    """When a local icon is provided, it is rendered using CSS mask."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
            "icon": "/assets/icons/custom.svg",
        },
    ]
    tree = Tree(items=items)

    inner_div = _get_tree_content_div(tree)
    nav_link = inner_div.children[0]
    assert isinstance(nav_link, dmc.NavLink)
    icon = nav_link.leftSection
    assert isinstance(icon, html.Span)
    assert icon.className == "tree-icon-mask"
    _assert_mask_image_uses_icon_value(icon, "/assets/icons/custom.svg")


def test_tree_local_icon_with_icon_color_applies_color_style():
    """When icon_color is provided, the local mask icon receives explicit color."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
            "icon": "/assets/icons/custom.svg",
            "icon_color": "red",
        },
    ]
    tree = Tree(items=items)

    inner_div = _get_tree_content_div(tree)
    nav_link = inner_div.children[0]
    icon = nav_link.leftSection
    assert isinstance(icon, html.Span)
    assert icon.style["backgroundColor"] == "red"


def test_tree_iconify_icon_with_icon_color_applies_color_style():
    """When icon_color is provided, iconify icon receives explicit color style."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
            "icon": "material-symbols:light-mode",
            "icon_color": "red",
        }
    ]
    tree = Tree(items=items)

    inner_div = _get_tree_content_div(tree)
    nav_link = inner_div.children[0]
    icon = nav_link.leftSection
    assert isinstance(icon, DashIconify)
    assert icon.style == {"color": "red"}


def test_save_clicked_item_callback_no_trigger_no_initial_selection(
    callback_context_mock: mock.MagicMock,
):
    """save_clicked_item raises PreventUpdate when no item click triggered the callback."""
    callback_context_mock.triggered_id = None

    with pytest.raises(PreventUpdate):
        Tree.save_clicked_item(
            [0],  # dummy
            [0],  # dummy
            {
                "component": "tree",
                "subcomponent": "navlink-item",
                "aio_id": "tree-aio",
                "index": "item-1",
            },
            [],
        )


def test_save_clicked_item_callback_no_trigger_with_initial_selection(
    callback_context_mock: mock.MagicMock,
):
    """save_clicked_item returns the clicked navlink item id."""
    current_selected_item = {
        "component": "tree",
        "subcomponent": "navlink-item",
        "aio_id": "tree_aioid",
        "index": "old_item",
    }
    callback_context_mock.triggered_id = {
        "component": "tree",
        "subcomponent": "navlink-item",
        "aio_id": "tree_aioid",
        "index": "tree_item",
    }

    result = Tree.save_clicked_item(
        [1],  # dummy
        [0],  # dummy
        current_selected_item,
        [],
    )

    assert result == {
        "component": "tree",
        "subcomponent": "navlink-item",
        "aio_id": "tree_aioid",
        "index": "tree_item",
    }


def test_save_clicked_item_callback_triggered_by_tree_item(
    callback_context_mock: mock.MagicMock,
):
    """save_clicked_item raises PreventUpdate when clicked item is already selected."""
    navlink_id = {
        "component": "tree",
        "subcomponent": "navlink-item",
        "aio_id": "tree_aioid",
        "index": "tree_item",
    }
    callback_context_mock.triggered_id = navlink_id

    with pytest.raises(PreventUpdate):
        Tree.save_clicked_item(
            [1],  # dummy
            [0],  # dummy
            navlink_id,
            [],
        )


def test_save_clicked_item_callback_triggered_by_row_selector(
    callback_context_mock: mock.MagicMock,
):
    """Row-selector proxy click resolves to the matching navlink ID."""
    row_selector_id = {
        "component": "tree",
        "subcomponent": "row-selector",
        "aio_id": "tree_aioid",
        "index": "tree_item",
    }
    callback_context_mock.triggered_id = row_selector_id

    result = Tree.save_clicked_item(
        [0],
        [1],
        {
            "component": "tree",
            "subcomponent": "navlink-item",
            "aio_id": "tree_aioid",
            "index": "old_item",
        },
        [row_selector_id],
    )

    assert result == {
        "component": "tree",
        "subcomponent": "navlink-item",
        "aio_id": "tree_aioid",
        "index": "tree_item",
    }


def test_save_clicked_item_callback_row_selector_missing_parts_raises_prevent_update(
    callback_context_mock: mock.MagicMock,
):
    """Invalid row-selector IDs are ignored and do not update selection."""
    row_selector_id_missing_aio_id = {
        "component": "tree",
        "subcomponent": "row-selector",
        "index": "tree_item",
    }
    callback_context_mock.triggered_id = row_selector_id_missing_aio_id

    with pytest.raises(PreventUpdate):
        Tree.save_clicked_item(
            [0],
            [1],
            {
                "component": "tree",
                "subcomponent": "navlink-item",
                "aio_id": "tree_aioid",
                "index": "old_item",
            },
            [row_selector_id_missing_aio_id],
        )


def test_toggle_opened_item_callback_no_trigger_raises_prevent_update(
    callback_context_mock: mock.MagicMock,
):
    """toggle_opened_item raises PreventUpdate when no item click triggered callback."""
    callback_context_mock.triggered_id = None

    with pytest.raises(PreventUpdate):
        Tree.toggle_opened_item([0], ["item-1"])


def test_toggle_opened_item_callback_missing_index_raises_prevent_update(
    callback_context_mock: mock.MagicMock,
):
    """toggle_opened_item raises PreventUpdate when triggered id has no index."""
    callback_context_mock.triggered_id = {
        "component": "tree",
        "subcomponent": "expander-proxy",
        "aio_id": "tree_aioid",
    }

    with pytest.raises(PreventUpdate):
        Tree.toggle_opened_item([1], ["item-1"])


@pytest.mark.parametrize(
    ("opened_items", "triggered_id", "expected"),
    [
        (["item-1", "item-3"], {"index": "item-2"}, ["item-1", "item-2", "item-3"]),
        (["item-1", "item-2"], {"index": "item-2"}, ["item-1"]),
        (None, {"index": "item-2"}, ["item-2"]),
    ],
)
def test_toggle_opened_item_callback_toggles_and_sorts(
    callback_context_mock: mock.MagicMock,
    opened_items: list[str] | None,
    triggered_id: dict[str, str],
    expected: list[str],
):
    """toggle_opened_item updates opened IDs by toggling triggered index and sorting."""
    callback_context_mock.triggered_id = triggered_id
    assert Tree.toggle_opened_item([1], opened_items) == expected


def test_sync_opened_items_applies_flags_and_expander_classes():
    """sync_opened_items maps opened ids to navlink opened flags and expander classes."""
    all_navlink_ids = [
        Tree.ids.navlink_item("aio-id", "item-1"),
        Tree.ids.navlink_item("aio-id", "item-2"),
        Tree.ids.navlink_item("aio-id", "item-3"),
    ]
    all_expander_ids = [
        Tree.ids._expander("aio-id", "item-2"),
        Tree.ids._expander("aio-id", "item-3"),
    ]

    opened_flags, expander_classes = Tree.sync_opened_items(
        opened_items=["item-2"],
        all_navlink_ids=all_navlink_ids,
        all_expander_ids=all_expander_ids,
    )

    assert opened_flags == [False, True, False]
    assert expander_classes == ["tree-expander-control tree-expander-open", "tree-expander-control"]


def test_tree_with_default_styles():
    """Test Tree applies default label color when no styles are provided."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
        },
    ]
    tree = Tree(items=items)

    # assert styles explicitly
    inner_div = _get_tree_content_div(tree)
    nav_link = inner_div.children[0]
    assert isinstance(nav_link, dmc.NavLink)
    assert nav_link.styles == {"label": {"color": "var(--mantine-color-text)"}}

    _assert_tree(items, tree, tree.aio_id, None, None)


def test_tree_with_empty_styles():
    """Test Tree applies default label color when styles dict is empty."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
            "styles": {},
        },
    ]
    tree = Tree(items=items)

    # assert styles explicitly
    inner_div = _get_tree_content_div(tree)
    nav_link = inner_div.children[0]
    assert isinstance(nav_link, dmc.NavLink)
    assert nav_link.styles == {"label": {"color": "var(--mantine-color-text)"}}

    _assert_tree(items, tree, tree.aio_id, None, None)


def test_tree_with_label_styles_no_color():
    """Test Tree applies default label color when label styles exist but color is None."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
            "styles": {"label": {"color": None}},
        },
    ]
    tree = Tree(items=items)

    # assert styles explicitly
    inner_div = _get_tree_content_div(tree)
    nav_link = inner_div.children[0]
    assert isinstance(nav_link, dmc.NavLink)
    assert nav_link.styles == {"label": {"color": "var(--mantine-color-text)"}}

    _assert_tree(items, tree, tree.aio_id, None, None)


def test_tree_with_custom_label_color():
    """Test Tree preserves custom label color when explicitly provided."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
            "styles": {"label": {"color": "#ff0000"}},
        },
    ]
    tree = Tree(items=items)

    # assert styles explicitly
    inner_div = _get_tree_content_div(tree)
    nav_link = inner_div.children[0]
    assert isinstance(nav_link, dmc.NavLink)
    assert nav_link.styles == {"label": {"color": "#ff0000"}}

    _assert_tree(items, tree, tree.aio_id, None, None)


def test_tree_with_custom_styles_other_properties():
    """Test Tree preserves additional style properties alongside the default label color."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
            "styles": {"root": {"backgroundColor": "#f0f0f0"}},
        },
    ]
    tree = Tree(items=items)

    # assert styles explicitly
    inner_div = _get_tree_content_div(tree)
    nav_link = inner_div.children[0]
    assert isinstance(nav_link, dmc.NavLink)
    assert nav_link.styles == {
        "root": {"backgroundColor": "#f0f0f0"},
        "label": {"color": "var(--mantine-color-text)"},
    }

    _assert_tree(items, tree, tree.aio_id, None, None)


def test_tree_with_custom_styles_on_nested_items():
    """Test Tree applies styles correctly to nested items."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
            "styles": {"label": {"color": "#ff0000"}},
            "children": [
                {
                    "id": "item1_1",
                    "text": "Item 1.1",
                    "styles": {"label": {"color": "#00ff00"}},
                },
                {
                    "id": "item1_2",
                    "text": "Item 1.2",
                    # no styles: should get default
                },
            ],
        },
    ]
    tree = Tree(items=items)

    # assert styles explicitly
    inner_div = _get_tree_content_div(tree)
    parent_nav_link = inner_div.children[0]
    assert isinstance(parent_nav_link, dmc.NavLink)
    assert parent_nav_link.styles == {"label": {"color": "#ff0000"}}

    child_nav_link_1 = parent_nav_link.children[0]
    assert isinstance(child_nav_link_1, dmc.NavLink)
    assert child_nav_link_1.styles == {"label": {"color": "#00ff00"}}

    child_nav_link_2 = parent_nav_link.children[1]
    assert isinstance(child_nav_link_2, dmc.NavLink)
    assert child_nav_link_2.styles == {"label": {"color": "var(--mantine-color-text)"}}

    _assert_tree(items, tree, tree.aio_id, None, None)


def test_tree_with_label_styles_other_properties_no_color():
    """Test Tree preserves other label properties when color is not set."""
    items = [
        {
            "id": "item1",
            "text": "Item 1",
            "styles": {"label": {"fontWeight": "bold"}},
        },
    ]
    tree = Tree(items=items)

    # assert styles explicitly
    inner_div = _get_tree_content_div(tree)
    nav_link = inner_div.children[0]
    assert isinstance(nav_link, dmc.NavLink)
    assert nav_link.styles == {"label": {"fontWeight": "bold", "color": "var(--mantine-color-text)"}}

    _assert_tree(items, tree, tree.aio_id, None, None)


def _assert_tree(
    items_input: list[dict],
    tree: html.Div,
    aio_id: str,
    default_icon: str | None,
    active_item_id: str | None,
):
    assert isinstance(tree, html.Div)
    assert tree.children is not None
    assert len(tree.children) == 7

    _assert_tree_style(tree)
    _assert_selected_item_storage(tree, aio_id, active_item_id)
    _assert_old_selected_item_storage(tree, aio_id, active_item_id)
    _assert_opened_items_storage(tree, items_input, aio_id)
    _assert_behavior_installed_storage(tree, aio_id)
    _assert_hidden_proxy_container(tree, items_input, aio_id)
    _assert_tree_structure(
        items_input,
        tree,
        aio_id,
        default_icon,
        active_item_id,
    )


def _assert_tree_style(tree: html.Div):
    style_link = tree.children[0]
    assert isinstance(style_link, html.Link)
    assert style_link.rel == "stylesheet"
    assert style_link.href == "/super-components/tree-styles.css"


def _assert_selected_item_storage(tree: html.Div, aio_id: str, active_item_id: str | None):
    selected_item_store = tree.children[1]
    assert isinstance(selected_item_store, dcc.Store)
    assert selected_item_store.id == Tree.ids.selected_item(aio_id)
    assert selected_item_store.storage_type == "memory"
    assert selected_item_store.data == Tree.ids.navlink_item(aio_id, active_item_id)


def _assert_old_selected_item_storage(tree: html.Div, aio_id: str, active_item_id: str | None):
    old_selected_item_store = tree.children[2]
    assert isinstance(old_selected_item_store, dcc.Store)
    assert old_selected_item_store.id == Tree.ids._old_selected_item(aio_id)
    assert old_selected_item_store.storage_type == "memory"
    assert old_selected_item_store.data == Tree.ids.navlink_item(aio_id, active_item_id)


def _assert_opened_items_storage(tree: html.Div, items_input: list[dict[str, Any]], aio_id: str):
    opened_items_store = tree.children[3]
    assert isinstance(opened_items_store, dcc.Store)
    assert opened_items_store.id == Tree.ids._opened_items(aio_id)
    assert opened_items_store.storage_type == "memory"

    expected_opened_ids, _, _ = Tree._collect_tree_item_metadata(items_input)
    assert opened_items_store.data == sorted(expected_opened_ids)


def _assert_hidden_proxy_container(tree: html.Div, items_input: list[dict[str, Any]], aio_id: str):
    proxy_container = tree.children[5]
    assert isinstance(proxy_container, html.Div)
    assert proxy_container.className == "tree-row-selector-container"
    assert proxy_container.style == {"display": "none"}

    _, all_item_ids, parent_item_ids = Tree._collect_tree_item_metadata(items_input)
    proxy_children = proxy_container.children
    assert isinstance(proxy_children, list)

    expected_count = len(all_item_ids) + len(parent_item_ids)
    assert len(proxy_children) == expected_count

    for item_id in all_item_ids:
        matching_buttons = [
            child
            for child in proxy_children
            if isinstance(child, html.Button) and child.id == Tree.ids._row_selector(aio_id, item_id)
        ]
        assert len(matching_buttons) == 1
        button = matching_buttons[0]
        assert button.className == "tree-row-selector-proxy"
        assert button.n_clicks == 0
        assert button.title == Tree.ids._generate_data_index_for_row_selector(aio_id, item_id)

    for item_id in parent_item_ids:
        matching_buttons = [
            child
            for child in proxy_children
            if isinstance(child, html.Button) and child.id == Tree.ids._expander_proxy(aio_id, item_id)
        ]
        assert len(matching_buttons) == 1
        button = matching_buttons[0]
        assert button.className == "tree-expander-proxy"
        assert button.n_clicks == 0
        assert button.title == Tree.ids._generate_data_index_for_expander_proxy(aio_id, item_id)


def _assert_tree_structure(
    items_input: list[dict],
    tree: html.Div,
    aio_id: str,
    default_icon: str | None,
    active_item_id: str | None,
):
    inner_div = _get_tree_content_div(tree)
    assert isinstance(inner_div, html.Div)
    tree_items = inner_div.children
    assert tree_items is not None

    _assert_tree_items(
        items_input,
        aio_id,
        default_icon,
        active_item_id,
        tree_items,
    )


def _assert_behavior_installed_storage(tree: html.Div, aio_id: str):
    behavior_installed_store = tree.children[4]
    assert isinstance(behavior_installed_store, dcc.Store)
    assert behavior_installed_store.id == Tree.ids._behavior_installed(aio_id)
    assert behavior_installed_store.storage_type == "memory"
    assert behavior_installed_store.data is False


def _assert_tree_items(
    items_input: list[dict],
    aio_id: str,
    default_icon: str | None,
    active_item_id: str | None,
    tree_items: list[Any],
):
    assert len(tree_items) == len(items_input)

    for i, item_input in enumerate(items_input):
        tree_item = tree_items[i]
        expected_item_id = item_input["id"]
        expected_label = item_input["text"]
        expected_active = False
        if active_item_id:
            expected_active = active_item_id == expected_item_id
        expected_disabled = item_input.get("disabled", False)
        expected_item_description = item_input.get("description", "")
        expected_opened = item_input.get("expanded", False)

        assert isinstance(tree_item, dmc.NavLink)
        assert tree_item.id == Tree.ids.navlink_item(aio_id, expected_item_id)
        assert tree_item.attributes == {
            "root": {
                "data-index": Tree.ids._generate_data_index_for_navlink_item(aio_id, expected_item_id),
                "data-aio-id": aio_id,
                "data-item-index": expected_item_id,
            }
        }
        assert tree_item.label == expected_label
        _assert_icon(default_icon, item_input, tree_item)

        assert tree_item.active == expected_active
        assert tree_item.disabled == expected_disabled
        assert tree_item.description == expected_item_description
        assert tree_item.opened == expected_opened
        assert tree_item.childrenOffset == 28

        expected_has_children = bool(item_input.get("children"))
        expected_right_section_class = (
            "tree-expander-control tree-expander-open"
            if expected_has_children and expected_opened
            else "tree-expander-control"
        )
        if expected_has_children:
            right_section = tree_item.rightSection
            assert isinstance(right_section, html.Span)
            assert right_section.id == Tree.ids._expander(aio_id, expected_item_id)
            assert right_section.className == expected_right_section_class
            assert right_section.n_clicks == 0
        else:
            assert tree_item.rightSection is None

        expected_styles: dict[str, Any] = copy.deepcopy(item_input.get("styles", {}))
        expected_styles.setdefault("label", {})
        color = expected_styles["label"].setdefault("color", "var(--mantine-color-text)")
        if color is None:
            expected_styles["label"]["color"] = "var(--mantine-color-text)"
        assert tree_item.styles == expected_styles

        # recursively check children
        if "children" in item_input:
            assert tree_item.children is not None
            _assert_tree_items(
                item_input["children"],
                aio_id,
                default_icon,
                active_item_id,
                tree_item.children,
            )
        else:
            assert tree_item.children is None


def _assert_icon(
    default_icon: str | None,
    item_input: dict[str, Any],
    tree_item: dmc.NavLink,
):
    icon_slot = tree_item.leftSection
    item_icon_value = item_input.get("icon")

    expected_icon_value: str | None = default_icon
    if item_icon_value not in (None, ""):
        expected_icon_value = item_icon_value

    if expected_icon_value in (None, ""):
        assert icon_slot is None
        expected_img = False
    else:
        icon_type = item_input.get("icon_type", "auto")
        expected_img = False
        if icon_type == "local":
            expected_img = True
        elif icon_type == "iconify":
            expected_img = False
        else:
            expected_img = Tree._is_local_icon_value(expected_icon_value)

    if expected_icon_value in (None, ""):
        pass
    else:
        # Icons now always render as a single component.
        assert icon_slot is not None
        icon_component = icon_slot
        if expected_img:
            assert isinstance(icon_component, html.Span)
            assert icon_component.className == "tree-icon-mask"
            _assert_mask_image_uses_icon_value(icon_component, expected_icon_value)
        else:
            assert isinstance(icon_component, DashIconify)
            assert icon_component.icon == expected_icon_value
            assert icon_component.height == 16


def _assert_mask_image_uses_icon_value(icon_component: html.Span, expected_icon_value: str):
    """Assert a mask span encodes an icon value into both CSS mask properties."""
    assert icon_component.style is not None
    mask_image = icon_component.style["maskImage"]
    webkit_mask_image = icon_component.style["WebkitMaskImage"]

    assert mask_image == webkit_mask_image
    assert mask_image.startswith('url("')
    assert mask_image.endswith('")')

    escaped_icon_value = expected_icon_value.replace("\\", "\\\\").replace('"', '\\"')
    assert escaped_icon_value in mask_image


def _get_tree_content_div(tree: html.Div) -> html.Div:
    """Return the main tree content container from the component root."""
    content_div = tree.children[6]
    assert isinstance(content_div, html.Div)
    return content_div


# ---------------------------------------------------------------------------
# Tests for Tree.ids.get_index_from_navlink_item_id
# ---------------------------------------------------------------------------


def test_get_index_from_navlink_item_id_valid():
    """Returns the index value from a valid navlink item ID dict."""
    valid_id = Tree.ids.navlink_item("my-aio", "my-index")
    assert Tree.ids.get_index_from_navlink_item_id(valid_id) == "my-index"


def test_get_index_from_navlink_item_id_wrong_component():
    """Raises ValueError when the 'component' value does not match."""
    bad_id = Tree.ids.navlink_item("my-aio", "my-index")
    bad_id["component"] = "wrong-component"
    with pytest.raises(ValueError, match="component"):
        Tree.ids.get_index_from_navlink_item_id(bad_id)


def test_get_index_from_navlink_item_id_wrong_subcomponent():
    """Raises ValueError when the 'subcomponent' value does not match."""
    bad_id = Tree.ids.navlink_item("my-aio", "my-index")
    bad_id["subcomponent"] = "wrong-subcomponent"
    with pytest.raises(ValueError, match="subcomponent"):
        Tree.ids.get_index_from_navlink_item_id(bad_id)


def test_get_index_from_navlink_item_id_missing_key():
    """Raises ValueError when a required key is absent from the dict."""
    bad_id = Tree.ids.navlink_item("my-aio", "my-index")
    del bad_id["component"]
    with pytest.raises(ValueError, match="component"):
        Tree.ids.get_index_from_navlink_item_id(bad_id)


def test_get_index_from_navlink_item_id_missing_index():
    """Raises ValueError when the index value is falsy (None or empty string)."""
    bad_id = Tree.ids.navlink_item("my-aio", None)
    with pytest.raises(ValueError, match="Index not found"):
        Tree.ids.get_index_from_navlink_item_id(bad_id)

    bad_id_empty = Tree.ids.navlink_item("my-aio", "")
    with pytest.raises(ValueError, match="Index not found"):
        Tree.ids.get_index_from_navlink_item_id(bad_id_empty)


def test_get_index_from_navlink_item_id_extra_keys_ignored():
    """Extra keys in the dict beyond the navlink_item schema do not cause errors."""
    valid_id = Tree.ids.navlink_item("my-aio", "my-index")
    valid_id["unexpected_key"] = "unexpected_value"
    assert Tree.ids.get_index_from_navlink_item_id(valid_id) == "my-index"
