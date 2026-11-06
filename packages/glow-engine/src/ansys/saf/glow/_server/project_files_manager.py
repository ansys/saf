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

import asyncio
from datetime import datetime
import json
from pathlib import Path
import platform
import shutil
from stat import S_IFREG
from typing import TYPE_CHECKING, Any
import zipfile

import aiofiles
from stream_zip import ZIP_64, AsyncMemberFile

from ansys.saf.glow._core.live_files import LIVE_FILE_LOCKS_DIR_NAME
from ansys.saf.glow._core.project_files_locator import ProjectFilesLocator
from ansys.saf.glow._server.exceptions import BadRequestError, ForbiddenError, NotFoundError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from fastapi import UploadFile

    from ansys.saf.glow._server.schemas import ProjectInfo


class ProjectFilesManager:
    def __init__(
        self,
        project_files_directory: Path,
    ) -> None:
        self._project_files_directory = project_files_directory
        self._project_files_directory.mkdir(parents=True, exist_ok=True)

    def _raise_file_not_found(self, relative_filepath: str):
        raise NotFoundError(detail=f"Cannot find the file specified: '{relative_filepath}'.")

    def _raise_bad_filepath_request(self, filepath: str):
        raise BadRequestError(detail=f"The filepath: '{filepath}' is incorrect.")

    def create_project_files_dir(self, project_id: str) -> Path:
        project_files_dir = self.get_project_files_dir(project_id)
        project_files_dir.mkdir(parents=True, exist_ok=True)
        return project_files_dir

    def import_project_files_dir(self, project_id: str, dir_to_import: Path) -> Path:
        project_files_dir = self.get_project_files_dir(project_id)
        project_files_dir.parent.mkdir(parents=True, exist_ok=True)
        if dir_to_import.exists():
            shutil.move(dir_to_import, project_files_dir)
        else:
            # We create an empty project_files_dir so that it can be used in migration transformations
            # without having to check if it exists.
            project_files_dir.mkdir(exist_ok=True)
        return project_files_dir

    def _get_platform_buffer_size(self) -> int:
        # These values are extracted from shutil.copyfileobj, which takes into account
        # the difference in ideal buffer size between Windows and other operating systems.
        return 1024 * 1024 if platform.system() == "Windows" else 64 * 1024

    async def _async_read_file(self, file_path: Path, read_bufsize: int):
        async with aiofiles.open(file_path, "rb") as f:
            while True:
                part = await f.read(read_bufsize)
                if not part:
                    break
                yield part

    async def _async_read_bytes(self, data: bytes, read_bufsize: int):
        for i in range(0, len(data), read_bufsize):
            yield data[i : i + read_bufsize]
            await asyncio.sleep(0)  # yield control to the loop

    def create_async_project_files_generator(
        self,
        project_info: ProjectInfo,
        project_as_dict: dict[str, Any],
    ) -> Callable[[], AsyncGenerator[AsyncMemberFile, None]]:
        project_files_dir = self.get_project_files_dir(project_info.project_id)
        files_path = [
            item
            for item in project_files_dir.rglob("*")
            if ".method_logs" not in str(item)
            and ".asset_cache" not in str(item)
            and LIVE_FILE_LOCKS_DIR_NAME not in item.parts
            and item.is_file()
        ]

        async def _async_project_file_generator():
            project_files_dir = self.get_project_files_dir(project_info.project_id)
            read_bufsize = self._get_platform_buffer_size()
            for file_path in files_path:
                file_rel_path = file_path.relative_to(project_files_dir.parent)
                new_file_rel_path = Path(project_info.display_name) / Path(*file_rel_path.parts[1:])
                yield (
                    new_file_rel_path.as_posix(),
                    datetime.now(),
                    S_IFREG | 0o644,
                    ZIP_64,
                    self._async_read_file(file_path, read_bufsize),
                )
            yield (
                f"{project_info.display_name}.sap",
                datetime.now(),
                S_IFREG | 0o644,
                ZIP_64,
                self._async_read_bytes(json.dumps(project_as_dict).encode("utf-8"), read_bufsize),
            )

        return _async_project_file_generator

    def remove_project_files_dir(self, project_id: str):
        project_files_dir = self.get_project_files_dir(project_id)
        if project_files_dir.exists():
            shutil.rmtree(project_files_dir)

    async def write_file_to(self, upload_file: UploadFile, destination: str) -> None:
        try:
            # when not copying files, upload_file.file.name can actually be an integer
            if (
                upload_file.file.name
                and isinstance(upload_file.file.name, str)
                and upload_file.file.name.endswith(".glwzp")
            ):
                destination_path = Path(destination.replace(".glwzp", "")).parent
                with zipfile.ZipFile(upload_file.file, "r") as zip_ref:
                    zip_ref.extractall(destination_path)
            else:
                async with aiofiles.open(destination, "wb") as out_file:
                    copy_bufsize = self._get_platform_buffer_size()
                    while content := await upload_file.read(copy_bufsize):
                        await out_file.write(content)
        except PermissionError:
            raise ForbiddenError(detail=f"Permission denied: '{destination}'") from None

    def get_project_files_dir(self, project_id: str) -> Path:
        return ProjectFilesLocator.get_project_files_dir(self._project_files_directory, project_id)

    def get_project_files_root(self) -> Path:
        return self._project_files_directory
