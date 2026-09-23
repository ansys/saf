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

import re
from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ansys.bdm.api.entity_handle import EntityHandle


class RecursiveDictionaryOfEntityHandles(
    dict[str, "EntityHandle | RecursiveDictionaryOfEntityHandles"],
):
    """A recursive dictionary structure for storing entity handles in a nested hierarchy that maps a filesystem-like
    directory structure."""

    # Defining it as a class instead of a type, in case in the future we want to add methods that operate on the
    # recursive dict (e.g., filter) and don't require the storage scope.

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Generate Pydantic core schema to be able to serialize/deserialize this structure with Pydantic.

        We cannot use a simple:
        > return core_schema.no_info_after_validator_function(cls, handler(dict))
        because it would not instantiate the nested EntityHandles, leaving them as plain dictionaries.
        """
        entity_handle_schema = handler.generate_schema(EntityHandle)

        dict_schema = core_schema.dict_schema(
            keys_schema=core_schema.str_schema(),
            values_schema=core_schema.union_schema(
                [
                    entity_handle_schema,
                    core_schema.definition_reference_schema(
                        "RecursiveDictionaryOfEntityHandles",
                    ),
                ],
            ),
        )

        validated_schema = core_schema.no_info_after_validator_function(
            cls,
            dict_schema,
        )

        return core_schema.definitions_schema(
            schema=validated_schema,
            definitions=[
                core_schema.dict_schema(
                    keys_schema=core_schema.str_schema(),
                    values_schema=core_schema.union_schema(
                        [
                            entity_handle_schema,
                            core_schema.definition_reference_schema(
                                "RecursiveDictionaryOfEntityHandles",
                            ),
                        ],
                    ),
                    ref="RecursiveDictionaryOfEntityHandles",
                ),
            ],
        )


def get_and_create_nested_dict(
    parts: tuple[str, ...],
    value: RecursiveDictionaryOfEntityHandles,
) -> RecursiveDictionaryOfEntityHandles:
    if not parts:
        return value
    if parts[0] not in value:
        value[parts[0]] = RecursiveDictionaryOfEntityHandles()

    # Ensure the value at parts[0] is a RecursiveDictionaryOfEntityHandles
    nested_value = value[parts[0]]
    if not isinstance(nested_value, RecursiveDictionaryOfEntityHandles):
        # If it's an EntityHandle, we need to convert it to a nested dict
        # This shouldn't normally happen in correct usage, but we handle it for type safety
        nested_value = RecursiveDictionaryOfEntityHandles()
        value[parts[0]] = nested_value

    return get_and_create_nested_dict(
        parts[1:],
        nested_value,
    )


def validate_path_component(name: str) -> None:
    """Validate that a string is suitable for use as a file or directory name."""
    # Would be great if we could validate at assign or construction time, e.g.,:
    # > my_dict['invalid/string'] = my_entity
    # or
    # > my_dict = RecursiveDictionaryOfEntityHandles({'invalid/string': my_entity})
    # but given the definition of RecursiveDictionaryOfEntityHandles, we are left with validation only within
    # get_copy_from_dictionary()

    if not name or not name.strip():
        raise ValueError("Path component cannot be empty")
    if name in (".", ".."):  # special names for current and parent directory
        raise ValueError(f"Path component cannot be '{name}'")
    if name.endswith((".", " ")):  # Windows rule
        raise ValueError(f"Path component '{name}' cannot end with a dot or space")

    # Check for invalid characters
    # - Windows: < > : " / \\ | ? * and control characters (0-31)
    # - Linux: / and null character
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    if re.search(invalid_chars, name):
        raise ValueError(
            f"Path component '{name}' contains invalid characters. "
            f'The following characters are not allowed: < > : " / \\ | ? * and control characters',
        )
