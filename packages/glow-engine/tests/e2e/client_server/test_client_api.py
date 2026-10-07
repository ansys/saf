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

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import re
from threading import Thread
import time

import httpx2
import pytest

from ansys.saf.glow.client import BadRequestException, Client, NotFoundException
from ansys.saf.glow.solution import MethodState, MethodStatus
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, ProjectFixture
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.transaction_verification_step import (
    CustomTypeABC,
    CustomTypeXYZ,
)

pytestmark = pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)


def wait_for_method(method_name: str, state_retrieval_func: Callable[[str], MethodState], status_to_exit: str):
    tries = 0
    max_tries = 250
    while state_retrieval_func(method_name).status == status_to_exit:
        time.sleep(0.2)
        tries += 1
        if tries > max_tries:
            pytest.fail(
                f"Max number of tries reached while waiting for {method_name} "
                f"to exit status {status_to_exit} using function {state_retrieval_func}.",
            )


@pytest.mark.parametrize(
    "deployment_type",
    ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
    indirect=True,
)
class TestClientAPI:
    def test_client(self, session_glow: GlowBaseProcess[EndToEndSolution], function_client: Client[EndToEndSolution]):
        """
        Test that the Client API can be retrieved given the Solution module and the API address.
        """
        # GIVEN: A running glow process and a GLOW Client
        # THEN: GLOW Client works as expected
        assert function_client.get_schema()["title"] == session_glow.solution_name

    def test_method_state(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test that the Client API can be used to retrieve method states.
        """
        # GIVEN: A GLOW project
        step = function_project.project.steps.transaction_verification_step
        step.create_text_file()

        # WHEN: Getting state of inexistent method
        with pytest.raises(NotFoundException, match="fake_method is not a method on transaction_verification_step"):
            # THEN: Raises exception
            step.get_method_state("fake_method")

        # WHEN: Running regular method in background
        background_thread = Thread(target=step.sleep_dummy)

        # THEN: Its status can be retrieved at any point of its process
        assert step.get_method_state("sleep_dummy").status == MethodStatus.RunRequired
        background_thread.start()
        wait_for_method("sleep_dummy", step.get_method_state, MethodStatus.RunRequired)
        assert step.get_method_state("sleep_dummy").status == MethodStatus.Running
        wait_for_method("sleep_dummy", step.get_method_state, MethodStatus.Running)
        assert step.get_method_state("sleep_dummy").status == MethodStatus.Completed

    def test_set_attr_modify_in_transaction_and_get_attr(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test that the Client can be used to modify and access Step fields.
        """
        # GIVEN: A GLOW project with default field values
        step = function_project.project.steps.transaction_verification_step
        assert step.field_1 == 0
        # WHEN: Modifying the step attr, calling a transaction that modifies it again and then getting the attr
        step.field_1 = 2
        step.set_field_1_to_1()
        # THEN: The field value should be the set by the transaction
        assert step.field_1 == 1

    def test_set_attr_twice(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test that assigning a value using the Client does not hinder its ability to retrieve new values.
        """
        # GIVEN: A GLOW project where a field has been modified via setattr
        step = function_project.project.steps.transaction_verification_step

        assert step.field_1 == 0
        assert step.field_2 == 0
        step.field_1 = 2
        step.copy_field_1_to_field_2()
        assert step.field_2 == 2

        # WHEN: Modifying that same field again, and calling a transaction that copies to another field
        step.field_1 = 3
        step.copy_field_1_to_field_2()

        # THEN: value of field_1 used in the transaction should be the latest one
        assert step.field_2 == 3

    def test_get_fields(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test the method 'get fields' for the StepProxy.
        """
        # GIVEN: A GLOW project with default field values
        step = function_project.project.steps.transaction_verification_step
        # WHEN: calling get_fields with a list of existing field names
        fields = step.get_fields(["field_1", "field_2"])
        # THEN: we get the correct values and only the requested values
        assert fields["field_1"] == step.field_1 == 0
        assert fields["field_2"] == step.field_2 == 0
        assert len(fields) == 2
        # WHEN: changing the field values
        step.set_field_1_to_1()
        step.field_2 = 2
        fields = step.get_fields(["field_1", "field_2"])
        # THEN: we still get the correct values
        assert fields["field_1"] == step.field_1 == 1
        assert fields["field_2"] == step.field_2 == 2
        # WHEN: calling get_fields with a list containing at least one non-existent field name
        error_msg = f"At least one of the provided field names is not a '{step}' step field.\nAvailable fields are: "
        with pytest.raises(AttributeError, match=error_msg):
            # THEN: raises an AttributeError exception
            fields = step.get_fields(["field_1", "field_2", "fake_field"])
        # WHEN: calling get_fields with a list containing a step method
        with pytest.raises(AttributeError, match=error_msg):
            # THEN: raises an AttributeError exception
            fields = step.get_fields(["field_1", "field_2", "copy_field_1_to_field_2"])

    def test_set_fields(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test the method 'get fields' for the StepProxy in a proper use case.
        """
        # GIVEN: A GLOW project
        step = function_project.project.steps.transaction_verification_step

        assert step.field_1 == step.field_2 == 0

        # WHEN: Setting multiple fields at once
        step.set_fields({"field_1": 2, "field_2": 3})

        # THEN: The fields should be set correctly
        assert step.field_1 == 2
        assert step.field_2 == 3

    def test_set_non_existent_fields(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test the method 'get fields' for the StepProxy fails when trying to set a field that does not exist.
        """
        # GIVEN: A GLOW project
        step = function_project.project.steps.transaction_verification_step

        # WHEN: Setting non-existent fields
        with pytest.raises(
            AttributeError,
            match=re.escape(
                f"'{step}' has no field(s) 'wrong_field, another_wrong_field'. "
                f"Available fields are: {', '.join(step._step_model_type.model_fields)}.",  # type: ignore
            ),
        ):
            step.set_fields({"wrong_field": "random_value", "another_wrong_field": "another_random_value"})

    def test_assign_non_existent_fields(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test the failing mode of trying to assign a value to a non-existing field using StepProxy attributes.
        """
        # GIVEN: A GLOW project
        step = function_project.project.steps.transaction_verification_step

        # WHEN: Setting non-existent fields
        with pytest.raises(
            AttributeError,
            match=re.escape(
                f"'{step}' has no field(s) 'wrong_field'. "
                f"Available fields are: {', '.join(step._step_model_type.model_fields)}.",  # type: ignore
            ),
        ):
            step.wrong_field = "random_value"  # pyright: ignore[reportAttributeAccessIssue]

    def test_set_fields_with_wrong_type(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test the method 'get fields' for the StepProxy fails when trying to set a field with a wrong type.
        """
        # GIVEN: A GLOW project
        step = function_project.project.steps.transaction_verification_step

        # WHEN: Setting fields with wrong type
        with pytest.raises(
            BadRequestException,
            match=("Input should be a valid number, unable to parse string as a number"),
        ):
            step.set_fields({"field_1": "wrong_type"})

    def test_set_fields_with_empty_dict(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test the method 'get fields' for the StepProxy doesn't raise an exception when provided with an empty dict.
        """
        # GIVEN: A GLOW project
        step = function_project.project.steps.transaction_verification_step

        # WHEN: Setting fields with an empty dictionary
        step.set_fields({})

        # THEN: No error should be raised

    def test_long_running_method_state(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test that the Client API can be used to retrieve the state of a long_running method.
        """
        # GIVEN: A GLOW project
        step = function_project.project.steps.transaction_verification_step
        step.create_text_file()

        # WHEN: Getting state of an existent regular method
        assert step.get_method_state("sleep_dummy").status == MethodStatus.RunRequired
        with pytest.raises(
            NotFoundException,
            match="sleep_dummy is not a long running method on transaction_verification_step",
        ):
            # THEN: Raises exception
            step.get_long_running_method_state("sleep_dummy")

        # WHEN: Running a longrunning method
        step.long_running_dummy()

        # THEN: Its status can be retrieved at any point of its process
        assert step.get_method_state("long_running_dummy").status == MethodStatus.Running
        assert step.get_long_running_method_state("long_running_dummy").status == MethodStatus.Running
        wait_for_method("long_running_dummy", step.get_long_running_method_state, MethodStatus.Running)
        assert step.get_method_state("long_running_dummy").status == MethodStatus.Completed
        assert step.get_long_running_method_state("long_running_dummy").status == MethodStatus.Completed

    def test_long_running_transaction(self, function_project: ProjectFixture[EndToEndSolution]):
        """
        Test that the Client API can wait for a long_running transaction to finish.
        """
        project = function_project.project

        project.steps.transaction_verification_step.field_1 = 1
        project.steps.transaction_verification_step.field_2 = 2

        assert project.steps.transaction_verification_step.result != 3

        project.steps.transaction_verification_step.lr_get_field_1_and_2_and_set_the_sum_in_result().wait()

        assert project.steps.transaction_verification_step.result == 3

    def test_api_replies_during_sleepy_method(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test that API can reply during a long_running method with time.sleep calls.
        """
        # GIVEN: A GLOW project
        step = function_project.project.steps.transaction_verification_step
        step.create_text_file()

        # WHEN: Getting state of an existent regular method
        assert step.get_method_state("sleep_dummy").status == MethodStatus.RunRequired

        step.sleepy_seconds = 20

        # WHEN: Running regular method in background
        background_thread = Thread(target=step.sleep_dummy)
        background_thread.start()

        # THEN: API replies while sleep method is running
        while step.get_method_state("sleep_dummy").status == MethodStatus.Running:
            try:
                httpx2.get(f"{session_glow.base_api_url}/projects", timeout=2)
            except httpx2.TimeoutException:
                pytest.fail("GLOW API did not reply on time")
            time.sleep(5)

        background_thread.join()


def test_read_entity_handle_uploaded_periodically_from_transaction(function_project: ProjectFixture[EndToEndSolution]):
    """
    Test that a file can be repeatedly uploaded during a long_running transaction.
    """
    sleep_between_upload = 0.02
    sleep_between_reads = 0.01

    # GIVEN: A GLOW project
    step = function_project.project.steps.transaction_verification_step
    step.sleepy_seconds = sleep_between_upload
    scope = function_project.project.storage_scope
    step.text_file = scope.store_stream(b"start")
    # WHEN: Running a long running transaction that uploads an entity handle periodically
    step.upload_file_periodically()
    num_tries = 0
    contents: set[str] = set()
    while step.get_method_state("upload_file_periodically").status == MethodStatus.Running:
        # THEN: We are able to read the file at any time
        content = scope.get_text(step.text_file)
        contents.add(content)
        time.sleep(sleep_between_reads)
        num_tries += 1

    assert len(contents) > 2, "The file was not updated during the long running transaction"


def test_write_entity_handle_from_client_read_from_transaction(function_project: ProjectFixture[EndToEndSolution]):
    """
    Test that a file can be repeatedly read and written without an exception being thrown.
    """
    sleep_between_reads = 0.01

    # GIVEN: A GLOW project
    step = function_project.project.steps.transaction_verification_step
    scope = function_project.project.storage_scope
    step.text_file = scope.store_stream(b"start")

    def execute_50_times(func: Callable[[], None]):
        i = 0
        while i < 50:
            func()
            time.sleep(0.01)
            i += 1

    # WHEN: Running a transaction 50 times that will read the file
    with ThreadPoolExecutor() as executor:
        f = executor.submit(execute_50_times, step.read_text_file_upload_content)  # type: ignore
        # AND: the file is written by the client in the same time
        num_tries = 0
        while num_tries < 100:
            step.text_file = scope.store_stream(str(num_tries).encode())
            time.sleep(sleep_between_reads)
            num_tries += 1
        # THEN: No exception has been thrown
        f.result()
    assert num_tries == 100
    assert len(step.text_content) > 20  # pyright: ignore


def test_no_pydantic_serializer_warnings(
    session_glow: GlowBaseProcess[EndToEndSolution],
    function_project: ProjectFixture[EndToEndSolution],
):
    """
    Test that there are not Pydantic serializer warnings while serializing custom types.
    """
    step = function_project.project.steps.transaction_verification_step
    step.compound_custom_object = CustomTypeABC(a=1, b=CustomTypeXYZ(x=1, y=1, z=1), c=0)
    assert "UserWarning: Pydantic serializer warnings" not in "".join(session_glow.api_output)
