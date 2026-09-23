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
from typing import Protocol

from anyio.abc import ByteSendStream

from ansys.bdm.api.entity_handle import EntityHandle


class IAsyncEntityWriter(Protocol):
    """
    An object used to create a new entity from a stream of data.

    Instances are created from :func:`IAsyncStorageScope.begin_store()`
    """

    async def __aenter__(self) -> "IAsyncEntityWriter":
        """Start writing data that will comprise an entity."""
        # deliberately not implemented
        ...

    async def __aexit__(
        self,
        __exc_type: type[BaseException] | None,  # noqa: PYI063
        __exc_value: BaseException | None,
        __traceback: TracebackType | None,
    ) -> None:
        """
        Finish collecting data and store entity.

        This method will throw an exception if __enter__ has not been called.
        """
        # deliberately not implemented
        ...

    @property
    def stream(self) -> ByteSendStream:
        """
        Return object that can be written to, which will be stored as the entity.

        This method will throw an exception if __enter__ has not been called.

        This method will throw an exception if __exit__ has been called.
        """
        # deliberately not implemented
        ...

    @property
    def handle(self) -> EntityHandle:
        """
        Return the entity created by this object.

        This method will throw an exception if __exit__ has not been called.
        """
        # deliberately not implemented
        ...
