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

from ansys.iam.oidc import OidcDependency, UserInfo
from ansys.saf.glow._config.const import DatabaseType
from ansys.saf.glow._server.dependencies import get_oidc_client, oidc_scheme
import tests.mocks.solutions.user_info as user_info
from tests.unit.routes.conftest import ProjectFixture

pytestmark = pytest.mark.parametrize(
    "mock_module_settings",
    [{"glow_database_type": DatabaseType.Sqlite}, {"glow_database_type": DatabaseType.PostgreSql}],
    ids=["sqlite", "postgres"],
    indirect=True,
)
solution = user_info


class OidcClientMock:
    def get_user_info(
        self,
        access_token: str,  # pyright: ignore[reportUnusedParameter]
        fields: list[str] | None = None,  # pyright: ignore[reportUnusedParameter]
        from_issuer: bool = False,  # pyright: ignore[reportUnusedParameter]
    ) -> UserInfo:
        return UserInfo(name="admin", email="admin@glow.com", preferred_username="admin", middle_name="")


@pytest.fixture(autouse=True)
def override_oauth_scheme(project_fixture: ProjectFixture):
    """Override oidc_scheme dependencies to avoid querying the oidc metadata server."""
    project_fixture.client.app.dependency_overrides[oidc_scheme] = OidcDependency("", "", auto_error=False)  # type: ignore
    project_fixture.client.app.dependency_overrides[get_oidc_client] = lambda: OidcClientMock()  # type: ignore
    yield
    # reset the overrides
    project_fixture.client.app.dependency_overrides = {}  # type: ignore


@pytest.mark.parametrize("attribute", ["property", "method"])
def test_user_info_extracted_and_available_in_transaction(
    project_fixture: ProjectFixture,
    dummy_jwt_token: str,
    attribute: str,
):
    project_name = project_fixture.properties["name"]
    json_data = {"fields": ["name", "email", "preferred_username"]} if attribute == "method" else {}
    response = project_fixture.client.post(
        f"{project_name}/steps/a-step:get-user-info-with-{attribute}",
        headers={"Authorization": f"bearer {dummy_jwt_token}"},
        json=json_data,
    )
    response.raise_for_status()
    assert UserInfo.model_validate(response.json()) == UserInfo(
        name="admin",
        email="admin@glow.com",
        preferred_username="admin",
    )


@pytest.mark.parametrize("attribute", ["property", "method"])
def test_token_with_partial_content_is_available_in_transaction_through_property(
    project_fixture: ProjectFixture,
    dummy_jwt_token_with_partial_info: str,
    attribute: str,
):
    project_name = project_fixture.properties["name"]
    json_data = {"fields": ["name", "email", "preferred_username"]} if attribute == "method" else {}
    response = project_fixture.client.post(
        f"{project_name}/steps/a-step:get-user-info-with-{attribute}",
        headers={"Authorization": f"bearer {dummy_jwt_token_with_partial_info}"},
        json=json_data,
    )
    response.raise_for_status()
    assert UserInfo.model_validate(response.json()) == UserInfo(
        name="admin",
        preferred_username="admin",
        email="admin@glow.com",
    )


@pytest.mark.parametrize("attribute", ["property", "method"])
def test_empty_user_info_available_through_property_if_request_doesnt_have_bearer_token(
    project_fixture: ProjectFixture,
    attribute: str,
):
    project_fixture.client.app.dependency_overrides[oidc_scheme] = OidcDependency("", "", auto_error=False)  # type: ignore
    project_name = project_fixture.properties["name"]
    json_data = {"fields": ["name", "email", "preferred_username"]} if attribute == "method" else {}
    response = project_fixture.client.post(
        f"{project_name}/steps/a-step:get-user-info-with-{attribute}",
        json=json_data,
    )
    response.raise_for_status()
    assert UserInfo.model_validate(response.json()) == UserInfo()
