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

from enum import Enum
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, field_validator, model_validator

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow._core.step_spec import StepSpec
from ansys.saf.glow._core.transaction import transaction
from ansys.saf.glow.solution import (
    Solution,
    StepModel,
    StepsModel,
)


def validate_even_numbers(v: int) -> int:
    """Ensure that the given value is an even number."""
    assert v % 2 == 0, f"{v} is not an even number"
    return v


SquaredNumber = Annotated[int, AfterValidator(validate_even_numbers)]


class MyEnum(Enum):
    a = "a"
    b = "b"


class User(BaseModel):
    user_id: int
    name: str


class Users(BaseModel):
    users: list[User]


class MinimalStep(StepModel):
    """A step for testing purpose."""

    x: int = 99
    name: str = "a string"
    optional_thing: str | None = None
    value: int = 2
    squared_value: int = 4
    even_numbers: list[SquaredNumber] = [2, 4]
    users: Users = Users(users=[User(user_id=1, name="Zea Woods")])
    my_enum: MyEnum = MyEnum.a
    my_tuple: tuple[str, str] = ("a", "b")
    my_list_of_tuple: list[tuple[str, str]] = [("a", "b"), ("c", "d")]
    dict_int_int: dict[int, int] = {}
    dict_user: dict[str, User] = {"admin": User(user_id=0, name="Admin User")}
    space_dict: dict[str, str] = {"key with space": "value"}
    dot_dict: dict[str, str] = {"key.with.dots": "value"}
    slash_dict: dict[str, str] = {"key/s": "value"}
    accent_dict: dict[str, str] = {"éèàêë": "value"}
    special_char_dict: dict[str, str] = {"()+[]{}%*<>?-_": "value"}
    _private: str = "private"
    hello_file: EntityHandle = NO_ENTITY
    handles: list[EntityHandle] = []

    @field_validator("name")  # type: ignore
    @classmethod
    def name_must_contain_space(cls, v: str) -> str:
        """Ensure that the field 'name' must contain a space."""
        if " " not in v:
            raise ValueError(f"{v} must contain a space")
        return v

    @model_validator(mode="after")
    def validate_squared_value(self) -> Self:
        """Ensure that 'squared_value' is always equal to the square of 'value'.
        and that at least one flag is False"""
        if self.value * self.value != self.squared_value:
            raise ValueError("squared_value must be equal to value x value.")
        return self

    @transaction(self=StepSpec(upload=["x"]))
    def dont_change_x(self) -> None:
        self.x = 99

    @transaction(self=StepSpec(upload=["hello_file"]))
    def create_hello_file(self) -> None:
        file_path = self.storage_scope.get_storage_root() / "hello.txt"
        file_path.write_text("Hello!")
        self.hello_file = self.storage_scope.store(file_path)


class OtherStep(StepModel):
    id: str = "hey"


class FieldlessStep(StepModel):
    @transaction()
    def square(self, number: int) -> int:
        return number**2


class Steps(StepsModel):
    minimal_step: MinimalStep
    other_step: OtherStep
    fieldless_step: FieldlessStep


class MinimalSolution(Solution):
    display_name: str = "Minimal Solution"
    steps: Steps
