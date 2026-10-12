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

from ansys.bdm.api import NO_ENTITY, EntityHandle, RecursiveDictionaryOfEntityHandles
from ansys.iam.oidc import UserInfo
from ansys.saf.glow._core.field_state import FieldState
from ansys.saf.glow._core.instance.decorator import create_instance, instance
from ansys.saf.glow._core.instance.manager import InstanceManager, ProductInstanceManager
from ansys.saf.glow._core.instance.recoverystate import RecoveryStateInfo
from ansys.saf.glow._core.long_running import long_running
from ansys.saf.glow._core.method_status import MethodState, MethodStatus
from ansys.saf.glow._core.migrations import Migration, MigrationContext, MigrationTransformation
from ansys.saf.glow._core.solution import MethodIdentifier, Solution, StepsModel
from ansys.saf.glow._core.step_model import StepModel, Transaction
from ansys.saf.glow._core.step_spec import StepSpec
from ansys.saf.glow._core.transaction import transaction
from ansys.saf.glow._crud.solution_configuration_models import SolutionConfiguration
from ansys.saf.glow._server.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)

__all__ = [
    "InstanceManager",
    "ProductInstanceManager",
    "RecoveryStateInfo",
    "BadRequestError",
    "create_instance",
    "ConflictError",
    "EntityHandle",
    "RecursiveDictionaryOfEntityHandles",
    "NO_ENTITY",
    "NotFoundError",
    "ForbiddenError",
    "FieldState",
    "instance",
    "MigrationContext",
    "long_running",
    "MethodIdentifier",
    "MethodState",
    "MethodStatus",
    "Migration",
    "MigrationTransformation",
    "Solution",
    "SolutionConfiguration",
    "StepsModel",
    "StepModel",
    "StepSpec",
    "transaction",
    "Transaction",
    "UserInfo",
]
