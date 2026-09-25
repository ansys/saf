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

from ansys.bdm.api import (
    NO_ENTITY,
    EntityHandle,
    EntityNotFoundInBlobStorageError,
    InvalidContextError,
)
from ansys.bdm.shared_volume.identifier_parser import IdentifierParser
from ansys.bdm.shared_volume.storage_configuration import SharedFilesystemConfiguration

type PathTreeDict = dict[str, "PathTreeDict"]


class PathTree:
    def __init__(self):
        self._tree: PathTreeDict | None = None

    @classmethod
    def _check_entity_is_directory(cls, entity: Path):
        if not entity.is_dir():
            # we try to raise a helpful error message if the entity is not a directory
            # because its going to be difficult to understand if its not a directory
            # we're expecting to occur if someone has messed with the storage scope
            # after a handle was created in that scope
            raise EntityNotFoundInBlobStorageError(
                f"At least one handle was created when {entity.name} was a file system directory "
                f"containing referenced entities however it is now a file at {entity}",
            )

    def _create_path_branch(self, parts: list[str]) -> PathTreeDict:
        if not parts:
            return {}
        else:
            return {parts[0]: self._create_path_branch(parts[1:])}

    def _add_path_to_tree(self, node: PathTreeDict, parts: list[str]):
        if len(parts) == 0:
            raise AssertionError("parts should not be empty when adding a path to the tree")
        if not node:
            # don't extend the tree if it's a leaf node i.e. has been referenced before
            return
        if parts[0] in node:
            if len(parts) == 1:
                # prune the tree so that the referenced node is a leaf node
                # this code is not normally reachable if the paths are added shortest first (which they are)
                node[parts[0]] = {}
            else:
                # continue traversing the tree
                self._add_path_to_tree(node[parts[0]], parts[1:])
        else:
            # add the path to the tree down to the referenced node
            node[parts[0]] = self._create_path_branch(parts[1:])

    def add_to_tree(self, path: Path):
        # path is the relative path of a file or directory within a storage scope root derived from a handle
        # we assume it is not empty because it is not possible for a handle to reference the root of a storage scope
        parts = list(path.parts)
        if self._tree is None:
            self._tree = self._create_path_branch(parts)
        else:
            self._add_path_to_tree(self._tree, parts)

    def _find_unreferenced_paths(self, node: PathTreeDict, root: Path) -> list[Path]:
        if not node:
            return []

        self._check_entity_is_directory(root)

        unreferenced_paths: list[Path] = []
        for entry in root.iterdir():
            if entry.name in node:
                unreferenced_paths.extend(self._find_unreferenced_paths(node[entry.name], entry))
            else:
                unreferenced_paths.append(entry)

        return unreferenced_paths

    def find_unreferenced_paths(self, root: Path) -> list[Path]:
        if self._tree is None:
            self._check_entity_is_directory(root)
            return list(root.iterdir())

        return self._find_unreferenced_paths(self._tree, root)


class EntityTracker:
    def __init__(self, context: str, config: SharedFilesystemConfiguration):
        """
        Parameters
        ----------

        context: str
            the name of the context to be used for this scope

        config: SharedFilesystemConfiguration
            The storage configuration"""
        # TODO: check that volume strings and config keys don't contain the handle delimiter
        if context not in config.contexts:
            raise InvalidContextError(f"context {context} is not an available context")

        self._storage_root = Path(config.shared_filesystem_root, config.contexts[context].relative_path)
        self._stored_entities: list[EntityHandle] = []
        self._config = config

    @property
    def required_files(self) -> list[Path]:
        return [self.get_handle_path(e) for e in self._stored_entities]

    def get_storage_root(self) -> Path:
        self._storage_root.mkdir(parents=True, exist_ok=True)
        return self._storage_root.resolve()

    def add_stored_entity(self, entity: EntityHandle):
        self._stored_entities.append(entity)

    @property
    def stored_entities(self) -> list[EntityHandle]:
        return self._stored_entities

    def get_original_storage_root(self, handle: EntityHandle) -> Path:
        return self._config.shared_filesystem_root / IdentifierParser(handle).relative_path_of_original_storage_root

    def get_handle_path(self, handle: EntityHandle) -> Path:
        if handle == NO_ENTITY:
            raise EntityNotFoundInBlobStorageError("accessing storage using NO_ENTITY handle")

        return self._config.shared_filesystem_root / IdentifierParser(handle).relative_path

    def create_handle(
        self,
        storage_root: Path,
        path: Path,
        mime_type: str | None = None,
        encoding: str | None = None,
    ) -> EntityHandle:
        return IdentifierParser.create_handle(
            self._config.shared_filesystem_root,
            storage_root,
            path,
            mime_type,
            encoding,
        )

    def get_unreferenced_entities(self, context: str, live_handles: list[EntityHandle]) -> list[EntityHandle]:
        # Compute a local directory that defines the physical boundary of the given context
        context_relative_path = self._config.contexts[context].relative_path
        context_boundary_path = self._config.shared_filesystem_root / context_relative_path

        # Now, convert the supplied list of handles into a set of relative paths that refer to files and directories
        # at the root of the scope in which they were created
        storage_root_to_handle_paths: dict[Path, list[Path]] = {}
        for handle in live_handles:
            if handle == NO_ENTITY:
                continue
            parser = IdentifierParser(handle)
            handle_storage_root = parser.relative_path_of_original_storage_root
            if str(handle_storage_root.parent) not in str(context_boundary_path):
                raise ValueError(
                    f"The storage scope has been misconfigured: the scope directory '{handle_storage_root.as_posix()}'"
                    f" is not a subdirectory of the '{context}' context",
                )
            absolute_storage_root = self._config.shared_filesystem_root / handle_storage_root
            if absolute_storage_root not in storage_root_to_handle_paths:
                storage_root_to_handle_paths[absolute_storage_root] = []

            storage_root_to_handle_paths[absolute_storage_root].append(
                parser.relative_path_within_original_storage_root,
            )

        if not context_boundary_path.exists():
            return []

        unreferenced_handles: list[EntityHandle] = []

        # assume that the storage root is a subdirectory of the context boundary
        for storage_root in context_boundary_path.iterdir():
            self._get_unreferenced_handles_in_storage_root(
                storage_root_to_handle_paths,
                unreferenced_handles,
                storage_root,
            )

        return unreferenced_handles

    def _get_unreferenced_handles_in_storage_root(
        self,
        storage_root_to_handle_paths: dict[Path, list[Path]],
        unreferenced_handles: list[EntityHandle],
        storage_root: Path,
    ):
        if handle_paths := storage_root_to_handle_paths.get(storage_root):
            # this is an optimization to reduce the number of parts of handles that are examined
            handle_paths.sort(key=lambda p: len(str(p)))
        else:
            handle_paths = []

        tree = PathTree()
        for path in handle_paths:
            tree.add_to_tree(path)

        unreferenced_paths = tree.find_unreferenced_paths(storage_root)

        # Convert paths to entities
        for unreferenced_path in unreferenced_paths:
            unreferenced_handle = IdentifierParser.create_handle(
                file_system_root=self._config.shared_filesystem_root,
                storage_root=storage_root,
                path=unreferenced_path,
            )
            unreferenced_handles.append(unreferenced_handle)
