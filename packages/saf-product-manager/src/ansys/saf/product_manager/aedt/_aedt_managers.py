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

from abc import abstractmethod
import logging
import os
from pathlib import Path
import time
from typing import Any, TypeVar

import ansys.aedt.core  # pyright: ignore[reportMissingTypeStubs]
import ansys.aedt.core.common_rpc  # pyright: ignore[reportMissingTypeStubs]
import httpx2

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.solution import (
    InstanceManager,
    ProductInstanceManager,
    RecoveryStateInfo,
)
from ansys.saf.product_manager._utilities.const import ANSYS_GRPC_CERTIFICATES, INSECURE_GRPC_MSG
from ansys.saf.product_manager._utilities.ip_utilities import is_localhost

T = TypeVar("T")
logger = logging.getLogger(__name__)

DEFAULT_PROJECT_FILENAME = "project.aedt"


class AedtStateInfo(RecoveryStateInfo):
    project_filename: str = DEFAULT_PROJECT_FILENAME
    design_name: str | None = None
    solution_type: str | None = None


class AbstractAedtManagerImpl(InstanceManager[T, AedtStateInfo]):
    """Base class for all managers of shared AEDT product instances.
    The typevar ``T`` is the AEDT client class that is used to access the API of the managed product.

    Notes
    -----
    It is not expected that GLOW transaction methods or GLOW clients will directly call the constructors of
    ``AbstractAedtManagerImpl`` or classes derived from it. Instead, a class derived from ``AbstractAedtManagerImpl``
    should be passed as an argument to each :py:func:`~ansys.saf.glow.solution.create_instance` decorator to indicate
    the type of AEDT product instance to create and the pyAEDT client API to be used to access the created instance.

    Use the :py:meth:`~ansys.saf.glow.solution.aedt.AbstractAedtManagerImpl.initialize` method to set the initial state
    of the instance within the method decorated with :py:func:`~ansys.saf.glow.solution.create_instance`.
    """

    PRODUCT_NAME = "aedt"
    SERVICE_NAME = "http"

    def initialize(
        self,
        project_file: EntityHandle = NO_ENTITY,
        version: str | None = None,
        design_name: str | None = None,
        solution_type: str | None = None,
    ) -> None:
        """Set the initial state of the AEDT product instance.

        Parameters
        ----------
        project_file : EntityHandle, optional
            The entity handle referencing the project file that contains the initial state of the instance.

        version : str, optional
            The AEDT version of the instance. The format is 3 decimal digits where the first two digits indicate the
            year of release in the 21st century and the third digit indicates the release within that year.
            For example, "222" indicates that "2022 revision 2" is required.
            If ``version`` is not supplied, the GLOW infrastructure will use a version of AEDT that is available in
            the GLOW deployment.

        design_name : str, optional
            Name of the design that is initially selected in the instance. If no value is supplied, then an attempt is
            made to get an active design. If no designs are present, then an empty design is created.

        solution_type : str, optional
            Solution type to apply to the design. The default is None, in which case the default type is applied.
        """
        self.initialize_service(self.SERVICE_NAME, version)
        project_filename = (
            project_file.original_name or DEFAULT_PROJECT_FILENAME
            if project_file != NO_ENTITY
            else DEFAULT_PROJECT_FILENAME
        )
        self.recovery_state_info = AedtStateInfo(
            project_filename=project_filename,
            design_name=design_name,
            solution_type=solution_type,
        )
        if project_file != NO_ENTITY:
            self.copy_to_state_directory(project_file, Path(project_filename))

    @classmethod
    def get_product_name_implement(cls) -> str:
        return cls.PRODUCT_NAME

    def _confirm_session(
        self,
        http_client: "httpx2.Client",
        wrapper_url: str,
        state: dict[str, Any],
    ) -> None:
        """Confirm to the PyAEDT service manager that the session is running."""
        logger.debug("Confirming session to PyAEDT service manager")
        http_client.post(
            f"{wrapper_url}/confirm_session_running",
            timeout=60,
            json={
                "session_rpyc_port": state["session_rpyc_port"],
                "session_grpc_port": state["session_grpc_port"],
            },
        ).raise_for_status()

    @staticmethod
    def _get_or_create_local_session(
        http_client: "httpx2.Client",
        aedt_wrapper_url: str,
        state: dict[str, Any],
    ) -> None:
        logger.debug("Starting new AEDT local session")
        http_client.post(
            f"{aedt_wrapper_url}/get_or_create_local_session",
            timeout=60,
            json={
                "session_running": state["session_running"],
                "session_grpc_port": state["session_grpc_port"],
            },
        ).raise_for_status()

    def _create_remote_session(self, hostname: str, grpc_secure_mode: bool, state: dict[str, Any]) -> None:
        logger.debug("Starting new AEDT remote session")
        # On some environments (e.g. GitHub VM) AEDT may take a while to start,
        # so we need to wait for it to be ready.
        session_created = False
        attempts = 0
        error: Exception | None = None
        while not session_created and attempts < 30:
            try:
                (
                    ansys.aedt.core.common_rpc.create_session(  # type: ignore
                        host=hostname,  # type: ignore
                        launch_aedt_on_server=True,
                        client_port=state["session_rpyc_port"],
                        non_graphical=True,
                        aedt_port=state["session_grpc_port"],
                        secure=grpc_secure_mode,
                    ),
                )
                session_created = True
            except Exception as e:
                error = e
            time.sleep(0.5)
            attempts += 1
        if not session_created:
            raise RuntimeError(
                f"Failed to connect to AEDT session on {hostname}:{state['session_grpc_port']}",
            ) from error

    def _start_service_manager(
        self,
        aedt_wrapper_url: str,
        state: dict[str, Any],
        http_client: httpx2.Client,
    ) -> dict[str, Any]:
        if not state["service_manager_running"]:
            logger.debug("Starting PyAEDT service manager")
            http_client.post(f"{aedt_wrapper_url}/start_service_manager", timeout=300).raise_for_status()
            response = http_client.get(aedt_wrapper_url)
            response.raise_for_status()
            state = response.json()
        return state

    def get_client_object_implement(self, hostname: str, port: int) -> T:
        aedt_wrapper_url = f"http://{hostname}:{port}"
        # map from XYZ to 20XY.Z e.g 222 => 2022.2
        specified_version = f"20{self.product_version[:2]}.{self.product_version[2]}"

        with httpx2.Client() as http_client:
            response = http_client.get(aedt_wrapper_url)
            response.raise_for_status()
            state = response.json()

            grpc_secure_mode = state["transport_mode"] in ("WNUA", "UDS", "MTLS")
            if not grpc_secure_mode:
                logger.warning(INSECURE_GRPC_MSG)
            elif state["transport_mode"] == "MTLS":
                if not os.environ.get(ANSYS_GRPC_CERTIFICATES):
                    raise RuntimeError(
                        "MTLS transport mode requires ANSYS_GRPC_CERTIFICATES to be set to the directory containing "
                        "the certificates.",
                    )
                certs_dir = os.environ.get(ANSYS_GRPC_CERTIFICATES)
                logger.info(f"MTLS secure flags found, creating MTLS channel with certificates from {certs_dir}")
            else:
                logger.info(f"{state['transport_mode']} secure flag found, creating secure channel.")

            if is_localhost(hostname):
                self._get_or_create_local_session(http_client, aedt_wrapper_url, state)
            else:
                state = self._start_service_manager(aedt_wrapper_url, state, http_client)
                ansys.aedt.core.settings.remote_rpc_service_manager_port = state["service_manager_port"]  # pyright: ignore
                if not state["session_running"]:
                    self._create_remote_session(hostname, grpc_secure_mode, state)

            if not state["session_running"]:
                self._confirm_session(http_client, aedt_wrapper_url, state)

        project_filepath = self.state_directory / self.recovery_state_info.project_filename

        # Define the same settings used in the wrapper that launches AEDT for the PyAEDT product client.
        ansys.aedt.core.settings.grpc_local = is_localhost(hostname)
        ansys.aedt.core.settings.grpc_secure_mode = grpc_secure_mode

        # Ensure the manager connects with the same transport mode the wrapper used to launch AEDT.
        # If the wrapper didn't use MTLS, remove ANSYS_GRPC_CERTIFICATES from the manager's env
        # so pyAEDT doesn't override to MTLS when the product client internally calls _get_grpcsrv_args.
        saved_certs = os.environ.pop(ANSYS_GRPC_CERTIFICATES, None) if state["transport_mode"] != "MTLS" else None
        try:
            return self.get_aedt_product_client(
                str(project_filepath),
                specified_version,
                hostname,
                state["session_grpc_port"],
                self.recovery_state_info.design_name,
                self.recovery_state_info.solution_type,
            )
        finally:
            if saved_certs is not None:
                os.environ[ANSYS_GRPC_CERTIFICATES] = saved_certs

    @abstractmethod
    def get_aedt_product_client(
        self,
        project_name: str,
        specified_version: str,
        machine: str,
        port: int,
        design_name: str | None = None,
        solution_type: str | None = None,
    ) -> T:
        raise NotImplementedError()

    def save_state_implement(self) -> None:
        # Save the active AEDT project as the state of the instance.
        projects = self.instance.desktop_class.project_list  # pyright: ignore
        if projects:
            project_filename = self.recovery_state_info.project_filename
            project_path = self.state_directory / project_filename
            self._check_execution(
                self.instance.save_project(str(project_path), overwrite=True),  # type: ignore
                "save project",
            )
            if self.instance.design_list:  # type: ignore
                self.recovery_state_info.design_name = str(self.instance.odesign.GetName())  # type: ignore

    def _check_execution(self, ok: bool, verb: str) -> None:
        if not ok:
            raise RuntimeError(f"failed to {verb}")

    def load_state_implement(self) -> None:
        return

    def close_client_object_implement(self) -> None:
        self._check_execution(
            self.instance.desktop_class.release_desktop(close_projects=True, close_on_exit=False),  # type: ignore
            "release desktop",
        )

    def shutdown_implement(self) -> None:
        self._check_execution(
            self.instance.desktop_class.close_desktop(),  # type: ignore
            "close desktop",
        )


class InternalMaxwell2DManagerImpl(AbstractAedtManagerImpl[ansys.aedt.core.Maxwell2d]):
    """A manager of a shared `AEDT Maxwell <https://www.ansys.com/en-gb/products/electronics/ansys-maxwell>`_ 2D
    product instance.

    Notes
    -----
    It is not expected that GLOW transaction methods or GLOW clients will directly call the constructor of
    ``Maxwell2DManager``. Instead, the ``Maxwell2DManager`` class should
    be passed as an argument to a :py:func:`~ansys.saf.glow.solution.create_instance` decorator to indicate that
    the created instance is AEDT Maxwell 2D.

    Use the :py:meth:`~ansys.saf.glow.solution.aedt.AbstractAedtManagerImpl.initialize` method to set the initial state
    of the instance within the method decorated with :py:func:`~ansys.saf.glow.solution.create_instance`.

    The :py:attr:`~ansys.saf.glow.solution.InstanceManager.instance` property returns a
    `pyAEDT Maxwell2d
    <https://aedt.docs.pyansys.com/version/stable/API/_autosummary/ansys.aedt.core.maxwell.Maxwell2d.html>`_
    object which is the API for the managed instance.
    """

    def get_aedt_product_client(
        self,
        project_name: str,
        specified_version: str,
        machine: str,
        port: int,
        design_name: str | None = None,
        solution_type: str | None = None,
    ) -> ansys.aedt.core.Maxwell2d:
        logger.info(
            f'calling Maxwell2d(project="{project_name}", version="{specified_version}", '
            f'"machine="{machine}", port={port}, design={"<None>" if design_name is None else design_name}, '
            f"solution_type={'<None>' if solution_type is None else solution_type})",
        )
        return ansys.aedt.core.Maxwell2d(
            project=project_name,
            design=design_name,
            version=specified_version,
            machine=machine,
            port=port,
            solution_type=solution_type,
            remove_lock=True,  # if instance is killed externally, otherwise the project remains locked and fails.
        )


class Maxwell2DManager(
    ProductInstanceManager[ansys.aedt.core.Maxwell2d, AedtStateInfo],
    instance_manager_impl_type=InternalMaxwell2DManagerImpl,
):
    """
    A manager of a `AEDT Maxwell <https://www.ansys.com/en-gb/products/electronics/ansys-maxwell>`_ 2D product instance.
    """

    def __init__(self, **kwargs: Any) -> None:
        """A manager of a `AEDT Maxwell <https://www.ansys.com/en-gb/products/electronics/ansys-maxwell>`_ 2D
        product instance.

        Parameters
        ----------
        project_file : EntityHandle, optional
            The entity handle referencing the project file that contains the initial state of the instance.

        version : str, optional
            The AEDT version of the instance. The format is 3 decimal digits where the first two digits indicate the
            year of release in the 21st century and the third digit indicates the release within that year.
            For example, "222" indicates that "2022 revision 2" is required.
            If ``version`` is not supplied, the GLOW infrastructure will use a version of AEDT that is available in
            the GLOW deployment.

        design_name : str, optional
            Name of the design that is initially selected in the instance. If no value is supplied, then an attempt is
            made to get an active design. If no designs are present, then an empty design is created.

        solution_type : str, optional
            Solution type to apply to the design. The default is None, in which case the default type is applied.
        """
        super().__init__(**kwargs)

    def initialize(
        self,
        project_file: EntityHandle = NO_ENTITY,
        version: str | None = None,
        design_name: str | None = None,
        solution_type: str | None = None,
    ) -> None:
        """Set the initial state of the AEDT product instance.

        Parameters
        ----------
        project_file : EntityHandle, optional
            The entity handle referencing the project file that contains the initial state of the instance.

        version : str, optional
            The AEDT version of the instance. The format is 3 decimal digits where the first two digits indicate the
            year of release in the 21st century and the third digit indicates the release within that year.
            For example, "222" indicates that "2022 revision 2" is required.
            If ``version`` is not supplied, the GLOW infrastructure will use a version of AEDT that is available in
            the GLOW deployment.

        design_name : str, optional
            Name of the design that is initially selected in the instance. If no value is supplied, then an attempt is
            made to get an active design. If no designs are present, then an empty design is created.

        solution_type : str, optional
            Solution type to apply to the design. The default is None, in which case the default type is applied.
        """
        super().start(project_file=project_file, version=version, design_name=design_name, solution_type=solution_type)


class InternalMaxwell3DManagerImpl(AbstractAedtManagerImpl[ansys.aedt.core.Maxwell3d]):
    """
    A manager of a `AEDT Maxwell <https://www.ansys.com/en-gb/products/electronics/ansys-maxwell>`_ 3D product instance.
    """

    def get_aedt_product_client(
        self,
        project_name: str,
        specified_version: str,
        machine: str,
        port: int,
        design_name: str | None = None,
        solution_type: str | None = None,
    ) -> ansys.aedt.core.Maxwell3d:
        logger.info(
            f'calling Maxwell3d(project="{project_name}", version="{specified_version}", '
            f'"machine="{machine}", port={port}, design={"<None>" if design_name is None else design_name}, '
            f"solution_type={'<None>' if solution_type is None else solution_type})",
        )
        return ansys.aedt.core.Maxwell3d(
            project=project_name,
            design=design_name,
            version=specified_version,
            machine=machine,
            port=port,
            solution_type=solution_type,
            remove_lock=True,  # if instance is killed externally, otherwise the project remains locked and fails.
        )


class Maxwell3DManager(
    ProductInstanceManager[ansys.aedt.core.Maxwell3d, AedtStateInfo],
    instance_manager_impl_type=InternalMaxwell3DManagerImpl,
):
    """
    A manager of a `AEDT Maxwell <https://www.ansys.com/en-gb/products/electronics/ansys-maxwell>`_ 3D product instance.
    """

    def __init__(self, **kwargs: Any) -> None:
        """A manager of a shared `AEDT Maxwell <https://www.ansys.com/en-gb/products/electronics/ansys-maxwell>`_ 3D
        product instance.

        Parameters
        ----------
        project_file : EntityHandle, optional
            The entity handle referencing the project file that contains the initial state of the instance.

        version : str, optional
            The AEDT version of the instance. The format is 3 decimal digits where the first two digits indicate the
            year of release in the 21st century and the third digit indicates the release within that year.
            For example, "222" indicates that "2022 revision 2" is required.
            If ``version`` is not supplied, the GLOW infrastructure will use a version of AEDT that is available in
            the GLOW deployment.

        design_name : str, optional
            Name of the design that is initially selected in the instance. If no value is supplied, then an attempt is
            made to get an active design. If no designs are present, then an empty design is created.

        solution_type : str, optional
            Solution type to apply to the design. The default is None, in which case the default type is applied.
        """
        super().__init__(**kwargs)

    def initialize(
        self,
        project_file: EntityHandle = NO_ENTITY,
        version: str | None = None,
        design_name: str | None = None,
        solution_type: str | None = None,
    ) -> None:
        """Set the initial state of the AEDT product instance.

        Parameters
        ----------
        project_file : EntityHandle, optional
            The entity handle referencing the project file that contains the initial state of the instance.

        version : str, optional
            The AEDT version of the instance. The format is 3 decimal digits where the first two digits indicate the
            year of release in the 21st century and the third digit indicates the release within that year.
            For example, "222" indicates that "2022 revision 2" is required.
            If ``version`` is not supplied, the GLOW infrastructure will use a version of AEDT that is available in
            the GLOW deployment.

        design_name : str, optional
            Name of the design that is initially selected in the instance. If no value is supplied, then an attempt is
            made to get an active design. If no designs are present, then an empty design is created.

        solution_type : str, optional
            Solution type to apply to the design. The default is None, in which case the default type is applied.
        """
        super().start(project_file=project_file, version=version, design_name=design_name, solution_type=solution_type)


class InternalHfssManagerImpl(AbstractAedtManagerImpl[ansys.aedt.core.Hfss]):
    """A manager of a `AEDT HFSS <https://www.ansys.com/products/electronics/ansys-hfss>`_ product instance."""

    def get_aedt_product_client(
        self,
        project_name: str,
        specified_version: str,
        machine: str,
        port: int,
        design_name: str | None = None,
        solution_type: str | None = None,
    ) -> ansys.aedt.core.Hfss:
        logger.info(
            f'calling Hfss(project="{project_name}", version="{specified_version}", '
            f'"machine="{machine}", port={port}, design={"<None>" if design_name is None else design_name}, '
            f"solution_type={'<None>' if solution_type is None else solution_type})",
        )
        return ansys.aedt.core.Hfss(
            project=project_name,
            design=design_name,
            version=specified_version,
            machine=machine,
            port=port,
            solution_type=solution_type,
            remove_lock=True,  # if instance is killed externally, otherwise the project remains locked and fails.
        )


class HfssManager(
    ProductInstanceManager[ansys.aedt.core.Hfss, AedtStateInfo],
    instance_manager_impl_type=InternalHfssManagerImpl,
):
    """A manager of a `AEDT HFSS <https://www.ansys.com/products/electronics/ansys-hfss>`_ product instance."""

    def __init__(self, **kwargs: Any) -> None:
        """A manager of a `AEDT HFSS <https://www.ansys.com/products/electronics/ansys-hfss>`_ product instance.

        Parameters
        ----------
        project_file : EntityHandle, optional
            The entity handle referencing the project file that contains the initial state of the instance.

        version : str, optional
            The AEDT version of the instance. The format is 3 decimal digits where the first two digits indicate the
            year of release in the 21st century and the third digit indicates the release within that year.
            For example, "222" indicates that "2022 revision 2" is required.
            If ``version`` is not supplied, the GLOW infrastructure will use a version of AEDT that is available in
            the GLOW deployment.

        design_name : str, optional
            Name of the design that is initially selected in the instance. If no value is supplied, then an attempt is
            made to get an active design. If no designs are present, then an empty design is created.

        solution_type : str, optional
            Solution type to apply to the design. The default is None, in which case the default type is applied.
        """
        super().__init__(**kwargs)

    def initialize(
        self,
        project_file: EntityHandle = NO_ENTITY,
        version: str | None = None,
        design_name: str | None = None,
        solution_type: str | None = None,
    ) -> None:
        """Set the initial state of the AEDT product instance.

        Parameters
        ----------
        project_file : EntityHandle, optional
            An entity handle referencing the project file that contains the initial state of the instance.

        version : str, optional
            The AEDT version of the instance. The format is 3 decimal digits where the first two digits indicate the
            year of release in the 21st century and the third digit indicates the release within that year.
            For example, "222" indicates that "2022 revision 2" is required.
            If ``version`` is not supplied, the GLOW infrastructure will use a version of AEDT that is available in
            the GLOW deployment.

        design_name : str, optional
            Name of the design that is initially selected in the instance. If no value is supplied, then an attempt is
            made to get an active design. If no designs are present, then an empty design is created.
        """
        super().start(project_file=project_file, version=version, design_name=design_name, solution_type=solution_type)


class InternalIcepakManagerImpl(AbstractAedtManagerImpl[ansys.aedt.core.Icepak]):
    """A manager of a `AEDT Icepak <https://www.ansys.com/en-gb/products/electronics/ansys-icepak>`_
    product instance.
    """

    def get_aedt_product_client(
        self,
        project_name: str,
        specified_version: str,
        machine: str,
        port: int,
        design_name: str | None = None,
        solution_type: str | None = None,
    ) -> ansys.aedt.core.Icepak:
        logger.info(
            f'calling Icepak(project="{project_name}", version="{specified_version}", '
            f'"machine="{machine}", port={port}, design={"<None>" if design_name is None else design_name}, '
            f"solution_type={'<None>' if solution_type is None else solution_type})",
        )
        return ansys.aedt.core.Icepak(
            project=project_name,
            design=design_name,
            version=specified_version,
            machine=machine,
            port=port,
            solution_type=solution_type,
            remove_lock=True,  # if instance is killed externally, otherwise the project remains locked and fails.
        )


class IcepakManager(
    ProductInstanceManager[ansys.aedt.core.Icepak, AedtStateInfo],
    instance_manager_impl_type=InternalIcepakManagerImpl,
):
    """A manager of a `AEDT Icepak <https://www.ansys.com/en-gb/products/electronics/ansys-icepak>`_
    product instance.
    """

    def __init__(self, **kwargs: Any) -> None:
        """A manager of a shared `AEDT Icepak <https://www.ansys.com/en-gb/products/electronics/ansys-icepak>`_
        product instance.

        Parameters
        ----------
        project_file : EntityHandle, optional
            The entity handle referencing the project file that contains the initial state of the instance.

        version : str, optional
            The AEDT version of the instance. The format is 3 decimal digits where the first two digits indicate the
            year of release in the 21st century and the third digit indicates the release within that year.
            For example, "222" indicates that "2022 revision 2" is required.
            If ``version`` is not supplied, the GLOW infrastructure will use a version of AEDT that is available in
            the GLOW deployment.

        design_name : str, optional
            Name of the design that is initially selected in the instance. If no value is supplied, then an attempt is
            made to get an active design. If no designs are present, then an empty design is created.
        """
        super().__init__(**kwargs)

    def initialize(
        self,
        project_file: EntityHandle = NO_ENTITY,
        version: str | None = None,
        design_name: str | None = None,
        solution_type: str | None = None,
    ) -> None:
        """Set the initial state of the AEDT product instance.

        Parameters
        ----------
        project_file : EntityHandle, optional
            The entity handle referencing the project file that contains the initial state of the instance.

        version : str, optional
            The AEDT version of the instance. The format is 3 decimal digits where the first two digits indicate the
            year of release in the 21st century and the third digit indicates the release within that year.
            For example, "222" indicates that "2022 revision 2" is required.
            If ``version`` is not supplied, the GLOW infrastructure will use a version of AEDT that is available in
            the GLOW deployment.

        design_name : str, optional
            Name of the design that is initially selected in the instance. If no value is supplied, then an attempt is
            made to get an active design. If no designs are present, then an empty design is created.

        solution_type : str, optional
            Solution type to apply to the design. The default is None, in which case the default type is applied.
        """
        super().start(project_file=project_file, version=version, design_name=design_name, solution_type=solution_type)
