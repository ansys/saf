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
from unittest.mock import MagicMock

from ansys.optislang.core.communication_channels import CommunicationChannel  # pyright: ignore[reportMissingTypeStubs]
from ansys.optislang.core.errors import (  # pyright: ignore[reportMissingTypeStubs]
    OslServerLicensingError,
    OslServerStartError,
)
from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from pytest_mock import MockerFixture

from ansys.saf.product_configuration.wrappers.optislang import (
    CONNECTION_MODE_LOCAL_DOMAIN,
    CONNECTION_MODE_TCP,
    SAF_OPTISLANG_TIMEOUT,
    OptislangInstance,
    app,
    get_global_optislang_instance,
)

client = TestClient(app)


def test_get_health_check():
    response = client.get("/health")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.status_code == 200  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.json() == "healthy"  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]


def test_get_logs_no_log_path(mocker: MockerFixture):
    instance = get_global_optislang_instance()
    instance.osl_log_path = None
    response = client.get("/logs")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.status_code == 500  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.json() == {"detail": "Logs are not available"}  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]


def test_get_logs_log_path_does_not_exist(mocker: MockerFixture):
    instance = get_global_optislang_instance()
    mocker.patch.object(instance, "osl_log_path", new_callable=MagicMock)
    instance.osl_log_path.exists.return_value = False  # type: ignore
    response = client.get("/logs")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.status_code == 500  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.json() == {"detail": "Log file does not exist"}  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]


def test_get_logs_success(mocker: MockerFixture):
    log_content = "Sample log content"
    instance = get_global_optislang_instance()
    mocker.patch.object(instance, "osl_log_path", new_callable=MagicMock)
    instance.osl_log_path.exists.return_value = True  # type: ignore
    instance.osl_log_path.read_text.return_value = log_content  # type: ignore
    response = client.get("/logs")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.status_code == 200  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.text == log_content  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]


def test_get_connection_not_started():
    instance = get_global_optislang_instance()
    instance._connection_mode = None  # pyright: ignore[reportPrivateUsage]
    instance._local_server_id = None  # pyright: ignore[reportPrivateUsage]
    instance._osl_port = None  # pyright: ignore[reportPrivateUsage]
    instance._osl_host = None  # pyright: ignore[reportPrivateUsage]
    response = client.get("/connection")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.status_code == 500  # pyright: ignore[reportUnknownMemberType]
    assert response.json() == {"detail": "Local connection information is not available"}  # pyright: ignore[reportUnknownMemberType]


def test_get_connection_local_domain_success():
    instance = get_global_optislang_instance()
    instance._connection_mode = CONNECTION_MODE_LOCAL_DOMAIN  # pyright: ignore[reportPrivateUsage]
    instance._local_server_id = "localhost:1234#0"  # pyright: ignore[reportPrivateUsage]
    instance._osl_port = None  # pyright: ignore[reportPrivateUsage]
    instance._osl_host = None  # pyright: ignore[reportPrivateUsage]
    response = client.get("/connection")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.status_code == 200  # pyright: ignore[reportUnknownMemberType]
    assert response.json() == {"connection_mode": CONNECTION_MODE_LOCAL_DOMAIN, "local_server_id": "localhost:1234#0"}  # pyright: ignore[reportUnknownMemberType]


def test_get_connection_tcp_success():
    instance = get_global_optislang_instance()
    instance._connection_mode = CONNECTION_MODE_TCP  # pyright: ignore[reportPrivateUsage]
    instance._osl_port = 5678  # pyright: ignore[reportPrivateUsage]
    instance._osl_host = "0.0.0.0"  # pyright: ignore[reportPrivateUsage]
    instance._local_server_id = None  # pyright: ignore[reportPrivateUsage]
    response = client.get("/connection")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.status_code == 200  # pyright: ignore[reportUnknownMemberType]
    assert response.json() == {"connection_mode": CONNECTION_MODE_TCP, "host": "0.0.0.0", "port": 5678}  # pyright: ignore[reportUnknownMemberType]


def test_get_connection_tcp_no_host_port():
    instance = get_global_optislang_instance()
    instance._connection_mode = CONNECTION_MODE_TCP  # pyright: ignore[reportPrivateUsage]
    instance._osl_port = None  # pyright: ignore[reportPrivateUsage]
    instance._osl_host = None  # pyright: ignore[reportPrivateUsage]
    response = client.get("/connection")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.status_code == 500  # pyright: ignore[reportUnknownMemberType]
    assert response.json() == {"detail": "TCP connection information is not available"}  # pyright: ignore[reportUnknownMemberType]


@pytest.mark.parametrize(
    (
        "instance_connection_mode",
        "instance_local_server_id",
        "instance_host",
        "instance_port",
        "request_connection_mode",
        "expected_response",
    ),
    [
        (
            CONNECTION_MODE_LOCAL_DOMAIN,
            "localhost:1234#0",
            None,
            None,
            None,
            {"connection_mode": CONNECTION_MODE_LOCAL_DOMAIN, "local_server_id": "localhost:1234#0"},
        ),
        (
            CONNECTION_MODE_TCP,
            None,
            "0.0.0.0",
            5678,
            "TCP",
            {"connection_mode": CONNECTION_MODE_TCP, "host": "0.0.0.0", "port": 5678},
        ),
    ],
)
def test_start_instance(
    mocker: MockerFixture,
    instance_connection_mode: str,
    instance_local_server_id: str | None,
    instance_host: str | None,
    instance_port: int | None,
    request_connection_mode: str | None,
    expected_response: dict[str, str | int],
):
    instance = get_global_optislang_instance()
    mocker.patch.object(instance, "start")

    instance._connection_mode = instance_connection_mode  # pyright: ignore[reportPrivateUsage]
    instance._local_server_id = instance_local_server_id  # pyright: ignore[reportPrivateUsage]
    instance._osl_port = instance_port  # pyright: ignore[reportPrivateUsage]
    instance._osl_host = instance_host  # pyright: ignore[reportPrivateUsage]

    request_body = {
        "project_path": "project_path",
        "project_properties_file": "project_properties_file",
        "osl_version": 251,
        "input_files": ["input_file1", "input_file2"],
        "loglevel": "INFO",
        "log_file_path": "log_file_path",
    }

    if request_connection_mode is not None:
        request_body["connection_mode"] = request_connection_mode

    response = client.post("/start", json=request_body)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.status_code == 200  # pyright: ignore[reportUnknownMemberType]
    instance.start.assert_called_once()  # type: ignore

    response_body = response.json()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response_body == expected_response


def test_start_instance_no_executable(mocker: MockerFixture):
    mocker.patch(
        "ansys.saf.product_configuration.wrappers.optislang.utils.get_osl_exec",
        return_value=None,
    )

    request_body = {
        "project_path": "project_path",
        "project_properties_file": "project_properties_file",
        "osl_version": 251,
        "input_files": ["input_file1", "input_file2"],
        "loglevel": "INFO",
        "log_file_path": "log_file_path",
    }

    response = client.post("/start", json=request_body)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.status_code == 500  # pyright: ignore[reportUnknownMemberType]

    response_body = response.json()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    assert response_body == {"detail": "OptiSLang executable not found"}


def test_shutdown(mocker: MockerFixture):
    instance = get_global_optislang_instance()
    mocker.patch.object(instance, "shutdown")
    response = client.post("/shutdown")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.status_code == 200  # pyright: ignore[reportUnknownMemberType]
    instance.shutdown.assert_called_once()  # type: ignore


def test_close_optislang(mocker: MockerFixture):
    instance = get_global_optislang_instance()
    mocker.patch.object(instance, "close_optislang")
    response = client.post("/close-optislang")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.status_code == 200  # pyright: ignore[reportUnknownMemberType]
    instance.close_optislang.assert_called_once()  # type: ignore


@pytest.mark.parametrize(("timeout_value", "expected_timeout"), [(None, 300), ("42", 42)])
def test_optislang_instance_start(
    tmp_path: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    timeout_value: str | None,
    expected_timeout: int,
):

    if timeout_value is None:
        monkeypatch.delenv(SAF_OPTISLANG_TIMEOUT, raising=False)
    else:
        monkeypatch.setenv(SAF_OPTISLANG_TIMEOUT, timeout_value)

    opf_file_content = b"SOME DATA"

    source_folder = tmp_path / "source"
    source_folder.mkdir()
    project_path = source_folder / "project.opf"
    project_path.write_bytes(opf_file_content)

    input_files_folder = source_folder / "Input_Files"
    input_files_folder.mkdir()
    (input_files_folder / "input_file.txt").write_text("SOME DATA")

    target_folder = tmp_path / "target"
    target_folder.mkdir()

    mocker.patch("tempfile.mkdtemp", return_value=target_folder.as_posix())

    py_optislang = mocker.patch("ansys.saf.product_configuration.wrappers.optislang.Optislang")
    py_optislang_instance = py_optislang.return_value
    py_optislang_instance.name = "Optislang"
    py_optislang_instance.osl_server.local_server_id = "localhost:1234#0"

    get_osl_exec = mocker.patch("ansys.saf.product_configuration.wrappers.optislang.utils.get_osl_exec")

    copied_project_path = target_folder / "project.opf"

    project_properties_file = source_folder / "project_properties.json"
    project_properties_file.write_text('{"key": "value"}')

    instance = OptislangInstance()
    instance.start(
        project_path=project_path,
        project_properties_file=project_properties_file,
        input_files=list(input_files_folder.iterdir()),
        osl_version=251,
        loglevel="INFO",
        connection_mode="LOCAL_DOMAIN",
        log_file_path=None,
    )

    # Check if the correct Optislang version was used to get the executable path
    assert get_osl_exec.call_args.args[0] == 251

    # Check if the Optislang instance was initialized with the correct arguments
    assert py_optislang.call_args.kwargs["project_path"] == copied_project_path
    assert py_optislang.call_args.kwargs["import_project_properties_file"] == project_properties_file
    assert py_optislang.call_args.kwargs["loglevel"] == "INFO"
    assert py_optislang.call_args.kwargs["reset"] is True
    assert py_optislang.call_args.kwargs["auto_relocate"] is True
    assert py_optislang.call_args.kwargs["shutdown_on_finished"] is False
    assert py_optislang.call_args.kwargs["env_vars"] == {"PYTHONPATH": ""}
    assert py_optislang.call_args.kwargs["ini_timeout"] == expected_timeout
    assert py_optislang.call_args.kwargs["communication_channel"] == CommunicationChannel.LOCAL_DOMAIN
    assert py_optislang.call_args.kwargs["server_address"] is None

    # Check if the project file and input files were copied
    assert copied_project_path.exists()
    assert copied_project_path.read_bytes() == opf_file_content

    assert (target_folder / "Input_Files").exists()
    assert (target_folder / "Input_Files" / "input_file.txt").exists()
    assert (target_folder / "Input_Files" / "input_file.txt").read_text() == "SOME DATA"

    # Check that the log file was created
    assert (target_folder / "optiSLang.log").exists()

    # Check that the local_server_id was set (LOCAL_DOMAIN mode)
    assert instance.local_server_id == "localhost:1234#0"
    assert instance.port is None
    assert instance.host is None


@pytest.mark.parametrize("timeout_value", ["", "0", "-1", "not-an-integer"])
def test_optislang_instance_start_rejects_invalid_timeout(
    tmp_path: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    timeout_value: str,
):
    monkeypatch.setenv(SAF_OPTISLANG_TIMEOUT, timeout_value)

    source_folder = tmp_path / "source"
    source_folder.mkdir()
    project_path = source_folder / "project.opf"
    project_path.write_bytes(b"SOME DATA")
    project_properties_file = source_folder / "project_properties.json"
    project_properties_file.write_text('{"key": "value"}')

    target_folder = tmp_path / "target"
    target_folder.mkdir()
    mocker.patch("tempfile.mkdtemp", return_value=target_folder.as_posix())
    mocker.patch(
        "ansys.saf.product_configuration.wrappers.optislang.utils.get_osl_exec",
        return_value=("251", "fake_exec"),
    )

    with pytest.raises(ValueError, match=f"{SAF_OPTISLANG_TIMEOUT} must be a positive integer"):
        OptislangInstance().start(
            project_path=project_path,
            project_properties_file=project_properties_file,
            input_files=[],
            osl_version=251,
            loglevel="INFO",
            connection_mode=CONNECTION_MODE_LOCAL_DOMAIN,
            log_file_path=None,
        )


def test_optislang_instance_start_no_executable(tmp_path: Path, mocker: MockerFixture):

    mocker.patch(
        "ansys.saf.product_configuration.wrappers.optislang.utils.get_osl_exec",
        return_value=None,
    )
    instance = OptislangInstance()

    with pytest.raises(HTTPException, match="OptiSLang executable not found"):
        instance.start(
            project_path=Path("project_path"),
            project_properties_file=Path("project_properties_file"),
            input_files=[],
            osl_version=251,
            loglevel="INFO",
            connection_mode="LOCAL_DOMAIN",
            log_file_path=None,
        )


def test_optislang_instance_start_invalid_connection_mode(tmp_path: Path, mocker: MockerFixture):

    source_folder = tmp_path / "source"
    source_folder.mkdir()
    project_path = source_folder / "project.opf"
    project_path.write_bytes(b"SOME DATA")

    project_properties_file = source_folder / "project_properties.json"
    project_properties_file.write_text('{"key": "value"}')

    target_folder = tmp_path / "target"
    target_folder.mkdir()
    mocker.patch("tempfile.mkdtemp", return_value=target_folder.as_posix())

    mocker.patch(
        "ansys.saf.product_configuration.wrappers.optislang.utils.get_osl_exec",
        return_value=("251", "fake_exec"),
    )
    py_optislang = mocker.patch("ansys.saf.product_configuration.wrappers.optislang.Optislang")

    instance = OptislangInstance()

    with pytest.raises(HTTPException, match="Invalid connection_mode 'INVALID_MODE'") as exc_info:
        instance.start(
            project_path=project_path,
            project_properties_file=project_properties_file,
            input_files=[],
            osl_version=251,
            loglevel="INFO",
            connection_mode="INVALID_MODE",
            log_file_path=None,
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == ("Invalid connection_mode 'INVALID_MODE'. Expected one of: LOCAL_DOMAIN, TCP")
    py_optislang.assert_not_called()


@pytest.mark.parametrize(
    ("side_effect", "expected_error", "expected_error_code"),
    [
        (OslServerLicensingError, "No available licenses at this time", 1),
        (OslServerStartError, "OptiSLang server error", 2),
    ],
)
def test_optislang_instance_start_errors(
    mocker: MockerFixture,
    side_effect: type[Exception],
    expected_error: str,
    expected_error_code: int,
):

    instance = get_global_optislang_instance()
    mocker.patch.object(instance, "start", side_effect=side_effect)

    request_body = {
        "project_path": "project_path",
        "project_properties_file": "project_properties_file",
        "osl_version": 251,
        "input_files": ["input_file1", "input_file2"],
        "loglevel": "INFO",
        "log_file_path": "log_file_path",
    }

    response = client.post("/start", json=request_body)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert response.status_code == 500  # pyright: ignore[reportUnknownMemberType]

    response_body = response.json()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    expected_message = (
        f"Unable to start optiSLang 251: {expected_error}. Please try again later or contact your IT administrator."
    )

    assert response_body == {
        "message": expected_message,
        "error_code": expected_error_code,
    }


def test_optislang_instance_close_optislang(mocker: MockerFixture, tmp_path: Path):
    working_directory = tmp_path / "working_directory"
    working_directory.mkdir()
    osl_mock = mocker.MagicMock()

    instance = OptislangInstance()
    instance._osl_working_directory = working_directory.as_posix()  # pyright: ignore[reportPrivateUsage]
    instance._osl = osl_mock  # pyright: ignore[reportPrivateUsage]

    instance.close_optislang()

    osl_mock.shutdown.assert_called_once_with(force=True)

    assert instance._osl is None  # pyright: ignore[reportPrivateUsage]

    assert working_directory.exists()  # The working directory should not be deleted
    assert instance._osl_working_directory is not None  # pyright: ignore[reportPrivateUsage]


def test_optislang_instance_shutdown(mocker: MockerFixture, tmp_path: Path):
    working_directory = tmp_path / "working_directory"
    working_directory.mkdir()
    osl_mock = mocker.MagicMock()

    instance = OptislangInstance()
    instance._osl_working_directory = working_directory.as_posix()  # pyright: ignore[reportPrivateUsage]
    instance._osl = osl_mock  # pyright: ignore[reportPrivateUsage]

    instance.shutdown()

    osl_mock.shutdown.assert_called_once_with(force=True)

    assert instance._osl is None  # pyright: ignore[reportPrivateUsage]
    assert instance._osl_working_directory is None  # pyright: ignore[reportPrivateUsage]

    assert not working_directory.exists()
