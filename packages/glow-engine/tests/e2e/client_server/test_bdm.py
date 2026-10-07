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
import re
import shutil

import httpx2
import pytest

from ansys.bdm.api import (
    NO_ENTITY,
    CannotGenerateStreamForDirectoryError,
    EntityNotFoundInBlobStorageError,
    NotFoundInLocalStorageRootError,
)
from ansys.saf.glow._bdm.storage_contexts import CLIENT_CONTEXT, METHOD_CONTEXT
from ansys.saf.glow.client import Client, InternalSolutionException, NotFoundException
from ansys.saf.glow.solution import EntityHandle
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, ProjectFixture
from tests.conftest import SOLUTIONS_MOCKS_DIR
from tests.mocks.solutions.bdm_solution import BdmSolution, InnerSubModel, SubModel

pytestmark = pytest.mark.parametrize("solution_type", [BdmSolution], indirect=True)

BDM_NO_ENTITY_ERROR_MSG = "entity does not exist"
METHOD_TIMEOUT = 30


def assert_no_entity_and_no_files(handle: EntityHandle, project_files_dir: Path):
    assert handle == NO_ENTITY
    assert len(list(project_files_dir.iterdir())) == 0


def assert_entity_handle_is_created(handle: EntityHandle, original_name: str):
    assert handle != NO_ENTITY
    assert handle.original_name == original_name


def test_bdm_store_result(
    function_project: ProjectFixture[BdmSolution],
):
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert step.result == NO_ENTITY
    assert len(list(function_project.project_files_dir.iterdir())) == 0
    # WHEN - entity handle is stored in a transaction
    step.store_result()
    # THEN - the file and the entity handle have been created
    assert step.result != NO_ENTITY
    assert step.result.original_name == "result.txt"
    result_file = next(function_project.project_files_dir.rglob("result.txt"))
    # AND - it is stored in the right place
    assert re.search(rf"{METHOD_CONTEXT}_\w{{8}}/result.txt", result_file.as_posix())
    # AND - it has the right content
    assert result_file.read_text() == "hello world!"


def test_bdm_store_entity_in_list(
    function_project: ProjectFixture[BdmSolution],
):
    """
    Test that entity handles can be stored within a list within a field.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert step.list_handles == []
    assert len(list(function_project.project_files_dir.iterdir())) == 0
    # WHEN - list handle is stored in a transaction
    step.store_list_handles()
    # THEN - the file and the entity handle have been created
    assert step.list_handles[0] != NO_ENTITY
    assert step.list_handles[0].original_name == "list_handles.txt"
    list_file = next(function_project.project_files_dir.rglob("list_handles.txt"))
    # AND - it has the right content
    assert list_file.read_text() == "list_handles.txt"


def test_bdm_store_entity_handle_list_read_from_client(
    function_project: ProjectFixture[BdmSolution],
):
    """
    Test that when storing an entity handle into a step field being a list of entity handles,
    the entity handles can be read by the client storage scope.
    """
    step = function_project.project.steps.bdm_step
    # WHEN: running a transaction storing an entity handle in a list of entity handles
    step.store_list_handles()
    # THEN: the entity handle can be accessed by a client storage scope
    scope = function_project.project.storage_scope
    assert scope.get_text(step.list_handles[0]) == "list_handles.txt"


def test_bdm_store_entity_handle_list_read_from_client_without_context_mgr(
    function_project_without_context_mgr: ProjectFixture[BdmSolution],
):
    """
    Test that when storing an entity handle into a step field being a list of entity handles,
    the entity handles can be read by the client storage scope.
    """
    step = function_project_without_context_mgr.project.steps.bdm_step
    # WHEN: running a transaction storing an entity handle in a list of entity handles
    step.store_list_handles()
    # THEN: the entity handle can be accessed by a client storage scope
    with function_project_without_context_mgr.project.get_storage_scope() as scope:
        assert scope.get_text(step.list_handles[0]) == "list_handles.txt"


def test_bdm_store_entity_in_dict(
    function_project: ProjectFixture[BdmSolution],
):
    """
    Test that entity handles can be stored within a dictionary within a field.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert step.dict_handles == {}
    assert len(list(function_project.project_files_dir.iterdir())) == 0
    # WHEN - dict handle is stored in a transaction
    step.store_dict_handles()
    # THEN - the file and the entity handle have been created
    assert step.dict_handles != NO_ENTITY
    assert step.dict_handles["dict_handle"].original_name == "dict_handles.txt"
    dict_file = next(function_project.project_files_dir.rglob("dict_handles.txt"))
    # AND - it has the right content
    assert dict_file.read_text() == "dict_handles.txt"


def test_bdm_gc_store_entity_handle_dict_read_from_client(
    function_project: ProjectFixture[BdmSolution],
):
    """
    Test that when storing an entity handle into a step field being a dict of entity handles,
    the entity handles can be read by the client storage scope.
    """
    step = function_project.project.steps.bdm_step
    # WHEN: running a transaction storing a dict of entity handles
    step.store_dict_handles()
    # THEN: the entity handle can be accessed by a client storage scope
    scope = function_project.project.storage_scope
    assert scope.get_text(step.dict_handles["dict_handle"]) == "dict_handles.txt"


def test_bdm_gc_store_entity_handle_dict_read_from_client_without_context_mgr(
    function_project_without_context_mgr: ProjectFixture[BdmSolution],
):
    """
    Test that when storing an entity handle into a step field being a dict of entity handles,
    the entity handles can be read by the client storage scope.
    """
    step = function_project_without_context_mgr.project.steps.bdm_step
    # WHEN: running a transaction storing a dict of entity handles
    step.store_dict_handles()
    # THEN: the entity handle can be accessed by a client storage scope
    with function_project_without_context_mgr.project.get_storage_scope() as scope:
        assert scope.get_text(step.dict_handles["dict_handle"]) == "dict_handles.txt"


def test_bdm_store_entity_in_submodel(
    function_project: ProjectFixture[BdmSolution],
):
    """
    Test that entity handles can be stored within a custom model within a field.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert step.sub.sub_handle == NO_ENTITY
    assert len(list(function_project.project_files_dir.iterdir())) == 0
    # WHEN - sub model entity handle is stored in a transaction
    step.store_sub_model()
    # THEN - the file and the entity handle have been created
    assert step.sub.sub_handle != NO_ENTITY
    assert step.sub.sub_handle.original_name == "sub.txt"
    sub_file = next(function_project.project_files_dir.rglob("sub.txt"))
    # AND - it has the right content
    assert sub_file.read_text() == "sub"
    # THEN - the file and the entity handle have been created
    assert step.sub.inner_sub.inner_sub_handle != NO_ENTITY
    assert step.sub.inner_sub.inner_sub_handle.original_name == "inner_sub.txt"
    inner_sub_file = next(function_project.project_files_dir.rglob("inner_sub.txt"))
    # AND - it has the right content
    assert inner_sub_file.read_text() == "inner_sub"


def test_bdm_store_entity_handle_sub_read_from_client(
    function_project: ProjectFixture[BdmSolution],
):
    """
    Test that when storing an entity handle into a step field being a sub model containing
    entity handles, the entity handles can be read by the client storage scope.
    """
    step = function_project.project.steps.bdm_step
    # WHEN: running a transaction storing a sub model containing entity handle
    step.store_sub_model()
    # THEN: the entity handle can be accessed by a client storage scope
    scope = function_project.project.storage_scope
    assert scope.get_text(step.sub.sub_handle) == "sub"
    assert scope.get_text(step.sub.inner_sub.inner_sub_handle) == "inner_sub"


def test_bdm_store_entity_handle_sub_read_from_client_without_context_mgr(
    function_project_without_context_mgr: ProjectFixture[BdmSolution],
):
    """
    Test that when storing an entity handle into a step field being a sub model containing
    entity handles, the entity handles can be read by the client storage scope.
    """
    step = function_project_without_context_mgr.project.steps.bdm_step
    # WHEN: running a transaction storing a sub model containing entity handle
    step.store_sub_model()
    # THEN: the entity handle can be accessed by a client storage scope
    with function_project_without_context_mgr.project.get_storage_scope() as scope:
        assert scope.get_text(step.sub.sub_handle) == "sub"
        assert scope.get_text(step.sub.inner_sub.inner_sub_handle) == "inner_sub"


def test_bdm_store_result_and_return_stored_entities(function_project: ProjectFixture[BdmSolution]):
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # WHEN - entity handle is stored in a transaction
    stored_entities = step.store_result_and_return_stored_entities()
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.result, "result.txt")
    # AND - there is only one stored entity
    assert len(stored_entities) == 1
    # AND - there is only one file and it is stored in the right place
    txt_files = list(function_project.project_files_dir.rglob("*.txt"))
    assert len(txt_files) == 1
    assert re.search(rf"{METHOD_CONTEXT}_\w{{8}}/result.txt", txt_files[0].as_posix())
    # AND - no other directory has been created
    assert len(list(function_project.project_files_dir.iterdir())) == 1
    # AND - the file has the right content
    assert txt_files[0].read_text() == "hello world!"


def test_bdm_store_result_get_text_from_client(function_project: ProjectFixture[BdmSolution]):
    """
    Test that entity handle can be stored on transaction and read from the client.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # WHEN - entity handle is stored in a transaction
    step.store_result()
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.result, "result.txt")
    # AND - the content can be accessed through get_text from the client
    storage_scope = function_project.project.storage_scope
    text = storage_scope.get_text(step.result)
    assert text == "hello world!"


def test_bdm_store_result_get_text_from_transaction(function_project: ProjectFixture[BdmSolution]):
    """
    Test that entity handle can be stored on transaction and read from the long
    running transaction.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # WHEN - entity handle is stored in a transaction
    step.store_result()
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.result, "result.txt")
    # AND - the content can be accessed through get_text from the transaction
    text = step.get_text_result_long_running().wait(timeout=METHOD_TIMEOUT)
    assert text == "hello world!"


def test_bdm_store_from_transaction_get_cached_from_client(function_project: ProjectFixture[BdmSolution]):
    """
    Test that entity handle can be stored on transaction and accessed
    from client storage scope.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # WHEN - entity handle is stored in a transaction
    step.store_result()
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.result, "result.txt")
    storage_scope = function_project.project.storage_scope
    path = storage_scope.get_cached(step.result)
    # AND - the file it is stored in the right place
    assert path.exists()
    assert path.name == "result.txt"
    # AND - it has the right content
    assert path.read_text() == "hello world!"


def test_bdm_store_from_transaction_get_cached_from_client_without_mgr(
    function_project_without_context_mgr: ProjectFixture[BdmSolution],
):
    # GIVEN - no entity handle and no files
    step = function_project_without_context_mgr.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project_without_context_mgr.project_files_dir)
    # WHEN - entity handle is stored in a transaction
    step.store_result()
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.result, "result.txt")
    with function_project_without_context_mgr.project.get_storage_scope() as storage_scope:
        path = storage_scope.get_cached(step.result)
        # AND - the file it is stored in the right place
        assert path.exists()
        assert path.name == "result.txt"
        # AND - it has the right content
        assert path.read_text() == "hello world!"


def test_bdm_store_from_client_get_cached_from_transaction(function_project: ProjectFixture[BdmSolution]):
    """
    Test that entity handle can be stored from the client storage scope
    and accessed from the transaction.
    """

    # GIVEN - a file stored using the client storage scope
    step = function_project.project.steps.bdm_step
    storage_scope = function_project.project.storage_scope
    result_txt = storage_scope.get_storage_root() / "result.txt"
    result_txt.write_text("hello there!")
    handle = storage_scope.store(result_txt)
    # AND - assigning the handle to a step field
    step.result = handle
    # WHEN - using the handle from within the transaction
    stored_result_path = step.get_cached_result()
    # THEN - the entity handle resolves to the right place
    assert stored_result_path == result_txt


def test_bdm_store_from_client_without_context_mgr_get_cached_from_transaction(
    function_project_without_context_mgr: ProjectFixture[BdmSolution],
):
    # GIVEN - a file stored using the client storage scope
    step = function_project_without_context_mgr.project.steps.bdm_step
    with function_project_without_context_mgr.project.get_storage_scope() as storage_scope:
        result_txt = storage_scope.get_storage_root() / "result.txt"
        result_txt.write_text("hello there!")
        handle = storage_scope.store(result_txt)
        # AND - assigning the handle to a step field
        step.result = handle
    # WHEN - using the handle from within the transaction
    stored_result_path = step.get_cached_result()
    # THEN - the entity handle resolves to the right place
    assert stored_result_path == result_txt


def test_bdm_store_directory_from_transaction_get_children_from_client(function_project: ProjectFixture[BdmSolution]):
    """
    Test that entity handle directory can be stored on transaction and children accessed
    from client storage scope.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # WHEN - storing a directory as entity handle within a transaction
    step.store_directory_in_entity_handle()
    # THEN - the entity handle has been set
    assert_entity_handle_is_created(step.directory, "top")
    # WHEN - accessing the entity handle children from the client
    storage_scope = function_project.project.storage_scope
    children = storage_scope.get_children(step.directory)
    # THEN - the children can be accessed
    assert len(children) == 2
    assert {child.original_name for child in children} == {"empty", "subtop"}
    storage_scope = function_project.project.storage_scope
    parent = storage_scope.get_parent(children[0])
    assert parent.original_name == "top"  # pyright: ignore[reportOptionalMemberAccess]


def test_bdm_store_directory_from_client_get_child_from_transaction(function_project: ProjectFixture[BdmSolution]):
    """
    Test that entity handle directory can be stored on transaction and child accessed
    from client storage scope.
    """
    # GIVEN - directory entity handle created on the client
    step = function_project.project.steps.bdm_step
    storage_scope = function_project.project.storage_scope
    root = storage_scope.get_storage_root()
    top = root / "top"
    top.mkdir(exist_ok=True, parents=True)
    (top / "empty").mkdir()
    subtop = top / "subtop"
    subtop.mkdir()
    leaf = subtop / "leaf.txt"
    leaf.write_text("hello world!")
    directory_handle = storage_scope.store(top)
    # AND - assigning the entity handle to the step field
    step.directory = directory_handle
    # THEN - get_child can be used on the entity handle step field within a transaction
    child_handle = step.get_directory_child()
    # AND - the child handle has the right values
    assert_entity_handle_is_created(child_handle, "empty")


def test_bdm_store_file_from_client_get_parent_from_transaction(function_project: ProjectFixture[BdmSolution]):
    """
    Test that entity handle can be stored from client storage scope
    and its parent can be accessed from a transaction.
    """
    # GIVEN - a file entity handle created on the client
    step = function_project.project.steps.bdm_step
    storage_scope = function_project.project.storage_scope
    root = storage_scope.get_storage_root()
    tree = root / "tree"
    tree.mkdir(exist_ok=True, parents=True)
    leaf = tree / "leaf.txt"
    leaf.write_text("hello world!")
    file_handle = storage_scope.store(leaf)
    step.file = file_handle
    # THEN - get_parent can be used in a transaction to create an entity handle of the parent directory
    step.get_directory_parent()
    # AND - the parent handle has the right values
    assert_entity_handle_is_created(step.directory, "tree")  # pyright: ignore[reportArgumentType]


def test_bdm_store_file_from_client_without_context_mgr_get_parent_from_transaction(
    function_project_without_context_mgr: ProjectFixture[BdmSolution],
):
    """
    Test that entity handle can be stored from client storage scope
    without context manager and that and its parent can be accessed from a transaction.
    """
    # GIVEN - a file entity handle created on the client
    step = function_project_without_context_mgr.project.steps.bdm_step
    with function_project_without_context_mgr.project.get_storage_scope() as storage_scope:
        root = storage_scope.get_storage_root()
        tree = root / "tree"
        tree.mkdir(exist_ok=True, parents=True)
        leaf = tree / "leaf.txt"
        leaf.write_text("hello world!")
        file_handle = storage_scope.store(leaf)
        step.file = file_handle
    # THEN - get_parent can be used in a transaction to create an entity handle of the parent directory
    step.get_directory_parent()
    # AND - the parent handle has the right values
    assert_entity_handle_is_created(step.directory, "tree")  # pyright: ignore[reportArgumentType]


def test_bdm_store_file_from_transaction_get_parent_from_client(function_project: ProjectFixture[BdmSolution]):
    """
    Test that entity handle can be stored from a transaction
    and its parent can be accessed from the client storage scope.
    """
    # GIVEN - a file entity handle created on the client
    step = function_project.project.steps.bdm_step
    # WHEN - storing a file as entity handle within a transaction
    step.store_file_in_entity_handle()
    # THEN - the entity handle has been set
    assert_entity_handle_is_created(step.file, "leaf.txt")
    # THEN - get_parent can be used from the client to create an entity handle of the parent directory
    storage_scope = function_project.project.storage_scope
    tree = storage_scope.get_parent(step.file)
    # AND - the parent handle has the right values
    assert_entity_handle_is_created(tree, "tree")  # pyright: ignore[reportArgumentType]


def test_bdm_store_result_long_running_get_cached_from_client(function_project: ProjectFixture[BdmSolution]):
    """
    Test that entity handle can be stored from a long running transaction
    and it can be accessed from the client storage scope.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # WHEN - entity handle is stored in a long running transaction
    step.store_result_long_running().wait()
    # THEN - the entity handle has the right values
    assert_entity_handle_is_created(step.result, "result.txt")
    # AND - the content can be accessed using the client storage scope
    storage_scope = function_project.project.storage_scope
    path = storage_scope.get_cached(step.result)
    text = storage_scope.get_text(step.result)
    assert path.exists()
    assert path.name == "result.txt"
    assert text == "hello world!"


def test_bdm_store_from_client_get_cached_long_running_from_transaction(function_project: ProjectFixture[BdmSolution]):
    """
    Test that entity handle can be stored from the client storage scope
    and it can be accessed from the long running transaction.
    """
    # GIVEN - an entity handle stored using the client storage scope
    step = function_project.project.steps.bdm_step
    storage_scope = function_project.project.storage_scope
    result_txt = storage_scope.get_storage_root() / "result.txt"
    result_txt.write_text("hello there!")
    handle = storage_scope.store(result_txt)
    # AND - assigning the handle to a step field
    step.result = handle
    # WHEN - resolving the file path from the long running transaction
    stored_result_path = step.get_cached_result_long_running().wait()
    # THEN - the file path is the same on both side
    assert stored_result_path == result_txt


def test_bdm_store_stream_from_transaction(function_project: ProjectFixture[BdmSolution]):
    # GIVEN - a transaction storing a stream using bdm
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # WHEN - executing the transaction
    step.store_stream()
    # THEN - the file has been created
    txt_files = [f for f in function_project.project_files_dir.rglob("*") if f.is_file()]
    assert len(txt_files) == 1
    # AND - it is stored in the right place with a random name as we have not provided one
    uuid_regex = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    assert re.search(rf"{METHOD_CONTEXT}_\w{{8}}/{uuid_regex}", txt_files[0].as_posix())
    # AND - it has the right content
    assert txt_files[0].read_text() == "hello world!"


def test_bdm_store_stream_from_client(function_project: ProjectFixture[BdmSolution]):
    """
    Test that the client storage scope can store a stream within an entity handle.
    """
    # GIVEN - a transaction storing a stream using bdm
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # WHEN - executing store_stream from the client
    storage_scope = function_project.project.storage_scope
    step.result = storage_scope.store_stream(b"hello world!", relative_location=Path("result.txt"))
    # THEN - the file has been created
    txt_files = [f for f in function_project.project_files_dir.rglob("*") if f.is_file()]
    assert len(txt_files) == 1
    # AND - it is stored in the right place with a random name as we have not provided one
    assert re.search(rf"{CLIENT_CONTEXT}_\w{{8}}/result.txt", txt_files[0].as_posix())
    # AND - it has the right content
    assert txt_files[0].read_text() == "hello world!"


def test_bdm_begin_store_from_transaction(function_project: ProjectFixture[BdmSolution]):
    # GIVEN - a transaction storing a stream using bdm
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # WHEN - executing the transaction
    step.begin_store_result()
    # THEN - the entity handle has been created
    assert step.result != NO_ENTITY
    # AND - there is only one file and it is stored in the right place with the provided name
    txt_files = list(function_project.project_files_dir.rglob("*.txt"))
    assert len(txt_files) == 1
    assert re.search(rf"{METHOD_CONTEXT}_\w{{8}}/result.txt", txt_files[0].as_posix())
    # AND - no other directory has been created
    assert len(list(function_project.project_files_dir.iterdir())) == 1
    # AND - the file has the right content
    assert txt_files[0].read_text() == "hello world!"


def test_bdm_begin_store_from_client(function_project: ProjectFixture[BdmSolution]):
    """
    Test that the client storage scope can store a file using begin_store.
    """
    # GIVEN - a transaction storing a stream using bdm
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # WHEN - executing store_stream from the client
    storage_scope = function_project.project.storage_scope
    with storage_scope.begin_store(relative_location=Path("result.txt")) as writer:
        writer.stream.write(b"hello world!")
    step.result = writer.handle
    # THEN - the file has been created
    txt_files = [f for f in function_project.project_files_dir.rglob("*") if f.is_file()]
    assert len(txt_files) == 1
    # AND - it is stored in the right place with a random name as we have not provided one
    assert re.search(rf"{CLIENT_CONTEXT}_\w{{8}}/result.txt", txt_files[0].as_posix())
    # AND - it has the right content
    assert txt_files[0].read_text() == "hello world!"


def test_get_copy_in_transaction(function_project: ProjectFixture[BdmSolution], tmp_path: Path):
    # GIVEN - a transaction storing a stream using bdm
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # WHEN - entity handle is stored in a transaction
    step.store_result()
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.result, "result.txt")
    # WHEN - copying the created file to another location
    destination_file = tmp_path / "result.txt"
    assert not destination_file.exists()
    step.get_copy_result(destination=str(destination_file))
    # THEN - the file exists in the new location
    assert destination_file.exists()
    # AND - has the right content
    assert destination_file.read_text() == "hello world!"


def test_get_copy_in_client(function_project: ProjectFixture[BdmSolution]):
    """
    Test that the client storage scope can copy a file using get_copy.
    """
    # GIVEN - a transaction storing a stream using bdm
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # WHEN - entity handle is stored in the client storage space
    storage_scope = function_project.project.storage_scope
    root = storage_scope.get_storage_root()
    origin = root / "origin"
    origin.mkdir(exist_ok=True, parents=True)
    origin_file = origin / "result.txt"
    origin_file.write_text("hello there!")
    step.result = storage_scope.store(origin_file)
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.result, "result.txt")
    # WHEN - copying the created file to another location in the same storage scope
    destination = root / "destination"
    destination.mkdir(exist_ok=True, parents=True)
    destination_file = destination / "result.txt"
    storage_scope.get_copy(step.result, destination_file)
    # THEN - the file exists in the client storage space
    assert destination_file.exists()
    # AND - has the right content
    assert destination_file.read_text() == "hello there!"


def test_get_stream_in_transaction(function_project: ProjectFixture[BdmSolution]):
    # GIVEN - a transaction storing a stream using bdm
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # WHEN - entity handle is stored in a transaction
    step.store_result()
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.result, "result.txt")
    # AND - can be streamed and the content is correct
    assert step.get_stream_result() == "hello world!"


def test_get_stream_in_client(function_project: ProjectFixture[BdmSolution]):
    """
    Test that the client storage scope can stream the content of an entity handle.
    """
    # GIVEN - a transaction storing a stream using bdm
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    storage_scope = function_project.project.storage_scope
    result_txt = storage_scope.get_storage_root() / "result.txt"
    result_txt.write_text("hello there!")
    step.result = storage_scope.store(result_txt)
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.result, "result.txt")
    # AND - can be streamed ad the content is correct
    assert storage_scope.get_stream(step.result).readall().decode() == "hello there!"


def test_bdm_store_list_handle_from_client_read_from_transaction(function_project: ProjectFixture[BdmSolution]):
    """
    Test that list of entity handles can be stored in a step field from the client and that its content
    can be retrieved from a transaction method
    """
    step = function_project.project.steps.bdm_step
    storage_scope = function_project.project.storage_scope
    result_txt = storage_scope.get_storage_root() / "result.txt"
    result_txt.write_text("hello there!")
    handle = storage_scope.store(result_txt)
    step.list_handles = [handle]
    assert step.get_text_first_item_list_handles() == "hello there!"


def test_bdm_store_dict_handle_from_client_read_from_transaction(function_project: ProjectFixture[BdmSolution]):
    """
    Test that a dict of entity handles can be stored in a step field from the client and that its content
    can be retrieved from a transaction method
    """
    step = function_project.project.steps.bdm_step
    storage_scope = function_project.project.storage_scope
    result_txt = storage_scope.get_storage_root() / "result.txt"
    result_txt.write_text("hello there!")
    handle = storage_scope.store(result_txt)
    step.dict_handles = {"dict_handle": handle}
    assert step.get_text_handle_item_dict_handles() == "hello there!"


def test_bdm_store_sub_model_from_client_read_from_transaction(function_project: ProjectFixture[BdmSolution]):
    """
    Test that sub models containing entity handles can be stored in a step field from the client and that its content
    can be retrieved from a transaction method
    """
    step = function_project.project.steps.bdm_step
    storage_scope = function_project.project.storage_scope
    sub_file = storage_scope.get_storage_root() / "sub.txt"
    sub_file.write_text("sub")
    sub_handle = storage_scope.store(sub_file)
    inner_sub_file = storage_scope.get_storage_root() / "inner_sub.txt"
    inner_sub_file.write_text("inner_sub")
    inner_sub_handle = storage_scope.store(inner_sub_file)
    sub = SubModel(sub_handle=sub_handle, inner_sub=InnerSubModel(inner_sub_handle=inner_sub_handle))
    step.sub = sub
    assert step.get_text_sub_handle() == "sub"
    assert step.get_text_inner_sub_handle() == "inner_sub"


def test_bdm_delete_result(function_project: ProjectFixture[BdmSolution]):
    # GIVEN - an entity handle stored
    step = function_project.project.steps.bdm_step
    step.store_result()
    result_txt = list(function_project.project_files_dir.rglob("result.txt"))[0]
    assert result_txt.exists()
    # WHEN - replacing the entity handle by NO_ENTITY
    step.delete_result()
    # THEN - the new entity handle is NO_ENTITY
    assert step.result == NO_ENTITY
    # AND - the file is deleted by the garbage collection
    assert not result_txt.exists()


def test_import_exported_bdm_project_can_resolve_entity_handle(
    session_glow: GlowBaseProcess[BdmSolution],
    function_project: ProjectFixture[BdmSolution],
    tmp_path: Path,
):
    # GIVEN - an entity handle stored in a step field
    function_project.project.steps.bdm_step.store_result()
    # AND - the project is exported
    function_project.project.export(tmp_path)
    safx_path = tmp_path / f"{function_project.project.project_display_name}.safx"
    assert safx_path.exists()
    # WHEN - project is imported
    project_name = "imported_project"
    with Client(session_glow.solution_type, session_glow.base_api_url) as client:
        project = client.import_project(Path(safx_path), project_name)
        # THEN - entity handled can be resolved properly
        result_path = project.steps.bdm_step.get_cached_result()
        assert result_path.exists()
        assert result_path.read_text() == "hello world!"


def test_bdm_store_two_times(function_project: ProjectFixture[BdmSolution]):
    """
    Test that storing entity handles twice using two transactions creates
    two distinct files in the storage root.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # GIVEN - a file entity handle stored in a step field from a transaction
    first_entity = step.store_result_and_return_stored_entities()[0]
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.result, "result.txt")
    # AND - it is possible to store it again in the same storage scope
    second_entity = step.store_result_and_return_stored_entities()[0]
    # AND - there are two different files
    storage_scope = function_project.project.storage_scope
    with pytest.raises(EntityNotFoundInBlobStorageError, match=BDM_NO_ENTITY_ERROR_MSG):
        assert storage_scope.get_cached(first_entity)
    assert storage_scope.get_cached(second_entity).exists()


def test_bdm_store_same_handle_in_two_fields_modify_one_of_the_fields(function_project: ProjectFixture[BdmSolution]):
    """
    Test that storing same entity handle in two step fields and modifying one doesn't
    affect the initial one.
    """
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # GIVEN - a file entity handle stored in a step field from a transaction
    step.store_two_results()
    # THEN - the entity handle has been created and stored in two different step fields
    assert_entity_handle_is_created(step.result, "result.txt")
    assert_entity_handle_is_created(step.another_result, "result.txt")
    storage_scope = function_project.project.storage_scope
    # AND - there is only one file
    assert storage_scope.get_cached(step.result) == storage_scope.get_cached(step.another_result)
    # WHEN - uploading another entity to only one of these step fields
    step.store_another_result()
    # THEN - there are two different files with different content
    assert storage_scope.get_cached(step.result) != storage_scope.get_cached(step.another_result)
    assert storage_scope.get_text(step.result) != storage_scope.get_text(step.another_result)


def test_bdm_get_cached_exception_with_no_entity(function_project: ProjectFixture[BdmSolution]):
    """
    Test that given no entity handle and no files, then get_cached raised an error.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    storage_scope = function_project.project.storage_scope
    # THEN - get_cached raises an error
    with pytest.raises(EntityNotFoundInBlobStorageError):
        storage_scope.get_cached(step.result)


def test_bdm_get_copy_exception_with_no_entity(function_project: ProjectFixture[BdmSolution]):
    """
    Test that given no entity handle and no files, then get_copy raised an error.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    storage_scope = function_project.project.storage_scope
    # THEN - get_copy raises an error
    destination = storage_scope.get_storage_root() / "result_copy.txt"
    with pytest.raises(EntityNotFoundInBlobStorageError):
        storage_scope.get_copy(step.result, destination)


def test_bdm_get_stream_exception_with_no_entity(function_project: ProjectFixture[BdmSolution]):
    """
    Test that given no entity handle and no files, then get_stream raised an error.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    storage_scope = function_project.project.storage_scope
    # THEN - get_stream raises an error
    with pytest.raises(EntityNotFoundInBlobStorageError):
        storage_scope.get_stream(step.result)


def test_bdm_get_parent_exception_with_no_entity(function_project: ProjectFixture[BdmSolution]):
    """
    Test that given no entity handle and no files, then get_parent raised an error.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    storage_scope = function_project.project.storage_scope
    # THEN - get_parent raises an error
    with pytest.raises(EntityNotFoundInBlobStorageError):
        storage_scope.get_parent(step.result)


def test_bdm_get_children_exception_with_file_entity(function_project: ProjectFixture[BdmSolution]):
    """
    Test that get_children raises an exception when the entity is a file.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # GIVEN - a file entity handle stored in a step field
    step.store_result()
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.result, "result.txt")
    storage_scope = function_project.project.storage_scope
    # AND - get_children raises an error because the entity is a file
    with pytest.raises(NotADirectoryError):
        storage_scope.get_children(step.result)


def test_bdm_get_child_exception_with_file_entity(function_project: ProjectFixture[BdmSolution]):
    """
    Test that get_child raises an exception when the entity is a file.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # GIVEN - a file entity handle stored in a step field
    step.store_result()
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.result, "result.txt")
    storage_scope = function_project.project.storage_scope
    # AND - get_child raises an error because the entity is a file
    with pytest.raises(NotADirectoryError):
        storage_scope.get_child(step.result, "random_name")


def test_bdm_get_cached_exception_with_removed_entity_file(function_project: ProjectFixture[BdmSolution]):
    """
    Test that get_cached raises an exception with removed entity file.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # GIVEN - a file entity handle stored in a step field
    step.store_result()
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.result, "result.txt")
    storage_scope = function_project.project.storage_scope
    # WHEN - the file is removed
    result_path = storage_scope.get_cached(step.result)
    result_path.unlink()
    # THEN - get_cached raises an error despite the EntityHandle object existing
    with pytest.raises(EntityNotFoundInBlobStorageError):
        storage_scope.get_cached(step.result)


def test_bdm_get_parent_exception_with_removed_entity_file(function_project: ProjectFixture[BdmSolution]):
    """
    Test that get_parent raises an exception with removed entity file.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # GIVEN - a file entity handle stored in a step field
    step.store_result()
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.result, "result.txt")
    storage_scope = function_project.project.storage_scope
    # WHEN - the file is removed
    result_path = storage_scope.get_cached(step.result)
    result_path.unlink()
    # THEN - get_parent raises an error despite the EntityHandle object existing
    with pytest.raises(EntityNotFoundInBlobStorageError):
        storage_scope.get_parent(step.result)


def test_bdm_get_stream_exception_with_directory_entity(function_project: ProjectFixture[BdmSolution]):
    """
    Test that get_stream raises an exception with directory entity.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # GIVEN - a directory entity handle stored in a step field
    step.store_directory_in_entity_handle()
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.directory, "top")
    storage_scope = function_project.project.storage_scope
    # AND - get_stream raises an error because the entity is a directory
    with pytest.raises(CannotGenerateStreamForDirectoryError):
        storage_scope.get_stream(step.directory)


def test_bdm_get_children_exception_with_removed_entity_directory(function_project: ProjectFixture[BdmSolution]):
    """
    Test that get_children raises an exception with removed directory entity.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # GIVEN - a directory entity handle stored in a step field
    step.store_directory_in_entity_handle()
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.directory, "top")
    storage_scope = function_project.project.storage_scope
    # WHEN - the directory is removed
    directory_path = storage_scope.get_cached(step.directory)
    shutil.rmtree(directory_path)
    # THEN - get_children raises an error despite the EntityHandle object existing
    with pytest.raises(EntityNotFoundInBlobStorageError):
        storage_scope.get_children(step.directory)


def test_bdm_get_children_exception_with_file_entity_long_running(function_project: ProjectFixture[BdmSolution]):
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # GIVEN - a file entity handle stored in a step field
    step.store_result()
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.result, "result.txt")
    # AND - get_children raises an error because the entity is a file but we get an InternalSolutionException
    # as this is happening in the server side.
    with pytest.raises(InternalSolutionException):
        step.raise_not_a_directory_error_long_running().wait()


def test_bdm_store_in_a_second_scope_exception(function_project: ProjectFixture[BdmSolution]):
    """
    Test that storing an entity in a second storage scope raises an exception.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # GIVEN - a file entity handle stored in a step field from a transaction
    step.store_result()
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.result, "result.txt")
    storage_scope = function_project.project.storage_scope
    result_path = storage_scope.get_cached(step.result)
    # AND - store raises an error because it is already stored in the transaction storage scope
    with pytest.raises(NotFoundInLocalStorageRootError):
        storage_scope.store(result_path)


def test_bdm_store_a_nonexistent_path_exception(function_project: ProjectFixture[BdmSolution]):
    """
    Test that storing a non existing path in a storage scope raises an exception.
    """
    # GIVEN - no entity handle and no files
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # GIVEN - a file entity handle stored in a step field from a transaction
    step.store_result()
    # THEN - the entity handle has been created
    assert_entity_handle_is_created(step.result, "result.txt")
    storage_scope = function_project.project.storage_scope
    result_path = storage_scope.get_cached(step.result)
    # WHEN - the file is removed
    result_path.unlink()
    # THEN - store raises an error because the file no longer exists
    with pytest.raises(NotFoundInLocalStorageRootError):
        storage_scope.store(result_path)


def test_get_entity_url(function_project: ProjectFixture[BdmSolution]):
    # GIVEN - a GLOW project with a stored file entity
    step = function_project.project.steps.bdm_step
    assert_no_entity_and_no_files(step.result, function_project.project_files_dir)
    # GIVEN - a file entity handle stored in a step field from a transaction
    step.store_result()
    # WHEN: getting the entity URL
    entity_url = step.get_entity_url("result")
    # THEN: we can retrieve the content of the file that the entity is pointing to
    response = function_project._client.http_client.get(entity_url)  # pyright: ignore[reportPrivateUsage]
    assert response.content == b"hello world!"


def test_using_storage_scope_in_client_without_context_manager_raise_error(
    function_project_without_context_mgr: ProjectFixture[BdmSolution],
):
    """Test that client used without the 'with' statement cannot use the property storage_scope
    and that a proper exception is raised.
    """
    with pytest.raises(
        ValueError,
        match="'storage_scope' cannot be used when the project is created without a context manager. Use 'get_storage_scope' instead.",  # noqa: E501
    ):
        _ = function_project_without_context_mgr.project.storage_scope


def test_using_get_storage_scope_in_client_with_context_manager_raise_error(
    function_project: ProjectFixture[BdmSolution],
):
    """Test that client used with the 'with' statement cannot use the get_storage_scope method
    and that a proper exception is raised.
    """
    with (
        pytest.raises(
            ValueError,
            match="'get_storage_scope' cannot be used when the project is created using a context manager. Use the property 'storage_scope' instead.",  # noqa: E501
        ),
        function_project.project.get_storage_scope(),
    ):
        ...


@pytest.mark.parametrize(
    ("filename", "allowed_content_types"),
    [
        ("text.txt", ["text/plain; charset=utf-8"]),
        ("document.pdf", ["application/pdf"]),
        ("img.png", ["image/png"]),
        (
            "word.docx",
            [
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "text/plain; charset=utf-8",
                "application/octet-stream",
            ],
        ),
        ("script.py", ["text/x-python; charset=utf-8"]),
        ("archive.zip", ["application/x-zip-compressed", "application/zip"]),
        ("geometry.scdoc", ["text/plain; charset=utf-8", "application/octet-stream"]),
    ],
)
def test_bdm_download_file(
    function_project: ProjectFixture[BdmSolution],
    filename: str,
    allowed_content_types: list[str],
) -> None:
    """Test that blobs endpoint download entity handle using the proper referenced filename."""
    # GIVEN - an entity handle referencing a file
    step = function_project.project.steps.bdm_step
    filepath = SOLUTIONS_MOCKS_DIR / "assets" / filename
    step.store_file(filename=filepath)
    entity_url = step.get_entity_url("result")
    # WHEN - downloading the file using the entity url
    response = httpx2.get(entity_url)
    # THEN - the filename and content type are correct
    assert response.headers.get("content-disposition") == f'attachment; filename="{filename}"'
    assert response.headers.get("content-type") in allowed_content_types
    assert response.text


@pytest.mark.parametrize(
    ("datapath", "method", "filename"),
    [
        ("result", "store_result", "result.txt"),
        ("list_handles/0", "store_list_handles", "list_handles.txt"),
        ("dict_handles/dict_handle", "store_dict_handles", "dict_handles.txt"),
        ("directory/subtop/leaf.txt", "store_directory_in_entity_handle", "leaf.txt"),
        ("directory/empty", "store_directory_in_entity_handle", "empty"),
        ("sub/sub_handle", "store_sub_model", "sub.txt"),
        ("sub/inner_sub/inner_sub_handle", "store_sub_model", "inner_sub.txt"),
        ("my_entities/root_file.txt", "manually_create_entities_dict", "root_file.txt"),
        ("my_entities/subdir1/level1_file.json", "manually_create_entities_dict", "level1_file.json"),
    ],
)
def test_get_data(function_project: ProjectFixture[BdmSolution], datapath: str, method: str, filename: str):
    """Test that get_data retrieves the correct entity handle stored in different level of a step field."""
    step = function_project.project.steps.bdm_step
    getattr(step, method)()
    data = step.get_data(datapath)
    entity_handle = EntityHandle.model_validate(data)
    assert entity_handle != NO_ENTITY
    assert entity_handle.original_name == filename


@pytest.mark.parametrize(
    ("datapath", "method"),
    [
        ("sub/sub_handle/extra", "store_sub_model"),
        ("sub/wrong_handle", "store_sub_model"),
        ("directory/empty/wrong", "store_directory_in_entity_handle"),
        ("no_entity/wrong", "store_result"),
        ("my_entities/wrong", "manually_create_entities_dict"),
    ],
)
def test_get_data_raises_not_found_wrong_entity_handle(
    function_project: ProjectFixture[BdmSolution],
    datapath: str,
    method: str,
):
    """Test that get_data raises NotFoundException when trying to access invalid entity handle paths."""
    step = function_project.project.steps.bdm_step
    getattr(step, method)()
    with pytest.raises(NotFoundException, match="The object referenced by the datapath cannot be found"):
        _ = step.get_data(datapath)
