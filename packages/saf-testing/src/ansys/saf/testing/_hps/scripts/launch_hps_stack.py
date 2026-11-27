# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
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
import time

import click

from ansys.saf.testing._hps.process.hps_deployment_process import HpsDeploymentProcess
from ansys.saf.testing._hps.process.hps_scaler_process import HpsScalerProcess
from ansys.saf.testing._hps.scripts.hps_installer import get_hps_external_name


@click.command()
@click.option("--deployment", type=str, default="Desktop", help="Solution deployment type. [default: Desktop]")
@click.option("--no-scaling", is_flag=True, default=False, help="Do not start the HPS Scaling Service.")
@click.option("--product-host", type=str, default="", help="Host of the product, reachable from the Solution API.")
def main(deployment: str, no_scaling: bool, product_host: str) -> None:
    from ansys.saf.glow.client import Deployment  # pyright: ignore[reportMissingImports]

    deployment_type = Deployment.Desktop if deployment.lower() == "desktop" else Deployment.MultiContainer
    hps_scaling = HpsScalerProcess(deployment_type, product_host=product_host) if not no_scaling else None
    try:
        if platform.system() == "Linux":
            print(f"Starting HPS Deployment for {deployment_type.name}...")
            HpsDeploymentProcess.run(deployment_type)
        else:
            print(
                "Assuming HPS Deployment is already running on WSL and exposed on "
                f"https://{get_hps_external_name(deployment_type.name)}:8443/hps...",
            )

        if hps_scaling:
            print(f"Starting HPS Scaling Service for {deployment_type.name}. Exposed on {hps_scaling.product_host}...")
            hps_scaling.start()

        while True:
            time.sleep(10)

    finally:
        if hps_scaling:
            print("Stopping HPS Scaling Service...")
            hps_scaling.stop()
        if platform.system() == "Linux":
            print("Stopping HPS Deployment...")
            HpsDeploymentProcess.stop()


if __name__ == "__main__":
    main()
