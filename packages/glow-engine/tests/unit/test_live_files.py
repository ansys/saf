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

import concurrent.futures
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
from ansys.saf.glow._core.live_files import (
    LiveFile,
    LiveFileOwnership,
    LiveFileOwnershipError,
    LiveFileProxy,
    TransactionLiveFile,
)
from tests.mocks.solution_end_to_end.solution.transaction_verification_step import TransactionVerificationStep
from tests.mocks.solutions.minimal_solution import MinimalSolution


def _make_step_proxy(http_client: httpx2.Client, project_id: str, project_files_dir: Path) -> StepProxy:
    return StepProxy(
        project_url=f"http://127.0.0.1:5432/projects/{project_id}",
        external_project_url=f"http://127.0.0.1:5432/projects/{project_id}",
        step_name="transaction_verification_step",
        step_model_type=TransactionVerificationStep,
        http_client=http_client,
        project_id=project_id,
        project_files_dir=project_files_dir,
        graphql_client=GqlClientConnectionPool(url="http://127.0.0.1:5432/graphql"),
    )


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


def test_base_live_file_read_is_not_implemented_and_has_no_path():
    live_file = LiveFile("logs/runtime.log")

    with pytest.raises(NotImplementedError):
        live_file.read_text()
    with pytest.raises(NotImplementedError):
        live_file.read_bytes()
    with pytest.raises(NotImplementedError):
        live_file.exists()
    assert not hasattr(live_file, "path")


def test_live_file_validation_accepts_nested_relative_file_path():
    validated = TypeAdapter(LiveFile).validate_python("logs/runtime.log")

    assert isinstance(validated, LiveFile)
    assert validated == "logs/runtime.log"
    assert validated.name == "runtime.log"
    assert repr(validated) == "LiveFile('logs/runtime.log')"


def test_live_file_validation_rejects_wildcards_with_dedicated_error():
    with pytest.raises(ValueError, match=r"cannot contain wildcard characters"):
        TypeAdapter(LiveFile).validate_python("logs/data[0].txt")


def test_transaction_live_file_path_and_read(tmp_path: Path):
    live_file = TransactionLiveFile("nested/runtime.log", tmp_path / "project-id", LiveFileOwnership())

    assert live_file.path == tmp_path / "project-id" / "nested" / "runtime.log"
    assert not live_file.exists()

    live_file.path.parent.mkdir(parents=True)
    live_file.path.write_text("alpha")

    assert live_file.exists()
    assert live_file.read_text() == "alpha"
    assert live_file.read_bytes() == b"alpha"


def test_transaction_live_file_read_text_honors_encoding(tmp_path: Path):
    live_file = TransactionLiveFile("logs/runtime.log", tmp_path / "project-id", LiveFileOwnership())
    text = "caf\u00e9"
    live_file.path.parent.mkdir(parents=True)
    live_file.path.write_bytes(text.encode("latin-1"))

    assert live_file.read_text(encoding="latin-1") == text
    with pytest.raises(UnicodeDecodeError):
        live_file.read_text()


def test_live_file_read_missing_raises_file_not_found(tmp_path: Path):
    live_file = TransactionLiveFile("logs/missing.log", tmp_path / "project-id", LiveFileOwnership())

    with pytest.raises(FileNotFoundError):
        live_file.read_text()

    with pytest.raises(FileNotFoundError):
        live_file.read_bytes()


def test_transaction_live_file_path_is_owned_by_first_transaction_accessing_it(tmp_path: Path):
    project_dir = tmp_path / "project-id"
    with LiveFileOwnership() as first_ownership, LiveFileOwnership() as second_ownership:
        first = TransactionLiveFile("logs/runtime.log", project_dir, first_ownership)
        second = TransactionLiveFile("logs/runtime.log", project_dir, second_ownership)

        first_path = first.path
        assert first.path == first_path

        with pytest.raises(LiveFileOwnershipError, match=r"'logs/runtime.log' is owned by another running transaction"):
            _ = second.path

        first_path.parent.mkdir(parents=True)
        first_path.write_text("alpha")
        assert second.read_text() == "alpha"
        assert second.exists()


def test_transaction_live_file_ownership_is_released_when_context_exits(tmp_path: Path):
    project_dir = tmp_path / "project-id"
    with LiveFileOwnership() as first_ownership:
        _ = TransactionLiveFile("logs/runtime.log", project_dir, first_ownership).path

    with LiveFileOwnership() as second_ownership:
        assert TransactionLiveFile("logs/runtime.log", project_dir, second_ownership).path.name == "runtime.log"


def _fail_while_owning_live_file(project_dir: Path) -> None:
    with LiveFileOwnership() as ownership:
        _ = TransactionLiveFile("logs/runtime.log", project_dir, ownership).path
        raise ValueError("transaction failed")


def test_transaction_live_file_ownership_is_released_when_transaction_fails(tmp_path: Path):
    project_dir = tmp_path / "project-id"
    with pytest.raises(ValueError, match="transaction failed"):
        _fail_while_owning_live_file(project_dir)

    with LiveFileOwnership() as second_ownership:
        assert TransactionLiveFile("logs/runtime.log", project_dir, second_ownership).path.name == "runtime.log"


def test_transaction_live_file_ownership_is_per_file_and_per_project(tmp_path: Path):
    with LiveFileOwnership() as first_ownership, LiveFileOwnership() as second_ownership:
        _ = TransactionLiveFile("logs/runtime.log", tmp_path / "project-a", first_ownership).path
        _ = TransactionLiveFile("logs/other.log", tmp_path / "project-a", second_ownership).path
        _ = TransactionLiveFile("logs/runtime.log", tmp_path / "project-b", second_ownership).path


def _try_to_own_live_file(project_dir: str) -> bool:
    with LiveFileOwnership() as ownership:
        try:
            _ = TransactionLiveFile("logs/runtime.log", Path(project_dir), ownership).path
        except LiveFileOwnershipError:
            return False
        return True


def test_transaction_live_file_ownership_is_enforced_across_processes(tmp_path: Path):
    project_dir = tmp_path / "project-id"
    with concurrent.futures.ProcessPoolExecutor(max_workers=1) as pool:
        with LiveFileOwnership() as ownership:
            _ = TransactionLiveFile("logs/runtime.log", project_dir, ownership).path
            assert pool.submit(_try_to_own_live_file, str(project_dir)).result() is False
        assert pool.submit(_try_to_own_live_file, str(project_dir)).result() is True


def test_live_file_proxy_is_read_only(tmp_path: Path):
    project_dir = tmp_path / "project-id"
    live_file_path = project_dir / "logs" / "runtime.log"
    live_file_path.parent.mkdir(parents=True)
    live_file_path.write_text("content")
    live_file = LiveFileProxy("logs/runtime.log", project_dir)

    assert live_file.read_text() == "content"
    assert live_file.exists()
    assert not hasattr(live_file, "path")


def test_step_proxy_returns_live_file_proxy_for_live_file_fields(tmp_path: Path):
    project_root = tmp_path / "projects"
    project_file = project_root / "my_project_id" / "logs" / "runtime.log"
    project_file.parent.mkdir(parents=True)
    project_file.write_text("hello")

    http_client = mock.Mock(spec=httpx2.Client)
    http_client.get.return_value = httpx2.Response(200, json={"live_file": "logs/runtime.log"})
    step = _make_step_proxy(http_client, "my_project_id", project_root)

    live_file = step.live_file

    assert isinstance(live_file, LiveFileProxy)
    assert live_file.read_text() == "hello"
    assert not hasattr(live_file, "path")


def test_step_proxy_get_fields_converts_live_file_field(tmp_path: Path):
    project_root = tmp_path / "projects"
    project_file = project_root / "my_project_id" / "logs" / "runtime.log"
    project_file.parent.mkdir(parents=True)
    project_file.write_text("hello")

    http_client = mock.Mock(spec=httpx2.Client)
    http_client.get.return_value = httpx2.Response(200, json={"live_file": "logs/runtime.log", "field_1": 7})
    step = _make_step_proxy(http_client, "my_project_id", project_root)

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

    step_a = _make_step_proxy(http_client, "project_a", project_root)
    step_b = _make_step_proxy(http_client, "project_b", project_root)

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

    assert project.project_id == "my_project_id"
    assert step._project_id == "my_project_id"
