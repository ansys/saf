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
import platform
from typing import Any
from unittest import mock

from click.testing import CliRunner
import pytest

from ansys.saf.product_configuration.wrappers.fluent import (
    DEFAULT_TIMEOUT,
    SAF_FLUENT_WRAPPER_TIMEOUT,
    FluentInstance,
    TransportMode,
    main,
)

TESTING_GEOMETRY = "2d"
TESTING_HOST = "192.168.1.35"
TESTING_MODE = "solver"
TESTING_PORT = 46547
TESTING_PRECISION = "double"
TESTING_VERSION = "252"
DEFAULT_TRANSPORT_MODE = TransportMode.INSECURE
DEFAULT_CERTS_DIR = None


class MockProcess:
    def __init__(self, pid: int):
        self.pid = pid


def test_cli_without_required_options():
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code == 2


def test_cli_required_options():
    with (
        mock.patch.object(
            FluentInstance,
            "__init__",
            side_effect=FluentInstance.__init__,
            autospec=True,
        ) as fluent_init_mocked,
        mock.patch("uvicorn.run") as uvicorn_mocked,
        mock.patch.object(FluentInstance, "shutdown") as fluent_shutdown_mocked,
    ):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--host",
                TESTING_HOST,
                "--port",
                str(TESTING_PORT),
                "--version",
                TESTING_VERSION,
                "--mode",
                TESTING_MODE,
                "--geometry",
                TESTING_GEOMETRY,
                "--precision",
                TESTING_PRECISION,
            ],
        )
        assert result.exit_code == 0

        fluent_init_mocked.assert_called_once()
        assert fluent_init_mocked.call_args_list[0][1] == {
            "host": TESTING_HOST,
            "version": TESTING_VERSION,
            "mode": TESTING_MODE,
            "geometry": TESTING_GEOMETRY,
            "precision": TESTING_PRECISION,
            "transport_mode": DEFAULT_TRANSPORT_MODE,
            "certs_dir": DEFAULT_CERTS_DIR,
        }

        uvicorn_mocked.assert_called_once()
        assert uvicorn_mocked.call_args_list[0][1] == {
            "host": TESTING_HOST,
            "port": TESTING_PORT,
        }

        fluent_shutdown_mocked.assert_called_once()


def test_cli_optional_args():
    with (
        mock.patch.object(
            FluentInstance,
            "__init__",
            side_effect=FluentInstance.__init__,
            autospec=True,
        ) as fluent_init_mocked,
        mock.patch("uvicorn.run") as uvicorn_mocked,
        mock.patch.object(FluentInstance, "shutdown") as fluent_shutdown_mocked,
    ):
        runner = CliRunner()
        transport_mode = TransportMode.UDS
        assert transport_mode != DEFAULT_TRANSPORT_MODE
        certs_dir = "/tmp/certs"
        assert certs_dir != DEFAULT_CERTS_DIR
        result = runner.invoke(
            main,
            [
                "--host",
                TESTING_HOST,
                "--port",
                str(TESTING_PORT),
                "--version",
                TESTING_VERSION,
                "--mode",
                TESTING_MODE,
                "--geometry",
                TESTING_GEOMETRY,
                "--precision",
                TESTING_PRECISION,
                "--transport-mode",
                transport_mode.value,
                "--certs-dir",
                certs_dir,
            ],
        )
        assert result.exit_code == 0

        fluent_init_mocked.assert_called_once()
        assert fluent_init_mocked.call_args_list[0][1] == {
            "host": TESTING_HOST,
            "version": TESTING_VERSION,
            "mode": TESTING_MODE,
            "geometry": TESTING_GEOMETRY,
            "precision": TESTING_PRECISION,
            "transport_mode": transport_mode,
            "certs_dir": certs_dir,
        }

        uvicorn_mocked.assert_called_once()
        assert uvicorn_mocked.call_args_list[0][1] == {
            "host": TESTING_HOST,
            "port": TESTING_PORT,
        }

        fluent_shutdown_mocked.assert_called_once()


@pytest.mark.parametrize("mode", [None, "pure-meshing", 234])
def test_cli_custom_invalid_mode(mode: Any):
    runner = CliRunner()
    result = runner.invoke(main, ["--mode", str(mode)])
    assert result.exit_code == 2
    assert f"Error: Invalid value for '--mode': '{str(mode)}' is not one of 'solver', 'meshing'." in result.output


@pytest.mark.parametrize("geometry", [None, "4d", "3-dim", 3.0])
def test_cli_custom_invalid_geometry(geometry: Any):
    runner = CliRunner()
    result = runner.invoke(main, ["--geometry", str(geometry)])
    assert result.exit_code == 2
    assert f"Error: Invalid value for '--geometry': '{str(geometry)}' is not one of '2d', '3d'." in result.output


@pytest.mark.parametrize("precision", [None, "triple", 2])
def test_cli_custom_invalid_precision(precision: Any):
    runner = CliRunner()
    result = runner.invoke(main, ["--precision", str(precision)])
    assert result.exit_code == 2
    assert (
        f"Error: Invalid value for '--precision': '{str(precision)}' is not one of 'double', 'single'." in result.output
    )


@pytest.mark.parametrize("transport_mode", [None, "supersecure", 2])
def test_cli_custom_invalid_transport_mode(transport_mode: Any):
    runner = CliRunner()
    result = runner.invoke(main, ["--transport-mode", str(transport_mode)])
    assert result.exit_code == 2
    assert f"Error: Invalid value for '--transport-mode': '{str(transport_mode)}' is not one of" in result.output


@pytest.mark.parametrize(
    ("mode", "geometry", "precision"),
    [
        ("solver", "3d", "double"),
        ("solver", "2d", "double"),
        ("meshing", "3d", "double"),
    ],
)
def test_fluent_instance_workflow(mode: str, geometry: str, precision: str, tmp_path: Path):

    fluent_port = 12345

    def create_fluent_files(cmd: list[str], **kwargs: Any) -> MockProcess:
        if platform.system() == "Windows":
            cmd_txt = f'REM (%KILL_CMD% 22222)\nREM (%KILL_CMD% 3333)\ndel "{(tmp_path / "cleanup-fluent-test.bat")}"'
            (tmp_path / "cleanup-fluent-test.bat").write_text(cmd_txt)
        else:
            cmd_txt = f"# kill -9 22222;\n# kill -9 3333;\nrm {(tmp_path / 'cleanup-fluent-test.sh')}"
            (tmp_path / "cleanup-fluent-test.sh").write_text(cmd_txt)
        # Find the sifile argument in the command list
        sifile_arg = next(arg for arg in cmd if "-sifile=" in arg)
        Path(sifile_arg.split("-sifile=")[1].strip()).write_text(f"{TESTING_HOST}:{fluent_port}")  # type: ignore
        return MockProcess(23123)

    with (
        mock.patch("subprocess.Popen") as popen_cmd,
        mock.patch.object(FluentInstance, "_find_fluent_bin", return_value="fluent"),
    ):
        popen_cmd.side_effect = create_fluent_files
        # GIVEN: fresh FluentInstance
        f = FluentInstance(TESTING_HOST, TESTING_VERSION, mode, geometry, precision, TransportMode.INSECURE)
        assert f.port is None

        # WHEN: launching fluent
        f.initialize(tmp_path)
        popen_cmd.assert_called_once()

        # THEN: CMD is correct
        args = popen_cmd.call_args_list[0]
        assert all(arg in args[0][0] for arg in ["-grpc-allow-remote-host", "-grpc-insecure-mode"])
        if mode == "meshing":
            assert "-meshing" in args[0][0]
        precision_str = "dp" if precision == "double" else "sp"
        assert f"{geometry}{precision_str}" in args[0][0]
        no_gui_str = "-hidden" if platform.system() == "Windows" else "-g"
        assert no_gui_str in args[0][0]

        # THEN: CWD is correct
        assert args[1]["cwd"] == tmp_path

        # THEN: ENV VARS are correct
        assert args[1]["env"]["REMOTING_SERVER_ADDRESS"] == TESTING_HOST

        # THEN: cleanup and server_info files are parsed correctly
        assert f.get_fluent_pids() == [22222, 3333]
        assert f.port == fluent_port
        assert f._fluent  # pyright: ignore[reportPrivateUsage]
        assert f._cleanup_file.exists()  # pyright: ignore[reportPrivateUsage, reportOptionalMemberAccess]

    with mock.patch("ansys.saf.product_configuration.wrappers.fluent.kill_proc_tree") as kill_proc_tree_mock:
        # GIVEN: running FluentInstance
        # WHEN: stopping fluent
        f.shutdown()

        # THEN: main PID and PIDs from the cleanup file are killed
        kill_proc_tree_mock.assert_called()
        assert kill_proc_tree_mock.call_args_list[0][0] == (23123,)  # fluent PID

        # THEN: Port value is reset and cleanup file is removed
        assert f.port is None
        assert not f._fluent  # pyright: ignore[reportPrivateUsage]
        assert not f._fluent_address  # pyright: ignore[reportPrivateUsage]
        assert not f._cleanup_file  # pyright: ignore[reportPrivateUsage, reportOptionalMemberAccess]


def test_fluent_instance_shutdown_before_instance(tmp_path: Path):
    with mock.patch("ansys.saf.product_configuration.wrappers.fluent.kill_proc_tree") as kill_proc_tree_mock:
        # GIVEN: fresh FluentInstance
        f = FluentInstance(
            TESTING_HOST,
            TESTING_VERSION,
            TESTING_MODE,
            TESTING_GEOMETRY,
            TESTING_PRECISION,
            TransportMode.INSECURE,
        )
        assert f.port is None

        # WHEN: Trying to stop fluent
        f.shutdown()

        # THEN: nothing is killed and values are reset
        assert not kill_proc_tree_mock.called
        assert f.port is None


def test_fluent_instance_shutdown_twice(tmp_path: Path):

    fluent_port = 12345

    def create_fluent_files(cmd: list[str], **kwargs: Any) -> MockProcess:
        if platform.system() == "Windows":
            cmd_txt = f'REM (%KILL_CMD% 22222)\nREM (%KILL_CMD% 3333)\ndel "{(tmp_path / "cleanup-fluent-test.bat")}"'
            (tmp_path / "cleanup-fluent-test.bat").write_text(cmd_txt)
        else:
            cmd_txt = f"# kill -9 22222;\n# kill -9 3333;\nrm {(tmp_path / 'cleanup-fluent-test.sh')}"
            (tmp_path / "cleanup-fluent-test.sh").write_text(cmd_txt)
        # Find the sifile argument in the command list
        sifile_arg = next(arg for arg in cmd if "-sifile=" in arg)
        Path(sifile_arg.split("-sifile=")[1].strip()).write_text(f"{TESTING_HOST}:{fluent_port}")  # type: ignore
        return MockProcess(23123)

    with (
        mock.patch("subprocess.Popen") as popen_cmd,
        mock.patch.object(FluentInstance, "_find_fluent_bin", return_value="fluent"),
        mock.patch("ansys.saf.product_configuration.wrappers.fluent.kill_proc_tree") as kill_proc_tree_mock,
    ):
        popen_cmd.side_effect = create_fluent_files
        # GIVEN: running FluentInstance that is stopped
        f = FluentInstance(
            TESTING_HOST,
            TESTING_VERSION,
            TESTING_MODE,
            TESTING_GEOMETRY,
            TESTING_PRECISION,
            TransportMode.INSECURE,
        )
        f.initialize(tmp_path)

    with mock.patch("ansys.saf.product_configuration.wrappers.fluent.kill_proc_tree") as kill_proc_tree_mock:
        # WHEN: stopping fluent once
        f.shutdown()

        # THEN: proc is killed and values are reset
        kill_proc_tree_mock.assert_called_once()
        assert f.port is None

        # WHEN: stopping fluent twice
        kill_proc_tree_mock.reset_mock()
        f.shutdown()

        # THEN: nothing is killed and values are reset
        assert not kill_proc_tree_mock.called
        assert f.port is None


def test_fluent_instance_launch_twice(tmp_path: Path):

    fluent_port = 12345

    def create_fluent_files(cmd: list[str], **kwargs: Any) -> MockProcess:
        if platform.system() == "Windows":
            cmd_txt = f'REM (%KILL_CMD% 22222)\nREM (%KILL_CMD% 3333)\ndel "{(tmp_path / "cleanup-fluent-test.bat")}"'
            (tmp_path / "cleanup-fluent-test.bat").write_text(cmd_txt)
        else:
            cmd_txt = f"# kill -9 22222;\n# kill -9 3333;\nrm {(tmp_path / 'cleanup-fluent-test.sh')}"
            (tmp_path / "cleanup-fluent-test.sh").write_text(cmd_txt)
        # Find the sifile argument in the command list
        sifile_arg = next(arg for arg in cmd if "-sifile=" in arg)
        Path(sifile_arg.split("-sifile=")[1].strip()).write_text(f"{TESTING_HOST}:{fluent_port}")  # type: ignore
        return MockProcess(23123)

    with (
        mock.patch("subprocess.Popen") as popen_cmd,
        mock.patch.object(FluentInstance, "_find_fluent_bin", return_value="fluent"),
    ):
        popen_cmd.side_effect = create_fluent_files
        # GIVEN: freshly launched FluentInstance
        f = FluentInstance(
            TESTING_HOST,
            TESTING_VERSION,
            TESTING_MODE,
            TESTING_GEOMETRY,
            TESTING_PRECISION,
            TransportMode.INSECURE,
        )
        f.initialize(tmp_path)
        popen_cmd.assert_called_once()
        assert f.get_fluent_pids() == [22222, 3333]
        assert f.port == fluent_port

        # WHEN: Launching it twice
        popen_cmd.reset_mock()
        f.initialize(tmp_path)

        # THEN: Nothing is done, values are not reset either
        assert not popen_cmd.called
        assert f.get_fluent_pids() == [22222, 3333]
        assert f.port == fluent_port


def test_fluent_timeout(monkeypatch: pytest.MonkeyPatch):
    # GIVEN: value not configured using env var
    # WHEN: launching FluentInstance
    f = FluentInstance(
        TESTING_HOST,
        TESTING_VERSION,
        TESTING_MODE,
        TESTING_GEOMETRY,
        TESTING_PRECISION,
        TransportMode.INSECURE,
    )
    # THEN: Timeout is the default one
    assert f._timeout == DEFAULT_TIMEOUT  # pyright: ignore[reportPrivateUsage]

    # GIVEN: value configured using env var
    new_timeout = 10
    assert new_timeout != DEFAULT_TIMEOUT
    monkeypatch.setenv(SAF_FLUENT_WRAPPER_TIMEOUT, str(new_timeout))
    # WHEN: launching FluentInstance
    f = FluentInstance(
        TESTING_HOST,
        TESTING_VERSION,
        TESTING_MODE,
        TESTING_GEOMETRY,
        TESTING_PRECISION,
        TransportMode.INSECURE,
    )
    # THEN: Timeout is properly configured
    assert f._timeout == new_timeout  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize(
    ("fluent_address", "expected_port"),
    [
        (None, None),
        ("/tmp/fluent.sock", None),
        ("unix:///tmp/fluent.sock", None),
        ("127.0.0.1", None),
        ("127.0.0.1:not-a-port", None),
        ("127.0.0.1:12345:extra", None),
        (f"{TESTING_HOST}:{TESTING_PORT}", TESTING_PORT),
    ],
)
def test_fluent_instance_port_parsing(fluent_address: str | None, expected_port: int | None):
    f = FluentInstance(
        TESTING_HOST,
        TESTING_VERSION,
        TESTING_MODE,
        TESTING_GEOMETRY,
        TESTING_PRECISION,
        TransportMode.INSECURE,
    )
    f._fluent_address = fluent_address  # pyright: ignore[reportPrivateUsage]
    assert f.port == expected_port


@pytest.mark.parametrize("server_info_content", ["", "\n127.0.0.1:12345\n", "   \n127.0.0.1:12345\n"])
def test_find_fluent_address_requires_first_line(tmp_path: Path, server_info_content: str):
    server_info_file_path = tmp_path / "sifile.txt"
    server_info_file_path.write_text(server_info_content)

    f = FluentInstance(
        TESTING_HOST,
        TESTING_VERSION,
        TESTING_MODE,
        TESTING_GEOMETRY,
        TESTING_PRECISION,
        TransportMode.INSECURE,
    )

    with pytest.raises(RuntimeError, match="Couldn't find Fluent's address in server_info file."):
        f._find_fluent_address(server_info_file_path)  # pyright: ignore[reportPrivateUsage]


def test_build_cmd_insecure_transport(tmp_path: Path):
    with mock.patch.object(FluentInstance, "_find_fluent_bin", return_value="fluent"):
        f = FluentInstance(
            TESTING_HOST,
            TESTING_VERSION,
            TESTING_MODE,
            TESTING_GEOMETRY,
            TESTING_PRECISION,
            TransportMode.INSECURE,
        )
        cmd = f._build_cmd(tmp_path / "sifile.txt", TransportMode.INSECURE, None)  # pyright: ignore[reportPrivateUsage]
        assert "-grpc-allow-remote-host" in cmd
        assert "-grpc-insecure-mode" in cmd


def test_build_cmd_mtls_transport(tmp_path: Path):
    with mock.patch.object(FluentInstance, "_find_fluent_bin", return_value="fluent"):
        f = FluentInstance(
            TESTING_HOST,
            TESTING_VERSION,
            TESTING_MODE,
            TESTING_GEOMETRY,
            TESTING_PRECISION,
            TransportMode.MTLS,
        )
        cmd = f._build_cmd(tmp_path / "sifile.txt", TransportMode.MTLS, "/tmp/certs")  # pyright: ignore[reportPrivateUsage]
        assert "-grpc-allow-remote-host" in cmd
        assert "-grpc-certs-folder=/tmp/certs" in cmd
        assert "-grpc-insecure-mode" not in cmd


def test_build_cmd_uds_transport(tmp_path: Path):
    with mock.patch.object(FluentInstance, "_find_fluent_bin", return_value="fluent"):
        f = FluentInstance(
            TESTING_HOST,
            TESTING_VERSION,
            TESTING_MODE,
            TESTING_GEOMETRY,
            TESTING_PRECISION,
            TransportMode.UDS,
        )
        cmd = f._build_cmd(tmp_path / "sifile.txt", TransportMode.UDS, None)  # pyright: ignore[reportPrivateUsage]
        assert "-grpc-allow-remote-host" not in cmd
        assert "-grpc-insecure-mode" not in cmd


def test_build_cmd_wnua_transport(tmp_path: Path):
    assert TESTING_HOST != "127.0.0.1"
    with mock.patch.object(FluentInstance, "_find_fluent_bin", return_value="fluent"):
        f = FluentInstance(
            TESTING_HOST,
            TESTING_VERSION,
            TESTING_MODE,
            TESTING_GEOMETRY,
            TESTING_PRECISION,
            TransportMode.WNUA,
        )
        cmd = f._build_cmd(tmp_path / "sifile.txt", TransportMode.WNUA, None)  # pyright: ignore[reportPrivateUsage]
        assert "-grpc-allow-remote-host" not in cmd
        assert "-grpc-insecure-mode" not in cmd
        assert f._host == "127.0.0.1"  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize(
    ("transport_mode", "certs_dir", "expected_error_msg"),
    [
        (TransportMode.MTLS, None, "certs-dir must be provided when transport-mode is MTLS"),
        ("unknown", None, "Unknown transport mode: unknown"),
    ],
)
def test_build_cmd_invalid_transport(
    tmp_path: Path,
    transport_mode: TransportMode | str,
    certs_dir: str | None,
    expected_error_msg: str,
):
    with mock.patch.object(FluentInstance, "_find_fluent_bin", return_value="fluent"):
        f = FluentInstance(
            TESTING_HOST,
            TESTING_VERSION,
            TESTING_MODE,
            TESTING_GEOMETRY,
            TESTING_PRECISION,
            transport_mode,  # pyright: ignore[reportArgumentType]
        )
        with pytest.raises(RuntimeError, match=expected_error_msg):
            f._build_cmd(tmp_path / "sifile.txt", transport_mode, certs_dir)  # pyright: ignore[reportPrivateUsage, reportArgumentType]
