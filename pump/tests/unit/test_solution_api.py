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

from unittest.mock import MagicMock

import pytest

from saf.solutions.pump.solution.definition import CompressorSolution
from saf.solutions.pump.solution.logic.case_builder import CaseArtifacts


def test_setup_step_exposes_its_defaults(client_project: CompressorSolution):
    setup_step = client_project.steps.setup_step
    assert setup_step.processor_count == 4
    assert setup_step.zone_names == []


def test_setup_step_accepts_a_new_processor_count(client_project: CompressorSolution):
    setup_step = client_project.steps.setup_step
    setup_step.processor_count = 8
    assert setup_step.processor_count == 8


def test_build_case_stores_the_artefacts(monkeypatch, client_project: CompressorSolution):
    def fake_build_case(work_dir, processor_count, progress, log):
        case_path = work_dir / "pump_volute_setup.cas.h5"
        case_path.write_bytes(b"case")
        data_path = work_dir / "pump_volute_setup.dat.h5"
        data_path.write_bytes(b"data")
        image_path = work_dir / "pump-volute-mesh.png"
        image_path.write_bytes(b"png")
        progress("Launching Fluent", 0.0)
        return CaseArtifacts(
            case_path=case_path, data_path=data_path, mesh_image_path=image_path, zone_names=["blade", "inlet"]
        )

    monkeypatch.setattr(
        "saf.solutions.compressor.solution.steps.setup_step.build_case",
        MagicMock(side_effect=fake_build_case),
    )

    setup_step = client_project.steps.setup_step
    setup_step.build_case().wait(timeout=60)

    assert setup_step.zone_names == ["blade", "inlet"]
    assert client_project.storage_scope.get_bytes(setup_step.case_file) == b"case"
    assert client_project.storage_scope.get_bytes(setup_step.data_file) == b"data"
    assert client_project.storage_scope.get_bytes(setup_step.mesh_image) == b"png"


def test_build_case_records_the_last_progress_stage(monkeypatch, client_project: CompressorSolution):
    def fake_build_case(work_dir, processor_count, progress, log):
        case_path = work_dir / "pump_volute_setup.cas.h5"
        case_path.write_bytes(b"case")
        data_path = work_dir / "pump_volute_setup.dat.h5"
        data_path.write_bytes(b"data")
        image_path = work_dir / "pump-volute-mesh.png"
        image_path.write_bytes(b"png")
        progress("Launching Fluent", 0.0)
        log(["Welcome to ANSYS Fluent"])
        progress("Case ready", 1.0)
        return CaseArtifacts(case_path=case_path, data_path=data_path, mesh_image_path=image_path, zone_names=[])

    monkeypatch.setattr(
        "saf.solutions.compressor.solution.steps.setup_step.build_case",
        MagicMock(side_effect=fake_build_case),
    )

    setup_step = client_project.steps.setup_step
    setup_step.build_case().wait(timeout=60)

    assert setup_step.progress_stage == "Case ready"
    assert setup_step.progress_fraction == 1.0
    # The transcript is persisted so that reopening the page still shows the console.
    assert "Welcome to ANSYS Fluent" in setup_step.log_text


def test_build_case_rejects_an_out_of_range_processor_count(client_project: CompressorSolution):
    setup_step = client_project.steps.setup_step
    setup_step.processor_count = 99
    with pytest.raises(Exception, match="processor_count must be between 1 and 32"):
        setup_step.build_case().wait(timeout=60)


def test_prepare_scene_stores_the_converted_case(monkeypatch, client_project: CompressorSolution):
    def fake_build_case(work_dir, processor_count, progress, log):
        case_path = work_dir / "pump_volute_setup.cas.h5"
        case_path.write_bytes(b"case")
        data_path = work_dir / "pump_volute_setup.dat.h5"
        data_path.write_bytes(b"data")
        image_path = work_dir / "pump-volute-mesh.png"
        image_path.write_bytes(b"png")
        return CaseArtifacts(case_path=case_path, data_path=data_path, mesh_image_path=image_path, zone_names=[])

    def fake_export_scene(case_path, data_path, work_dir):
        assert case_path.read_bytes() == b"case"
        assert data_path.read_bytes() == b"data"
        scene_path = work_dir / "pump_volute_setup.vtkhdf"
        scene_path.write_bytes(b"scene")
        return scene_path

    monkeypatch.setattr(
        "saf.solutions.compressor.solution.steps.setup_step.build_case",
        MagicMock(side_effect=fake_build_case),
    )
    monkeypatch.setattr(
        "saf.solutions.compressor.solution.steps.setup_step.export_scene",
        MagicMock(side_effect=fake_export_scene),
    )

    setup_step = client_project.steps.setup_step
    setup_step.build_case().wait(timeout=60)
    setup_step.prepare_scene().wait(timeout=60)

    assert client_project.storage_scope.get_bytes(setup_step.scene_file) == b"scene"


def test_prepare_scene_requires_a_built_case(client_project: CompressorSolution):
    setup_step = client_project.steps.setup_step
    with pytest.raises(Exception, match="Build the case before preparing the 3D view"):
        setup_step.prepare_scene().wait(timeout=60)
