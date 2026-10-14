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


"""Provides a validation mechanism for Path strings."""

import os
from pathlib import Path
import platform


class PathError(Exception):
    """Base Error class for Path Errors.

    Parameters
    ----------
    *args : object
        Forwarded to :class:`Exception`.
    """

    def __init__(self, *args):
        """Initialize PathError."""
        super().__init__(*args)


class PathIsTooLongError(PathError):
    """Raised when a path exceeds the maximum allowed length for the current system.

    Parameters
    ----------
    max_length : int
        The maximum allowed path length.
    path : str
        The path that exceeded the limit.

    Attributes
    ----------
    path : str
        The path that triggered the error.
    """

    def __init__(self, max_length, path: str):
        """Initialize PathIsTooLongError."""
        error_message = (
            "The path exceeds the maximum length of " + str(max_length) + " characters allowed on this system. "
        )
        error_message += "Please move your assets on a shallower position"
        super().__init__(error_message)
        self.path = path


class PathDoesNotExistError(PathError):
    """Raised when a path does not exist on the file system.

    Parameters
    ----------
    path : str
        The path that does not exist.

    Attributes
    ----------
    path : str
        The path that triggered the error.
    """

    def __init__(self, path: str):
        """Initialize PathDoesNotExistError."""
        error_message = (
            "The path does not exist on this system. Check for misspellings or verify possible race conditions"
        )
        super().__init__(error_message)
        self.path = path


class PathValidator:
    """Validates a path string against system constraints.

    Parameters
    ----------
    path_as_str : str
        The path string to validate.

    Attributes
    ----------
    path_as_str : str
        The path string provided at construction time.
    """

    def __init__(self, path_as_str: str):
        self.path_as_str = path_as_str

    def validate(
        self,
        max_path_length: int | None = None,
        check_existence: bool = True,
    ) -> Path | PathIsTooLongError | PathDoesNotExistError:
        """Validate the stored path string.

        Checks that the path length does not exceed *max_path_length* and,
        optionally, that the path exists on the file system.

        Parameters
        ----------
        max_path_length : int, optional
            Maximum allowed path length in characters. Defaults to the value
            returned by :meth:`max_path_length`.
        check_existence : bool, optional
            If ``True``, verify that the path exists. Default is ``True``.

        Returns
        -------
        Path
            A resolved :class:`~pathlib.Path` object when the path is valid.
        PathIsTooLongError
            When the path exceeds *max_path_length*.
        PathDoesNotExistError
            When *check_existence* is ``True`` and the path does not exist.
        """
        if not max_path_length:
            max_path_length = self.max_path_length()

        if len(self.path_as_str) > max_path_length:
            return PathIsTooLongError(max_path_length, self.path_as_str)

        path = Path(self.path_as_str)
        if check_existence and not path.exists():
            return PathDoesNotExistError(self.path_as_str)
        return path

    @classmethod
    def max_path_length(cls) -> int:
        """Compute the maximum allowed path length for the current platform.

        Returns
        -------
        int
            Maximum path length in characters: ``250`` on Windows, the
            value of ``PC_PATH_MAX`` on Unix, or ``4096`` as a fallback.
        """
        if platform.system() == "Windows":
            return 250
        else:
            # Use pathconf on Unix systems, with fallback
            try:
                return os.pathconf(".", "PC_PATH_MAX")  # type: ignore[attr-defined]
            except (AttributeError, OSError, ValueError):
                return 4096  # Common default for many Unix systems
