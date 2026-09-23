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

from uuid import UUID

from pydantic import BaseModel


class EntityHandle(BaseModel, frozen=True):
    """
    A handle to a entity stored by a BDM provider and the associated lightweight data about it.

    This lightweight, immutable object is intended to be easy to serialize and pass around across processes,
    services, and hosts. The actual behavior of the entity contents is up to the :class:`IStorageScope` or
    :class:`IAsyncStorageScope`.

    """

    is_blob: bool
    """True if this entity refers to a blob. False if it refers to a collection of blobs."""
    original_name: str | None = None
    """
    The original filename of the entity.

    This is just the filename and does not include the path. May be `None` or empty if not known.
    May not refer to a file on the local system.
    """
    entity_id: UUID
    """
    A unique id that identifies the entity.

    Typically this value is a new, random Guid created at the moment that the
    :class:`Entityandle` is created from contents such as a file on disk. It should
    be preserved across clone and save/load operations. It is not guaranteed to be
    the same value if you read the same contents into an BlobHandle twice.

    The UUID '00000000-0000-0000-0000-000000000000' is reserved for :data:`NO_ENTITY`.
    """
    opaque_identifier: str
    """
    A custom identifier that the :class:`IStorageScope` can use to identify the
    handle. Opaque as each BDM system may have its own form for this field. Consumers
    are not to assume anything about this field, even if it looks parseable.
    """
    mime_type: str | None = None
    """
    The mime type of the data, if it is known. None otherwise.
    """
    encoding: str | None = None
    """
    The Internet Assigned Numbers Authority (IANA) registered encoding name used for textual data.

    This may be None if not known and should not be set for binary mime types.

    This encoding name may be passed to other languages and implementations. IANA registered
    encoding names MUST be used.
    """
    size: int | None = None
    """
    Size of the data in bytes, if known.

    Size must be None if is_blob is False.

    Note that 0 is a valid blob size and has a different meaning than None.
    """

    def __eq__(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        __value: object,
        /,
    ) -> bool:
        return isinstance(__value, EntityHandle) and self.opaque_identifier == __value.opaque_identifier

    def __hash__(self) -> int:
        return self.opaque_identifier.__hash__()


# TODO: Documentation on a module constant doesn't appear to be working.
#: A constant empty EntityHandle which means no content or metadata has been assigned.
NO_ENTITY: EntityHandle = EntityHandle(
    is_blob=True,
    original_name="",
    entity_id=UUID(int=0),
    opaque_identifier="",
)
