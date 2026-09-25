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

from io import BufferedIOBase, RawIOBase
from pathlib import Path
import shutil
from types import TracebackType
from typing import TYPE_CHECKING, Protocol

from ansys.bdm.api.entity_handle import EntityHandle
from ansys.bdm.api.ientity_writer import IEntityWriter
from ansys.bdm.api.recursive_dictionary import (
    RecursiveDictionaryOfEntityHandles,
    get_and_create_nested_dict,
    validate_path_component,
)
from ansys.bdm.api.storage_exceptions import NotFoundInLocalStorageRootError

if TYPE_CHECKING:
    from os import PathLike

    import ansys.bdm.api.iasync_storage_scope


class IReadStorageScope(Protocol):
    """
    Represents access to a read only Blob Data Management system.
    Allows consumers to produce and consume :class:`EntityHandle` instances.

    This is the synchronous version of the :class:`IAsyncReadStorageScope` interface.
    """

    def __enter__(self) -> "IReadStorageScope":
        """
        Track the set of files that are stored centrally.
        """
        # deliberately not implemented
        ...

    def __exit__(
        self,
        __exc_type: type[BaseException] | None,  # noqa: PYI063
        __exc_value: BaseException | None,
        __traceback: TracebackType | None,
    ) -> None:
        """
        Remove all files from local storage that are not stored centrally.
        """
        # deliberately not implemented
        ...

    def get_cached(self, entity: EntityHandle) -> Path:
        """
        Realize the data to a local filesystem if needed and returns a path to the cached or original file.

        The :class:`EntityHandle` is intended to represent an immutable value. The file
        returned by this call may point to a cached or even the original file. Callers
        must not modify the file on disk or undefined behavior, including class 3 errors,
        may occur. If the caller needs to modify the file, consider using
        :func:`get_copy()`, or copying the file before modifying it.

        Parameters
        ----------
        entity: EntityHandle
            The handle to the data to realize

        Returns
        -------
        Path
            The path to the contents of the EntityHandle as realized locally. The caller
            MUST NOT modify the returned path.
        """
        # deliberately not implemented
        ...

    def get_copy(self, entity: EntityHandle, destination: Path) -> None:
        """
        Realize the data to a local filesystem by writing to a specified file.

        The caller is free to modify the written file. The caller is responsible
        for deleting the generated file. If the destination path is within the storage root
        then the copy at that location will be deleted when the storage scope context is closed.

        Parameters
        ----------
        entity: EntityHandle
            The handle to the data to realize
        destination: Path
            The path to the file to write
        """
        # deliberately not implemented
        ...

    def get_stream(self, entity: EntityHandle) -> RawIOBase:
        """
        Open the EntityHandle contents for reading as a stream.

        The returned stream MUST NOT be writable. The returned stream MAY be seekable.

        Parameters
        ----------
        entity: EntityHandle
            The handle to the data to realize

        Returns
        -------
        RawIOBase
            The stream which, when read, will return the contents of the EntityHandle.

        Raises
        ------

        CannotGenerateStreamForDirectoryError
            If the entity requested is a collection
        """
        # deliberately not implemented
        ...

    def get_bytes(self, entity: EntityHandle) -> bytes:
        """
        Return the content of the referenced blob.

        Parameters
        ----------
        entity: EntityHandle
            The handle to the data to realize

        Returns
        -------
        bytes
            the contents of the EntityHandle.

        Raises
        ------

        CannotGenerateStreamForDirectoryError
            If the entity requested is a collection
        """
        # deliberately not implemented
        ...

    def get_text(self, entity: EntityHandle, encoding: str | None = None) -> str:
        """
        Return the content of the referenced blob.

        Parameters
        ----------
        entity: EntityHandle
            The handle to the data to realize
        encoding: Optional[str]
            The name of an encoding.  When this argument is not None the bytes
            of ``entity`` will be read using that encoding.

        Returns
        -------
        str
            the contents of the EntityHandle in text form with the encoding determined
            in order of preference by:
            - the encoding argument if not None
            - the encoding field of the entity argument if set
            - the BOM of the referenced entity if it contains one; or
            - UTF-8

        Raises
        ------

        CannotGenerateStreamForDirectoryError
            If the entity requested is a collection
        """
        # deliberately not implemented
        ...

    def get_children(self, entity: EntityHandle) -> list[EntityHandle]:
        """
        Return the entities contained in this entity.

        Parameters
        ----------

        entity: EntityHandle
            The entity to query


        Returns
        -------

        List[EntityHandle]
            The list of entities that are children of the provided entity

        Raises
        ------

        NotADirectoryError
            If the requested entity is not a directory

        """
        # deliberately not implemented
        ...

    def get_child(self, entity: EntityHandle, child_name: str) -> EntityHandle:
        """
        Return the entity contained in this entity with a given name.

        Parameters
        ----------

        entity: EntityHandle
            The entity to query
        child_name: str
            The child to search for

        Returns
        -------

        EntityHandle
            The :class:`EntityHandle` requested

        Raises
        ------

        NotADirectoryError
            If the requested entity is not a directory
        EntityNotFoundInBlobStorageError
            If the requested entity is not found
        """
        # deliberately not implemented
        ...

    def get_parent(self, entity: EntityHandle) -> EntityHandle | None:
        """
        Return the entity containing in this entity.

        Parameters
        ----------

        entity: EntityHandle
            The entity to query

        Returns
        -------

        Optional[EntityHandle]
            The :class:`EntityHandle` requested, or None if the entity is stored at the root of its scope.

        Raises
        ------

        EntityNotFoundInBlobStorageError
            If the requested entity is not found.
        """
        # deliberately not implemented
        ...

    def get_unreferenced_entities(
        self,
        context: str,
        live_handles: list[EntityHandle],
    ) -> list[EntityHandle]:
        """
        Return a list of all entities within the context that are not referenced by the given live entity handles.

        Parameters
        ----------

        context: str
            A label for storage scopes that enables them to be categorized and configured given
            a common system wide configuration.
            It defines the bounds over which methods supporting garbage collection are constrained.

        live_handles: list[EntityHandle]
            A list of handles that are expected to refer to blobs.

        Returns
        -------

        list[EntityHandle]
            The list of all entities within the context that are not referenced by the given live entity handles.

        Raises
        ------

        ValueError
            If the live_handles do not belong to the provided context.
        """
        # deliberately not implemented
        ...

    @property
    def asynchronous(
        self,
    ) -> "ansys.bdm.api.iasync_storage_scope.IAsyncReadStorageScope":
        """
        Return a object with an asynchronous interface to the same scope.
        """
        # deliberately not implemented
        ...

    def _copy_nested_dictionary(
        self,
        nested_dict: RecursiveDictionaryOfEntityHandles,
        current_path: Path,
        glob: str | None,
    ) -> None:
        for key, value in nested_dict.items():
            validate_path_component(key)
            dest_path = current_path / key
            if isinstance(value, EntityHandle):
                if not glob or dest_path.match(glob):
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    self.get_copy(value, dest_path)
            else:
                if not glob or dest_path.match(glob):
                    dest_path.mkdir(parents=True, exist_ok=True)
                # we cannot stop iterating. even if the directory does not match glob,
                # there may be files within it that do match glob.
                # Don't create the directory if it doesn't match, though, to avoid orphaned directories that would need
                # to be cleaned up later.
                self._copy_nested_dictionary(value, dest_path, glob)

    def get_copy_from_dictionary(
        self,
        root: "PathLike[str]",
        source: RecursiveDictionaryOfEntityHandles,
        glob: str | None = None,
    ) -> None:
        """
        Create a recursive directory structure containing copies of entities from source.

        This method creates a directory structure on the file system at root containing
        copies of the entities in source. If glob is None, all files at or within source
        are copied to root. Note that file and directory names used when creating the
        directory structure at root are always taken from the keys in source, not from
        the original_name attribute of the EntityHandle objects.

        Parameters
        ----------
        root : PathLike[str]
            The root directory to create the directory structure in.
        source : RecursiveDictionaryOfEntityHandles
            A recursive nested dictionary of EntityHandle objects.
        glob : str | None, optional
            A glob pattern to filter which files and directories to copy. Behaves
            identically to Path.match() and is interpreted as relative to root using
            the keys in source as the path components. Default is None.

        Raises
        ------
        NotADirectoryError
            If root points to an existing file.
        """
        # deliberately not implemented
        abs_dest_path = Path(root).resolve()
        if abs_dest_path.is_file():
            raise NotADirectoryError("destination path must be a directory")
        if abs_dest_path.is_dir():
            shutil.rmtree(abs_dest_path)
        abs_dest_path.mkdir(parents=True)
        # An implementation must perform matching against source not the file system. Callers expect the minimum number
        # of copies between BDM and root. An implementation which copied the whole of source to root then deleted
        # non-matching entities is not acceptable.
        self._copy_nested_dictionary(source, abs_dest_path, glob)


class IStorageScope(IReadStorageScope, Protocol):
    """
    Represents access to a Blob Data Management system. Allows consumers
    to produce and consume :class:`EntityHandle` instances.

    This is the synchronous version of the :class:`IAsyncStorageScope` interface.

    On dispose, files within the :func:`storage_root` that have not been passed to
    :func:`store()` will be deleted.
    """

    def __enter__(self) -> "IStorageScope":
        """
        Track the set of files that are stored centrally.
        """
        # deliberately not implemented
        ...

    def store(
        self,
        from_: "PathLike[str]",
        mime_type: str | None = None,
        encoding: str | None = None,
    ) -> EntityHandle:
        """
        Create an :class:`EntityHandle` from a file on disk.

        Many blob handler implementations will try to optimize performance and the file contents
        may not be immediately read from disk. To avoid class 3 type errors, the file MUST NOT be
        externally modified after calling this method.

        Parameters
        ----------

        from_: PathLike[str]
            The local file on disk which contains the contents for the generated :class:`EntityHandle`
        mime_type: Optional[str]
            Mime type of this file, if known. If None is passed in, the IAsyncStorageScope SHOULD
            use file extension to determine the mime type.
        encoding: Optional[str]
            The Internet Assigned Numbers Authority (IANA) registered encoding name used for textual data.
            This MAY be None if not known and SHOULD NOT be set for binary mime types.

        Returns
        -------
            An :class:`EntityHandle` that rerpesents the contents of the read file at the moment
            this method is invoked
        """
        # deliberately not implemented
        ...

    def store_stream(
        self,
        from_: RawIOBase | BufferedIOBase | bytes,
        relative_location: Path | None = None,
        mime_type: str | None = None,
        encoding: str | None = None,
    ) -> EntityHandle:
        """
        Fully reads a passed in stream and returns a handle for the given content.

        Parameters
        ----------

        from_ : Union[RawIOBase, BufferedIOBase, bytes]
            The stream or in-memory bytes from which the new entity will be created
        relative_location : Optional[Path]
            The nominal relative path of the entity. The path is relative to the storage_root of
            the scope.  No data is expected at this location.
            The filename from this path will be used as the original name of the entity.
            If this parameter is not set then the implementation will generate a unique location.
        mime_type: Optional[str]
            Mime type of this file, if known. If None is passed in, the IAsyncStorageScope SHOULD
            use file extension to determine the mime type.
        encoding: Optional[str]
            The Internet Assigned Numbers Authority (IANA) registered encoding name used for textual data.
            This MAY be None if not known and SHOULD NOT be set for binary mime types.

        Returns
        -------

        EntityHandle
            The :class:`EntityHandle` that represents the passed in data.
        """
        # deliberately not implemented
        ...

    def begin_store(
        self,
        relative_location: Path | None = None,
        mime_type: str | None = None,
        encoding: str | None = None,
    ) -> IEntityWriter:
        """
        Create an :class:`IEntityWriter` by writing to a stream object.

        Parameters
        ----------

        relative_location : Optional[Path]
            The nominal relative path of the entity. The path is relative to the storage_root of
            the scope.  No data is expected at this location.
            The filename from this path will be used as the original name of the entity.
            If this parameter is not set then the implementation will generate a unique location.
        mime_type: Optional[str]
            Mime type of this file, if known. If None is passed in, the IAsyncStorageScope SHOULD
            use file extension to determine the mime type.
        encoding: Optional[str]
            The Internet Assigned Numbers Authority (IANA) registered encoding name used for textual data.
            This MAY be None if not known and SHOULD NOT be set for binary mime types.

        Returns
        -------

        IEntityWriter
            An object which allows you to write to a stream and retrieve the handle.
        """
        # deliberately not implemented
        ...

    def get_storage_root(self) -> Path:
        """
        A local filesystem directory that can be used to stage files.

        Since this folder is managed by the BDM implementation, there may be performance
        benefits to storing files here.

        This directory usually is lazy instantiated on the first call to this function.
        """
        # deliberately not implemented
        ...

    @property
    def stored_entities(self) -> list[EntityHandle]:
        """
        The set of :class:`EntityHandle` instances that have been stored via this scope.
        """
        # deliberately not implemented
        ...

    def destroy(self, *entities: EntityHandle) -> None:
        """
        Delete the entities referenced by the handle.

        As :class:`EntityHandle` instances are intended to be simple immutable structures
        that can be passed across process and service boundaries, their lifespan must be managed
        by an external system. This call allows the resources associated with a BlobHandle
        to be removed.

        Parameters
        ----------

        *entities: EntityHandle
            The entities to delete
        """
        # deliberately not implemented
        ...

    @property
    def asynchronous(self) -> "ansys.bdm.api.iasync_storage_scope.IAsyncStorageScope":
        """
        Return an object with an asynchronous interface to the same scope.
        """
        # deliberately not implemented
        ...

    def store_to_dictionary(
        self,
        root: "PathLike[str]",
        glob: str | None = None,
    ) -> RecursiveDictionaryOfEntityHandles:
        """
        Create a recursive nested dictionary of EntityHandles from a directory.

        This method creates a recursive nested dictionary containing EntityHandle objects for files and nested
        dictionaries for directories. If glob is None, all files at or within root are included in the result.

        Parameters
        ----------
        root : PathLike[str]
            The root directory to store to a nested dictionary.
        glob : str | None, optional
            A glob pattern to filter which files and directories to include in the result. Behaves identically to
            Path.rglob() and is interpreted as relative to root. Default is None.

        Returns
        -------
        RecursiveDictionaryOfEntityHandles
            A recursive nested dictionary of EntityHandle objects.

        Raises
        ------
        FileNotFoundError
            If root does not exist.
        NotADirectoryError
            If root is a file.
        NotFoundInLocalStorageRootError
            If root is not within the storage root of storage scope.
        """
        abs_root_path = Path(root).resolve()

        storage_root = self.get_storage_root()
        try:
            abs_root_path.relative_to(storage_root)
        except ValueError as e:
            raise NotFoundInLocalStorageRootError(
                f"root path is not within the storage root. storage_root={storage_root}, root={root}",
            ) from e

        if not abs_root_path.exists():
            raise FileNotFoundError(f"root path does not exist: {root}")

        if abs_root_path.is_file():
            raise NotADirectoryError(f"root path is a file: {root}")

        result_dict = RecursiveDictionaryOfEntityHandles()
        for path in abs_root_path.rglob(glob or "*"):
            subdirs = path.parent.relative_to(abs_root_path).parts
            subresult_dict = get_and_create_nested_dict(subdirs, result_dict)
            if path.is_file():
                subresult_dict[path.name] = self.store(path)
            else:
                # needed, otherwise empty directories are not created in _get_and_create_nested_dict
                subresult_dict[path.name] = RecursiveDictionaryOfEntityHandles()

        return result_dict
