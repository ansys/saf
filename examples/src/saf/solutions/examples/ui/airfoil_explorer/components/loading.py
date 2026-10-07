# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Loading wrapper component."""

from dash_extensions.enrich import dcc

LOADING_OVERLAY_STYLE = {
    "visibility": "visible",
    "filter": "blur(2px)",
}


def loading_wrapper(
    children,
    *,
    loading_id: str | None = None,
):
    """Wrap children in a standardized loading component."""
    return dcc.Loading(
        id=loading_id,
        type="circle",
        color="#ffb71b",
        overlay_style=LOADING_OVERLAY_STYLE,
        children=children,
    )
