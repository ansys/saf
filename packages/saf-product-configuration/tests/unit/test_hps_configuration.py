# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import platform

import pytest

from ansys.saf.product_configuration.aedt import AedtInstanceConfiguration
from ansys.saf.product_configuration.fluent import (
    Fluent2DDPSolverInstanceConfiguration,
    Fluent3DDPMeshingInstanceConfiguration,
    Fluent3DDPSolverInstanceConfiguration,
)
from ansys.saf.product_configuration.geometry import GeometryInstanceConfiguration
from ansys.saf.product_configuration.interfaces import (
    IProductInstanceConfiguration,
    Software,
)
from ansys.saf.product_configuration.mapdl import MapdlInstanceConfiguration
from ansys.saf.product_configuration.mechanical import MechanicalInstanceConfiguration
from ansys.saf.product_configuration.optislang_wrapper import (
    OptislangWrapperInstanceConfiguration,
)
from ansys.saf.product_configuration.visor import VisorInstanceConfiguration
from ansys.saf.product_configuration.wrappers.versions import (
    AEDT_WRAPPER_VERSION,
    FLUENT_WRAPPER_VERSION,
    OPTISLANG_WRAPPER_VERSION,
)


@pytest.mark.parametrize(
    ("product_config", "version", "expected_software"),
    [
        (
            AedtInstanceConfiguration,
            "252",
            [
                ("Ansys SAF Product Wrapper [AEDT]", AEDT_WRAPPER_VERSION),
                ("Ansys Electronics Desktop", "2025 R2"),
            ],
        ),
        (
            Fluent2DDPSolverInstanceConfiguration,
            "252",
            [
                ("Ansys SAF Product Wrapper [Fluent]", FLUENT_WRAPPER_VERSION),
                ("Ansys Fluent", "2025 R2"),
            ],
        ),
        (
            Fluent3DDPMeshingInstanceConfiguration,
            "241",
            [
                ("Ansys SAF Product Wrapper [Fluent]", FLUENT_WRAPPER_VERSION),
                ("Ansys Fluent", "2024 R1"),
            ],
        ),
        (
            Fluent3DDPSolverInstanceConfiguration,
            "241",
            [
                ("Ansys SAF Product Wrapper [Fluent]", FLUENT_WRAPPER_VERSION),
                ("Ansys Fluent", "2024 R1"),
            ],
        ),
        (GeometryInstanceConfiguration, "261", [("Ansys Geometry", "2026 R1")]),
        (MapdlInstanceConfiguration, "251", [("Ansys Mechanical APDL", "2025 R1")]),
        (MechanicalInstanceConfiguration, "251", [("Ansys Mechanical", "2025 R1")]),
        (
            OptislangWrapperInstanceConfiguration,
            "241",
            [
                ("Ansys SAF Product Wrapper [optiSLang]", OPTISLANG_WRAPPER_VERSION),
                ("Ansys optiSLang", "2024 R1"),
            ],
        ),
        (VisorInstanceConfiguration, "0", [("Visor Viewer", "0")]),
    ],
)
def test_hps_software_requirement(
    product_config: type[IProductInstanceConfiguration],
    version: str,
    expected_software: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
):
    # GIVEN: Env vars pointing to supported Ansys installations
    mock_ansys_dir = "fake_ansys_install_dir"
    monkeypatch.setenv(f"AWP_ROOT{version}", mock_ansys_dir)
    monkeypatch.setenv(f"ANSYSEM_ROOT{version}", mock_ansys_dir)
    monkeypatch.setenv(f"GEOMETRY_ROOT{version}", mock_ansys_dir)

    if not expected_software:
        with pytest.raises(RuntimeError, match="is not officially supported by HPS yet."):
            software_reqs = product_config().get_version_configuration(version).software_requirements
        return

    software_reqs = product_config().get_version_configuration(version).software_requirements
    assert len(software_reqs) == len(expected_software)
    for i, software in enumerate(software_reqs):
        assert isinstance(software, Software)
        assert software.name == expected_software[i][0]
        assert software.version == expected_software[i][1]


def test_geometry_251_only_works_in_windows(monkeypatch: pytest.MonkeyPatch):
    # GIVEN: Env vars pointing to local Geometry installation
    mock_ansys_dir = "fake_ansys_install_dir"
    monkeypatch.setenv("GEOMETRY_ROOT251", mock_ansys_dir)

    # WHEN: Collecting HPS requirements
    if platform.system() == "Linux":
        with pytest.raises(
            ValueError,
            match="Only Windows platform is supported for Geometry version 251.",
        ):
            software_reqs = GeometryInstanceConfiguration().get_version_configuration("251").software_requirements
    else:
        software_reqs = GeometryInstanceConfiguration().get_version_configuration("251").software_requirements
        assert len(software_reqs) == 1
        assert isinstance(software_reqs[0], Software)
        assert software_reqs[0].name == "Ansys Geometry"
        assert software_reqs[0].version == "2025 R1"
