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

"""FastAPI dependencies enforcing project access control on the routes of a project.

Routes add them ahead of ``validate_project`` so that a non-member gets the same answer whether or not the project
exists. Every dependency is a no-op when project access control is disabled.
"""

import logging

from fastapi import WebSocketException, status

from ansys.saf.glow._server.dependencies import AccessCrudDep, PrincipalDep, WSAccessCrudDep, WSPrincipalDep
from ansys.saf.glow._server.exceptions import GlowErrorBase

logger = logging.getLogger(__name__)


def _project_id(project_id: str) -> str:
    # fastapi keeps the colon in "project_id:export", so let's remove it.
    return project_id.split(":")[0]


async def require_project_read(project_id: str, principal: PrincipalDep, access: AccessCrudDep) -> None:
    """The caller must be a member of the project (404 otherwise)."""
    await access.check_read(_project_id(project_id), principal)


async def require_project_write(project_id: str, principal: PrincipalDep, access: AccessCrudDep) -> None:
    """The caller must hold the write lock of the project (404 for non-members, 423 for other members)."""
    await access.check_write(_project_id(project_id), principal)


async def require_project_owner(project_id: str, principal: PrincipalDep, access: AccessCrudDep) -> None:
    """The caller must own the project, or be a super admin (404 for non-members, 403 for other members)."""
    await access.check_owner(_project_id(project_id), principal, allow_super_admin=True)


async def require_project_metadata(project_id: str, principal: PrincipalDep, access: AccessCrudDep) -> None:
    """The caller must be a member of the project or a super admin (404 otherwise)."""
    await access.check_metadata(_project_id(project_id), principal)


async def require_project_read_for_websocket(
    project_id: str,
    principal: WSPrincipalDep,
    access: WSAccessCrudDep,
) -> None:
    """Close the websocket with 1008 unless the caller is a member of the project.

    The close reason is the same whether the project exists or not.
    """
    try:
        await access.check_read(_project_id(project_id), principal)
    except GlowErrorBase as ex:
        logger.debug(f"Websocket refused for project '{project_id}': {ex.status_code}")
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Forbidden") from None
