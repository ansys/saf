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

import pytest

from ansys.bdm.api import IStorageScope
from ansys.saf.glow._bdm.multiplexor import BdmMultiplexor, SafMultiplexorStorageScopeFactory
from ansys.saf.glow._bdm.storage_contexts import METHOD_CONTEXT
from ansys.saf.glow._config.const import (
    GLOW_HPS_HOST,
    GLOW_HPS_PASSWORD,
    GLOW_HPS_PORT,
    GLOW_HPS_USERNAME,
)
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.blob_managers import HpsBlobManager
from ansys.saf.glow._executor.local import transaction_local
from ansys.saf.glow._hps_auth.hps_authenticator import DesktopHpsAuthenticator
from ansys.saf.glow._hps_auth.ihps_authenticator import IHpsAuthenticator


@pytest.fixture(scope="class")
def multiplexor(
    hps_port: int | None,
    tmp_path_factory: pytest.TempPathFactory,
    monkeyclass: pytest.MonkeyPatch,
) -> Generator[IStorageScope]:
    monkeyclass.setenv(GLOW_HPS_HOST, "localhost")
    monkeyclass.setenv(GLOW_HPS_PORT, str(hps_port))
    monkeyclass.setenv(GLOW_HPS_USERNAME, "repadmin")
    monkeyclass.setenv(GLOW_HPS_PASSWORD, "repadmin")

    settings = Settings(glow_solution_definition="tests.mocks.solution_with_hps_python_script.hps_parametric_study")
    multiplexor_scope_factory = SafMultiplexorStorageScopeFactory(
        project_files_dir=str(tmp_path_factory.getbasetemp()),
        project_id="project_id",
        settings=settings,
    )
    multiplexor_scope_factory.with_hps_storage_scope(
        access_token="",
    )
    with multiplexor_scope_factory.create_storage_scope(
        METHOD_CONTEXT,
    ) as multiplexor:
        yield multiplexor


@pytest.fixture(scope="class")
def hps_blob_manager(multiplexor: BdmMultiplexor) -> HpsBlobManager:
    return HpsBlobManager(multiplexor)


@pytest.fixture(scope="class")
def hps_authentication(monkeyclass: pytest.MonkeyPatch, hps_blob_manager: HpsBlobManager) -> IHpsAuthenticator:
    settings = Settings(glow_solution_definition="TEST")
    hps_authenticator = DesktopHpsAuthenticator(
        "http://localhost:5432/",  # fake url, we are going to use user/pwd
        client_id=settings.glow_hps_client_id,
        glow_hps_username=settings.glow_hps_username,
        glow_hps_password=settings.glow_hps_password,
    )
    monkeyclass.setattr(transaction_local, "settings", settings, raising=False)
    monkeyclass.setattr(transaction_local, "hps_blob_manager", hps_blob_manager, raising=False)
    return hps_authenticator


@pytest.fixture(scope="class")
def hps_auth_for_custom_url(monkeyclass: pytest.MonkeyPatch, hps_blob_manager: HpsBlobManager):
    monkeyclass.delenv(GLOW_HPS_HOST, raising=False)
    monkeyclass.delenv(GLOW_HPS_PORT, raising=False)
    monkeyclass.setenv(GLOW_HPS_USERNAME, "repadmin")
    monkeyclass.setenv(GLOW_HPS_PASSWORD, "repadmin")
    settings = Settings(glow_solution_definition="TEST")
    hps_authenticator = DesktopHpsAuthenticator(
        "http://localhost:5432/",  # fake url, we are going to use user/pwd
        client_id=settings.glow_hps_client_id,
        glow_hps_username=settings.glow_hps_username,
        glow_hps_password=settings.glow_hps_password,
    )
    monkeyclass.setattr(transaction_local, "settings", settings, raising=False)
    monkeyclass.setattr(transaction_local, "hps_authenticator", hps_authenticator, raising=False)
    monkeyclass.setattr(transaction_local, "hps_blob_manager", hps_blob_manager, raising=False)
    return
