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

import _strptime  # noqa: F401 # type: ignore
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
import zipfile

import httpx2
from pydantic import ValidationError
import pytest

from ansys.saf.glow.client import BadRequestException, Client, NotFoundException
from ansys.saf.glow.solution import NO_ENTITY
from ansys.saf.testing.common import YieldFixture
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, ProjectFixture
from tests.check_message import check_message
from tests.e2e.conftest import SetExternalApiUrlConfiguration
from tests.mocks.solutions.minimal_solution import MinimalSolution, MinimalStep, MyEnum, User, Users

if TYPE_CHECKING:
    from ansys.bdm.api import EntityHandle

pytestmark = pytest.mark.parametrize("solution_type", [MinimalSolution], indirect=True)


@pytest.fixture
def project_filenames() -> list[str]:
    return ["myfile.py", "something_else.txt", "path with space.py", "directory/file.ext", "directory/test.py"]


@pytest.fixture
def project_files(function_project: ProjectFixture[MinimalSolution], project_filenames: list[str]) -> Path:
    with function_project.project.storage_scope as storage:
        root = storage.get_storage_root()
        handles: list[EntityHandle] = []
        for project_file in project_filenames:
            file_path = root / project_file
            file_path.parent.mkdir(exist_ok=True, parents=True)
            file_path.touch(exist_ok=True)
            if project_file == "directory/file.ext":
                file_path.write_text("hello world!")
            handles.append(storage.store(file_path))
        function_project.project.steps.minimal_step.handles = handles

    return function_project.project_files_dir


@pytest.fixture
def safx_path(function_project: ProjectFixture[MinimalSolution], tmp_path: Path) -> Path:
    function_project.project.export(tmp_path)
    safx_path = tmp_path / f"{function_project.project.project_display_name}.safx"
    return safx_path


@pytest.fixture(autouse=True)
def cleanup_projects(session_glow: GlowBaseProcess[MinimalSolution]):
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        # Keep deleting page 1 until empty, so pagination cannot hide leftovers
        while True:
            projects = client.list_projects(page=1, page_size=100)["projects"]
            if not projects:
                break
            for project in projects:
                client.get_project(project["name"]).delete()


def test_minimal_docs(session_glow: GlowBaseProcess[MinimalSolution]):
    url = f"{session_glow.base_api_url}/openapi.json"
    r = httpx2.get(url)
    assert {
        "/",
        "/projects",
        "/projects:import",
        "/projects/{project_id}:export",
        "/projects/{project_id}/bdm-locks",
        "/projects/{project_id}/bdm-locks/{lock_id}",
        "/projects/{project_id}",
        "/projects/{project_id}:upgrade",
        "/health",
        "/schema",
        "/projects/{project_id}/steps/minimal-step",
        "/projects/{project_id}/steps/minimal-step/data/{datapath}",
        "/projects/{project_id}/steps/minimal-step:dont-change-x",
        "/projects/{project_id}/steps/minimal-step/blobs/{datapath}",
        "/projects/{project_id}/steps/minimal-step/blobs/hello-file",
        "/projects/{project_id}/steps/minimal-step:create-hello-file",
        "/projects/{project_id}/steps/other-step",
        "/projects/{project_id}/steps/other-step/data/{datapath}",
        "/projects/{project_id}/steps/other-step/blobs/{datapath}",
        "/projects/{project_id}/steps/fieldless-step",
        "/projects/{project_id}/steps/fieldless-step/data/{datapath}",
        "/projects/{project_id}/steps/fieldless-step/blobs/{datapath}",
        "/projects/{project_id}/steps/fieldless-step:square",
        "/desktop:exit",
        "/desktop:hps-auth-info",
        "/graphql",
        "/events/projects/{project_id}/steps/{step_id}/streams/{stream_name}",
    } == set(r.json()["paths"].keys())


@pytest.mark.parametrize("with_description", [True, False])
def test_create_project(session_glow: GlowBaseProcess[MinimalSolution], with_description: bool):
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        project = client.create_project("x", description="Created with description" if with_description else "")
        payload = client.list_projects(filter='display_name = "x"')
        created_project = next(
            project_data for project_data in payload["projects"] if project_data["name"] == project.project_name
        )
        assert created_project["display_name"] == "x"
        assert created_project["description"] == ("Created with description" if with_description else "")


def test_create_project_not_known_from_server(session_glow: GlowBaseProcess[MinimalSolution]):
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        project_proxy = client.create_project("my_project")
        assert f"{session_glow.base_api_url}/projects/" in project_proxy.url


@pytest.mark.parametrize("with_description", [True, False])
def test_create_project_multiple_times_no_error(session_glow: GlowBaseProcess[MinimalSolution], with_description: bool):
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        create_kwargs = {"display_name": "my_project"}
        if with_description:
            create_kwargs["description"] = "my custom description"
        project_proxy = client.create_project(**create_kwargs)
        project_proxy2 = client.create_project(**create_kwargs)
        assert project_proxy.url != project_proxy2.url


def test_export_project_create_safx_file(function_project: ProjectFixture[MinimalSolution], tmp_path: Path):
    function_project.project.export(tmp_path)
    safx_path = tmp_path / f"{function_project.project.project_display_name}.safx"
    assert safx_path.exists()


@pytest.mark.parametrize("with_description", [True, False])
def test_export_create_sap_file(
    function_project: ProjectFixture[MinimalSolution],
    tmp_path: Path,
    project_files: Path,
    with_description: bool,
):
    # GIVEN - Project with a modified value exported into a SAFX file
    minimal_step = function_project.project.steps.minimal_step
    new_x_value = 3256
    minimal_step.x = new_x_value

    # GIVEN - Some (dummy) logs in the project
    method_logs_path_1 = project_files / ".method_logs" / "minimal_step" / "dummy_method" / "log_o3ntmbjb.log"
    method_logs_path_1.parent.mkdir(parents=True, exist_ok=True)
    method_logs_path_1.touch()
    method_logs_path_2 = project_files / ".method_logs" / "minimal_step" / "dummy_method" / "log_ogdrgbjb.log"
    method_logs_path_2.touch()

    if with_description:
        function_project.project.modify_info(description="my custom description")

    function_project.project.export(tmp_path)

    # WHEN - Extracting the SAFX file
    safx_path = tmp_path / f"{function_project.project.project_display_name}.safx"
    with zipfile.ZipFile(safx_path, "r") as archive:
        archive.extractall(tmp_path)

    # THEN - the logs are not in the archive
    log_files = [f for f in tmp_path.rglob("*") if ".method_logs" in str(f)]
    assert not log_files

    # THEN - a SAP file exists with correct information about the project, solution schema and project data
    project_file = [f for f in tmp_path.iterdir() if f.suffix == ".sap"][0]
    assert project_file

    project_data = json.loads(project_file.read_text())
    assert project_data["name"] == function_project.project_name
    assert project_data["display_name"] == function_project.display_name

    assert project_data["solution_name"] == function_project.solution_schema["title"]
    assert project_data["description"] == function_project.project.project_description
    assert (
        list(project_data["solution"]["steps"].keys()) == function_project.solution_schema["$defs"]["Steps"]["required"]
    )
    assert (
        project_data["solution"]["steps"]["minimal_step"].keys()
        == function_project.solution_schema["$defs"]["MinimalStep"]["properties"].keys()
    )

    # check modified solution data
    assert project_data["solution"]["steps"]["minimal_step"]["x"] == new_x_value


def test_export_creates_copies_of_all_project_files(
    function_project: ProjectFixture[MinimalSolution],
    tmp_path: Path,
    project_files: Path,
):
    function_project.project.export(tmp_path)
    safx_path = tmp_path / f"{function_project.project.project_display_name}.safx"
    with zipfile.ZipFile(safx_path, "r") as archive:
        archive.extractall(tmp_path)

    project_file = [f for f in tmp_path.iterdir() if f.suffix == ".sap"][0]
    project_files_dir = tmp_path / project_file.stem
    project_files_in_zip = [f.relative_to(project_files_dir) for f in project_files_dir.rglob("*") if f.is_file()]
    project_files_in_glow = [
        f.relative_to(function_project.project_files_dir)
        for f in function_project.project_files_dir.rglob("*")
        if f.is_file()
    ]

    assert sorted(project_files_in_zip) == sorted(project_files_in_glow)


@pytest.mark.parametrize("with_description", [True, False])
def test_import_creates_new_project_with_target_name(
    function_project: ProjectFixture[MinimalSolution],
    tmp_path: Path,
    session_glow: GlowBaseProcess[MinimalSolution],
    with_description: bool,
):
    if with_description:
        function_project.project.modify_info(description="my custom description")

    function_project.project.export(tmp_path)
    safx_path = tmp_path / f"{function_project.project.project_display_name}.safx"

    project_name = "my_project"
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        project = client.import_project(safx_path, project_name)
        assert project.project_display_name == project_name
        assert project.project_description == ("my custom description" if with_description else "")


@pytest.mark.parametrize("safx_archive", ["safx_path"])
def test_import_creates_copies_of_all_the_files_in_the_source_archive(
    safx_archive: str,
    request: pytest.FixtureRequest,
    session_glow: GlowBaseProcess[MinimalSolution],
    project_files: Path,
):
    project_name = "my_project"
    safx_archive = request.getfixturevalue(safx_archive)
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        project = client.import_project(Path(safx_archive), project_name)
        imported_project_dir = session_glow.project_files_directory / project.project_id
        imported_project_files = [
            f.relative_to(imported_project_dir) for f in (imported_project_dir).rglob("*") if f.is_file()
        ]
        assert imported_project_files == [f.relative_to(project_files) for f in project_files.rglob("*") if f.is_file()]


def _get_solution_data_from_safx_file(safx_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(safx_path, "r") as archive:
        project_file = [f for f in archive.namelist() if f.endswith(".sap")][0]
        project_data = json.loads(archive.read(project_file))
        if "name" in project_data:
            # older GLOW versions didn't save ProjectInfo fields in the SAP file
            del project_data["name"]
            del project_data["display_name"]
            del project_data["date_created"]
            del project_data["date_modified"]
            del project_data["bdm_locks"]

    return project_data


@pytest.mark.parametrize("safx_archive", ["safx_path"])
def test_import_creates_solution_with_correct_data(
    safx_archive: str,
    request: pytest.FixtureRequest,
    session_glow: GlowBaseProcess[MinimalSolution],
    tmp_path: Path,
):
    safx_archive = request.getfixturevalue(safx_archive)
    imported_project_data = _get_solution_data_from_safx_file(Path(safx_archive))

    project_name = "my_project"
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        project = client.import_project(Path(safx_archive), project_name)
        project.export(tmp_path)
        exported_safx_path = tmp_path / f"{project.project_display_name}.safx"
        exported_project_data = _get_solution_data_from_safx_file(exported_safx_path)
        assert imported_project_data == exported_project_data


def test_when_import_passed_file_with_the_wrong_file_extension_an_exception_is_raised(
    session_glow: GlowBaseProcess[MinimalSolution],
    tmp_path: Path,
):
    project_name = "my_project"
    safx = tmp_path / "target.sap"
    safx.write_text("wrong_file")
    with (
        Client(
            session_glow.solution_type,
            session_glow.base_api_url,
        ) as client,
        pytest.raises(BadRequestException, match="Expected a .safx file, but received: 'target.sap'."),
    ):
        client.import_project(safx, project_name)


def test_get_step_proxy_property_same_value_as_step_server(function_project: ProjectFixture[MinimalSolution]):
    """Tests that accessing property from the step proxy returns the same result
    as the property on the step used by the server."""
    url = f"{function_project.url}/steps/minimal-step"
    response = httpx2.get(url).json()
    minimal_step = function_project.project.steps.minimal_step
    assert minimal_step.x == response["x"]
    assert minimal_step.name == response["name"]
    assert minimal_step.optional_thing == response["optional_thing"]
    url = f"{function_project.url}/steps/other-step"
    response = httpx2.get(url).json()
    other_step = function_project.project.steps.other_step
    assert other_step.id == response["id"]


def test_set_step_proxy_property_modify_value_from_step_server(
    function_project: ProjectFixture[MinimalSolution],
):
    """Tests that setting property from the step proxy modify the step server-side."""
    url = f"{function_project.url}/steps/minimal-step"
    minimal_step = function_project.project.steps.minimal_step
    new_value = 2
    minimal_step.x = new_value
    new_response = httpx2.get(url).json()
    assert new_value == new_response["x"]
    assert minimal_step.x == new_value


def test_set_step_invalid_type_value_raise_invalid_argument_exception(
    function_project: ProjectFixture[MinimalSolution],
):
    """Tests that setting property from the step proxy with a wrong type raises an exception."""
    minimal_step = function_project.project.steps.minimal_step
    with pytest.raises(BadRequestException, match="Input should be a valid integer"):
        minimal_step.x = "Nan"  # type: ignore


def test_set_step_invalid_model_type_value_raises_understandable_bad_request_exception(
    function_project: ProjectFixture[MinimalSolution],
):
    """Tests that setting a model type property from the step proxy
    with a wrong type raises an understandable exception."""
    minimal_step = function_project.project.steps.minimal_step
    with pytest.raises(BadRequestException) as e:
        minimal_step.users = NO_ENTITY  # type: ignore
    check_message(
        [
            "1 validation error for MinimalStep",
            "users",
            "Input should be a valid dictionary or instance of Users "
            "[type=model_type, input_value=EntityHandle(is_blob=True...ncoding=None, size=None), "
            "input_type=EntityHandle]",
        ],
        e.value.args[0],
    )


def test_set_step_property_invalid_value_raise_invalid_argument_exception(
    function_project: ProjectFixture[MinimalSolution],
):
    """Tests that setting property from the step proxy with a wrong value from validator raises an exception."""
    minimal_step = function_project.project.steps.minimal_step
    with pytest.raises(BadRequestException, match="NoSpace must contain a space"):
        minimal_step.name = "NoSpace"  # type: ignore


def test_set_step_multiple_fields_validation_is_not_supported(function_project: ProjectFixture[MinimalSolution]):
    """Tests that setting property from the step proxy with a value that is validated using values from other fields
    is not supported.

    When fields are validated before being set, all validation is executed but fields except the modified one have
    the default value. Therefore, we are going to test that a value that should be valid based on another value that
    is not set to the default actually raises an exception."""
    minimal_step = function_project.project.steps.minimal_step
    modified_step = MinimalStep.model_validate({"value": 3, "squared_value": 9})
    with pytest.raises(BadRequestException, match="squared_value must be equal to value x value."):
        minimal_step.set_fields(modified_step.model_dump(exclude_defaults=True))


def test_set_step_invalid_item_from_list_raise_invalid_argument_exception(
    function_project: ProjectFixture[MinimalSolution],
):
    """Tests that setting property from the step proxy with values that are not validated raises an exception."""
    minimal_step = function_project.project.steps.minimal_step
    new_list = [2, 4, 5]
    with pytest.raises(BadRequestException, match="5 is not an even number"):
        minimal_step.even_numbers = new_list  # type: ignore


def test_set_step_proxy_unexistent_property_raise_error(function_project: ProjectFixture[MinimalSolution]):
    """Tests that setting an unexistent property from the step proxy raises an exception."""
    minimal_step = function_project.project.steps.minimal_step
    with pytest.raises(
        AttributeError,
        match="'MinimalStep' object has no attribute 'a'.\nAvailable attributes are: state, x, name, optional_thing.",
    ):
        _ = minimal_step.a  # type: ignore


def test_set_step_proxy_property_same_value_get_step_proxy(function_project: ProjectFixture[MinimalSolution]):
    """Tests that setting property from the step proxy returns the same value when accessing the value afterward."""
    minimal_step = function_project.project.steps.minimal_step
    new_value = "new name"
    minimal_step.name = new_value
    assert new_value == minimal_step.name


def test_access_unexistent_step_raise_error(function_project: ProjectFixture[MinimalSolution]):
    """Tests that accessing an nonexistent step from the project proxy raises an exception."""
    with pytest.raises(
        AttributeError,
        match="'unexistent' is not a valid step name. Possible values are: minimal_step, other_step.",
    ):
        _ = function_project.project.steps.unexistent  # type: ignore


@pytest.mark.parametrize("with_description", [True, False])
def test_project_has_project_properties_with_the_expected_value(
    session_glow: GlowBaseProcess[MinimalSolution],
    with_description: bool,
):
    # GIVEN - SAF client
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        # WHEN - create project
        if with_description:
            project = client.create_project("x", description="my custom description")
        else:
            project = client.create_project("x")

        # THEN - project has project_display_name, project_name, project_id, and url properties
        assert project.project_id
        assert project.project_name == f"projects/{project.project_id}"
        assert project.project_display_name == "x"
        assert project.project_description == ("my custom description" if with_description else "")
        assert project.url == f"{session_glow.base_api_url}/{project.project_name}"
        # THEN - project has date_created and date_modified property
        date_created = datetime.strptime(project.date_created, "%Y-%m-%dT%H:%M:%S.%f")  # type: ignore
        assert datetime.now() - date_created < timedelta(minutes=1)
        # THEN - project has project_create_date property
        date_modified = datetime.strptime(project.date_modified, "%Y-%m-%dT%H:%M:%S.%f")  # type: ignore
        assert date_created == date_modified


@pytest.fixture
def configure_external_api_url(session_glow: GlowBaseProcess[MinimalSolution]) -> YieldFixture[None]:
    session_glow.change_configuration(SetExternalApiUrlConfiguration, external_api_url="https://my.external.url:1234")
    yield
    session_glow.configure_default_execution()


@pytest.mark.usefixtures("configure_external_api_url")
def test_project_url_does_not_reflect_external_api_url(session_glow: GlowBaseProcess[MinimalSolution]):
    # GIVEN - SAF client
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        # WHEN - create project
        project = client.create_project("x")

        # THEN - project's url property still returns the internal URL which may not be accessible from the user side.
        assert project.url != f"https://my.external.url:1234/{project.project_name}"
        assert project.url == f"{session_glow.base_api_url}/{project.project_name}"


@pytest.mark.parametrize(
    ("modify_kwargs", "expected_display_name", "expected_description"),
    [
        ({"display_name": ""}, "", "old_description"),
        ({"description": "Updated description"}, "x", "Updated description"),
        ({"display_name": "y", "description": "new_description"}, "y", "new_description"),
        ({"display_name": "", "description": ""}, "", ""),
    ],
)
def test_modify_project_info_from_client(
    session_glow: GlowBaseProcess[MinimalSolution],
    modify_kwargs: dict[str, str],
    expected_display_name: str,
    expected_description: str,
):
    """Test modify_info updates the requested fields while preserving others."""
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        project = client.create_project("x", description="old_description")
        old_date_modified = project.date_modified  # type: ignore

        project.modify_info(**modify_kwargs)

        listed_projects = client.list_projects()["projects"]
        project_payload = next(
            project_data for project_data in listed_projects if project_data["name"] == project.project_name
        )
        assert project_payload["display_name"] == expected_display_name
        assert project_payload["description"] == expected_description
        assert project.project_display_name == expected_display_name
        assert project.date_modified != old_date_modified  # type: ignore


def test_project_display_name_modified_to_invalid_string_value(session_glow: GlowBaseProcess[MinimalSolution]):
    """Test that the display name of a project cannot be changed to an invalid string."""
    # GIVEN - SAF client
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        # WHEN - create project and modify its display name
        project = client.create_project("x")
        with pytest.raises(
            BadRequestException,
            match="Value error, Display name cannot contain any of the following characters",
        ):
            project.modify_info(display_name="*:<>|?")


@pytest.mark.parametrize("project_field", ["display_name", "description"])
def test_project_properties_modified_to_non_string_value(
    session_glow: GlowBaseProcess[MinimalSolution],
    project_field: str,
):
    """Test that the display name of a project cannot be changed to a non-string value."""
    # GIVEN - SAF client
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        # WHEN - create project and modify its display name
        project = client.create_project("x")
        with pytest.raises(BadRequestException, match="Input should be a valid string"):
            project.modify_info(**{project_field: 123})  # type: ignore


@pytest.mark.parametrize(
    "modify_kwargs",
    [{}, {"display_name": None, "description": None}, {"display_name": None}, {"description": None}],
)
def test_modify_project_without_fields_raises_error(
    session_glow: GlowBaseProcess[MinimalSolution],
    modify_kwargs: dict[str, Any],
):
    """Test that calling modify_info without any field value raises a ValueError."""
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        project = client.create_project("x", description="old_description")
        with pytest.raises(ValueError, match="At least one of 'display_name' or 'description' must be provided"):
            project.modify_info(**modify_kwargs)


def test_list_projects(session_glow: GlowBaseProcess[MinimalSolution]):
    """Test that the projects of a particular solution can be listed using the client."""
    # GIVEN - SAF client
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        # WHEN - create projects
        project_1 = client.create_project("distinct_display_name_1")
        project_2 = client.create_project(
            "distinct_display_name_2",
            description="This is a description for distinct_display_name_2",
        )

        # THEN - The projects are listed
        listed_projects: list[dict[str, Any]] = client.list_projects()["projects"]
        assert any(
            project_1.project_display_name == project.get("display_name")
            and project_1.project_name == project.get("name")
            and project_1.project_description == project.get("description")
            for project in listed_projects
        )
        assert any(
            project_2.project_display_name == project.get("display_name")
            and project_2.project_name == project.get("name")
            and project_2.project_description == project.get("description")
            for project in listed_projects
        )


def test_list_projects_with_no_project(session_glow: GlowBaseProcess[MinimalSolution]):
    """Test that listing the projects of a solution with no projects returns an empty list."""
    # GIVEN - SAF client
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        listed_projects = client.list_projects()["projects"]
        assert listed_projects == []


def test_list_projects_default_pagination(session_glow: GlowBaseProcess[MinimalSolution]):
    """Test that default pagination returns up to 100 projects."""
    # GIVEN - SAF client and many projects
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        for i in range(105):
            client.create_project(f"project_{i:03}")
        # WHEN - listing projects with default query parameters
        payload = client.list_projects()

        # THEN - first page is returned with default page size
        assert len(payload["projects"]) == 100
        assert payload["total_projects"] == 105
        assert payload["current_page"] == 1
        assert payload["page_size"] == 100
        assert payload["total_pages"] == 2


@pytest.mark.parametrize(
    ("kwargs"),
    [
        {"page": 0},
        {"page": -5},
        {"page_size": 0},
        {"page_size": -10},
    ],
)
def test_list_projects_invalid_pagination_returns_bad_request(
    session_glow: GlowBaseProcess[MinimalSolution],
    kwargs: dict[str, int],
):
    """Test that invalid pagination values return a bad request client exception."""
    # GIVEN - SAF client and at least one project
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        client.create_project("project_001")
        # WHEN / THEN - listing projects with an invalid pagination query raises
        with pytest.raises(BadRequestException) as ex:
            client.list_projects(**kwargs)  # pyright: ignore[reportArgumentType]
        assert ex.value.args[0][0]["msg"] == "Input should be greater than 0"


def test_list_projects_page_size_exceeds_max_is_capped(session_glow: GlowBaseProcess[MinimalSolution]):
    """Test that page_size greater than 100 is capped to 100."""
    # GIVEN - SAF client and more than 100 projects
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        for i in range(105):
            client.create_project(f"project_{i:03}")
        # WHEN - listing projects with page_size above the documented maximum
        payload = client.list_projects(page_size=200)

        # THEN - response is limited to 100 projects and reports capped page size
        assert len(payload["projects"]) == 100
        assert payload["page_size"] == 100
        assert payload["total_projects"] == 105
        assert payload["total_pages"] == 2


def test_list_projects_pagination_second_page(session_glow: GlowBaseProcess[MinimalSolution]):
    """Test that requesting page 2 returns the second chunk of data."""
    # GIVEN - SAF client and many projects
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        for i in range(10):
            client.create_project(f"project_{i:03}")
        # WHEN - requesting the second page with a custom page size
        payload = client.list_projects(page=2, page_size=3)
        # THEN - the second page metadata and item count are correct
        assert len(payload["projects"]) == 3
        assert payload["current_page"] == 2
        assert payload["page_size"] == 3
        assert payload["total_projects"] == 10
        assert payload["total_pages"] == 4


def test_list_projects_pagination_beyond_total_pages(session_glow: GlowBaseProcess[MinimalSolution]):
    """Test that requesting a page beyond the total pages returns an error."""
    # GIVEN - SAF client and a bounded number of projects
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        for i in range(10):
            client.create_project(f"project_{i:03}")
        # WHEN / THEN - requesting a page that does not contain any projects raises
        with pytest.raises(BadRequestException, match="Invalid page number"):
            client.list_projects(page=10, page_size=3)


@pytest.mark.parametrize("str_field", ["display_name", "description"])
def test_list_projects_filter_by_str_field(session_glow: GlowBaseProcess[MinimalSolution], str_field: str):
    """Test filtering by a string field (display_name, description) does a case-insensitive contains matching."""
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        # GIVEN - projects with distinct and overlapping names
        client.create_project("Electric Motor v1", description="This is a description for Electric Motor v1")
        client.create_project("Thermal Motor v2", description="This is a description for Thermal Motor v2")
        client.create_project("Fluid AND Simulation", description="This is a description for Fluid AND Simulation")

        # WHEN/THEN - no filter returns all projects
        results = client.list_projects()["projects"]
        assert len(results) == 3
        assert {p["display_name"] for p in results} == {"Electric Motor v1", "Thermal Motor v2", "Fluid AND Simulation"}

        # WHEN/THEN - filter that matches no project returns empty list
        results = client.list_projects(filter=f"{str_field} = NonExistentProject")["projects"]
        assert not results

        # WHEN/THEN - unquoted lowercase filter matches both "Motor" projects (case-insensitive substring matching)
        results = client.list_projects(filter=f"{str_field} = motor")["projects"]
        assert len(results) == 2
        assert {p["display_name"] for p in results} == {"Electric Motor v1", "Thermal Motor v2"}

        # WHEN/THEN - quoted filter with spaces and no spaces around operator matches both "Motor" projects
        results = client.list_projects(filter=f'{str_field}="motor v"')["projects"]
        assert len(results) == 2
        assert {p["display_name"] for p in results} == {"Electric Motor v1", "Thermal Motor v2"}

        # WHEN/THEN - duplicate display_name AND conditions narrow the result
        results = client.list_projects(filter=f"{str_field} = motor AND {str_field} = v1")["projects"]
        assert len(results) == 1
        assert results[0]["display_name"] == "Electric Motor v1"

        # WHEN/THEN - filter value containing AND is correctly parsed when quoted
        results = client.list_projects(filter=f'{str_field}="Fluid AND"')["projects"]
        assert len(results) == 1
        assert results[0]["display_name"] == "Fluid AND Simulation"


def test_list_projects_filter_by_date(session_glow: GlowBaseProcess[MinimalSolution]):
    """Test filtering by date fields with various operators and ranges."""
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        # GIVEN - two projects, one of which will be modified
        project_to_modify = client.create_project("Will Be Modified")
        unchanged = client.create_project("Unchanged Project")
        timestamp_before_modification = datetime.now().isoformat()
        project_to_modify.modify_info(display_name="Modified Project")

        # THEN - a far-future date_created >= returns no projects
        filter_str = "date_created >= 2099-12-31T23:59:59"
        results = client.list_projects(filter=filter_str)["projects"]
        assert not results

        # WHEN/THEN - date_modified > timestamp returns only the modified project
        results = client.list_projects(filter=f"date_modified > {timestamp_before_modification}")["projects"]
        assert len(results) == 1
        assert results[0]["display_name"] == "Modified Project"

        # WHEN/THEN - date_created <= now returns both projects (all were created before now)
        results = client.list_projects(filter=f"date_created <= {datetime.now().isoformat()}")["projects"]
        assert len(results) == 2
        assert {p["display_name"] for p in results} == {"Modified Project", "Unchanged Project"}

        # WHEN/THEN - date_created with != excludes the unchanged project
        filter_str = f"date_created != {unchanged.date_created}"  # type: ignore
        results = client.list_projects(filter=filter_str)["projects"]
        assert len(results) == 1
        assert results[0]["display_name"] == "Modified Project"

        # WHEN/THEN - using date value instead of datetime
        filter_str = f"date_created >= {project_to_modify.date_created.split('T')[0]}"  # type: ignore
        results = client.list_projects(filter=filter_str)["projects"]
        assert len(results) == 2
        assert {p["display_name"] for p in results} == {"Unchanged Project", "Modified Project"}

        # WHEN/THEN - date range: date_created >= first project AND date_created <= unchanged project
        filter_str = (
            f"date_created >= {project_to_modify.date_created}"  # type: ignore
            f" AND date_created <= {unchanged.date_created}"  # type: ignore
        )
        results = client.list_projects(filter=filter_str)["projects"]
        assert len(results) == 2
        assert {p["display_name"] for p in results} == {"Modified Project", "Unchanged Project"}

        # WHEN/THEN - date range: date_modified >= now AND date_modified <= timestamp_before_modification
        # invalid date range returns no project instead of raising error
        filter_str = (
            f"date_modified > {datetime.now().isoformat()}"  # type: ignore
            f" AND date_modified <= {timestamp_before_modification}"  # type: ignore
        )
        results = client.list_projects(filter=filter_str)["projects"]
        assert not results


def test_list_projects_filter_by_date_and_display_name(
    session_glow: GlowBaseProcess[MinimalSolution],
):
    """Test AND-combined filter with display_name and date fields."""
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        # GIVEN - three projects created sequentially
        client.create_project("Alpha Analysis")
        p2 = client.create_project("Beta Analysis")
        p3 = client.create_project("Beta Simulation")

        # WHEN - filtering by name substring AND date_created > second project's creation date
        filter_str = (
            f"display_name = beta AND date_created > {p2.date_created} AND "  # type: ignore
            f"date_modified >= {p3.date_modified}"  # type: ignore
        )
        results = client.list_projects(filter=filter_str)["projects"]

        # THEN - only "Beta Simulation" matches the three conditions
        assert len(results) == 1
        assert results[0]["display_name"] == "Beta Simulation"


def test_list_projects_filter_with_pagination(session_glow: GlowBaseProcess[MinimalSolution]):
    """Test that filter is applied before pagination and interacts correctly with page/page_size."""
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        # GIVEN - 7 "Target" projects and 3 "Other" projects
        for i in range(7):
            client.create_project(f"Target {i}")
        for i in range(3):
            client.create_project(f"Other {i}")

        # WHEN/THEN - filter + page_size produces correct multi-page metadata
        payload = client.list_projects(filter="display_name = Target", page_size=3, page=1)
        assert payload["total_projects"] == 7
        assert payload["total_pages"] == 3
        assert payload["current_page"] == 1
        assert len(payload["projects"]) == 3
        assert all("Target" in p["display_name"] for p in payload["projects"])

        # WHEN/THEN - requesting page 2 of filtered results
        payload = client.list_projects(filter="display_name = Target", page_size=3, page=2)
        assert payload["current_page"] == 2
        assert len(payload["projects"]) == 3
        assert all("Target" in p["display_name"] for p in payload["projects"])

        # WHEN/THEN - last page has remaining items
        payload = client.list_projects(filter="display_name = Target", page_size=3, page=3)
        assert len(payload["projects"]) == 1
        assert "Target" in payload["projects"][0]["display_name"]


def test_list_projects_filter_empty_string_returns_all(session_glow: GlowBaseProcess[MinimalSolution]):
    """Test that an explicitly empty filter string returns all projects (no filtering applied)."""
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        client.create_project("Alpha")
        client.create_project("Beta")

        # WHEN/THEN - explicit empty filter returns all projects
        payload = client.list_projects(filter="")
        assert payload["total_projects"] == 2
        assert {p["display_name"] for p in payload["projects"]} == {"Alpha", "Beta"}


@pytest.mark.parametrize(
    ("invalid_filter", "expected_error_fragment"),
    [
        ("unknown_field = value", "Input should be 'display_name', 'description', 'date_created' or 'date_modified'"),
        ("date_created >= not-a-date", "Invalid isoformat string"),
        ("date_created >= 2024-01-01T00:00:00+02:00", "Datetime values must be timezone-naive"),
        ("display_name != value", "Only '=' is allowed"),
    ],
    ids=["invalid_field", "invalid_date_value", "timezone_aware_datetime", "invalid_operator_for_field"],
)
def test_list_projects_filter_invalid_expressions(
    session_glow: GlowBaseProcess[MinimalSolution],
    invalid_filter: str,
    expected_error_fragment: str,
):
    """Test that invalid filter expressions return a client error with a descriptive message."""
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:  # noqa: SIM117
        with pytest.raises(BadRequestException, match=expected_error_fragment):
            client.list_projects(filter=invalid_filter)


@pytest.mark.parametrize(
    ("sort_by", "expected_result"),
    [
        ("display_name", ["alpha", "beta", "gamma"]),
        ("description", ["gamma", "alpha", "beta"]),
        ("description desc", ["beta", "alpha", "gamma"]),
        ("display_name desc", ["gamma", "beta", "alpha"]),
        ("date_created", ["beta", "alpha", "gamma"]),
        ("date_created desc", ["gamma", "alpha", "beta"]),
        ("date_modified", ["beta", "alpha", "gamma"]),
        ("date_modified desc", ["gamma", "alpha", "beta"]),
    ],
)
def test_list_projects_order_by(
    session_glow: GlowBaseProcess[MinimalSolution],
    sort_by: str,
    expected_result: list[str],
):
    """Test ordering by various criteria in ascending and descending order."""
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        descriptions = {
            "beta": "zeta",
            "alpha": "omega",
            "gamma": "alpha",
        }
        for name in ["beta", "alpha", "gamma"]:
            client.create_project(name, description=descriptions[name])

        payload = client.list_projects(order_by=sort_by)
        assert [project["display_name"] for project in payload["projects"]] == expected_result


@pytest.mark.parametrize(
    ("sort_by"),
    [
        ("name"),
        ("name desc"),
    ],
)
def test_list_projects_order_by_name(
    session_glow: GlowBaseProcess[MinimalSolution],
    sort_by: str,
):
    """Test ordering by name."""
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        names: list[str] = []
        for name in ["beta", "alpha", "gamma"]:
            names.append(client.create_project(name).project_name)

        payload = client.list_projects(order_by=sort_by)
        names.sort(reverse=sort_by == "name desc")
        assert [project["name"] for project in payload["projects"]] == names


@pytest.mark.parametrize(
    ("order_by", "expected_message"),
    [
        (
            "unsupported_field desc",
            "Value error, Invalid order_by field: 'unsupported_field'. "
            + "Allowed fields are: display_name, description, date_created, date_modified, name.",
        ),
        ("display_name downward", "Invalid order_by direction"),
        ("display_name,,name", "Invalid order_by syntax"),
    ],
)
def test_list_projects_invalid_order_by_returns_raise_error(
    session_glow: GlowBaseProcess[MinimalSolution],
    order_by: str,
    expected_message: str,
):
    """Test that an invalid order_by field raise a proper error."""
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        client.create_project("project_001")
        with pytest.raises(BadRequestException, match=expected_message):
            client.list_projects(order_by=order_by)


@pytest.mark.parametrize(
    ("order_by", "expected_display_names", "expected_project_names"),
    [
        (
            "display_name asc, date_created desc",
            ["alpha", "alpha", "beta"],
            ["second_alpha", "first_alpha", "beta"],
        ),
        (
            "display_name asc,date_created desc",
            ["alpha", "alpha", "beta"],
            ["second_alpha", "first_alpha", "beta"],
        ),
        (
            " display_name asc ,  date_created desc ",
            ["alpha", "alpha", "beta"],
            ["second_alpha", "first_alpha", "beta"],
        ),
        (
            "display_name  asc, date_created    desc",
            ["alpha", "alpha", "beta"],
            ["second_alpha", "first_alpha", "beta"],
        ),
        (
            "display_name desc, date_created asc",
            ["beta", "alpha", "alpha"],
            ["beta", "first_alpha", "second_alpha"],
        ),
        (
            "date_created asc, display_name desc",
            ["alpha", "alpha", "beta"],
            ["first_alpha", "second_alpha", "beta"],
        ),
        (
            "date_created desc, display_name asc",
            ["beta", "alpha", "alpha"],
            ["beta", "second_alpha", "first_alpha"],
        ),
    ],
)
def test_list_projects_order_by_multiple_fields(
    session_glow: GlowBaseProcess[MinimalSolution],
    order_by: str,
    expected_display_names: list[str],
    expected_project_names: list[str],
):
    """Test listing projects by multiple fields, including tie-breakers and whitespace edge cases."""
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        first_alpha = client.create_project("alpha")
        second_alpha = client.create_project("alpha")
        beta = client.create_project("beta")

        payload = client.list_projects(order_by=order_by)
        projects = payload["projects"]

        assert [project["display_name"] for project in projects] == expected_display_names

        project_name_map = {
            "first_alpha": first_alpha.project_name,
            "second_alpha": second_alpha.project_name,
            "beta": beta.project_name,
        }
        assert [project["name"] for project in projects] == [project_name_map[name] for name in expected_project_names]


@pytest.mark.parametrize(
    ("new_users"),
    [
        # Add a user
        Users(users=[User(user_id=1, name="Zea Woods"), User(user_id=99, name="John Doe")]),
        # Modify a user entirely
        Users(users=[User(user_id=2, name="Peter White")]),
        # Modify a user partially
        Users(users=[User(user_id=1, name="Peter White")]),
        # Remove all users
        Users(users=[]),
    ],
)
def test_custom_type_can_be_modified(new_users: Users, function_project: ProjectFixture[MinimalSolution]):
    """Tests that setting a property from the step proxy returns the same value when accessing the value."""
    minimal_step = function_project.project.steps.minimal_step
    assert minimal_step.users == Users(users=[User(user_id=1, name="Zea Woods")])
    minimal_step.users = new_users
    assert minimal_step.users == new_users


def test_custom_type_wrong_data_raises_validation_error(function_project: ProjectFixture[MinimalSolution]):
    """Tests that setting a wrong property raises ValidationError."""
    minimal_step = function_project.project.steps.minimal_step
    with pytest.raises(ValidationError, match="1 validation error for User"):
        minimal_step.users = Users(
            users=[
                User(user_id=1, name="Zea Woods"),
                User(id=2, name="Peter White", wrong_field="wrong_data"),  # type: ignore
            ],
        )


def test_modify_enum_step_field(function_project: ProjectFixture[MinimalSolution]):
    minimal_step = function_project.project.steps.minimal_step
    assert minimal_step.my_enum == MyEnum.a
    minimal_step.my_enum = MyEnum.b
    assert minimal_step.my_enum == MyEnum.b


def test_modify_tuple_step_field(function_project: ProjectFixture[MinimalSolution]):
    minimal_step = function_project.project.steps.minimal_step
    assert minimal_step.my_tuple == ("a", "b")
    minimal_step.my_tuple = ("c", "d")
    assert minimal_step.my_tuple == ("c", "d")


def test_modify_list_tuple_step_field(function_project: ProjectFixture[MinimalSolution]):
    minimal_step = function_project.project.steps.minimal_step
    assert minimal_step.my_list_of_tuple == [("a", "b"), ("c", "d")]
    minimal_step.my_list_of_tuple = [("c", "d")]
    assert minimal_step.my_list_of_tuple == [("c", "d")]


def test_modify_dict_int_int_step_field(function_project: ProjectFixture[MinimalSolution]):
    minimal_step = function_project.project.steps.minimal_step
    assert minimal_step.dict_int_int == {}
    minimal_step.dict_int_int = {0: 0}
    assert minimal_step.dict_int_int == {0: 0}


@pytest.mark.parametrize("substitute_urls", [True, False])
class TestGetData:
    """Test get_data method with and without URL substitution."""

    @pytest.mark.parametrize(
        ("datapath", "expected_value"),
        [
            ("x", 99),
            ("even_numbers", [2, 4]),
            ("even_numbers/0", 2),
            ("users", {"users": [{"name": "Zea Woods", "user_id": 1}]}),
            ("users/users/0/name", "Zea Woods"),
            ("my_tuple/0", "a"),
            ("my_list_of_tuple/1/1", "d"),
            ("dict_user/admin/user_id", 0),
            ("space_dict/key with space", "value"),
            ("dot_dict/key.with.dots", "value"),
            (r"slash_dict/key\/s", "value"),
            ("accent_dict/éèàêë", "value"),
            ("special_char_dict/()+[]{}%*<>?-_", "value"),
        ],
    )
    def test_get_data(
        self,
        function_project: ProjectFixture[MinimalSolution],
        substitute_urls: bool,
        datapath: str,
        expected_value: Any,
    ):
        """Test that get_data retrieves the correct proper data stored in different level of a step field."""
        minimal_step = function_project.project.steps.minimal_step
        data = minimal_step.get_data(datapath, substitute_urls)
        assert data == expected_value

    def test_get_data_empty_string_return_all_step_fields(
        self,
        function_project: ProjectFixture[MinimalSolution],
        substitute_urls: bool,
    ):
        """Test that get_data with an empty string retrieves all the data stored in a step."""
        minimal_step = function_project.project.steps.minimal_step
        data = minimal_step.get_data(substitute_file_handles_with_urls=substitute_urls)
        assert MinimalStep().model_dump().keys() == data.keys()
        data["hello_file"] = NO_ENTITY
        assert MinimalStep.model_validate(data)

    @pytest.mark.parametrize(
        ("datapath"),
        [
            "x/0",
            "even_numbers/a",
            "wrong",
            "users/users/10",
            "users/wrong",
            "users/0",
            "my_tuple/5",
            "_private",
            "dict_user//emptykey",
        ],
    )
    def test_get_data_raise_not_found_wrong_field(
        self,
        function_project: ProjectFixture[MinimalSolution],
        datapath: str,
        substitute_urls: bool,
    ):
        """Test that get_data raises NotFoundException when the datapath is invalid."""
        minimal_step = function_project.project.steps.minimal_step
        with pytest.raises(NotFoundException, match="The object referenced by the datapath cannot be found"):
            _ = minimal_step.get_data(datapath, substitute_file_handles_with_urls=substitute_urls)
