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

"""Image utility functions for UI components."""

from datetime import datetime

from ansys.saf.glow.solution import NO_ENTITY


def get_image_url_with_cache_bust(step, handle_name: str) -> str:
    """Get image URL with timestamp to force browser reload.

    Args:
        step: The step instance containing the image handle
        handle_name: Name of the handle attribute (e.g., "flow_png_handle")

    Returns:
        URL string with cache-busting timestamp, or empty string if handle is invalid
    """
    handle = getattr(step, handle_name)
    if handle == NO_ENTITY:
        return ""

    try:
        url = step.get_entity_url(handle_name)
        # Add timestamp query param to bust cache
        timestamp = datetime.now().timestamp()
        return f"{url}?t={timestamp}"
    except Exception:
        return ""
