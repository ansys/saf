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

"""Simulation runner package -- re-exports public API for backward compatibility."""

from saf.solutions.examples.solution.airfoil_explorer.utils.simulation_runner.base import SimulationRunner  # noqa: F401
from saf.solutions.examples.solution.airfoil_explorer.utils.simulation_runner.hps_runner import (  # noqa: F401
    HpsSimulationRunner,
    HpsUnavailableError,
)
from saf.solutions.examples.solution.airfoil_explorer.utils.simulation_runner.local_runner import (  # noqa: F401
    LocalSimulationRunner,
)
from saf.solutions.examples.solution.airfoil_explorer.utils.simulation_runner.simulation_status import (  # noqa: F401
    SimulationStatus,
)

__all__ = [
    "SimulationRunner",
    "LocalSimulationRunner",
    "HpsSimulationRunner",
    "HpsUnavailableError",
    "SimulationStatus",
]
