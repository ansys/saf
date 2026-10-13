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

from typing import TypeVar

import httpx2
import pytest

from ansys.saf.glow._core.instance.manager import JOB_DEFAULT_MAX_RUNNING_TIME  # type: ignore
from ansys.saf.glow.client import InternalSolutionException
from ansys.saf.glow.solution import Solution
from ansys.saf.testing.platform_specific import CONNECTION_ERROR
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, ProjectFixture
from tests.mocks.solution_end_to_end.solution.custom_http_instance_step import (
    INSTANCE_MAX_EXECUTION_TIME,
)
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

pytestmark = [pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True), pytest.mark.use_instances]

T = TypeVar("T", bound=Solution)
STEP_NAME = "custom-http-shared-instance-step"


@pytest.mark.parametrize("instance_system_type", [pytest.param("HPS", marks=pytest.mark.use_hps)], indirect=True)
@pytest.mark.parametrize(
    "deployment_type",
    ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
    indirect=True,
)
class TestHpsMaxExecutionTime:
    def test_instance_max_execution_time_before_timeout(
        self,
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test the max_execution_time parameter of the create_instance decorator using HPS.
        Instance shall not be healthy after timeout.
        """
        instance_name = "custom_http_product_instance"
        project_id = function_project.project_id
        step = function_project.project.steps.custom_http_shared_instance_step

        # GIVEN instance cannot be found since it hasn't been initialized and step field has default value
        with pytest.raises(httpx2.HTTPError, match="Client error '404 Not Found'"):
            function_project.get_instance(STEP_NAME, instance_name)
        assert step.value == "white"

        # WHEN Initializing custom product instance with max_execution_time
        step.initialize_max_exec_time_custom_http_product_instance()

        custom_product_instance = function_project.get_instance(STEP_NAME, instance_name)
        assert (
            custom_product_instance["name"]
            == f"projects/{project_id}/steps/{STEP_NAME}/instances/{instance_name.replace('_', '-')}"
        )

        # THEN call transaction that takes longer than product instance is alive. It interacts with the product before
        # the timeout. Value is changed but not uploaded automatically since the transaction fails to store the state
        # of the product at the end. healthy_before_timeout and healthy_after_timeout are uploaded manually to be able
        # to access them.
        with pytest.raises(InternalSolutionException):
            step.change_retrieve_and_timeout_custom_http_product_instance()

        assert step.value == "white"
        assert step.healthy_before_timeout
        assert INSTANCE_MAX_EXECUTION_TIME < JOB_DEFAULT_MAX_RUNNING_TIME
        assert not step.healthy_after_timeout

    def test_instance_max_execution_time_before_and_after_timeout(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test the max_execution_time parameter of the create_instance decorator using HPS.
        Trying to access the instance after timeout will result in a Connection Refused error.
        """
        instance_name = "custom_http_product_instance"
        project_id = function_project.project_id
        step = function_project.project.steps.custom_http_shared_instance_step

        # GIVEN instance cannot be found since it hasn't been initialized and step field has default value
        with pytest.raises(httpx2.HTTPError, match="Client error '404 Not Found'"):
            function_project.get_instance(STEP_NAME, instance_name)
        assert step.value == "white"

        # WHEN Initializing custom product instance with max_execution_time
        step.initialize_max_exec_time_custom_http_product_instance()

        custom_product_instance = function_project.get_instance(STEP_NAME, instance_name)
        assert (
            custom_product_instance["name"]
            == f"projects/{project_id}/steps/{STEP_NAME}/instances/{instance_name.replace('_', '-')}"
        )

        # THEN call transaction that takes longer than product instance is alive.
        # It interacts with the product before and after the timeout.
        # Nothing is uploaded at the end, nor the state of the product is tried to be stored.
        with pytest.raises(InternalSolutionException):
            step.change_timeout_and_retrieve_custom_http_product_instance()

        assert step.value == "white"
        assert INSTANCE_MAX_EXECUTION_TIME < JOB_DEFAULT_MAX_RUNNING_TIME

        assert session_glow.text_in_output(CONNECTION_ERROR)

    def test_instance_max_execution_time_access_after_timeout(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test the max_execution_time parameter of the create_instance decorator using HPS.
        Trying to access the instance after timing out during the transaction will result in a Connection Refused error.
        """
        instance_name = "custom_http_product_instance"
        step = function_project.project.steps.custom_http_shared_instance_step

        # GIVEN instance cannot be found since it hasn't been initialized and step field has default value
        with pytest.raises(httpx2.HTTPError, match="Client error '404 Not Found'"):
            function_project.get_instance(STEP_NAME, instance_name)
        assert step.value == "white"

        # WHEN Initializing custom product instance with max_execution_time and changing product state
        step.initialize_max_exec_time_custom_http_product_instance()
        step.set_red_custom_http_product_instance()

        # THEN call transaction that interacts with the product only after the time has expired.
        # Since instances are only reinitialized at the beginning of a transaction, it will fail.
        # Nothing is uploaded at the end, nor the state of the product is tried to be stored.
        with pytest.raises(InternalSolutionException):
            step.timeout_and_retrieve_custom_http_product_instance()
        assert step.value == "white"

        assert session_glow.text_in_output(CONNECTION_ERROR)

    def test_instance_max_execution_time_reinitialized(
        self,
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_project: ProjectFixture[EndToEndSolution],
    ):
        """
        Test the max_execution_time parameter of the create_instance decorator using HPS.
        Instance is reinitialized at the beginning of transactions after it has already timed out.
        """
        instance_name = "custom_http_product_instance"
        step = function_project.project.steps.custom_http_shared_instance_step

        # GIVEN Initializing custom product instance with max_execution_time and let it timeout
        step.initialize_max_exec_time_custom_http_product_instance()
        with pytest.raises(InternalSolutionException):
            step.change_retrieve_and_timeout_custom_http_product_instance()

        assert step.healthy_before_timeout
        assert not step.healthy_after_timeout

        # WHEN REINVOKING the @instance with max_execution
        step.healthy_before_timeout = False
        step.healthy_after_timeout = True

        # THEN the instance has indeed timed out during its execution again
        with pytest.raises(InternalSolutionException):
            step.change_retrieve_and_timeout_custom_http_product_instance()

        assert session_glow.text_in_output(f"Restarting {instance_name.replace('_', '-')}")

        assert step.healthy_before_timeout
        assert not step.healthy_after_timeout
