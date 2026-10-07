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

"""Path resolution utilities for UI components."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from saf.solutions.examples.solution.definition import ExamplesSolution

if TYPE_CHECKING:
    from ansys.saf.glow.solution import StepModel

# Mapping of step types to their log file names
LOG_FILE_NAMES: dict[str, str] = {
    "airfoil_setup": "airfoil_setup.log",
    "simulation": "simulation.log",
}


def get_step_log_file_path(step: StepModel, project: ExamplesSolution, logfile_name: str) -> str | None:
    """Resolve the log file path for a step.

    Returns the step's logfile if already set by a transaction, otherwise None.
    LogsSupervisor handles None gracefully and will start monitoring once the file exists.

    Args:
        step: The StepModel instance with a logfile attribute.
        logfile_name: Name of the log file (unused, kept for API consistency).

    Returns:
        Log file path string if set, None otherwise.
    """
    if step.logfile:
        return step.logfile

    project_dir = project.storage_scope.get_storage_root()
    if isinstance(project_dir, (str, Path)):
        return str((Path(project_dir) / logfile_name).resolve())

    return None
