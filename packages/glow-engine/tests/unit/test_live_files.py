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

from io import BytesIO
from pathlib import Path
import sys
from unittest import mock

import httpx2
from pydantic import TypeAdapter
import pytest

from ansys.saf.glow._client.project_proxy import ProjectProxy
from ansys.saf.glow._client.step_proxy import StepProxy
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.gql import GqlClientConnectionPool
from ansys.saf.glow._core.live_files import LiveFile, LiveFileProxy, TransactionLiveFile
from tests.mocks.solution_end_to_end.solution.transaction_verification_step import TransactionVerificationStep
from tests.mocks.solutions.minimal_solution import MinimalSolution


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("../logs/runtime.log", r"\.\. is not allowed inside a LiveFile field"),
        ("", r"A LiveFile must refer to a file path"),
        (".", r"A LiveFile must refer to a file path"),
        ("logs/", r"A LiveFile must refer to a file and cannot end with a path separator"),
        ("logs\\", r"A LiveFile must refer to a file and cannot end with a path separator"),
        ("logs\\runtime.log", r"A LiveFile can't contain any of the following characters"),
        ("logs/*.txt", r"A LiveFile can't contain any of the following characters"),
    ],
)
def test_live_file_validation_rejects_invalid_paths(value: str, message: str):
    with pytest.raises(ValueError, match=message):
        TypeAdapter(LiveFile).validate_python(value)


def test_live_file_validation_rejects_absolute_paths():
    absolute_path = "C:/absolute/runtime.log" if sys.platform == "win32" else "/absolute/runtime.log"

    with pytest.raises(ValueError, match=r"Absolute path: '.*' is not allowed in a LiveFile field"):
        TypeAdapter(LiveFile).validate_python(absolute_path)


def test_base_live_file_read_and_path_are_not_implemented():
    live_file = LiveFile("logs/runtime.log")

    with pytest.raises(NotImplementedError):
        live_file.read_text()
    with pytest.raises(NotImplementedError):
        live_file.read_bytes()
    with pytest.raises(NotImplementedError):
        _ = live_file.path


def test_live_file_validation_accepts_nested_relative_file_path():
    validated = TypeAdapter(LiveFile).validate_python("logs/runtime.log")

    assert isinstance(validated, LiveFile)
    assert validated == "logs/runtime.log"
    assert validated.name == "runtime.log"
    assert repr(validated) == "LiveFile('logs/runtime.log')"


def test_live_file_validation_rejects_wildcards_with_dedicated_error():
    with pytest.raises(ValueError, match=r"cannot contain wildcard characters"):
        TypeAdapter(LiveFile).validate_python("logs/data[0].txt")


def test_transaction_live_file_write_lifecycle(tmp_path: Path):
    live_file = TransactionLiveFile("nested/runtime.log", tmp_path / "project-id")

    assert live_file.path == tmp_path / "project-id" / "nested" / "runtime.log"
    assert live_file.path.parent == tmp_path / "project-id" / "nested"
    assert not live_file.exists()

    live_file.write_text("alpha")
    live_file.write_text("beta", mode="a")

    assert live_file.exists()
    assert live_file.read_text() == "alphabeta"

    live_file.delete()

    assert not live_file.exists()


def test_transaction_live_file_write_text_and_read_text_honor_encoding(tmp_path: Path):
    live_file = TransactionLiveFile("logs/runtime.log", tmp_path / "project-id")
    text = "café"

    live_file.write_text(text, encoding="latin-1")

    assert live_file.read_bytes() == text.encode("latin-1")
    assert live_file.read_text(encoding="latin-1") == text
    with pytest.raises(UnicodeDecodeError):
        live_file.read_text()


def test_transaction_live_file_delete_is_idempotent(tmp_path: Path):
    live_file = TransactionLiveFile("nested/runtime.log", tmp_path / "project-id")

    live_file.delete()
    live_file.delete()

    assert not live_file.exists()


def test_transaction_live_file_supports_binary_write_and_copy_from_live_file(tmp_path: Path):
    project_dir = tmp_path / "project-id"
    source = TransactionLiveFile("inputs/source.bin", project_dir)
    destination = TransactionLiveFile("outputs/destination.bin", project_dir)

    source.write(BytesIO(b"ab"))
    source.write_bytes(b"cd", mode="ab")
    destination.write_from_file(source)

    assert source.read_bytes() == b"abcd"
    assert destination.read_bytes() == b"abcd"


def test_transaction_live_file_write_from_str_path_and_append_stream(tmp_path: Path):
    project_dir = tmp_path / "project-id"
    source_path = tmp_path / "source.txt"
    source_path.write_text("from-str")
    destination = TransactionLiveFile("outputs/destination.txt", project_dir)

    destination.write_from_file(str(source_path))
    destination.write(BytesIO(b"-appended"), mode="ab")

    assert destination.read_text() == "from-str-appended"


def test_transaction_live_file_write_from_missing_file_raises(tmp_path: Path):
    live_file = TransactionLiveFile("outputs/runtime.log", tmp_path / "project-id")
    missing_source = tmp_path / "missing.txt"

    with pytest.raises(FileNotFoundError):
        live_file.write_from_file(missing_source)


def test_live_file_read_missing_raises_file_not_found(tmp_path: Path):
    live_file = TransactionLiveFile("logs/missing.log", tmp_path / "project-id")

    with pytest.raises(FileNotFoundError):
        live_file.read_text()

    with pytest.raises(FileNotFoundError):
        live_file.read_bytes()


def test_transaction_live_file_single_writer_lock_is_exclusive(tmp_path: Path):
    project_dir = tmp_path / "project-id"
    first_writer = TransactionLiveFile("logs/runtime.log", project_dir)
    second_writer = TransactionLiveFile("logs/runtime.log", project_dir)

    assert first_writer.path == project_dir / "logs" / "runtime.log"
    with pytest.raises(PermissionError, match="already being written"):
        _ = second_writer.path

    first_writer.release_lock()

    assert second_writer.path == project_dir / "logs" / "runtime.log"
    second_writer.release_lock()


def test_transaction_live_file_release_lock_is_idempotent(tmp_path: Path):
    project_dir = tmp_path / "project-id"
    live_file = TransactionLiveFile("logs/runtime.log", project_dir)

    _ = live_file.path
    live_file.release_lock()
    live_file.release_lock()

    other_writer = TransactionLiveFile("logs/runtime.log", project_dir)
    assert other_writer.path == project_dir / "logs" / "runtime.log"
    other_writer.release_lock()


@pytest.mark.parametrize("operation", ["write_text", "write", "write_bytes", "write_from_file", "delete"])
def test_live_file_proxy_is_read_only(operation: str, tmp_path: Path):
    project_dir = tmp_path / "project-id"
    project_dir.mkdir(parents=True)
    source_path = tmp_path / "source.txt"
    source_path.write_text("source")
    live_file_path = project_dir / "logs" / "runtime.log"
    live_file_path.parent.mkdir(parents=True)
    live_file_path.write_text("content")
    live_file = LiveFileProxy("logs/runtime.log", project_dir)

    if operation == "write_text":
        with pytest.raises(PermissionError, match="cannot be mutated from the Client scope"):
            live_file.write_text("forbidden")
    elif operation == "write":
        with pytest.raises(PermissionError, match="cannot be mutated from the Client scope"):
            live_file.write(BytesIO(b"forbidden"))
    elif operation == "write_bytes":
        with pytest.raises(PermissionError, match="cannot be mutated from the Client scope"):
            live_file.write_bytes(b"forbidden")
    elif operation == "write_from_file":
        with pytest.raises(PermissionError, match="cannot be mutated from the Client scope"):
            live_file.write_from_file(source_path)
    elif operation == "delete":
        with pytest.raises(PermissionError, match="cannot be mutated from the Client scope"):
            live_file.delete()

    assert live_file.read_text() == "content"
    assert live_file.exists()
    with pytest.raises(NotImplementedError):
        _ = live_file.path


def test_step_proxy_returns_live_file_proxy_for_live_file_fields(tmp_path: Path):
    project_root = tmp_path / "projects"
    project_file = project_root / "my_project_id" / "logs" / "runtime.log"
    project_file.parent.mkdir(parents=True)
    project_file.write_text("hello")

    http_client = mock.Mock(spec=httpx2.Client)
    http_client.get.return_value = httpx2.Response(200, json={"live_file": "logs/runtime.log"})
    step = StepProxy(
        project_url="http://127.0.0.1:5432/projects/my_project_id",
        external_project_url="http://127.0.0.1:5432/projects/my_project_id",
        step_name="transaction_verification_step",
        step_model_type=TransactionVerificationStep,
        http_client=http_client,
        project_id="my_project_id",
        project_files_dir=project_root,
        graphql_client=GqlClientConnectionPool(url="http://127.0.0.1:5432/graphql"),
    )

    live_file = step.live_file

    assert isinstance(live_file, LiveFileProxy)
    assert live_file.read_text() == "hello"
    with pytest.raises(NotImplementedError):
        _ = live_file.path


def test_step_proxy_get_fields_converts_live_file_field(tmp_path: Path):
    project_root = tmp_path / "projects"
    project_file = project_root / "my_project_id" / "logs" / "runtime.log"
    project_file.parent.mkdir(parents=True)
    project_file.write_text("hello")

    http_client = mock.Mock(spec=httpx2.Client)
    http_client.get.return_value = httpx2.Response(200, json={"live_file": "logs/runtime.log", "field_1": 7})
    step = StepProxy(
        project_url="http://127.0.0.1:5432/projects/my_project_id",
        external_project_url="http://127.0.0.1:5432/projects/my_project_id",
        step_name="transaction_verification_step",
        step_model_type=TransactionVerificationStep,
        http_client=http_client,
        project_id="my_project_id",
        project_files_dir=project_root,
        graphql_client=GqlClientConnectionPool(url="http://127.0.0.1:5432/graphql"),
    )

    fields = step.get_fields(["live_file", "field_1"])

    assert isinstance(fields["live_file"], LiveFileProxy)
    assert fields["live_file"].read_text() == "hello"
    assert fields["field_1"] == 7


def test_step_proxy_live_file_is_project_scoped(tmp_path: Path):
    project_root = tmp_path / "projects"
    project_a_file = project_root / "project_a" / "logs" / "runtime.log"
    project_b_file = project_root / "project_b" / "logs" / "runtime.log"
    project_a_file.parent.mkdir(parents=True)
    project_b_file.parent.mkdir(parents=True)
    project_a_file.write_text("project-a-content")
    project_b_file.write_text("project-b-content")

    http_client = mock.Mock(spec=httpx2.Client)
    http_client.get.return_value = httpx2.Response(200, json={"live_file": "logs/runtime.log"})

    step_a = StepProxy(
        project_url="http://127.0.0.1:5432/projects/project_a",
        external_project_url="http://127.0.0.1:5432/projects/project_a",
        step_name="transaction_verification_step",
        step_model_type=TransactionVerificationStep,
        http_client=http_client,
        project_id="project_a",
        project_files_dir=project_root,
        graphql_client=GqlClientConnectionPool(url="http://127.0.0.1:5432/graphql"),
    )
    step_b = StepProxy(
        project_url="http://127.0.0.1:5432/projects/project_b",
        external_project_url="http://127.0.0.1:5432/projects/project_b",
        step_name="transaction_verification_step",
        step_model_type=TransactionVerificationStep,
        http_client=http_client,
        project_id="project_b",
        project_files_dir=project_root,
        graphql_client=GqlClientConnectionPool(url="http://127.0.0.1:5432/graphql"),
    )

    assert step_a.live_file.read_text() == "project-a-content"
    assert step_b.live_file.read_text() == "project-b-content"


def test_project_proxy_steps_propagates_project_id():
    project = ProjectProxy(
        name="projects/my_project_id",
        solution_type=MinimalSolution,
        url="http://127.0.0.1:5432/projects/my_project_id",
        external_url="http://127.0.0.1:5432/projects/my_project_id",
        http_client=httpx2.Client(),
        project_files_dir=Path.cwd(),
        graphql_client=GqlClientConnectionPool(url="http://127.0.0.1:5432/graphql"),
        settings=mock.Mock(spec=Settings),
    )

    step = project.steps.minimal_step

    assert step._project_id == "my_project_id"
