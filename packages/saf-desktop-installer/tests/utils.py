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

from collections.abc import Generator
from contextlib import contextmanager
import getpass
import os
from pathlib import Path
import platform
import subprocess
import sys


def get_appdata_directory() -> str:
    if platform.system() == "Windows":
        return Path(os.environ["APPDATA"]).as_posix()
    else:
        return str(Path(os.getenv("XDG_DATA_HOME", "~/.local/share")).expanduser())


def run_icacls(args: list[str]) -> str:
    """Helper to run icacls command."""
    result = subprocess.run(
        ["icacls"] + args,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"icacls error: {result.stderr.strip()}")
    return result.stdout.strip()


@contextmanager
def remove_directory_write_permissions(path: Path) -> Generator[None, None, None]:
    """
    Context manager that makes a directory (and its contents) without write access
    for the current user, then restores permissions afterwards.

    Args:
        path: Directory path.
    """
    if platform.system() == "Windows":
        current_user = getpass.getuser()
        try:
            # Deny write permissions to current user on the directory only.
            run_icacls([str(path), "/deny", f"{current_user}:(W,D)"])
            yield
        finally:
            try:
                run_icacls([str(path), "/remove:d", current_user])
            except Exception as e:
                print(f"Warning: Failed to restore permissions: {e}")
    else:
        original_mode = path.stat().st_mode
        try:
            # Remove write permission for owner, group, and others
            path.chmod(original_mode & ~0o222)
            yield
        finally:
            path.chmod(original_mode)


@contextmanager
def deny_directory_access(path: Path) -> Generator[None, None, None]:
    """Deny the current user listing/reading a directory and its contents, then restore it."""
    if sys.platform == "win32":
        current_user = getpass.getuser()
        # Full deny (F) would also deny WRITE_DAC, preventing the ACE removal below.
        run_icacls([str(path), "/deny", f"{current_user}:(OI)(CI)(RD,RA)"])
        try:
            yield
        finally:
            run_icacls([str(path), "/remove:d", current_user])
    else:
        assert os.geteuid() != 0, "Root bypasses file permissions, so access cannot be denied."
        original_mode = path.stat().st_mode
        path.chmod(0)
        try:
            yield
        finally:
            path.chmod(original_mode)
