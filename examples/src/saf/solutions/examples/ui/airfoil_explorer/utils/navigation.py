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

"""URL helpers for the Airfoil Explorer pages."""

from __future__ import annotations

from urllib.parse import urlparse

AIRFOIL_EXPLORER_URL_SEGMENT = "airfoil-explorer"


def get_airfoil_explorer_page(href: str | None) -> str | None:
    """Return the Airfoil Explorer page slug of a URL, or None when the URL is not an Airfoil Explorer page.

    Args:
        href: Full URL of the browser location (``dcc.Location.href``).

    Returns:
        The last path segment (``about``, ``airfoil-setup``, ``simulation`` or ``report``) when the URL points
        to a page of the Airfoil Explorer, otherwise None.
    """
    if not href:
        return None
    segments = urlparse(href).path.strip("/").split("/")
    if len(segments) >= 2 and segments[-2] == AIRFOIL_EXPLORER_URL_SEGMENT:
        return segments[-1]
    return None
