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

"""Project access control API: members, ownership, write lock, write requests and the live access stream.

These routes are only mounted when project access control is enabled. They are thin wrappers around
``AccessCrud``, which decides who may do what. Project routes require the caller to be a member or a super admin
before anything else, so that strangers get the same 404 whether or not the project exists.
"""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from wsproto.utilities import LocalProtocolError

from ansys.iam.oidc import get_websocket_subprotocol
from ansys.saf.glow._access.dependencies import require_project_metadata, require_project_read_for_websocket
from ansys.saf.glow._access.schemas import AuditEntryInfo, ProjectAccess, UserRef, WriteRequestInfo
from ansys.saf.glow._server.dependencies import (
    AccessCrudDep,
    PrincipalDep,
    SettingsDep,
    WSAccessCrudDep,
    WSPrincipalDep,
    oidc_scheme_ws_with_roles,
)
from ansys.saf.glow._server.exceptions import GlowErrorBase
from ansys.saf.glow._server.routers.events import _websocket_connected  # pyright: ignore[reportPrivateUsage]

logger = logging.getLogger(__name__)

TAG = "access"
router = APIRouter(tags=[TAG])
"""HTTP routes. Included with the global authentication dependency."""

events_router = APIRouter(prefix="/events", tags=[TAG])
"""Websocket routes. Included without it: websockets authenticate with their own dependency."""

_project_access = [Depends(require_project_metadata)]


class AccessMe(BaseModel):
    user_id: str | None
    is_super_admin: bool


class FailedMethods(BaseModel):
    failed: list[str]


# --------------------------------------------------------------------------------------------------------------------
# Identity and audit


@router.get("/access/me")
async def get_me(principal: PrincipalDep) -> AccessMe:
    """Who the caller is, as far as project access control is concerned."""
    return AccessMe(user_id=principal.user_id, is_super_admin=principal.is_super_admin)


@router.get("/access/audit")
async def list_audit(
    principal: PrincipalDep,
    access: AccessCrudDep,
    project_id: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[AuditEntryInfo]:
    """Audit log of the access changes, most recent first. Super admins only."""
    return await access.list_audit(project_id, page, page_size, principal)


# --------------------------------------------------------------------------------------------------------------------
# Access state, members and ownership


@router.get("/projects/{project_id}/access", dependencies=_project_access)
async def get_access(project_id: str, principal: PrincipalDep, access: AccessCrudDep) -> ProjectAccess:
    return await access.get_access(project_id, principal)


@router.post("/projects/{project_id}/access/members", dependencies=_project_access)
async def share(project_id: str, body: UserRef, principal: PrincipalDep, access: AccessCrudDep) -> ProjectAccess:
    """Share the project with a user, as a viewer. Owner only."""
    return await access.share(project_id, body.user_id, principal)


@router.delete("/projects/{project_id}/access/members/{user_id}", dependencies=_project_access)
async def unshare(project_id: str, user_id: str, principal: PrincipalDep, access: AccessCrudDep) -> ProjectAccess:
    """Stop sharing the project with a user. Owner only."""
    return await access.unshare(project_id, user_id, principal)


@router.post("/projects/{project_id}/access:transfer-ownership", dependencies=_project_access)
async def transfer_ownership(
    project_id: str,
    body: UserRef,
    principal: PrincipalDep,
    access: AccessCrudDep,
) -> ProjectAccess:
    """Give the project to another member. Owner only."""
    return await access.transfer_ownership(project_id, body.user_id, principal)


@router.post("/projects/{project_id}/access:assign-owner", dependencies=_project_access)
async def assign_owner(
    project_id: str,
    body: UserRef,
    principal: PrincipalDep,
    access: AccessCrudDep,
) -> ProjectAccess:
    """Make a user the owner of the project. Super admins only."""
    return await access.assign_owner(project_id, body.user_id, principal)


# --------------------------------------------------------------------------------------------------------------------
# Write lock


@router.post("/projects/{project_id}/lock:acquire", dependencies=_project_access)
async def acquire_lock(project_id: str, principal: PrincipalDep, access: AccessCrudDep) -> ProjectAccess:
    return await access.acquire(project_id, principal)


@router.post("/projects/{project_id}/lock:release", dependencies=_project_access)
async def release_lock(project_id: str, principal: PrincipalDep, access: AccessCrudDep) -> ProjectAccess:
    return await access.release(project_id, principal)


@router.post("/projects/{project_id}/lock:take-over", dependencies=_project_access)
async def take_over_lock(project_id: str, principal: PrincipalDep, access: AccessCrudDep) -> ProjectAccess:
    """Take the write lock from its holder. Owner only."""
    return await access.take_over(project_id, principal)


@router.post("/projects/{project_id}/lock:force-release", dependencies=_project_access)
async def force_release_lock(project_id: str, principal: PrincipalDep, access: AccessCrudDep) -> ProjectAccess:
    """Release the write lock whoever holds it. Super admins only."""
    return await access.force_release(project_id, principal)


# --------------------------------------------------------------------------------------------------------------------
# Write requests


@router.post("/projects/{project_id}/write-requests", dependencies=_project_access)
async def create_write_request(project_id: str, principal: PrincipalDep, access: AccessCrudDep) -> WriteRequestInfo:
    return await access.create_request(project_id, principal)


@router.post("/projects/{project_id}/write-requests/{request_id}:approve", dependencies=_project_access)
async def approve_write_request(
    project_id: str,
    request_id: str,
    principal: PrincipalDep,
    access: AccessCrudDep,
) -> ProjectAccess:
    return await access.approve_request(project_id, request_id, principal)


@router.post("/projects/{project_id}/write-requests/{request_id}:deny", dependencies=_project_access)
async def deny_write_request(
    project_id: str,
    request_id: str,
    principal: PrincipalDep,
    access: AccessCrudDep,
) -> ProjectAccess:
    return await access.deny_request(project_id, request_id, principal)


@router.post("/projects/{project_id}/write-requests/{request_id}:withdraw", dependencies=_project_access)
async def withdraw_write_request(
    project_id: str,
    request_id: str,
    principal: PrincipalDep,
    access: AccessCrudDep,
) -> ProjectAccess:
    return await access.withdraw_request(project_id, request_id, principal)


# --------------------------------------------------------------------------------------------------------------------
# Maintenance


@router.post("/projects/{project_id}/methods:fail-stuck", dependencies=_project_access)
async def fail_stuck_methods(project_id: str, principal: PrincipalDep, access: AccessCrudDep) -> FailedMethods:
    """Mark as failed the methods that have been running for too long. Owner or super admin."""
    return FailedMethods(failed=await access.fail_stuck_methods(project_id, principal))


# --------------------------------------------------------------------------------------------------------------------
# Live access stream


@events_router.websocket(
    "/projects/{project_id}/access",
    dependencies=[
        Depends(oidc_scheme_ws_with_roles),
        Depends(require_project_read_for_websocket),
    ],
)
async def stream_access(
    websocket: WebSocket,
    project_id: str,
    principal: WSPrincipalDep,
    access: WSAccessCrudDep,
    settings: SettingsDep,
) -> None:
    """Send the access state of the project on connection, then each time it changes.

    The connection is closed with 1008 as soon as the caller is no longer a member of the project.
    """
    context = f"access stream, project: {project_id}"
    await websocket.accept(subprotocol=get_websocket_subprotocol(websocket))
    last_version: int | None = None
    try:
        while True:
            try:
                state = await access.get_access(project_id, principal)
            except GlowErrorBase as ex:
                logger.info(f"closing {context}: {ex.status_code}")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Forbidden")
                return
            if state.version != last_version:
                last_version = state.version
                await websocket.send_json(state.model_dump(mode="json"))
            if not await _websocket_connected(websocket):
                logger.info(f"websocket disconnected (on receive) {context}")
                return
            await asyncio.sleep(settings.glow_project_access_poll_interval)
    except (WebSocketDisconnect, LocalProtocolError):
        logger.info(f"websocket disconnected (on transmit) {context}")
