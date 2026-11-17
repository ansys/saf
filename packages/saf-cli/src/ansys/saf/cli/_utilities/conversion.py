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

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version


def poetry_constraint_to_pep440(specification: str) -> str:
    """Translate common Poetry version constraints without changing their bounds.

    Union constraints cannot be represented by one PEP 440 specifier and are
    rejected rather than silently broadening the allowed versions.
    """
    constraints: list[str] = []
    for constraint in specification.split(","):
        constraint = constraint.strip()
        if constraint in {"", "*"}:
            continue
        try:
            SpecifierSet(constraint)
        except InvalidSpecifier:
            if constraint.startswith(("^", "~")):
                try:
                    version = Version(constraint[1:].strip())
                except InvalidVersion as error:
                    raise ValueError(f"Unsupported dependency version constraint: {specification!r}.") from error
                release = version.release
                upper = [*release, *([0] * max(0, 3 - len(release)))]
                if constraint.startswith("^"):
                    index = next((i for i, part in enumerate(release) if part), len(release) - 1)
                else:
                    index = min(1, len(release) - 1)
                upper[index] += 1
                upper[index + 1 :] = [0] * (len(upper) - index - 1)
                epoch = f"{version.epoch}!" if version.epoch else ""
                constraint = f">={version},<{epoch}{'.'.join(map(str, upper))}"
            else:
                constraint = f"=={constraint}"
        try:
            SpecifierSet(constraint)
        except InvalidSpecifier as error:
            raise ValueError(f"Unsupported dependency version constraint: {specification!r}.") from error
        constraints.append(constraint)
    return ",".join(constraints)


def to_display_name(name: str) -> str:
    # input: "my-name" or "my_name" or "my name" or "My name"
    # output: "My Name"
    return name.replace("-", " ").replace("_", " ").title()


def to_module_name(name: str, module_type: str = "") -> str:
    # input: "my-name" or "my_name" or "my name" or "My name"
    # output: "my_name{_module-type}" (module_type: _step or _page)
    module_name = name.lower().replace("-", "_").replace(" ", "_")
    if module_type and not module_name.endswith(module_type):
        module_name += f"_{module_type}"
    return module_name


def to_class_name(name: str, class_type: str) -> str:
    # input: "my-name" or "my_name" or "my name" or "My name"
    # output: "MyName{ClassType}" (class_type: Solution or Step)
    class_name = name.title().replace("-", "").replace("_", "").replace(" ", "")
    if not class_name.endswith(class_type):
        class_name += class_type
    return class_name


def to_package_name(name: str) -> str:
    # input: "my-name" or "my_name" or "my name" or "My name"
    # output: "my-name"
    return name.lower().replace("_", "-").replace(" ", "-")


def namespace_to_pkg_name(namespace: str) -> str:
    # input:  "my_org.my_project"
    # output: "my-org-my-project"
    namespace_parts = [to_package_name(part) for part in namespace.split(".")]
    return "-".join(namespace_parts)


def to_docker_name(name: str, version: str) -> str:
    # input: "my-name" or "my_name" or "my name" or "My name" and version = "0.1.dev0"
    # output: "my-name-0-1-dev0"
    return f"{to_package_name(name)}_{version.replace('.', '-')}"


def namespace_to_path(namespace: str) -> str:
    # input:  "my_org.my_project"
    # output: "my_org/my_project"
    return namespace.replace(".", "/")
