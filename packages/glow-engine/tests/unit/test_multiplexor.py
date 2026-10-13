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

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest

from ansys.bdm.api import IAsyncReadStorageScope, IAsyncStorageScope, IReadStorageScope, IStorageScope
from ansys.bdm.api.entity_handle import EntityHandle
from ansys.saf.glow._bdm.multiplexor import PRIMARY_BDM_SYSTEM_NAME, AsyncBdmMultiplexor, BdmMultiplexor
from ansys.saf.glow._bdm.storage_contexts import METHOD_CONTEXT, PROJECT_BOUNDARY
from ansys.saf.glow._bdm.storage_factory import create_shared_storage_factory


class TestMultiplexor:
    def test_multiplexor_subsystem_name_containing_slash_raise_error(
        self,
        primary_bdm_scope: IStorageScope,
        subsystem_scope: IReadStorageScope,
    ):
        with pytest.raises(ValueError, match="Subsystem names cannot contain the following character: '/'"):
            BdmMultiplexor(primary_bdm_scope, {"wrong/name": subsystem_scope})

    def test_multiplexor_wrap_handle_prefix_opaque_identifier(self, primary_bdm_scope: IStorageScope):
        multiplexor = BdmMultiplexor(primary_bdm_scope, {})
        with primary_bdm_scope.begin_store(relative_location=Path("result.txt")) as writer:
            writer.stream.write(b"hello world!")
        wrapped_handle = multiplexor.wrap_handle(PRIMARY_BDM_SYSTEM_NAME, writer.handle)
        assert wrapped_handle.opaque_identifier == f"{PRIMARY_BDM_SYSTEM_NAME}/{writer.handle.opaque_identifier}"

    def test_multiplexor_wrap_handle_wrong_bdm_system_name_raise_error(self, multiplexor: BdmMultiplexor):
        test_txt = multiplexor.get_storage_root() / "test.txt"
        test_txt.touch()
        entity = multiplexor.store(test_txt)
        with pytest.raises(ValueError, match="The BDM system 'wrong_bdm_system_name' cannot be found."):
            multiplexor.wrap_handle("wrong_bdm_system_name", entity)

    def test_multiplexor_get_storage_root_use_primary_system(
        self,
        multiplexor: BdmMultiplexor,
        primary_bdm_scope: IStorageScope,
    ):
        assert multiplexor.get_storage_root() == primary_bdm_scope.get_storage_root()

    def test_multiplexor_store_wraps_entity_with_primary_system(self, multiplexor: BdmMultiplexor):
        test_txt = multiplexor.get_storage_root() / "test.txt"
        test_txt.touch()
        handle = multiplexor.store(test_txt)
        assert handle.opaque_identifier.startswith(PRIMARY_BDM_SYSTEM_NAME)

    def test_multiplexor_store_stream_wraps_entity_with_primary_system(self, multiplexor: BdmMultiplexor):
        handle = multiplexor.store_stream(b"hello world")
        assert handle.opaque_identifier.startswith(PRIMARY_BDM_SYSTEM_NAME)

    def test_multiplexor_begin_store_wraps_entity_with_primary_system(self, multiplexor: BdmMultiplexor):
        with multiplexor.begin_store(relative_location=Path("result.txt")) as writer:
            writer.stream.write(b"hello world!")
        assert writer.handle.opaque_identifier.startswith(PRIMARY_BDM_SYSTEM_NAME)

    def test_multiplexor_store_entities_wraps_entities_in_primary_system(
        self,
        multiplexor: BdmMultiplexor,
        primary_bdm_scope: IStorageScope,
    ):
        handle = primary_bdm_scope.store_stream(b"hello")
        assert len(multiplexor.stored_entities) == 1
        assert (
            f"{PRIMARY_BDM_SYSTEM_NAME}/{handle.opaque_identifier}" == multiplexor.stored_entities[0].opaque_identifier
        )

    @dataclass
    class MockEntityHandle:
        seen_from_system: EntityHandle
        seen_from_multiplexor: EntityHandle
        inner_scope: IStorageScope
        system_name: str

    @pytest.fixture(params=["primary_bdm_scope", "subsystem_scope"])
    def created_entity(
        self,
        request: pytest.FixtureRequest,
    ) -> MockEntityHandle:
        system_name = "primary" if "primary" in request.param else "subsystem"
        inner_scope: IStorageScope = request.getfixturevalue(request.param)
        entity_handle = inner_scope.store_stream(b"hello")
        wrapped_entity = entity_handle.model_copy(
            update={"opaque_identifier": f"{system_name}/{entity_handle.opaque_identifier}"},
        )
        return TestMultiplexor.MockEntityHandle(
            seen_from_system=entity_handle,
            seen_from_multiplexor=wrapped_entity,
            inner_scope=inner_scope,
            system_name=system_name,
        )

    @pytest.fixture(params=["primary_bdm_scope", "subsystem_scope"])
    def created_dir_entity(
        self,
        request: pytest.FixtureRequest,
    ) -> MockEntityHandle:
        system_name = "primary" if "primary" in request.param else "subsystem"
        inner_scope: IStorageScope = request.getfixturevalue(request.param)
        directory = inner_scope.get_storage_root() / "dir"
        directory.mkdir()
        my_file = directory / "my_file.txt"
        my_file.write_text("hello")
        entity_handle = inner_scope.store(directory)
        wrapped_entity = entity_handle.model_copy(
            update={"opaque_identifier": f"{system_name}/{entity_handle.opaque_identifier}"},
        )
        return TestMultiplexor.MockEntityHandle(
            seen_from_system=entity_handle,
            seen_from_multiplexor=wrapped_entity,
            inner_scope=inner_scope,
            system_name=system_name,
        )

    def test_multiplexor_get_cached_returns_from_inner_system_scope(
        self,
        created_entity: MockEntityHandle,
        multiplexor: BdmMultiplexor,
    ):
        assert multiplexor.get_cached(created_entity.seen_from_multiplexor) == created_entity.inner_scope.get_cached(
            created_entity.seen_from_system,
        )

    def test_multiplexor_get_text_returns_from_inner_system_scope(
        self,
        created_entity: MockEntityHandle,
        multiplexor: BdmMultiplexor,
    ):
        assert multiplexor.get_text(created_entity.seen_from_multiplexor) == created_entity.inner_scope.get_text(
            created_entity.seen_from_system,
        )

    def test_multiplexor_get_bytes_returns_from_inner_system_scope(
        self,
        created_entity: MockEntityHandle,
        multiplexor: BdmMultiplexor,
    ):
        assert multiplexor.get_bytes(created_entity.seen_from_multiplexor) == created_entity.inner_scope.get_bytes(
            created_entity.seen_from_system,
        )

    def test_multiplexor_get_stream_returns_from_inner_system_scope(
        self,
        created_entity: MockEntityHandle,
        multiplexor: BdmMultiplexor,
    ):
        assert (
            multiplexor.get_stream(created_entity.seen_from_multiplexor).read()
            == created_entity.inner_scope.get_stream(created_entity.seen_from_system).read()
        )

    def test_multiplexor_get_copy_returns_from_inner_system_scope(
        self,
        created_entity: MockEntityHandle,
        tmp_path: Path,
        multiplexor: BdmMultiplexor,
    ):
        multiplexor_dest = tmp_path / "multiplexor_dest.txt"
        inner_scope_dest = tmp_path / "inner_scope_dest.txt"
        multiplexor.get_copy(created_entity.seen_from_multiplexor, multiplexor_dest)
        created_entity.inner_scope.get_copy(created_entity.seen_from_system, inner_scope_dest)
        assert multiplexor_dest.read_text() == inner_scope_dest.read_text()

    def test_multiplexor_get_child_returns_wrapped_entity_from_inner_system_scope(
        self,
        created_dir_entity: MockEntityHandle,
        multiplexor: BdmMultiplexor,
    ):
        assert (
            multiplexor.get_child(
                created_dir_entity.seen_from_multiplexor,
                "my_file.txt",
            ).opaque_identifier.removeprefix(
                f"{created_dir_entity.system_name}/",
            )
            == created_dir_entity.inner_scope.get_child(
                created_dir_entity.seen_from_system,
                "my_file.txt",
            ).opaque_identifier
        )

    def test_multiplexor_get_parent_returns_wrapped_entity_from_inner_system_scope(
        self,
        created_dir_entity: MockEntityHandle,
        multiplexor: BdmMultiplexor,
    ):
        child = multiplexor.get_child(created_dir_entity.seen_from_multiplexor, "my_file.txt")
        parent = multiplexor.get_parent(child)
        assert parent is not None
        assert parent.original_name == "dir"
        assert (
            parent.opaque_identifier.removeprefix(created_dir_entity.system_name + "/")
            == created_dir_entity.seen_from_system.opaque_identifier
        )

    def test_multiplexor_get_children_returns_wrapped_entities_from_inner_system_scope(
        self,
        created_dir_entity: MockEntityHandle,
        multiplexor: BdmMultiplexor,
    ):
        multiplexor_children = multiplexor.get_children(created_dir_entity.seen_from_multiplexor)
        innerscope_children = created_dir_entity.inner_scope.get_children(created_dir_entity.seen_from_system)
        assert len(multiplexor_children) == len(innerscope_children)
        multiplexor_unwrapped_opaque_ids = [
            child.opaque_identifier.removeprefix(f"{created_dir_entity.system_name}/") for child in multiplexor_children
        ]
        innerscope_opaque_ids = [child.opaque_identifier for child in innerscope_children]
        assert multiplexor_unwrapped_opaque_ids == innerscope_opaque_ids

    def test_multiplexor_get_unreferenced_entities_returns_wrapped_entities_from_primary_system_scope(
        self,
        multiplexor: BdmMultiplexor,
        primary_bdm_scope: IStorageScope,
    ):
        entity = primary_bdm_scope.store_stream(b"hello")
        wrapped_entity = entity.model_copy(
            update={"opaque_identifier": f"{PRIMARY_BDM_SYSTEM_NAME}/{entity.opaque_identifier}", "entity_id": ""},
        )
        unreferenced_entities = multiplexor.get_unreferenced_entities(PROJECT_BOUNDARY, [])
        assert len(unreferenced_entities) == 1
        unreferenced_entity = unreferenced_entities[0]
        # entity_id is changing when entity is being multiplexed
        assert wrapped_entity == unreferenced_entity.model_copy(update={"entity_id": ""})

    def test_multiplexor_get_unreferenced_entities_filters_entities_from_sub_system_scope(
        self,
        multiplexor: BdmMultiplexor,
        subsystem_scope: IStorageScope,
    ):
        subsystem_scope.store_stream(b"hello")
        unreferenced_entities = multiplexor.get_unreferenced_entities(PROJECT_BOUNDARY, [])
        assert len(unreferenced_entities) == 0

    def test_multiplexor_unwrap_handle_remove_prefix_opaque_identifier(
        self,
        primary_bdm_scope: IStorageScope,
        subsystem_scope: IReadStorageScope,
    ):
        multiplexor = BdmMultiplexor(primary_bdm_scope, {"subsystem": subsystem_scope})
        sub_entity_handle = EntityHandle(
            entity_id=uuid4(),
            opaque_identifier="subsystem/project_id/bdm/context/12345678:_DELIMITERfile.txt",
            is_blob=True,
        )
        unwrapped_handle, _ = multiplexor._unwrap_handle(sub_entity_handle)  # pyright: ignore[reportPrivateUsage]
        assert unwrapped_handle.opaque_identifier == sub_entity_handle.opaque_identifier.removeprefix("subsystem/")


class TestAsyncMultiplexor:
    @pytest.fixture
    async def primary(self, tmp_path: Path) -> AsyncGenerator[IAsyncStorageScope]:
        project_dir = tmp_path / "project_files" / "abcdefghijklmnopqrstuvwx"
        project_dir.mkdir(parents=True, exist_ok=True)
        storage_factory = create_shared_storage_factory()
        async with await storage_factory.create_async_storage_scope(
            METHOD_CONTEXT,
            {
                "ROOT": str(project_dir.parent),
                "PROJECT_ID": str(project_dir.name),
                "SHORTID": "12345678",
            },
        ) as primary:
            yield primary

    @pytest.fixture
    async def subsystem(self, tmp_path: Path) -> AsyncGenerator[IAsyncReadStorageScope]:
        sub_dir = tmp_path / "sub" / "abcdefghijklmnopqrstuvwx"
        sub_dir.mkdir(parents=True, exist_ok=True)
        storage_factory = create_shared_storage_factory()
        async with await storage_factory.create_async_storage_scope(
            METHOD_CONTEXT,
            {
                "ROOT": str(sub_dir.parent),
                "PROJECT_ID": str(sub_dir.name),
                "SHORTID": "12345678",
            },
        ) as primary:
            yield primary

    @pytest.fixture
    async def multiplexor(self, primary: IAsyncStorageScope, subsystem: IAsyncReadStorageScope) -> AsyncBdmMultiplexor:
        return AsyncBdmMultiplexor(primary, {"subsystem": subsystem})

    async def test_multiplexor_wrap_handle_prefix_opaque_identifier(self, primary: IAsyncStorageScope):
        multiplexor = AsyncBdmMultiplexor(primary, {})
        async with await primary.begin_store(relative_location=Path("result.txt")) as writer:
            await writer.stream.send(b"hello world!")
        wrapped_handle = multiplexor.wrap_handle(PRIMARY_BDM_SYSTEM_NAME, writer.handle)
        assert wrapped_handle.opaque_identifier == f"{PRIMARY_BDM_SYSTEM_NAME}/{writer.handle.opaque_identifier}"

    async def test_multiplexor_wrap_handle_wrong_bdm_system_name_raise_error(self, multiplexor: AsyncBdmMultiplexor):
        test_txt = await multiplexor.get_storage_root() / "test.txt"
        test_txt.touch()
        entity = await multiplexor.store(test_txt)
        with pytest.raises(ValueError, match="The BDM system 'wrong_bdm_system_name' cannot be found."):
            multiplexor.wrap_handle("wrong_bdm_system_name", entity)

    async def test_multiplexor_get_storage_root_use_primary_system(
        self,
        multiplexor: AsyncBdmMultiplexor,
        primary: IAsyncStorageScope,
    ):
        assert await multiplexor.get_storage_root() == await primary.get_storage_root()

    async def test_multiplexor_store_wraps_entity_with_primary_system(self, multiplexor: AsyncBdmMultiplexor):
        test_txt = await multiplexor.get_storage_root() / "test.txt"
        test_txt.touch()
        handle = await multiplexor.store(test_txt)
        assert handle.opaque_identifier.startswith(PRIMARY_BDM_SYSTEM_NAME)

    async def test_multiplexor_store_stream_wraps_entity_with_primary_system(self, multiplexor: AsyncBdmMultiplexor):
        handle = await multiplexor.store_stream(b"hello world")
        assert handle.opaque_identifier.startswith(PRIMARY_BDM_SYSTEM_NAME)

    async def test_multiplexor_begin_store_wraps_entity_with_primary_system(self, multiplexor: AsyncBdmMultiplexor):
        async with await multiplexor.begin_store(relative_location=Path("result.txt")) as writer:
            await writer.stream.send(b"hello world!")
        assert writer.handle.opaque_identifier.startswith(PRIMARY_BDM_SYSTEM_NAME)

    async def test_multiplexor_store_entities_wraps_entities_in_primary_system(
        self,
        multiplexor: AsyncBdmMultiplexor,
        primary: IAsyncStorageScope,
    ):
        handle = await primary.store_stream(b"hello")
        stored_entities = multiplexor.get_stored_entities()
        async for stored_entity in stored_entities:
            assert f"{PRIMARY_BDM_SYSTEM_NAME}/{handle.opaque_identifier}" == stored_entity.opaque_identifier

    @dataclass
    class MockEntityHandle:
        seen_from_system: EntityHandle
        seen_from_multiplexor: EntityHandle
        inner_scope: IAsyncStorageScope
        system_name: str

    @pytest.fixture(params=["primary", "subsystem"])
    async def created_entity(
        self,
        request: pytest.FixtureRequest,
        primary: IAsyncStorageScope,
        subsystem: IAsyncStorageScope,
    ) -> MockEntityHandle:
        system_name = request.param
        # getfixturevalue does not work with pytest-asyncio...
        # https://github.com/pytest-dev/pytest-asyncio/issues/112
        inner_scope: IAsyncStorageScope = primary if system_name == "primary" else subsystem
        entity_handle = await inner_scope.store_stream(b"hello")
        wrapped_entity = entity_handle.model_copy(
            update={"opaque_identifier": f"{system_name}/{entity_handle.opaque_identifier}"},
        )
        return TestAsyncMultiplexor.MockEntityHandle(
            seen_from_system=entity_handle,
            seen_from_multiplexor=wrapped_entity,
            inner_scope=inner_scope,
            system_name=system_name,
        )

    @pytest.fixture(params=["primary", "subsystem"])
    async def created_dir_entity(
        self,
        request: pytest.FixtureRequest,
        primary: IAsyncStorageScope,
        subsystem: IAsyncStorageScope,
    ) -> MockEntityHandle:
        system_name = request.param
        # getfixturevalue does not work with pytest-asyncio...
        # https://github.com/pytest-dev/pytest-asyncio/issues/112
        inner_scope: IAsyncStorageScope = primary if system_name == "primary" else subsystem
        directory = await inner_scope.get_storage_root() / "dir"
        directory.mkdir()
        my_file = directory / "my_file.txt"
        my_file.write_text("hello")
        entity_handle = await inner_scope.store(directory)
        wrapped_entity = entity_handle.model_copy(
            update={"opaque_identifier": f"{system_name}/{entity_handle.opaque_identifier}"},
        )
        return TestAsyncMultiplexor.MockEntityHandle(
            seen_from_system=entity_handle,
            seen_from_multiplexor=wrapped_entity,
            inner_scope=inner_scope,
            system_name=system_name,
        )

    async def test_multiplexor_get_cached_returns_from_inner_system_scope(
        self,
        created_entity: MockEntityHandle,
        multiplexor: AsyncBdmMultiplexor,
    ):
        assert await multiplexor.get_cached(
            created_entity.seen_from_multiplexor,
        ) == await created_entity.inner_scope.get_cached(
            created_entity.seen_from_system,
        )

    async def test_multiplexor_get_text_returns_from_inner_system_scope(
        self,
        created_entity: MockEntityHandle,
        multiplexor: AsyncBdmMultiplexor,
    ):
        assert await multiplexor.get_text(
            created_entity.seen_from_multiplexor,
        ) == await created_entity.inner_scope.get_text(
            created_entity.seen_from_system,
        )

    async def test_multiplexor_get_bytes_returns_from_inner_system_scope(
        self,
        created_entity: MockEntityHandle,
        multiplexor: AsyncBdmMultiplexor,
    ):
        assert await multiplexor.get_bytes(
            created_entity.seen_from_multiplexor,
        ) == await created_entity.inner_scope.get_bytes(
            created_entity.seen_from_system,
        )

    async def test_multiplexor_get_stream_returns_from_inner_system_scope(
        self,
        created_entity: MockEntityHandle,
        multiplexor: AsyncBdmMultiplexor,
    ):
        multiplexor_stream = await multiplexor.get_stream(created_entity.seen_from_multiplexor)
        inner_scope_stream = await created_entity.inner_scope.get_stream(created_entity.seen_from_system)
        assert await multiplexor_stream.receive() == await inner_scope_stream.receive()

    async def test_multiplexor_get_copy_returns_from_inner_system_scope(
        self,
        created_entity: MockEntityHandle,
        tmp_path: Path,
        multiplexor: AsyncBdmMultiplexor,
    ):
        multiplexor_dest = tmp_path / "multiplexor_dest.txt"
        inner_scope_dest = tmp_path / "inner_scope_dest.txt"
        await multiplexor.get_copy(created_entity.seen_from_multiplexor, multiplexor_dest)
        await created_entity.inner_scope.get_copy(created_entity.seen_from_system, inner_scope_dest)
        assert multiplexor_dest.read_text() == inner_scope_dest.read_text()

    async def test_multiplexor_get_child_returns_wrapped_entity_from_inner_system_scope(
        self,
        created_dir_entity: MockEntityHandle,
        multiplexor: AsyncBdmMultiplexor,
    ):
        multiplexor_child = await multiplexor.get_child(created_dir_entity.seen_from_multiplexor, "my_file.txt")
        inner_scope_child = await created_dir_entity.inner_scope.get_child(
            created_dir_entity.seen_from_system,
            "my_file.txt",
        )
        assert (
            multiplexor_child.opaque_identifier.removeprefix(
                f"{created_dir_entity.system_name}/",
            )
            == inner_scope_child.opaque_identifier
        )

    async def test_multiplexor_get_parent_returns_wrapped_entity_from_inner_system_scope(
        self,
        created_dir_entity: MockEntityHandle,
        multiplexor: AsyncBdmMultiplexor,
    ):
        child = await multiplexor.get_child(created_dir_entity.seen_from_multiplexor, "my_file.txt")
        parent = await multiplexor.get_parent(child)
        assert parent is not None
        assert parent.original_name == "dir"
        assert (
            parent.opaque_identifier.removeprefix(created_dir_entity.system_name + "/")
            == created_dir_entity.seen_from_system.opaque_identifier
        )

    async def test_multiplexor_get_children_returns_wrapped_entities_from_inner_system_scope(
        self,
        created_dir_entity: MockEntityHandle,
        multiplexor: AsyncBdmMultiplexor,
    ):
        multiplexor_children = [
            child.opaque_identifier.removeprefix(f"{created_dir_entity.system_name}/")
            async for child in multiplexor.get_children(created_dir_entity.seen_from_multiplexor)
        ]
        innerscope_children = [
            child.opaque_identifier
            async for child in created_dir_entity.inner_scope.get_children(created_dir_entity.seen_from_system)
        ]
        assert len(multiplexor_children) == len(innerscope_children)
        assert multiplexor_children == innerscope_children

    async def test_multiplexor_get_unreferenced_entities_returns_wrapped_entities_from_primary_system_scope(
        self,
        multiplexor: AsyncBdmMultiplexor,
        primary: IAsyncStorageScope,
    ):
        entity = await primary.store_stream(b"hello")
        wrapped_entity = entity.model_copy(
            update={"opaque_identifier": f"{PRIMARY_BDM_SYSTEM_NAME}/{entity.opaque_identifier}", "entity_id": ""},
        )
        unreferenced_entities = await multiplexor.get_unreferenced_entities(PROJECT_BOUNDARY, [])
        assert len(unreferenced_entities) == 1
        unreferenced_entity = unreferenced_entities[0]
        # entity_id is changing when entity is being multiplexed
        assert wrapped_entity == unreferenced_entity.model_copy(update={"entity_id": ""})

    async def test_multiplexor_get_unreferenced_entities_filters_entities_from_sub_system_scope(
        self,
        multiplexor: AsyncBdmMultiplexor,
        subsystem: IAsyncStorageScope,
    ):
        await subsystem.store_stream(b"hello")
        unreferenced_entities = await multiplexor.get_unreferenced_entities(PROJECT_BOUNDARY, [])
        assert len(unreferenced_entities) == 0

    def test_multiplexor_unwrap_handle_remove_prefix_opaque_identifier(
        self,
        primary: IAsyncStorageScope,
        subsystem: IAsyncReadStorageScope,
    ):
        multiplexor = AsyncBdmMultiplexor(primary, {"subsystem": subsystem})
        sub_entity_handle = EntityHandle(
            entity_id=uuid4(),
            opaque_identifier="subsystem/project_id/bdm/context/12345678:_DELIMITERfile.txt",
            is_blob=True,
        )
        unwrapped_handle, _ = multiplexor._unwrap_handle(sub_entity_handle)  # pyright: ignore[reportPrivateUsage]
        assert unwrapped_handle.opaque_identifier == sub_entity_handle.opaque_identifier.removeprefix("subsystem/")

    async def test_async_multiplexor_wrap_handle_prefix_opaque_identifier(
        self,
        primary: IAsyncStorageScope,
    ):
        multiplexor = AsyncBdmMultiplexor(primary, {})
        async with await primary.begin_store(relative_location=Path("result.txt")) as writer:
            await writer.stream.send(b"hello world!")
        wrapped_handle = multiplexor.wrap_handle(PRIMARY_BDM_SYSTEM_NAME, writer.handle)
        assert wrapped_handle.opaque_identifier == f"{PRIMARY_BDM_SYSTEM_NAME}/{writer.handle.opaque_identifier}"

    def test_async_multiplexor_subsystem_name_containing_slash_raise_error(
        self,
        primary: IAsyncStorageScope,
        subsystem: IAsyncReadStorageScope,
    ):
        with pytest.raises(ValueError, match="Subsystem names cannot contain the following character: '/'"):
            AsyncBdmMultiplexor(primary, {"wrong/name": subsystem})
