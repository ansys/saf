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

import logging
from pathlib import Path
import platform

import pytest
from pytest_mock import MockerFixture

from ansys.saf.glow._core.instance.iinstance_system import IProductInstanceSystemFactory
from ansys.saf.glow._core.instance.manager import JOB_DEFAULT_MAX_RUNNING_TIME
from ansys.saf.glow._utilities.ip_utilities import get_local_ip
from ansys.saf.testing.pim.process import PimProcess
from tests.integration.conftest import assert_instance, assert_instance_deleted, create_product_instance_system


@pytest.mark.parametrize("instance_system_type", [pytest.param("PIM", marks=pytest.mark.use_pim)], indirect=True)
@pytest.mark.parametrize("product_name", ["custom-grpc-product", "custom-http-product", "custom-tcp-product"])
class TestSecurePIMLightServer:
    def test_localhost_pim(
        self,
        product_name: str,
        product_instance_system_factory: IProductInstanceSystemFactory,
        product_instance_system_uri: str,
        session_pim: PimProcess,
        mocker: MockerFixture,
    ):
        if platform.system() == "Windows":
            assert session_pim.find_msg_in_output("Transport mode is: Wnua")
            assert session_pim.find_msg_in_output(f"Now listening on: http://127.0.0.1:{session_pim.port}")
        else:
            assert session_pim.find_msg_in_output("Transport mode is: Uds")
            assert session_pim.find_msg_in_output(f"Server will listen on UNIX socket: {session_pim.socket_path}")

        mock_logger_info = mocker.patch.object(logging.Logger, "info")
        product_instance_system = create_product_instance_system(
            product_instance_system_factory,
            product_instance_system_uri,
        )
        if platform.system() == "Windows":
            expected_msg = f"Connecting to PIM Light Server via 127.0.0.1:{session_pim.port} without credentials."
        else:
            expected_msg = f"Connecting to PIM Light Server via unix:{session_pim.socket_path} without credentials."
        assert any(call for call in mock_logger_info.call_args_list if call[0][0] == expected_msg)

        instance = product_instance_system.create_instance(product_name, JOB_DEFAULT_MAX_RUNNING_TIME)
        try:
            assert_instance(instance, product_name)
        finally:
            instance.delete()
            assert_instance_deleted(instance, product_name)

    @pytest.mark.parametrize("pim_host", [get_local_ip()], indirect=True)
    def test_external_pim(
        self,
        product_name: str,
        product_instance_system_factory: IProductInstanceSystemFactory,
        product_instance_system_uri: str,
        session_pim: PimProcess,
        certificates_directory: Path,
        local_ip: str,
        mocker: MockerFixture,
    ):
        assert session_pim.find_msg_in_output("Transport mode is: Mtls")
        assert session_pim.find_msg_in_output(f"Certificates folder is: {certificates_directory.as_posix()}")
        assert session_pim.find_msg_in_output(f"Server will listen with mutual TLS on {local_ip}:{session_pim.port}")

        mock_logger_info = mocker.patch.object(logging.Logger, "info")
        product_instance_system = create_product_instance_system(
            product_instance_system_factory,
            product_instance_system_uri,
        )
        expected_msg = (
            f"Connecting to PIM Light Server via {local_ip}:{session_pim.port} with credentials from "
            f"{certificates_directory.as_posix()}."
        )
        assert any(call for call in mock_logger_info.call_args_list if call[0][0] == expected_msg)

        instance = product_instance_system.create_instance(product_name, JOB_DEFAULT_MAX_RUNNING_TIME)
        try:
            assert_instance(instance, product_name)
        finally:
            instance.delete()
            assert_instance_deleted(instance, product_name)
