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

import gc
import logging
import os
import time
from unittest import mock

import httpx2
import pytest
from pytest_mock.plugin import MockerFixture

from ansys.saf.glow._config.const import (
    DEFAULT_HPS_CLIENT_CACHE_TTL_SECONDS,
    GLOW_HPS_CLIENT_ID,
    GLOW_HPS_PASSWORD,
    GLOW_HPS_USERNAME,
    TEST_HPS_CLIENT_CACHE_TTL_SECONDS,
    Deployment,
)
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._hps_auth.hps_authentication_type import HpsAuthenticationType
from ansys.saf.glow._hps_auth.hps_authenticator import (
    CachedClient,
    CachedClients,
    DesktopHpsAuthenticator,
    NullHpsAuthenticator,
    OnPremHpsAuthenticator,
    create_hps_authenticator,
)
from ansys.saf.glow._hps_auth.ihps_authenticator import IHpsAuthenticator
from ansys.saf.glow._server.exceptions import InternalError


@pytest.fixture(autouse=True)
def clean_env():
    # End-to-end tests might set values for environment variables such as GLOW_HPS_USERNAME, GLOW_HPS_USERNAME,
    # GLOW_HPS_CLIENT_ID... and interfere with the following tests. Thus, we clean os.environ between tests.
    existing_glow_env_vars = [env_var for env_var in os.environ if env_var.startswith("GLOW_")]
    for env_var in existing_glow_env_vars:
        os.environ.pop(env_var)
    with mock.patch.dict(os.environ, os.environ.copy()):
        yield


def test_hps_authentication_type_desktop_keycloak_default_values(mocker: MockerFixture):
    hps_authenticator = DesktopHpsAuthenticator(glow_api_url="127.0.0.1:5432", client_id="rep-jms-web")
    assert hps_authenticator.auth_type == HpsAuthenticationType.KEYCLOAK_INTERACTIVE

    mocked_hps_client = mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)
    with (
        mocker.patch.object(
            httpx2.Client,
            "get",
            return_value=httpx2.Response(
                200,
                json={"access_token": "fake_access_token", "refresh_token": "fake_refresh_token"},
            ),
        ),
        mocker.patch.object(httpx2.Response, "raise_for_status"),
        hps_authenticator.get_hps_client("https://localhost:8443/hps"),
    ):
        ...
    mocked_hps_client.assert_called_once_with(
        url="https://localhost:8443/hps",
        client_id="rep-jms-web",
        refresh_token="fake_refresh_token",
    )


def test_hps_authentication_type_desktop_keycloak_custom_values(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
):
    monkeypatch.setenv(GLOW_HPS_CLIENT_ID, "custom-rep-jms-web")
    hps_authenticator = DesktopHpsAuthenticator(glow_api_url="127.0.0.1:5432", client_id="custom-rep-jms-web")
    assert hps_authenticator.auth_type == HpsAuthenticationType.KEYCLOAK_INTERACTIVE

    mocked_hps_client = mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)
    with (
        mocker.patch.object(
            httpx2.Client,
            "get",
            return_value=httpx2.Response(
                200,
                json={"access_token": "fake_access_token", "refresh_token": "fake_refresh_token"},
            ),
        ),
        mocker.patch.object(httpx2.Response, "raise_for_status"),
        hps_authenticator.get_hps_client("https://localhost:8443/hps"),
    ):
        ...
    mocked_hps_client.assert_called_once_with(
        url="https://localhost:8443/hps",
        client_id="custom-rep-jms-web",
        refresh_token="fake_refresh_token",
    )


def test_hps_authentication_type_desktop_username_password(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
):
    monkeypatch.setenv(GLOW_HPS_USERNAME, "repadmin")
    monkeypatch.setenv(GLOW_HPS_PASSWORD, "repadmin")
    settings = Settings(glow_solution_definition="TEST")
    hps_authenticator = DesktopHpsAuthenticator(
        glow_api_url="127.0.0.1:5432",
        client_id="rep-jms-web",
        glow_hps_username=settings.glow_hps_username,
        glow_hps_password=settings.glow_hps_password,
    )
    assert hps_authenticator.auth_type == HpsAuthenticationType.USER_PASSWORD

    monkeypatch.setenv(GLOW_HPS_CLIENT_ID, "custom-rep-jms-web")
    hps_authenticator = DesktopHpsAuthenticator(
        glow_api_url="127.0.0.1:5432",
        client_id="custom-rep-jms-web",
        glow_hps_username=settings.glow_hps_username,
        glow_hps_password=settings.glow_hps_password,
    )
    assert hps_authenticator.auth_type == HpsAuthenticationType.USER_PASSWORD

    mocked_hps_client = mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)
    with hps_authenticator.get_hps_client("https://localhost:8443/hps"):
        ...
    mocked_hps_client.assert_called_once_with(
        url="https://localhost:8443/hps",
        username="repadmin",
        password="repadmin",
    )


def test_hps_authentication_type_onprem_keycloak():
    authenticator = OnPremHpsAuthenticator()
    with pytest.raises(  # noqa: SIM117
        RuntimeError,
        match="On-prem HPS authentication requires either token or username and password authentication.",
    ):
        with authenticator.get_hps_client("https://localhost:8443/hps"):
            ...


def test_hps_authentication_type_onprem_token_no_client_or_auth_issuer_url(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
):
    hps_authenticator = OnPremHpsAuthenticator(token="fake_access_token")
    assert hps_authenticator.auth_type == HpsAuthenticationType.TOKEN_EXCHANGE

    monkeypatch.setenv(GLOW_HPS_USERNAME, "repadmin")
    monkeypatch.setenv(GLOW_HPS_PASSWORD, "repadmin")
    hps_authenticator = OnPremHpsAuthenticator(token="fake_access_token")
    assert hps_authenticator.auth_type == HpsAuthenticationType.TOKEN_EXCHANGE

    mocked_hps_client = mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)
    error_msg = (
        "GLOW_AUTH_CLIENT_ID and GLOW_AUTH_ISSUER_URL must be provided for token exchange authentication with HPS."
    )
    with pytest.raises(ValueError, match=error_msg):  # noqa: SIM117
        with hps_authenticator.get_hps_client("https://localhost:8443/hps"):
            ...
    mocked_hps_client.assert_not_called()


def test_hps_authentication_type_onprem_token_with_token_exchange(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
):
    hps_authenticator = OnPremHpsAuthenticator(token="fake_access_token")
    assert hps_authenticator.auth_type == HpsAuthenticationType.TOKEN_EXCHANGE

    monkeypatch.setenv(GLOW_HPS_USERNAME, "repadmin")
    monkeypatch.setenv(GLOW_HPS_PASSWORD, "repadmin")
    hps_authenticator = OnPremHpsAuthenticator(
        token="fake_access_token",
        client_id="some_client_id",
        glow_auth_issuer_url="some_issuer_url",
    )
    assert hps_authenticator.auth_type == HpsAuthenticationType.TOKEN_EXCHANGE

    mocked_hps_client = mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)
    with (
        mocker.patch(
            "ansys.saf.glow._hps_auth.hps_authenticator.OnPremHpsAuthenticator._get_username_from_access_token",
        ),
        mocker.patch(
            "ansys.saf.glow._hps_auth.hps_authenticator.OnPremHpsAuthenticator._request_action_token_url",
            return_value="https://fake_auth_url",
        ),
        mocker.patch(
            "ansys.saf.glow._hps_auth.hps_authenticator.OnPremHpsAuthenticator._get_access_and_refresh_tokens",
            return_value={"access_token": "hps_fake_access_token", "refresh_token": "hps_fake_refresh_token"},
        ),
        hps_authenticator.get_hps_client(
            "https://localhost:8443/hps",
        ),
    ):
        ...
    mocked_hps_client.assert_called_once_with(
        url="https://localhost:8443/hps",
        access_token="hps_fake_access_token",
        refresh_token="hps_fake_refresh_token",
    )


def test_hps_authentication_type_onprem_token_with_service_account_action_token(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
):
    """When action-token client credentials are configured, the service account token, not the
    user's access token, should be used to request the action token (platform flow)."""
    monkeypatch.setenv(GLOW_HPS_USERNAME, "repadmin")
    monkeypatch.setenv(GLOW_HPS_PASSWORD, "repadmin")
    hps_authenticator = OnPremHpsAuthenticator(
        token="fake_access_token",
        client_id="some_client_id",
        glow_auth_issuer_url="some_issuer_url",
        glow_auth_service_account_client_id="action-token-client",
        glow_auth_service_account_client_secret="action-token-secret",
    )
    assert hps_authenticator.auth_type == HpsAuthenticationType.TOKEN_EXCHANGE

    mocked_hps_client = mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)
    mocked_service_account_token = mocker.patch(
        "ansys.saf.glow._hps_auth.hps_authenticator.OnPremHpsAuthenticator._get_service_account_access_token",
        return_value="service_account_access_token",
    )
    mocked_request_action_token_url = mocker.patch(
        "ansys.saf.glow._hps_auth.hps_authenticator.OnPremHpsAuthenticator._request_action_token_url",
        return_value="https://fake_auth_url",
    )
    with (
        mocker.patch(
            "ansys.saf.glow._hps_auth.hps_authenticator.OnPremHpsAuthenticator._get_username_from_access_token",
        ),
        mocker.patch(
            "ansys.saf.glow._hps_auth.hps_authenticator.OnPremHpsAuthenticator._get_access_and_refresh_tokens",
            return_value={"access_token": "hps_fake_access_token", "refresh_token": "hps_fake_refresh_token"},
        ),
        hps_authenticator.get_hps_client(
            "https://localhost:8443/hps",
        ),
    ):
        ...
    mocked_service_account_token.assert_called_once_with(
        issuer_url="some_issuer_url",
        service_account_client_id="action-token-client",
        service_account_client_secret="action-token-secret",
    )
    # THEN: the service account token, not the user's access token, is passed on to request the action token.
    assert mocked_request_action_token_url.call_args.kwargs["access_token"] == "service_account_access_token"
    mocked_hps_client.assert_called_once_with(
        url="https://localhost:8443/hps",
        access_token="hps_fake_access_token",
        refresh_token="hps_fake_refresh_token",
    )


def test_get_service_account_access_token(mocker: MockerFixture):
    hps_authenticator = OnPremHpsAuthenticator()
    mocked_post = mocker.patch.object(
        httpx2.Client,
        "post",
        return_value=httpx2.Response(
            200,
            json={"access_token": "service_account_access_token"},
            request=httpx2.Request("POST", "/"),
        ),
    )
    mocker.patch.object(httpx2.Response, "raise_for_status")

    token = hps_authenticator._get_service_account_access_token(  # pyright: ignore[reportPrivateUsage]
        issuer_url="https://issuer.example.com/auth/",
        service_account_client_id="action-token-client",
        service_account_client_secret="action-token-secret",
    )

    assert token == "service_account_access_token"
    mocked_post.assert_called_once_with(
        "https://issuer.example.com/auth/protocol/openid-connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "action-token-client",
            "client_secret": "action-token-secret",
        },
    )


def test_hps_authentication_type_onprem_username_password(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
):
    monkeypatch.setenv(GLOW_HPS_USERNAME, "repadmin")
    monkeypatch.setenv(GLOW_HPS_PASSWORD, "repadmin")
    settings = Settings(glow_solution_definition="TEST")
    hps_authenticator = OnPremHpsAuthenticator(
        glow_hps_username=settings.glow_hps_username,
        glow_hps_password=settings.glow_hps_password,
    )
    assert hps_authenticator.auth_type == HpsAuthenticationType.USER_PASSWORD

    mocked_hps_client = mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)
    with hps_authenticator.get_hps_client("https://localhost:8443/hps"):
        ...
    mocked_hps_client.assert_called_once_with(
        url="https://localhost:8443/hps",
        username="repadmin",
        password="repadmin",
    )


def test_hps_auth_custom_url_user_pwd(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
):
    monkeypatch.setenv(GLOW_HPS_USERNAME, "repadmin")
    monkeypatch.setenv(GLOW_HPS_PASSWORD, "repadmin")
    settings = Settings(glow_solution_definition="TEST")
    hps_authenticator = DesktopHpsAuthenticator(
        glow_api_url="http://localhost:5432",
        client_id="rep-jms-web",
        glow_hps_username=settings.glow_hps_username,
        glow_hps_password=settings.glow_hps_password,
    )
    mocked_hps_client = mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)
    with hps_authenticator.get_hps_client(hps_server_url="https://custom_url:1234"):
        ...
    mocked_hps_client.assert_called_once_with(
        url="https://custom_url:1234",
        username="repadmin",
        password="repadmin",
    )


def test_hps_server_url_on_desktop_interactive_auth(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
):
    monkeypatch.delenv(GLOW_HPS_USERNAME, raising=False)
    monkeypatch.delenv(GLOW_HPS_PASSWORD, raising=False)
    hps_authenticator = DesktopHpsAuthenticator(
        glow_api_url="http://localhost:5432",
        client_id="rep-jms-web",
    )
    mocked_hps_client = mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)
    with mocker.patch.object(
        httpx2.Client,
        "get",
        return_value=httpx2.Response(
            200,
            json={"access_token": "test_access", "refresh_token": "test_refresh"},
            request=httpx2.Request("GET", "/"),
        ),
    ):
        with hps_authenticator.get_hps_client(hps_server_url="https://custom_url:1234"):
            ...
        mocked_hps_client.assert_called_once_with(
            url="https://custom_url:1234",
            client_id="rep-jms-web",
            refresh_token="test_refresh",
        )


def test_cached_hps_client():
    mock_client = mock.Mock()
    # Create client with timestamp 30 seconds ago
    old_timestamp = time.time() - 30.0
    cached_client = CachedClient(mock_client, old_timestamp)

    # WHEN: using TTL of 20 seconds
    assert cached_client.is_expired(cache_ttl_seconds=20.0)
    # WHEN: using TTL of 40 seconds
    assert not cached_client.is_expired(cache_ttl_seconds=40.0)


def test_cached_hps_client_close_releases_resources():
    mock_client = mock.Mock()
    cached_client = CachedClient(mock_client, time.time())

    cached_client.close()

    # The refresh thread pins the client and the data transfer client runs as a child process.
    mock_client._stop_event.set.assert_called_once_with()
    mock_client._token_refresh_thread.join.assert_called_once_with(timeout=1.0)
    mock_client._dt_client.stop.assert_called_once_with()
    mock_client.session.close.assert_called_once_with()


def test_cached_hps_client_close_without_background_resources():
    mock_client = mock.Mock()
    mock_client._dt_client = None
    mock_client._stop_event = None
    mock_client._token_refresh_thread = None
    cached_client = CachedClient(mock_client, time.time())

    cached_client.close()

    mock_client.session.close.assert_called_once_with()


def test_cached_hps_client_close_survives_failures(caplog: pytest.LogCaptureFixture):
    mock_client = mock.Mock()
    mock_client._stop_event.set.side_effect = RuntimeError("signal failed")
    mock_client._token_refresh_thread.join.side_effect = RuntimeError("join failed")
    mock_client._dt_client.stop.side_effect = RuntimeError("data transfer stop failed")
    mock_client.session.close.side_effect = RuntimeError("session close failed")
    cached_client = CachedClient(mock_client, time.time())

    # A failure in one cleanup step must not prevent later steps from running.
    with caplog.at_level(logging.WARNING):
        cached_client.close()

    mock_client._stop_event.set.assert_called_once_with()
    mock_client._token_refresh_thread.join.assert_called_once_with(timeout=1.0)
    mock_client._dt_client.stop.assert_called_once_with()
    mock_client.session.close.assert_called_once_with()
    assert caplog.messages == [
        "Failed to signal the HPS token refresh thread to stop.",
        "Failed to join the HPS token refresh thread.",
        "Failed to stop the HPS data transfer client.",
        "Failed to close the HPS client session.",
    ]


@pytest.mark.parametrize("authenticator_type", [DesktopHpsAuthenticator, OnPremHpsAuthenticator])
def test_authenticator_closes_client_it_replaces(
    authenticator_type: type[IHpsAuthenticator],
    mocker: MockerFixture,
):
    mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)
    spy_close = mocker.spy(CachedClient, "close")

    init_args = {"glow_hps_username": "user", "glow_hps_password": "pass"}
    if authenticator_type is DesktopHpsAuthenticator:
        init_args["glow_api_url"] = "127.0.0.1:5432"
        init_args["client_id"] = "rep-jms-web"
    hps_authenticator = authenticator_type(**init_args)

    hps_url = "https://localhost:8443/hps"
    current_time = time.time()

    with mocker.patch("time.time", return_value=current_time), hps_authenticator.get_hps_client(hps_url):
        pass
    # WHEN: the cached client expires and is replaced
    with mocker.patch("time.time", return_value=current_time + 70), hps_authenticator.get_hps_client(hps_url):
        pass

    # THEN: only the replaced client is released
    assert spy_close.call_count == 1


@pytest.mark.parametrize("authenticator_type", [DesktopHpsAuthenticator, OnPremHpsAuthenticator])
def test_authenticator_does_not_support_concurrent_client_contexts(
    authenticator_type: type[IHpsAuthenticator],
    mocker: MockerFixture,
):
    mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)
    spy_close = mocker.spy(CachedClient, "close")

    init_args = {"glow_hps_username": "user", "glow_hps_password": "pass"}
    if authenticator_type is DesktopHpsAuthenticator:
        init_args["glow_api_url"] = "127.0.0.1:5432"
        init_args["client_id"] = "rep-jms-web"
    hps_authenticator = authenticator_type(**init_args)

    hps_url = "https://localhost:8443/hps"
    first_context = hps_authenticator.get_hps_client(hps_url)  # pyright: ignore[reportUnknownVariableType]
    first_context.__enter__()

    # A second request for the expired URL replaces and closes the client still yielded above.
    with mocker.patch("time.time", return_value=time.time() + 70), hps_authenticator.get_hps_client(hps_url):
        pass

    # Concurrent use is unsupported; callers must not overlap these contexts.
    assert spy_close.call_count == 1
    first_context.__exit__(None, None, None)


@pytest.mark.parametrize("authenticator_type", [DesktopHpsAuthenticator, OnPremHpsAuthenticator])
def test_authenticator_does_not_close_reused_client(
    authenticator_type: type[IHpsAuthenticator],
    mocker: MockerFixture,
):
    mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)
    spy_close = mocker.spy(CachedClient, "close")

    init_args = {"glow_hps_username": "user", "glow_hps_password": "pass"}
    if authenticator_type is DesktopHpsAuthenticator:
        init_args["glow_api_url"] = "127.0.0.1:5432"
        init_args["client_id"] = "rep-jms-web"
    hps_authenticator = authenticator_type(**init_args)

    # WHEN: the cached client is still valid and gets reused
    hps_url = "https://localhost:8443/hps"
    with hps_authenticator.get_hps_client(hps_url):
        pass
    with hps_authenticator.get_hps_client(hps_url):
        pass

    # THEN: nothing is released, the client is still in use
    spy_close.assert_not_called()


@pytest.mark.parametrize("authenticator_type", [DesktopHpsAuthenticator, OnPremHpsAuthenticator])
def test_authenticator_does_not_close_clients_of_other_urls(
    authenticator_type: type[IHpsAuthenticator],
    mocker: MockerFixture,
):
    mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)
    spy_close = mocker.spy(CachedClient, "close")

    init_args = {"glow_hps_username": "user", "glow_hps_password": "pass"}
    if authenticator_type is DesktopHpsAuthenticator:
        init_args["glow_api_url"] = "127.0.0.1:5432"
        init_args["client_id"] = "rep-jms-web"
    hps_authenticator = authenticator_type(**init_args)

    # WHEN: caching clients for two different servers
    with hps_authenticator.get_hps_client("https://localhost:8443/hps"):
        pass
    with hps_authenticator.get_hps_client("https://remote:8443/hps"):
        pass

    # THEN: neither entry replaces the other, so neither is released
    spy_close.assert_not_called()


def test_cached_clients_close_releases_every_entry():
    cache = CachedClients()
    first, second = mock.Mock(), mock.Mock()
    cache.set("https://localhost:8443/hps", first)  # pyright: ignore[reportUnknownMemberType]
    cache.set("https://remote:8443/hps", second)  # pyright: ignore[reportUnknownMemberType]

    cache.close()

    first._dt_client.stop.assert_called_once_with()
    second._dt_client.stop.assert_called_once_with()
    assert cache.get("https://localhost:8443/hps", 60.0) is None  # pyright: ignore[reportUnknownMemberType]
    assert cache.get("https://remote:8443/hps", 60.0) is None  # pyright: ignore[reportUnknownMemberType]


def test_cached_clients_close_is_idempotent():
    cache = CachedClients()
    client = mock.Mock()
    cache.set("https://localhost:8443/hps", client)  # pyright: ignore[reportUnknownMemberType]

    cache.close()
    cache.close()

    client._dt_client.stop.assert_called_once_with()


@pytest.mark.parametrize("authenticator_type", [DesktopHpsAuthenticator, OnPremHpsAuthenticator])
def test_authenticator_releases_cached_clients_when_collected(
    authenticator_type: type[IHpsAuthenticator],
    mocker: MockerFixture,
):
    mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)
    spy_close = mocker.spy(CachedClient, "close")

    init_args = {"glow_hps_username": "user", "glow_hps_password": "pass"}
    if authenticator_type is DesktopHpsAuthenticator:
        init_args["glow_api_url"] = "127.0.0.1:5432"
        init_args["client_id"] = "rep-jms-web"
    hps_authenticator = authenticator_type(**init_args)

    with hps_authenticator.get_hps_client("https://localhost:8443/hps"):
        pass
    spy_close.assert_not_called()

    # WHEN: the authenticator goes out of scope, as it does at the end of a request
    del hps_authenticator
    gc.collect()

    # THEN: the client it cached is released rather than left to the process lifetime
    assert spy_close.call_count == 1


@pytest.mark.parametrize("authenticator_type", [DesktopHpsAuthenticator, OnPremHpsAuthenticator])
def test_authenticator_caches_clients(authenticator_type: type[IHpsAuthenticator], mocker: MockerFixture):
    mocked_hps_client_class = mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)

    init_args = {"glow_hps_username": "user", "glow_hps_password": "pass"}
    if authenticator_type is DesktopHpsAuthenticator:
        init_args["glow_api_url"] = "127.0.0.1:5432"
        init_args["client_id"] = "rep-jms-web"
    hps_authenticator = authenticator_type(**init_args)

    # WHEN: creating client for same URL twice
    hps_url = "https://localhost:8443/hps"
    with hps_authenticator.get_hps_client(hps_url):
        pass
    with hps_authenticator.get_hps_client(hps_url):
        pass

    # THEN: Client constructor should only be called once due to caching
    mocked_hps_client_class.assert_called_once_with(url=hps_url, username="user", password="pass")


@pytest.mark.parametrize("ttl_value", [None, "5.0"])
@pytest.mark.parametrize("authenticator_type", [DesktopHpsAuthenticator, OnPremHpsAuthenticator])
def test_authenticator_ttl_cache_configurable(
    ttl_value: None | str,
    authenticator_type: type[IHpsAuthenticator],
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
):
    if ttl_value:
        monkeypatch.setenv(TEST_HPS_CLIENT_CACHE_TTL_SECONDS, ttl_value)
    else:
        monkeypatch.delenv(TEST_HPS_CLIENT_CACHE_TTL_SECONDS, raising=False)

    mocked_hps_client_class = mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)
    spy_cache_client_expired = mocker.spy(CachedClient, "is_expired")

    init_args = {"glow_hps_username": "user", "glow_hps_password": "pass"}
    if authenticator_type is DesktopHpsAuthenticator:
        init_args["glow_api_url"] = "127.0.0.1:5432"
        init_args["client_id"] = "rep-jms-web"
    hps_authenticator = authenticator_type(**init_args)

    # WHEN: creating client for same URL twice
    hps_url = "https://localhost:8443/hps"
    with hps_authenticator.get_hps_client(hps_url):
        pass
    with hps_authenticator.get_hps_client(hps_url):
        pass

    # Expiration was checked with the right TTL value
    spy_cache_client_expired.assert_called_once()
    assert spy_cache_client_expired.call_args[0][1] == (
        float(ttl_value) if ttl_value else DEFAULT_HPS_CLIENT_CACHE_TTL_SECONDS
    )

    # THEN: Client constructor should only be called once due to caching
    mocked_hps_client_class.assert_called_once_with(url=hps_url, username="user", password="pass")


@pytest.mark.parametrize("authenticator_type", [DesktopHpsAuthenticator, OnPremHpsAuthenticator])
def test_desktop_authenticator_creates_separate_clients_for_different_urls(
    authenticator_type: type[IHpsAuthenticator],
    mocker: MockerFixture,
):
    mocked_hps_client_class = mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)

    init_args = {"glow_hps_username": "user", "glow_hps_password": "pass"}
    if authenticator_type is DesktopHpsAuthenticator:
        init_args["glow_api_url"] = "127.0.0.1:5432"
        init_args["client_id"] = "rep-jms-web"
    hps_authenticator = authenticator_type(**init_args)

    # WHEN: creating clients for different URLs
    hps_url1 = "https://localhost:8443/hps"
    hps_url2 = "https://remote:8443/hps"
    with hps_authenticator.get_hps_client(hps_url1):
        pass
    with hps_authenticator.get_hps_client(hps_url2):
        pass

    # THEN: Client constructor should be called twice for different URLs
    assert mocked_hps_client_class.call_count == 2
    mocked_hps_client_class.assert_any_call(url=hps_url1, username="user", password="pass")
    mocked_hps_client_class.assert_any_call(url=hps_url2, username="user", password="pass")


@pytest.mark.parametrize("authenticator_type", [DesktopHpsAuthenticator, OnPremHpsAuthenticator])
def test_desktop_authenticator_cache_expiration_creates_new_client(
    authenticator_type: type[IHpsAuthenticator],
    mocker: MockerFixture,
):
    mocked_hps_client_class = mocker.patch("ansys.hps.client.client.Client.__init__", return_value=None)

    init_args = {"glow_hps_username": "user", "glow_hps_password": "pass"}
    if authenticator_type is DesktopHpsAuthenticator:
        init_args["glow_api_url"] = "127.0.0.1:5432"
        init_args["client_id"] = "rep-jms-web"
    hps_authenticator = authenticator_type(**init_args)

    hps_url = "https://localhost:8443/hps"
    current_time = time.time()

    # WHEN: creating client first time
    with mocker.patch("time.time", return_value=current_time), hps_authenticator.get_hps_client(hps_url):
        pass

    # WHEN: creating client again, 70 seconds later, passing the default 60 seconds TTL
    with mocker.patch("time.time", return_value=current_time + 70), hps_authenticator.get_hps_client(hps_url):
        pass

    # THEN: Client constructor should be called twice due to expiration
    assert mocked_hps_client_class.call_count == 2


def test_create_hps_authenticator_desktop_deployment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", "TEST")
    settings = Settings(
        glow_deployment=Deployment.Desktop,
        glow_api_port=5432,
        glow_hps_username="test-user",
        glow_hps_password="test-pass",
    )

    # WHEN: creating authenticator for desktop deployment
    authenticator = create_hps_authenticator(settings)

    # THEN: should return DesktopHpsAuthenticator
    assert isinstance(authenticator, DesktopHpsAuthenticator)
    # Verify behavior by checking auth type
    assert authenticator.auth_type == HpsAuthenticationType.USER_PASSWORD


def test_create_hps_authenticator_desktop_deployment_no_credentials(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", "TEST")
    settings = Settings(
        glow_deployment=Deployment.Desktop,
        glow_api_port=5432,
    )

    # WHEN: creating authenticator for desktop deployment
    authenticator = create_hps_authenticator(settings)

    # THEN: should return DesktopHpsAuthenticator
    assert isinstance(authenticator, DesktopHpsAuthenticator)
    # Verify behavior by checking auth type
    assert authenticator.auth_type == HpsAuthenticationType.KEYCLOAK_INTERACTIVE


def test_create_hps_authenticator_docker_compose_deployment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", "TEST")
    settings = Settings(
        glow_deployment=Deployment.DockerCompose,
        glow_hps_username="test-user",
        glow_hps_password="test-pass",
    )

    # WHEN: creating authenticator for docker-compose deployment
    authenticator = create_hps_authenticator(settings, access_token="test-token")

    # THEN: should return OnPremHpsAuthenticator
    assert isinstance(authenticator, OnPremHpsAuthenticator)
    # Verify behavior by checking auth type
    assert authenticator.auth_type == HpsAuthenticationType.TOKEN_EXCHANGE


def test_create_hps_authenticator_docker_compose_deployment_with_configured_service_account(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", "TEST")
    settings = Settings(
        glow_deployment=Deployment.DockerCompose,
        glow_hps_username="test-user",
        glow_hps_password="test-pass",
        glow_auth_service_account_client_id="action-token-client",
        glow_auth_service_account_client_secret="action-token-secret",
    )

    # WHEN: creating authenticator for docker-compose deployment with action token client credentials configured
    authenticator = create_hps_authenticator(settings, access_token="test-token")

    # THEN: should return OnPremHpsAuthenticator wired with the action token client credentials
    assert isinstance(authenticator, OnPremHpsAuthenticator)
    assert authenticator._service_account_client_id == "action-token-client"  # pyright: ignore[reportPrivateUsage]
    assert (
        authenticator._service_account_client_secret  # pyright: ignore[reportPrivateUsage]
        == "action-token-secret"
    )


def test_create_hps_authenticator_docker_compose_no_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", "TEST")
    settings = Settings(
        glow_deployment=Deployment.DockerCompose,
        glow_hps_username="test-user",
        glow_hps_password="test-pass",
    )

    # WHEN: creating authenticator without access token
    authenticator = create_hps_authenticator(settings)

    # THEN: should return OnPremHpsAuthenticator with empty token
    assert isinstance(authenticator, OnPremHpsAuthenticator)
    # Verify behavior by checking auth type
    assert authenticator.auth_type == HpsAuthenticationType.USER_PASSWORD


def test_create_hps_authenticator_unknown_deployment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", "TEST")
    settings = Settings(glow_deployment=Deployment.Unknown)

    # WHEN: creating authenticator for unknown deployment
    authenticator = create_hps_authenticator(settings)

    # THEN: should return NullHpsAuthenticator
    assert isinstance(authenticator, NullHpsAuthenticator)


def test_null_authenticator_raises_error_on_get_client():
    authenticator = NullHpsAuthenticator()

    # WHEN: trying to get HPS client
    with pytest.raises(InternalError, match="Unknown deployment type."):  # noqa: SIM117
        with authenticator.get_hps_client("https://localhost:8443/hps"):
            pass
