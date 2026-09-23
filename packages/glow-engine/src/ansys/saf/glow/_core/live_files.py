# ©2022, ANSYS Inc. Unauthorized use, distribution or duplication is prohibited.
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic_core import core_schema

from ansys.saf.glow._storage.os import INVALID_CHARACTERS, is_filepath_invalid

if TYPE_CHECKING:
    from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
    from pydantic.json_schema import JsonSchemaValue


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
    """

    def __new__(cls, value: str, project_files_dir: Path):
        return super().__new__(cls, value)

    def __init__(self, value: str, project_files_dir: Path):
        self._project_files_dir = project_files_dir

    @property
    def _absolute_path(self) -> Path:
        return self._project_files_dir / self._relative_path

    @property
    def path(self) -> Path:
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
