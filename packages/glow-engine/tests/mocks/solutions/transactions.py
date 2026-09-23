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
import json
import logging
import multiprocessing as mp
import subprocess
import sys
import time
from typing import Annotated, Any, ClassVar

import psutil
from pydantic import BaseModel, Field

from ansys.saf.glow._hps_parametric_studies.base import (
    DynamicHpsParametricStudyProject,
    DynamicHpsSimpleProject,
)
from ansys.saf.glow._hps_parametric_studies.system import HpsParametricStudySystem
from ansys.saf.glow.solution import (
    NO_ENTITY,
    BadRequestError,
    EntityHandle,
    Solution,
    StepModel,
    StepsModel,
    StepSpec,
    long_running,
    transaction,
)
from ansys.saf.glow.solution.hps import HpsParametricStudyProject, HpsSimpleProject

logger = logging.getLogger(__name__)


class MyEnum(Enum):
    a = "a"
    b = "b"


class CustomField(BaseModel):
    x: int
    y: int
    z: int


class CustomFieldWithNestedCustomField(BaseModel):
    x: int
    y: CustomField
    z: dict[str, int]


class LastStep(StepModel):
    last_value: int = 1


class OtherStep(StepModel):
    x: int = 88
    my_string: str | None = "my_string"


class TransactionStep(StepModel):
    """This is a step for testing purpose."""

    x: int = 99
    y: int = 1
    a: int = 0
    b: int = 0
    c: int = 0
    str_field: str = ""
    custom_field: CustomField = CustomField(x=1, y=2, z=3)
    optional_custom_field: CustomFieldWithNestedCustomField | None = None
    union_custom_field: int | str | CustomField | float = 0
    child_process_pid: int = 0
    child_process_is_running: bool = False
    start_method: str = ""
    dict_int_int: dict[int, int] = {}
    my_list_of_tuple: list[tuple[str, str]] = [("a", "b"), ("c", "d")]
    my_tuple: tuple[str, str] = ("a", "b")
    my_enum: MyEnum = MyEnum.a
    inputs_as_json: str = ""
    stored_entity: EntityHandle = NO_ENTITY
    simple_projects: list[HpsSimpleProject] = []
    study_projects: list[HpsParametricStudyProject] = []
    simple_projects_by_name: dict[str, HpsSimpleProject] = {}
    study_projects_by_name: dict[str, HpsParametricStudyProject] = {}
    nested_simple_projects: dict[str, list[HpsSimpleProject]] = {}
    # this is not part of the schema for this step see
    # https://docs.pydantic.dev/usage/models/#automatically-excluded-attributes
    INFORMATION_LOGGED_BY_LOG_METHOD: ClassVar[str] = "information logged by log method"

    @transaction(self=StepSpec(upload=["x"]))
    def increment(self) -> None:
        self.x = 100

    @transaction()
    def log_information(self) -> None:
        logger.warning(self.INFORMATION_LOGGED_BY_LOG_METHOD)

    @transaction()
    @long_running
    def log_long_running_information(self) -> None:
        logger.warning(self.INFORMATION_LOGGED_BY_LOG_METHOD)

    @transaction(self=StepSpec(upload=["x", "y"]))
    def return_x_and_y(self) -> None:
        self.x = 12
        self.y = 1234

    @transaction(self=StepSpec(download=["x"], upload=["y"]))
    def download_x_upload_y(self) -> None:
        self.y = self.x
        self.x = 33  # does nothing since not uploaded

    @transaction(self=StepSpec(download=["x"], upload=["y"]))
    @long_running
    def long_running_download_x_upload_y(self) -> None:
        self.y = self.x
        self.x = 33  # does nothing since not uploaded

    @transaction(self=StepSpec(upload=["x"]), other_step=StepSpec(download=["x"]))
    def increment_from_other_step(self, other_step: OtherStep) -> None:
        self.x = other_step.x + 1

    @transaction(self=StepSpec(download=["y"]))
    def access_field_that_is_not_declared_in_transaction(self) -> None:
        self.x = self.x + 1

    @transaction(self=StepSpec(upload=["str_field"]))
    def assign_int_to_string_field(self) -> None:
        self.str_field = 99  # type: ignore

    @transaction(self=StepSpec(upload=["stored_entity"]))
    def assign_custom_model_to_entity_handle(self) -> None:
        self.stored_entity = CustomField(x=1, y=2, z=3)  # type: ignore

    @transaction(self=StepSpec(upload=["x", "str_field", "stored_entity"]))
    def assign_multiple_fields_wrong_types(self) -> None:
        self.x = "foo"  # type: ignore
        self.str_field = 99  # type: ignore
        self.stored_entity = CustomField(x=1, y=2, z=3)  # type: ignore

    @transaction(self=StepSpec(upload=["x"]))
    def assign_string_to_int_field(self) -> None:
        self.x = "foo"  # type: ignore

    @long_running  # type: ignore
    @transaction(self=StepSpec(upload=["y"]))
    def long_running_before_transaction(self) -> None:
        self.y = 23

    def internal_method(self):
        self.y = self.x

    @transaction(self=StepSpec(download=["x"], upload=["y"]))
    def call_internal_method(self):
        self.internal_method()

    def internal_method_wrong_field(self):
        # access wrong field must throw exception
        _ = self.x

    @transaction(self=StepSpec(download=["y"]))
    def call_internal_method_wrong_field(self):
        self.internal_method_wrong_field()

    @transaction(
        self=StepSpec(upload=["x"]),
        last_step=StepSpec(download=["last_value"]),
        other_step=StepSpec(download=["x"]),
    )
    def method_parameter_wrong_order(self, other_step: OtherStep, last_step: LastStep):
        self.x = other_step.x + last_step.last_value

    @transaction(self=StepSpec(upload=["x"]))
    @long_running
    def upload_x_within_method(self):
        self.x = 0
        logger.debug("Uploading x within method")
        self.transaction.upload(["x"])  # type: ignore
        logger.debug("Uploaded x within method")
        self.x = 1
        raise Exception("Just to avoid uploading files automatically at the end.")

    @transaction(self=StepSpec(upload=["x"]))
    @long_running
    def upload_wrong_field_within_method(self):
        self.transaction.upload("y")  # type: ignore

    def add_one(self, value: int):
        return value + 1

    @transaction(self=StepSpec(upload=["a"]))
    def first(self) -> None:
        self.a = self.add_one(0)

    @transaction(self=StepSpec(download=["a"], upload=["b"]))
    def second(self):
        self.b = self.add_one(self.a)

    @transaction(self=StepSpec(download=["b"], upload=["c"]))
    def third(self):
        self.c = self.add_one(self.b)

    @transaction(self=StepSpec())
    @long_running
    def one_second_async(self):
        time.sleep(1)

    @transaction(self=StepSpec())
    def one_second_sync(self):
        time.sleep(1)

    @transaction(self=StepSpec())
    def raise_bad_request_error(self):
        raise BadRequestError("State of project invalid")

    @transaction(self=StepSpec())
    def raise_exception(self):
        raise Exception("Oops, something went wrong")

    @transaction(self=StepSpec())
    @long_running
    def raise_exception_lr(self):
        raise Exception("Oops, something went wrong")

    @transaction(self=StepSpec())
    @long_running
    def raise_bad_request_error_lr(self):
        raise BadRequestError("State of project invalid")

    @transaction(self=StepSpec(upload=["custom_field"]))
    def upload_custom_field(self) -> None:
        self.custom_field = CustomField(x=4, y=5, z=6)

    @transaction(self=StepSpec(upload=["child_process_pid"]))
    def start_process(self) -> None:
        self.child_process_pid = self._start_process()

    @transaction(self=StepSpec(upload=["child_process_pid"]))
    @long_running
    def start_process_in_long_running_method(self) -> None:
        self.child_process_pid = self._start_process()

    def _start_process(self) -> int:
        child_process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        return child_process.pid

    @transaction(self=StepSpec(download=["child_process_pid"], upload=["child_process_is_running"]))
    def check_child_process_is_running(self) -> None:
        self.child_process_is_running = psutil.pid_exists(self.child_process_pid)

    @transaction(self=StepSpec(upload=["optional_custom_field"]))
    def upload_optional_custom_field(self) -> None:
        nested = CustomField(x=7, y=8, z=9)
        self.optional_custom_field = CustomFieldWithNestedCustomField(x=7, y=nested, z={"a": 1})

    @transaction(self=StepSpec(upload=["union_custom_field"]))
    def set_union_custom_field_to_custom_field(self) -> None:
        self.union_custom_field = CustomField(x=10, y=11, z=12)

    @transaction(self=StepSpec())
    def raise_runtime_error(self) -> None:
        raise RuntimeError("Runtime Error!")

    @transaction(self=StepSpec())
    def raise_wrong_attribute_error(self) -> None:
        _ = self.wrong  # type: ignore

    @transaction(self=StepSpec())
    @long_running
    def raise_bad_request_error_long(self):
        raise BadRequestError("State of project invalid")

    @transaction(self=StepSpec())
    @long_running
    def raise_runtime_error_long(self):
        raise RuntimeError("Runtime Error!")

    @transaction(self=StepSpec())
    @long_running
    def raise_wrong_attribute_error_long(self) -> None:
        _ = self.wrong  # type: ignore

    @transaction(self=StepSpec(upload=["start_method"]))
    @long_running
    def get_process_start_method(self) -> None:
        self.start_method = mp.get_start_method()

    @transaction(self=StepSpec(upload=["dict_int_int", "my_tuple", "my_enum", "my_list_of_tuple"]))
    def upload_fields_not_working_with_strict(self) -> None:
        self.my_tuple = ("c", "d")
        self.my_list_of_tuple = [("e", "f")]
        self.my_enum = MyEnum.b
        self.dict_int_int = {0: 0}

    @transaction(self=StepSpec())
    def raise_event(self) -> None:
        self.transaction.raise_event({"message": "hello1"})

    @transaction(self=StepSpec())
    def raise_event_custom_stream_name(self) -> None:
        self.transaction.raise_event({"message": "hello2"}, "my-stream")

    @transaction(self=StepSpec())
    def raise_event_invalid_custom_stream_name(self) -> None:
        self.transaction.raise_event({"message": "hello3"}, "my_stream")

    @transaction(self=StepSpec())
    def raise_event_invalid_message(self) -> None:
        self.transaction.raise_event(message=None, stream="test-stream")  # type: ignore

    @transaction(self=StepSpec())
    def raise_event_long_running(self) -> None:
        self.transaction.raise_event({"message": "hello4"})

    @transaction(self=StepSpec(upload=["inputs_as_json"]))
    def input_str_or_none(self, my_input: str | None = None) -> None:
        self.inputs_as_json = str(my_input)

    @transaction(self=StepSpec(upload=["inputs_as_json"]))
    def input_str_with_field(self, my_input: Annotated[str, Field(max_length=5)]) -> None:
        self.inputs_as_json = str(my_input)

    @transaction(self=StepSpec(upload=["inputs_as_json"]))
    def input_str_with_default(self, my_input: str = "default_value") -> None:
        self.inputs_as_json = str(my_input)

    @transaction(self=StepSpec(upload=["inputs_as_json"]), other_step=StepSpec(download=["x"]))
    def input_int_with_other_step(self, my_input: int, other_step: OtherStep) -> None:
        self.inputs_as_json = json.dumps(other_step.x + my_input)

    @transaction(self=StepSpec(upload=["inputs_as_json"]))
    def input_dict(self, my_input: dict[str, Any]) -> None:
        self.inputs_as_json = json.dumps(my_input)

    @transaction(self=StepSpec(upload=["inputs_as_json"]))
    def input_custom_model(self, my_input: CustomField) -> None:
        self.inputs_as_json = my_input.model_dump_json()

    @transaction(self=StepSpec(upload=["inputs_as_json"]))
    def multiple_inputs(self, int_input: int, str_input: str) -> None:
        inputs = {"int_input": int_input, "str_input": str_input}
        self.inputs_as_json = json.dumps(inputs)

    @transaction(self=StepSpec(upload=["inputs_as_json"]))
    def multiple_custom_inputs(self, custom_1: CustomField, custom_2: CustomField) -> None:
        inputs = {"custom_1": custom_1.model_dump(), "custom_2": custom_2.model_dump()}
        self.inputs_as_json = json.dumps(inputs)

    @transaction(self=StepSpec(upload=["inputs_as_json"]))
    @long_running
    def input_str_long_running(self, my_input: str | None = None) -> None:
        self.inputs_as_json = str(my_input)

    @transaction(self=StepSpec())
    def return_int(self) -> int:
        return 10

    @transaction(self=StepSpec())
    def return_dict(self) -> dict[str, Any]:
        return {"hello": "world"}

    @transaction(self=StepSpec())
    def return_custom_model(self) -> CustomField:
        return CustomField(x=1, y=2, z=3)

    @transaction(self=StepSpec())
    @long_running
    def return_long_running_int(self) -> int:
        return 10

    @transaction(self=StepSpec())
    @long_running
    def return_long_running_custom_model(self) -> CustomField:
        return CustomField(x=1, y=2, z=3)

    @transaction(self=StepSpec())
    def return_input_str(self, my_input: str | None = None) -> str | None:
        return my_input

    @transaction(self=StepSpec())
    @long_running
    def return_input_str_long_running(self, my_input: str) -> str:
        return my_input

    @transaction(self=StepSpec(upload=["custom_field"]))
    def store_custom_field_from_input(self, custom_field: CustomField) -> None:
        self.custom_field = custom_field

    @transaction(self=StepSpec())
    def create_hps_client(self) -> str:
        with HpsParametricStudySystem.get_hps_client():
            return "ok"

    @transaction(self=StepSpec())
    def create_hps_client_with_custom_hps_url(self) -> str:
        with HpsParametricStudySystem.get_hps_client(hps_server_url="https://custom_url:1234/hps"):
            return "ok"

    @transaction(self=StepSpec())
    def create_hps_client_with_custom_params(self) -> str:
        with HpsParametricStudySystem.get_hps_client(
            hps_server_url="https://custom_host:1234/hps",
            client_id="custom_client",
        ):
            return "ok"

    @transaction(
        self=StepSpec(
            upload=[
                "simple_projects",
                "study_projects",
                "simple_projects_by_name",
                "study_projects_by_name",
                "nested_simple_projects",
            ],
        ),
    )
    def append_hps_project_collections(self) -> None:
        self.simple_projects.append(HpsSimpleProject.start_hps_job({}, {}))
        self.simple_projects.append(HpsSimpleProject.start_hps_job({}, {}))
        self.study_projects.append(HpsParametricStudyProject.start_hps_parametric_study({}, {}, {}))
        self.study_projects.append(HpsParametricStudyProject.start_hps_parametric_study({}, {}, {}))
        self.simple_projects_by_name["first"] = HpsSimpleProject.start_hps_job({}, {})
        self.simple_projects_by_name["second"] = HpsSimpleProject.start_hps_job({}, {})
        self.study_projects_by_name["first"] = HpsParametricStudyProject.start_hps_parametric_study({}, {}, {})
        self.study_projects_by_name["second"] = HpsParametricStudyProject.start_hps_parametric_study({}, {}, {})
        self.nested_simple_projects["group_1"] = [
            self.simple_projects[0],
            self.simple_projects[1],
        ]

    @transaction(
        self=StepSpec(
            download=[
                "simple_projects",
                "study_projects",
                "simple_projects_by_name",
                "study_projects_by_name",
                "nested_simple_projects",
            ],
        ),
    )
    def inspect_hps_project_collections(self) -> dict[str, Any]:
        nested_simple_projects = [project for projects in self.nested_simple_projects.values() for project in projects]
        simple_projects = [*self.simple_projects, *self.simple_projects_by_name.values(), *nested_simple_projects]
        study_projects = [*self.study_projects, *self.study_projects_by_name.values()]
        all_projects = [*simple_projects, *study_projects]
        return {
            "all_simple_projects_are_dynamic": all(
                isinstance(project, DynamicHpsSimpleProject) for project in simple_projects
            ),
            "all_study_projects_are_dynamic": all(
                isinstance(project, DynamicHpsParametricStudyProject) for project in study_projects
            ),
            "identifiers": [project.hps_project_identifier for project in all_projects],
            "dictionary_keys": [*self.simple_projects_by_name, *self.study_projects_by_name],
            "nested_dictionary_keys": list(self.nested_simple_projects),
            "ui_urls": [project.ui_url for project in all_projects],
            "finished": [project.finished for project in all_projects],
            "exists": [project.exists for project in all_projects],
            "status_counts": [len(project.get_status_of_design_points()) for project in study_projects],
            "parameter_values": [project.fetch_values_of_parameters(["result"]) for project in study_projects],
        }

    @transaction(self=StepSpec(upload=["simple_projects"]))
    def append_raw_hps_project_to_collection(self) -> None:
        self.simple_projects.append(HpsSimpleProject(hps_project_identifier="raw-project"))

    @long_running
    @transaction(self=StepSpec(upload=["stored_entity"]))
    def store_entity_handle_lr(self) -> None:
        file_path = self.storage_scope.get_storage_root() / "test_entity.txt"
        file_path.write_text("entity handle content")
        self.stored_entity = self.storage_scope.store(file_path)

    @transaction(self=StepSpec(upload=["stored_entity"]))
    def store_entity_handle(self) -> None:
        file_path = self.storage_scope.get_storage_root() / "test_entity.txt"
        file_path.write_text("entity handle content")
        self.stored_entity = self.storage_scope.store(file_path)


class Steps(StepsModel):
    transaction_step: TransactionStep
    other_step: OtherStep
    last_step: LastStep


class TransactionsSolution(Solution):
    """This is a solution for testing purpose."""

    display_name: str = "Transactions"
    steps: Steps
