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

from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from pathlib import Path
import random
import string

import pytest

from ansys.bdm.api import (
    EntityHandle,
    IAsyncStorageScope,
    IStorageScope,
    IStorageScopeFactory,
    RecursiveDictionaryOfEntityHandles,
)
from ansys.bdm.shared_volume.storage_configuration import (
    SharedFilesystemConfiguration,
    SharedFilesystemContextConfiguration,
)
from ansys.bdm.shared_volume.storage_factory import StorageScopeFactory
from tests.content import CONTENT, create_directory_content


def get_random_identifier(k: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choices(alphabet, k=k))


class SharedVolumeStorageFactoryForTest(StorageScopeFactory):
    def __init__(self):
        config = SharedFilesystemConfiguration(
            shared_filesystem_root=Path("$TEMP_DIR"),
            contexts={
                "TEST": SharedFilesystemContextConfiguration(relative_path=Path("$PROJECT_ID/$UUID")),
                "PROJECT_BOUNDARY": SharedFilesystemContextConfiguration(relative_path=Path("$PROJECT_ID")),
            },
        )
        super().__init__(config)


@pytest.fixture(scope="session")
def storage_scope_factory_under_test() -> IStorageScopeFactory:
    return SharedVolumeStorageFactoryForTest()


SimpleStorageScopeFactory = Callable[[], IStorageScope]
SimpleAsyncStorageScopeFactory = Callable[[], Awaitable[IAsyncStorageScope]]


@pytest.fixture
def storage_scope_factory(
    storage_scope_factory_under_test: IStorageScopeFactory,
    tmp_path: Path,
) -> SimpleStorageScopeFactory:
    return lambda: storage_scope_factory_under_test.create_storage_scope(
        "TEST",
        {
            "TEMP_DIR": str(tmp_path),
            "UUID": get_random_identifier(),
            "PROJECT_ID": str(f"proj_{get_random_identifier(k=12)}"),
        },
    )


@pytest.fixture
async def async_storage_scope_factory(
    storage_scope_factory_under_test: IStorageScopeFactory,
    tmp_path: Path,
) -> SimpleAsyncStorageScopeFactory:
    return lambda: storage_scope_factory_under_test.create_async_storage_scope(
        "TEST",
        {
            "TEMP_DIR": str(tmp_path),
            "UUID": get_random_identifier(),
            "PROJECT_ID": str(f"proj_{get_random_identifier(k=12)}"),
        },
    )


@pytest.fixture
def file_entity(storage_scope_factory: SimpleStorageScopeFactory) -> EntityHandle:
    with storage_scope_factory() as scope:
        x = scope.get_storage_root() / "x.txt"
        x.write_text(CONTENT)
        return scope.store(x)


@pytest.fixture
def directory_entity(storage_scope_factory: SimpleStorageScopeFactory) -> EntityHandle:
    with storage_scope_factory() as scope:
        return scope.store(create_directory_content(scope.get_storage_root()))


@pytest.fixture
def destroyed_file_entity(file_entity: EntityHandle, storage_scope_factory: SimpleStorageScopeFactory) -> EntityHandle:
    with storage_scope_factory() as scope:
        scope.destroy(file_entity)
    return file_entity


@pytest.fixture
def destroyed_directory_entity(
    directory_entity: EntityHandle,
    storage_scope_factory: SimpleStorageScopeFactory,
) -> EntityHandle:
    with storage_scope_factory() as scope:
        scope.destroy(directory_entity)
    return directory_entity


@pytest.fixture
def create_directory_structure() -> Callable[[Path], None]:
    def _create_directory_structure(base_dir: Path) -> None:
        """
        Helper to create a comprehensive directory structure for testing. Should include:
        - files and subdirs
        - nested directories
        - various file types and names
        - empty directories at different levels
        - hidden files

        Structure:
        test_root/
            .hidden_file.txt
            single_file.txt
            file.multiple.dots.json
            empty_dir_root/
                (empty)
            src/
                main.py
            level1/
                level2/
                    deep_file.txt
                empty_dir_nested/
                    (empty)
        """
        base_dir.mkdir(parents=True, exist_ok=True)
        (base_dir / ".hidden_file.txt").write_text("hidden content")
        (base_dir / "single_file.txt").write_text("single content")
        (base_dir / "file.multiple.dots.json").write_text('{"key": "value"}')
        (base_dir / "empty_dir_root").mkdir()
        src_dir = base_dir / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("main source")
        deep_path = base_dir / "level1" / "level2"
        deep_path.mkdir(parents=True)
        (deep_path / "deep_file.txt").write_text("deep content")
        (base_dir / "level1" / "empty_dir_nested").mkdir()

    return _create_directory_structure


@pytest.fixture
def scope(storage_scope_factory: SimpleStorageScopeFactory) -> Generator[IStorageScope, None, None]:
    with storage_scope_factory() as storage_scope:
        yield storage_scope


@pytest.fixture
async def async_scope(
    async_storage_scope_factory: SimpleAsyncStorageScopeFactory,
) -> AsyncGenerator[IAsyncStorageScope, None]:
    async with await async_storage_scope_factory() as storage_scope:
        yield storage_scope


@pytest.fixture
def test_root(
    scope: IStorageScope,
    create_directory_structure: Callable[[Path], None],
) -> Path:
    root = scope.get_storage_root()
    test_root_path = root / "test_root"
    create_directory_structure(test_root_path)
    return test_root_path


@pytest.fixture
async def async_test_root(
    async_scope: IAsyncStorageScope,
    create_directory_structure: Callable[[Path], None],
) -> Path:
    root = await async_scope.get_storage_root()
    test_root_path = root / "test_root"
    create_directory_structure(test_root_path)
    return test_root_path


@pytest.fixture
def manually_create_dictionary() -> Callable[[dict[str, EntityHandle]], RecursiveDictionaryOfEntityHandles]:
    def _manually_create_dictionary(entities: dict[str, EntityHandle]) -> RecursiveDictionaryOfEntityHandles:
        # match the structure in create_directory_structure
        return RecursiveDictionaryOfEntityHandles(
            {
                ".hidden_file.txt": entities["hidden_file"],
                "single_file.txt": entities["single_file"],
                "file.multiple.dots.json": entities["multiple_dots_file"],
                "empty_dir_root": RecursiveDictionaryOfEntityHandles(),
                "src": RecursiveDictionaryOfEntityHandles(
                    {
                        "main.py": entities["main_py"],
                    },
                ),
                "level1": RecursiveDictionaryOfEntityHandles(
                    {
                        "level2": RecursiveDictionaryOfEntityHandles(
                            {
                                "deep_file.txt": entities["deep_file"],
                            },
                        ),
                        "empty_dir_nested": RecursiveDictionaryOfEntityHandles(),
                    },
                ),
            },
        )

    return _manually_create_dictionary


@pytest.fixture
def manually_create_dictionary_simple_syntax() -> Callable[
    [dict[str, EntityHandle]],
    RecursiveDictionaryOfEntityHandles,
]:
    def _manually_create_dictionary_simple_syntax(
        entities: dict[str, EntityHandle],
    ) -> RecursiveDictionaryOfEntityHandles:
        # Ignore pyright issues on purpose to simulate what a solution developer could do and make sure that it still
        # works.
        # match the structure in create_directory_structure
        return {  # pyright: ignore
            ".hidden_file.txt": entities["hidden_file"],
            "single_file.txt": entities["single_file"],
            "file.multiple.dots.json": entities["multiple_dots_file"],
            "empty_dir_root": {},
            "src": {"main.py": entities["main_py"]},
            "level1": {
                "level2": {"deep_file.txt": entities["deep_file"]},
                "empty_dir_nested": {},
            },
        }

    return _manually_create_dictionary_simple_syntax


@pytest.fixture
def source_dict(
    scope: IStorageScope,
    create_directory_structure: Callable[[Path], None],
    manually_create_dictionary: Callable[[dict[str, EntityHandle]], RecursiveDictionaryOfEntityHandles],
    manually_create_dictionary_simple_syntax: Callable[[dict[str, EntityHandle]], RecursiveDictionaryOfEntityHandles],
    request: pytest.FixtureRequest,
) -> RecursiveDictionaryOfEntityHandles:
    root = scope.get_storage_root()
    create_directory_structure(root)

    hidden_file_entity = scope.store(root / ".hidden_file.txt")
    single_file_entity = scope.store(root / "single_file.txt")
    multiple_dots_entity = scope.store(root / "file.multiple.dots.json")
    main_py_entity = scope.store(root / "src" / "main.py")
    deep_file_entity = scope.store(root / "level1" / "level2" / "deep_file.txt")

    creation_syntax = getattr(request, "param", "full_syntax")
    method = (
        manually_create_dictionary if creation_syntax == "full_syntax" else manually_create_dictionary_simple_syntax
    )
    return method(
        {
            "hidden_file": hidden_file_entity,
            "single_file": single_file_entity,
            "multiple_dots_file": multiple_dots_entity,
            "main_py": main_py_entity,
            "deep_file": deep_file_entity,
        },
    )


@pytest.fixture
async def async_source_dict(
    async_scope: IAsyncStorageScope,
    create_directory_structure: Callable[[Path], None],
    manually_create_dictionary: Callable[[dict[str, EntityHandle]], RecursiveDictionaryOfEntityHandles],
    manually_create_dictionary_simple_syntax: Callable[[dict[str, EntityHandle]], RecursiveDictionaryOfEntityHandles],
    request: pytest.FixtureRequest,
) -> RecursiveDictionaryOfEntityHandles:
    root = await async_scope.get_storage_root()
    create_directory_structure(root)

    hidden_file_entity = await async_scope.store(root / ".hidden_file.txt")
    single_file_entity = await async_scope.store(root / "single_file.txt")
    multiple_dots_entity = await async_scope.store(root / "file.multiple.dots.json")
    main_py_entity = await async_scope.store(root / "src" / "main.py")
    deep_file_entity = await async_scope.store(root / "level1" / "level2" / "deep_file.txt")

    creation_syntax = getattr(request, "param", "full_syntax")
    method = (
        manually_create_dictionary if creation_syntax == "full_syntax" else manually_create_dictionary_simple_syntax
    )
    return method(
        {
            "hidden_file": hidden_file_entity,
            "single_file": single_file_entity,
            "multiple_dots_file": multiple_dots_entity,
            "main_py": main_py_entity,
            "deep_file": deep_file_entity,
        },
    )
