# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections.abc import Mapping, MutableMapping
from pathlib import Path
import subprocess
from typing import Any, cast

import click
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from pydantic import BaseModel
import tomlkit
from tomlkit.items import Array, InlineTable, Table
from tomlkit.toml_document import TOMLDocument

from ansys.saf.cli._solutions.backend_detection import SolutionBackend, parse_solution_backend
from ansys.saf.cli._solutions.plugins import SafTemplate


class ManualDependency(BaseModel):
    name: str
    specification: str | dict[str, Any]
    group: str


class DependencyManager:
    def __init__(
        self,
        saf_template: SafTemplate,
        solution_root_dir: Path,
    ) -> None:
        self._saf_template = saf_template
        self._solution_root_dir = solution_root_dir
        self._pyproject_path = solution_root_dir / "pyproject.toml"
        if not self._pyproject_path.is_file():
            raise FileNotFoundError(f"pyproject.toml not found in solution root directory '{self._solution_root_dir}'.")

    @staticmethod
    def _create_new_poetry_dependency_group() -> Table:
        new_group = tomlkit.table()
        new_group.add("optional", True)
        deps = tomlkit.table()
        new_group.add("dependencies", deps)
        new_group.add(tomlkit.nl())
        return new_group

    def _get_poetry_solution_dependency_groups(self, poetry_section: dict[str, Any]) -> dict[str, Any]:
        if "group" not in poetry_section:  # type: ignore
            if any(step_dep_group != "main" for step_dep_group in self._saf_template.dependencies):
                poetry_section["group"] = tomlkit.table(is_super_table=True)  # type: ignore
            else:
                return {}
        return poetry_section["group"]  # type: ignore

    def _find_poetry_dependency_in_solution(
        self,
        dependency_name: str,
        main_dependencies: dict[str, Any],
        dependency_groups: dict[str, Any],
    ) -> bool:
        if dependency_name in main_dependencies:
            return True
        for _, group_dependencies in dependency_groups.items():
            if dependency_name in group_dependencies.get("dependencies", {}):
                return True
        return False

    def _add_poetry_dependency_to_solution(
        self,
        step_dependency_name: str,
        step_dependency_spec: str | dict[str, Any],
        solution_dependencies: dict[str, Any],
    ) -> None:
        if isinstance(step_dependency_spec, str):
            # Dependencies in the format dependency_name: "dependency_specification"
            solution_dependencies[step_dependency_name] = step_dependency_spec
        else:
            # Dependencies in the format dependency_name: { "key": "value", ... }
            inline_dependency = tomlkit.inline_table()
            inline_dependency.update(step_dependency_spec)  # pyright: ignore[reportUnknownMemberType]
            inline_dependency.trivia.trail = "\n"
            solution_dependencies[step_dependency_name] = inline_dependency

    @staticmethod
    def _get_lock_install_cmd(backend: SolutionBackend, groups: set[str]) -> list[list[str]]:
        """Build backend-specific lock and installation commands for the requested groups."""
        if backend is SolutionBackend.POETRY:
            install = ["poetry", "install"]
            if groups:
                install.extend(["--with", ",".join(sorted(groups))])
            return [["poetry", "lock"], install]
        sync = ["uv", "sync", "--locked", "--no-default-groups", "--inexact", "--no-python-downloads"]
        for group in sorted(groups):
            sync.extend(["--group", group])
        return [["uv", "lock", "--no-python-downloads"], sync]

    def _render_manual_dependency_warning(
        self,
        manual_dependencies: list[ManualDependency],
        groups: set[str],
        backend: SolutionBackend,
    ) -> None:
        click.secho(
            f"WARNING: the step template '{self._saf_template.name}' has some dependencies in common with the "
            f"solution's pyproject.toml at {self._pyproject_path}. Review the solution's pyproject.toml and manually "
            f"update it if necessary, to ensure that it is compatible with the step template's dependencies.\n",
            fg="yellow",
        )
        click.secho("Step specification of the common dependencies:", fg="yellow")
        for manual_dependency in manual_dependencies:
            group_label = "main" if manual_dependency.group == "main" else f"{manual_dependency.group} group"
            click.secho(
                f"  - {manual_dependency.name} ({group_label}): {manual_dependency.specification}",
                fg="yellow",
            )
        lock_command, install_command = (" ".join(command) for command in self._get_lock_install_cmd(backend, groups))
        click.secho(
            f"\nAfter reviewing the dependencies, please run:\n"
            f'  - saf execute {self._solution_root_dir.name} "{lock_command}"\n'
            f'  - saf execute {self._solution_root_dir.name} "{install_command}"',
            fg="yellow",
        )

    def _merge_poetry_dependencies(self, pyproject_content: TOMLDocument) -> list[ManualDependency]:
        if not pyproject_content.get("tool", {}).get("poetry", {}):  # type: ignore
            raise ValueError(f"No [tool.poetry] section found in pyproject.toml at '{self._pyproject_path}'.")
        poetry_section = pyproject_content["tool"]["poetry"]  # type: ignore
        main_deps = poetry_section.get("dependencies", {})  # type: ignore
        if not main_deps:
            raise ValueError(f"No main dependencies found in pyproject.toml at '{self._pyproject_path}'.")
        dep_groups = self._get_poetry_solution_dependency_groups(poetry_section)  # type: ignore

        manual_deps: list[ManualDependency] = []
        for step_dep_group in self._saf_template.dependencies:
            if step_dep_group != "main" and step_dep_group not in dep_groups:
                dep_groups[step_dep_group] = self._create_new_poetry_dependency_group()
            group_deps = dep_groups.get(step_dep_group, {}).get("dependencies", {})
            for step_dep_name, step_dep_spec in self._saf_template.dependencies[step_dep_group].items():
                if self._find_poetry_dependency_in_solution(step_dep_name, main_deps, dep_groups):  # type: ignore
                    manual_deps.append(
                        ManualDependency(
                            name=step_dep_name,
                            specification=step_dep_spec,
                            group=step_dep_group,
                        ),
                    )
                else:
                    self._add_poetry_dependency_to_solution(
                        step_dep_name,
                        step_dep_spec,
                        main_deps if step_dep_group == "main" else group_deps,  # type: ignore
                    )
        return manual_deps

    @staticmethod
    def _format_uv_requirement(name: str, specification: str | dict[str, Any]) -> tuple[str, bool | None]:
        """Format a SAF dependency for UV, leaving dependency syntax validation to uv lock."""
        if isinstance(specification, str):
            specification = {"version": specification}
        unsupported = specification.keys() - {"version", "extras", "markers", "allow-prereleases"}
        if unsupported:
            raise ValueError(f"Unsupported UV dependency fields for '{name}': {', '.join(sorted(unsupported))}.")

        extras = specification.get("extras", [])
        requirement = name + (f"[{','.join(extras)}]" if extras else "")
        version = specification.get("version", "")
        if version:
            requirement += f" {version}"
        markers = specification.get("markers", "")
        if markers:
            requirement += f"; {markers}"
        return requirement, specification.get("allow-prereleases")

    def _get_or_create_uv_table(self, parent: MutableMapping[str, Any], key: str) -> MutableMapping[str, Any]:
        """Get or create a UV configuration table, rejecting non-table values."""
        value = parent.setdefault(key, tomlkit.table())
        if not isinstance(value, MutableMapping):
            raise ValueError(f"'{key}' must be a table in '{self._pyproject_path}'.")
        return cast("MutableMapping[str, Any]", value)

    def _get_or_create_uv_array(self, parent: MutableMapping[str, Any], key: str) -> Array:
        """Get or create a UV dependency array, rejecting non-array values."""
        value = parent.setdefault(key, tomlkit.array())
        if not isinstance(value, Array):
            raise ValueError(f"'{key}' must be an array in '{self._pyproject_path}'.")
        return value

    def _collect_uv_dependency_names(self, dependencies: Array, *, allow_includes: bool = False) -> set[str]:
        """Collect normalized package names, allowing group references where appropriate."""
        names: set[str] = set()
        for dependency in dependencies:
            if isinstance(dependency, str):
                names.add(canonicalize_name(Requirement(dependency).name))
            elif (
                allow_includes
                and isinstance(dependency, InlineTable)
                and set(dependency) == {"include-group"}
                and isinstance(dependency["include-group"], str)
            ):
                # The referenced group is covered by scanning every dependency group.
                continue
            else:
                raise ValueError(f"Invalid dependency entry in '{self._pyproject_path}': {dependency!r}.")
        return names

    def _merge_uv_dependencies(self, pyproject_content: TOMLDocument) -> list[ManualDependency]:
        """Merge new UV requirements and prerelease settings, returning overlaps for manual review."""
        project = self._get_or_create_uv_table(pyproject_content, "project")
        main_dependencies = self._get_or_create_uv_array(project, "dependencies")
        dependency_groups = self._get_or_create_uv_table(pyproject_content, "dependency-groups")
        existing_names = self._collect_uv_dependency_names(main_dependencies)
        for group in dependency_groups:
            existing_names.update(
                self._collect_uv_dependency_names(
                    self._get_or_create_uv_array(dependency_groups, group),
                    allow_includes=True,
                ),
            )
        optional_dependencies = project.get("optional-dependencies", {})
        if not isinstance(optional_dependencies, Mapping):
            raise ValueError(f"'project.optional-dependencies' must be a table in '{self._pyproject_path}'.")
        for extra, dependencies in optional_dependencies.items():
            if not isinstance(dependencies, Array):
                raise ValueError(f"Optional dependencies '{extra}' must be an array in '{self._pyproject_path}'.")
            existing_names.update(self._collect_uv_dependency_names(dependencies))

        return self._add_uv_template_dependencies(
            pyproject_content,
            main_dependencies,
            dependency_groups,
            existing_names,
        )

    def _add_uv_template_dependencies(
        self,
        pyproject_content: TOMLDocument,
        main_dependencies: Array,
        dependency_groups: MutableMapping[str, Any],
        existing_names: set[str],
    ) -> list[ManualDependency]:
        """Add template requirements and prerelease settings, returning overlaps for manual review."""
        manual_deps: list[ManualDependency] = []
        for group, dependencies in self._saf_template.dependencies.items():
            if not isinstance(dependencies, dict):
                raise ValueError(f"Template dependency group '{group}' must be a mapping.")
            target = main_dependencies if group == "main" else self._get_or_create_uv_array(dependency_groups, group)
            for name, specification in dependencies.items():
                normalized_name = canonicalize_name(name)
                if normalized_name in existing_names:
                    manual_deps.append(ManualDependency(name=name, specification=specification, group=group))
                    continue
                requirement, prereleases = self._format_uv_requirement(name, specification)
                target.append(requirement)
                existing_names.add(normalized_name)
                if prereleases is not None:
                    tool = self._get_or_create_uv_table(pyproject_content, "tool")
                    uv = self._get_or_create_uv_table(tool, "uv")
                    package_prereleases = self._get_or_create_uv_table(uv, "prerelease-package")
                    package_prereleases[normalized_name] = {True: "allow", False: "disallow"}[prereleases]
        return manual_deps

    def update_solution_dependencies(self, executable: Path, solution_env: dict[str, str]) -> None:
        """Detect the backend, save merged dependencies, and install them or warn about overlaps."""
        backend = parse_solution_backend(self._solution_root_dir).backend
        pyproject_content = tomlkit.loads(self._pyproject_path.read_bytes())
        if backend is SolutionBackend.UV:
            manual_deps = self._merge_uv_dependencies(pyproject_content)
            solution_env = solution_env.copy()
            solution_env.pop("VIRTUAL_ENV", None)
            solution_env["UV_PROJECT_ENVIRONMENT"] = str((self._solution_root_dir / ".venv").resolve())
        else:
            manual_deps = self._merge_poetry_dependencies(pyproject_content)

        self._pyproject_path.write_text(tomlkit.dumps(pyproject_content), newline="")  # type: ignore

        groups = {group for group in self._saf_template.dependencies if group != "main"}
        if not manual_deps:
            for command in self._get_lock_install_cmd(backend, groups):
                subprocess.run(
                    [executable.as_posix(), *command[1:]],
                    env=solution_env,
                    cwd=self._solution_root_dir,
                    check=True,
                )
        else:
            self._render_manual_dependency_warning(manual_deps, groups, backend)
