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


"""Unit tests for the FolderSelector component and its helpers."""

# pyright: reportAttributeAccessIssue=false
# pyright: reportOptionalSubscript=false

import copy
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import uuid

try:
    import tkinter
except ImportError:

    class _TclError(Exception):
        pass

    tkinter = SimpleNamespace(TclError=_TclError)

try:
    # dash >=3.2.0
    from dash import NoUpdate
except ImportError:
    # dash >=2.18.2, <3.2.0
    from dash._callback import NoUpdate  # pyright: ignore[reportPrivateImportUsage]
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import dcc, html, no_update
import dash_mantine_components as dmc
import pytest
from pytest_mock import MockerFixture

import ansys.solutions.dash_super_components.folder_selector as folder_selector_module
from ansys.solutions.dash_super_components.folder_selector import FolderSelector, FolderSelectorMode
from ansys.solutions.dash_super_components.tree import Tree
from ansys.solutions.dash_super_components.utils import config as dsc_config
from ansys.solutions.dash_super_components.utils._common_colors import _CommonColors as CommonColors
from ansys.solutions.dash_super_components.utils.path_validator import PathValidator
from ansys.solutions.dash_super_components.utils.svg_icons import IconNames, create_base64_svg_src


@pytest.fixture(autouse=True)
def reset_folder_selector_config(mocker: MockerFixture):
    """Reset shared FolderSelector-related config around each test.

    Most tests in this module exercise bootstrap behavior, so they opt in by default.
    """
    dsc_config._config.notification_container_id = dsc_config._DEFAULT_NOTIFICATION_CONTAINER_ID
    dsc_config._config.enable_beta_features = True
    if not folder_selector_module.TKINTER_AVAILABLE:
        mocker.patch.object(
            folder_selector_module,
            "tkinter",
            new=SimpleNamespace(TclError=tkinter.TclError, Tk=None),
        )
        mocker.patch.object(
            folder_selector_module,
            "filedialog",
            new=SimpleNamespace(askdirectory=None),
        )
        mocker.patch.object(folder_selector_module, "TKINTER_AVAILABLE", new=True)
    yield
    dsc_config._config.notification_container_id = dsc_config._DEFAULT_NOTIFICATION_CONTAINER_ID
    dsc_config._config.enable_beta_features = dsc_config._DEFAULT_ENABLE_BETA_FEATURES


EXPECTED_BROWSE_BUTTON_ICON_SRC = create_base64_svg_src(IconNames.MDI_FOLDER_SEARCH, "#000")
EXPECTED_CLEAR_BUTTON_ICON_SRC = create_base64_svg_src(IconNames.MATERIAL_DELETE, "#000")


def _bootstrap_settings(max_path_length: int | None = None) -> dict[str, Any]:
    return {
        "topmost": True,
        "max_path_length": max_path_length or PathValidator.max_path_length(),
        "default_path": None,
        "mode": FolderSelectorMode.BOOTSTRAP,
        "browse_from": "/root_node",
        "max_tree_depth": 5,
        "max_children_per_node": 500,
    }


"""----------------------------------------------------------------------------------------------"""

"""----------------------------------------------------------------------------------------------"""
"""Initialization Tests"""
"""----------------------------------------------------------------------------------------------"""


def test_folder_selector_ids():
    """Verify ID generation for FolderSelector subcomponents."""
    folder_selector = FolderSelector(aio_id="test_aio_id")

    assert folder_selector.aio_id == "test_aio_id"

    assert folder_selector.ids._settings("test_aio_id") == {
        "component": "folder-selector",
        "subcomponent": "settings",
        "aio_id": "test_aio_id",
    }

    assert folder_selector.ids._folder_selector_is_open("test_aio_id") == {
        "component": "folder-selector",
        "subcomponent": "folder-selector-is-open",
        "aio_id": "test_aio_id",
    }

    assert folder_selector.ids._folder_selector_modal("test_aio_id") == {
        "component": "folder-selector",
        "subcomponent": "folder-selector-modal",
        "aio_id": "test_aio_id",
    }

    assert folder_selector.ids._folder_selector_modal_done_button("test_aio_id") == {
        "component": "folder-selector",
        "subcomponent": "folder-selector-modal-done-button",
        "aio_id": "test_aio_id",
    }

    assert folder_selector.ids._folders_structure("test_aio_id") == {
        "component": "folder-selector",
        "subcomponent": "folders-structure",
        "aio_id": "test_aio_id",
    }

    assert folder_selector.ids.browse_button("test_aio_id") == {
        "component": "folder-selector",
        "subcomponent": "browse-button",
        "aio_id": "test_aio_id",
    }

    assert folder_selector.ids.clear_button("test_aio_id") == {
        "component": "folder-selector",
        "subcomponent": "clear-button",
        "aio_id": "test_aio_id",
    }

    assert folder_selector.ids._display_field("test_aio_id") == {
        "component": "folder-selector",
        "subcomponent": "display-field",
        "aio_id": "test_aio_id",
    }

    assert folder_selector.ids._display_field_tooltip("test_aio_id") == {
        "component": "folder-selector",
        "subcomponent": "display-field-tooltip",
        "aio_id": "test_aio_id",
    }

    assert folder_selector.ids.selected_folder("test_aio_id") == {
        "component": "folder-selector",
        "subcomponent": "selected-folder",
        "aio_id": "test_aio_id",
    }


def test_folder_selector_initialization_default_aio_id():
    """Ensure a default aio_id is generated and is a string."""
    folder_selector = FolderSelector()

    assert folder_selector.aio_id is not None
    assert isinstance(folder_selector.aio_id, str)


def test_two_folder_selectors_unique_ids():
    """Ensure two FolderSelector instances have unique aio_ids."""
    folder_selector_1 = FolderSelector()
    folder_selector_2 = FolderSelector()

    assert folder_selector_1.aio_id != folder_selector_2.aio_id


def test_folder_selector_initialization_mode_tkinter_available_env_var_not_set(
    mocker: MockerFixture,
):
    """When tkinter is available and env var is not set, default mode is tkinter."""
    mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.TKINTER_AVAILABLE",
        new=True,
    )
    folder_selector = FolderSelector()

    assert folder_selector.mode == FolderSelectorMode.TKINTER


def test_folder_selector_initialization_mode_tkinter_not_available(
    mocker: MockerFixture,
    tmp_path: Path,
):
    """When tkinter is not available, default mode falls back to bootstrap."""
    mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.TKINTER_AVAILABLE",
        new=False,
    )
    mocker.patch.dict(os.environ, {"FOLDER_SELECTOR_BROWSE_FROM": str(tmp_path)})
    folder_selector = FolderSelector()

    assert folder_selector.mode == FolderSelectorMode.BOOTSTRAP


def test_folder_selector_initialization_mode_tkinter_not_available_beta_disabled(
    mocker: MockerFixture,
):
    """When tkinter is unavailable and bootstrap beta is disabled, mode stays tkinter."""
    mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.TKINTER_AVAILABLE",
        new=False,
    )
    dsc_config._config.enable_beta_features = False

    folder_selector = FolderSelector()

    assert folder_selector.mode == FolderSelectorMode.TKINTER


@pytest.mark.parametrize(
    ("environment_variable_value"),
    [
        "1",
        "true",
        "True",
        "TRUE",
        "yes",
    ],
)
def test_folder_selector_initialization_mode_tkinter_available_env_var_set_truthy(
    mocker: MockerFixture,
    tmp_path: Path,
    environment_variable_value: str,
):
    """Truthy remote deployment env var forces bootstrap mode even if tkinter available."""
    mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.TKINTER_AVAILABLE",
        new=True,
    )
    mocker.patch.dict(
        os.environ,
        {
            "FOLDER_SELECTOR_REMOTE_DEPLOYMENT": environment_variable_value,
            "FOLDER_SELECTOR_BROWSE_FROM": str(tmp_path),
        },
    )
    folder_selector = FolderSelector()

    assert folder_selector.mode == FolderSelectorMode.BOOTSTRAP


@pytest.mark.parametrize(
    ("environment_variable_value"),
    ["1", "true", "True", "TRUE", "yes"],
)
def test_folder_selector_initialization_mode_tkinter_available_env_var_truthy_beta_disabled(
    mocker: MockerFixture,
    environment_variable_value: str,
):
    """Truthy remote deployment env var raises when bootstrap beta is disabled."""
    mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.TKINTER_AVAILABLE",
        new=True,
    )
    dsc_config._config.enable_beta_features = False
    mocker.patch.dict(
        os.environ,
        {
            "FOLDER_SELECTOR_REMOTE_DEPLOYMENT": environment_variable_value,
        },
    )
    with pytest.raises(ValueError, match="BOOTSTRAP mode is a beta feature"):
        FolderSelector()


@pytest.mark.parametrize(
    ("environment_variable_value"),
    [
        "0",
        "false",
        "False",
        "FALSE",
        "no",
    ],
)
def test_folder_selector_initialization_mode_tkinter_available_env_var_set_falsy(
    mocker: MockerFixture,
    environment_variable_value: str,
):
    """Falsy remote deployment env var keeps tkinter mode when available."""
    mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.TKINTER_AVAILABLE",
        new=True,
    )

    mocker.patch.dict(
        "os.environ",
        {"FOLDER_SELECTOR_REMOTE_DEPLOYMENT": environment_variable_value},
    )
    folder_selector = FolderSelector()

    assert folder_selector.mode == FolderSelectorMode.TKINTER


@pytest.mark.parametrize(
    ("mode", "expected_mode"),
    [
        (FolderSelectorMode.TKINTER, FolderSelectorMode.TKINTER),
        (FolderSelectorMode.BOOTSTRAP, FolderSelectorMode.BOOTSTRAP),
    ],
)
def test_folder_selector_initialization_mode_tkinter_available_mode_explicitly_set(
    mocker: MockerFixture,
    tmp_path: Path,
    mode: FolderSelectorMode,
    expected_mode: FolderSelectorMode,
):
    """Explicitly provided mode is respected when tkinter is available."""
    mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.TKINTER_AVAILABLE",
        new=True,
    )
    mocker.patch.dict(
        os.environ,
        {
            "FOLDER_SELECTOR_REMOTE_DEPLOYMENT": "true",
            "FOLDER_SELECTOR_BROWSE_FROM": str(tmp_path),
        },
    )
    folder_selector = FolderSelector(mode=mode)

    assert folder_selector.mode == expected_mode


@pytest.mark.parametrize(
    ("mode", "expected_mode"),
    [
        (FolderSelectorMode.TKINTER, FolderSelectorMode.BOOTSTRAP),
        (FolderSelectorMode.BOOTSTRAP, FolderSelectorMode.BOOTSTRAP),
    ],
)
def test_folder_selector_initialization_mode_tkinter_not_available_mode_explicitly_set(
    mocker: MockerFixture,
    tmp_path: Path,
    mode: FolderSelectorMode,
    expected_mode: FolderSelectorMode,
):
    """Explicit mode is respected (or overridden) when tkinter unavailable."""
    mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.TKINTER_AVAILABLE",
        new=False,
    )
    mocker.patch.dict(os.environ, {"FOLDER_SELECTOR_BROWSE_FROM": str(tmp_path)})
    folder_selector = FolderSelector(mode=mode)

    assert folder_selector.mode == expected_mode


def test_folder_selector_initialization_mode_tkinter_explicit_tkinter_not_available_beta_disabled(
    mocker: MockerFixture,
):
    """Explicit tkinter mode falls back to tkinter when unavailable and beta is disabled."""
    mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.TKINTER_AVAILABLE",
        new=False,
    )
    dsc_config._config.enable_beta_features = False

    folder_selector = FolderSelector(mode=FolderSelectorMode.TKINTER)

    assert folder_selector.mode == FolderSelectorMode.TKINTER


@pytest.mark.parametrize(
    ("mode", "environment_variable_value", "expected_mode"),
    [
        (FolderSelectorMode.TKINTER, True, FolderSelectorMode.TKINTER),
        (FolderSelectorMode.TKINTER, False, FolderSelectorMode.TKINTER),
        (FolderSelectorMode.BOOTSTRAP, True, FolderSelectorMode.BOOTSTRAP),
        (FolderSelectorMode.BOOTSTRAP, False, FolderSelectorMode.BOOTSTRAP),
    ],
)
def test_folder_selector_initialization_mode_explicitly_set_environment_variable_set(
    mocker: MockerFixture,
    tmp_path: Path,
    mode: FolderSelectorMode,
    environment_variable_value: bool,
    expected_mode: FolderSelectorMode,
):
    """Explicit mode with remote deployment env var yields expected mode."""
    mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.TKINTER_AVAILABLE",
        new=True,
    )
    mocker.patch.dict(
        os.environ,
        {
            "FOLDER_SELECTOR_REMOTE_DEPLOYMENT": str(environment_variable_value).lower(),
            "FOLDER_SELECTOR_BROWSE_FROM": str(tmp_path),
        },
    )
    folder_selector = FolderSelector(mode=mode)

    assert folder_selector.mode == expected_mode


def test_folder_selector_initialization_mode_explicitly_set_no_valid_folder_selector_mode():
    """Providing an invalid mode type raises a TypeError."""
    with pytest.raises(TypeError) as exc_info:
        FolderSelector(mode="invalid_mode")  # type: ignore - testing invalid input

    assert str(exc_info.value) == "mode must be an instance of FolderSelectorMode, got <class 'str'>"


def test_folder_selector_bootstrap_mode_requires_beta_opt_in(
    mocker: MockerFixture,
    tmp_path: Path,
):
    """Explicit bootstrap mode raises when bootstrap beta is not enabled."""
    dsc_config._config.enable_beta_features = False
    mocker.patch.dict(os.environ, {"FOLDER_SELECTOR_BROWSE_FROM": str(tmp_path)})

    with pytest.raises(ValueError, match="BOOTSTRAP mode is a beta feature"):
        FolderSelector(mode=FolderSelectorMode.BOOTSTRAP)


def test_folder_selector_bootstrap_mode_requires_browse_from(
    mocker: MockerFixture,
):
    """Bootstrap mode requires browse_from via options or environment."""
    mocker.patch.dict(os.environ, {}, clear=True)

    with pytest.raises(ValueError, match="browse_from is required in BOOTSTRAP mode"):
        FolderSelector(mode=FolderSelectorMode.BOOTSTRAP)


def test_folder_selector_browse_from_is_normalized(tmp_path: Path):
    """browse_from path is normalized before being stored in settings."""
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)

    options = {
        "browse_from": str(root / "sub" / ".."),
    }

    folder_selector = FolderSelector(mode=FolderSelectorMode.BOOTSTRAP, options=options)
    expected = os.path.normpath(str(root))

    assert folder_selector.browse_from == expected


"""----------------------------------------------------------------------------------------------"""
"""Folder Selector Structure Tests"""
"""----------------------------------------------------------------------------------------------"""


def test_folder_selector_structure_default_settings_mode_bootstrap(
    tmp_path: Path,
    mocker: MockerFixture,
):
    """Verify folder selector structure using default bootstrap settings."""
    aio_id = "test_aio_id"
    mode = FolderSelectorMode.BOOTSTRAP

    expected_browse_from_folder_path = tmp_path / "dummy_folder_without_subfolders"
    expected_browse_from_folder_path.mkdir()

    mocker.patch.dict(
        "os.environ",
        {"FOLDER_SELECTOR_BROWSE_FROM": str(expected_browse_from_folder_path)},
    )

    folder_selector = FolderSelector(
        aio_id=aio_id,
        mode=mode,
    )

    _assert_folder_selector(
        folder_selector,
        aio_id=aio_id,
        mode=mode,
        browse_from=str(expected_browse_from_folder_path),
        topmost=True,
        max_path_length=PathValidator.max_path_length(),
        default_path=None,
        display_field_enabled=True,
        selected_folder_value=None,
        style={},
        browse_button_props={},
        clear_button_props={},
    )


def test_folder_selector_structure_with_browse_from_from_environment_variable(
    tmp_path: Path,
    mocker: MockerFixture,
):
    """When env var sets browse_from, folder selector uses that path."""
    aio_id = "test_aio_id"
    mode = FolderSelectorMode.BOOTSTRAP

    expected_browse_from_folder_path = tmp_path / "dummy_folder_without_subfolders"
    expected_browse_from_folder_path.mkdir()

    mocker.patch.dict(
        "os.environ",
        {"FOLDER_SELECTOR_BROWSE_FROM": str(expected_browse_from_folder_path)},
    )

    folder_selector = FolderSelector(
        aio_id=aio_id,
        mode=mode,
    )

    _assert_folder_selector(
        folder_selector,
        aio_id=aio_id,
        mode=mode,
        browse_from=str(expected_browse_from_folder_path),
        topmost=True,
        max_path_length=PathValidator.max_path_length(),
        default_path=None,
        display_field_enabled=True,
        selected_folder_value=None,
        style={},
        browse_button_props={},
        clear_button_props={},
    )


def test_folder_selector_structure_with_browse_from_in_options_environment_variable_not_set(
    tmp_path: Path,
):
    """When options provide browse_from and env var absent, folder selector uses options value."""
    aio_id = "test_aio_id"
    mode = FolderSelectorMode.BOOTSTRAP

    expected_browse_from_folder_path = tmp_path / "dummy_folder_without_subfolders"
    expected_browse_from_folder_path.mkdir()

    options = {
        "browse_from": str(expected_browse_from_folder_path),
    }

    folder_selector = FolderSelector(aio_id=aio_id, mode=mode, options=options)

    _assert_folder_selector(
        folder_selector,
        aio_id=aio_id,
        mode=mode,
        browse_from=str(expected_browse_from_folder_path),
        topmost=True,
        max_path_length=PathValidator.max_path_length(),
        default_path=None,
        display_field_enabled=True,
        selected_folder_value=None,
        style={},
        browse_button_props={},
        clear_button_props={},
    )


def test_folder_selector_structure_with_browse_from_from_environment_variable_and_in_options(
    tmp_path: Path,
    mocker: MockerFixture,
):
    """Options override the environment variable browse_from when both are present."""
    aio_id = "test_aio_id"
    mode = FolderSelectorMode.BOOTSTRAP

    expected_browse_from_folder_path = tmp_path / "dummy_folder_without_subfolders"
    expected_browse_from_folder_path.mkdir()

    mocker.patch.dict(
        "os.environ",
        {"FOLDER_SELECTOR_BROWSE_FROM": "dummy_path_that_should_be_ignored"},
    )

    options = {
        "browse_from": str(expected_browse_from_folder_path),
    }

    folder_selector = FolderSelector(aio_id=aio_id, mode=mode, options=options)

    _assert_folder_selector(
        folder_selector,
        aio_id=aio_id,
        mode=mode,
        browse_from=str(expected_browse_from_folder_path),
        topmost=True,
        max_path_length=PathValidator.max_path_length(),
        default_path=None,
        display_field_enabled=True,
        selected_folder_value=None,
        style={},
        browse_button_props={},
        clear_button_props={},
    )


def test_folder_selector_structure_with_default_folder_string(tmp_path: Path, mocker: MockerFixture):
    """Default path provided in options initializes the selected default path."""
    aio_id = "test_aio_id"
    mode = FolderSelectorMode.BOOTSTRAP

    browse_from_folder_path = tmp_path / "dummy_folder_without_subfolders"
    browse_from_folder_path.mkdir()

    options = {
        "default_path": "dummy_path",
        "browse_from": str(browse_from_folder_path),
    }

    folder_selector = FolderSelector(aio_id=aio_id, mode=mode, options=options)

    _assert_folder_selector(
        folder_selector,
        aio_id=aio_id,
        mode=mode,
        browse_from=str(browse_from_folder_path),
        topmost=True,
        max_path_length=PathValidator.max_path_length(),
        default_path="dummy_path",
        display_field_enabled=True,
        selected_folder_value=None,
        style={},
        browse_button_props={},
        clear_button_props={},
    )


def test_folder_selector_structure_with_default_folder_path(tmp_path: Path, mocker: MockerFixture):
    """Default path provided in options initializes the selected default path."""
    aio_id = "test_aio_id"
    mode = FolderSelectorMode.BOOTSTRAP

    browse_from_folder_path = tmp_path / "dummy_folder_without_subfolders"
    browse_from_folder_path.mkdir()

    options = {
        "default_path": Path("dummy_path"),
        "browse_from": str(browse_from_folder_path),
    }

    folder_selector = FolderSelector(aio_id=aio_id, mode=mode, options=options)

    _assert_folder_selector(
        folder_selector,
        aio_id=aio_id,
        mode=mode,
        browse_from=str(browse_from_folder_path),
        topmost=True,
        max_path_length=PathValidator.max_path_length(),
        default_path=str(Path("dummy_path")),
        display_field_enabled=True,
        selected_folder_value=None,
        style={},
        browse_button_props={},
        clear_button_props={},
    )


def test_folder_selector_structure_with_topmost_set(tmp_path: Path, mocker: MockerFixture):
    """Topmost option controls behavior passed to tkinter if used."""
    aio_id = "test_aio_id"
    mode = FolderSelectorMode.BOOTSTRAP

    browse_from_folder_path = tmp_path / "dummy_folder_without_subfolders"
    browse_from_folder_path.mkdir()

    options = {
        "topmost": False,
        "browse_from": str(browse_from_folder_path),
    }

    folder_selector = FolderSelector(aio_id=aio_id, mode=mode, options=options)

    _assert_folder_selector(
        folder_selector,
        aio_id=aio_id,
        mode=mode,
        browse_from=str(browse_from_folder_path),
        topmost=False,
        max_path_length=PathValidator.max_path_length(),
        default_path=None,
        display_field_enabled=True,
        selected_folder_value=None,
        style={},
        browse_button_props={},
        clear_button_props={},
    )


def test_folder_selector_structure_with_max_path_length_set(tmp_path: Path, mocker: MockerFixture):
    """Custom max_path_length from options is respected."""
    aio_id = "test_aio_id"
    mode = FolderSelectorMode.BOOTSTRAP

    browse_from_folder_path = tmp_path / "dummy_folder_without_subfolders"
    browse_from_folder_path.mkdir()

    options = {
        "max_path_length": 100,
        "browse_from": str(browse_from_folder_path),
    }

    folder_selector = FolderSelector(aio_id=aio_id, mode=mode, options=options)

    _assert_folder_selector(
        folder_selector,
        aio_id=aio_id,
        mode=mode,
        browse_from=str(browse_from_folder_path),
        topmost=True,
        max_path_length=100,
        default_path=None,
        display_field_enabled=True,
        selected_folder_value=None,
        style={},
        browse_button_props={},
        clear_button_props={},
    )


def test_folder_selector_structure_with_max_display_field_enabled_set_to_false(
    tmp_path: Path,
    mocker: MockerFixture,
):
    """Display field can be disabled via options."""
    aio_id = "test_aio_id"
    mode = FolderSelectorMode.BOOTSTRAP

    browse_from_folder_path = tmp_path / "dummy_folder_without_subfolders"
    browse_from_folder_path.mkdir()

    options = {
        "display_field": {"enabled": False},
        "browse_from": str(browse_from_folder_path),
    }

    folder_selector = FolderSelector(aio_id=aio_id, mode=mode, options=options)

    _assert_folder_selector(
        folder_selector,
        aio_id=aio_id,
        mode=mode,
        browse_from=str(browse_from_folder_path),
        topmost=True,
        max_path_length=PathValidator.max_path_length(),
        default_path=None,
        display_field_enabled=False,
        selected_folder_value=None,
        style={},
        browse_button_props={},
        clear_button_props={},
    )


def test_folder_selector_structure_with_max_display_lines_set(
    tmp_path: Path,
    mocker: MockerFixture,
):
    """Custom max_display_lines option controls the lineClamp value on the display field."""
    aio_id = "test_aio_id"
    mode = FolderSelectorMode.BOOTSTRAP

    browse_from_folder_path = tmp_path / "dummy_folder_without_subfolders"
    browse_from_folder_path.mkdir()

    options = {
        "display_field": {"enabled": True, "max_display_lines": 5},
        "browse_from": str(browse_from_folder_path),
    }

    folder_selector = FolderSelector(aio_id=aio_id, mode=mode, options=options)

    _assert_folder_selector(
        folder_selector,
        aio_id=aio_id,
        mode=mode,
        browse_from=str(browse_from_folder_path),
        topmost=True,
        max_path_length=PathValidator.max_path_length(),
        default_path=None,
        display_field_enabled=True,
        selected_folder_value=None,
        style={},
        browse_button_props={},
        clear_button_props={},
        max_display_lines=5,
    )


def test_folder_selector_structure_with_style(tmp_path: Path, mocker: MockerFixture):
    """Custom style is applied to the outer container."""
    aio_id = "test_aio_id"
    mode = FolderSelectorMode.BOOTSTRAP

    browse_from_folder_path = tmp_path / "dummy_folder_without_subfolders"
    browse_from_folder_path.mkdir()

    style = {
        "margin-top": "10px",
        "margin-bottom": "10px",
    }

    folder_selector = FolderSelector(
        aio_id=aio_id,
        mode=mode,
        style=copy.deepcopy(style),
        options={"browse_from": str(browse_from_folder_path)},
    )

    _assert_folder_selector(
        folder_selector,
        aio_id=aio_id,
        mode=mode,
        browse_from=str(browse_from_folder_path),
        topmost=True,
        max_path_length=PathValidator.max_path_length(),
        default_path=None,
        display_field_enabled=True,
        selected_folder_value=None,
        style=style,
        browse_button_props={},
        clear_button_props={},
    )


def test_folder_selector_structure_with_value(tmp_path: Path, mocker: MockerFixture):
    """Providing a value initializes the selected folder store appropriately."""
    aio_id = "test_aio_id"
    mode = FolderSelectorMode.BOOTSTRAP

    browse_from_folder_path = tmp_path / "dummy_folder_without_subfolders"
    browse_from_folder_path.mkdir()

    folder_selector = FolderSelector(
        aio_id=aio_id,
        mode=mode,
        value="test_folder",
        options={"browse_from": str(browse_from_folder_path)},
    )

    _assert_folder_selector(
        folder_selector,
        aio_id=aio_id,
        mode=mode,
        browse_from=str(browse_from_folder_path),
        topmost=True,
        max_path_length=PathValidator.max_path_length(),
        default_path=None,
        display_field_enabled=True,
        selected_folder_value="test_folder",
        style={},
        browse_button_props={},
        clear_button_props={},
    )


def test_folder_selector_structure_tkinter_mode_uses_no_folder_structure(
    tmp_path: Path,
):
    """Tkinter mode does not precompute folders structure for the modal tree."""
    aio_id = "test_aio_id"
    mode = FolderSelectorMode.TKINTER

    browse_from_folder_path = tmp_path / "dummy_folder_without_subfolders"
    browse_from_folder_path.mkdir()

    folder_selector = FolderSelector(
        aio_id=aio_id,
        mode=mode,
        options={"browse_from": str(browse_from_folder_path)},
    )

    _assert_folder_selector(
        folder_selector,
        aio_id=aio_id,
        mode=mode,
        browse_from=str(browse_from_folder_path),
        topmost=True,
        max_path_length=PathValidator.max_path_length(),
        default_path=None,
        display_field_enabled=True,
        selected_folder_value=None,
        style={},
        browse_button_props={},
        clear_button_props={},
    )


def test_folder_selector_structure_with_browse_button_props_and_clear_button_props(
    tmp_path: Path,
    mocker: MockerFixture,
):
    """Custom browse and clear button props override defaults where provided."""
    aio_id = "test_aio_id"
    mode = FolderSelectorMode.BOOTSTRAP

    browse_from_folder_path = tmp_path / "dummy_folder_without_subfolders"
    browse_from_folder_path.mkdir()

    browse_button_props = {
        "children": "Select Folder",
        "radius": "md",
        "className": "mantine-button-custom",
        "color": "blue",
        "style": {"width": "90%"},
        "variant": "filled",
        "leftSection": html.Img(src="custom_browse_icon_src"),
        "autoContrast": True,  # additional property not included in default browse button props
    }

    clear_button_props = {
        "radius": "md",
        # additional property not included in clear button props
        "className": "mantine-button-custom",
        "color": "blue",
        "size": "xl",
        "variant": "filled",
        "children": "blah",
    }

    folder_selector = FolderSelector(
        aio_id=aio_id,
        mode=mode,
        browse_button_props=copy.deepcopy(browse_button_props),
        clear_button_props=copy.deepcopy(clear_button_props),
        options={"browse_from": str(browse_from_folder_path)},
    )

    _assert_folder_selector(
        folder_selector,
        aio_id=aio_id,
        mode=mode,
        browse_from=str(browse_from_folder_path),
        topmost=True,
        max_path_length=PathValidator.max_path_length(),
        default_path=None,
        display_field_enabled=True,
        selected_folder_value=None,
        style={},
        browse_button_props=browse_button_props,
        clear_button_props=clear_button_props,
    )


def test_folder_selector_does_not_mutate_button_props_inputs(
    tmp_path: Path,
    mocker: MockerFixture,
):
    """Ensure caller-provided button props are not mutated in place."""
    aio_id = "test_aio_id"
    mode = FolderSelectorMode.BOOTSTRAP

    browse_from_folder_path = tmp_path / "dummy_folder_without_subfolders"
    browse_from_folder_path.mkdir()

    browse_button_props = {
        "children": "Select Folder",
        "radius": "md",
    }
    clear_button_props = {
        "size": "xl",
    }

    original_browse_button_props = copy.deepcopy(browse_button_props)
    original_clear_button_props = copy.deepcopy(clear_button_props)

    folder_selector = FolderSelector(
        aio_id=aio_id,
        mode=mode,
        browse_button_props=browse_button_props,
        clear_button_props=clear_button_props,
        options={"browse_from": str(browse_from_folder_path)},
    )

    # Inputs must remain unchanged (no defaults injected into caller objects).
    assert browse_button_props == original_browse_button_props
    assert clear_button_props == original_clear_button_props

    # Rendered output still includes merged defaults.
    _assert_folder_selector(
        folder_selector,
        aio_id=aio_id,
        mode=mode,
        browse_from=str(browse_from_folder_path),
        topmost=True,
        max_path_length=PathValidator.max_path_length(),
        default_path=None,
        display_field_enabled=True,
        selected_folder_value=None,
        style={},
        browse_button_props=browse_button_props,
        clear_button_props=clear_button_props,
    )


def _assert_folder_selector(
    folder_selector: FolderSelector,
    aio_id: str,
    mode: FolderSelectorMode,
    browse_from: str,
    topmost: bool,
    max_path_length: int,
    default_path: str | None,
    display_field_enabled: bool,
    selected_folder_value: str | None,
    style: dict[str, Any],
    browse_button_props: dict[str, Any],
    clear_button_props: dict[str, Any],
    max_display_lines: int = 2,
    max_tree_depth: int = 10,
    max_children_per_node: int = 100,
):

    expected_folders_structure = (
        FolderSelector.get_folders_structure(browse_from) if mode == FolderSelectorMode.BOOTSTRAP else None
    )

    assert isinstance(folder_selector, html.Div)
    assert folder_selector.children is not None
    assert len(folder_selector.children) == 1

    outer_div = folder_selector.children[0]
    assert isinstance(outer_div, html.Div)
    assert outer_div.style == style
    assert outer_div.children is not None
    assert len(outer_div.children) == 7

    button_group = outer_div.children[0]
    assert isinstance(button_group, dmc.Group)
    assert button_group.children is not None
    assert len(button_group.children) == 2

    browse_button = button_group.children[0]
    assert isinstance(browse_button, dmc.Button)
    assert browse_button.id == FolderSelector.ids.browse_button(aio_id)

    # assert default browse button props (might be overridden by browse_button_props)
    assert browse_button.children == browse_button_props.get("children", "Browse")
    assert browse_button.radius == browse_button_props.get("radius", "xl")
    assert browse_button.variant == browse_button_props.get("variant", "outline")
    assert browse_button.className == browse_button_props.get("className", "mantine-button")
    if "color" in browse_button_props:
        assert browse_button.color == browse_button_props.get("color")
    else:
        assert not hasattr(browse_button, "color")
    assert browse_button.style == browse_button_props.get("style", {"width": "80%"})

    if "leftSection" in browse_button_props:
        assert str(browse_button.leftSection) == str(browse_button_props["leftSection"])
    else:
        assert isinstance(browse_button.leftSection, html.Span)
        assert browse_button.leftSection.style is not None
        assert browse_button.leftSection.style.get("backgroundColor") == "currentColor"
        assert browse_button.leftSection.style.get("width") == "16px"
        assert browse_button.leftSection.style.get("height") == "16px"
        assert str(browse_button.leftSection.style.get("maskImage", "")) in {
            f"url('{EXPECTED_BROWSE_BUTTON_ICON_SRC}')",
            f'url("{EXPECTED_BROWSE_BUTTON_ICON_SRC}")',
        }

    for prop, value in browse_button_props.items():
        if prop not in [
            "children",
            "radius",
            "variant",
            "className",
            "color",
            "style",
            "leftSection",
        ]:
            assert getattr(browse_button, prop) == value

    clear_button = button_group.children[1]
    assert isinstance(clear_button, dmc.ActionIcon)
    assert clear_button.id == FolderSelector.ids.clear_button(aio_id)

    # assert default clear button props (might be overridden by clear_button_props)
    assert clear_button.size == clear_button_props.get("size", "md")
    assert clear_button.radius == clear_button_props.get("radius", "sm")
    assert clear_button.variant == clear_button_props.get("variant", "outline")
    if "color" in clear_button_props:
        assert clear_button.color == clear_button_props.get("color")
    else:
        assert not hasattr(clear_button, "color")

    if "children" in clear_button_props:
        assert clear_button.children == clear_button_props["children"]
    else:
        assert isinstance(clear_button.children, html.Span)
        assert clear_button.children.style is not None
        assert clear_button.children.style.get("backgroundColor") == "currentColor"
        assert clear_button.children.style.get("width") == "20px"
        assert clear_button.children.style.get("height") == "20px"
        assert str(clear_button.children.style.get("maskImage", "")) in {
            f"url('{EXPECTED_CLEAR_BUTTON_ICON_SRC}')",
            f'url("{EXPECTED_CLEAR_BUTTON_ICON_SRC}")',
        }

    for prop, value in clear_button_props.items():
        if prop not in ["size", "radius", "variant", "color", "children"]:
            assert getattr(clear_button, prop) == value

    tooltip = outer_div.children[1]
    assert isinstance(tooltip, dmc.Tooltip)
    assert tooltip.id == FolderSelector.ids._display_field_tooltip(aio_id)
    assert tooltip.multiline is True
    assert tooltip.withArrow is True

    display_field = tooltip.children
    assert isinstance(display_field, dmc.Text)
    assert display_field.id == FolderSelector.ids._display_field(aio_id)
    assert display_field.lineClamp == max_display_lines
    if display_field_enabled:
        assert "display" not in display_field.style
    else:
        assert display_field.style.get("display") == "none"

    selected_folder_store = outer_div.children[2]
    assert isinstance(selected_folder_store, dcc.Store)
    assert selected_folder_store.id == FolderSelector.ids.selected_folder(aio_id)
    assert selected_folder_store.storage_type == "memory"
    assert selected_folder_store.data == selected_folder_value

    settings_store = outer_div.children[3]
    assert isinstance(settings_store, dcc.Store)
    assert settings_store.id == FolderSelector.ids._settings(aio_id)
    assert settings_store.storage_type == "memory"
    assert settings_store.data == {
        "topmost": topmost,
        "max_path_length": max_path_length,
        "default_path": default_path,
        "mode": mode,
        "browse_from": browse_from,
        "max_tree_depth": max_tree_depth,
        "max_children_per_node": max_children_per_node,
    }

    folder_selector_is_open_store = outer_div.children[4]
    assert isinstance(folder_selector_is_open_store, dcc.Store)
    assert folder_selector_is_open_store.id == FolderSelector.ids._folder_selector_is_open(aio_id)
    assert folder_selector_is_open_store.storage_type == "memory"
    assert folder_selector_is_open_store.data is False

    folders_structure_store = outer_div.children[5]
    assert isinstance(folders_structure_store, dcc.Store)
    assert folders_structure_store.id == FolderSelector.ids._folders_structure(aio_id)
    assert folders_structure_store.storage_type == "memory"
    assert folders_structure_store.data == expected_folders_structure

    modal = outer_div.children[6]
    assert modal.id == FolderSelector.ids._folder_selector_modal(aio_id)
    assert modal.title == "Pick a folder from the server"
    assert modal.zIndex == 10000
    assert modal.closeOnClickOutside is False
    assert modal.closeOnEscape is False
    assert modal.withCloseButton is False
    assert modal.size == "xl"

    modal_children = modal.children
    assert len(modal_children) == 2
    tree = modal_children[0]
    assert isinstance(tree, Tree)
    assert tree.aio_id == aio_id
    assert tree.default_icon == create_base64_svg_src(IconNames.MATERIAL_FOLDER)

    done_button_group = modal_children[1]
    assert isinstance(done_button_group, dmc.Group)
    assert done_button_group.justify == "center"
    assert done_button_group.children is not None
    assert len(done_button_group.children) == 1
    done_button = done_button_group.children[0]
    assert isinstance(done_button, dmc.Button)
    assert done_button.id == FolderSelector.ids._folder_selector_modal_done_button(aio_id)
    assert done_button.children == "Done"


"""----------------------------------------------------------------------------------------------"""
"""Callback Tests"""
"""----------------------------------------------------------------------------------------------"""


@pytest.mark.parametrize(
    ("selected_folder", "default_path", "expected"),
    [
        (None, "/default/path", "/default/path"),
        (None, None, no_update),
        ("/existing/path", "/default/path", no_update),
        ("", "/default/path", "/default/path"),
    ],
)
def test_populate_selected_folder_with_default_path(
    selected_folder: str | None,
    default_path: str | None,
    expected: str | NoUpdate,
):
    """Populate selected folder with default when appropriate."""
    settings = {
        "default_path": default_path,
        "topmost": True,
        "max_path_length": 260,
        "mode": FolderSelectorMode.BOOTSTRAP,
        "browse_from": "/",
    }

    result = FolderSelector.populate_selected_folder_with_default_path(
        selected_folder,
        settings,
    )

    assert result == expected


@pytest.mark.parametrize(
    ("n_clicks", "expected"),
    [
        (1, True),
        (2, True),
        (0, no_update),
        (None, no_update),
    ],
)
def test_disable_browse_button(n_clicks: int | None, expected: bool | NoUpdate):
    """Disable browse button when clicked; otherwise no update."""
    result = FolderSelector.disable_browse_button(n_clicks)  # type: ignore - deliberately testing None input
    assert result == expected


@pytest.mark.parametrize(
    ("folder_selector_open", "expected_browse_button_disabled", "raises"),
    [
        (False, False, False),
        (True, None, True),
    ],
)
def test_enable_browse_button(
    folder_selector_open: bool,
    expected_browse_button_disabled: bool | None,
    raises: bool,
):
    """Enable or preserve disabled state for the browse button depending on open state."""
    if raises:
        with pytest.raises(PreventUpdate):
            FolderSelector.enable_browse_button(folder_selector_open)
    else:
        result = FolderSelector.enable_browse_button(folder_selector_open)
        assert result == expected_browse_button_disabled


@pytest.mark.parametrize(
    ("n_clicks", "expected"),
    [
        (1, True),
        (2, True),
    ],
)
def test_browse(n_clicks: int, expected: bool):
    """Request to browse should mark folder selector as open."""
    result = FolderSelector.browse(n_clicks)
    assert result is expected


def test_browse_no_clicks():
    """No clicks results in PreventUpdate from browse."""
    with pytest.raises(PreventUpdate):
        FolderSelector.browse(0)


def test_open_folder_selector_tkinter_success(mocker: MockerFixture, tmp_path: Path):
    """Successful tkinter-based selection returns chosen path and closes modal."""
    selected_directory = str(tmp_path / "selected_folder")
    Path(selected_directory).mkdir(parents=True, exist_ok=True)
    mocker.patch.object(
        FolderSelector,
        "ask_directory_with_tkinter",
        return_value=selected_directory,
    )

    settings = {
        "topmost": True,
        "max_path_length": 260,
        "default_path": None,
        "mode": FolderSelectorMode.TKINTER,
        "browse_from": "/root_node",
    }

    is_open, selected, modal_opened, selected_item = FolderSelector.open_folder_selector(
        True,
        settings,
        1,
        None,
        {"id": "root-id", "text": "/root_node", "children": []},
        {"aio_id": "test_aio_id"},
    )

    assert is_open is False
    assert selected == selected_directory
    assert modal_opened == no_update
    assert selected_item == no_update


def test_open_folder_selector_tkinter_cancel_keeps_previous_selection(mocker: MockerFixture):
    """Canceling tkinter dialog should not overwrite selected folder."""
    mocker.patch.object(
        FolderSelector,
        "ask_directory_with_tkinter",
        return_value=None,
    )
    mock_set_props = mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.set_props",
    )

    settings = {
        "topmost": True,
        "max_path_length": 260,
        "default_path": None,
        "mode": FolderSelectorMode.TKINTER,
        "browse_from": "/root_node",
    }

    is_open, selected, modal_opened, selected_item = FolderSelector.open_folder_selector(
        True,
        settings,
        1,
        "/existing/path",
        {"id": "root-id", "text": "/root_node", "children": []},
        {"aio_id": "test_aio_id"},
    )

    assert is_open is False
    assert selected == no_update
    assert modal_opened == no_update
    assert selected_item == no_update
    mock_set_props.assert_not_called()


def test_open_folder_selector_tkinter_path_too_long(mocker: MockerFixture):
    """Validation failures send an error notification via set_props and return no selection."""
    max_path_length = 10
    selected_directory = "/very/long/path/exceeding/maximum"
    mocker.patch.object(
        FolderSelector,
        "ask_directory_with_tkinter",
        return_value=selected_directory,
    )
    mock_set_props = mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.set_props",
    )

    settings = {
        "topmost": True,
        "max_path_length": max_path_length,
        "default_path": None,
        "mode": FolderSelectorMode.TKINTER,
        "browse_from": "/root_node",
    }

    is_open, selected, modal_opened, selected_item = FolderSelector.open_folder_selector(
        True,
        settings,
        1,
        None,
        {"id": "root-id", "text": "/root_node", "children": []},
        {"aio_id": "test_aio_id"},
    )

    assert is_open is False
    assert selected is None
    assert modal_opened == no_update
    assert selected_item == no_update

    # Verify set_props was called with the notification
    mock_set_props.assert_called_once()
    notification = mock_set_props.call_args[0][1]["sendNotifications"][0]
    assert notification["title"] == "Error during folder selection"
    assert notification["color"] == CommonColors.MANTINE_ERROR
    assert "exceeds the maximum length" in notification["message"]
    assert not notification["autoClose"]
    assert notification["action"] == "show"
    assert notification["id"] == "folder-selector-notify-failure-1"


def test_open_folder_selector_tkinter_tcl_error(mocker: MockerFixture):
    """TclError during tkinter selection is handled and reported via set_props notification."""
    # Mock ask_directory_with_tkinter to raise TclError
    mocker.patch.object(
        FolderSelector,
        "ask_directory_with_tkinter",
        side_effect=tkinter.TclError("No display"),
    )
    mock_set_props = mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.set_props",
    )

    settings = {
        "topmost": True,
        "max_path_length": 260,
        "default_path": None,
        "mode": FolderSelectorMode.TKINTER,
        "browse_from": "/root_node",
    }

    is_open, selected, modal_opened, selected_item = FolderSelector.open_folder_selector(
        True,
        settings,
        1,
        None,
        {"id": "root-id", "text": "/root_node", "children": []},
        {"aio_id": "test_aio_id"},
    )

    assert is_open is False
    assert selected is None
    assert modal_opened is False
    assert selected_item == no_update

    # Verify set_props was called with the notification
    mock_set_props.assert_called_once()
    notification = mock_set_props.call_args[0][1]["sendNotifications"][0]
    assert notification["title"] == "Error during folder selection"
    assert "does not support tkinter" in notification["message"] or "BOOTSTRAP mode" in notification["message"]
    assert not notification["autoClose"]
    assert notification["action"] == "show"
    assert notification["id"] == "folder-selector-notify-failure-1"


def test_open_folder_selector_tkinter_runtime_error_when_bootstrap_beta_disabled(
    mocker: MockerFixture,
):
    """RuntimeError in tkinter mode reports actionable beta opt-in guidance."""
    dsc_config._config.enable_beta_features = False
    mocker.patch.object(
        FolderSelector,
        "ask_directory_with_tkinter",
        side_effect=RuntimeError("tkinter is not available in this environment"),
    )
    mock_set_props = mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.set_props",
    )

    settings = {
        "topmost": True,
        "max_path_length": 260,
        "default_path": None,
        "mode": FolderSelectorMode.TKINTER,
        "browse_from": "/root_node",
    }

    is_open, selected, modal_opened, selected_item = FolderSelector.open_folder_selector(
        True,
        settings,
        1,
        None,
        {"id": "root-id", "text": "/root_node", "children": []},
        {"aio_id": "test_aio_id"},
    )

    assert is_open is False
    assert selected is None
    assert modal_opened is False
    assert selected_item == no_update

    mock_set_props.assert_called_once()
    notification = mock_set_props.call_args[0][1]["sendNotifications"][0]
    assert notification["title"] == "Error during folder selection"
    assert "BOOTSTRAP mode is disabled because it is a beta feature" in notification["message"]
    assert "configure(enable_beta_features=True)" in notification["message"]


def test_open_folder_selector_bootstrap_mode():
    """Bootstrap mode opens modal and preselects nothing if no current selection exists."""
    settings = {
        "topmost": True,
        "max_path_length": 260,
        "default_path": None,
        "mode": FolderSelectorMode.BOOTSTRAP,
        "browse_from": "/root_node",
    }

    folders_structure = {
        "id": "root-id",
        "text": "/root_node",
        "children": [{"id": "folder1-id", "text": "folder1", "children": []}],
    }

    is_open, selected, modal_opened, selected_item = FolderSelector.open_folder_selector(
        True,
        settings,
        1,
        None,
        folders_structure,
        {"aio_id": "test_aio_id"},
    )

    assert is_open == no_update
    assert selected == no_update
    assert modal_opened is True
    assert selected_item is None


def test_open_folder_selector_bootstrap_mode_restores_previous_selection():
    """Bootstrap mode returns the previously selected tree node for highlight persistence."""
    settings = {
        "topmost": True,
        "max_path_length": 260,
        "default_path": None,
        "mode": FolderSelectorMode.BOOTSTRAP,
        "browse_from": "/root_node",
    }

    folders_structure = {
        "id": "root-id",
        "text": "/root_node",
        "children": [
            {
                "id": "folder1-id",
                "text": "folder1",
                "children": [{"id": "sub-id", "text": "sub", "children": []}],
            },
        ],
    }

    is_open, selected, modal_opened, selected_item = FolderSelector.open_folder_selector(
        True,
        settings,
        1,
        str(Path("/root_node") / "folder1"),
        folders_structure,
        {"aio_id": "test_aio_id"},
    )

    assert is_open == no_update
    assert selected == no_update
    assert modal_opened is True
    assert selected_item == Tree.ids.navlink_item("test_aio_id", "folder1-id")


def test_open_folder_selector_not_open():
    """If not open, attempting to open folder selector raises PreventUpdate."""
    settings = {
        "topmost": True,
        "max_path_length": 260,
        "default_path": None,
        "mode": FolderSelectorMode.TKINTER,
        "browse_from": "/root_node",
    }

    with pytest.raises(PreventUpdate):
        FolderSelector.open_folder_selector(
            False,
            settings,
            1,
            None,
            {"id": "root-id", "text": "/root_node", "children": []},
            {"aio_id": "test_aio_id"},
        )


def test_dismiss_modal_and_update_selected_folder_with_selection(tmp_path: Path):
    """Dismiss modal and update selected folder when a valid selection exists."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "folder1").mkdir()
    (root / "folder2").mkdir()

    tree_structure = {
        "id": "root-id",
        "text": str(root),
        "children": [
            {"id": "folder1-id", "text": "folder1", "children": []},
            {"id": "folder2-id", "text": "folder2", "children": []},
        ],
    }

    selected_item_id = {
        "aio_id": "test_aio_id",
        "component": "tree",
        "subcomponent": "navlink-item",
        "index": "folder1-id",
    }

    is_open, modal_opened, selected_folder = FolderSelector.dismiss_modal_and_update_selected_folder(
        1,
        selected_item_id,
        tree_structure,
        _bootstrap_settings(),
    )

    assert is_open is False
    assert modal_opened is False
    assert selected_folder == str(root / "folder1")


def test_dismiss_modal_and_update_selected_folder_no_selection():
    """Dismiss modal with no selection results in no_update for selected folder."""
    tree_structure = {
        "id": "root-id",
        "text": "/root_node",
        "children": [],
    }

    is_open, modal_opened, selected_folder = FolderSelector.dismiss_modal_and_update_selected_folder(
        1,
        None,
        tree_structure,
        _bootstrap_settings(),
    )

    assert is_open is False
    assert modal_opened is False
    assert selected_folder == no_update


def test_dismiss_modal_and_update_selected_folder_empty_tree(mocker: MockerFixture):
    """Missing/empty tree structure triggers notification and no selection update."""
    mock_set_props = mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.set_props",
    )

    is_open, modal_opened, selected_folder = FolderSelector.dismiss_modal_and_update_selected_folder(
        1,
        None,
        {},
        _bootstrap_settings(),
    )

    assert is_open is False
    assert modal_opened is False
    assert selected_folder == no_update

    mock_set_props.assert_called_once()
    notification = mock_set_props.call_args[0][1]["sendNotifications"][0]
    assert notification["title"] == "Error during folder selection"
    assert notification["color"] == CommonColors.MANTINE_ERROR
    assert notification["autoClose"]
    assert notification["action"] == "show"


@pytest.mark.parametrize(
    ("selected_item_id"),
    [
        # Wrong component type
        {
            "aio_id": "test_aio_id",
            "component": "other_component",
            "subcomponent": "navlink-item",
            "index": "folder1-id",
        },
        # Wrong subcomponent type
        {
            "aio_id": "test_aio_id",
            "component": "tree",
            "subcomponent": "other_subcomponent",
            "index": "folder1-id",
        },
        # Missing index
        {"aio_id": "test_aio_id", "component": "tree", "subcomponent": "navlink-item"},
    ],
)
def test_dismiss_modal_and_update_selected_folder_invalid_selections(
    mocker: MockerFixture,
    selected_item_id: dict[str, Any],
):
    """Invalid selection sends notification and returns no_update for selected folder."""
    tree_structure = {
        "id": "root-id",
        "text": "/root_node",
        "children": [],
    }

    mock_set_props = mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.set_props",
    )

    is_open, modal_opened, selected_folder = FolderSelector.dismiss_modal_and_update_selected_folder(
        1,
        selected_item_id,
        tree_structure,
        _bootstrap_settings(),
    )

    assert is_open is False
    assert modal_opened is False
    assert selected_folder == no_update

    # Verify set_props was called with the notification
    mock_set_props.assert_called_once()
    notification = mock_set_props.call_args[0][1]["sendNotifications"][0]
    assert notification["title"] == "Error during folder selection"
    assert notification["color"] == CommonColors.MANTINE_ERROR
    assert notification["autoClose"]
    assert notification["action"] == "show"


def test_dismiss_modal_and_update_selected_folder_no_clicks():
    """No clicks when dismissing modal raises PreventUpdate."""
    tree_structure = {"id": "root-id", "text": "/root_node", "children": []}

    with pytest.raises(PreventUpdate):
        FolderSelector.dismiss_modal_and_update_selected_folder(
            None,
            None,
            tree_structure,
            _bootstrap_settings(),
        )


def test_open_folder_selector_uses_configured_notification_container_id(
    mocker: MockerFixture,
):
    """set_props targets the ID from utils/config._config.notification_container_id."""
    custom_id = "my-custom-notifications"
    dsc_config._config.notification_container_id = custom_id

    mocker.patch.object(
        FolderSelector,
        "ask_directory_with_tkinter",
        side_effect=tkinter.TclError("No display"),
    )
    mock_set_props = mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.set_props",
    )

    settings = {
        "topmost": True,
        "max_path_length": 260,
        "default_path": None,
        "mode": FolderSelectorMode.TKINTER,
        "browse_from": "/root_node",
    }

    FolderSelector.open_folder_selector(
        True,
        settings,
        1,
        None,
        {"id": "root-id", "text": "/root_node", "children": []},
        {"aio_id": "test_aio_id"},
    )

    mock_set_props.assert_called_once()
    actual_container_id = mock_set_props.call_args[0][0]
    assert actual_container_id == custom_id


def test_dismiss_modal_rejects_nonexistent_path_and_notifies(mocker: MockerFixture):
    """Bootstrap dismissal rejects nonexistent directories and preserves current selection."""
    tree_structure = {"id": "root-id", "text": "/root_node", "children": []}
    selected_item_id = {
        "aio_id": "test_aio_id",
        "component": "tree",
        "subcomponent": "navlink-item",
        "index": "missing-id",
    }
    mock_set_props = mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.set_props",
    )
    mocker.patch.object(FolderSelector, "resolve_folder", return_value="/root_node/missing")

    result = FolderSelector.dismiss_modal_and_update_selected_folder(
        1,
        selected_item_id,
        tree_structure,
        _bootstrap_settings(),
    )

    assert result == (False, False, no_update)
    mock_set_props.assert_called_once()


def test_dismiss_modal_rejects_non_directory_path_and_notifies(
    tmp_path: Path,
    mocker: MockerFixture,
):
    """Bootstrap dismissal rejects existing file paths."""
    file_path = tmp_path / "file.txt"
    file_path.write_text("test")
    tree_structure = {"id": "root-id", "text": str(tmp_path), "children": []}
    selected_item_id = {
        "aio_id": "test_aio_id",
        "component": "tree",
        "subcomponent": "navlink-item",
        "index": "file-id",
    }
    mock_set_props = mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.set_props",
    )
    mocker.patch.object(FolderSelector, "resolve_folder", return_value=str(file_path))

    result = FolderSelector.dismiss_modal_and_update_selected_folder(
        1,
        selected_item_id,
        tree_structure,
        _bootstrap_settings(),
    )

    assert result == (False, False, no_update)
    mock_set_props.assert_called_once()


def test_dismiss_modal_rejects_path_with_traversal_sequences_and_notifies(
    tmp_path: Path,
    mocker: MockerFixture,
):
    """Bootstrap dismissal rejects paths containing traversal sequences."""
    root = tmp_path / "root"
    root.mkdir()
    target = root / "safe"
    target.mkdir()
    traversing_path = str(root / ".." / root.name / "safe")

    tree_structure = {"id": "root-id", "text": str(root), "children": []}
    selected_item_id = {
        "aio_id": "test_aio_id",
        "component": "tree",
        "subcomponent": "navlink-item",
        "index": "safe-id",
    }
    mock_set_props = mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.set_props",
    )
    mocker.patch.object(FolderSelector, "resolve_folder", return_value=traversing_path)

    result = FolderSelector.dismiss_modal_and_update_selected_folder(
        1,
        selected_item_id,
        tree_structure,
        _bootstrap_settings(),
    )

    assert result == (False, False, no_update)
    mock_set_props.assert_called_once()


def test_validate_bootstrap_selected_path_accepts_valid_directory(tmp_path: Path):
    """Validation helper accepts existing directories without traversal markers."""
    valid_dir = tmp_path / "valid"
    valid_dir.mkdir()

    result = FolderSelector._validate_bootstrap_selected_path(
        str(valid_dir),
        PathValidator.max_path_length(),
    )

    assert result == valid_dir.resolve()


@pytest.mark.parametrize(
    ("selected_folder", "expected_text", "expected_tooltip"),
    [
        (
            "/path/to/folder",
            "Selected folder: /\u200bpath/\u200bto/\u200bfolder",
            "/\u200bpath/\u200bto/\u200bfolder",
        ),
        (None, "No folder selected", ""),
        ("", "No folder selected", ""),
    ],
)
def test_update_display_field(selected_folder: str | None, expected_text: str, expected_tooltip: str):
    """Update the display field text and tooltip label based on selected folder value."""
    text, tooltip = FolderSelector.update_display_field(selected_folder)
    assert text == expected_text
    assert tooltip == expected_tooltip


def test_update_display_field_tooltip_breaks_on_delimiters():
    """Tooltip label inserts zero-width spaces after path delimiters for clean wrapping."""
    path = r"D:\some_dir\file.name-suffix"
    _, tooltip = FolderSelector.update_display_field(path)
    # Every delimiter should be followed by a zero-width space
    for char in "/\\._-":
        if char in path:
            assert f"{char}\u200b" in tooltip


@pytest.mark.parametrize(
    ("n_clicks", "expected"),
    [
        (1, (True, True)),
        (2, (True, True)),
        (10, (True, True)),
    ],
)
def test_clear_selected_folder(n_clicks: int, expected: tuple[bool, bool]):
    """Clear selected folder and selected tree item when clear button is clicked."""
    result = FolderSelector.clear_selected_folder(n_clicks)
    assert result == expected


def test_clear_selected_folder_no_clicks():
    """No clicks when clearing selected folder raises PreventUpdate."""
    with pytest.raises(PreventUpdate):
        FolderSelector.clear_selected_folder(0)


"""----------------------------------------------------------------------------------------------"""
"""Helper Method Tests"""
"""----------------------------------------------------------------------------------------------"""


def test_get_folders_structure_returns_empty_dict_for_none_path():
    """If the provided path is None, the method should return an empty dictionary."""
    result = FolderSelector.get_folders_structure(None)
    assert result == {}


def test_get_folders_structure(tmp_path: Path):
    """Return a nested dict representing folder structure, ignoring files and hidden folders."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "folder1").mkdir()
    (root / "folder2").mkdir()
    (root / "folder1" / "subfolder1").mkdir()
    (root / "file.txt").write_text("test")
    (root / ".hidden_folder").mkdir()

    result = FolderSelector.get_folders_structure(str(root), _as_absolute_path=True)

    root_path = str(root)
    folder1_path = str(root / "folder1")
    folder2_path = str(root / "folder2")
    subfolder1_path = str(root / "folder1" / "subfolder1")

    expected = {
        "id": str(uuid.uuid3(uuid.NAMESPACE_URL, root_path)),
        "text": str(root),
        "children": [
            {
                "id": str(uuid.uuid3(uuid.NAMESPACE_URL, folder1_path)),
                "text": "folder1",
                "children": [
                    {
                        "id": str(uuid.uuid3(uuid.NAMESPACE_URL, subfolder1_path)),
                        "text": "subfolder1",
                        "children": [],
                    },
                ],
            },
            {
                "id": str(uuid.uuid3(uuid.NAMESPACE_URL, folder2_path)),
                "text": "folder2",
                "children": [],
            },
        ],
    }

    assert result == expected


def test_get_folders_structure_empty_directory(tmp_path: Path):
    """Empty directory yields no children in folder structure."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    result = FolderSelector.get_folders_structure(str(empty_dir))

    assert result["children"] == []


def test_get_folders_structure_skips_symlink_directories(tmp_path: Path):
    """Symlinked directories are excluded from the generated tree."""
    root = tmp_path / "root"
    root.mkdir()

    real_dir = root / "real_dir"
    real_dir.mkdir()

    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()

    symlink_dir = root / "symlink_dir"
    try:
        symlink_dir.symlink_to(outside_dir, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks are not supported in this environment")

    result = FolderSelector.get_folders_structure(str(root), _as_absolute_path=True)

    child_names = [child["text"] for child in result["children"]]
    assert "real_dir" in child_names
    assert "symlink_dir" not in child_names


def test_get_folders_structure_respects_max_depth(tmp_path: Path):
    """Tree generation truncates children when the maximum depth is reached."""
    root = tmp_path / "root"
    deepest = root / "a" / "b" / "c"
    deepest.mkdir(parents=True)

    result = FolderSelector.get_folders_structure(
        str(root),
        max_depth=2,
        max_children_per_node=500,
    )

    first_child = result["children"][0]
    second_child = first_child["children"][0]
    assert second_child["children"] == []
    # Verify description is added for depth truncation
    assert "description" in second_child
    assert "subfolders not shown" in second_child["description"]
    assert "maximum depth" in second_child["description"]


def test_get_folders_structure_respects_max_children_per_node(tmp_path: Path):
    """Tree generation caps the number of child folders per node."""
    root = tmp_path / "root"
    root.mkdir()
    for index in range(3):
        (root / f"child_{index}").mkdir()

    result = FolderSelector.get_folders_structure(
        str(root),
        max_depth=10,
        max_children_per_node=2,
    )

    assert len(result["children"]) == 2
    # Verify description is added for children truncation
    assert "description" in result
    assert "1 more subfolder not shown" in result["description"]
    assert "maximum of 2 subfolders reached" in result["description"]


def test_get_folders_structure_adds_description_for_depth_truncation(tmp_path: Path):
    """Description is added when depth cap is hit."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "child").mkdir()
    ((root / "child") / "grandchild").mkdir()

    result = FolderSelector.get_folders_structure(
        str(root),
        max_depth=1,
        max_children_per_node=500,
    )

    assert "description" in result["children"][0]
    assert "subfolders not shown" in result["children"][0]["description"]
    assert "maximum depth" in result["children"][0]["description"]


def test_get_folders_structure_description_includes_correct_count(tmp_path: Path):
    """Description shows correct count of excluded subfolders."""
    root = tmp_path / "root"
    root.mkdir()
    # Create 5 children, but limit to 2
    for index in range(5):
        (root / f"child_{index}").mkdir()

    result = FolderSelector.get_folders_structure(
        str(root),
        max_depth=10,
        max_children_per_node=2,
    )

    assert len(result["children"]) == 2
    assert "description" in result
    # 3 more subfolders are hidden (5 - 2 = 3)
    assert "3 more subfolders not shown" in result["description"]


def test_get_folders_structure_singular_subfolder_in_description(tmp_path: Path):
    """Description uses singular 'subfolder' when exactly one is hidden."""
    root = tmp_path / "root"
    root.mkdir()
    # Create 2 children, but limit to 1 (1 will be hidden)
    (root / "child_0").mkdir()
    (root / "child_1").mkdir()

    result = FolderSelector.get_folders_structure(
        str(root),
        max_depth=10,
        max_children_per_node=1,
    )

    assert len(result["children"]) == 1
    assert "description" in result
    # Should use singular "subfolder"
    assert "1 more subfolder not shown" in result["description"]


def test_get_folders_structure_no_recursion_error_deep_nesting(tmp_path: Path):
    """Deep trees complete when bounded by max_depth."""
    current = tmp_path / "root"
    current.mkdir()
    for index in range(20):
        current = current / f"level_{index}"
        current.mkdir()

    result = FolderSelector.get_folders_structure(
        str(tmp_path / "root"),
        max_depth=5,
        max_children_per_node=500,
    )

    node = result
    while node["children"]:
        node = node["children"][0]

    assert node["text"].endswith("level_4")


def test_resolve_folder():
    """Resolve folder paths from tree node ids correctly."""
    tree_structure = {
        "id": "root-id",
        "text": "/root_node",
        "children": [
            {
                "id": "folder1-id",
                "text": "folder1",
                "children": [
                    {"id": "subfolder1-id", "text": "subfolder1", "children": []},
                ],
            },
            {"id": "folder2-id", "text": "folder2", "children": []},
        ],
    }

    result = FolderSelector.resolve_folder("root-id", tree_structure)
    assert result == "/root_node"

    result = FolderSelector.resolve_folder("folder1-id", tree_structure)
    assert result == f"/root_node{os.sep}folder1"

    result = FolderSelector.resolve_folder("subfolder1-id", tree_structure)
    assert result == f"/root_node{os.sep}folder1{os.sep}subfolder1"

    result = FolderSelector.resolve_folder("folder2-id", tree_structure)
    assert result == f"/root_node{os.sep}folder2"

    result = FolderSelector.resolve_folder("non-existent-id", tree_structure)
    assert result is None


def test_get_folder_id():
    """Resolve tree node ids from folder paths correctly."""
    tree_structure = {
        "id": "root-id",
        "text": "/root_node",
        "children": [
            {
                "id": "folder1-id",
                "text": "folder1",
                "children": [
                    {"id": "subfolder1-id", "text": "subfolder1", "children": []},
                ],
            },
            {"id": "folder2-id", "text": "folder2", "children": []},
        ],
    }

    assert FolderSelector.get_folder_id("/root_node", tree_structure) == "root-id"
    assert FolderSelector.get_folder_id(f"/root_node{os.sep}folder1", tree_structure) == "folder1-id"
    assert (
        FolderSelector.get_folder_id(
            f"/root_node{os.sep}folder1{os.sep}subfolder1",
            tree_structure,
        )
        == "subfolder1-id"
    )
    assert FolderSelector.get_folder_id("/not/found", tree_structure) is None


def test_ask_directory_with_tkinter(mocker: MockerFixture):
    """Askdirectory uses tkinter properly and returns selected path."""
    mock_root = mocker.MagicMock()
    mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.tkinter.Tk",
        return_value=mock_root,
    )
    mock_filedialog = mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.filedialog",
    )
    mock_filedialog.askdirectory.return_value = "/selected/path"

    result = FolderSelector.ask_directory_with_tkinter(topmost=True)

    assert result == "/selected/path"
    mock_root.withdraw.assert_called_once()
    mock_root.wm_attributes.assert_called_once_with("-topmost", 1)
    mock_filedialog.askdirectory.assert_called_once()
    mock_root.destroy.assert_called_once()


def test_ask_directory_with_tkinter_cancel_returns_none(mocker: MockerFixture):
    """Empty tkinter selection (cancel) should be normalized to None."""
    mock_root = mocker.MagicMock()
    mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.tkinter.Tk",
        return_value=mock_root,
    )
    mock_filedialog = mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.filedialog",
    )
    mock_filedialog.askdirectory.return_value = ""

    result = FolderSelector.ask_directory_with_tkinter(topmost=True)

    assert result is None
    mock_root.withdraw.assert_called_once()
    mock_root.wm_attributes.assert_called_once_with("-topmost", 1)
    mock_filedialog.askdirectory.assert_called_once()
    mock_root.destroy.assert_called_once()


def test_ask_directory_with_tkinter_not_topmost(mocker: MockerFixture):
    """When not topmost, askdirectory should not set topmost attribute."""
    mock_root = mocker.MagicMock()
    mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.tkinter.Tk",
        return_value=mock_root,
    )
    mock_filedialog = mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.filedialog",
    )
    mock_filedialog.askdirectory.return_value = "/selected/path"

    result = FolderSelector.ask_directory_with_tkinter(topmost=False)

    assert result == "/selected/path"
    mock_root.wm_attributes.assert_not_called()


def test_ask_directory_with_tkinter_tkinter_not_available(mocker: MockerFixture):
    """When tkinter is unavailable, helper raises a RuntimeError."""
    mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.TKINTER_AVAILABLE",
        new=False,
    )

    with pytest.raises(RuntimeError, match="tkinter is not available"):
        FolderSelector.ask_directory_with_tkinter(topmost=False)


def test_ask_directory_with_tkinter_exception_cleanup(mocker: MockerFixture):
    """Ensure cleanup (destroy) is called even when askdirectory raises."""
    mock_root = mocker.MagicMock()
    mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.tkinter.Tk",
        return_value=mock_root,
    )
    mock_filedialog = mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.filedialog",
    )
    mock_filedialog.askdirectory.side_effect = RuntimeError("Dialog error")

    with pytest.raises(RuntimeError, match="Dialog error"):
        FolderSelector.ask_directory_with_tkinter(topmost=True)

    mock_root.destroy.assert_called_once()


def test_ask_directory_with_tkinter_withdraw_exception_cleanup(mocker: MockerFixture):
    """Ensure cleanup (destroy) is called even when withdraw raises."""
    mock_root = mocker.MagicMock()
    mock_root.withdraw.side_effect = RuntimeError("Withdraw failed")
    mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.tkinter.Tk",
        return_value=mock_root,
    )
    mocker.patch("ansys.solutions.dash_super_components.folder_selector.filedialog")

    with pytest.raises(RuntimeError, match="Withdraw failed"):
        FolderSelector.ask_directory_with_tkinter(topmost=False)

    mock_root.destroy.assert_called_once()


def test_ask_directory_with_tkinter_wm_attributes_exception_cleanup(mocker: MockerFixture):
    """Ensure cleanup (destroy) is called even when wm_attributes raises."""
    mock_root = mocker.MagicMock()
    mock_root.wm_attributes.side_effect = RuntimeError("WM attributes failed")
    mocker.patch(
        "ansys.solutions.dash_super_components.folder_selector.tkinter.Tk",
        return_value=mock_root,
    )
    mocker.patch("ansys.solutions.dash_super_components.folder_selector.filedialog")

    with pytest.raises(RuntimeError, match="WM attributes failed"):
        FolderSelector.ask_directory_with_tkinter(topmost=True)

    mock_root.destroy.assert_called_once()


def test_generate_tree(mocker: MockerFixture):
    """generate_tree should instantiate Tree with provided folder items."""
    folders_structure = {
        "id": "root-id",
        "text": "/root_node",
        "children": [],
    }

    mock_tree_class = mocker.patch("ansys.solutions.dash_super_components.folder_selector.Tree")
    mock_tree_instance = mocker.MagicMock()
    mock_tree_class.return_value = mock_tree_instance

    result = FolderSelector.generate_tree("test-aio-id", folders_structure)

    mock_tree_class.assert_called_once_with(
        aio_id="test-aio-id",
        items=[folders_structure],
        default_icon=create_base64_svg_src(IconNames.MATERIAL_FOLDER),
    )
    assert result is mock_tree_instance


def test_generate_tree_with_none(mocker: MockerFixture):
    """generate_tree handles None input by passing empty items list to Tree."""
    mock_tree_class = mocker.patch("ansys.solutions.dash_super_components.folder_selector.Tree")
    mock_tree_instance = mocker.MagicMock()
    mock_tree_class.return_value = mock_tree_instance

    result = FolderSelector.generate_tree("test-aio-id", None)

    mock_tree_class.assert_called_once_with(
        aio_id="test-aio-id",
        items=[],
        default_icon=create_base64_svg_src(IconNames.MATERIAL_FOLDER),
    )
    assert result is mock_tree_instance


"""----------------------------------------------------------------------------------------------"""
"""Tests For FolderSelectorMode Class"""
"""----------------------------------------------------------------------------------------------"""


def test_folder_selector_mode_values():
    """Verify FolderSelectorMode enum values are correct strings."""
    assert FolderSelectorMode.BOOTSTRAP.value == "bootstrap"
    assert FolderSelectorMode.TKINTER.value == "tkinter"
