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

import uuid

from pydantic import BaseModel

from ansys.bdm.api import EntityHandle, RecursiveDictionaryOfEntityHandles


def test_recursive_dictionary_can_be_serialized_and_deserialized():
    class Step(BaseModel):
        data: RecursiveDictionaryOfEntityHandles

    x = RecursiveDictionaryOfEntityHandles()
    x["a"] = EntityHandle(
        is_blob=True,
        original_name="a",
        entity_id=uuid.uuid4(),
        opaque_identifier="X",
    )

    s = Step(data=x)
    reconstructed_step = Step.model_validate_json(s.model_dump_json())
    assert isinstance(reconstructed_step.data["a"], EntityHandle)
