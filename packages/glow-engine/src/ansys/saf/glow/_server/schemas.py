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

# pyright: reportIncompatibleVariableOverride=false
from datetime import datetime
from typing import Generic, Self

from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from ansys.saf.glow._access.schemas import ProjectAccessSummary
from ansys.saf.glow._config.const import JOB_DEFAULT_MAX_RUNNING_TIME
from ansys.saf.glow._core.instance.recoverystate import TRecoveryStateInfo
from ansys.saf.glow._storage.os import (
    INVALID_CHARACTERS,
    is_filepath_invalid,
)


class ProjectBase(BaseModel):
    display_name: str = Field(..., description="The project name displayed to the user.", examples=["my project"])
    description: str = Field(default="", description="The project description.")

    @field_validator("display_name")
    @classmethod
    def display_name_is_filepath_valid(cls, v: str):
        # At some point, we may use the display_name as part of a filepath or filename.
        # For example, when exporting a project. Ensure that it's valid for that kind of use case.
        if is_filepath_invalid(v):
            raise ValueError(
                f"Display name cannot contain any of the following characters: {' '.join(INVALID_CHARACTERS)} ..)",
            )
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "display_name": "test project",
                    "description": "my project description",
                },
            ],
        },
    )


class ProjectInfo(ProjectBase):
    date_created: datetime = Field(
        default_factory=datetime.now,
        title="Creation date",
        description="Date and time of creation",
    )
    date_modified: datetime = Field(  # pyright: ignore[reportAssignmentType]
        default=None,
        validate_default=True,
        title="Last modification date",
        description="Date and time of last modification",
    )
    name: str = Field(
        ...,
        description="The URI path identifying the project resource.",
        pattern="^projects/.+",
        examples=["projects/1a34b678"],
    )
    access: ProjectAccessSummary | None = Field(
        default=None,
        description=(
            "Who owns, holds the write lock of and has access to the project. "
            "Null when project access control is disabled, and in responses that do not carry it."
        ),
    )
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "display_name": "test project",
                    "description": "my project description",
                    "name": "projects/2ztdlpa2",
                    "date_created": "2023-01-01T01:02:03.000004",
                    "date_modified": "2024-01-01T01:02:03.000004",
                },
            ],
        },
    )

    @field_validator("date_modified", mode="before")
    @classmethod
    def set_date_modified(cls, value: datetime | None, info: ValidationInfo):
        if value is None:
            return info.data["date_created"]
        return value

    @property
    def project_id(self) -> str:
        return self.name.removeprefix("projects/")

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return False
        return self.name == other.name


class ListProjectRequest(BaseModel):
    page_size: int = Field(
        100,
        description="""The maximum number of projects to return. The service may return fewer than this value.
            If unspecified, at most 100 projects will be returned. The maximum value is 100;
            values above 100 will be coerced to 100.""",
        gt=0,
    )
    page: int = Field(
        1,
        description="""The page number to return, starting from 1.
        This value is used in conjunction with `page_size` to determine the range of projects to return.
        For example, if `page_size` is 10 and `page` is 2, projects 11-20 will be returned.""",
        gt=0,
    )
    order_by: str | None = Field(
        None,
        description=(
            """Comma-separated list of fields to order by.
            The default sorting order is ascending.
            To specify descending order for a field, users append a " desc" suffix; for example: "foo desc, bar".

            Supported fields: display_name, description, date_created, date_modified, name.
            """
        ),
        examples=[
            "date_modified desc, name",
            "description asc, display_name desc",
        ],
    )
    filter: str | None = Field(
        None,
        description="""An optional filter expression string to narrow down the listed projects.
            Follows the syntax: `<field> <operator> <value> [AND <field> <operator> <value>]...`

            Supported fields: ``display_name``, ``description``, ``date_created``, ``date_modified``.

            Supported operators: ``=``, ``!=``, ``<``, ``>``, ``<=``, ``>=``.
            Note: ``display_name`` and ``description`` only support ``=`` (case-insensitive, contains match).

            Date values must be ISO 8601 strings (e.g., ``2024-01-15T00:00:00``, ``2024-01-15``).""",
        examples=[
            "display_name = Motor",
            "description = benchmark",
            "date_created >= 2024-01-01T00:00:00",
            'display_name = "My Project" AND date_created >= 2024-01-01T00:00:00',
        ],
    )
    orphans_only: bool = Field(
        False,
        description="""Only list the projects that have no owner (super admins only).""",
    )

    @field_validator("page_size", mode="after")
    @classmethod
    def validate_page_size(cls, value: int) -> int:
        if value > 100:
            return 100
        return value

    @field_validator("order_by", mode="after")
    @classmethod
    def validate_order_by(cls, value: str | None) -> str | None:
        if value is None:
            return value

        allowed_values = ("display_name", "description", "date_created", "date_modified", "name")
        for field in value.split(","):
            parts = field.strip().split()
            if len(parts) == 0 or len(parts) > 2:
                raise ValueError(
                    "Invalid order_by syntax.",
                )
            field_name = parts[0].lower()
            direction = parts[1].lower() if len(parts) == 2 else "asc"
            if direction not in ("asc", "desc"):
                raise ValueError(
                    "Invalid order_by direction.",
                )
            if field_name not in allowed_values:
                raise ValueError(
                    f"Invalid order_by field: '{field_name}'. Allowed fields are: {', '.join(allowed_values)}.",
                )

        return value


class ListProjectResponse(BaseModel):
    projects: list[ProjectInfo] = Field(..., description="The list of projects.")

    current_page: int = Field(
        ...,
        description=(
            """The current page number. The first page is numbered 1.
            This value is used in conjunction with `total_pages` to determine if there are more pages to retrieve."""
        ),
    )
    total_pages: int = Field(..., description="The total number of pages available.")
    page_size: int = Field(..., description="""The number of projects requested per page.""")
    total_projects: int = Field(..., description="The total number of projects available.")


class CreateProjectRequest(ProjectBase): ...


class ModifyProjectRequest(ProjectBase):
    display_name: str | None = Field(
        default=None,
        description="The project name displayed to the user.",
        examples=["my project"],
    )
    description: str | None = Field(
        default=None,
        description="The project description.",
        examples=["my project description"],
    )

    @model_validator(mode="after")
    def modify_at_least_one_field(self) -> Self:
        if self.display_name is None and self.description is None:
            raise ValueError("At least one of 'display_name' or 'description' must be provided")
        return self


class InstanceBase(BaseModel, Generic[TRecoveryStateInfo]):
    name: str = Field(
        ...,
        description="The URI path identifying the instance resource.",
        examples=["projects/1a34b678/steps/test-step/instances/x"],
        pattern="^projects/.+",
    )
    # pim_name is allowed to be an empty string because, when importing a project,
    # it is reset to force the initialization with the new PIM.
    pim_name: str = Field(
        ...,
        description="The URI for the instance used by the Product Instance Manager",
        examples=["instances/x"],
        pattern="^$|^instances/.+",
    )
    product_version: str = Field(
        ...,
        description="The Product Instance Manager identifier for the version of the product",
    )
    service_name: str = Field(..., description="The Product Instance Manager identifier for the service in the product")
    max_execution_time: int = Field(
        default=JOB_DEFAULT_MAX_RUNNING_TIME,
        description="Amount of time (in seconds) after which an instance managed by Ansys HPS will be timed-out by HPS."
        "If not set, the value is set to 7200 seconds (2 hours).",
    )
    recovery_state_info: TRecoveryStateInfo | None = Field(
        default=None,
        description="The state information used to restore the product instance.",
    )


class InstanceResponse(InstanceBase[TRecoveryStateInfo]): ...


class NoInstanceResponse(Response):
    def __init__(self) -> None:
        super().__init__(status_code=204)


class CreateInstanceRequest(InstanceBase[TRecoveryStateInfo]):
    pass


class ModifyInstanceRequest(BaseModel, Generic[TRecoveryStateInfo]):
    pim_name: str | None = Field(
        default=None,
        description="The URI for the instance used by the Product Instance Manager",
        examples=["instances/x"],
        pattern="^instances/.+",
    )
    recovery_state_info: TRecoveryStateInfo | None = Field(
        default=None,
        description="The state information used to restore the product instance.",
    )


class SolutionInfo(BaseModel):
    """Information about the served solution."""

    name: str = Field(..., description="The Python class name of the solution.")
    display_name: str = Field(..., description="The user-facing name of the solution.")
    schema_version: int = Field(..., description="The version of the solution data schema.")


class ServerInfo(BaseModel):
    """Information about the running Solution API server."""

    solution: SolutionInfo = Field(..., description="Information about the served solution.")
    glow_version: str = Field(..., description="Version of the installed GLOW engine package.")
    external_api_url: str = Field(..., description="External-facing URL of this API server.")
