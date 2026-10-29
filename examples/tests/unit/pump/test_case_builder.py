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

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from saf.solutions.examples.solution.logic.pump import case_builder
from saf.solutions.examples.solution.logic.pump.constants import (
    CASE_FILE_NAME,
    DATA_FILE_NAME,
    DENSITY_WATER,
    GRAVITY,
    MESH_IMAGE_NAME,
    SOLVER_EXIT_WAIT_SECONDS,
)


@pytest.fixture
def fake_fluent(monkeypatch, tmp_path):
    """Patch PyFluent so build_case runs without a solver."""
    solver = MagicMock()
    solver.settings.results.graphics.mesh.__getitem__.return_value.surfaces_list.allowed_values.return_value = [
        "inlet",
        "blade",
    ]
    monkeypatch.setattr(case_builder.pyfluent, "launch_fluent", MagicMock(return_value=solver))

    def fake_download(file_name: str, repository: str, save_path: str) -> str:
        path = Path(save_path) / file_name
        path.write_bytes(b"mesh")
        return str(path)

    monkeypatch.setattr(case_builder.examples, "download_file", fake_download)
    return solver


def test_build_case_returns_expected_artefact_paths(fake_fluent, tmp_path):
    artifacts = case_builder.build_case(tmp_path, processor_count=4, progress=lambda stage, fraction: None)
    assert artifacts.case_path == tmp_path / CASE_FILE_NAME
    assert artifacts.mesh_image_path == tmp_path / MESH_IMAGE_NAME
    assert artifacts.zone_names == ["blade", "inlet"]


def test_build_case_launches_fluent_with_the_requested_processor_count(fake_fluent, tmp_path):
    case_builder.build_case(tmp_path, processor_count=8, progress=lambda stage, fraction: None)
    _, kwargs = case_builder.pyfluent.launch_fluent.call_args
    assert kwargs["processor_count"] == 8
    assert kwargs["mode"] == "solver"
    assert kwargs["cwd"] == str(tmp_path)


def test_build_case_configures_the_sst_turbulence_model(fake_fluent, tmp_path):
    case_builder.build_case(tmp_path, processor_count=4, progress=lambda stage, fraction: None)
    viscous = fake_fluent.settings.setup.models.viscous
    assert viscous.model == "k-omega"
    assert viscous.k_omega_model == "sst"


def test_build_case_enables_frame_motion_without_setting_the_rotation_speed(fake_fluent, tmp_path):
    case_builder.build_case(tmp_path, processor_count=4, progress=lambda stage, fraction: None)
    impeller = fake_fluent.settings.setup.cell_zone_conditions.fluid.__getitem__.return_value
    assert impeller.reference_frame.frame_motion is True
    # The rotation speed belongs to the operating point. If build_case assigned it, the
    # attribute would hold a float instead of the auto-created mock.
    assert isinstance(impeller.reference_frame.mrf_omega.value, MagicMock)


def test_build_case_builds_the_head_expression_from_the_density_constant(fake_fluent, tmp_path):
    case_builder.build_case(tmp_path, processor_count=4, progress=lambda stage, fraction: None)
    expression = fake_fluent.settings.setup.named_expressions.create.return_value
    assert f"{DENSITY_WATER} [kg/m^3]" in expression.definition
    assert f"{GRAVITY}[m/s^2]" in expression.definition
    assert "998.2 [kg/m^3] * 9.81[m/s^2]" in expression.definition


def test_build_case_writes_the_case_and_data_files(fake_fluent, tmp_path):
    artifacts = case_builder.build_case(tmp_path, processor_count=4, progress=lambda stage, fraction: None)
    fake_fluent.settings.file.write.assert_called_once_with(
        file_type="case-data", file_name=str(tmp_path / CASE_FILE_NAME)
    )
    assert artifacts.data_path == tmp_path / DATA_FILE_NAME


def test_build_case_always_exits_the_session_even_on_failure(fake_fluent, tmp_path):
    fake_fluent.settings.file.read_mesh.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        case_builder.build_case(tmp_path, processor_count=4, progress=lambda stage, fraction: None)
    fake_fluent.exit.assert_called_once_with(wait=SOLVER_EXIT_WAIT_SECONDS)


def test_build_case_rejects_an_out_of_range_processor_count(fake_fluent, tmp_path):
    with pytest.raises(ValueError, match="processor_count must be between 1 and 32"):
        case_builder.build_case(tmp_path, processor_count=99, progress=lambda stage, fraction: None)


def test_build_case_reports_progress_stages_in_order(fake_fluent, tmp_path):
    seen: list[tuple[str, float]] = []
    case_builder.build_case(
        tmp_path, processor_count=4, progress=lambda stage, fraction: seen.append((stage, fraction))
    )
    assert [stage for stage, _ in seen][:2] == ["Launching Fluent", "Reading meshes"]
    assert seen[-1][1] == 1.0
