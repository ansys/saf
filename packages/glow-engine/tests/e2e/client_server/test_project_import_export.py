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

from pathlib import Path
import re
from typing import Any, TypeVar
import zipfile

import pytest

from ansys.saf.glow.client import BadRequestException, Client
from ansys.saf.glow.solution import Solution
from ansys.saf.testing.solution.const import TestProductInstanceSystemType
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, ProjectFixture
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.transaction_verification_step import TEXT_FILE_DUMMY_STRING

pytestmark = pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True)

T = TypeVar("T", bound=Solution)
BOX_DIMENSIONS = [5.0, 5.0, 0.0]
TOLERANCE = 1e-3


@pytest.mark.parametrize(
    "deployment_type",
    ["Desktop", pytest.param("DockerCompose", marks=pytest.mark.use_containerized)],
    indirect=True,
)
class TestExportImportProjects:
    def test_proper_export_import(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        session_glow: GlowBaseProcess[EndToEndSolution],
        function_client: Client[EndToEndSolution],
        tmp_path: Path,
    ):
        """
        Test that an exported project can be imported again.
        """
        step = function_project.project.steps.transaction_verification_step

        step.create_text_file()
        assert step.read_text_file() == TEXT_FILE_DUMMY_STRING

        function_project.project.export(tmp_path)
        exported_project_file = tmp_path / f"{function_project.display_name}.safx"
        assert exported_project_file.is_file()

        # Check that the exported project does not contain any method logs
        target = tmp_path / "exported_project_extracted"
        with zipfile.ZipFile(exported_project_file) as archive:
            archive.extractall(target)
        log_files = [f for f in target.rglob("*") if ".method_logs" in str(f)]
        assert not log_files

        with ProjectFixture(session_glow, function_client, safx_path=exported_project_file) as new_project:
            step = new_project.project.steps.transaction_verification_step
            assert step.read_text_file() == TEXT_FILE_DUMMY_STRING

    def test_export_during_long_running_method(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        tmp_path: Path,
    ):
        """
        Test that a project cannot be exported while a long_running method is running.
        """
        step = function_project.project.steps.transaction_verification_step
        waiting_seconds = 4

        step.create_text_file()
        assert step.read_text_file() == TEXT_FILE_DUMMY_STRING

        step.sleepy_seconds = waiting_seconds
        method = step.long_running_dummy()

        with pytest.raises(
            BadRequestException,
            match="Unable to perform this action because the following methods are still running",
        ):
            function_project.project.export(tmp_path)
        exported_project_file = tmp_path / f"{function_project.display_name}.safx"
        assert not exported_project_file.is_file()

        method.wait()


@pytest.mark.parametrize("instance_system_type", [pytest.param("PIM", marks=pytest.mark.use_pim)], indirect=True)
def test_export_import_with_product_instance(
    instance_system_type: TestProductInstanceSystemType,
    session_glow: GlowBaseProcess[EndToEndSolution],
    function_client: Client[EndToEndSolution],
    function_project: ProjectFixture[EndToEndSolution],
    tmp_path: Path,
):
    """
    Test that instances are preserved after a project is exported and imported again.
    """

    def verify_instances_of_original_and_imported_projects(
        original_instance: dict[str, Any],
        imported_instance: dict[str, Any],
    ):
        assert re.match(r"projects/.*/steps", original_instance["name"])
        assert re.match(r"projects/.*/steps", imported_instance["name"])
        assert original_instance["name"] != imported_instance["name"]

        assert re.match(r"instances/.*", original_instance["pim_name"])
        assert not imported_instance["pim_name"]

        assert original_instance["product_version"] == imported_instance["product_version"]
        assert original_instance["service_name"] == imported_instance["service_name"]

    # GIVEN: Project that has used a product instance
    original_step = function_project.project.steps.custom_http_shared_instance_step
    original_step.initialize_custom_http_product_instance().wait()
    # changes internal state to "red", but step value is not modified
    original_step.set_red_custom_http_product_instance()
    assert original_step.value == "white"

    # WHEN: Exporting the project and importing it
    function_project.project.export(tmp_path)
    exported_project_file = tmp_path / f"{function_project.display_name}.safx"
    assert exported_project_file.is_file()
    with ProjectFixture(session_glow, function_client, safx_path=exported_project_file) as imported_project:
        # THEN: Instance records are kept
        original_instance = function_project.get_instance(
            "custom_http_shared_instance_step",
            "custom_http_product_instance",
        )
        imported_instance = imported_project.get_instance(
            "custom_http_shared_instance_step",
            "custom_http_product_instance",
        )
        verify_instances_of_original_and_imported_projects(original_instance, imported_instance)

        # THEN: Instance can be used without calling initialize() and its state is restored
        imported_step = imported_project.project.steps.custom_http_shared_instance_step
        imported_step.retrieve_value_custom_http_product_instance()
        assert imported_step.value == "red"

        # Close instance
        imported_step.shutdown_custom_http_product_instance()
    original_step.shutdown_custom_http_product_instance()
