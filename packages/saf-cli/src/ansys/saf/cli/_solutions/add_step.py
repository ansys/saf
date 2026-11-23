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
import re
import shutil
import tempfile

import click
from cookiecutter.main import cookiecutter  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]
from packaging.version import Version
import tomlkit

from ansys.saf.cli._solutions.backend_detection import SolutionBackend, parse_solution_backend
from ansys.saf.cli._solutions.dependencies import DependencyManager
from ansys.saf.cli._solutions.plugins import SafTemplate
from ansys.saf.cli._utilities.conversion import namespace_to_path, to_class_name, to_module_name
from ansys.saf.cli._utilities.solution_modules import (
    create_solution_environment,
    get_exec_from_solution_venv,
    get_main_module,
    resolve_solution_main_file,
)

WRONG_FRAMEWORK_ERROR_MSG = (
    "The step you are creating is using a different framework than the one you used to create the solution with."
)
WRONG_DASH_STRUCTURE_ERROR_MSG = (
    "The target solution does not use the expected multi-page Dash structure required by 'saf add-step'."
)


def _insert_step_line(pattern: re.Pattern[str], content: str, new_line: str) -> str:
    content_lines = content.splitlines()

    if new_line not in content_lines:
        insert_position = 0
        last_non_empty_line = 0

        for i, line in enumerate(content_lines):
            if pattern.match(line):
                insert_position = last_non_empty_line + 1
                break
            if line.strip():
                last_non_empty_line = i

        content_lines.insert(insert_position, new_line)

    return "\n".join(content_lines)


def _resolve_solution_namespace_info(
    solution_root_dir: Path,
    solution_package_name: str | None = None,
) -> tuple[str, str, str]:
    """
    Resolve namespace information from a solution's main.py file.
    """
    solution_main_file = resolve_solution_main_file(solution_root_dir)
    main_module = get_main_module(solution_main_file)
    resolved_solution_module = main_module.removesuffix(".main")
    namespace, resolved_solution_package_name = resolved_solution_module.rsplit(".", 1)

    # Trust the discovered module path; this supports both default and custom namespaces
    if solution_package_name and solution_package_name != resolved_solution_package_name:
        resolved_solution_package_name = solution_package_name

    namespace_path = namespace_to_path(namespace)

    return namespace, namespace_path, resolved_solution_package_name


def step_name_exists(solution_root_dir: Path, solution_package_name: str, step_name: str) -> bool:
    """Return True if the step name already exists in the given solution."""
    step_module_name = to_module_name(step_name, "step")

    _, namespace_path, resolved_solution_package_name = _resolve_solution_namespace_info(
        solution_root_dir,
        solution_package_name,
    )

    solution_definition_path = (
        solution_root_dir / "src" / namespace_path / resolved_solution_package_name / "solution" / "definition.py"
    )

    if not solution_definition_path.is_file():
        raise FileNotFoundError(f"Solution definition not found in expected location: {solution_definition_path}")

    return step_module_name in solution_definition_path.read_text()


def check_template_cli_compatibility(
    solution_root_dir: Path,
    saf_step_template: SafTemplate,
) -> None:
    if saf_step_template.saf_cli_compatibility_range is None:
        return

    pyproject_path = solution_root_dir / "pyproject.toml"
    try:
        pyproject_data = tomlkit.loads(pyproject_path.read_bytes()).unwrap()
        solution_saf_cli_version = Version(pyproject_data.get("saf-cli-version", {}).get("saf-cli-version"))
    except Exception:
        solution_saf_cli_version = None

    if solution_saf_cli_version is None:
        click.secho(
            f"Warning: Template '{saf_step_template.name}' declares the saf-cli compatibility constraint "
            f"'{saf_step_template.saf_cli_compatibility_range}', but the solution does not declare a valid saf-cli "
            f"version in pyproject.toml. The step might not work as expected.",
            fg="yellow",
        )
        return

    if not saf_step_template.saf_cli_compatibility_range.contains(solution_saf_cli_version, prereleases=True):
        raise ValueError(
            f"Template '{saf_step_template.name}' requires a saf-cli version in the range "
            f"'{saf_step_template.saf_cli_compatibility_range}', "
            f"but the solution's saf-cli version is {solution_saf_cli_version}.",
        ) from None


def _add_step_to_definition(
    solution_root_dir: Path,
    solution_module_name: str,
    step_module_name: str,
    step_definition_class_name: str,
    namespace: str,
    namespace_path: str,
) -> None:
    solution_definition_path = (
        solution_root_dir / "src" / namespace_path / solution_module_name / "solution" / "definition.py"
    )

    if not solution_definition_path.is_file():
        raise FileNotFoundError(f"Solution definition not found in {solution_definition_path}.")

    solution_definition_content = solution_definition_path.read_text()

    new_step_line = f"    {step_module_name}: {step_definition_class_name}"

    solution_definition_content = _insert_step_line(
        pattern=re.compile(r"^class .*?\(Solution\):$"),
        content=solution_definition_content,
        new_line=new_step_line,
    )
    solution_definition_content = _insert_step_line(
        pattern=re.compile(r"^class .*?\(StepsModel\):$"),
        content=solution_definition_content,
        new_line=f"from {namespace}.{solution_module_name}.solution.{step_module_name} import {step_definition_class_name}",  # noqa: E501
    )
    solution_definition_path.write_text(solution_definition_content)


def _validate_multi_page_dash_solution(
    solution_root_dir: Path,
    solution_module_name: str,
    namespace_path: str,
) -> None:
    main_page_path = solution_root_dir / "src" / namespace_path / solution_module_name / "ui" / "pages" / "page.py"
    app_path = solution_root_dir / "src" / namespace_path / solution_module_name / "ui" / "app.py"
    # temporary fix until saf-cli supports detecting which framework the solution was created with.
    if not main_page_path.is_file() or not app_path.is_file():
        raise RuntimeError(WRONG_FRAMEWORK_ERROR_MSG)

    app_content = app_path.read_text(encoding="utf-8")
    if not re.search(r"\buse_pages\s*=\s*True\b", app_content):
        raise RuntimeError(WRONG_DASH_STRUCTURE_ERROR_MSG)


def add_step_to_solution(
    solution_name: str,
    solution_root_dir: Path,
    solution_module_name: str,
    step_name: str,
    ui_type: str,
    saf_step_template: SafTemplate,
) -> None:
    # see docs' glossary for a detailed explanation of every term used in the cookiecutter kwargs

    namespace, namespace_path, resolved_solution_module_name = _resolve_solution_namespace_info(
        solution_root_dir,
        solution_module_name,
    )
    solution_module_name = resolved_solution_module_name

    solution_definition_class_name = to_class_name(solution_name, "Solution")
    step_module_name = to_module_name(step_name, "step")
    step_definition_class_name = to_class_name(step_name, "Step")
    ui_page_file_name = to_module_name(step_module_name.removesuffix("_step"), "page")

    if ui_type == "dash":
        _validate_multi_page_dash_solution(
            solution_root_dir,
            solution_module_name,
            namespace_path,
        )

    # Generate into a temporary directory and then copy generated files to the solution.
    # This avoids cookiecutter complaining about an existing output directory, and lets the
    # template hooks enforce that existing step files are not overwritten.
    with tempfile.TemporaryDirectory() as baking_path:
        cookiecutter(
            template=saf_step_template.location.as_posix(),
            output_dir=baking_path,
            no_input=True,
            # overwrite all cookiecutter.json terms
            extra_context={
                "__solution_name": solution_name,
                "__solution_root_dir": solution_root_dir.absolute().as_posix(),
                "__solution_module_name": solution_module_name,
                "__solution_namespace": namespace,
                "__solution_namespace_path": namespace_path,
                "__solution_definition_class_name": solution_definition_class_name,
                "__step_name": step_name,
                "__step_module_name": step_module_name,
                "__step_definition_class_name": step_definition_class_name,
                "__ui_page_file_name": ui_page_file_name,
                "__ui_framework": ui_type,
            },
        )

    _add_step_to_definition(
        solution_root_dir,
        solution_module_name,
        step_module_name,
        step_definition_class_name,
        namespace,
        namespace_path,
    )
    if saf_step_template.dependencies:
        click.secho(
            "Updating solution dependencies. Do not modify solution files until completion.",
            fg="cyan",
            bold=True,
        )

        backend = parse_solution_backend(solution_root_dir).backend
        if backend is SolutionBackend.UV:
            uv_executable = shutil.which("uv")
            if uv_executable is None:
                raise FileNotFoundError("UV executable not found. Install UV and ensure it is available on PATH.")
            executable = Path(uv_executable)
        else:
            executable = get_exec_from_solution_venv(solution_root_dir, "poetry")
        solution_env = create_solution_environment(solution_root_dir)

        dependency_manager = DependencyManager(
            saf_template=saf_step_template,
            solution_root_dir=solution_root_dir,
        )
        dependency_manager.update_solution_dependencies(executable, solution_env)
