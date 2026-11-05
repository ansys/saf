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
import shutil
from typing import Any

import pytest
import tomlkit

from ansys.saf.cli._config.const import DEFAULT_SOLUTION_NAMESPACE
from ansys.saf.cli._solutions.backend_detection import SolutionBackend
from ansys.saf.cli._solutions.plugins import SafTemplate
from ansys.saf.cli._utilities.conversion import namespace_to_path
from tests.conftest import get_template_path, get_templates_toml_path


# This runs mock_appdata automatically for each unit test
@pytest.fixture(autouse=True)
def auto_use_mock_appdata(mock_appdata: Path) -> None:
    return


@pytest.fixture
def solution_name(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def solution_namespace(request: pytest.FixtureRequest) -> str:
    # Default namespace for existing tests
    param = getattr(request, "param", DEFAULT_SOLUTION_NAMESPACE)
    return param if param is not None else DEFAULT_SOLUTION_NAMESPACE


@pytest.fixture
def root_solution_dir(tmp_path: Path, solution_name: str, solution_namespace: str) -> Path:
    mock_solution_src_path = Path(__file__).parent / "mocks" / "solutions" / solution_name
    assert mock_solution_src_path.is_dir()

    dest_solution_dir = tmp_path / mock_solution_src_path.name
    dest_solution_src_dir = (
        dest_solution_dir / "src" / namespace_to_path(solution_namespace) / mock_solution_src_path.name
    )
    dest_solution_src_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(mock_solution_src_path, dest_solution_src_dir)

    for file in dest_solution_src_dir.rglob("*.py"):
        file.write_text(
            file.read_text(encoding="utf-8").replace("from tests.mocks.solutions", f"from {solution_namespace}"),
            encoding="utf-8",
        )

    return dest_solution_dir


@pytest.fixture
def root_solution_dir_with_pyproject_and_lock(root_solution_dir: Path, request: pytest.FixtureRequest) -> Path:
    """Create backend-specific project metadata and a lockfile, defaulting to Poetry."""
    pyproject_path = root_solution_dir / "pyproject.toml"
    config = getattr(request, "param", {})
    backend = SolutionBackend(config.get("backend", SolutionBackend.POETRY))
    (root_solution_dir / f"{backend.value}.lock").touch()

    data: dict[str, Any]
    if backend is SolutionBackend.UV:
        data = {
            "project": {
                "name": "saf-solutions-my-solution",
                "version": "0.1.0",
                "requires-python": ">=3.11,<3.15",
                "dependencies": [],
            },
            "tool": {"uv": {}},
        }
        if "main_dependencies" in config or "ui_dependencies" in config:
            data["project"]["dependencies"] = ["ansys-saf-sdk==0.2.0"]
        if "ui_dependencies" in config:
            data["dependency-groups"] = {"ui": ["dash>=4.2.0,<5.0.0"]}
    else:
        data = {"tool": {"poetry": {"name": "saf-solutions-my-solution"}}}
        if "main_dependencies" in config or "ui_dependencies" in config:
            data["tool"]["poetry"]["dependencies"] = {
                "python": ">=3.11,<3.15",
                "ansys-saf-sdk": "0.2.0",
            }
        if "ui_dependencies" in config:
            data["tool"]["poetry"]["group"] = {
                "ui": {
                    "optional": True,
                    "dependencies": {
                        "dash": "^4.2.0",
                    },
                },
            }
    if "version" in config:
        data.update({"saf-cli-version": {"saf-cli-version": config["version"]}})

    pyproject_path.write_text(tomlkit.dumps(data))  # type: ignore
    return root_solution_dir


@pytest.fixture
def solution_dir(root_solution_dir: Path, solution_name: str, solution_namespace: str) -> Path:
    return root_solution_dir / "src" / namespace_to_path(solution_namespace) / solution_name


@pytest.fixture
def solution_ui_framework(solution_name: str) -> str:
    if "dash" in solution_name:
        return "dash"
    else:
        return "none"


@pytest.fixture
def default_saf_step_template() -> SafTemplate:
    templates_toml_content = tomlkit.loads(get_templates_toml_path("templates").read_bytes())
    calculator_step = templates_toml_content["templates"]["calculator-step"]  # type: ignore
    return SafTemplate.model_validate(
        {
            "name": "calculator-step",
            "type": "step",
            "description": "a step that performs calculator operations",
            "location": get_template_path("templates", "calculator"),
            "saf_cli_compatibility_range": calculator_step["saf_cli_compatibility_range"],  # type: ignore
        },
    )


@pytest.fixture
def default_saf_step_template_without_saf_cli_compat_range() -> SafTemplate:
    return SafTemplate.model_validate(
        {
            "name": "calculator-step",
            "type": "step",
            "description": "a step that performs calculator operations",
            "location": get_template_path("templates", "calculator"),
        },
    )


@pytest.fixture
def custom_saf_step_template(request: pytest.FixtureRequest) -> SafTemplate:
    module_name = "test_custom_templates" if not hasattr(request, "param") else request.param
    templates_toml_content = tomlkit.loads((get_templates_toml_path(module_name)).read_bytes())
    dependencies = templates_toml_content["templates"]["second-step"].get("dependencies", {})  # type: ignore
    return SafTemplate.model_validate(
        {
            "name": "second-step",
            "type": "step",
            "description": "a step that is second to another step",
            "location": get_template_path(module_name, "second_step"),
            "dependencies": dependencies,
        },
    )
