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

# ©2026, ANSYS Inc. Unauthorized use, distribution or duplication is prohibited.
"""Creation and setup of the serverless ADR instance used by the ADR reference example.

PyDynamicReporting documentation: https://dynamicreporting.docs.pyansys.com/version/stable/index.html
"""

import logging
from pathlib import Path
import threading

from ansys.dynamicreporting.core.serverless import ADR

from saf.solutions.examples.solution.logic.adr_reference.adr_settings import (
    MEDIA_URL,
    STATIC_URL,
    AdrPaths,
    get_adr_paths,
)

logger = logging.getLogger(__name__)

adr_lock = threading.RLock()
"""Lock serializing the ADR operations of this process.

ADR.setup() configures Django for the whole process and must never run twice or concurrently. The ADR
documentation also recommends running database writes, report rendering, and exports one at a time.
"""


def get_or_create_adr() -> ADR:
    """Get the serverless ADR instance of this process, creating and setting it up if needed.

    Returns
    -------
    ADR
        The ADR singleton, ready to be used.

    Raises
    ------
    AdrNotAvailableError
        If ADR is not configured in the environment.
    """
    paths = get_adr_paths()

    with adr_lock:
        try:
            adr = ADR.get_instance()
        except RuntimeError:
            adr = None

        if adr is not None and adr.is_setup:
            logger.debug("Reusing the serverless ADR instance of this process.")
            _warn_if_configuration_differs(adr, paths)
            return adr

        logger.info("Creating and setting up the serverless ADR instance (database: %s).", paths.database_directory)
        paths.media_directory.mkdir(parents=True, exist_ok=True)
        paths.static_directory.mkdir(parents=True, exist_ok=True)

        # ADR is a singleton: if a previous attempt failed before setup(), this call reconfigures it.
        adr = ADR(
            ansys_installation=str(paths.installation_directory),
            db_directory=str(paths.database_directory),
            media_directory=str(paths.media_directory),
            static_directory=str(paths.static_directory),
            media_url=MEDIA_URL,
            static_url=STATIC_URL,
        )
        adr.setup(collect_static=True)
        logger.info("Serverless ADR instance is set up.")
        return adr


def _warn_if_configuration_differs(adr: ADR, paths: AdrPaths) -> None:
    """Log a warning if the existing ADR instance does not use the expected database directory."""
    if Path(adr.db_directory).resolve() != paths.database_directory.resolve():
        logger.warning(
            "The serverless ADR instance of this process uses the database '%s' instead of '%s'. "
            "ADR can only be configured once per process, so the existing configuration is used.",
            adr.db_directory,
            paths.database_directory,
        )
