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

from enum import Enum
import os
import re

from branch import Branch
from constants import (
    DEPENDENCY_PINNING_ENV_VAR,
    INITIAL_META_PACKAGE_VERSION,
    META_PACKAGE_NAME,
    PACKAGE_LIBRARY_DIRS,
    PACKAGE_VERSION_ENV_VARS,
    PYPROJECT_PATH,
)
from packaging.version import InvalidVersion, Version
import requests
import tomlkit

PACKAGES = list(PACKAGE_LIBRARY_DIRS)
REQUIREMENT_RE = re.compile(r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)(?P<extras>\[[^\]]+\])?")


class UpdateType(Enum):
    """The types of version updates that can be resolved for a set of dependencies."""

    def __new__(cls, value: str, priority: int):
        """Create an update type with a comparison priority."""
        member = object.__new__(cls)
        member._value_ = value
        member.priority = priority
        return member

    AUTO = "auto", -1
    NO_UPDATE = "no_update", 0
    PATCH = "patch", 1
    MINOR = "minor", 2
    MAJOR = "major", 3


class DependencyPinning(Enum):
    """Supported dependency version constraint styles."""

    RANGE = "range"
    STRICT = "strict"


def release_branch_exists(version: str) -> bool:
    """Return whether the SDK release branch for ``version`` exists on GitHub.

    Parameters
    ----------
    version : str
        SDK version used to construct the release branch name.

    Returns
    -------
    bool
        ``True`` when the branch exists, otherwise ``False``.

    Raises
    ------
    requests.HTTPError
        If GitHub returns an unsuccessful response other than ``404``.
    """
    branch_name = f"release/v{version}/saf-sdk"
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    repository = os.environ.get("GITHUB_REPOSITORY", "ansys/saf")
    url = f"https://api.github.com/repos/{repository}/branches/{branch_name}"
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        return True
    if response.status_code == 404:
        return False
    response.raise_for_status()
    raise RuntimeError(f"Unable to determine whether release branch '{branch_name}' exists.")


def meta_package_release_exists(version: str) -> bool:
    """Return whether a meta-package version has been published to PyPI.

    A missing meta-package is treated as unpublished and returns ``False``.

    Parameters
    ----------
    version : str
        Version to look up in the package's PyPI release list.

    Returns
    -------
    bool
        ``True`` if the version is listed on PyPI, otherwise ``False``.

    Raises
    ------
    requests.HTTPError
        If the PyPI request fails for a reason other than a missing package.
    """
    response = requests.get(f"https://pypi.org/pypi/{META_PACKAGE_NAME}/json", timeout=10)
    if response.status_code == 404:
        return False
    response.raise_for_status()
    return version in response.json()["releases"]


def bump_version(version: str, update_type: UpdateType) -> str:
    """Return ``version`` incremented according to ``update_type``.

    Parameters
    ----------
    version : str
        Existing semantic version.
    update_type : UpdateType
        Major, minor, or patch increment to apply. Other values leave the
        version unchanged.

    Returns
    -------
    str
        Updated semantic version string.
    """
    parsed = Version(version)
    if update_type == UpdateType.MAJOR:
        return f"{parsed.major + 1}.0.0"
    if update_type == UpdateType.MINOR:
        return f"{parsed.major}.{parsed.minor + 1}.0"
    if update_type == UpdateType.PATCH:
        return f"{parsed.major}.{parsed.minor}.{parsed.micro + 1}"
    return version


def validate_user_selected_update_type(branch: Branch) -> UpdateType:
    """Validate and return the requested update type for a branch.

    Release branches permit only ``auto`` and ``patch``. Non-release branches
    also permit ``major`` and ``minor``. The candidate next version must not
    already exist as a GitHub release branch or PyPI release. On release
    branches, ``auto`` can only ever resolve to a patch update, so it is
    checked as such; on non-release branches, ``auto``'s actual next version
    is only known once dependency updates are resolved, so it is not checked
    here.

    Parameters
    ----------
    branch : Branch
        Branch context used to determine valid update types and the current
        version.

    Returns
    -------
    UpdateType
        Validated update policy.

    Raises
    ------
    ValueError
        If the selected update type is not allowed or the next version
        already exists.
    """
    user_selected_update_type = os.environ.get("USER_SELECTED_UPDATE_TYPE", "auto")

    valid_update_types = ["auto", "patch"] if branch.is_release_branch else ["auto", "major", "minor", "patch"]
    if user_selected_update_type not in valid_update_types:
        raise ValueError(
            (
                f"Invalid meta-package version update type: "
                f"{user_selected_update_type}. Valid values are {valid_update_types}.",
            ),
        )

    update_type = UpdateType(user_selected_update_type)
    if update_type == UpdateType.AUTO and not branch.is_release_branch:
        return update_type

    next_version = bump_version(
        branch.version,
        UpdateType.PATCH if update_type == UpdateType.AUTO else update_type,
    )
    if release_branch_exists(next_version) or meta_package_release_exists(next_version):
        raise ValueError(f"The next version {next_version} already exists as a branch or PyPI release.")

    return update_type


def extract_package_name(requirement: str) -> str:
    """Extract the package name from the beginning of a requirement string.

    The returned name includes only the leading package-name characters. Any
    extras, version specifiers, environment markers, or other trailing text
    are left out. This function extracts the name but does not validate the
    remainder of the requirement.

    Parameters
    ----------
    requirement : str
        Requirement string, such as ``"package[extra]>=1.0"``.

    Returns
    -------
    str
        The package name extracted from ``requirement``.

    Raises
    ------
    ValueError
        If ``requirement`` does not begin with a supported package name.
    """
    requirement_name_re = re.compile(r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)")
    match = requirement_name_re.match(requirement)
    if not match:
        raise ValueError(f"Unsupported requirement format: {requirement}")
    return match.group("name")


def extract_lower_bound(requirement: str) -> str:
    """Extract the version from a ``>=`` or ``==`` requirement constraint.

    Parameters
    ----------
    requirement : str
        Requirement containing a lower-bound or exact-version constraint.

    Returns
    -------
    str
        Version specified by the first matching constraint.

    Raises
    ------
    ValueError
        If the requirement contains neither ``>=`` nor ``==``.
    """
    match = re.search(r"(?:>=|==)\s*(?P<version>[^,]+)", requirement)
    if not match:
        raise ValueError(f"Unsupported requirement format: {requirement}")
    return match.group("version")


def get_current_dependency_versions() -> dict[str, str]:
    """Read current dependency versions for packages managed by the SDK.

    Returns
    -------
    dict[str, str]
        Mapping of managed package names to their declared lower-bound or
        exact versions from project dependencies and optional dependencies.
    """
    document = tomlkit.parse(PYPROJECT_PATH.read_text(encoding="utf-8"))
    project = document["project"]

    versions: dict[str, str] = {}
    for requirement in project.get("dependencies", []):
        name = extract_package_name(requirement)
        if name in PACKAGES:
            versions.setdefault(name, extract_lower_bound(requirement))

    for extra_requirements in project.get("optional-dependencies", {}).values():
        for requirement in extra_requirements:
            name = extract_package_name(requirement)
            if name in PACKAGES:
                versions.setdefault(name, extract_lower_bound(requirement))

    return versions


def determine_update_type(
    user_selected_update_type: UpdateType,
    current_versions: dict[str, str],
    latest_versions: dict[str, str],
) -> UpdateType:
    """Determine the highest-impact required update across dependencies.

    Parameters
    ----------
    user_selected_update_type : UpdateType
        User-requested update policy.
    current_versions : dict[str, str]
        Current version for each managed package.
    latest_versions : dict[str, str]
        Latest available version for each managed package.

    Returns
    -------
    UpdateType
        Highest required update for ``AUTO``, or the user-selected update
        type when it satisfies every dependency update.

    Raises
    ------
    ValueError
        If the selected update type is less significant than a required
        dependency update.
    """
    update_type = UpdateType.NO_UPDATE
    for name, latest_version in latest_versions.items():
        current, latest = Version(current_versions[name]), Version(latest_version)
        if latest.major > current.major:
            component_update_type = UpdateType.MAJOR
        elif latest.minor > current.minor:
            component_update_type = UpdateType.MINOR
        elif latest.micro > current.micro:
            component_update_type = UpdateType.PATCH
        else:
            component_update_type = UpdateType.NO_UPDATE
        if component_update_type.priority > update_type.priority:
            update_type = component_update_type

    if user_selected_update_type == UpdateType.AUTO:
        return update_type
    if user_selected_update_type.priority < update_type.priority:
        raise ValueError(
            f"The user selected a {user_selected_update_type.name} update, but at least one component has a "
            f"{update_type.name} update.",
        )
    return user_selected_update_type


def get_latest_stable_version(name: str) -> str:
    """Return the highest stable, non-yanked version published on PyPI.

    Parameters
    ----------
    name : str
        PyPI package name.

    Returns
    -------
    str
        Highest stable release version.

    Raises
    ------
    ValueError
        If the package has no stable, non-yanked releases.
    requests.HTTPError
        If the PyPI request fails.
    """
    pypi_json_url = "https://pypi.org/pypi/{name}/json"
    response = requests.get(pypi_json_url.format(name=name), timeout=10)
    response.raise_for_status()
    releases = response.json()["releases"]

    stable_versions: list[Version] = []
    for version_string, release_files in releases.items():
        if not release_files or all(release_file["yanked"] for release_file in release_files):
            continue

        try:
            version = Version(version_string)
        except InvalidVersion:
            continue

        if not version.is_prerelease and not version.is_devrelease:
            stable_versions.append(version)

    if not stable_versions:
        raise ValueError(f"No stable version found for package: {name}")

    return str(max(stable_versions))


def get_latest_stable_versions(package_names: list[str]) -> dict[str, str]:
    """Return selected stable versions for each requested package.

    A non-empty package-specific ``USER_SELECTED_*_VERSION`` environment
    variable takes precedence over PyPI. This allows release workflows to use
    versions that are not yet published. Packages without an override use the
    latest stable, non-yanked PyPI release.

    Parameters
    ----------
    package_names : list[str]
        PyPI package names to query.

    Returns
    -------
    dict[str, str]
        Mapping of package names to their selected versions.
    """
    versions = {}
    for name in package_names:
        override_variable = PACKAGE_VERSION_ENV_VARS.get(name)
        override_version = os.environ.get(override_variable, "").strip() if override_variable else ""
        versions[name] = override_version or get_latest_stable_version(name)
    return versions


def get_meta_package_version(update_type: UpdateType) -> str:
    """Return the next meta-package version for the requested update type.

    If the meta-package has not yet been published, the initial version is
    returned. Otherwise, the latest stable published version is bumped.

    Parameters
    ----------
    update_type : UpdateType
        Version increment to apply to the latest published version.

    Returns
    -------
    str
        Next meta-package version.
    """
    try:
        published_version = get_latest_stable_version(META_PACKAGE_NAME)
        return bump_version(published_version, update_type)
    except requests.HTTPError as error:
        if error.response is not None and error.response.status_code == 404:
            return INITIAL_META_PACKAGE_VERSION
        raise


def get_dependency_pinning() -> DependencyPinning:
    """Return dependency pinning selected by ``SAF_SDK_DEPENDENCY_PINNING``.

    Defaults to strict pinning when the environment variable is unset.

    Returns
    -------
    DependencyPinning
        Selected range or strict pinning style.

    Raises
    ------
    ValueError
        If the environment variable contains an unsupported value.
    """
    value = os.environ.get(DEPENDENCY_PINNING_ENV_VAR, DependencyPinning.STRICT.value).lower()
    try:
        return DependencyPinning(value)
    except ValueError as error:
        valid_values = ", ".join(pinning.value for pinning in DependencyPinning)
        raise ValueError(f"{DEPENDENCY_PINNING_ENV_VAR} must be one of: {valid_values}") from error


def build_updated_requirement(
    requirement: str,
    versions: dict[str, str],
    pinning: DependencyPinning | None = None,
) -> str:
    """Rebuild a requirement using the selected dependency pinning style.

    Package names and extras are preserved. Requirements for packages not
    listed in ``PACKAGES`` are returned unchanged.

    Parameters
    ----------
    requirement : str
        Original requirement string.
    versions : dict[str, str]
        Resolved versions keyed by package name.
    pinning : DependencyPinning or None
        Pinning style to use. When omitted, the environment-selected style is
        used.

    Returns
    -------
    str
        Rebuilt or unchanged requirement string.

    Raises
    ------
    ValueError
        If the requirement does not begin with a supported package name.
    """
    match = REQUIREMENT_RE.match(requirement)
    if not match:
        raise ValueError(f"Unsupported requirement format: {requirement}")
    name, extras = match.group("name"), match.group("extras") or ""

    if name not in PACKAGES:
        return requirement

    version = versions[name]
    if (pinning or get_dependency_pinning()) == DependencyPinning.STRICT:
        return f"{name}{extras}=={version}"

    major, minor, *_ = version.split(".")
    minor_bound = f">={version},<{major}.{int(minor) + 1}.0"
    return f"{name}{extras}{minor_bound}"
