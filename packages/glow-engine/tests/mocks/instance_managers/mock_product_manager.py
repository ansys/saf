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

from abc import ABC
import logging
import os
from pathlib import Path
from typing import Any, Generic, TypeVar, get_args
import uuid

from pydantic import BaseModel, Field

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow._config.const import ANSYS_GRPC_CERTIFICATES
from ansys.saf.glow.solution import (
    InstanceManager,
    ProductInstanceManager,
    RecoveryStateInfo,
)
from ansys.saf.product_configuration.interfaces import ServiceType
from tests.mocks.mock_products.client import (
    IMockProductClient,
    MockDummyProductClient,
    MockGrpcProductClient,
    MockHttpProductClient,
    MockSecureGrpcProductClient,
    MockTcpProductClient,
    TransportMode,
)

T = TypeVar("T", bound=IMockProductClient)

logger = logging.getLogger(__name__)


class SubProductInfo(BaseModel):
    sub_handle: EntityHandle = NO_ENTITY


class MockStateInfo(RecoveryStateInfo):
    project_filename: str = "project.txt"
    random_value: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_list_handles: list[EntityHandle] = []
    product_dict_handles: dict[str, EntityHandle] = {}
    product_sub_model: SubProductInfo = SubProductInfo()


class InternalBaseProductInstanceManagerImpl(InstanceManager[T, MockStateInfo], ABC, Generic[T]):
    shutdown_state: str = "SHUTDOWN"
    _service_type: str
    _product_client_type: IMockProductClient

    def __init_subclass__(cls, service_type: ServiceType | None, **kwargs: Any):
        if service_type:
            cls._service_type = service_type.value
            cls.SERVICE_NAME = service_type.value
        # Get the product client type from the type specified within the concrete class implementation.
        cls._product_client_type = get_args(cls.__orig_bases__[0])[0]  # type: ignore
        super().__init_subclass__(**kwargs)

    def initialize(self, version: str | None = None, project: EntityHandle = NO_ENTITY):
        self.initialize_service(f"{self._service_type}", version)
        project_filename = (project.original_name or "project") if project != NO_ENTITY else "project.txt"
        self.recovery_state_info = MockStateInfo(
            project_filename=project_filename,
            random_value=str(uuid.uuid4()),
        )
        if project != NO_ENTITY:
            self.copy_to_state_directory(project, Path(project_filename))
            self.load_state_implement()

    def get_client_object_implement(self, hostname: str, port: int) -> T:
        return self._product_client_type(port, hostname)  # type: ignore

    def close_client_object_implement(self) -> None:
        return self.instance.close()

    def _write_to_spy_file(self, content: str):
        spy_path = self._project_directory_path_on_solution / "spy.txt"
        with spy_path.open(mode="a") as f:
            f.write(content)

    def save_state_implement(self) -> None:
        self._write_to_spy_file("saving state...")
        project_filepath = self.state_directory / self.recovery_state_info.project_filename
        self.instance.store_given_absolute_path(str(project_filepath))
        self.recovery_state_info.random_value = str(uuid.uuid4())

    def load_state_implement(self) -> None:
        self._write_to_spy_file("loading state...")
        project_filepath = self.state_directory / self.recovery_state_info.project_filename
        self.instance.restore_given_absolute_path(str(project_filepath))

    def shutdown_implement(self) -> None:
        self._write_to_spy_file("shutting instance down...")
        self.instance.the_property = self.shutdown_state

    @classmethod
    def get_product_name_implement(cls) -> str:
        return f"custom-{cls._service_type}-product"


class InternalMockTcpProductInstanceManagerImpl(
    InternalBaseProductInstanceManagerImpl[MockTcpProductClient],
    service_type=ServiceType.TCP,
):
    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(service_type=ServiceType.TCP, **kwargs)


class InternalMockHttpProductInstanceManagerImpl(
    InternalBaseProductInstanceManagerImpl[MockHttpProductClient],
    service_type=ServiceType.HTTP,
):
    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(service_type=ServiceType.HTTP, **kwargs)


class InternalMockHttpNoSaveProductInstanceManagerImpl(
    InternalBaseProductInstanceManagerImpl[MockHttpProductClient],
    service_type=ServiceType.HTTP,
):
    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(service_type=ServiceType.HTTP, **kwargs)

    def save_state_implement(self) -> None:
        pass


class InternalMockGrpcProductInstanceManagerImpl(
    InternalBaseProductInstanceManagerImpl[MockGrpcProductClient],
    service_type=ServiceType.GRPC,
):
    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(service_type=ServiceType.GRPC, **kwargs)


class InternalMockSecureGrpcProductInstanceManagerImpl(
    InternalBaseProductInstanceManagerImpl[MockSecureGrpcProductClient],
    service_type=ServiceType.GRPC,
):
    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(service_type=ServiceType.GRPC, **kwargs)

    @classmethod
    def get_product_name_implement(cls) -> str:
        return f"custom-{cls._service_type}-product-secure"

    def get_client_object_implement(self, hostname: str, port: int) -> MockSecureGrpcProductClient:
        service = self._get_service()

        if service.secure_flags is None:
            logger.info("No secure flags found, defaulting to insecure transport mode.")
            return MockSecureGrpcProductClient(
                port=port,
                host=hostname,
                transport_mode=TransportMode.INSECURE,
            )

        if "mtls" in service.secure_flags.lower():
            certs_dir = os.getenv(ANSYS_GRPC_CERTIFICATES, None)
            if certs_dir is None:
                raise RuntimeError(
                    "MTLS transport mode requires certificates directory to be set in environment variable ANSYS_GRPC_CERTIFICATES.",  # noqa: E501
                )
            logger.info("MTLS secure flags found, creating MTLS channel with certificates from %s", certs_dir)
            return MockSecureGrpcProductClient(
                port=port,
                host=hostname,
                transport_mode=TransportMode.MTLS,
                certs_dir=Path(certs_dir),
            )
        elif "uds" in service.secure_flags.lower() and service.uds_dir and service.uds_id:
            logger.info(
                "UDS secure flags found, creating UDS channel with uds_dir=%s and uds_id=%s",
                service.uds_dir,
                service.uds_id,
            )
            return MockSecureGrpcProductClient(
                port=port,
                host=hostname,
                transport_mode=TransportMode.UDS,
                uds_dir=Path(service.uds_dir),
                uds_id=service.uds_id,
            )
        elif "wnua" in service.secure_flags.lower():
            return MockSecureGrpcProductClient(
                port=port,
                host=hostname,
                transport_mode=TransportMode.WNUA,
            )
        else:
            logger.warning(
                "Secure flags found but no supported transport mode identified, defaulting to insecure transport mode.",
            )
            return MockSecureGrpcProductClient(
                port=port,
                host=hostname,
                transport_mode=TransportMode.INSECURE,
            )


class InternalMockSecureGrpcCustomProductInstanceManagerImpl(InternalMockSecureGrpcProductInstanceManagerImpl):
    @classmethod
    def get_product_name_implement(cls) -> str:
        return f"custom-{cls._service_type}-product-secure-2"


class InternalMockSecureGrpcMtlsProductInstanceManagerImpl(InternalMockSecureGrpcProductInstanceManagerImpl):
    @classmethod
    def get_product_name_implement(cls) -> str:
        return f"custom-{cls._service_type}-product-secure-mtls"


class InternalMockGrpcCustomHostProductInstanceManagerImpl(
    InternalBaseProductInstanceManagerImpl[MockGrpcProductClient],
    service_type=ServiceType.GRPC,
):
    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(service_type=ServiceType.GRPC, **kwargs)

    @classmethod
    def get_product_name_implement(cls) -> str:
        return f"custom-{cls._service_type}-product-custom-host"


class InternalMockGrpcProductDummyClientInstanceManagerImpl(
    InternalBaseProductInstanceManagerImpl[MockDummyProductClient],
    service_type=ServiceType.GRPC,
):
    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(service_type=ServiceType.GRPC, **kwargs)


class MockTcpProductInstanceManager(
    ProductInstanceManager[MockTcpProductClient, MockStateInfo],
    instance_manager_impl_type=InternalMockTcpProductInstanceManagerImpl,
):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None, project: EntityHandle = NO_ENTITY):
        super().start(version=version, project=project)


class MockHttpProductInstanceManager(
    ProductInstanceManager[MockHttpProductClient, MockStateInfo],
    instance_manager_impl_type=InternalMockHttpProductInstanceManagerImpl,
):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None, project: EntityHandle = NO_ENTITY):
        super().start(version=version, project=project)


class InternalMockHttpNoVersionArgProductInstanceManagerImpl(InternalMockHttpProductInstanceManagerImpl):
    def initialize(self, project: EntityHandle = NO_ENTITY):  # pyright: ignore[reportIncompatibleMethodOverride]
        super().initialize(version=None, project=project)


class MockHttpNoVersionArgProductInstanceManager(
    ProductInstanceManager[MockHttpProductClient, MockStateInfo],
    instance_manager_impl_type=InternalMockHttpNoVersionArgProductInstanceManagerImpl,
):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def initialize(self, project: EntityHandle = NO_ENTITY):
        super().start(project=project)


class InternalMockHttpNoServiceNameProductInstanceManagerImpl(
    InternalBaseProductInstanceManagerImpl[MockHttpProductClient],
    service_type=None,
):
    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(service_type=None, **kwargs)


class MockHttpNoServiceNameProductInstanceManager(
    ProductInstanceManager[MockHttpProductClient, MockStateInfo],
    instance_manager_impl_type=InternalMockHttpNoServiceNameProductInstanceManagerImpl,
):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None, project: EntityHandle = NO_ENTITY):
        super().start(version=version, project=project)


class MockHttpNoSaveProductInstanceManager(
    ProductInstanceManager[MockHttpProductClient, MockStateInfo],
    instance_manager_impl_type=InternalMockHttpNoSaveProductInstanceManagerImpl,
):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None, project: EntityHandle = NO_ENTITY):
        super().start(version=version, project=project)


class MockGrpcProductInstanceManager(
    ProductInstanceManager[MockGrpcProductClient, MockStateInfo],
    instance_manager_impl_type=InternalMockGrpcProductInstanceManagerImpl,
):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None, project: EntityHandle = NO_ENTITY):
        super().start(version=version, project=project)


class MockSecureGrpcProductInstanceManager(
    ProductInstanceManager[MockSecureGrpcProductClient, MockStateInfo],
    instance_manager_impl_type=InternalMockSecureGrpcProductInstanceManagerImpl,
):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None, project: EntityHandle = NO_ENTITY):
        super().start(version=version, project=project)


class MockSecureGrpcCustomProductInstanceManager(
    ProductInstanceManager[MockSecureGrpcProductClient, MockStateInfo],
    instance_manager_impl_type=InternalMockSecureGrpcCustomProductInstanceManagerImpl,
):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None, project: EntityHandle = NO_ENTITY):
        super().start(version=version, project=project)


class MockSecureGrpcMtlsProductInstanceManager(
    ProductInstanceManager[MockSecureGrpcProductClient, MockStateInfo],
    instance_manager_impl_type=InternalMockSecureGrpcMtlsProductInstanceManagerImpl,
):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None, project: EntityHandle = NO_ENTITY):
        super().start(version=version, project=project)


class MockGrpcCustomHostProductInstanceManager(
    ProductInstanceManager[MockGrpcProductClient, MockStateInfo],
    instance_manager_impl_type=InternalMockGrpcCustomHostProductInstanceManagerImpl,
):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None, project: EntityHandle = NO_ENTITY):
        super().start(version=version, project=project)


class MockGrpcProductDummyClientInstanceManager(
    ProductInstanceManager[MockDummyProductClient, MockStateInfo],
    instance_manager_impl_type=InternalMockGrpcProductDummyClientInstanceManagerImpl,
):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None, project: EntityHandle = NO_ENTITY):
        super().start(version=version, project=project)


class CustomRouteHttpProductManagerImpl(InternalMockHttpProductInstanceManagerImpl):
    @classmethod
    def get_product_name_implement(cls) -> str:
        return "custom-http-product-custom-route"


class CustomRouteHttpProductManager(
    ProductInstanceManager[MockHttpProductClient, MockStateInfo],
    instance_manager_impl_type=CustomRouteHttpProductManagerImpl,
):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None, project: EntityHandle = NO_ENTITY):
        super().start(version=version, project=project)


class FakeRouteHttpProductManagerImpl(InternalMockHttpProductInstanceManagerImpl):
    @classmethod
    def get_product_name_implement(cls) -> str:
        return "custom-http-product-wrong-route"


class FakeRouteHttpProductManager(
    ProductInstanceManager[MockHttpProductClient, MockStateInfo],
    instance_manager_impl_type=FakeRouteHttpProductManagerImpl,
):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None, project: EntityHandle = NO_ENTITY):
        super().start(version=version, project=project)


class WrongServiceTypeProductManagerImpl(InternalMockHttpProductInstanceManagerImpl):
    @classmethod
    def get_product_name_implement(cls) -> str:
        return "custom-http-product-wrong-service-type"


class WrongServiceTypeProductManager(
    ProductInstanceManager[MockHttpProductClient, MockStateInfo],
    instance_manager_impl_type=WrongServiceTypeProductManagerImpl,
):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None, project: EntityHandle = NO_ENTITY):
        super().start(version=version, project=project)


class WrongPortConfigProductManagerImpl(InternalMockHttpProductInstanceManagerImpl):
    @classmethod
    def get_product_name_implement(cls) -> str:
        return "wrong-port-http-product"


class WrongPortConfigProductManager(
    ProductInstanceManager[MockHttpProductClient, MockStateInfo],
    instance_manager_impl_type=WrongPortConfigProductManagerImpl,
):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def initialize(self, version: str | None = None, project: EntityHandle = NO_ENTITY):
        super().start(version=version, project=project)
