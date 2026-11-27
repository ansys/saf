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

import os
from pathlib import Path
import sys

from ansys.saf.glow.solution.products.config import (
    IProductInstanceConfiguration,
    IProductInstanceVersionConfiguration,
    ISoftware,
    ServiceType,
    Software,
)


class MockHTTPInstanceVersionConfiguration(IProductInstanceVersionConfiguration):
    def __init__(self, version: str) -> None:
        self._version = version

    @property
    def service_name(self) -> str:
        return "http"

    @property
    def execution_command(self) -> str:
        return (
            f"${{EXECUTABLE}} -m tests.mocks.solutions.minimal_pim_solution.custom_product ${{PORT}} "
            f"--version {self._version}"
        )

    @property
    def exe_path_for_pim(self) -> str:
        return sys.executable

    @property
    def environment(self) -> dict[str, str]:
        root = os.environ.get("APPDATA" if sys.platform == "win32" else "XDG_DATA_HOME", "~/.local/share")
        return {"SAF_MOCK_PRODUCT_ALLOWED_ROOT": str(Path(root).expanduser().resolve())}

    @property
    def software_requirements(self) -> list[ISoftware]:
        return [Software(name="Python", version=f"{sys.version_info.major}.{sys.version_info.minor}")]

    @property
    def service_type(self) -> ServiceType:
        return ServiceType.HTTP


class MockHTTPInstanceConfiguration(IProductInstanceConfiguration):
    @property
    def product_name(self) -> str:
        return "custom-http-product"

    @property
    def versions(self) -> list[str]:
        return ["1", "2", "222"]

    def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
        return MockHTTPInstanceVersionConfiguration(version)
