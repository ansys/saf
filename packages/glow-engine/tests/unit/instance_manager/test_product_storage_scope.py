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
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil

import pytest

from ansys.bdm.api import NO_ENTITY, IStorageScope
from ansys.saf.glow._bdm.multiplexor import BdmMultiplexor
from ansys.saf.glow._bdm.storage_contexts import METHOD_CONTEXT, PRODUCT_CONTEXT
from ansys.saf.glow._bdm.storage_factory import create_shared_storage_factory, random_shortid
from ansys.saf.glow._bdm.storage_variable_names import PROJECT_ID, ROOT, SHORTID
from ansys.saf.glow._core.instance.storagescope import ProductStorageScope

STATE_DIR_NAME = "state_dir"
MOCK_PROJECT_ID = "664de7e977e87fb188a8e476"


@pytest.fixture
def project_directory_on_product(tmp_path: Path) -> Path:
    return tmp_path / "win" / "Ansys" / "glow" / "MySolution" / "project_files" / MOCK_PROJECT_ID


@pytest.fixture
def project_directory_on_solution(tmp_path: Path) -> Path:
    return tmp_path / "lin" / "Ansys" / "glow" / "MySolution" / "project_files" / MOCK_PROJECT_ID


@pytest.fixture
def asset_scope(tmp_path: Path, project_directory_on_solution: PureWindowsPath) -> Generator[IStorageScope]:
    storage_factory = create_shared_storage_factory()
    with storage_factory.create_storage_scope(
        METHOD_CONTEXT,
        {
            "ROOT": str(tmp_path / "asset_dir"),
            "PROJECT_ID": str(project_directory_on_solution.name),
            "SHORTID": random_shortid(),
        },
    ) as mock_scope:
        yield mock_scope


@pytest.fixture
def mock_transaction_scope(project_directory_on_solution: PureWindowsPath) -> Generator[IStorageScope]:
    storage_factory = create_shared_storage_factory()
    with storage_factory.create_storage_scope(
        METHOD_CONTEXT,
        {
            "ROOT": str(project_directory_on_solution.parent),
            "PROJECT_ID": str(project_directory_on_solution.name),
            "SHORTID": random_shortid(),
        },
    ) as mock_scope:
        yield mock_scope


@pytest.fixture
def product_storage_scope(
    project_directory_on_product: PureWindowsPath,
    project_directory_on_solution: PurePosixPath,
) -> ProductStorageScope:
    storage_scope_factory = create_shared_storage_factory()
    product_storage_scope_on_solution = storage_scope_factory.create_storage_scope(
        PRODUCT_CONTEXT,
        {
            ROOT: str(project_directory_on_solution.parent),
            PROJECT_ID: str(project_directory_on_product.name),
            SHORTID: random_shortid(),
        },
    ).__enter__()
    product_storage_scope = ProductStorageScope(
        storage_scope=product_storage_scope_on_solution,
        project_directory_path_on_solution=project_directory_on_solution,
        project_directory_path_on_product=project_directory_on_product,
        state_directory_name=STATE_DIR_NAME,
    )
    return product_storage_scope


def test_product_storage_root_return_path_on_product(tmp_path: Path, product_storage_scope: ProductStorageScope):
    assert re.search(
        rf"{tmp_path.as_posix()}/win/Ansys/glow/MySolution/project_files/{MOCK_PROJECT_ID}/bdm/product_\w{{8}}",
        product_storage_scope.get_storage_root().as_posix(),
    )


def test_product_storage_store_on_product(
    product_storage_scope: ProductStorageScope,
    project_directory_on_solution: PurePosixPath,
    project_directory_on_product: PureWindowsPath,
):
    p = product_storage_scope.get_storage_root() / "hello.txt"
    relative_path = p.relative_to(project_directory_on_product)
    Path(project_directory_on_solution / relative_path).write_text("hello")
    entity_handle = product_storage_scope.store(p)
    assert entity_handle != NO_ENTITY


def test_product_storage_store_on_solution_raise_error(
    mock_transaction_scope: IStorageScope,
    product_storage_scope: ProductStorageScope,
):
    filepath = mock_transaction_scope.get_storage_root() / "hello.txt"
    filepath.write_text("hello")
    with pytest.raises(ValueError, match=("'*' is not in the subpath of '*'")):
        product_storage_scope.store(filepath)


def test_product_storage_get_cached_return_path_on_product(
    tmp_path: Path,
    mock_transaction_scope: IStorageScope,
    product_storage_scope: ProductStorageScope,
):
    p = mock_transaction_scope.get_storage_root() / "hello.txt"
    p.write_text("hello")
    entity_handle = mock_transaction_scope.store(p)
    path_from_solution = mock_transaction_scope.get_cached(entity_handle)
    assert re.match(
        rf"{tmp_path.as_posix()}/lin/Ansys/glow/MySolution/project_files/{MOCK_PROJECT_ID}/bdm/method_\w{{8}}/hello.txt",
        path_from_solution.as_posix(),
    )

    path_from_product = product_storage_scope.get_cached(entity_handle)
    assert re.match(
        rf"{tmp_path.as_posix()}/win/Ansys/glow/MySolution/project_files/{MOCK_PROJECT_ID}/bdm/method_\w{{8}}/hello.txt",
        path_from_product.as_posix(),
    )


def test_product_storage_get_cached_outside_storage_scope_return_product_cache(
    tmp_path: Path,
    mock_transaction_scope: IStorageScope,
    asset_scope: IStorageScope,
    project_directory_on_product: PureWindowsPath,
    project_directory_on_solution: PurePosixPath,
):
    # Given an asset stored in a different storage scope
    multiplexor = BdmMultiplexor(mock_transaction_scope, {"method_asset": asset_scope})
    p = asset_scope.get_storage_root() / "hello.txt"
    p.write_text("hello")
    entity_handle = asset_scope.store(p)
    # (update the opaque identifier to indicate to the multiplexor it is from a subsidiary scope)
    wrapped_entity_handle = entity_handle.model_copy(
        update={"opaque_identifier": f"method_asset/{entity_handle.opaque_identifier}"},
    )
    product_scope = ProductStorageScope(
        multiplexor,
        project_directory_path_on_product=project_directory_on_product,
        project_directory_path_on_solution=project_directory_on_solution,
        state_directory_name=STATE_DIR_NAME,
    )
    # When getting the cached path from the product storage scope
    path_from_product = product_scope.get_cached(wrapped_entity_handle)
    uuid_regex = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    # Then the file is found in a new .product_cache directory
    assert re.match(
        rf"{tmp_path.as_posix()}/win/Ansys/glow/MySolution/project_files/{MOCK_PROJECT_ID}/state_dir/.product_cache/{uuid_regex}/hello.txt",
        path_from_product.as_posix(),
    )


def test_product_storage_get_copy(
    mock_transaction_scope: IStorageScope,
    product_storage_scope: ProductStorageScope,
    project_directory_on_solution: PurePosixPath,
):
    p = mock_transaction_scope.get_storage_root() / "hello.txt"
    p.write_text("hello")
    entity_handle = mock_transaction_scope.store(p)
    destination = product_storage_scope.get_storage_root() / "destination.txt"
    assert next(Path(project_directory_on_solution).rglob("destination.txt"), None) is None
    product_storage_scope.get_copy(entity_handle, destination)
    destination_file = next(Path(project_directory_on_solution).rglob("destination.txt"))
    assert destination_file.exists()


def test_product_storage_get_copy_destination_outside_product_storage_root_raise_error(
    mock_transaction_scope: IStorageScope,
    product_storage_scope: ProductStorageScope,
):
    p = mock_transaction_scope.get_storage_root() / "hello.txt"
    p.write_text("hello")
    entity_handle = mock_transaction_scope.store(p)
    destination = mock_transaction_scope.get_storage_root() / "destination.txt"
    with pytest.raises(
        ValueError,
        match=re.escape(f"The destination path '{str(destination)}' is not inside the product storage root"),
    ):
        product_storage_scope.get_copy(entity_handle, destination)


def test_product_storage_store_file_on_product_from_state_directory(
    product_storage_scope: ProductStorageScope,
    project_directory_on_solution: PurePosixPath,
    project_directory_on_product: PureWindowsPath,
):
    state_dir = Path(project_directory_on_product) / STATE_DIR_NAME
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "hello.txt"
    state_file.write_text("hello")
    # simulate the fact that the volume is shared and the file exists on the solution side
    state_dir_on_solution = Path(project_directory_on_solution / STATE_DIR_NAME)
    state_dir_on_solution.mkdir(parents=True, exist_ok=True)
    shutil.copy(state_file, state_dir_on_solution / "hello.txt")
    entity_handle = product_storage_scope.store_from_state_directory(state_file)
    assert entity_handle != NO_ENTITY
    new_filepath = Path(project_directory_on_solution).parent / entity_handle.opaque_identifier.replace(
        ":_DELIMITER",
        "/",
    )
    assert new_filepath.exists()


def test_product_storage_store_directory_on_product_from_state_directory(
    product_storage_scope: ProductStorageScope,
    project_directory_on_solution: PurePosixPath,
    project_directory_on_product: PureWindowsPath,
):
    state_dir = Path(project_directory_on_product) / STATE_DIR_NAME
    state_file = state_dir / "dir" / "hello.txt"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text("hello")
    # simulate the fact that the volume is shared and the file exists on the solution side
    state_dir_on_solution = Path(project_directory_on_solution / STATE_DIR_NAME)
    (state_dir_on_solution / "dir").mkdir(parents=True, exist_ok=True)
    shutil.copy(state_file, state_dir_on_solution / "dir" / "hello.txt")
    entity_handle = product_storage_scope.store_from_state_directory(state_file)
    assert entity_handle != NO_ENTITY
    new_filepath = Path(project_directory_on_solution).parent / entity_handle.opaque_identifier.replace(
        ":_DELIMITER",
        "/",
    )
    assert new_filepath.exists()


def test_product_storage_store_from_state_directory_outside_state_directory_raise_error(
    product_storage_scope: ProductStorageScope,
    tmp_path: Path,
):
    outside_state_dir_file = tmp_path / "outside_state_dir.txt"
    outside_state_dir_file.write_text("hello")
    with pytest.raises(
        ValueError,
        match=re.escape(
            f"The file '{str(outside_state_dir_file)}' is not inside the product state directory.",
        ),
    ):
        product_storage_scope.store_from_state_directory(outside_state_dir_file)
