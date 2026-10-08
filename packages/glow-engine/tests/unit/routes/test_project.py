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

from collections.abc import Callable, Generator
from datetime import datetime, timedelta
import io
from pathlib import Path
import re
import sqlite3
import zipfile

import asyncpg  # pyright: ignore[reportMissingTypeStubs]
from fastapi import status
from fastapi.testclient import TestClient
from httpx2 import Response
import pytest

from ansys.saf.glow._config.settings import DatabaseType, Settings
from ansys.saf.glow._server.dependencies import get_settings
from ansys.saf.glow._storage.os import INVALID_CHARACTERS
from ansys.saf.testing.database import PostgresqlServerInfo
from tests.mocks.solutions import has_methods, minimal_solution
from tests.unit.routes.conftest import ProjectFixture

# These tests assume that projects are not leaked between tests, thus we parametrize settings to force creating a new DB
# in every test.
pytestmark = pytest.mark.parametrize(
    "settings",
    [
        {"glow_database_type": DatabaseType.Sqlite},
        {"glow_database_type": DatabaseType.PostgreSql},
    ],
    ids=["sqlite", "postgres"],
    indirect=True,
)
solution = minimal_solution
modified_solution = has_methods


def test_upgrade(client: TestClient, create_project: Callable[[str], Response]):
    create_response = create_project("x")
    project_id = create_response.json()["name"].split("/")[-1]
    response = client.post(f"/projects/{project_id}:upgrade")
    assert response.status_code == status.HTTP_200_OK


def test_list_project_default_pagination(
    client: TestClient,
    create_project: Callable[[str], Response],
):
    """Test that listing the projects returns a paginated lists with a default
    page=1 and page_size=100."""
    for i in range(105):
        create_project(str(i))
    response = client.get("/projects").raise_for_status().json()
    projects = response["projects"]
    assert len(projects) == 100
    assert response["total_projects"] == 105
    assert response["current_page"] == 1
    assert response["page_size"] == 100


def test_list_project_without_projects(client: TestClient):
    """Tests that GET /projects returns an empty list if there is no project."""
    response = client.get("/projects").raise_for_status().json()
    projects = response["projects"]
    assert len(projects) == 0
    assert response["total_projects"] == 0
    assert response["current_page"] == 1
    assert response["page_size"] == 100
    assert response["total_pages"] == 1


def test_list_project_with_inconsistent_solution(
    client_for_app_built_with_modified_solution: TestClient,
    create_project: Callable[[str], Response],
):
    create_project("x")
    response = client_for_app_built_with_modified_solution.get("/projects")
    assert response.status_code == status.HTTP_200_OK
    projects = response.json()["projects"]
    assert len(projects) == 1
    assert projects[0]["display_name"] == "x"
    assert projects[0]["name"] != "projects/__to_be_created__"


def test_list_project_default_order(
    client: TestClient,
    create_project: Callable[[str], Response],
):
    """Test that listing the projects returns a paginated lists with default order."""
    for i in range(11):
        create_project(str(i))
    expected_pages = {
        1: [str(10 - i) for i in range(5)],
        2: [str(5 - i) for i in range(5)],
        3: ["0"],
    }

    for page, expected_display_names in expected_pages.items():
        response = client.get("/projects", params={"page": page, "page_size": 5}).raise_for_status().json()
        projects = response["projects"]
        assert len(projects) == len(expected_display_names)
        assert [project["display_name"] for project in projects] == expected_display_names


@pytest.mark.parametrize(
    ("sort_by", "expected_result"),
    [
        ("display_name", ["alpha", "beta", "gamma"]),
        ("description", ["gamma", "alpha", "beta"]),
        ("description desc", ["beta", "alpha", "gamma"]),
        (" display_name", ["alpha", "beta", "gamma"]),  # testing leading whitespace is ignored
        ("display_name  ", ["alpha", "beta", "gamma"]),  # testing trailing whitespace is ignored
        ("display_name desc", ["gamma", "beta", "alpha"]),
        ("date_created", ["beta", "alpha", "gamma"]),
        ("date_created desc", ["gamma", "alpha", "beta"]),
        ("date_modified", ["beta", "alpha", "gamma"]),
        ("date_modified desc", ["gamma", "alpha", "beta"]),
    ],
)
def test_list_project_order_by(
    client: TestClient,
    create_project: Callable[[str, str], Response],
    sort_by: str,
    expected_result: list[str],
):
    """Test ordering by various criteria in ascending and descending order."""
    descriptions = {
        "beta": "zeta",
        "alpha": "omega",
        "gamma": "alpha",
    }
    for name in ["beta", "alpha", "gamma"]:
        create_project(name, descriptions[name]).json()

    response = client.get("/projects", params={"order_by": sort_by}).raise_for_status().json()
    assert [project["display_name"] for project in response["projects"]] == expected_result


@pytest.mark.parametrize(
    ("sort_by"),
    [
        ("name"),
        ("name desc"),
    ],
)
def test_list_project_order_by_name(
    client: TestClient,
    create_project: Callable[[str], Response],
    sort_by: str,
):
    names: list[str] = []
    for name in ["beta", "alpha", "gamma"]:
        names.append(create_project(name).raise_for_status().json()["name"])

    response = client.get("/projects", params={"order_by": sort_by}).raise_for_status().json()
    names.sort(reverse=sort_by == "name desc")
    assert [project["name"] for project in response["projects"]] == names


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
def test_list_project_order_by_multiple_fields(
    client: TestClient,
    create_project: Callable[[str], Response],
    order_by: str,
    expected_display_names: list[str],
    expected_project_names: list[str],
):
    """Test ordering by multiple fields, including tie-breakers and whitespace edge cases."""
    first_alpha = create_project("alpha").json()
    second_alpha = create_project("alpha").json()
    beta = create_project("beta").json()

    projects = client.get("/projects", params={"order_by": order_by}).raise_for_status().json()["projects"]
    assert [project["display_name"] for project in projects] == expected_display_names

    project_name_map = {
        "first_alpha": first_alpha["name"],
        "second_alpha": second_alpha["name"],
        "beta": beta["name"],
    }
    assert [project["name"] for project in projects] == [project_name_map[name] for name in expected_project_names]


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
def test_list_project_invalid_order_by_field(
    client: TestClient,
    create_project: Callable[[str], Response],
    order_by: str,
    expected_message: str,
):
    """Test that invalid order_by returns a 422 request error."""
    create_project("a")
    response = client.get("/projects", params={"order_by": order_by})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert expected_message in response.json()["detail"][0]["msg"]


@pytest.mark.parametrize("page_value", ["0", "-1"])
def test_list_project_invalid_page(
    page_value: str,
    client: TestClient,
    create_project: Callable[[str], Response],
):
    """Test that invalid page returns a 400 BadRequest error."""
    create_project("a")
    response = client.get(f"/projects?page={page_value}")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"][0]["msg"] == "Input should be greater than 0"


@pytest.mark.parametrize("page_size", ["0", "-1"])
def test_list_project_invalid_page_size(
    page_size: str,
    client: TestClient,
    create_project: Callable[[str], Response],
):
    """Test that invalid page_size returns a 400 BadRequest error."""
    create_project("a")
    response = client.get(f"/projects?page_size={page_size}")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"][0]["msg"] == "Input should be greater than 0"


def test_list_project_page_size_exceeds_max(
    client: TestClient,
    create_project: Callable[[str], Response],
):
    """Test that page_size > 100 is coerced to 100."""
    for i in range(101):
        create_project(str(i))
    response = client.get("/projects?page_size=200").raise_for_status().json()
    # Should be coerced to 100
    assert len(response["projects"]) == 100
    assert response["page_size"] == 100
    assert response["total_projects"] == 101


def test_list_project_custom_page_size(
    client: TestClient,
    create_project: Callable[[str], Response],
):
    """Test pagination with a custom page_size."""
    for i in range(5):
        create_project(str(i))
    response = client.get("/projects?page_size=1").raise_for_status().json()
    projects = response["projects"]
    assert len(projects) == 1
    assert response["current_page"] == 1
    assert response["page_size"] == 1
    assert response["total_projects"] == 5
    assert response["total_pages"] == 5


def test_list_project_second_page(
    client: TestClient,
    create_project: Callable[[str], Response],
):
    """Test retrieving second page with custom page_size."""
    for i in range(15):
        create_project(str(i))
    response = client.get("/projects?page=2&page_size=5").raise_for_status().json()
    projects = response["projects"]
    assert len(projects) == 5
    assert response["current_page"] == 2
    assert response["page_size"] == 5
    assert response["total_projects"] == 15
    assert response["total_pages"] == 3
    assert projects[0]["display_name"] == "9"


def test_list_project_last_page_partial(
    client: TestClient,
    create_project: Callable[[str], Response],
):
    """Test that last page returns remaining projects when count is less than page_size."""
    for i in range(11):
        create_project(str(i))
    response = client.get("/projects?page=3&page_size=5").raise_for_status().json()
    projects = response["projects"]
    assert len(projects) == 1
    assert response["current_page"] == 3
    assert response["page_size"] == 5
    assert response["total_projects"] == 11
    assert response["total_pages"] == 3


def test_list_project_beyond_total_pages(
    client: TestClient,
    create_project: Callable[[str], Response],
):
    """Test that requesting a page beyond available pages returns an error."""
    for i in range(5):
        create_project(str(i))
    response = client.get("/projects?page=2&page_size=5")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Invalid page number"


def test_delete_project_with_inconsistent_solution(
    client_for_app_built_with_modified_solution: TestClient,
    create_project: Callable[[str], Response],
):
    create_response = create_project("x")
    url = f"/{create_response.json()['name']}"
    response = client_for_app_built_with_modified_solution.delete(url)
    assert response.status_code == status.HTTP_200_OK
    response = client_for_app_built_with_modified_solution.get("/projects")
    projects = response.json()["projects"]
    assert len(projects) == 0


def test_export_project_with_inconsistent_solution(
    client_for_app_built_with_modified_solution: TestClient,
    create_project: Callable[[str], Response],
):
    create_response = create_project("x")
    url = f"/{create_response.json()['name']}:export"
    response = client_for_app_built_with_modified_solution.get(url)
    assert response.status_code == status.HTTP_200_OK


def test_get_project_with_inconsistent_solution_returns_422(
    client_for_app_built_with_modified_solution: TestClient,
    create_project: Callable[[str], Response],
):
    create_response = create_project("x")
    url = f"/{create_response.json()['name']}"
    response = client_for_app_built_with_modified_solution.get(url)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_modify_project_with_inconsistent_solution_returns_422(
    client_for_app_built_with_modified_solution: TestClient,
    create_project: Callable[[str], Response],
):
    create_project_response = create_project("old_name").json()
    modified_project_request = {"display_name": "new_name"}
    modify_project_response = client_for_app_built_with_modified_solution.patch(
        create_project_response["name"],
        json=modified_project_request,
    )
    assert modify_project_response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_get_project(client: TestClient, create_project: Callable[[str], Response]):
    create_response = create_project("x")
    create_response.raise_for_status()
    url = f"/{create_response.json()['name']}"
    get_response = client.get(url)
    assert get_response.status_code == status.HTTP_200_OK
    assert create_response.json() == get_response.json()


@pytest.mark.parametrize("with_description", [True, False])
def test_create_project_response(create_project: Callable[[str, str], Response], with_description: bool):
    """Tests that PUT /projects returns the proper response."""
    response = create_project("x", "my custom description" if with_description else "")
    project = response.json()
    date_created = datetime.strptime(project["date_created"], "%Y-%m-%dT%H:%M:%S.%f")
    date_modified = datetime.strptime(project["date_modified"], "%Y-%m-%dT%H:%M:%S.%f")
    assert datetime.now() - date_created < timedelta(minutes=1)
    assert date_created == date_modified
    assert project["display_name"] == "x"
    assert project["description"] == ("my custom description" if with_description else "")
    assert re.match(r"^projects/\w{8}", project["name"])


def test_create_project_wrong_payload_raise_422(client: TestClient):
    """Tests that giving an incorrect payload to PUT /projects returns 422."""
    create_project_request = {"invalid_field": "test"}
    response = client.post("/projects", json=create_project_request)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.parametrize("with_description", [True, False])
def test_create_project_duplicate_generates_no_error(
    create_project: Callable[[str, str], Response],
    with_description: bool,
):
    """Tests that doing twice a PUT /projects with same payload returns 200."""
    create_args = ("x", "Description") if with_description else ("x", "")
    response = create_project(*create_args)
    assert response.status_code == status.HTTP_200_OK
    response = create_project(*create_args)
    assert response.status_code == status.HTTP_200_OK


def test_create_project_invalid_character(client: TestClient, create_project: Callable[[str], Response]):
    create_project_response = create_project(f"name_with invalid_{INVALID_CHARACTERS[0]}")
    assert create_project_response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert (
        "Value error, Display name cannot contain any of the following characters: \\ : * ? < > | ..)"
        in create_project_response.json()["detail"][0]["msg"]
    )
    response = client.get("/projects")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["projects"]) == 0


def test_create_project_invalid_description(client: TestClient, create_project: Callable[[str], Response]):
    create_project_response = create_project("x", 123)  # type: ignore
    assert create_project_response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT  # type: ignore
    assert "Input should be a valid string" in create_project_response.json()["detail"][0]["msg"]  # type: ignore
    response = client.get("/projects")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["projects"]) == 0


@pytest.fixture
def unknown_minimal_project(project_fixture: ProjectFixture, unknown_project: Callable[[ProjectFixture], Path]) -> Path:
    new_values = {"x": 1, "name": "this is a new value"}
    project_fixture.client.patch(url=f"{project_fixture.properties['name']}/steps/minimal-step", json=new_values)
    unknown_project_path = unknown_project(project_fixture)
    return unknown_project_path


def test_export_project_openapi_spec(project_fixture: ProjectFixture):
    # Verify that the OpenAPI spec declares the export endpoint as returning application/zip,
    # not application/json, so that API clients and code generators treat the response as a binary download.
    openapi_response = project_fixture.client.get("openapi.json")
    openapi_response.raise_for_status()
    openapi_spec = openapi_response.json()
    export_path = "/projects/{project_id}:export"
    spec_get_operation = openapi_spec["paths"][export_path]["get"]
    spec_200_content = spec_get_operation["responses"]["200"]["content"]
    assert spec_200_content == {"application/zip": {"schema": {"type": "string", "format": "binary"}}}


def test_export_project_as_safx_attachment(project_fixture: ProjectFixture):
    response = project_fixture.client.get(f"{project_fixture.properties['name']}:export")
    assert response.status_code == status.HTTP_200_OK
    assert response.headers.get("content-type", "") == "application/zip"
    assert response.headers.get("content-disposition", "") == 'attachment; filename="project.safx"'


@pytest.mark.usefixtures("project_dir")
def test_export_project_extracted_safx_contains_all_files(project_fixture: ProjectFixture, tmp_path: Path):
    response = project_fixture.client.get(f"{project_fixture.properties['name']}:export")
    assert response.status_code == status.HTTP_200_OK
    target = tmp_path / "archive"
    assert not target.exists()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        archive.extractall(target)
    extracted_files = [str(i.relative_to(target)) for i in target.rglob("*") if i.is_file()]
    project_files = [
        f.replace(project_fixture.project_id, project_fixture.project_display_name)
        for f in project_fixture.project_files()
    ]
    expected_files = project_files + [f"{project_fixture.project_display_name}.sap"]
    assert sorted(expected_files) == sorted(extracted_files)


@pytest.mark.usefixtures("project_dir")
def test_import_project_extract_files_into_target(project_fixture: ProjectFixture, safx_path: Path):
    with safx_path.open("rb") as f:
        response = project_fixture.client.post(
            "/projects:import",
            files={"safx_file": f},
            data={"display_name": "my_project"},
        )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["display_name"] == "my_project"
    assert response.json()["name"] != project_fixture.properties["name"]

    old_project_name = project_fixture.properties["name"].replace("projects/", "")
    new_project_name = response.json()["name"].replace("projects/", "")
    target_path = project_fixture.project_files_path / new_project_name
    new_project_files = [
        str(i.relative_to(project_fixture.project_files_path)) for i in target_path.rglob("*") if i.is_file()
    ]
    assert new_project_files == [f.replace(old_project_name, new_project_name) for f in project_fixture.project_files()]
    assert (target_path / "myfile.txt").read_bytes() == b"hello world"


def test_import_project_wrong_archive_extension_raise_422(client: TestClient, projects_path: Path):
    wrong_archive = projects_path / "wrong_archive.wrong"
    wrong_archive.write_text("wrong")
    with wrong_archive.open("rb") as f:
        response = client.post(
            "/projects:import",
            files={"safx_file": f},
            data={"display_name": "my_project"},
        )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"] == "Expected a .safx file, but received: 'wrong_archive.wrong'."


def test_import_project_missing_sap_in_safx_content_raise_400(client: TestClient, projects_path: Path):
    project_files_path = projects_path / "missing_sap"
    project_files_path.mkdir()
    safx = projects_path / "missing_sap.safx"
    with zipfile.ZipFile(safx, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(project_files_path, arcname=project_files_path.relative_to(projects_path))
    with safx.open("rb") as f:
        response = client.post(
            "/projects:import",
            files={"safx_file": f},
            data={"display_name": "my_project"},
        )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.json()["detail"]
        == "'missing_sap.safx' is not a valid project archive. It does not contain a top level file."
    )


@pytest.mark.parametrize("clear_values", [True, False])
def test_modify_project(client: TestClient, create_project: Callable[[str, str], Response], clear_values: bool):
    create_project_response = create_project("old_name", "old_description").json()
    modified_project_request = {"display_name": "new_name", "description": "new_description"}
    if clear_values:
        # if an empty string is passed, field values are cleared.
        modified_project_request = dict.fromkeys(modified_project_request, "")
    modify_project_response = client.patch(create_project_response["name"], json=modified_project_request)
    assert modify_project_response.status_code == status.HTTP_200_OK
    modified_project = modify_project_response.json()
    assert modified_project["name"] == create_project_response["name"]
    assert modified_project["display_name"] == ("new_name" if not clear_values else "")
    assert modified_project["description"] == ("new_description" if not clear_values else "")
    date_created = datetime.strptime(modified_project["date_created"], "%Y-%m-%dT%H:%M:%S.%f")
    date_modified = datetime.strptime(modified_project["date_modified"], "%Y-%m-%dT%H:%M:%S.%f")
    assert date_created != date_modified
    list_project_response = client.get("/projects").json()["projects"]
    assert modify_project_response.json() in list_project_response


@pytest.mark.parametrize("field_name", ["display_name", "description"])
@pytest.mark.parametrize("new_value", ["new_value", ""])
def test_modify_project_only_one_field(
    client: TestClient,
    create_project: Callable[[str, str], Response],
    field_name: str,
    new_value: str,
):
    create_project_response = create_project("old_name", "old_description").json()
    modified_project_request = {field_name: new_value}
    modify_project_response = client.patch(create_project_response["name"], json=modified_project_request)
    assert modify_project_response.status_code == status.HTTP_200_OK
    modified_project = modify_project_response.json()
    assert modified_project["name"] == create_project_response["name"]
    other_field = "description" if field_name == "display_name" else "display_name"
    assert (
        modified_project[other_field] == create_project_response[other_field]
    )  # preserves old value if not set in the request
    assert (
        modified_project[field_name] == new_value
    )  # gets new value or clears up the field if empty string is provided
    date_created = datetime.strptime(modified_project["date_created"], "%Y-%m-%dT%H:%M:%S.%f")
    date_modified = datetime.strptime(modified_project["date_modified"], "%Y-%m-%dT%H:%M:%S.%f")
    assert date_created != date_modified
    list_project_response = client.get("/projects").json()["projects"]
    assert modify_project_response.json() in list_project_response


def test_modify_project_no_field(client: TestClient, create_project: Callable[[str, str], Response]):
    create_project_response = create_project("old_name", "old_description").json()
    modify_project_response = client.patch(create_project_response["name"], json={})
    assert modify_project_response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert (
        "Value error, At least one of 'display_name' or 'description' must be provided"
        in modify_project_response.json()["detail"][0]["msg"]
    )
    list_project_response = client.get("/projects").json()["projects"]
    assert create_project_response in list_project_response


def test_modify_project_display_name_invalid_character(client: TestClient, create_project: Callable[[str], Response]):
    create_project_response = create_project("old_name").json()
    modified_project_request = {"display_name": f"new_name_with invalid_{INVALID_CHARACTERS[0]}"}
    modify_project_response = client.patch(create_project_response["name"], json=modified_project_request)
    assert modify_project_response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    modify_project_response_text = modify_project_response.json()["detail"][0]["msg"]
    assert "Value error" in modify_project_response_text
    assert (
        "Display name cannot contain any of the following characters: \\ : * ? < > | ..)"
        in modify_project_response_text
    )
    response = client.get(create_project_response["name"])
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["display_name"] == "old_name"


def test_modify_project_description_non_string(client: TestClient, create_project: Callable[[str, str], Response]):
    create_project_response = create_project("old_name", "old_description").json()
    modified_project_request = {"description": 123}
    modify_project_response = client.patch(create_project_response["name"], json=modified_project_request)
    assert modify_project_response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    modify_project_response_text = modify_project_response.json()["detail"][0]["msg"]
    assert "Input should be a valid string" in modify_project_response_text
    response = client.get(create_project_response["name"])
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["description"] == "old_description"


def test_delete_project_remove_project_from_projects(create_project: Callable[[str], Response], client: TestClient):
    """Tests that DELETE /projects/{project_id} removes project from GET /projects."""
    create_response = create_project("x")
    assert create_response.status_code == status.HTTP_200_OK
    projects_response = client.get("/projects")
    assert create_response.json() in projects_response.json()["projects"]
    delete_response = client.delete(create_response.json()["name"])
    assert delete_response.status_code == status.HTTP_200_OK
    projects_response = client.get("/projects")
    assert delete_response.json() not in projects_response.json()["projects"]


def test_delete_project_nonexistent_project_returns_404(client: TestClient):
    """Tests that DELETE /projects/{wrong_id} returns a 404 error."""
    delete_response = client.delete("projects/not_a_project_id")
    assert delete_response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_project_removes_project(client: TestClient, create_project: Callable[[str], Response]):
    """Tests that DELETE /projects/{project_id} removes the .sap file."""
    create_response = create_project("to_be_removed")
    list_response = client.get("/projects")
    assert [create_response.json()] == list_response.json()["projects"]
    client.delete(create_response.json()["name"])
    list_response = client.get("/projects")
    assert not list_response.json()["projects"]


def test_project_delete_removes_project_directory(
    projects_path: Path,
    client: TestClient,
    create_project: Callable[[str], Response],
):
    create_response = create_project("to_be_removed")
    project_dir = projects_path / create_response.json()["name"].replace("projects/", "")
    project_dir.mkdir(exist_ok=True, parents=True)
    my_file = project_dir / "myfile.txt"
    my_file.write_bytes(b"hello world")
    client.delete(create_response.json()["name"])
    assert not project_dir.exists()


@pytest.fixture
def create_file(request: pytest.FixtureRequest, tmp_path: Path) -> Generator[Path, None, None]:
    filepath: str = str(request.param[0])  # type: ignore
    content: str = str(request.param[1])  # type: ignore
    myfile = tmp_path / filepath
    myfile.parent.mkdir(exist_ok=True, parents=True)
    myfile.write_text(content)
    yield myfile
    myfile.unlink()


def test_import_project_with_incompatible_field_is_prohibited(
    incompatible_minimal_project: Path,
    client: TestClient,
):
    """Tests that Glow fails to import a project that contains a field with an incompatible type."""
    with incompatible_minimal_project.open("rb") as f:
        response = client.post(
            "/projects:import",
            files={"safx_file": f},
            data={"display_name": "my_project"},
        )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert (
        "1 validation error for ProjectModel[MinimalSolution]\nsolution.steps.minimal_step.name\n"
        "  Input should be a valid string"
    ) in response.json()["detail"]


def test_import_project_with_less_field_is_allowed(
    compatible_minimal_project: Path,
    client: TestClient,
    settings: Settings,
):
    """Tests that Glow is able to import a project that contains less field than in the solution."""
    settings.glow_enable_automatic_project_migration = True
    with compatible_minimal_project.open("rb") as f:
        import_project_response = client.post(
            "/projects:import",
            files={"safx_file": f},
            data={"display_name": "my_project"},
        )
    step = client.get(f"{import_project_response.json()['name']}/steps/minimal-step").json()
    assert step["x"] == 99


def test_projects_directory_can_be_customized_by_settings(
    client: TestClient,
    create_project: Callable[[str], Response],
    tmp_path: Path,
    settings: Settings,
):
    """Tests that setting "GLOW_PROJECT_FILES_DIRECTORY" puts glow and project files in this directory."""
    custom_projects_directory = tmp_path / "custom_projects_directory"
    custom_projects_directory.mkdir(parents=True, exist_ok=True)
    settings.glow_project_files_directory = custom_projects_directory
    client.app.dependency_overrides[get_settings] = lambda: settings  # type: ignore
    response = create_project("x")
    project_name = response.json()["name"]
    response = client.post(f"{project_name}/steps/minimal-step:create-hello-file")
    response.raise_for_status()

    actual_file = [
        str(i.relative_to(custom_projects_directory).as_posix())
        for i in custom_projects_directory.rglob("*")
        if i.is_file()
    ][0]
    assert re.match(f"{project_name.split('/')[-1]}/bdm/method_\\w{{8}}/hello.txt", actual_file)


async def test_projects_database_can_be_customized_by_settings(
    client: TestClient,
    create_project: Callable[[str], Response],
    get_temp_sqlite_database: Callable[[], Path],
    get_temp_postgresql_database: Callable[[], PostgresqlServerInfo],
    settings: Settings,
):
    """Tests that setting "GLOW_DATABASE_LOCATION" puts glow database in this location."""
    if settings.glow_database_type == DatabaseType.Sqlite:
        custom_database_location = get_temp_sqlite_database()
    else:
        custom_database_location = get_temp_postgresql_database().url
    custom_settings = settings.model_copy()
    custom_settings.glow_database_location = custom_database_location
    client.app.dependency_overrides[get_settings] = lambda: custom_settings  # type: ignore

    create_project("_custom_project_")

    if settings.glow_database_type == DatabaseType.Sqlite:
        with sqlite3.connect(custom_database_location) as conn:  # type: ignore
            assert "_custom_project_" in conn.execute("SELECT project_display_name FROM projects").fetchone()[0]
    else:
        conn = await asyncpg.connect(custom_database_location.unicode_string())  # type: ignore
        try:
            result = await conn.fetchrow("SELECT project_display_name FROM projects")  # type: ignore
            assert result["project_display_name"] == "_custom_project_"
        finally:
            conn.close()  # type: ignore
