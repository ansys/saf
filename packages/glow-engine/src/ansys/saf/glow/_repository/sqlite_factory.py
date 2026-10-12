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

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import datetime
import logging
import os
from pathlib import Path
import platform
import sqlite3
import sys

import psutil
from sqlalchemy.ext.asyncio import AsyncSession

from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._repository.abstract_repository import AbstractRepositorySession
from ansys.saf.glow._repository.relational import RelationalSession, RelationalSessionFactory
from ansys.saf.glow._repository.sqlite import SqliteSession
from ansys.saf.glow._repository.sqlite_adapters import (
    adapt_date_iso,
    adapt_datetime_iso,
    convert_date,
    convert_datetime,
    convert_timestamp,
)
from ansys.saf.glow._server.solution import SolutionService

logger = logging.getLogger(__name__)


if sys.version_info >= (3, 12):  # noqa: UP036
    # The default datetime adapter is deprecated as of Python 3.12, we have to register our own adapters.
    sqlite3.register_adapter(datetime.date, adapt_date_iso)
    sqlite3.register_adapter(datetime.datetime, adapt_datetime_iso)
    sqlite3.register_converter("date", convert_date)
    sqlite3.register_converter("datetime", convert_datetime)
    sqlite3.register_converter("timestamp", convert_timestamp)


class SqliteSessionFactory(RelationalSessionFactory):
    def __init__(self, settings: Settings, solution_service: SolutionService) -> None:
        if self._running_in_multi_worker_mode():
            raise RuntimeError(
                "GLOW API server is running in multi-worker mode, "
                "which is not supported by the SQLite integration. "
                "Either use a single worker or a different type of database.",
            )

        location = settings.computed_database_location
        if isinstance(location, Path):
            location.parent.mkdir(parents=True, exist_ok=True)
            if not location.exists():
                sqlite3.connect(location).close()
                assert location.exists()  # noqa: S101  #nosec
                assert os.access(location, os.W_OK)  # noqa: S101  #nosec
                logger.debug(f"Created SQLite database at {location}")
            if platform.system() == "Linux":
                database_url = location.as_uri().replace("file:", "sqlite+aiosqlite:/", 1)
            else:
                database_url = f"sqlite+aiosqlite:///{location.as_posix()}"
            logger.debug(f"Using SQLite database at {database_url}")
        else:
            raise ValueError(f"Invalid database location. Got: {location}, type: {type(location)}")

        self._solution_service = solution_service
        super().__init__(database_url)
        self._old_table_name = location.stem
        self._settings = settings

    @classmethod
    def _running_in_multi_worker_mode(cls) -> bool:
        this_process = psutil.Process()
        this_process_cmd_line = this_process.cmdline()

        if "--multiprocessing-fork" in this_process_cmd_line:
            parent_process = this_process.parent()
            # perhaps this might be paranoid but this is a reasonable check to make
            # despite what sonar cube says...
            if parent_process is not None:
                parent_process_cmd_line = parent_process.cmdline()
                if "uvicorn" in parent_process_cmd_line[1]:
                    return True
        return False

    @asynccontextmanager
    async def get_session_implementation(
        self,
    ) -> AsyncGenerator[AbstractRepositorySession]:
        def construct_session(session: AsyncSession) -> RelationalSession:
            return SqliteSession(session, self._solution_service, self._settings)

        async with super().get_relational_session(construct_session) as session:
            yield session
