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

import subprocess
import sys
from unittest.mock import MagicMock

import pytest

from saf.solutions.pump.solution.logic import scene_export
from saf.solutions.pump.solution.logic.constants import (
    CASE_FILE_NAME,
    DATA_FILE_NAME,
    SCENE_FILE_NAME,
    SOLVED_SCENE_FILE_NAME,
)


@pytest.fixture
def inputs(tmp_path):
    source = tmp_path / "cache"
    source.mkdir()
    (source / "a.cas.h5").write_bytes(b"case")
    (source / "b.dat.h5").write_bytes(b"data")
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    return source / "a.cas.h5", source / "b.dat.h5", work_dir


def test_export_scene_pairs_the_files_and_converts_in_a_child_process(monkeypatch, inputs):
    case_path, data_path, work_dir = inputs
    run = MagicMock(return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(scene_export.subprocess, "run", run)

    result = scene_export.export_scene(case_path, data_path, work_dir)

    # The Fluent reader only finds <stem>.dat.h5 next to <stem>.cas.h5.
    assert (work_dir / DATA_FILE_NAME).read_bytes() == b"data"
    command = run.call_args.args[0]
    assert command[:3] == [sys.executable, "-m", "saf.solutions.compressor.solution.logic.export_fluent_vtkhdf"]
    assert command[3:] == [
        "--case",
        str(work_dir / CASE_FILE_NAME),
        "--data",
        str(work_dir / DATA_FILE_NAME),
        "--output",
        str(work_dir / SCENE_FILE_NAME),
    ]
    assert result == work_dir / SCENE_FILE_NAME


def test_export_scene_writes_the_requested_scene_name(monkeypatch, inputs):
    case_path, data_path, work_dir = inputs
    run = MagicMock(return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(scene_export.subprocess, "run", run)

    result = scene_export.export_scene(case_path, data_path, work_dir, SOLVED_SCENE_FILE_NAME)

    assert run.call_args.args[0][-1] == str(work_dir / SOLVED_SCENE_FILE_NAME)
    assert result == work_dir / SOLVED_SCENE_FILE_NAME


def test_export_scene_reports_the_converter_error(monkeypatch, inputs):
    failed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="RuntimeError: boom")
    monkeypatch.setattr(scene_export.subprocess, "run", MagicMock(return_value=failed))

    with pytest.raises(RuntimeError, match="boom"):
        scene_export.export_scene(*inputs)
