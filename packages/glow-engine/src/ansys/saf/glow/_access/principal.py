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

"""The identity behind a request. Must stay free of heavy imports: it is used by the method runner."""

from dataclasses import dataclass

ON_BEHALF_OF_HEADER = "x-glow-on-behalf-of"
"""Header carrying the id of the initiating user on API-key (internal) requests made by a running method."""


@dataclass(frozen=True)
class Principal:
    """Who is making a request.

    ``user_id`` is the ``sub`` claim of the access token, or, for internal calls (``is_internal``), the user on whose
    behalf the call is made. It is ``None`` when the caller cannot be identified. ``is_internal`` is true when the
    request was authenticated with the local API key.
    """

    user_id: str | None
    is_super_admin: bool
    is_internal: bool
