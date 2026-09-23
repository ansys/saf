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
# requires-python = ">=3.11"
# dependencies = [
#     "requests==2.32.2",
#     "packaging==26.3",
#     "pydantic==2.12.5",
# ]
# ///

"""Write the latest available Azure DevOps package versions as GitHub Actions outputs.

For each package supplied through ``--package-names``, the script queries the
Azure DevOps Packaging API, excludes deleted versions, and selects the latest
stable release. If no stable release exists, it selects the latest pre-release.
The selected version is written to ``GITHUB_OUTPUT`` using the package name as
the output name.

Environment variables
---------------------
AZURE_DEVOPS_ORG
    Azure DevOps organization name.
AZURE_DEVOPS_FEED
    Azure DevOps feed name.
AZURE_DEVOPS_PAT
    Personal access token used for Azure DevOps authentication.
"""

import argparse
import os

from github_utilities import write_github_output
from packaging.version import parse as parse_version
from pydantic import SecretStr
import requests


def _get_package_data(package_name: str) -> dict[str, object]:
    try:
        # Securely fetch configurations from Environment Variables using SecretStr
        # This wraps them immediately so they cannot be exposed in tracebacks or logs.
        organization = SecretStr(os.environ.get("AZURE_DEVOPS_ORG", ""))
        feed = SecretStr(os.environ.get("AZURE_DEVOPS_FEED", ""))
        token = SecretStr(os.environ["AZURE_DEVOPS_PAT"])

        # We construct the URL directly inside the requests parameters.
        # It lives purely in transient memory and is never assigned to a loggable string.
        response = requests.get(
            f"https://feeds.dev.azure.com/{organization.get_secret_value()}/_apis/packaging/Feeds/{feed.get_secret_value()}/packages",
            params={
                "packageNameQuery": package_name,
                "includeAllVersions": "true",
                "api-version": "7.1",
            },
            auth=("", token.get_secret_value()),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        raise ValueError(f"Failed to fetch package data for '{package_name}'") from error


def get_latest_versions(packages: list[str]) -> dict[str, str]:
    versions = {}
    for package_name in packages:
        data = _get_package_data(package_name)

        packages = data.get("value", [])
        matching_package = next((pkg for pkg in packages if pkg.get("name") == package_name), None)

        if not matching_package or "versions" not in matching_package:
            raise ValueError(f"Package '{package_name}' not found or has no versions in the feed.")

        # Loop through the version objects and filter out any where 'isDeleted' is true to skip yanked versions
        active_versions = [version for version in matching_package["versions"] if not version.get("isDeleted", False)]

        if not active_versions:
            raise ValueError(f"All versions for '{package_name}' have been yanked or deleted.")

        parsed_versions = [parse_version(version["version"]) for version in active_versions]
        stable_versions = [v for v in parsed_versions if not v.is_prerelease]

        if stable_versions:
            # 1st Priority: Return the highest stable version
            latest_version = max(stable_versions)
            print(f"Latest stable version (excluding yanked): {latest_version}")
        else:
            # 2nd Priority Fallback: Return the highest pre-release/dev version
            latest_version = max(parsed_versions)
            print(f"No stable versions found. Latest pre-release/dev version (excluding yanked): {latest_version}")
        versions[package_name] = str(latest_version)
        write_github_output(f"{package_name.replace('-', '_').lower()}_version", str(latest_version))
    return versions


def parse_args() -> argparse.Namespace:
    """Parse package names from the command line."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--package-names",
        nargs="+",
        required=True,
        help="Package names to fetch the latest versions for.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    get_latest_versions(args.package_names)


if __name__ == "__main__":
    raise SystemExit(main())
