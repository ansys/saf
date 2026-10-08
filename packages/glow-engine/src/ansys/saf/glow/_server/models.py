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

from typing import Generic, TypeVar
import uuid

from pydantic import (
    UUID4,
    AwareDatetime,
    BaseModel,
    Field,
    field_validator,
)

from ansys.bdm.api import EntityHandle
from ansys.saf.glow._core.instance.recoverystate import TRecoveryStateInfo
from ansys.saf.glow._core.method_status import MethodState
from ansys.saf.glow._core.solution import Solution
from ansys.saf.glow._server.schemas import InstanceBase, ProjectInfo
from ansys.saf.glow.solution import RecoveryStateInfo

T_co = TypeVar("T_co", bound=Solution, contravariant=True)


class VersionedModel(BaseModel):
    schema_version: int = 1


class Instance(InstanceBase[TRecoveryStateInfo]): ...


class BdmLockModel(BaseModel):
    id: UUID4 = Field(default_factory=uuid.uuid4)
    expiration_date: AwareDatetime | None = None

    def __eq__(self, other: object) -> bool:
        return isinstance(other, BdmLockModel) and self.id == other.id

    def __hash__(self) -> int:
        return self.id.__hash__()


class ProjectSchema(VersionedModel, BaseModel, Generic[T_co]):
    schema_version: int = 1
    solution_name: str | None = None  # optional for backward compatibility
    solution: T_co
    method_states: dict[str, dict[str, MethodState]]
    instances: dict[str, dict[str, Instance[RecoveryStateInfo]]]
    bdm_locks: list[BdmLockModel] = []

    def collect_live_handles(self) -> list[EntityHandle]:
        live_handles = self.solution.live_handles
        # find handles for product instances
        for step_name, step_instances in self.instances.items():
            step = self.solution.get_steps_fields()[step_name]
            for instance_name, instance_record in step_instances.items():
                create_instance = step._get_create_instance_by_name()[  # pyright: ignore[reportPrivateUsage]
                    instance_name
                ]
                recovery_state_info = instance_record.model_dump().get("recovery_state_info", None)
                if recovery_state_info is None:
                    continue
                instance = create_instance.recovery_state_type.model_validate(recovery_state_info)
                live_handles.extend(instance.live_handles)
        return live_handles

    @field_validator("solution_name")
    @classmethod
    def must_be_same_solution(cls, v: str | None) -> str | None:
        solution_field = cls.model_fields.get("solution")
        solution = solution_field.annotation if solution_field else None
        if solution and v and solution.__name__ != v:
            raise ValueError(
                f"The type of the Solution to validate '{v}' does not match "
                f"the current Solution type '{solution.__name__}'.",
            )
        return v


class ProjectModel(ProjectInfo, ProjectSchema[T_co], Generic[T_co]): ...
