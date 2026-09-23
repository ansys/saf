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

from ansys.bdm.api.entity_handle import EntityHandle
from ansys.bdm.api.iasync_storage_scope import IAsyncStorageScope
from ansys.bdm.base.encoder import encode_text
from anyio import EndOfStream


class AsyncStorageScopeBase(IAsyncStorageScope):
    """
    A partial implementation of ``IAsyncStorageScope`` that provides implementations
    of some methods based on other more fundamental methods.  ``AsyncStorageScopeBase``
    can be used as a base class for implementations of ``IAsyncStorageScope``.

    """

    async def get_bytes(self, entity: EntityHandle) -> bytes:
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
        stream = await self.get_stream(entity)
        result = bytearray()
        while True:
            try:
                data = await stream.receive()
                result.extend(data)
            except EndOfStream:
                break
        return bytes(result)

    async def get_text(self, entity: EntityHandle, encoding: str | None = None) -> str:
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
            the contents of the blob referenced by ``entity`` in text form with the encoding determined
            in order of preference:
            - the encoding argument if not None
            - the encoding field of the entity argument if set
            - the BOM of the referenced entity if it contains one; or
            - UTF-8

        Raises
        ------

        CannotGenerateStreamForDirectoryError
            If the entity requested is a collection
        """

        data = await self.get_bytes(entity)
        return encode_text(data, entity, encoding)
