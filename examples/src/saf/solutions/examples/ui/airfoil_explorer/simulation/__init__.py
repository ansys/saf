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

"""Simulation page package -- re-exports ``layout`` and registers callbacks on import."""

# Import callback modules to register their callbacks
from saf.solutions.examples.ui.airfoil_explorer.simulation import (
    logs_callbacks,
    status_callbacks,
    submission_callbacks,
    toggle_callbacks,
    visor_callbacks,
)
from saf.solutions.examples.ui.airfoil_explorer.simulation.layout import layout

__all__ = ["layout"]
