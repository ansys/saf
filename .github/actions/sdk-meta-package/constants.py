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

import os
from pathlib import Path

META_PACKAGE_NAME = "ansys-saf-sdk"
INITIAL_META_PACKAGE_VERSION = "0.1.0"

REPO_ROOT = (
    Path(os.environ["GITHUB_WORKSPACE"]) if os.environ.get("GITHUB_WORKSPACE") else Path(__file__).resolve().parents[3]
)
PYPROJECT_PATH = REPO_ROOT / "packages" / "saf-sdk" / "pyproject.toml"

# Maps each PyPI package name to its repository library directory, used to look up its GitHub release tag.
PACKAGE_LIBRARY_DIRS = {
    "ansys-bdm-api": "bdm-python-api",
    "ansys-bdm-shared-volume": "bdm-python-shared-volume",
    "ansys-saf-glow-engine": "glow-engine",
    "ansys-saf-desktop-installer": "saf-desktop-installer",
    "ansys-saf-desktop-orchestrator": "saf-desktop-orchestrator",
    "ansys-iam-oidc": "saf-iam-oidc",
    "ansys-saf-product-configuration": "saf-product-configuration",
    "ansys-saf-product-manager": "saf-product-manager",
}

DEPENDENCY_PINNING_ENV_VAR = "SAF_SDK_DEPENDENCY_PINNING"

PACKAGE_VERSION_ENV_VARS = {
    "ansys-bdm-api": "USER_SELECTED_BDM_API_VERSION",
    "ansys-bdm-shared-volume": "USER_SELECTED_BDM_SHARED_VOLUME_VERSION",
    "ansys-saf-glow-engine": "USER_SELECTED_ANSYS_SAF_GLOW_ENGINE_VERSION",
    "ansys-saf-desktop-installer": "USER_SELECTED_ANSYS_SAF_DESKTOP_INSTALLER_VERSION",
    "ansys-saf-desktop-orchestrator": "USER_SELECTED_ANSYS_SAF_DESKTOP_ORCHESTRATOR_VERSION",
    "ansys-iam-oidc": "USER_SELECTED_ANSYS_IAM_OIDC_VERSION",
    "ansys-saf-product-configuration": "USER_SELECTED_ANSYS_SAF_PRODUCT_CONFIGURATION_VERSION",
    "ansys-saf-product-manager": "USER_SELECTED_ANSYS_SAF_PRODUCT_MANAGER_VERSION",
}
