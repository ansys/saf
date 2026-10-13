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

import logging
import os
from typing import Generic, TypeVar

from ansys.saf.desktop.orchestrator._config.schema import (
    GLOW_API_HOST,
    GLOW_API_PORT,
    LOCALHOST_IP,
    PORTAL_UI_HOST,
    PORTAL_UI_PORT,
)
from ansys.saf.glow.client import Client
from ansys.saf.glow.solution import Solution

T = TypeVar("T", bound=Solution)
logger = logging.getLogger(__name__)


class StreamlitClient(Generic[T]):
    # TODO: unify with DashClient? There is nothing about Streamlit in this class

    _singleton: Client[T]

    @classmethod
    def initialize(
        cls,
        solution_type: type[T],
        storage_scope_factory: None = None,  # pyright: ignore
    ) -> None:
        api_host = os.getenv(GLOW_API_HOST, LOCALHOST_IP)
        solution_api_port = os.getenv(GLOW_API_PORT)
        cls._singleton = Client(
            solution_type,
            f"http://{api_host}:{solution_api_port}",
            storage_scope_factory,  # pyright: ignore[reportUnknownArgumentType]
        )

    @classmethod
    def get_project(cls, pathname: str) -> T:
        if pathname.startswith("/"):
            pathname = pathname[1:]
        logger.info(f"accessing {pathname}")
        return cls._singleton.get_project(pathname)

    @classmethod
    def get_portal_ui_url(cls) -> str | None:
        if portal_ui_port := os.getenv(PORTAL_UI_PORT):
            portal_ui_host = os.getenv(PORTAL_UI_HOST, LOCALHOST_IP)
            return f"http://{portal_ui_host}:{portal_ui_port}"
        return None
