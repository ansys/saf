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

# /// script
# dependencies = [
#   "tomlkit==0.15.1",
#   "requests==2.32.2",
#   "packaging==26.3",
#   "pydantic==2.12.5",
# ]
# ///

"""Utilities for updating the ansys-saf-sdk meta-package version and dependencies in packages/saf-sdk/pyproject.toml."""

from __future__ import annotations

import subprocess

from branch import Branch
from constants import (
    PYPROJECT_PATH,
)
from github_utilities import write_github_output
from release_notes_utilities import generate_release_notes
import tomlkit
from version_utilities import (
    UpdateType,
    build_updated_requirement,
    determine_update_type,
    get_current_dependency_versions,
    get_dependency_pinning,
    get_latest_stable_versions,
    get_meta_package_version,
    validate_user_selected_update_type,
)


def run_uv_lock() -> None:
    """Run ``uv lock`` in the meta-package directory.

    Raises
    ------
    subprocess.CalledProcessError
        If ``uv lock`` exits with a non-zero status.
    """

    subprocess.run(["uv", "lock"], check=True, cwd=PYPROJECT_PATH.parent)
    print("Executed 'uv lock' to update the lock file.")


def update_pyproject(branch: Branch, user_selected_update_type: UpdateType) -> None:
    """Resolve and write updated meta-package dependencies and version.

    Parameters
    ----------
    branch : Branch
        Current branch context used to determine the permitted update type.
    user_selected_update_type : UpdateType
        Requested update policy. ``AUTO`` selects the highest required update
        across all dependencies.

    Notes
    -----
    The function updates ``pyproject.toml`` only when the meta-package version
    or dependency requirements change. It also writes GitHub Actions outputs,
    refreshes the lock file after changes, and generates release notes. The
    ``changed`` output reflects whether ``pyproject.toml``/``uv.lock`` were
    actually rewritten, independent of ``update_type``.
    """
    document = tomlkit.parse(PYPROJECT_PATH.read_text(encoding="utf-8"))
    project = document["project"]
    current_versions = get_current_dependency_versions()
    latest_versions = get_latest_stable_versions(current_versions.keys())
    pinning = get_dependency_pinning()

    update_type = determine_update_type(user_selected_update_type, current_versions, latest_versions)

    write_github_output("update_type", update_type.value)
    project_version = get_meta_package_version(update_type)
    write_github_output("version", project_version)

    dependencies = project["dependencies"]

    updated_dependencies = [
        build_updated_requirement(requirement, latest_versions, pinning) for requirement in dependencies
    ]
    updated_optional_dependencies = {
        group: [build_updated_requirement(requirement, latest_versions, pinning) for requirement in requirements]
        for group, requirements in project["optional-dependencies"].items()
    }
    requirements_changed = list(dependencies) != updated_dependencies or any(
        list(project["optional-dependencies"][group]) != requirements
        for group, requirements in updated_optional_dependencies.items()
    )
    changed = update_type != UpdateType.NO_UPDATE or requirements_changed
    write_github_output("changed", str(changed).lower())

    if not changed:
        print("No updates found for any dependencies. No changes will be made to pyproject.toml.")
    else:
        print(f"Updating dependencies with {pinning.value} pinning...")
        if update_type != UpdateType.NO_UPDATE:
            project["version"] = project_version

        for index, requirement in enumerate(updated_dependencies):
            dependencies[index] = requirement

        for group, requirements in updated_optional_dependencies.items():
            extra_requirements = project["optional-dependencies"][group]
            for index, requirement in enumerate(requirements):
                extra_requirements[index] = requirement

        PYPROJECT_PATH.write_text(tomlkit.dumps(document), encoding="utf-8")

        print(
            f"Successfully updated meta-package version to {project['version']} and dependencies in {PYPROJECT_PATH}.",
        )

        run_uv_lock()

    generate_release_notes(latest_versions, project["version"], current_versions)


if __name__ == "__main__":
    branch = Branch()
    update_type = validate_user_selected_update_type(branch)
    update_pyproject(branch, update_type)
