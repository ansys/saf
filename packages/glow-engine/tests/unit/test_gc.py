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
from contextlib import AbstractContextManager
from pathlib import Path
import sys
from typing import Any
import uuid

from fastapi.testclient import TestClient
from pydantic import BaseModel
import pytest

from ansys.bdm.api import NO_ENTITY, EntityHandle, IStorageScope, RecursiveDictionaryOfEntityHandles
from ansys.saf.glow._bdm.multiplexor import MultiplexorStorageScopeFactory
from ansys.saf.glow._bdm.storage_contexts import GC_CONTEXT, PROJECT_BOUNDARY
from ansys.saf.glow._bdm.storage_factory import create_shared_storage_factory, random_shortid
from ansys.saf.glow._bdm.storage_variable_names import PROJECT_ID, ROOT, SHORTID
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.livehandles import LiveHandlesModel
from ansys.saf.glow._server.models import ProjectModel
from ansys.saf.glow._server.server import create_app
import tests.mocks.solutions.bdm_solution as bdm_solution
from tests.mocks.solutions.bdm_solution import BdmSolution


class EmptyRecursiveThing(LiveHandlesModel):
    children: list["EmptyRecursiveThing"] = []


class RecursiveThing(BaseModel):
    children: list["RecursiveThing"] = []
    handle: EntityHandle = NO_ENTITY


class OtherSub(BaseModel):
    s: str = "other"


class InnerSub(BaseModel):
    s: str = "inner"
    inner_sub_handle: EntityHandle = NO_ENTITY
    inner_sub_no_entity: EntityHandle = NO_ENTITY


class Sub(BaseModel):
    i: int = 1
    sub_handle: EntityHandle = NO_ENTITY
    sub_no_entity: EntityHandle = NO_ENTITY
    inner_sub: InnerSub = InnerSub()


class ModelTest(LiveHandlesModel):
    i: int = 0
    s: str = "hello"
    handle: EntityHandle = NO_ENTITY
    no_entity: EntityHandle = NO_ENTITY
    handles: list[EntityHandle] = []
    handles_dict: dict[str, EntityHandle] = {}
    sub: Sub = Sub()
    list_of_inner_sub: list[InnerSub] = []
    nullable_handle_not_null: EntityHandle | None = None
    nullable_handle_null: EntityHandle | None = None
    nullable_handles_list: list[EntityHandle | None] = []
    union_list: list[OtherSub | InnerSub] = []
    other_union_list: list[Sub | InnerSub] = []
    handles_key_dict: dict[EntityHandle, str] = {}
    pair_of_handles: tuple[EntityHandle, EntityHandle] = (NO_ENTITY, NO_ENTITY)
    recursive_dict_of_handles: RecursiveDictionaryOfEntityHandles = RecursiveDictionaryOfEntityHandles()


class RecursiveTest(LiveHandlesModel):
    recursive_thing: RecursiveThing = RecursiveThing()


def create_entity_handle(name: str) -> EntityHandle:
    return EntityHandle(is_blob=True, opaque_identifier=name, entity_id=uuid.uuid4())


@pytest.fixture
def model() -> ModelTest:
    m = ModelTest(
        handle=create_entity_handle("handle"),
        handles=[create_entity_handle("handles"), NO_ENTITY],
        handles_dict={"entity": create_entity_handle("handles_dict"), "no_entity": NO_ENTITY},
        sub=Sub(
            sub_handle=create_entity_handle("sub.sub_handle"),
            inner_sub=InnerSub(
                inner_sub_handle=create_entity_handle("sub.inner_sub.inner_sub_handle"),
            ),
        ),
        list_of_inner_sub=[
            InnerSub(inner_sub_handle=create_entity_handle("list_of_inner_sub.inner_sub_handle1")),
            InnerSub(inner_sub_handle=create_entity_handle("list_of_inner_sub.inner_sub_handle2")),
        ],
        nullable_handle_not_null=create_entity_handle("nullable_handle_not_null"),
        nullable_handles_list=[None, create_entity_handle("nullable_handles_list")],
        union_list=[OtherSub(), InnerSub(inner_sub_handle=create_entity_handle("union_list.inner_sub_handle"))],
        other_union_list=[
            Sub(
                sub_handle=create_entity_handle("other_union_list.sub.sub_handle"),
                inner_sub=InnerSub(
                    inner_sub_handle=create_entity_handle("other_union_list.sub.inner_sub.inner_sub_handle"),
                ),
            ),
            InnerSub(inner_sub_handle=create_entity_handle("other_union_list.inner_sub_handle")),
        ],
        handles_key_dict={
            create_entity_handle("handles_key_dict.key1"): "value1",
            create_entity_handle("handles_key_dict.key2"): "value2",
        },
        pair_of_handles=(
            create_entity_handle("pair_of_handles.handle1"),
            create_entity_handle("pair_of_handles.handle2"),
        ),
        recursive_dict_of_handles=RecursiveDictionaryOfEntityHandles(
            {
                "top": create_entity_handle("recursive_dict_of_handles.top"),
                "nested": RecursiveDictionaryOfEntityHandles(
                    {"nested": create_entity_handle("recursive_dict_of_handles.nested")},
                ),
            },
        ),
    )
    return m


@pytest.fixture
def recursive_model() -> RecursiveTest:
    assert sys.version_info >= (
        3,
        11,
    ), "The recursive_model fixture requires Python 3.11 or higher to support recursive types in pydantic models"
    m = RecursiveTest(
        recursive_thing=RecursiveThing(
            handle=create_entity_handle("recursive_thing_root.handle"),
            children=[
                RecursiveThing(
                    handle=create_entity_handle("recursive_thing_child1.handle"),
                    children=[
                        RecursiveThing(handle=create_entity_handle("recursive_thing_grandchild1.handle")),
                    ],
                ),
                RecursiveThing(handle=create_entity_handle("recursive_thing_child2.handle")),
            ],
        ),
    )
    return m


def test_model_class_is_valid(model: ModelTest):
    model.model_validate(model)


def test_recursive_model_class_is_valid(recursive_model: RecursiveTest):
    recursive_model.model_validate(recursive_model)


def test_recursive_model_class_is_valid_with_gc_disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GLOW_BDM_GC_DISABLED", "True")
    RecursiveTest()  # should not raise


@pytest.mark.parametrize(
    "field_name",
    [
        "handle",
        "handles",
        "handles_dict",
        "sub.sub_handle",
        "sub.inner_sub.inner_sub_handle",
        "list_of_inner_sub.inner_sub_handle1",
        "list_of_inner_sub.inner_sub_handle2",
        "nullable_handle_not_null",
        "nullable_handles_list",
        "union_list.inner_sub_handle",
        "other_union_list.sub.sub_handle",
        "other_union_list.sub.inner_sub.inner_sub_handle",
        "other_union_list.inner_sub_handle",
        "handles_key_dict.key1",
        "handles_key_dict.key2",
        "pair_of_handles.handle1",
        "pair_of_handles.handle2",
        "recursive_dict_of_handles.top",
        "recursive_dict_of_handles.nested",
    ],
)
def test_live_handles_detected(model: ModelTest, field_name: str):
    live_handles = model.live_handles
    expected_handle = create_entity_handle(field_name)
    assert expected_handle in live_handles


@pytest.mark.parametrize(
    "field_name",
    [
        "recursive_thing_root.handle",
        "recursive_thing_child1.handle",
        "recursive_thing_grandchild1.handle",
        "recursive_thing_child2.handle",
    ],
)
def test_live_handles_detected_in_recursive_model(recursive_model: RecursiveTest, field_name: str):
    live_handles = recursive_model.live_handles
    expected_handle = create_entity_handle(field_name)
    assert expected_handle in live_handles


def test_recursive_model_without_handles_does_not_report_having_handle_fields():
    """if this is not true then the GC will redundently traverse recursive
    structures that don't contain handles"""
    model = EmptyRecursiveThing()
    assert not model.has_handle_fields


def test_live_handles_no_entity_not_counted(model: ModelTest):
    assert len(model.live_handles) == 19


def test_recursive_live_handles_no_entity_not_counted(recursive_model: RecursiveTest):
    assert len(recursive_model.live_handles) == 4


bdm_project: dict[str, Any] = {
    "schema_version": 1,
    "solution_name": "BdmSolution",
    "solution": {
        "display_name": "Bdm Solution",
        "version": 1,
        "steps": {
            "bdm_step": {
                "state": {
                    "my_entity": "UPTODATE",
                    "other": "UPTODATE",
                    "result": "OUTOFDATE",
                    "directory": "OUTOFDATE",
                },
                "my_entity": {
                    "is_blob": True,
                    "original_name": "my_entity.json",
                    "entity_id": "94033ee5-6c32-4132-898b-7a8addb3c208",
                    "opaque_identifier": "primary/project_id/bdm/product_aaaaaaaa:_DELIMITERmy_entity.json",
                    "mime_type": "text/plain",
                    "encoding": None,
                    "size": 14,
                },
                "no_entity": {
                    "is_blob": True,
                    "original_name": "",
                    "entity_id": "00000000-0000-0000-0000-000000000000",
                    "opaque_identifier": "",
                    "mime_type": None,
                    "encoding": None,
                    "size": None,
                },
                "other": 0,
                "result": {
                    "is_blob": True,
                    "original_name": "result.txt",
                    "entity_id": "94033ee5-6c38-4132-898b-7a8addb3c208",
                    "opaque_identifier": "primary/project_id/bdm/method_bbbbbbbb:_DELIMITERresult.txt",
                    "mime_type": "text/plain",
                    "encoding": None,
                    "size": 12,
                },
                "list_handles": [
                    {
                        "is_blob": True,
                        "original_name": "a.txt",
                        "entity_id": "aaaabee5-6c38-4132-898b-7a8addb3c208",
                        "opaque_identifier": "primary/project_id/bdm/method_cccccccc:_DELIMITERa.txt",
                        "mime_type": "text/plain",
                        "encoding": None,
                        "size": 12,
                    },
                    {
                        "is_blob": True,
                        "original_name": "b.txt",
                        "entity_id": "bbbb3ee5-6c38-4a32-898b-7a8addb3c208",
                        "opaque_identifier": "primary/project_id/bdm/method_dddddddd:_DELIMITERb.txt",
                        "mime_type": "text/plain",
                        "encoding": None,
                        "size": 12,
                    },
                ],
                "dict_handles": {
                    "handle_one": {
                        "is_blob": True,
                        "original_name": "dict_file.txt",
                        "entity_id": "aaaabee5-6c38-4132-898b-7a8eddb3c208",
                        "opaque_identifier": "primary/project_id/bdm/method_cccccccc:_DELIMITERdict_file.txt",
                        "mime_type": "text/plain",
                        "encoding": None,
                        "size": 12,
                    },
                    "handle_two": {
                        "is_blob": True,
                        "original_name": "dict_file_2.txt",
                        "entity_id": "aaaabee5-6c39-4132-898b-7a8eddb3c208",
                        "opaque_identifier": "primary/project_id/bdm/method_cccccccc:_DELIMITERdict_file_2.txt",
                        "mime_type": "text/plain",
                        "encoding": None,
                        "size": 12,
                    },
                    "no_entity": {
                        "is_blob": True,
                        "original_name": "",
                        "entity_id": "00000000-0000-0000-0000-000000000000",
                        "opaque_identifier": "",
                        "mime_type": None,
                        "encoding": None,
                        "size": None,
                    },
                },
                "dict_int": {"one": 1},
                "sub": {
                    "sub_handle": {
                        "is_blob": True,
                        "original_name": "sub_handle",
                        "entity_id": "aaaabee5-ec38-4132-898b-7a8addb3c208",
                        "opaque_identifier": "primary/project_id/bdm/method_cccccccc:_DELIMITERsub_handle.txt",
                        "mime_type": None,
                        "encoding": None,
                        "size": 100,
                    },
                    "inner_sub": {
                        "inner_sub_handle": {
                            "is_blob": True,
                            "original_name": "inner_sub_handle",
                            "entity_id": "aeaabee5-ec38-4132-898b-7a8addb3c208",
                            "opaque_identifier": "primary/project_id/bdm/method_cccccccc:_DELIMITERinner_sub_handle.txt",  # noqa: E501
                            "mime_type": None,
                            "encoding": None,
                            "size": 100,
                        },
                    },
                },
                "directory": {
                    "is_blob": False,
                    "original_name": "dir",
                    "entity_id": "aaaabee5-6c38-4132-898b-7a8addb3c208",
                    "opaque_identifier": "primary/project_id/bdm/method_eeeeeeee:_DELIMITERdir",
                    "mime_type": None,
                    "encoding": None,
                    "size": 100,
                },
            },
            "other_bdm_step": {
                "state": {},
            },
        },
    },
    "method_states": {
        "bdm_step": {
            "create": {
                "status": "failed",
                "result": None,
                "status_code": 500,
                "exception_message": "The solution encountered an internal error.",
                "exception_stack": None,
            },
        },
    },
    "instances": {
        "bdm_step": {
            "x_y": {
                "name": "projects/66b634db77e87f63301d87f2/steps/instance-step/instances/x-y",
                "pim_name": "instances/x",
                "product_version": "string",
                "service_name": "string",
                "max_execution_time": 7200,
                "recovery_state_info": {
                    "project_file": {
                        "is_blob": True,
                        "original_name": "project.json",
                        "entity_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "opaque_identifier": "primary/project_id/bdm/product_ffffffff:_DELIMITERproject.json",
                        "mime_type": None,
                        "encoding": None,
                        "size": 110,
                    },
                    "no_entity": {
                        "is_blob": True,
                        "original_name": "",
                        "entity_id": "00000000-0000-0000-0000-000000000000",
                        "opaque_identifier": "",
                        "mime_type": None,
                        "encoding": None,
                        "size": None,
                    },
                    "product_list_handles": [
                        {
                            "is_blob": True,
                            "original_name": "from_list_a.txt",
                            "entity_id": "9403bee5-6c38-4132-898b-7aaaaaaaaaaa",
                            "opaque_identifier": "primary/project_id/bdm/product_zzzzzzzz:_DELIMITERfrom_list_a.txt",
                            "mime_type": "text/plain",
                            "encoding": None,
                            "size": 12,
                        },
                        {
                            "is_blob": True,
                            "original_name": "",
                            "entity_id": "00000000-0000-0000-0000-000000000000",
                            "opaque_identifier": "",
                            "mime_type": None,
                            "encoding": None,
                            "size": None,
                        },
                    ],
                    "product_dict_handles": {
                        "handle_one": {
                            "is_blob": True,
                            "original_name": "prod_dict_file.txt",
                            "entity_id": "aaaabee5-6c38-4132-898b-7a8eddb3c298",
                            "opaque_identifier": "primary/project_id/bdm/product_pppppppp:_DELIMITERdict_file_prod.txt",
                            "mime_type": "text/plain",
                            "encoding": None,
                            "size": 12,
                        },
                        "no_entity": {
                            "is_blob": True,
                            "original_name": "",
                            "entity_id": "00000000-0000-0000-0000-000000000000",
                            "opaque_identifier": "",
                            "mime_type": None,
                            "encoding": None,
                            "size": None,
                        },
                    },
                    "product_sub_model": {
                        "sub_handle": {
                            "is_blob": True,
                            "original_name": "prod_sub_handle.txt",
                            "entity_id": "aaaabee5-ec38-4732-898b-7a8a3db3c208",
                            "opaque_identifier": "primary/project_id/bdm/product_zzzzzzzz:_DELIMITERprod_sub_handle.txt",  # noqa: E501
                            "mime_type": None,
                            "encoding": None,
                            "size": 100,
                        },
                    },
                    "random_value": "string",
                },
            },
        },
    },
    "bdm_locks": [],
    "display_name": "test project",
    "date_created": "2024-08-09T17:25:15.772466",
    "date_modified": "2024-08-09T17:26:12.597291",
    "name": "projects/66b634db77e87f63301d87f2",
}


def test_gc_step_live_handles():
    model = ProjectModel[BdmSolution].model_validate(bdm_project)
    live_handles = model.solution.steps.bdm_step.live_handles
    original_names = {live_handle.original_name for live_handle in live_handles}
    assert original_names == {
        "my_entity.json",
        "dir",
        "result.txt",
        "a.txt",
        "b.txt",
        "dict_file.txt",
        "dict_file_2.txt",
        "sub_handle",
        "inner_sub_handle",
    }


def test_gc_all_live_handles():
    model = ProjectModel[BdmSolution].model_validate(bdm_project)
    original_names = {live_handle.original_name for live_handle in model.collect_live_handles()}
    assert original_names == {
        "my_entity.json",
        "dir",
        "result.txt",
        "a.txt",
        "b.txt",
        "dict_file.txt",
        "dict_file_2.txt",
        "sub_handle",
        "inner_sub_handle",
        "from_list_a.txt",
        "prod_dict_file.txt",
        "prod_sub_handle.txt",
    }


@pytest.fixture
def project_files(tmp_path: Path) -> list[Path]:
    files = [
        tmp_path / "project_id" / "bdm" / "product_aaaaaaaa" / "my_entity.json",
        tmp_path / "project_id" / "bdm" / "method_bbbbbbbb" / "result.txt",
        tmp_path / "project_id" / "bdm" / "method_cccccccc" / "a.txt",
        tmp_path / "project_id" / "bdm" / "method_dddddddd" / "b.txt",
        tmp_path / "project_id" / "bdm" / "product_zzzzzzzz" / "from_list_a.txt",
        tmp_path / "project_id" / "bdm" / "product_llllllll" / "extra_file.json",
        tmp_path / "project_id" / "bdm" / "method_cccccccc" / "dict_file.txt",
        tmp_path / "project_id" / "bdm" / "method_cccccccc" / "dict_file_2.txt",
        tmp_path / "project_id" / "bdm" / "product_pppppppp" / "dict_file_prod.txt",
        tmp_path / "project_id" / "bdm" / "product_zzzzzzzz" / "prod_sub_handle.txt",
        tmp_path / "project_id" / "bdm" / "method_cccccccc" / "sub_handle.txt",
        tmp_path / "project_id" / "bdm" / "method_cccccccc" / "inner_sub_handle.txt",
    ]
    for f in files:
        f.parent.mkdir(exist_ok=True, parents=True)
        f.touch()
    folder = tmp_path / "project_id" / "bdm" / "method_eeeeeeee" / "dir"
    folder.mkdir(exist_ok=True, parents=True)
    files.append(folder)
    return files


@pytest.fixture
def storage_scope(tmp_path: Path) -> Generator[IStorageScope]:
    primary_factory = create_shared_storage_factory()
    storage_factory = MultiplexorStorageScopeFactory(primary_factory, {})
    project_id = "project_id"
    template_vars = {
        ROOT: str(tmp_path),
        PROJECT_ID: project_id,
        SHORTID: random_shortid(),
    }
    with storage_factory.create_storage_scope(GC_CONTEXT, template_vars) as scope:
        yield scope


def test_gc_destroy_unreferenced_files_keep_live_handles(
    storage_scope: IStorageScope,
    project_files: list[Path],
):
    model = ProjectModel[BdmSolution].model_validate(bdm_project)
    unreferenced_entities = storage_scope.get_unreferenced_entities(PROJECT_BOUNDARY, model.collect_live_handles())
    storage_scope.destroy(*unreferenced_entities)
    assert all(f.exists() for f in project_files if f.name != "extra_file.json")


def test_gc_destroy_only_solution_live_handles(storage_scope: IStorageScope, project_files: list[Path]):
    model = ProjectModel[BdmSolution].model_validate(bdm_project)
    live_handles = model.solution.steps.bdm_step.live_handles
    unreferenced_entities = storage_scope.get_unreferenced_entities(PROJECT_BOUNDARY, live_handles)
    storage_scope.destroy(*unreferenced_entities)
    existing_files = [f.name for f in project_files if f.exists()]
    assert {
        "my_entity.json",
        "result.txt",
        "a.txt",
        "b.txt",
        "dir",
        "dict_file.txt",
        "dict_file_2.txt",
        "sub_handle.txt",
        "inner_sub_handle.txt",
    } == set(
        existing_files,
    )


def test_gc_destroy_all_files_when_live_handles_empty(
    storage_scope: IStorageScope,
    project_files: list[Path],
):
    unreferenced_entities = storage_scope.get_unreferenced_entities(PROJECT_BOUNDARY, [])
    storage_scope.destroy(*unreferenced_entities)
    assert all(not f.exists() for f in project_files)


def test_expired_locks_removed_on_startup(
    monkeypatch: pytest.MonkeyPatch,
    mock_datetime_on_relational: Callable[[], AbstractContextManager[Any]],
):
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", bdm_solution.__name__)
    app = create_app(Settings.model_validate({}))

    with TestClient(app) as client, mock_datetime_on_relational():
        response = client.post("/projects", json={"display_name": "test_project"})
        response.raise_for_status()
        project = response.json()

        response = client.post(f"{project['name']}/bdm-locks")
        response.raise_for_status()
        expired_lock_id = response.json()["id"]

        response = client.get(f"{project['name']}/bdm-locks/{expired_lock_id}")
        response.raise_for_status()

    with TestClient(app) as client:
        response = client.get(f"{project['name']}/bdm-locks/{expired_lock_id}")
        assert response.status_code == 404
