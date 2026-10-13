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

import logging
from pathlib import Path

import ansys.platform.instancemanagement as pypim  # pyright: ignore[reportMissingTypeStubs]
import ansys.platform.instancemanagement.exceptions as pypim_exceptions  # pyright: ignore[reportMissingTypeStubs]
import grpc

from ansys.saf.glow._core.instance.healthcheck import create_health_client_factory
from ansys.saf.glow._core.instance.iinstance_system import (
    GenericProductInstance,
    IHealthClientFactory,
    IProductInstance,
    IProductInstanceService,
    IProductInstanceSystem,
    IProductInstanceSystemFactory,
    IProductInstanceVersionDefinition,
)
from ansys.saf.product_configuration.interfaces import IProductInstanceVersionConfiguration

logger = logging.getLogger(__name__)


class PimProductInstanceVersionDefinition(IProductInstanceVersionDefinition):
    """PIM implementation to configure a given version of a product instance."""

    def __init__(self, definition: pypim.Definition) -> None:
        self._definition = definition

    @property
    def name(self) -> str:
        return self._definition.name

    @property
    def product_version(self) -> str:
        return self._definition.product_version


class PimProductInstanceService(IProductInstanceService):
    def __init__(
        self,
        service: pypim.Service,
        config: IProductInstanceVersionConfiguration,
        product_host: str | None,
    ) -> None:
        self._service = service
        self._product_host = product_host
        self._config = config

    @property
    def host(self) -> str:
        if self._product_host:
            # PIM Light server returns host 127.0.0.1 for products
            # which is not useful for GLOW in non-desktop deployment.
            # Override with value from env var as we do with HPS too.
            return self._product_host
        try:
            return self._parse_uri()[-2].strip("/")
        except Exception:
            raise RuntimeError("Unable to parse URI") from None

    @property
    def port(self) -> int:
        try:
            return int(self._parse_uri()[-1])
        except Exception:
            raise RuntimeError("Unable to parse URI") from None

    @property
    def uds_id(self) -> str | None:
        # TODO: replace that once PIM supports secured gRPC connection
        return None

    @property
    def uds_dir(self) -> str | None:
        # TODO: replace that once PIM supports secured gRPC connection
        return None

    @property
    def secure_flags(self) -> str | None:
        # TODO: replace that once PIM supports secured gRPC connection
        # (always returning insecure flags for now if secure flags,
        # because there is currently no way to make the distinction between WNUA and insecure in PIM)
        return self._config.insecure_flags if self._config.enable_secure_flags else None

    def _parse_uri(self) -> list[str]:
        uri: str = str(self._service.uri)
        return uri.split(":")


class PimProductInstance(GenericProductInstance):
    def __init__(
        self,
        instance: pypim.Instance,
        health_client_factory: IHealthClientFactory,
        service_name: str,
        version: str,
        config: IProductInstanceVersionConfiguration,
        product_host: str | None,
    ) -> None:
        self._instance = instance
        self._version = version
        self._product_host = product_host
        self._config = config
        super().__init__(health_client_factory, service_name)

    @property
    def name(self) -> str:
        return self._instance.name

    @property
    def definition_name(self) -> str:
        return self._instance.definition_name

    @property
    def version(self) -> str:
        return self._version

    def wait_for_ready(self):
        try:
            self._instance.wait_for_ready()
            self._wait_for_healthy()
        except (pypim_exceptions.InstanceNotFoundError, pypim_exceptions.RemoteError) as ex:
            self.delete()
            raise TimeoutError(ex) from ex

    @property
    def services(self) -> dict[str, IProductInstanceService]:
        return {
            key: PimProductInstanceService(service=service, config=self._config, product_host=self._product_host)
            for key, service in self._instance.services.items()
        }

    def delete(self, missing_ok: bool = False) -> None:
        try:
            self._instance.delete()
            self._wait_for_removal()
        except (pypim_exceptions.InstanceNotFoundError, pypim_exceptions.RemoteError, grpc.RpcError):
            # there appears to be a Pim bug, where a generic RpcError is the exception thrown
            # instead of InstanceNotFoundError, with details such as:
            # details = "instances/custom-grpc-product1-e0y1Ydk6 not found."
            if missing_ok:
                return
            raise


class PimSystem(IProductInstanceSystem):
    def __init__(self, client: pypim.Client, product_host: str | None) -> None:
        self._client = client
        self._product_host = product_host

    def list_definitions(self, product_name: str) -> list[IProductInstanceVersionDefinition]:
        return [
            PimProductInstanceVersionDefinition(definition)
            for definition in self._client.list_definitions(product_name)
        ]

    def create_instance(
        self,
        product_name: str,
        max_execution_time: int,
        product_version: str | None = None,
    ) -> IProductInstance:
        product_version, version_configuration = self._configurations_manager.get_version_configuration(
            product_name,
            product_version,
        )
        instance = self._client.create_instance(product_name, product_version)
        health_client_factory = create_health_client_factory(version_configuration)
        product_instance = PimProductInstance(
            instance=instance,
            health_client_factory=health_client_factory,
            service_name=version_configuration.service_name,
            version=product_version,
            config=version_configuration,
            product_host=self._product_host,
        )

        try:
            product_instance.wait_for_ready()
        except Exception:
            try:
                logger.error(f"The product {product_name} failed to initialize.")
                product_instance.delete()
            finally:
                raise

        return product_instance

    def get_instance(self, instance_name: str) -> IProductInstance | None:
        if not instance_name:
            return None

        instance: pypim.Instance | None = None
        try:
            instance = self._client.get_instance(instance_name)
        except pypim_exceptions.InstanceNotFoundError:
            pass
        except pypim_exceptions.RemoteError:
            # there appears to be a Pim bug
            # InstanceNotFoundError should be thrown if pim_name is unknown
            # instead RemoteError is
            pass

        if not instance:
            return None

        definitions = [
            (product_name, product_version)
            for product_name in self._configurations_manager.get_products()
            for product_version in self._configurations_manager.list_versions(product_name)
            if instance.definition_name == f"definitions/{product_name}{product_version}"
        ]
        if len(definitions) != 1:
            raise RuntimeError(
                f"unable to parse definition name. {instance.definition_name=} "
                "expecting name in the form definitions/<product name><version>",
            )

        product_version, version_configuration = self._configurations_manager.get_version_configuration(
            definitions[0][0],
            definitions[0][1],
        )
        health_client_factory = create_health_client_factory(version_configuration)

        product_instance = PimProductInstance(
            instance=instance,
            health_client_factory=health_client_factory,
            service_name=version_configuration.service_name,
            version=product_version,
            config=version_configuration,
            product_host=self._product_host,
        )

        if not product_instance.is_healthy():
            return None

        return product_instance

    def close(self) -> None:
        self._client.close()


class LocalPimSystemFactory(IProductInstanceSystemFactory):
    def __init__(self, product_host: str | None = None) -> None:
        self._product_host = product_host

    def create_system(self, uri: str) -> PimSystem:
        logger.info(f"Connecting to PIM Light Server via {uri} without credentials.")
        options = (("grpc.default_authority", "localhost"),)
        channel = grpc.insecure_channel(uri, options=options)
        client = pypim.Client(channel)
        system = PimSystem(client, self._product_host)
        return system


class ExternalPimSystemFactory(IProductInstanceSystemFactory):
    def __init__(self, certificates_dir: Path, product_host: str | None = None) -> None:
        self._product_host = product_host
        self._certificates_dir = certificates_dir

    def create_system(self, uri: str) -> PimSystem:
        logger.info(
            f"Connecting to PIM Light Server via {uri} with credentials from {self._certificates_dir.as_posix()}.",
        )
        certificate_chain = (self._certificates_dir / "client.crt").read_bytes()
        private_key = (self._certificates_dir / "client.key").read_bytes()
        root_certificates = (self._certificates_dir / "ca.crt").read_bytes()
        creds = grpc.ssl_channel_credentials(
            root_certificates=root_certificates,
            private_key=private_key,
            certificate_chain=certificate_chain,
        )
        channel = grpc.secure_channel(uri, creds)
        client = pypim.Client(channel)
        system = PimSystem(client, self._product_host)
        return system
