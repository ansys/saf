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

import importlib
import inspect
import pkgutil
from types import SimpleNamespace
from typing import Any

import pytest

from ansys.saf.glow.solution import InstanceManager, ProductInstanceManager
import ansys.saf.product_manager as bdm_products
from ansys.saf.product_manager.aedt import HfssManager, IcepakManager, Maxwell2DManager, Maxwell3DManager
from ansys.saf.product_manager.fluent import (
    Fluent2DDPSolverManager,
    Fluent3DDPMeshingManager,
    Fluent3DDPSolverManager,
)
from ansys.saf.product_manager.geometry import GeometryManager
from ansys.saf.product_manager.mapdl import MapdlManager
from ansys.saf.product_manager.mechanical import MechanicalManager
from ansys.saf.product_manager.optislang_wrapper import OslManager
from ansys.saf.product_manager.visor import VisorManager
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution

EXPECTED_PRODUCTS = [
    "aedt",
    "fluent",
    "geometry",
    "mapdl",
    "mechanical",
    "optislang_wrapper",
    "visor",
]
EXPECTED_LEGACY_PRODUCTS = [product for product in EXPECTED_PRODUCTS if product != "visor"]
EXCLUDE_MODULES = ["_utilities", "legacy"]
EXPECTED_PRODUCT_MANAGERS = [
    "HfssManager",
    "IcepakManager",
    "Maxwell2DManager",
    "Maxwell3DManager",
    "Fluent2DDPSolverManager",
    "Fluent3DDPMeshingManager",
    "Fluent3DDPSolverManager",
    "GeometryManager",
    "MapdlManager",
    "MechanicalManager",
    "OslManager",
    "VisorManager",
]
EXPECTED_INTERNAL_MANAGERS = [
    "InternalHfssManagerImpl",
    "InternalIcepakManagerImpl",
    "InternalMaxwell2DManagerImpl",
    "InternalMaxwell3DManagerImpl",
    "Fluent2DDPSolverInternalManager",
    "Fluent3DDPMeshingInternalManager",
    "Fluent3DDPSolverInternalManager",
    "InternalGeometryManager",
    "InternalMapdlManager",
    "InternalMechanicalManager",
    "InternalOptislangManagerImpl",
    "InternalVisorManager",
]


@pytest.fixture(scope="module")
def discovered_managers() -> dict[str, dict[str, list[Any]]]:
    discovered_classes: dict[str, dict[str, list[Any]]] = {}
    for _, modname, ispkg in pkgutil.iter_modules(bdm_products.__path__, bdm_products.__name__ + "."):
        if not ispkg:
            continue
        module_name = modname.split(".")[-1]
        if module_name in EXCLUDE_MODULES:
            continue
        discovered_classes[module_name] = {"public": [], "internal": []}

        module = importlib.import_module(f"ansys.saf.product_manager.{module_name}")
        for class_name in module.__all__:
            cls = getattr(module, class_name)
            if not inspect.isclass(cls):
                continue
            elif issubclass(cls, InstanceManager):
                discovered_classes[module_name]["internal"].append(cls)
            elif issubclass(cls, ProductInstanceManager):
                discovered_classes[module_name]["public"].append(cls)

    return discovered_classes


def test_exposed_product_modules(discovered_managers: dict[str, dict[str, list[Any]]]):
    assert sorted(discovered_managers.keys()) == sorted(EXPECTED_PRODUCTS)


def test_exposed_public_managers(discovered_managers: dict[str, dict[str, list[Any]]]):
    discovered_public_managers_list = [
        cls.__name__ for product_managers in discovered_managers.values() for cls in product_managers["public"]
    ]
    assert sorted(discovered_public_managers_list) == sorted(EXPECTED_PRODUCT_MANAGERS)


def test_exposed_internal_managers(discovered_managers: dict[str, dict[str, list[Any]]]):
    discovered_internal_managers_list = [
        cls.__name__ for product_managers in discovered_managers.values() for cls in product_managers["internal"]
    ]
    assert sorted(discovered_internal_managers_list) == sorted(EXPECTED_INTERNAL_MANAGERS)


def test_linked_internal_managers_expose_product_name(discovered_managers: dict[str, dict[str, list[Any]]]):
    for product_managers in discovered_managers.values():
        for public_manager in product_managers["public"]:
            assert hasattr(public_manager, "_instance_manager_impl_type")
            assert public_manager._instance_manager_impl_type in product_managers["internal"]

        for private_manager in product_managers["internal"]:
            # required to easily modify existing built-in product configurations
            # this PRODUCT_NAME has to be the same as the one written in the product configuration
            assert hasattr(private_manager, "PRODUCT_NAME")


def test_recovery_state_info_has_defaults(discovered_managers: dict[str, dict[str, list[Any]]]):
    """Test that all internal managers can instantiate their recovery_state_info without providing arguments."""
    for product_managers in discovered_managers.values():
        for internal_manager in product_managers["internal"]:
            recovery_state_info = internal_manager.recovery_state_info_type()
            assert recovery_state_info


class MockMapdlClient:
    def __init__(self):
        self.port = 50052

    def graphics(self, mode: str) -> None:
        _ = mode


@pytest.mark.usefixtures("mock_product_instance")
@pytest.mark.parametrize(
    "mock_product_instance",
    [
        {"ansys.saf.product_manager.mapdl.MapdlManager": MockMapdlClient},
        {MapdlManager: MockMapdlClient},
    ],
    ids=["module_str", "class"],
    indirect=True,
)
def test_mapdl_manager_can_be_mocked_with_saf_testing(client_project: EndToEndSolution):
    port = client_project.steps.mapdl_step.launch_mapdl().wait()
    assert port == 50052


class MockMechanicalClient:
    def __init__(self):
        self._port = 50053


@pytest.mark.usefixtures("mock_product_instance")
@pytest.mark.parametrize(
    "mock_product_instance",
    [
        {"ansys.saf.product_manager.mechanical.MechanicalManager": MockMechanicalClient},
        {MechanicalManager: MockMechanicalClient},
    ],
    ids=["module_str", "class"],
    indirect=True,
)
def test_mechanical_manager_can_be_mocked_with_saf_testing(client_project: EndToEndSolution):
    client_project.steps.mechanical_instance_step.launch_mechanical().wait()
    assert client_project.steps.mechanical_instance_step.mechanical_port() == 50053


class MockHfssClient:
    def __init__(self):
        self.solution_type = "mock-solution-type"


@pytest.mark.usefixtures("mock_product_instance")
@pytest.mark.parametrize(
    "mock_product_instance",
    [{"ansys.saf.product_manager.aedt.HfssManager": MockHfssClient}, {HfssManager: MockHfssClient}],
    ids=["module_str", "class"],
    indirect=True,
)
def test_hfss_manager_can_be_mocked_with_saf_testing(client_project: EndToEndSolution):
    client_project.steps.aedt_solution_types_verification_step.initialize_hfss_instance_with_solution_type().wait()
    assert client_project.steps.aedt_solution_types_verification_step.retrieved_solution_type == "mock-solution-type"


class MockIcepakClient:
    def __init__(self):
        self.solution_type = "mock-solution-type"


@pytest.mark.usefixtures("mock_product_instance")
@pytest.mark.parametrize(
    "mock_product_instance",
    [{"ansys.saf.product_manager.aedt.IcepakManager": MockIcepakClient}, {IcepakManager: MockIcepakClient}],
    ids=["module_str", "class"],
    indirect=True,
)
def test_icepak_manager_can_be_mocked_with_saf_testing(client_project: EndToEndSolution):
    client_project.steps.aedt_solution_types_verification_step.initialize_icepak_instance_with_solution_type().wait()
    assert client_project.steps.aedt_solution_types_verification_step.retrieved_solution_type == "mock-solution-type"


class MockMaxwell2DClient:
    def __init__(self):
        self.aedt_version_id = "252"


@pytest.mark.usefixtures("mock_product_instance")
@pytest.mark.parametrize(
    "mock_product_instance",
    [{"ansys.saf.product_manager.aedt.Maxwell2DManager": MockMaxwell2DClient}, {Maxwell2DManager: MockMaxwell2DClient}],
    ids=["module_str", "class"],
    indirect=True,
)
def test_maxwell_2d_manager_can_be_mocked_with_saf_testing(client_project: EndToEndSolution):
    client_project.steps.maxwell_2d_verification_step.initialize_maxwell_2d_instance().wait()
    client_project.steps.maxwell_2d_verification_step.upload_aedt_version_from_aedt().wait()
    assert client_project.steps.maxwell_2d_verification_step.aedt_version == "252"


class MockMaxwell3DClient:
    def __init__(self):
        self.aedt_version_id = "252"


@pytest.mark.usefixtures("mock_product_instance")
@pytest.mark.parametrize(
    "mock_product_instance",
    [{"ansys.saf.product_manager.aedt.Maxwell3DManager": MockMaxwell3DClient}, {Maxwell3DManager: MockMaxwell3DClient}],
    ids=["module_str", "class"],
    indirect=True,
)
def test_maxwell_3d_manager_can_be_mocked_with_saf_testing(client_project: EndToEndSolution):
    client_project.steps.maxwell_3d_verification_step.initialize_maxwell_3d_instance().wait()
    client_project.steps.maxwell_3d_verification_step.upload_aedt_version_from_aedt().wait()
    assert client_project.steps.maxwell_3d_verification_step.aedt_version == "252"


class MockFluentClient:
    def __init__(self):
        self.product_kind = "mock-product"


@pytest.mark.usefixtures("mock_product_instance")
@pytest.mark.parametrize(
    "mock_product_instance",
    [
        {
            "ansys.saf.product_manager.fluent.Fluent3DDPSolverManager": MockFluentClient,
            "ansys.saf.product_manager.fluent.Fluent2DDPSolverManager": MockFluentClient,
            "ansys.saf.product_manager.fluent.Fluent3DDPMeshingManager": MockFluentClient,
        },
        {
            Fluent3DDPSolverManager: MockFluentClient,
            Fluent2DDPSolverManager: MockFluentClient,
            Fluent3DDPMeshingManager: MockFluentClient,
        },
    ],
    ids=["module_str", "class"],
    indirect=True,
)
def test_fluent_managers_can_be_mocked_with_saf_testing(client_project: EndToEndSolution):
    client_project.steps.fluent_instance_step.launch_fluent_3ddp_solver().wait()
    client_project.steps.fluent_instance_step.upload_fluent_3ddp_solver_product_kind()
    client_project.steps.fluent_instance_step.launch_fluent_2ddp_solver().wait()
    client_project.steps.fluent_instance_step.upload_fluent_2ddp_solver_product_kind()
    client_project.steps.fluent_instance_step.launch_fluent_3ddp_meshing().wait()
    client_project.steps.fluent_instance_step.upload_fluent_3ddp_meshing_product_kind()
    assert client_project.steps.fluent_instance_step.fluent_3ddp_solver_product_kind == "mock-product"
    assert client_project.steps.fluent_instance_step.fluent_2ddp_solver_product_kind == "mock-product"
    assert client_project.steps.fluent_instance_step.fluent_3ddp_meshing_product_kind == "mock-product"


class MockGeometryClient:
    def read_existing_design(self):
        return SimpleNamespace(name="MockGeometryDesign")


@pytest.mark.usefixtures("mock_product_instance")
@pytest.mark.parametrize(
    "mock_product_instance",
    [
        {"ansys.saf.product_manager.geometry.GeometryManager": MockGeometryClient},
        {GeometryManager: MockGeometryClient},
    ],
    ids=["module_str", "class"],
    indirect=True,
)
def test_geometry_manager_can_be_mocked_with_saf_testing(client_project: EndToEndSolution):
    client_project.steps.geometry_instance_step.launch_geometry().wait()
    client_project.steps.geometry_instance_step.get_active_design()
    assert client_project.steps.geometry_instance_step.active_design_name == "MockGeometryDesign"


class MockOptislangWrapperClient:
    def __init__(self):
        self.started = False

    def start(self, **_: Any) -> None:
        self.started = True


@pytest.mark.usefixtures("mock_product_instance")
@pytest.mark.parametrize(
    "mock_product_instance",
    [
        {"ansys.saf.product_manager.optislang_wrapper.OslManager": MockOptislangWrapperClient},
        {OslManager: MockOptislangWrapperClient},
    ],
    indirect=True,
    ids=["module_str", "class"],
)
def test_optislang_wrapper_manager_can_be_mocked_with_saf_testing(client_project: EndToEndSolution):
    client_project.steps.optislang_wrapper_step.download_example_file()
    client_project.steps.optislang_wrapper_step.write_properties_file()
    client_project.steps.optislang_wrapper_step.write_input_files()
    client_project.steps.optislang_wrapper_step.start_osl_project().wait()
    assert client_project.steps.optislang_wrapper_step.instance_running


class MockVisorClient:
    def __init__(self):
        self.port = 50052


@pytest.mark.usefixtures("mock_product_instance")
@pytest.mark.parametrize(
    "mock_product_instance",
    [{"ansys.saf.product_manager.visor.VisorManager": MockVisorClient}, {VisorManager: MockVisorClient}],
    indirect=True,
    ids=["module_str", "class"],
)
def test_visor_manager_can_be_mocked_with_saf_testing(client_project: EndToEndSolution):
    client_project.steps.visor_instance_step.start_visor().wait()
    assert client_project.steps.visor_instance_step.visor_port == 50052
