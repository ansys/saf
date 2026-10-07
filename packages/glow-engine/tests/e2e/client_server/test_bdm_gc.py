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
import datetime
import logging
from pathlib import Path
import sqlite3
import time

from fastapi import status
import httpx2
import pytest
from tenacity import TryAgain, retry, stop_after_attempt, stop_after_delay, wait_fixed

from ansys.bdm.api import (
    NO_ENTITY,
    EntityNotFoundInBlobStorageError,
)
from ansys.saf.glow.client import Client
from ansys.saf.testing.solution.end_to_end import (
    DisableGarbageCollection,
    EnvVarDebugLogLevel,
    GlowBaseProcess,
    ProjectFixture,
)
from tests.mocks.solutions.bdm_solution import BdmSolution

pytestmark = pytest.mark.parametrize("solution_type", [BdmSolution], indirect=True)

METHOD_TIMEOUT = 30


class TestGarbageCollection:
    @retry(
        stop=stop_after_attempt(20),
        wait=wait_fixed(0.1),
    )
    def wait_for_gc_cleaning_all_files(self, function_project: ProjectFixture[BdmSolution]) -> bool:
        # gc is not immediate since it is a background task
        if len([file for file in function_project.project_files_dir.rglob("*") if file.is_file()]) != 0:
            raise TryAgain
        return True

    @retry(
        stop=stop_after_attempt(20),
        wait=wait_fixed(0.1),
    )
    def wait_for_gc_contains_file(
        self,
        function_project: ProjectFixture[BdmSolution],
        filename: str,
        count: int,
    ) -> bool:
        if len(list(function_project.project_files_dir.rglob(filename))) != count:
            raise TryAgain
        return True

    @pytest.mark.parametrize("is_long_running", [False, True], ids=["sync", "long_running"])
    def test_bdm_gc_store_file_but_no_upload_removes_files(
        self,
        function_project: ProjectFixture[BdmSolution],
        is_long_running: bool,
    ):
        # GIVEN: no project files
        step = function_project.project.steps.bdm_step
        assert len([file for file in function_project.project_files_dir.rglob("*") if file.is_file()]) == 0
        # WHEN: storing file in the bdm method scope, but not saving it as entity handle
        if is_long_running:
            step.store_file_but_no_upload_long_running().wait(timeout=METHOD_TIMEOUT)
        else:
            step.store_file_but_no_upload()
        # THEN: the project files are removed after garbage collection.
        assert self.wait_for_gc_cleaning_all_files(function_project)

    def test_bdm_gc_occurs_only_after_long_running(self, function_project: ProjectFixture[BdmSolution], tmp_path: Path):
        @retry(stop=stop_after_attempt(100), wait=wait_fixed(0.3))
        def wait_for_long_running_method(signal_file: Path):
            # (the method state is set to 'running' when it returns, but it is not yet properly running.
            # we need to wait for the method to be actually running to be sure that the bdm lock
            # has been added.)
            inside_transaction = signal_file.read_text() == "inside transaction"
            if not inside_transaction:
                raise TryAgain

        # GIVEN: no project files
        step = function_project.project.steps.bdm_step
        signal_file = tmp_path / "signal.txt"
        # WHEN: executing a long running method that downloads an entity handle
        signal_file_method = step.wait_for_signal_file(signal_file=signal_file)
        # AND: making sure it is actually running
        wait_for_long_running_method(signal_file)
        # AND: adding files that should be garbage collected
        step.store_file_but_no_upload()
        step.store_result()
        step.result = NO_ENTITY
        # THEN: all the files are still there
        assert len([file for file in function_project.project_files_dir.rglob("*") if file.is_file()]) == 2
        # AND: all files are removed once the long running is done
        signal_file.write_text("stop")
        signal_file_method.wait(timeout=METHOD_TIMEOUT)
        assert self.wait_for_gc_cleaning_all_files(function_project)

    @pytest.mark.parametrize("is_long_running", [False, True], ids=["sync", "long_running"])
    def test_bdm_gc_not_triggered_if_client_scope_used_without_context_manager(
        self,
        function_project_without_context_mgr: ProjectFixture[BdmSolution],
        is_long_running: bool,
    ):
        project = function_project_without_context_mgr.project
        with project.get_storage_scope() as scope:
            step = project.steps.bdm_step
            # WHEN: storing file in the bdm method scope, but not saving it as entity handle
            if is_long_running:
                unreferenced_entity = step.store_file_but_no_upload_long_running().wait(timeout=METHOD_TIMEOUT)
            else:
                unreferenced_entity = step.store_file_but_no_upload()
            # THEN: the scope can accessed the unreferenced entity
            assert scope.get_text(unreferenced_entity) == "hello world!"
            # AND: adding files that should be garbage collected
            step.store_file_but_no_upload()
            step.store_result()
            dereferenced_entity = step.result
            step.result = NO_ENTITY
            # THEN: the file still exists
            assert scope.get_cached(dereferenced_entity).exists()
        # WHEN: reaching the end of the scope and waiting for gc
        assert self.wait_for_gc_cleaning_all_files(function_project_without_context_mgr)
        # THEN: the files do not exist anymore
        with project.get_storage_scope() as scope:
            with pytest.raises(EntityNotFoundInBlobStorageError):
                scope.get_cached(unreferenced_entity)
            with pytest.raises(EntityNotFoundInBlobStorageError):
                scope.get_cached(dereferenced_entity)

    @pytest.mark.parametrize("is_long_running", [False, True], ids=["sync", "long_running"])
    def test_bdm_gc_not_triggered_if_client_scope(
        self,
        function_project: ProjectFixture[BdmSolution],
        is_long_running: bool,
    ):
        # GIVEN: the client storage scope opened
        scope = function_project.project.storage_scope
        step = function_project.project.steps.bdm_step
        # WHEN: storing file in the bdm method scope, but not saving it as entity handle
        if is_long_running:
            unreferenced_entity = step.store_file_but_no_upload_long_running().wait(timeout=METHOD_TIMEOUT)
        else:
            unreferenced_entity = step.store_file_but_no_upload()
        # THEN: the scope can accessed the unreferenced entity
        assert scope.get_text(unreferenced_entity) == "hello world!"
        # AND: adding files that should be garbage collected
        step.store_file_but_no_upload()
        step.store_result()
        dereferenced_entity = step.result
        step.result = NO_ENTITY
        # THEN: the file still exists
        assert scope.get_cached(dereferenced_entity).exists()
        assert scope.get_cached(unreferenced_entity).exists()

    @pytest.mark.parametrize("is_long_running", [False, True], ids=["sync", "long_running"])
    def test_bdm_gc_overwrite_entity_handle_from_transaction_remove_previous_file(
        self,
        function_project: ProjectFixture[BdmSolution],
        is_long_running: bool,
    ):
        # GIVEN: no project files
        step = function_project.project.steps.bdm_step
        assert len(list(function_project.project_files_dir.rglob("result.txt"))) == 0
        # WHEN: running a transaction overwriting an entity handle
        if is_long_running:
            step.store_result_long_running().wait(timeout=METHOD_TIMEOUT)
            step.overwrite_result_long_running().wait(timeout=METHOD_TIMEOUT)
        else:
            step.store_result()
            step.overwrite_result()
        # THEN: garbage collection should remove initial file
        assert self.wait_for_gc_contains_file(function_project, "result.txt", 1)
        # AND: and only the last file is kept.
        result_txt = next(function_project.project_files_dir.rglob("result.txt"))
        assert result_txt.read_text() == "another hello world!"

    @pytest.mark.parametrize("is_long_running", [False, True], ids=["sync", "long_running"])
    def test_bdm_gc_overwrite_entity_handle_from_client_remove_previous_file(
        self,
        function_project_without_context_mgr: ProjectFixture[BdmSolution],
        is_long_running: bool,
    ):
        # GIVEN: no project files
        step = function_project_without_context_mgr.project.steps.bdm_step
        assert len(list(function_project_without_context_mgr.project_files_dir.rglob("result.txt"))) == 0
        # WHEN: running a transaction storing an entity handle
        if is_long_running:
            step.store_result_long_running().wait(timeout=METHOD_TIMEOUT)
        else:
            step.store_result()
        # THEN: one result file has been stored
        result_txt_files = list(function_project_without_context_mgr.project_files_dir.rglob("result.txt"))
        assert len(result_txt_files) == 1
        assert result_txt_files[0].read_text() == "hello world!"

        # WHEN: the entity handle is replaced with another one
        with function_project_without_context_mgr.project.get_storage_scope() as scope:
            result_txt = scope.get_storage_root() / "result.txt"
            result_txt.write_text("overwrite")
            new_entity = scope.store(result_txt)
            step.result = new_entity
        # THEN: garbage collection should remove initial file
        assert self.wait_for_gc_contains_file(function_project_without_context_mgr, "result.txt", 1)
        result_txt_file = next(function_project_without_context_mgr.project_files_dir.rglob("result.txt"))
        assert result_txt_file.read_text() == "overwrite"

    @pytest.mark.parametrize("is_long_running", [False, True], ids=["sync", "long_running"])
    def test_bdm_gc_set_no_entity_remove_previous_file(
        self,
        function_project: ProjectFixture[BdmSolution],
        is_long_running: bool,
    ):
        def contains_no_result_txt():
            return len(list(function_project.project_files_dir.rglob("result.txt"))) == 0

        # GIVEN: no result file
        step = function_project.project.steps.bdm_step
        assert contains_no_result_txt()
        # WHEN: entity handle is stored within a method
        if is_long_running:
            step.store_result_long_running().wait(timeout=METHOD_TIMEOUT)
        else:
            step.store_result()
        assert len(list(function_project.project_files_dir.rglob("result.txt"))) == 1
        # AND: this entity handle is assigned to NO_ENTITY
        step.result = NO_ENTITY
        # THEN: gc is cleaning up the result file
        assert self.wait_for_gc_contains_file(function_project, "result.txt", 0)

    def test_get_storage_scope_add_bdm_lock_on_enter_and_remove_it_on_exit(
        self,
        function_project_without_context_mgr: ProjectFixture[BdmSolution],
    ):
        # WHEN - a storage scope is entered
        with function_project_without_context_mgr.project.get_storage_scope() as scope:
            lock_id = (  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                scope._lock_id  # pyright: ignore[reportAttributeAccessIssue]
            )
            # THEN: a bdm_lock has been created
            response = function_project_without_context_mgr._client.http_client.get(  # pyright: ignore[reportPrivateUsage]
                f"{function_project_without_context_mgr.url}/bdm-locks/{lock_id}",  # type: ignore
            )
            assert response.status_code == status.HTTP_200_OK
            # WHEN: the scope has been closed
        # THEN: the bdm_lock doesn't exist anymore
        response = function_project_without_context_mgr._client.http_client.get(  # pyright: ignore[reportPrivateUsage]
            f"{function_project_without_context_mgr.url}/bdm-locks/{lock_id}",  # type: ignore
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_using_closed_storage_scope_raises_error(
        self,
        function_project_without_context_mgr: ProjectFixture[BdmSolution],
    ):
        # GIVEN - a storage scope used without the with statement
        with function_project_without_context_mgr.project.get_storage_scope() as scope:
            ...
        # THEN - an error is raised when using the scope outside of the with statement
        with pytest.raises(ValueError, match="The storage scope has been closed."):
            scope.get_storage_root()

    def test_bdm_gc_store_entity_handle_list_assign_empty_cleans_files(
        self,
        function_project: ProjectFixture[BdmSolution],
    ):
        """
        Test that clearing a list of entity handles in a step field,
        makes the garbage collection clearing all files referenced by
        the entity handles.
        """
        step = function_project.project.steps.bdm_step
        # WHEN: running a transaction storing an entity handle in a list of entity handles
        step.store_list_handles()
        assert self.wait_for_gc_contains_file(function_project, "list_handles.txt", 1)
        # WHEN: list is emptied
        step.list_handles = []
        # THEN: garbage collection should remove files
        assert self.wait_for_gc_cleaning_all_files(function_project)

    def test_bdm_gc_store_entity_handle_dict_assign_empty_cleans_files(
        self,
        function_project: ProjectFixture[BdmSolution],
    ):
        """
        Test that clearing a dict of entity handles in a step field,
        makes the garbage collection clearing all files referenced by
        the entity handles.
        """
        step = function_project.project.steps.bdm_step
        # WHEN: running a transaction storing a dict of entity handles
        step.store_dict_handles()
        assert self.wait_for_gc_contains_file(function_project, "dict_handles.txt", 1)
        # WHEN: dict is emptied
        step.dict_handles = {}
        # THEN: garbage collection should remove initial file
        assert self.wait_for_gc_cleaning_all_files(function_project)

    def test_bdm_gc_store_entity_handle_sub_assign_empty_cleans_files(
        self,
        function_project: ProjectFixture[BdmSolution],
    ):
        """
        Test that assigning NO_ENTITY to entity handles in a step field,
        containing submodel, makes the garbage collection clearing all files referenced by
        the entity handles.
        """
        step = function_project.project.steps.bdm_step
        # WHEN: running a transaction storing a sub model containing entity handles
        step.store_sub_model()
        assert self.wait_for_gc_contains_file(function_project, "sub.txt", 1)
        assert self.wait_for_gc_contains_file(function_project, "inner_sub.txt", 1)
        # WHEN: an inner sub entity handle is set to NO_ENTITY
        modified_sub = step.sub
        modified_sub.inner_sub.inner_sub_handle = NO_ENTITY
        step.sub = modified_sub
        # THEN: garbage collection should remove initial file
        assert self.wait_for_gc_contains_file(function_project, "sub.txt", 1)
        assert self.wait_for_gc_contains_file(function_project, "inner_sub.txt", 0)
        # WHEN: a sub entity handle is set to NO_ENTITY
        modified_sub.sub_handle = NO_ENTITY
        step.sub = modified_sub
        # THEN: garbage collection should remove all files
        assert self.wait_for_gc_cleaning_all_files(function_project)

    def test_client_storage_scope_remove_bdm_lock_on_client_close(
        self,
        session_glow: GlowBaseProcess[BdmSolution],
    ):
        # WHEN: creating a client with storage scope
        with Client(session_glow.solution_type, session_glow.base_api_url) as client:
            project = client.create_project("test")
            scope = project.storage_scope
            lock_id = (  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                scope._lock_id  # pyright: ignore[reportAttributeAccessIssue]
            )
            result_path = scope.get_storage_root() / "result.txt"
            result_path.write_text("hello world!")
            handle = scope.store(result_path)
            project.steps.bdm_step.result = handle
        # THEN: the bdm_lock doesn't exist anymore when client closes
        response = httpx2.get(f"{project.url}/bdm-locks/{lock_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_close_client_after_project_delete(
        self,
        session_glow: GlowBaseProcess[BdmSolution],
        caplog: pytest.LogCaptureFixture,
    ):
        # WHEN: creating a client with storage scope
        caplog.set_level(logging.ERROR)
        with Client(session_glow.solution_type, session_glow.base_api_url) as client:
            project = client.create_project("test")
            scope = project.storage_scope
            # AND: deleting the project using project proxy
            project.delete()
            lock_id = (  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                scope._lock_id  # pyright: ignore[reportAttributeAccessIssue]
            )
            assert lock_id is not None
            response = httpx2.get(f"{project.url}/bdm-locks/{lock_id}")
            # THEN: the bdm_lock does not exist
            assert response.status_code == status.HTTP_404_NOT_FOUND
        # AND: no error has been logged
        assert caplog.messages == []

    def test_client_storage_scope_fail_removal_bdm_lock_log_error_on_client_close(
        self,
        session_glow: GlowBaseProcess[BdmSolution],
        caplog: pytest.LogCaptureFixture,
    ):
        # WHEN: creating a client with storage scope
        caplog.set_level(logging.ERROR)
        with Client(session_glow.solution_type, session_glow.base_api_url) as client:
            project = client.create_project("test")
            scope = project.storage_scope
            # AND: deleting the project using http to make bdm lock removal fail when client closes
            lock_id = (  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                scope._lock_id  # pyright: ignore[reportAttributeAccessIssue]
            )
            httpx2.delete(f"{project.url}/bdm-locks/{lock_id}")
            assert lock_id is not None
            response = httpx2.get(f"{project.url}/bdm-locks/{lock_id}")
            # THEN: the bdm_lock does not exist
            assert response.status_code == status.HTTP_404_NOT_FOUND
        # AND: an error has been logged when trying to remove the bdm lock
        assert caplog.messages == [
            "An error occurred while removing the bdm lock for the client storage scope. Garbage collection may be deferred until expiration of the lock.",  # noqa: E501
        ]

    def test_project_not_failing_with_bdm_expired_lock(
        self,
        session_glow: GlowBaseProcess[BdmSolution],
        function_project: ProjectFixture[BdmSolution],
    ):
        """
        Test that project using expired bdm locks are not failing.
        """

        sqlite_db = session_glow.project_files_directory.parent / "glow.db"
        assert sqlite_db.is_file()

        step = function_project.project.steps.bdm_step
        scope = function_project.project.storage_scope
        statement_text = "UPDATE bdm_locks SET expiration_date = :expiration_date WHERE project_id = :project_id"
        with sqlite3.connect(str(sqlite_db)) as conn:
            conn.execute(
                statement_text,
                {
                    "project_id": function_project.project_id,
                    "expiration_date": datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1),
                },
            )

        # Prior to the fix, the following call was raising an error:
        # "ValidationError: expiration_date: Input should be in the future"
        step.store_result()
        assert scope.get_text(step.result) == "hello world!"


class TestGarbageCollectionDisabled:
    @pytest.fixture(scope="class", autouse=True)
    def disable_garbage_collection(self, session_glow: GlowBaseProcess[BdmSolution]) -> Generator[None, None, None]:
        session_glow.change_configuration(DisableGarbageCollection)
        mp = pytest.MonkeyPatch()
        mp.setenv("GLOW_BDM_GC_DISABLED", "True")  # also needed in the client
        yield
        mp.undo()
        session_glow.configure_default_execution()

    @pytest.mark.parametrize("is_long_running", [False, True], ids=["sync", "long_running"])
    def test_bdm_gc_store_file_but_no_upload_keeps_files(
        self,
        function_project: ProjectFixture[BdmSolution],
        is_long_running: bool,
    ):
        """
        Test that when disabling gc, blobs are kept even if not assigned to step fields.
        """
        # GIVEN: no project files
        step = function_project.project.steps.bdm_step
        assert len([file for file in function_project.project_files_dir.rglob("*") if file.is_file()]) == 0
        # WHEN: storing file in the bdm method scope, but not saving it as entity handle
        if is_long_running:
            step.store_file_but_no_upload_long_running().wait(timeout=METHOD_TIMEOUT)
        else:
            step.store_file_but_no_upload()
        time.sleep(0.5)  # give some time to the gc in case it is there to remove files
        # THEN: the project files are kept and not garbage collection occurred.
        assert len([file for file in function_project.project_files_dir.rglob("*") if file.is_file()]) == 1

    @pytest.mark.parametrize("is_long_running", [False, True], ids=["sync", "long_running"])
    def test_bdm_gc_not_triggered_when_client_scope_closed(
        self,
        function_project_without_context_mgr: ProjectFixture[BdmSolution],
        is_long_running: bool,
    ):
        """
        Test that when disabling gc, blobs are kept even when client scope is closed.
        """

        # GIVEN: the client storage scope opened
        with function_project_without_context_mgr.project.get_storage_scope() as scope:
            step = function_project_without_context_mgr.project.steps.bdm_step
            # WHEN: storing file in the bdm method scope, but not saving it as entity handle
            if is_long_running:
                unreferenced_entity = step.store_file_but_no_upload_long_running().wait(timeout=METHOD_TIMEOUT)
            else:
                unreferenced_entity = step.store_file_but_no_upload()
            # THEN: the scope can accessed the unreferenced entity
            assert scope.get_text(unreferenced_entity) == "hello world!"
            # AND: adding new file that is dereferenced
            step.store_result()
            dereferenced_entity = step.result
            step.result = NO_ENTITY
            # THEN: the file still exists
            assert scope.get_cached(dereferenced_entity).exists()
        time.sleep(0.5)  # give some time to the gc in case it is there to remove files
        # THEN: the files exist
        with function_project_without_context_mgr.project.get_storage_scope() as scope:
            assert scope.get_cached(unreferenced_entity).exists()
            assert scope.get_cached(dereferenced_entity).exists()

    @pytest.mark.parametrize("is_long_running", [False, True], ids=["sync", "long_running"])
    def test_bdm_gc_overwrite_entity_handle_from_transaction_keeps_previous_file(
        self,
        function_project: ProjectFixture[BdmSolution],
        is_long_running: bool,
    ):
        """
        Test that when disabling gc, two blobs are created and kept when an entity handles
        is overwritten within a method.
        """
        # GIVEN: no project files
        step = function_project.project.steps.bdm_step
        assert len(list(function_project.project_files_dir.rglob("result.txt"))) == 0
        # WHEN: running a transaction overwriting an entity handle
        if is_long_running:
            step.store_result_long_running().wait(timeout=METHOD_TIMEOUT)
            step.overwrite_result_long_running().wait(timeout=METHOD_TIMEOUT)
        else:
            step.store_result()
            step.overwrite_result()
        time.sleep(0.5)  # give some time to the gc in case it is there to remove files
        # THEN: both files are kept
        assert len(list(function_project.project_files_dir.rglob("result.txt"))) == 2

    @pytest.mark.parametrize("is_long_running", [False, True], ids=["sync", "long_running"])
    def test_bdm_gc_overwrite_entity_handle_from_client_keeps_previous_file(
        self,
        function_project: ProjectFixture[BdmSolution],
        is_long_running: bool,
    ):
        """
        Test that when disabling gc, two blobs are created and kept when an entity handles is overwritten by the client.
        """

        # GIVEN: no project files
        step = function_project.project.steps.bdm_step
        assert len(list(function_project.project_files_dir.rglob("result.txt"))) == 0
        # WHEN: running a transaction storing an entity handle
        if is_long_running:
            step.store_result_long_running().wait(timeout=METHOD_TIMEOUT)
        else:
            step.store_result()
        # THEN: one result file has been stored
        result_txt_files = list(function_project.project_files_dir.rglob("result.txt"))
        assert len(result_txt_files) == 1
        assert result_txt_files[0].read_text() == "hello world!"

        # WHEN: the entity handle is replaced with another one
        scope = function_project.project.storage_scope
        result_txt = scope.get_storage_root() / "result.txt"
        result_txt.write_text("overwrite")
        new_entity = scope.store(result_txt)
        step.result = new_entity
        time.sleep(0.5)  # give some time to the gc in case it is there to remove files
        # THEN: both files are kept
        assert len(list(function_project.project_files_dir.rglob("result.txt"))) == 2

    @pytest.mark.parametrize("is_long_running", [False, True], ids=["sync", "long_running"])
    def test_bdm_gc_set_no_entity_keeps_previous_file(
        self,
        function_project: ProjectFixture[BdmSolution],
        is_long_running: bool,
    ):
        """
        Test that when disabling gc, an entity handle being set to NO_ENTITY does not remove the blob associated to it.
        """

        def contains_no_result_txt():
            return len(list(function_project.project_files_dir.rglob("result.txt"))) == 0

        # GIVEN: no result file
        step = function_project.project.steps.bdm_step
        assert contains_no_result_txt()
        # WHEN: entity handle is stored within a method
        if is_long_running:
            step.store_result_long_running().wait(timeout=METHOD_TIMEOUT)
        else:
            step.store_result()
        assert len(list(function_project.project_files_dir.rglob("result.txt"))) == 1
        # AND: this entity handle is assigned to NO_ENTITY
        step.result = NO_ENTITY
        time.sleep(0.5)  # give some time to the gc in case it is there to remove files
        # THEN: file still exists
        return len(list(function_project.project_files_dir.rglob("result.txt"))) == 1

    def test_using_get_storage_scope_without_with_statement_raises_error(
        self,
        function_project: ProjectFixture[BdmSolution],
    ):
        """
        Test that when disabling gc, using the client storage scope without the 'with' statement raises an error.
        """
        # GIVEN - a storage scope used without the with statement
        step = function_project.project.steps.bdm_step
        scope = function_project.project.get_storage_scope()
        # THEN - an error is raised
        with pytest.raises(AttributeError, match="'_GeneratorContextManager' object has no attribute 'get_cached'"):
            scope.get_cached(step.result)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]

    def test_using_closed_storage_scope_raises_error(
        self,
        function_project_without_context_mgr: ProjectFixture[BdmSolution],
    ):
        """
        Test that when disabling gc, using a closed client storage scope raises an error.
        """
        # GIVEN - a storage scope used without the with statement
        with function_project_without_context_mgr.project.get_storage_scope() as scope:
            ...
        # THEN - an error is raised when using the scope outside of the with statement
        with pytest.raises(ValueError, match="The storage scope has been closed."):
            scope.get_storage_root()

    def test_get_bdm_lock_endpoint_raise_error(self, function_project: ProjectFixture[BdmSolution]):
        """
        Test that when disabling gc, accessing the bdm-locks endpoints raises a 403 error.
        """
        # GET raises 403
        response = function_project._client.http_client.get(  # pyright: ignore[reportPrivateUsage]
            f"{function_project.url}/bdm-locks/1234",  # type: ignore
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"] == "Garbage collection is disabled."

    def test_post_bdm_lock_endpoint_raise_error(self, function_project: ProjectFixture[BdmSolution]):
        """
        Test that when disabling gc, using POST on the bdm-locks endpoints raises a 403 error.
        """
        # GET raises 403
        response = function_project._client.http_client.get(  # pyright: ignore[reportPrivateUsage]
            f"{function_project.url}/bdm-locks/1234",  # type: ignore
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"] == "Garbage collection is disabled."

    def test_deleting_bdm_lock_endpoint_raise_error(self, function_project: ProjectFixture[BdmSolution]):
        """
        Test that when disabling gc, deleting the bdm-locks endpoints raises a 403 error.
        """
        # DELETE raises 403
        response = function_project._client.http_client.delete(  # pyright: ignore[reportPrivateUsage]
            f"{function_project.url}/bdm-locks/1234",  # type: ignore
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"] == "Garbage collection is disabled."


@retry(stop=stop_after_delay(10), wait=wait_fixed(0.1))
def assert_bdm_locks_count(session_glow: GlowBaseProcess[BdmSolution], expected_count: int):
    added_locks = len([line for line in session_glow.api_output if "Adding BDM lock" in line])
    removed_locks = len([line for line in session_glow.api_output if "Removing BDM lock" in line])
    if added_locks != expected_count or removed_locks != expected_count:
        raise TryAgain
    assert added_locks == expected_count
    assert removed_locks == expected_count


class TestBdmGarbageCollectorLocks:
    @pytest.fixture(scope="class", autouse=True)
    def set_logging_level_to_debug(self, session_glow: GlowBaseProcess[BdmSolution]) -> Generator[None, None, None]:
        session_glow.change_configuration(EnvVarDebugLogLevel)
        yield
        session_glow.configure_default_execution()

    def test_transaction_with_entity_handle_in_return_value(
        self,
        function_project: ProjectFixture[BdmSolution],
        session_glow: GlowBaseProcess[BdmSolution],
    ):
        """Test that if a transaction method returns an entity handle, a BDM lock is created for the duration of the
        transaction.
        """
        session_glow.clear_output()
        function_project.project.steps.bdm_step.store_file_but_no_upload()
        assert_bdm_locks_count(session_glow, 1)  # no upload, so only 1 lock for the transaction

    def test_transaction_with_entity_handle_in_input_param(
        self,
        function_project: ProjectFixture[BdmSolution],
        session_glow: GlowBaseProcess[BdmSolution],
    ):
        """Test that if a transaction method expects an entity handle as input parameter, a BDM lock is created for the
        duration of the transaction.
        """
        function_project.project.steps.bdm_step.store_result()
        entity = function_project.project.steps.bdm_step.result
        session_glow.clear_output()
        function_project.project.steps.bdm_step.get_text_from_input_handle_no_download(handle=entity)
        assert_bdm_locks_count(session_glow, 1)  # no upload, so only 1 lock for the transaction

    @pytest.mark.parametrize(
        ("transaction_upload_name", "transaction_download_name"),
        [
            ("store_result", "get_text_result"),
            ("store_list_handles", "get_text_first_item_list_handles"),
            ("store_dict_handles", "get_text_handle_item_dict_handles"),
            ("store_sub_model", "get_text_sub_handle"),
            ("store_directory_in_entity_handle", "get_directory_children"),
            ("upload_directory_to_recursive_dict", "download_directory_from_recursive_dict"),
        ],
    )
    def test_transaction_with_entity_handles_in_step_spec_upload_or_download(
        self,
        function_project: ProjectFixture[BdmSolution],
        session_glow: GlowBaseProcess[BdmSolution],
        transaction_upload_name: str,
        transaction_download_name: str,
    ):
        """Test that if a transaction method uploads or downloads entity handles as specified in the step spec,
        BDM locks are created for the duration of the transaction.
        """
        session_glow.clear_output()
        getattr(function_project.project.steps.bdm_step, transaction_upload_name)()
        assert_bdm_locks_count(session_glow, 2)  # upload, so 2 locks (1 for transaction, 1 for upload)

        session_glow.clear_output()
        getattr(function_project.project.steps.bdm_step, transaction_download_name)()
        assert_bdm_locks_count(session_glow, 1)  # no upload, so only 1 lock for the transaction

    def test_long_running_transaction_with_entity_handles_in_step_spec_upload_or_download(
        self,
        function_project: ProjectFixture[BdmSolution],
        session_glow: GlowBaseProcess[BdmSolution],
    ):
        """Test that if a long running transaction method uploads or downloads entity handles as specified in the
        step spec, BDM locks are created for the duration of the transaction.
        """
        session_glow.clear_output()
        function_project.project.steps.bdm_step.store_result_long_running().wait(timeout=METHOD_TIMEOUT)
        assert_bdm_locks_count(session_glow, 2)  # upload, so 2 locks (1 for transaction, 1 for upload)

        session_glow.clear_output()
        function_project.project.steps.bdm_step.get_cached_result_long_running().wait(timeout=METHOD_TIMEOUT)
        assert_bdm_locks_count(session_glow, 1)  # no upload, so only 1 lock for the transaction

    def test_transaction_with_entity_handles_in_others_step_spec_upload_or_download(
        self,
        function_project: ProjectFixture[BdmSolution],
        session_glow: GlowBaseProcess[BdmSolution],
    ):
        """Test that if a transaction method downloads entity handles from another step, BDM locks are created for the
        duration of the transaction.
        """
        session_glow.clear_output()
        function_project.project.steps.bdm_step.store_file_in_entity_handle()
        assert_bdm_locks_count(session_glow, 2)  # upload, so 2 locks (1 for transaction, 1 for upload)

        session_glow.clear_output()
        function_project.project.steps.other_bdm_step.get_text_from_handle_from_other_step()
        assert_bdm_locks_count(session_glow, 1)  # no upload, so only 1 lock for the transaction

    def test_transaction_no_entity_handles_in_step_spec(
        self,
        function_project: ProjectFixture[BdmSolution],
        session_glow: GlowBaseProcess[BdmSolution],
    ):
        """Test that if a transaction method uploads or downloads fields that do not contain entity handles, BDM locks
        are not created for the duration of the transaction.
        """
        session_glow.clear_output()
        function_project.project.steps.bdm_step.upload_other(other=4)
        assert_bdm_locks_count(session_glow, 0)

        session_glow.clear_output()
        function_project.project.steps.bdm_step.duplicate_other()
        assert_bdm_locks_count(session_glow, 0)

    def test_setting_field_in_client(
        self,
        function_project: ProjectFixture[BdmSolution],
        session_glow: GlowBaseProcess[BdmSolution],
    ):
        """Test that setting step fields in the client that are entity handles, creates and removes BDM locks as
        expected. BDM locks are not created for other types of fields.
        """
        session_glow.clear_output()
        function_project.project.steps.bdm_step.result = NO_ENTITY
        assert_bdm_locks_count(session_glow, 1)

        session_glow.clear_output()
        function_project.project.steps.bdm_step.other = 5
        assert_bdm_locks_count(session_glow, 0)

    def test_uploading_fields_in_client(
        self,
        function_project: ProjectFixture[BdmSolution],
        session_glow: GlowBaseProcess[BdmSolution],
    ):
        """Test that uploading step fields in the client that include entity handles, creates and removes BDM locks as
        expected. BDM locks are not created for other types of fields.
        """
        session_glow.clear_output()
        function_project.project.steps.bdm_step.set_fields({"result": NO_ENTITY})
        assert_bdm_locks_count(session_glow, 1)

        session_glow.clear_output()
        function_project.project.steps.bdm_step.set_fields({"other": 5})
        assert_bdm_locks_count(session_glow, 0)

        session_glow.clear_output()
        function_project.project.steps.bdm_step.set_fields({"result": NO_ENTITY, "other": 5})
        assert_bdm_locks_count(session_glow, 1)
