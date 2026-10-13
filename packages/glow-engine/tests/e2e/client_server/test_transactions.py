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

import asyncio
from collections.abc import Generator
import os
from pathlib import Path
import re
import time
from typing import Any
import zipfile

import httpx2
from pydantic import BaseModel, ValidationError
import pytest

from ansys.saf.glow.client import (
    BadRequestException,
    InternalSolutionException,
)
from ansys.saf.glow.solution import MethodStatus
from ansys.saf.testing.solution.end_to_end import (
    BaseGlowConfiguration,
    CustomMethodExecutionDirectory,
    EnvVarDebug,
    GlowBaseProcess,
    GlowDesktopProcess,
    ProjectFixture,
)
from tests.mocks.solutions.transactions import (
    CustomField,
    CustomFieldWithNestedCustomField,
    MyEnum,
    TransactionsSolution,
)

pytestmark = pytest.mark.parametrize("solution_type", [TransactionsSolution], indirect=True)

INTERNAL_ERROR_MESSAGE = "The solution encountered an internal error and was unable to complete the request. "


@pytest.fixture
def project_file(function_project: ProjectFixture[TransactionsSolution]) -> Generator[Path, None, None]:
    project_file = function_project.project_files_dir / "dir" / "file.txt"
    project_file.parent.mkdir(exist_ok=True, parents=True)
    project_file.write_text("hello world!")
    yield project_file
    project_file.unlink(missing_ok=True)


@pytest.fixture
def custom_method_execution_dir(
    session_glow: GlowDesktopProcess[TransactionsSolution],
    tmp_path: Path,
) -> Generator[Path, None, None]:
    custom_dir = tmp_path / "transactions"
    custom_dir.mkdir()
    session_glow.change_configuration(CustomMethodExecutionDirectory, tmp_path=custom_dir)
    yield custom_dir
    session_glow.configure_default_execution()


def test_method_transaction_increment_get_and_set_step_field(
    function_project: ProjectFixture[TransactionsSolution],
):
    """Test that a transaction can get and set a step field."""
    step = function_project.project.steps.transaction_step
    assert step.x == 99
    step.increment()
    assert step.x == 100


@pytest.mark.usefixtures("project_file")
def test_method_transaction_return_multiple_fields(function_project: ProjectFixture[TransactionsSolution]):
    """Test that a transaction can get and set a step field."""
    step = function_project.project.steps.transaction_step
    assert step.x == 99
    step.return_x_and_y()
    assert step.x == 12
    assert step.y == 1234


def test_method_transaction_with_optional_custom_field(function_project: ProjectFixture[TransactionsSolution]):
    """Test that a transaction can retrieve the type of a custom field if the field is optional."""
    step = function_project.project.steps.transaction_step

    # Check the field is None
    assert not step.optional_custom_field

    # Call the method to assign a CustomField to the field
    step.upload_optional_custom_field()

    assert step.optional_custom_field
    assert isinstance(step.optional_custom_field, CustomFieldWithNestedCustomField)
    assert isinstance(step.optional_custom_field.y, CustomField)
    assert isinstance(step.optional_custom_field.z, dict)


def test_method_transaction_with_union_custom_field(function_project: ProjectFixture[TransactionsSolution]):
    """Test that a transaction can retrieve the type of a custom field if the field is Union[...]."""
    step = function_project.project.steps.transaction_step

    # Check the initial field is not CustomField
    assert step.union_custom_field == 0

    # Call the method to assign CustomField
    step.set_union_custom_field_to_custom_field()

    assert isinstance(step.union_custom_field, CustomField)


def test_method_transaction_download_x_upload_y(function_project: ProjectFixture[TransactionsSolution]):
    """Test that a transaction can selectively download a field and upload another."""
    step = function_project.project.steps.transaction_step
    assert step.x == 99
    assert step.y == 1
    step.download_x_upload_y()
    assert step.x == 99
    assert step.y == 99


def test_method_transaction_download_updated_x_upload_y(function_project: ProjectFixture[TransactionsSolution]):
    """Test that a transaction can selectively download an updated field and upload another."""
    step = function_project.project.steps.transaction_step
    assert step.x == 99
    assert step.y == 1
    step.x = 56
    step.download_x_upload_y()
    assert step.x == 56
    assert step.y == 56


def test_method_transaction_increment_from_other_step_field(function_project: ProjectFixture[TransactionsSolution]):
    """Test that a transaction can get another step field and use its value."""
    step = function_project.project.steps.transaction_step
    other_step = function_project.project.steps.other_step
    assert other_step.x == 88
    step.increment_from_other_step()
    assert step.x == 89


def test_method_accessing_field_not_defined_in_the_transaction_results_in_an_exception(
    session_glow: GlowBaseProcess[TransactionsSolution],
    function_project: ProjectFixture[TransactionsSolution],
):
    """Test that one cannot access a field that is not defined in the transaction."""
    if session_glow.debug_mode_override:
        pytest.xfail("failing in debug, see #2342")
    step = function_project.project.steps.transaction_step
    with pytest.raises(InternalSolutionException, match=INTERNAL_ERROR_MESSAGE):
        step.access_field_that_is_not_declared_in_transaction()


def test_method_raising_bad_request_exception_triggers_bad_request_on_client(
    function_project: ProjectFixture[TransactionsSolution],
):
    with pytest.raises(BadRequestException, match="State of project invalid"):
        function_project.project.steps.transaction_step.raise_bad_request_error()


def test_method_transaction_call_internal_method_modify_field(
    function_project: ProjectFixture[TransactionsSolution],
):
    """Test that a transaction can call internal method not marked as transaction."""
    step = function_project.project.steps.transaction_step
    assert step.x == 99
    assert step.y == 1
    step.call_internal_method()
    assert step.x == step.y


def test_method_transaction_call_internal_method_wrong_field_throw_exception(
    function_project: ProjectFixture[TransactionsSolution],
):
    """Test that a transaction calling an internal method cannot access fields outside
    of the enclosing transaction."""
    step = function_project.project.steps.transaction_step
    with pytest.raises(InternalSolutionException, match=INTERNAL_ERROR_MESSAGE):
        step.call_internal_method_wrong_field()


def test_method_transaction_wrong_parameter_order_works(
    function_project: ProjectFixture[TransactionsSolution],
):
    """Test that a transaction method with parameters in the wrong order works."""
    step = function_project.project.steps.transaction_step
    assert step.x == 99
    step.method_parameter_wrong_order()
    assert step.x == 89


def test_method_transaction_upload_within_method(
    function_project: ProjectFixture[TransactionsSolution],
    session_glow: GlowBaseProcess[TransactionsSolution],
):
    """Test that a transaction method can upload field within method."""

    step = function_project.project.steps.transaction_step
    assert step.x == 99
    step.upload_x_within_method()
    while step.get_long_running_method_state("upload_x_within_method").status != MethodStatus.Failed:
        time.sleep(0.1)
    assert step.x == 0


def test_method_transaction_upload_wrong_field_within_method(
    function_project: ProjectFixture[TransactionsSolution],
):
    """Test that a transaction method cannot upload a field within method that is not an upload stepspec."""
    step = function_project.project.steps.transaction_step
    step.upload_wrong_field_within_method()
    state = step.get_long_running_method_state("upload_wrong_field_within_method")
    while state.status != MethodStatus.Failed:
        state = step.get_long_running_method_state("upload_wrong_field_within_method")
        time.sleep(0.1)
    assert INTERNAL_ERROR_MESSAGE in state.exception_message  # type: ignore


def test_export_project_with_running_method_raise_400(
    function_project: ProjectFixture[TransactionsSolution],
    tmp_path: Path,
):
    function_project.project.steps.transaction_step.one_second_async()
    with pytest.raises(
        BadRequestException,
        match="Unable to perform this action because the following methods are still running: "
        r"'\['one_second_async'\]'",
    ):
        function_project.project.export(tmp_path)
    assert not (tmp_path / f"{function_project.project.project_display_name}.safx").exists()


async def test_long_running_method_during_export(
    function_project: ProjectFixture[TransactionsSolution],
    tmp_path: Path,
):
    """
    Test that a project export is asynchronous by invoking a regular and a long_running method
    while the project is being exported. Additionally, check that the streaming starts immediately.
    """

    async def async_call_export() -> bytes:
        url = f"{function_project.project.url}:export"
        timeout = httpx2.Timeout(5, read=None, pool=None)
        async with httpx2.AsyncClient(timeout=timeout) as async_client:
            start_time = asyncio.get_event_loop().time()
            async with async_client.stream("GET", url) as response:
                assert response.status_code == 200
                is_first_chunk = True
                content = b""
                async for chunk in response.aiter_bytes():
                    if is_first_chunk:
                        is_first_chunk = False
                        # Check that the streaming starts immediately
                        assert asyncio.get_event_loop().time() - start_time < 1
                    content += chunk
        return content

    # Generate 5 files of 10 MB each reaching 50 MB to slow down export
    subdir = function_project.project_files_dir / "subdir"
    subdir.mkdir(exist_ok=True, parents=True)
    for i in range(5):
        (subdir / f"random_file_{str(i).zfill(4)}.txt").write_bytes(os.urandom(10485760))

    # Start export in an async task
    safx_path = tmp_path / f"{function_project.project.project_display_name}.safx"
    task = asyncio.create_task(async_call_export())

    # Give some CPU time to the export task so that it can start
    await asyncio.sleep(1)

    # Run a regular and a long_running transactions while the export is running
    function_project.project.steps.transaction_step.one_second_async().wait()
    function_project.project.steps.transaction_step.increment()

    # Wait for the export task to complete and check he downloaded content
    assert not task.done()
    content = await task
    safx_path.write_bytes(content)
    with zipfile.ZipFile(safx_path, mode="r", compression=zipfile.ZIP_DEFLATED) as archive:
        # 5 random files + .sap file
        assert len(archive.namelist()) == 6


async def test_already_running_exception_not_thrown_for_sync_methods(
    function_project: ProjectFixture[TransactionsSolution],
):
    async def launch_transaction(async_client: httpx2.AsyncClient, url: str) -> httpx2.Response:
        response = await async_client.post(url=url, timeout=10)
        return response

    async with httpx2.AsyncClient() as client:
        url = f"{function_project.url}/steps/transaction-step:one-second-sync"
        responses = await asyncio.gather(*[launch_transaction(client, url) for _ in range(2)])
        assert all(response.status_code == 200 for response in responses)


def test_long_running_method_starts_with_spawn(
    function_project: ProjectFixture[TransactionsSolution],
):
    """Test that a long running transaction method is started within 'spawn' context."""
    step = function_project.project.steps.transaction_step

    step.get_process_start_method().wait()
    assert step.start_method == "spawn"


def test_long_running_before_transaction(
    function_project: ProjectFixture[TransactionsSolution],
):
    step = function_project.project.steps.transaction_step
    assert step.y == 1
    long_running = step.long_running_before_transaction()
    long_running.wait()
    assert step.y == 23


def test_upload_fields_not_working_with_strict(
    function_project: ProjectFixture[TransactionsSolution],
):
    """Test that step fields not working with strict mode are properly working."""
    step = function_project.project.steps.transaction_step
    assert step.dict_int_int == {}
    assert step.my_list_of_tuple == [("a", "b"), ("c", "d")]
    assert step.my_enum == MyEnum.a
    assert step.my_tuple == ("a", "b")
    step.upload_fields_not_working_with_strict()
    assert step.dict_int_int == {0: 0}
    assert step.my_list_of_tuple == [("e", "f")]
    assert step.my_enum == MyEnum.b
    assert step.my_tuple == ("c", "d")


def test_set_attr_modify_in_transaction_and_get_attr(function_project: ProjectFixture[TransactionsSolution]):
    step = function_project.project.steps.transaction_step
    step.x = 0
    step.increment()
    assert step.x == 100


@pytest.mark.parametrize(
    ("method_name", "inputs", "expected_result"),
    [
        ("input_str_or_none", {"my_input": "hello"}, "hello"),
        ("input_str_with_field", {"my_input": "hello"}, "hello"),
        ("input_str_or_none", None, "None"),
        ("input_dict", {"my_input": {"a": "b", "c": {"d": "e"}}}, '{"a": "b", "c": {"d": "e"}}'),
        ("multiple_inputs", {"int_input": 1, "str_input": "string"}, '{"int_input": 1, "str_input": "string"}'),
        ("input_custom_model", {"my_input": {"x": 1, "y": 2, "z": 3}}, '{"x":1,"y":2,"z":3}'),
        ("input_custom_model", {"my_input": CustomField(x=1, y=2, z=3)}, '{"x":1,"y":2,"z":3}'),
        (
            "multiple_custom_inputs",
            {"custom_1": CustomField(x=1, y=2, z=3), "custom_2": CustomField(x=4, y=5, z=6)},
            '{"custom_1": {"x": 1, "y": 2, "z": 3}, "custom_2": {"x": 4, "y": 5, "z": 6}}',
        ),
    ],
)
def test_transaction_inputs(
    function_project: ProjectFixture[TransactionsSolution],
    method_name: str,
    inputs: dict[str, Any] | None,
    expected_result: Any,
):
    step = function_project.project.steps.transaction_step
    assert step.inputs_as_json == ""
    method = getattr(step, method_name)
    method() if inputs is None else method(**inputs)
    assert step.inputs_as_json == expected_result


def test_transaction_simple_input_wrong_type(
    function_project: ProjectFixture[TransactionsSolution],
):
    step = function_project.project.steps.transaction_step
    with pytest.raises(ValidationError, match="Input should be a valid string"):
        step.input_str_or_none(my_input=1)


def test_transaction_dict_input_none_raise_error(
    function_project: ProjectFixture[TransactionsSolution],
):
    step = function_project.project.steps.transaction_step
    with pytest.raises(ValidationError, match=re.escape("Field required")):
        step.input_dict()


def test_transaction_wrong_input_raise_error(
    function_project: ProjectFixture[TransactionsSolution],
):
    step = function_project.project.steps.transaction_step
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        step.input_dict(wrong_input="value")


def test_transaction_extra_wrong_input_raise_error(
    function_project: ProjectFixture[TransactionsSolution],
):
    step = function_project.project.steps.transaction_step
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        step.input_dict(my_input={"hello": "world"}, wrong_extra=1)


def test_transaction_field_input_with_field_wrong_max_length(
    function_project: ProjectFixture[TransactionsSolution],
):
    step = function_project.project.steps.transaction_step
    with pytest.raises(ValidationError, match="String should have at most 5 characters"):
        step.input_str_with_field(my_input="too_long_length")


def test_transaction_input_long_running(function_project: ProjectFixture[TransactionsSolution]):
    step = function_project.project.steps.transaction_step
    assert step.inputs_as_json == ""
    step.input_str_long_running(my_input="hello").wait()
    assert step.inputs_as_json == "hello"


def test_transaction_input_with_other_step(function_project: ProjectFixture[TransactionsSolution]):
    step = function_project.project.steps.transaction_step
    other_step = function_project.project.steps.other_step
    assert other_step.x == 88
    step.input_int_with_other_step(my_input=10)
    assert step.inputs_as_json == "98"


@pytest.mark.parametrize(
    ("method_name", "expected_result"),
    [
        ("return_int", 10),
        ("return_dict", {"hello": "world"}),
        ("return_custom_model", CustomField(x=1, y=2, z=3)),
    ],
)
def test_transaction_return(
    function_project: ProjectFixture[TransactionsSolution],
    method_name: str,
    expected_result: Any,
):
    step = function_project.project.steps.transaction_step
    method = getattr(step, method_name)
    result = method()
    assert result == expected_result


def test_transaction_return_long_running(function_project: ProjectFixture[TransactionsSolution]):
    step = function_project.project.steps.transaction_step
    result = step.return_long_running_int().wait()
    assert result == 10


def test_transaction_return_input(function_project: ProjectFixture[TransactionsSolution]):
    step = function_project.project.steps.transaction_step
    value = "hello"
    result = step.return_input_str(my_input=value)
    assert result == value


def test_transaction_return_input_long_running(function_project: ProjectFixture[TransactionsSolution]):
    step = function_project.project.steps.transaction_step
    value = "hello"
    result = step.return_input_str_long_running(my_input=value).wait()
    assert result == value


def test_method_positional_argument_raise_error(function_project: ProjectFixture[TransactionsSolution]):
    step = function_project.project.steps.transaction_step
    with pytest.raises(SyntaxError, match="Positional arguments are not supported. Use keyword arguments instead."):
        step.return_input_str("hello")


def test_transaction_return_value_is_casted_type(function_project: ProjectFixture[TransactionsSolution]):
    step = function_project.project.steps.transaction_step
    # When: calling a transaction method returning a custom type
    result = step.return_custom_model()
    # Then: the custom type can directly be used.
    assert result.x == 1


def test_transaction_long_running_return_value_is_casted_type(function_project: ProjectFixture[TransactionsSolution]):
    step = function_project.project.steps.transaction_step
    # When: calling a transaction method returning a custom type
    result = step.return_long_running_custom_model().wait()
    # Then: the custom type can directly be used.
    assert result.x == 1


def test_transaction_store_custom_field_from_input(function_project: ProjectFixture[TransactionsSolution]):
    step = function_project.project.steps.transaction_step
    # When: calling a transaction method with a custom field as input
    custom_field = CustomField(x=1, y=2, z=3)
    step.store_custom_field_from_input(custom_field=custom_field)
    # Then: the custom type has been properly saved to step field
    assert step.custom_field == custom_field


def test_transaction_wrong_pydantic_object(function_project: ProjectFixture[TransactionsSolution]):
    class NotCustomField(BaseModel):
        a: int

    step = function_project.project.steps.transaction_step
    # When: calling a transaction method with a custom field as input
    custom_field = NotCustomField(a=1)
    with pytest.raises(ValidationError, match="Input should be a valid dictionary or instance of CustomField"):
        # Then: an exception is raised
        step.store_custom_field_from_input(custom_field=custom_field)


@pytest.fixture(scope="class")
def debug_mode(session_glow: GlowBaseProcess[TransactionsSolution]) -> Generator[BaseGlowConfiguration, None, None]:
    debug_config = session_glow.change_configuration(EnvVarDebug)
    yield debug_config
    session_glow.configure_default_execution()


@pytest.mark.usefixtures("debug_mode")
@pytest.mark.parametrize("long_running", [False, True])
class TestTransactionsWithDebug:
    def test_transaction_is_registered_in_running_methods(
        self,
        long_running: bool,
        session_glow: GlowBaseProcess[TransactionsSolution],
        function_project: ProjectFixture[TransactionsSolution],
    ):
        step = function_project.project.steps.transaction_step
        if long_running:
            step.long_running_download_x_upload_y().wait()
            expected_method_name = "long_running_download_x_upload_y"
        else:
            step.download_x_upload_y()
            expected_method_name = "download_x_upload_y"
        assert session_glow.text_in_output(
            ["DEBUG", f"Running method transaction_step.{expected_method_name} added."],
            "api",
        )
        assert session_glow.text_in_output(
            ["DEBUG", f"Running method transaction_step.{expected_method_name} removed."],
            "api",
        )

    def test_transaction_can_be_relaunched_after_being_failed(
        self,
        long_running: bool,
        function_project: ProjectFixture[TransactionsSolution],
    ):
        """Test that a transaction can be launched again after its status is set to Failed."""
        step = function_project.project.steps.transaction_step
        num_launches = 0
        for _ in range(2):
            with pytest.raises(InternalSolutionException, match="Runtime Error!"):  # noqa: PT012
                if long_running:
                    step.raise_runtime_error_long().wait()
                else:
                    step.raise_runtime_error()
            method_state = step.get_method_state("raise_runtime_error_long" if long_running else "raise_runtime_error")
            assert method_state.status == "failed"
            assert method_state.exception_message == "Runtime Error!"
            num_launches += 1
        assert num_launches > 1
