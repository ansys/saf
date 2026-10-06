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

import pytest
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

from ansys.saf.testing.selenium import wait_for_element, wait_for_element_and_click, wait_for_text
from ansys.saf.testing.solution.const import TestDeployment
from ansys.saf.testing.solution.end_to_end import ProjectFixture
from tests.mocks.solution_end_to_end.flagship_const import LATEST_VERSION, PREVIOUS_VERSION
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.maxwell_2d_setup_verification_step import INPUT_AEDT_FILE

pytestmark = [
    pytest.mark.parametrize("solution_type", [EndToEndSolution], indirect=True),
    pytest.mark.usefixtures("configure_aedt_installation_dir"),
]


@pytest.fixture(autouse=True)
def upload_project_file_to_ui(
    function_project: ProjectFixture[EndToEndSolution],
    session_selenium_webdriver: WebDriver,
    deployment_type: TestDeployment,
) -> None:
    assert INPUT_AEDT_FILE.is_file()

    session_selenium_webdriver.get(function_project.ui_url)
    wait_for_element_and_click(session_selenium_webdriver, "//*[contains(text(), 'First Page')]", element_type=By.XPATH)
    wait_for_text(session_selenium_webdriver, "file_upload_completed", "File not uploaded yet.")

    element = wait_for_element(session_selenium_webdriver, "aedt_project_file_uploader")
    element.find_element(By.XPATH, ".//input").send_keys(  # pyright: ignore[reportUnknownMemberType]
        INPUT_AEDT_FILE.absolute().as_posix(),
    )
    wait_for_text(session_selenium_webdriver, "file_upload_completed", "File uploaded.")


@pytest.mark.use_aedt
@pytest.mark.parametrize("ui_enabled", [True], indirect=True)
@pytest.mark.parametrize(
    "instance_system_type",
    [pytest.param("PIM", marks=pytest.mark.use_pim), pytest.param("HPS", marks=pytest.mark.use_hps)],
    indirect=True,
)
@pytest.mark.parametrize(
    "deployment_type",
    [
        "Desktop",
        pytest.param("DockerCompose", marks=pytest.mark.xfail(reason="pyaedt not working with docker")),
    ],
    indirect=True,
)
@pytest.mark.parametrize("ansys_release", [LATEST_VERSION, PREVIOUS_VERSION], indirect=True)
class TestE2eBdmProductWorkflow:
    def test_file_handle_from_ui_flagship_product(
        self,
        function_project: ProjectFixture[EndToEndSolution],
        ansys_release: str,
    ):
        """Test that the BDM system can handle workflows in which a file provided from the UI can properly reach a
        Flagship product instance system.
        """
        step = function_project.project.steps.maxwell_2d_verification_step
        step.aedt_version = ansys_release
        step.use_project_cached_at_ui().wait()
        assert step.design_name_list == ["1 Magnetostatic"]

        step.upload_bdm_e2e_aedt_version_from_aedt().wait()
        assert step.aedt_version == f"ANSYSEM_ROOT{ansys_release}"
