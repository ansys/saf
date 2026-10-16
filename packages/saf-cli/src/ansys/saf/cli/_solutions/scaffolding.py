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

import importlib.metadata
from pathlib import Path
import sys

from cookiecutter.main import cookiecutter  # pyright: ignore[reportUnknownVariableType, reportMissingTypeStubs]

from ansys.saf.cli._config.const import DEFAULT_SOLUTION_NAMESPACE, SOLUTION_TEMPLATE_PATH, SOLUTIONS_PRIVATE_PYPI_URL
from ansys.saf.cli._utilities.conversion import (
    namespace_to_path,
    namespace_to_pkg_name,
    to_class_name,
    to_docker_name,
    to_module_name,
    to_package_name,
)
from ansys.saf.cli._utilities.platform import appdata_directory


def create_solution(
    solution_name: str,
    solution_display_name: str,
    ui_framework: str,
    namespace: str = DEFAULT_SOLUTION_NAMESPACE,
) -> None:
    # see docs' glossary for a detailed explanation of every term used in the cookiecutter_kwargs
    solution_module_name = to_module_name(solution_name)
    solution_definition_class_name = to_class_name(solution_name, "Solution")
    solution_package_name = to_package_name(solution_name)
    version = "0.0.0"
    docker_name = to_docker_name(solution_name, version)
    saf_cli_version = importlib.metadata.version("ansys-saf-cli")

    cookiecutter(
        SOLUTION_TEMPLATE_PATH.as_posix(),
        output_dir=Path.cwd().as_posix(),
        no_input=True,
        # overwrite all cookiecutter.json's terms
        extra_context={
            "__solution_name": solution_name,
            "__solution_display_name": solution_display_name,
            "__ui_framework": ui_framework,
            "__solution_module_name": solution_module_name,
            "__solution_definition_class_name": solution_definition_class_name,
            "__solution_package_name": solution_package_name,
            "__solution_namespace": namespace,
            "__solution_namespace_path": namespace_to_path(namespace),
            "__version": version,
            "__docker_name": docker_name,
            "__pkg_name": f"{namespace_to_pkg_name(namespace)}-{solution_package_name}",
            "__pkg_namespace": f"{namespace}.{solution_module_name}",
            "__pkg_path": f"{namespace_to_path(namespace)}/{solution_module_name}",
            "__repository_url": "",
            "__appdata_directory": appdata_directory(),
            "__python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "__saf_cli_version": saf_cli_version,
            "__solutions_private_pypi_url": SOLUTIONS_PRIVATE_PYPI_URL,
        },
    )
