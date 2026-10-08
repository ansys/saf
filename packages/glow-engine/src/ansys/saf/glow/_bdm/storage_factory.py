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

from __future__ import annotations

from pathlib import Path
import random
import string

from ansys.bdm.shared_volume.storage_configuration import (
    SharedFilesystemConfiguration,
    SharedFilesystemContextConfiguration,
)
from ansys.bdm.shared_volume.storage_factory import StorageScopeFactory
from ansys.saf.glow._bdm.storage_contexts import (
    CLIENT_CONTEXT,
    GC_CONTEXT,
    METHOD_CONTEXT,
    PRODUCT_CONTEXT,
    PRODUCT_MANAGER_CONTEXT,
    PROJECT_BOUNDARY,
    RESTAPI_CONTEXT,
)
from ansys.saf.glow._bdm.storage_variable_names import PROJECT_ID, ROOT, SHORTID
from ansys.saf.glow._server.hidden_project_directories import bdm_shared_directory_name


def random_shortid() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choices(alphabet, k=8))  # noqa: S311 #nosec


def _make_shared_filesystem_context_config(name: str) -> SharedFilesystemContextConfiguration:
    uuid_variable = f"${SHORTID}"
    return SharedFilesystemContextConfiguration(
        relative_path=Path(f"${PROJECT_ID}/{bdm_shared_directory_name}/{name}_{uuid_variable}"),
    )


def create_shared_storage_factory() -> StorageScopeFactory:
    client_config = _make_shared_filesystem_context_config(CLIENT_CONTEXT)
    project_config = _make_shared_filesystem_context_config(RESTAPI_CONTEXT)
    transaction_config = _make_shared_filesystem_context_config(METHOD_CONTEXT)
    product_config = _make_shared_filesystem_context_config(PRODUCT_CONTEXT)
    product_manager_config = _make_shared_filesystem_context_config(PRODUCT_MANAGER_CONTEXT)
    gc_config = _make_shared_filesystem_context_config(GC_CONTEXT)
    config = SharedFilesystemConfiguration(
        shared_filesystem_root=Path(f"${ROOT}"),
        contexts={
            PROJECT_BOUNDARY: SharedFilesystemContextConfiguration(
                relative_path=Path(f"${PROJECT_ID}/{bdm_shared_directory_name}"),
            ),
            CLIENT_CONTEXT: client_config,
            RESTAPI_CONTEXT: project_config,
            METHOD_CONTEXT: transaction_config,
            PRODUCT_CONTEXT: product_config,
            PRODUCT_MANAGER_CONTEXT: product_manager_config,
            GC_CONTEXT: gc_config,
        },
    )

    return StorageScopeFactory(config)
