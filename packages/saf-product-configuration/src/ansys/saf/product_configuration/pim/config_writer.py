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
import logging
import os
from pathlib import Path
import pkgutil
import platform
import shlex
import textwrap

from ansys.saf import product_configuration
from ansys.saf.product_configuration.interfaces import IProductInstanceConfiguration

_PIM_TIMEOUT_ENV = "SAF_PIM_TIMEOUT"
LOCALHOSTS = ["localhost", "127.0.0.1"]
DEFAULT_GLOW_PRODUCT_BINDING_HOST = "0.0.0.0"  # noqa: S104
DEFAULT_GLOW_PRODUCT_BINDING_SECURE_HOST = "localhost"


logger = logging.getLogger(__name__)


class PimLightConfigWriter:
    """A utility class for writing PIM Light Server configuration files."""

    @staticmethod
    def _list_built_in_product_configs() -> list[str]:
        built_in_product_configs: list[str] = []
        for _, submodule_name, is_pkg in pkgutil.iter_modules(product_configuration.__path__):
            if is_pkg:
                continue
            full_name = f"{product_configuration.__name__}.{submodule_name}"
            submodule = importlib.import_module(full_name)
            for member_name, _ in inspect.getmembers(
                submodule,
                lambda x: (
                    inspect.isclass(x)
                    and
                    # can't use issubclass for Protocol-based classes
                    IProductInstanceConfiguration in x.__bases__
                ),
            ):
                built_in_product_configs.append(member_name)

        return built_in_product_configs

    @classmethod
    def write_config(
        cls,
        configurations_dir: Path,
        instance_configuration: IProductInstanceConfiguration,
    ):
        """
        Writes the PIM configuration to a YAML file in the specified configurations directory.

        Parameters
        ----------
          configurations_dir : Path
              The path to the directory where the configuration YAML file will be written.

        Examples
        --------
        You can write the configuration to a directory called ``my_solution/product_instance_configs`` like this:

        >>> config.write_config(Path("my_solution/product_instance_configs"))
        """
        for version in instance_configuration.versions:
            try:
                instance_version_config = instance_configuration.get_version_configuration(version)
                bind_host = os.environ.get(
                    "GLOW_PRODUCT_BINDING_HOST",
                    (
                        DEFAULT_GLOW_PRODUCT_BINDING_HOST
                        if not instance_version_config.enable_secure_flags
                        else DEFAULT_GLOW_PRODUCT_BINDING_SECURE_HOST
                    ),
                )
                arguments = instance_version_config.execution_command.replace("\\", "\\\\").replace("${EXECUTABLE}", "")
                os_platform = platform.system().lower()
                startup_timeout = os.environ.get(_PIM_TIMEOUT_ENV, 30)
                command = instance_version_config.exe_path_for_pim.replace("\\", "\\\\")
                if instance_version_config.enable_secure_flags:
                    if bind_host in LOCALHOSTS and os_platform == "windows":
                        arguments += f" {instance_version_config.windows_local_secure_flags}"
                    else:
                        arguments += f" {instance_version_config.insecure_flags}"
                arguments = shlex.split(arguments)

                # we use dedent() to remove leading spaces in the string while keeping the overall indentation so
                # numpydoc does not raise an error.
                config = textwrap.dedent(
                    f"""\
                    configVersion: 1.0
                    name: {instance_configuration.product_name}{version}
                    productName: {instance_configuration.product_name}
                    productVersion: {version}
                    stateful: true
                    startupTimeout: {startup_timeout}
                    ports:
                      - name: {instance_version_config.service_type.value}
                        value: 0
                    services:
                      - name: {instance_version_config.service_name}
                        nameBeta2: {instance_version_config.service_name}
                        type: {instance_version_config.service_type.value}
                        port: {instance_version_config.service_type.value}
                        basePath: ""
                    recipes:
                      exec:
                        os:
                          - platform: {os_platform}
                            config:
                              command: "{command}"
                              args:
                    """,
                )
                if not arguments:
                    # PIM Light Server (or yaml) complains if args is empty or it's not present.
                    arguments.append("")
                for arg in arguments:
                    config += f'            - "{arg}"\n'

                if instance_version_config.environment:
                    config += "env:\n"
                    for (
                        env_name,
                        env_value,
                    ) in instance_version_config.environment.items():
                        config += f"  {env_name}: {env_value}\n"
                config = config.replace(
                    "${PORT}",
                    f"${{AENEID_PORT_{instance_version_config.service_type.value.upper()}}}",
                ).replace("${HOST}", bind_host)
                (configurations_dir / f"{instance_configuration.product_name}{version}.yaml").write_text(config)
            except Exception as e:
                error_msg = (
                    f"The configuration for '{instance_configuration.product_name}' '{version}' is not valid: {e}"
                )
                if instance_configuration.__class__.__name__ in cls._list_built_in_product_configs():
                    # It is expected that a host may not have all supported products installed
                    logger.warning(error_msg)
                else:
                    # If the product config is a custom one, we do expect it to work
                    logger.exception(error_msg)
                continue
