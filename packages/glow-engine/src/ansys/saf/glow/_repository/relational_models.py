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

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ansys.saf.glow._access.schemas import ProjectRole, WriteRequestStatus
from ansys.saf.glow._core.field_state import FieldState
from ansys.saf.glow._core.method_status import MethodStatus


class Base(AsyncAttrs, DeclarativeBase):
    pass


class HpsAuth(Base):
    """will be used for storing hps auth information but for now it's just used for locking hence no fields"""

    __tablename__ = "hps_auth"
    id: Mapped[str] = mapped_column(Integer, primary_key=True, index=True)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, index=True)  # we use a string for the id
    date_created: Mapped[datetime] = mapped_column(DateTime)
    date_modified: Mapped[datetime] = mapped_column(DateTime)
    project_display_name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    solution_display_name: Mapped[str] = mapped_column(String)
    glow_schema_version: Mapped[int] = mapped_column(Integer)
    solution_schema_version: Mapped[int] = mapped_column(Integer)

    # columns in other tables that have a foreign key relationship with this table
    steps: Mapped[list["Step"]] = relationship("Step", back_populates="project")
    bdm_locks: Mapped[list["BdmLock"]] = relationship("BdmLock", back_populates="project")


# Mapping between ProjectInfo fields and Project fields for sorting and filtering in the repository
PROJECT_MAPPING_FIELDS = {
    "display_name": Project.project_display_name,
    "description": Project.description,
    "date_created": Project.date_created,
    "date_modified": Project.date_modified,
    "name": Project.id,
}


class ProjectMethodLock(Base):
    """this is just used for locking"""

    __tablename__ = "project_method_locks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # This column has a loose foreign key relationship with the projects table
    # Tying this column to the projects table as a real foreign key causes problems with locking hence
    # this form.
    project_id: Mapped[str] = mapped_column(String(24), index=True)


class Step(Base):
    __tablename__ = "steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)

    # columns in this table that have a foreign key relationship with other tables
    project_id: Mapped[str] = mapped_column(String(24), ForeignKey("projects.id"), index=True)
    project: Mapped[Project] = relationship("Project", back_populates="steps")

    # columns in other tables that have a foreign key relationship with this table
    step_fields: Mapped[list["StepField"]] = relationship("StepField", back_populates="step")
    method_states: Mapped[list["MethodState"]] = relationship("MethodState", back_populates="step")
    instances: Mapped[list["Instance"]] = relationship("Instance", back_populates="step")
    event_sources: Mapped[list["EventSource"]] = relationship("EventSource", back_populates="step")


class StepField(Base):
    __tablename__ = "step_fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    value: Mapped[Any] = mapped_column(JSON)  # this is the JSON of the value
    state: Mapped[FieldState] = mapped_column(Enum(FieldState))  # The state of the field
    contains_entity_handles: Mapped[bool] = mapped_column(Boolean, index=True)  # The kind of handle for the field

    # columns in this table that have a foreign key relationship with other tables
    step_id: Mapped[int] = mapped_column(Integer, ForeignKey("steps.id"), index=True)
    step: Mapped[Step] = relationship("Step", back_populates="step_fields")


class MethodState(Base):
    __tablename__ = "method_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    method_name: Mapped[str] = mapped_column(String, index=True)  # The name of the method
    status: Mapped[MethodStatus] = mapped_column(Enum(MethodStatus))  # The state of the method
    result: Mapped[Any | None] = mapped_column(JSON)  # The value returned by the method, if any
    status_code: Mapped[int | None] = mapped_column(
        Integer,
    )  # If an error occurred, the result of the method execution encoded in the HTTP response status code standard
    exception_message: Mapped[str | None] = mapped_column(
        String,
    )  # If an error occurred, the exception message for the failure
    exception_stack: Mapped[str | None] = mapped_column(String)  # If an error occurred, the stack trace for the failure
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )  # When the method last entered the Running state

    # columns in this table that have a foreign key relationship with other tables
    step_id: Mapped[int] = mapped_column(Integer, ForeignKey("steps.id"), index=True)
    step: Mapped[Step] = relationship("Step", back_populates="method_states")


class Instance(Base):
    __tablename__ = "instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    pim_name: Mapped[str] = mapped_column(String, index=True)
    product_version: Mapped[str] = mapped_column(String)
    service_name: Mapped[str] = mapped_column(String)
    max_execution_time: Mapped[int] = mapped_column(Integer)
    recovery_state_info: Mapped[Any] = mapped_column(JSON)

    # columns in this table that have a foreign key relationship with other tables
    step_id: Mapped[int] = mapped_column(Integer, ForeignKey("steps.id"), index=True)
    step: Mapped[Step] = relationship("Step", back_populates="instances")


class BdmLock(Base):
    __tablename__ = "bdm_locks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String, index=True)
    expiration_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # columns in this table that have a foreign key relationship with other tables
    project_id: Mapped[str] = mapped_column(String(24), ForeignKey("projects.id"), index=True)
    project: Mapped[Project] = relationship("Project", back_populates="bdm_locks")


class EventSource(Base):
    __tablename__ = "event_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)

    # columns in this table that have a foreign key relationship with other tables
    step_id: Mapped[int] = mapped_column(Integer, ForeignKey("steps.id"), index=True)
    step: Mapped[Step] = relationship("Step", back_populates="event_sources")

    events: Mapped[list["Event"]] = relationship("Event", back_populates="event_source")
    event_listeners: Mapped[list["EventListener"]] = relationship("EventListener", back_populates="event_source")


class Event(Base):
    __tablename__ = "events"

    # Important: we need to use sqlite_autoincrement=True for the id column in order to guarantee that the ids
    # are not reused after deletion which is important for the event listener logic
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Ideally we'd a JSON column type for payload but SQLite and postgresql handle JSON differently
    # (SQLite converts floats into integers when the float is an integer value).
    # Not using JSON may restrict future queries on this column.
    payload: Mapped[str] = mapped_column(String)

    # columns in this table that have a foreign key relationship with other tables
    event_source_id: Mapped[int] = mapped_column(Integer, ForeignKey("event_sources.id"), index=True)
    event_source: Mapped[EventSource] = relationship("EventSource", back_populates="events")

    event_listeners: Mapped[list["EventListener"]] = relationship("EventListener", back_populates="last_fetched_event")


class EventListener(Base):
    __tablename__ = "event_listeners"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expiration: Mapped[int] = mapped_column(BigInteger)

    # columns in this table that have a foreign key relationship with other tables
    event_source_id: Mapped[int] = mapped_column(Integer, ForeignKey("event_sources.id"), index=True)
    event_source: Mapped[EventSource] = relationship("EventSource", back_populates="event_listeners")

    last_fetched_event_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("events.id"),
        nullable=True,
        index=True,
    )
    last_fetched_event: Mapped[Event | None] = relationship("Event", back_populates="event_listeners")


class ProjectMember(Base):
    """A user's role in a project. Only user ids (the ``sub`` claim) are stored."""

    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(24), ForeignKey("projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    role: Mapped[ProjectRole] = mapped_column(Enum(ProjectRole))


class ProjectWriteLock(Base):
    """The single-writer lock of a project. ``version`` is bumped on every change to the project access state."""

    __tablename__ = "project_write_locks"

    project_id: Mapped[str] = mapped_column(String(24), ForeignKey("projects.id"), primary_key=True)
    holder_id: Mapped[str | None] = mapped_column(String, nullable=True)
    acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_write_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=0)


class ProjectWriteRequest(Base):
    """A request from a project member to obtain the write lock."""

    __tablename__ = "project_write_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # uuid
    project_id: Mapped[str] = mapped_column(String(24), ForeignKey("projects.id"), index=True)
    requester_id: Mapped[str] = mapped_column(String)
    status: Mapped[WriteRequestStatus] = mapped_column(Enum(WriteRequestStatus))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProjectAuditEntry(Base):
    """Audit trail of access changes.

    ``project_id`` is deliberately not a foreign key so that entries survive the deletion of the project.
    """

    __tablename__ = "project_audit_entries"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(24), index=True)
    actor_id: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    details: Mapped[Any] = mapped_column(JSON)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
