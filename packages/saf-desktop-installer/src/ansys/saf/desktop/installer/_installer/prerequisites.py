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

from pathlib import Path
import random
import shutil
import tempfile


def _get_registry_str_value(hkey: int, subkey: str, value_name: str) -> str:
    # conditional import to avoid issues on non-Windows platforms
    import winreg

    try:
        with winreg.OpenKey(hkey, subkey) as key:  # type: ignore
            value, _ = winreg.QueryValueEx(key, value_name)  # type: ignore
            return str(value) if value else ""  # type: ignore
    except (FileNotFoundError, OSError, PermissionError):
        return ""


WEBVIEW2_ERROR_MSG = (
    "[ERROR] Microsoft Edge WebView2 Runtime is not installed. Please install it from "
    "https://developer.microsoft.com/en-us/microsoft-edge/webview2 "
    "and restart the installer."
)


def is_webview2_installed() -> tuple[bool, str]:
    """Check if WebView2 Runtime is installed."""
    # We follow the approach described in the official documentation:
    # https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution?tabs=dotnetcsharp#detect-if-a-webview2-runtime-is-already-installed

    # conditional import to avoid issues on non-Windows platforms
    import winreg

    webview2_guid = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    registry_paths = (  # type: ignore
        (winreg.HKEY_CURRENT_USER, f"Software\\Microsoft\\EdgeUpdate\\Clients\\{webview2_guid}"),  # type: ignore
        (winreg.HKEY_LOCAL_MACHINE, f"SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\{webview2_guid}"),  # type: ignore
        (winreg.HKEY_LOCAL_MACHINE, f"SOFTWARE\\WOW6432Node\\Microsoft\\EdgeUpdate\\Clients\\{webview2_guid}"),  # type: ignore
    )
    for registry, subpath in registry_paths:  # type: ignore
        version = _get_registry_str_value(registry, subpath, "pv")  # type: ignore
        if version.strip() not in ("", "0.0.0.0"):  # noqa: S104
            return True, version
    return False, ""


LONG_PATHS_ERROR_MSG = (
    "[ERROR] Windows Long Paths is not enabled. Follow the instructions at "
    "https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation "
    "and restart the installer."
)


def is_long_paths_enabled() -> bool:
    """Check if long path support is enabled in Windows."""
    # We do it pragmatically by trying to create a longpath and looking for an error.
    # Another approach would be to check the registry, as described in
    # https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation
    try:
        # creating a single dir with a very long name was unreliable, so we create a nested structure
        tmp_dir = Path(tempfile.gettempdir()) / f"saf_desktop_installer_long_paths_check_{random.randint(0, 100)}"  # noqa: S311
        long_tmp_dir = tmp_dir
        for _ in range(7):  # 38 chars * 7 = 266 chars
            long_tmp_dir = long_tmp_dir / "my_dummy_dir_name_for_long_paths_check"
        long_tmp_dir.mkdir(parents=True)
        shutil.rmtree(tmp_dir)
        return True
    except FileNotFoundError:
        # We are interested in WinError 206 (The filename or extension is too long), but sometimes it throws
        # WinError 3 (The system cannot find the path specified) instead. Hence, we are falling back in catching any
        # FileNotFoundError.
        return False
