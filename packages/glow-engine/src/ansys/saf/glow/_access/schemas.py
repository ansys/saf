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

"""Pydantic models for project access control. Must stay free of database imports."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ProjectRole(StrEnum):
    """Role of a user in a project."""

    owner = "owner"
    viewer = "viewer"


class WriteRequestStatus(StrEnum):
    """Status of a request to obtain the project write lock."""

    pending = "pending"
    approved = "approved"
    denied = "denied"
    withdrawn = "withdrawn"


class ProjectMemberInfo(BaseModel):
    user_id: str
    role: ProjectRole


class WriteRequestInfo(BaseModel):
    id: str
    requester_id: str
    status: WriteRequestStatus
    created_at: datetime
    decided_by: str | None = None
    decided_at: datetime | None = None


class ProjectAccessRecord(BaseModel):
    """Raw database view of the access state of a project."""

    project_id: str
    members: list[ProjectMemberInfo] = Field(default_factory=list)
    holder_id: str | None = None
    acquired_at: datetime | None = None
    last_write_at: datetime | None = None
    version: int = 0
    requests: list[WriteRequestInfo] = Field(default_factory=list)


class ProjectAccessSummary(BaseModel):
    owner_id: str | None = None
    holder_id: str | None = None
    my_role: ProjectRole | None = None
    pending_request_count: int = 0


class AuditEntryInfo(BaseModel):
    project_id: str
    actor_id: str
    action: str
    details: dict[str, Any] = Field(default_factory=dict)
    at: datetime
