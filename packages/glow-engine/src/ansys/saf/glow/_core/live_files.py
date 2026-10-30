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

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys
import threading
from typing import TYPE_CHECKING, Any, Self

from pydantic_core import core_schema

from ansys.saf.glow._storage.os import INVALID_CHARACTERS, is_filepath_invalid

if TYPE_CHECKING:
    from types import TracebackType

    from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
    from pydantic.json_schema import JsonSchemaValue

if sys.platform == "win32":
    import msvcrt

    def _try_lock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

    def _unlock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _try_lock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


LIVE_FILE_LOCKS_DIR_NAME = ".live_file_locks"


class LiveFileOwnershipError(RuntimeError):
    """Raised when a transaction accesses the path of a LiveFile owned by another running transaction."""


class LiveFileOwnership:
    """Set of LiveFiles owned by a single running transaction.

    A LiveFile becomes owned by the first transaction accessing its ``path`` and stays
    owned until that transaction ends. Use this class as a context manager spanning the
    transaction so that ownership is relinquished when it exits, whether it succeeds or fails.
    Ownership is backed by an OS-level
    lock on a sidecar file in the project files directory so that it is enforced across the
    threads and processes executing transactions, and is released automatically if the owning
    process dies.
    """

    def __init__(self) -> None:
        self._locks: dict[Path, int] = {}
        self._mutex = threading.Lock()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._release_all()

    def acquire(self, project_files_dir: Path, relative_path: Path) -> None:
        """Take ownership of a LiveFile, or do nothing if this transaction already owns it.

        Raises
        ------
        LiveFileOwnershipError
            If the LiveFile is owned by another running transaction.
        """
        key = os.path.normcase(relative_path.as_posix()).encode("utf-8")
        lock_path = project_files_dir / LIVE_FILE_LOCKS_DIR_NAME / f"{hashlib.sha256(key).hexdigest()}.lock"
        with self._mutex:
            if lock_path in self._locks:
                return
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
            try:
                _try_lock(fd)
            except OSError:
                os.close(fd)
                raise LiveFileOwnershipError(
                    f"LiveFile '{relative_path.as_posix()}' is owned by another running transaction "
                    "and its path cannot be accessed until that transaction ends.",
                ) from None
            self._locks[lock_path] = fd

    def _release_all(self) -> None:
        """Relinquish ownership of all LiveFiles owned by this transaction."""
        with self._mutex:
            for fd in self._locks.values():
                try:
                    _unlock(fd)
                except OSError:
                    pass
                finally:
                    os.close(fd)
            self._locks.clear()


class LiveFile(str):
    """Relative path to a file in a GLOW project.

    This class represents a file that can be read while being written. It only
    carries and validates the relative path; concrete subclasses resolve it to a
    location on disk.
    """

    def __new__(cls, value: str):
        return super().__new__(cls, value)

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(cls._validate, handler(str))

    @classmethod
    def _validate(cls, value: str):
        if not isinstance(value, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("String is required.")
        if ".." in value:
            raise ValueError(f".. is not allowed inside a {cls.__name__} field.")
        if Path(value).is_absolute():
            raise ValueError(f"Absolute path: '{value}' is not allowed in a {cls.__name__} field.")
        if value in {"", "."}:
            raise ValueError(f"A {cls.__name__} must refer to a file path.")
        if value.endswith(("/", "\\")):
            raise ValueError(f"A {cls.__name__} must refer to a file and cannot end with a path separator.")
        if is_filepath_invalid(value):
            raise ValueError(
                f"A {cls.__name__} can't contain any of the following characters: {' '.join(INVALID_CHARACTERS)}",
            )
        if any(char in value for char in "[]"):
            raise ValueError(f"A {cls.__name__} cannot contain wildcard characters like '[' or ']'.")
        return cls(value)

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        schema: core_schema.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        json_schema = handler(schema)
        json_schema.update(
            type="string",
            examples=["logs/runtime.log", "outputs/convergence.csv"],
        )
        return json_schema

    def __repr__(self):
        return f"LiveFile({super().__repr__()})"

    @property
    def _relative_path(self) -> Path:
        return Path(str(self))

    @property
    def name(self) -> str:
        return self._relative_path.name

    @property
    def _absolute_path(self) -> Path:
        raise NotImplementedError()

    def read_text(self, encoding: str = "utf-8") -> str:
        return self._absolute_path.read_text(encoding=encoding)

    def read_bytes(self) -> bytes:
        return self._absolute_path.read_bytes()

    def exists(self) -> bool:
        return self._absolute_path.exists()


class TransactionLiveFile(LiveFile):
    """Transaction-scoped view of a file for the current project.

    The relative path is resolved from ``project_files_dir / project_id``. This class
    provides read access and exposes the resolved filesystem path through ``path``.

    Only one transaction can write to a LiveFile at a time. The first transaction accessing
    ``path`` becomes the owner of the LiveFile until it ends. Reading through ``read_text``,
    ``read_bytes`` or ``exists`` does not require ownership.
    """

    def __new__(cls, value: str, project_files_dir: Path, ownership: LiveFileOwnership):
        return super().__new__(cls, value)

    def __init__(self, value: str, project_files_dir: Path, ownership: LiveFileOwnership):
        self._project_files_dir = project_files_dir
        self._ownership = ownership

    @property
    def _absolute_path(self) -> Path:
        return self._project_files_dir / self._relative_path

    @property
    def path(self) -> Path:
        """Resolved filesystem path. Accessing it takes ownership of the LiveFile.

        Raises
        ------
        LiveFileOwnershipError
            If the LiveFile is owned by another running transaction.
        """
        self._ownership.acquire(self._project_files_dir, self._relative_path)
        return self._absolute_path


class LiveFileProxy(LiveFile):
    """Client-side read-only view of a LiveFile.

    The relative path is resolved from ``project_files_dir / project_id``. This class
    allows reading file content and does not expose the resolved filesystem path.
    """

    def __new__(cls, value: str, project_files_dir: Path):
        return super().__new__(cls, value)

    def __init__(self, value: str, project_files_dir: Path):
        self._project_files_dir = project_files_dir

    @property
    def _absolute_path(self) -> Path:
        return self._project_files_dir / self._relative_path
