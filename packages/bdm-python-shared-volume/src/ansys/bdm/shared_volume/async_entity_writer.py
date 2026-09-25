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

from types import TracebackType

import anyio
from anyio.abc import ByteSendStream
from anyio.streams.file import FileWriteStream

from ansys.bdm.api import (
    EntityHandle,
    EntityWriterHasNotCompletedWritingDataError,
    EntityWriterHasWrittenDataError,
    EntityWriterIsNotWritingDataError,
    IAsyncEntityWriter,
    IAsyncStorageScope,
)


class AsyncEntityWriter(IAsyncEntityWriter):
    def __init__(
        self,
        scope: IAsyncStorageScope,
        path: anyio.Path,
        mime_type: str | None = None,
        encoding: str | None = None,
    ):
        self._scope = scope
        self._path = path
        self._entered = False
        self._exited = False
        self._mime_type = mime_type
        self._encoding = encoding

    async def __aenter__(self) -> "AsyncEntityWriter":
        """start writing data that will comprise an entity"""
        if self._entered:
            raise EntityWriterHasWrittenDataError("data has been written once already")
        self._entered = True
        self._stream = await FileWriteStream.from_path(self._path)
        return self

    async def __aexit__(
        self,
        __exc_type: type[BaseException] | None,  # noqa: PYI063
        __exc_value: BaseException | None,
        __traceback: TracebackType | None,
    ) -> None:
        """finish collecting data and store entity
        This method will throw an exception if __enter__ has not been called.
        This method will throw an exception if __exit__ has been called."""
        self._check_writing_in_progress()
        self._exited = True
        await self._stream.aclose()
        self._handle = await self._scope.store(self._path, self._mime_type, self._encoding)

    @property
    def stream(self) -> ByteSendStream:
        """returns object that can be written to, which will be stored as the entity.
        This method will throw an exception if __enter__ has not been called.
        This method will throw an exception if __exit__ has been called."""
        self._check_writing_in_progress()
        return self._stream

    def _check_writing_in_progress(self):
        if not self._entered:
            raise EntityWriterIsNotWritingDataError("writing context has not been entered")
        if self._exited:
            raise EntityWriterIsNotWritingDataError("writing context has closed")

    @property
    def handle(self) -> EntityHandle:
        """returns the entity created by this object
        This method will throw an exception if __exit__ has not been called"""
        if not self._exited:
            raise EntityWriterHasNotCompletedWritingDataError("writing has not completed")
        return self._handle
