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

"""Visor Dash viewer component utilities."""
from ansys.visor.viewer.config import settings
import visordash

VISOR_HOST = settings.default_host
VISOR_PORT = settings.default_port


def get_visor_dash_component(id="input", host=VISOR_HOST, port=VISOR_PORT, aspect_ratio=1.77, pixel_density=1000):
    """Create and return a VisorDash component for visualization."""
    return visordash.Visordash(id=id, host=host, port=port, aspectRatio=aspect_ratio, pixelDensity=pixel_density)
