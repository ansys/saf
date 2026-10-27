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

"""Conversion of the Fluent case into a scene the Visor viewer can load."""

from pathlib import Path
import shutil
import subprocess
import sys

from saf.solutions.examples.solution.logic.pump import export_fluent_vtkhdf
from saf.solutions.examples.solution.logic.pump.constants import CASE_FILE_NAME, DATA_FILE_NAME, SCENE_FILE_NAME

_ERROR_TAIL_CHARS = 2000


def export_scene(case_path: Path, data_path: Path, work_dir: Path, scene_file_name: str = SCENE_FILE_NAME) -> Path:
    """Convert a Fluent case and its data file into a VTKHDF scene.

    Parameters
    ----------
    case_path : Path
        Fluent ``.cas.h5`` file.
    data_path : Path
        Fluent ``.dat.h5`` file that belongs to the case.
    work_dir : Path
        Directory that receives the scene.
    scene_file_name : str
        File name of the scene written into ``work_dir``.

    Returns
    -------
    Path
        Path of the written ``.vtkhdf`` file.

    Raises
    ------
    RuntimeError
        If the conversion fails.
    """
    # VTK's Fluent reader only finds the data file when it sits next to the case under the same
    # stem. Cached BDM files carry no such guarantee, so both are copied side by side first.
    case_copy = work_dir / CASE_FILE_NAME
    data_copy = work_dir / DATA_FILE_NAME
    output_path = work_dir / scene_file_name
    shutil.copyfile(case_path, case_copy)
    shutil.copyfile(data_path, data_copy)
    # The conversion runs in a child process because VTK's Fluent reader keeps both input files
    # open until its process exits. In-process, the BDM sweep that follows the transaction could
    # not delete the copies and failed with WinError 32.
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            export_fluent_vtkhdf.__name__,
            "--case",
            str(case_copy),
            "--data",
            str(data_copy),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[-_ERROR_TAIL_CHARS:]
        raise RuntimeError(f"The case could not be converted for the 3D viewer: {detail}")
    return output_path
