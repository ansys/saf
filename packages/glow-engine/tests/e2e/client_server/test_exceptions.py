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

from collections.abc import Generator
import re

import pytest

from ansys.saf.glow.client import BadRequestException, InternalSolutionException
from ansys.saf.testing.solution.end_to_end import (
    BaseGlowConfiguration,
    DebugConfiguration,
    DefaultDebug,
    EnvVarDebug,
    GlowBaseProcess,
    ProjectFixture,
)
from tests.check_message import MATCH_ANYTHING, check_message
from tests.mocks.solutions.exceptions import ExceptionsSolution

pytestmark = pytest.mark.parametrize("solution_type", [ExceptionsSolution], indirect=True)

INTERNAL_ERROR_MESSAGE = "The solution encountered an internal error and was unable to complete the request. "
BDM_NO_ENTITY_ERROR_MSG = "entity does not exist"


@pytest.fixture(scope="module", autouse=True)
def exit_module(session_glow: GlowBaseProcess[ExceptionsSolution]) -> Generator[None, None, None]:
    yield
    session_glow.configure_default_execution()


@pytest.fixture(scope="class", autouse=True)
def debug_mode(
    session_glow: GlowBaseProcess[ExceptionsSolution],
    request: pytest.FixtureRequest,
) -> BaseGlowConfiguration:
    return session_glow.change_configuration(request.param)


@pytest.mark.parametrize("debug_mode", [EnvVarDebug, DefaultDebug], indirect=True)
class TestExceptions:
    def test_wrong_step_raise_attribute_error(self, function_project: ProjectFixture[ExceptionsSolution]):
        error_message = "'unknown_step' is not a valid step name."
        with pytest.raises(AttributeError, match=error_message):
            _ = function_project.project.steps.unknown_step  # type: ignore

    def test_wrong_field_value_raise_bad_request(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        session_glow: GlowBaseProcess[ExceptionsSolution],
    ):
        error_message = "Input should be a valid integer"
        with pytest.raises(BadRequestException, match=error_message):
            function_project.project.steps.exceptions_step.x = "wrong_value"  # type: ignore
        assert session_glow.text_in_output(error_message, "api")

    def test_extra_field_request_raise_attribute_error(self, function_project: ProjectFixture[ExceptionsSolution]):
        error_message = "'ExceptionsStep' object has no attribute 'wrong_field'"
        with pytest.raises(AttributeError, match=error_message):
            _ = function_project.project.steps.exceptions_step.wrong_field  # type: ignore

    def test_raise_bad_request_exception(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
    ):
        error_message = "State of project invalid"
        with pytest.raises(BadRequestException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.raise_bad_request_error()
        long_running = function_project.project.steps.exceptions_step.raise_bad_request_error_long()
        with pytest.raises(BadRequestException, match=re.escape(error_message)):
            long_running.wait()

    def test_raise_runtime_exception(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
    ):
        error_message = "Runtime Error!" if isinstance(debug_mode, EnvVarDebug) else INTERNAL_ERROR_MESSAGE
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.raise_runtime_error()
        long_running = function_project.project.steps.exceptions_step.raise_runtime_error_long()
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            long_running.wait()

    @pytest.mark.parametrize(
        ("long_method"),
        [False, True],
    )
    def test_method_assigning_the_wrong_type_to_a_field_results_in_a_helpful_exception(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
        long_method: bool,
    ):
        step = function_project.project.steps.exceptions_step
        if long_method:
            result = step.assign_string_to_int_field_long()
            with pytest.raises(InternalSolutionException) as e:
                result.wait()
        else:
            with pytest.raises(InternalSolutionException) as e:
                step.assign_string_to_int_field()

        message = e.value.args[0]
        if isinstance(debug_mode, EnvVarDebug):
            check_message(
                [
                    MATCH_ANYTHING,
                    "1 validation error for ExceptionsStep",
                    "x",
                    "Input should be a valid integer, unable to parse string as an integer "
                    "[type=int_parsing, input_value='foo', input_type=str]",
                ],
                message,
            )
        else:
            assert message == INTERNAL_ERROR_MESSAGE

    def test_raise_wrong_attribute_exception(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
    ):
        error_message = (
            "The solution definition is invalid: invalid attribute 'wrong'"
            if isinstance(debug_mode, EnvVarDebug)
            else INTERNAL_ERROR_MESSAGE
        )
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.raise_wrong_attribute_error()
        long_running = function_project.project.steps.exceptions_step.raise_wrong_attribute_error_long()
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            long_running.wait()

    def test_raise_upload_wrong_field_within_method(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
    ):
        error_message = (
            "The solution definition is invalid: 'y' cannot be uploaded: "
            "it is not marked as 'upload' in the StepSpec of the transaction."
        )
        if isinstance(debug_mode, DefaultDebug):
            error_message = INTERNAL_ERROR_MESSAGE
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.raise_upload_wrong_field_within_method()
        long_running = function_project.project.steps.exceptions_step.raise_upload_wrong_field_within_method_long()
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            long_running.wait()

    def test_raise_import_wrong_module(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
    ):
        error_message = (
            "No module named 'wrong_module'" if isinstance(debug_mode, EnvVarDebug) else INTERNAL_ERROR_MESSAGE
        )
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.raise_import_wrong_module()
        long_running = function_project.project.steps.exceptions_step.raise_import_wrong_module_long()
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            long_running.wait()

    def test_raise_error_unserializable_result(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
    ):
        error_message = (
            "Unable to serialize unknown type: <class 'ansys.saf.glow._core.step_spec.StepSpec'>"
            if isinstance(debug_mode, EnvVarDebug)
            else INTERNAL_ERROR_MESSAGE
        )
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.return_unjsonable()

    def test_raise_error_wrong_result_value(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
    ):
        error_message = "The returned data is invalid"
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.wrong_return_value()

    def test_raise_get_cached_of_no_entity(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
    ):
        error_message = (
            "accessing storage using NO_ENTITY handle"
            if isinstance(debug_mode, EnvVarDebug)
            else INTERNAL_ERROR_MESSAGE
        )
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.raise_get_cached()

    def test_raise_get_copy_of_no_entity(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
    ):
        error_message = (
            "accessing storage using NO_ENTITY handle"
            if isinstance(debug_mode, EnvVarDebug)
            else INTERNAL_ERROR_MESSAGE
        )
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.raise_get_copy()

    def test_raise_get_stream_of_no_entity(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
    ):
        error_message = (
            "accessing storage using NO_ENTITY handle"
            if isinstance(debug_mode, EnvVarDebug)
            else INTERNAL_ERROR_MESSAGE
        )
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.raise_get_stream_result()

    def test_raise_get_parent_of_no_entity(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
    ):
        error_message = BDM_NO_ENTITY_ERROR_MSG if isinstance(debug_mode, EnvVarDebug) else INTERNAL_ERROR_MESSAGE
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.raise_get_parent()

    def test_raise_get_children_with_file_entity(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
    ):
        step = function_project.project.steps.exceptions_step
        storage_scope = function_project.project.storage_scope
        result_txt = storage_scope.get_storage_root() / "result.txt"
        result_txt.write_text("hello world!")
        step.result = storage_scope.store(result_txt)
        error_message = "" if isinstance(debug_mode, EnvVarDebug) else INTERNAL_ERROR_MESSAGE
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.raise_get_children_result()

    def test_raise_get_child_with_file_entity(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
    ):
        step = function_project.project.steps.exceptions_step
        storage_scope = function_project.project.storage_scope
        result_txt = storage_scope.get_storage_root() / "result.txt"
        result_txt.write_text("hello world!")
        step.result = storage_scope.store(result_txt)
        error_message = "" if isinstance(debug_mode, EnvVarDebug) else INTERNAL_ERROR_MESSAGE
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.raise_get_child()

    def test_raise_get_cached_with_removed_entity_file(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
    ):
        step = function_project.project.steps.exceptions_step
        storage_scope = function_project.project.storage_scope
        result_txt = storage_scope.get_storage_root() / "result.txt"
        result_txt.write_text("hello world!")
        step.result = storage_scope.store(result_txt)
        result_txt.unlink()
        error_message = BDM_NO_ENTITY_ERROR_MSG if isinstance(debug_mode, EnvVarDebug) else INTERNAL_ERROR_MESSAGE
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.raise_get_cached()

    def test_raise_get_parent_with_removed_entity_file(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
    ):
        step = function_project.project.steps.exceptions_step
        storage_scope = function_project.project.storage_scope
        result_txt = storage_scope.get_storage_root() / "result.txt"
        result_txt.write_text("hello world!")
        step.result = storage_scope.store(result_txt)
        result_txt.unlink()
        error_message = BDM_NO_ENTITY_ERROR_MSG if isinstance(debug_mode, EnvVarDebug) else INTERNAL_ERROR_MESSAGE
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.raise_get_parent()

    def test_raise_get_stream_with_directory_entity(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
    ):
        step = function_project.project.steps.exceptions_step
        storage_scope = function_project.project.storage_scope
        top = storage_scope.get_storage_root() / "top"
        top.mkdir()
        step.directory = storage_scope.store(top)
        error_message = (
            "cannot create stream for directory" if isinstance(debug_mode, EnvVarDebug) else INTERNAL_ERROR_MESSAGE
        )
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.raise_get_stream_directory()

    def test_raise_get_children_with_removed_entity_directory(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
    ):
        step = function_project.project.steps.exceptions_step
        storage_scope = function_project.project.storage_scope
        top = storage_scope.get_storage_root() / "top"
        top.mkdir()
        step.directory = storage_scope.store(top)
        top.rmdir()
        error_message = BDM_NO_ENTITY_ERROR_MSG if isinstance(debug_mode, EnvVarDebug) else INTERNAL_ERROR_MESSAGE
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.raise_get_children_directory()

    def test_raise_get_children_with_file_entity_long_running(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
    ):
        step = function_project.project.steps.exceptions_step
        storage_scope = function_project.project.storage_scope
        result_txt = storage_scope.get_storage_root() / "result.txt"
        result_txt.write_text("hello world!")
        step.result = storage_scope.store(result_txt)
        error_message = "" if isinstance(debug_mode, EnvVarDebug) else INTERNAL_ERROR_MESSAGE
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.raise_get_children_result_long_running().wait()

    def test_raise_store_in_a_second_scope(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
    ):
        step = function_project.project.steps.exceptions_step
        storage_scope = function_project.project.storage_scope
        result_txt = storage_scope.get_storage_root() / "result.txt"
        result_txt.write_text("hello world!")
        step.result = storage_scope.store(result_txt)
        error_message = (
            "from_ path is not within the storage root.  storage_root="
            if isinstance(debug_mode, EnvVarDebug)
            else INTERNAL_ERROR_MESSAGE
        )
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.raise_store()

    def test_raise_store_a_nonexistent_path_exception(
        self,
        function_project: ProjectFixture[ExceptionsSolution],
        debug_mode: DebugConfiguration,
    ):
        step = function_project.project.steps.exceptions_step
        storage_scope = function_project.project.storage_scope
        result_txt = storage_scope.get_storage_root() / "result.txt"
        result_txt.write_text("hello world!")
        step.result = storage_scope.store(result_txt)
        result_txt.unlink()
        error_message = BDM_NO_ENTITY_ERROR_MSG if isinstance(debug_mode, EnvVarDebug) else INTERNAL_ERROR_MESSAGE
        with pytest.raises(InternalSolutionException, match=re.escape(error_message)):
            function_project.project.steps.exceptions_step.raise_store()
