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

# We are deliberately exporting unused symbols
# because we're consolidating the SDK for their solution developer
# pyright: reportUnusedImport=false

# This is the public module exposing everything related to product instance configurations
from ansys.saf.glow._core.instance.pim_system import PimProductInstanceVersionDefinition
from ansys.saf.product_configuration.interfaces import (
    IProductInstanceConfiguration,
    IProductInstanceVersionConfiguration,
    ISoftware,
    ServiceType,
    Software,
)
from ansys.saf.product_configuration.manager.configurations_manager import ProductInstanceConfigurationsManager
from ansys.saf.product_configuration.pim.config_writer import PimLightConfigWriter

__all__ = [
    "ProductInstanceConfigurationsManager",
    "IProductInstanceConfiguration",
    "IProductInstanceVersionConfiguration",
    "PimLightConfigWriter",
    "PimProductInstanceVersionDefinition",
    "ServiceType",
    "Software",
    "ISoftware",
]
