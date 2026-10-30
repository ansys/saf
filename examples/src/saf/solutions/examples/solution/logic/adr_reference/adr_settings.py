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
"""Configuration of the serverless ADR instance used by the ADR reference example.

The configuration is read from the environment (``.env`` file of the solution):

- ``ADR_INSTALLATION_DIRECTORY``: Ansys Dynamic Reporting installation directory,
  for example ``C:\\Program Files\\ANSYS Inc\\v271\\ADR``.
- ``GLOW_PROJECT_FILES_DIRECTORY``: GLOW project files directory. The ADR database,
  media, and static directories are created next to it.

Serverless ADR can only be configured once per Python process. All examples of this
solution therefore share the same ADR directories and URLs, and each example keeps
its content separate by using its own templates and item tags.
"""

from dataclasses import dataclass
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

MEDIA_URL = "/media/"
"""URL prefix used by ADR to reference media files (images, scenes, files) in rendered reports."""

STATIC_URL = "/static_assets/"
"""URL prefix used by ADR to reference static files (CSS, JavaScript, fonts) in rendered reports."""


class AdrNotAvailableError(RuntimeError):
    """Raised when Ansys Dynamic Reporting is not installed or not configured."""


class _AdrSettings(BaseSettings):
    """Environment variables needed to set up serverless ADR."""

    model_config = SettingsConfigDict(extra="ignore")

    adr_installation_directory: str = ""
    glow_project_files_directory: str = ""


@dataclass(frozen=True)
class AdrPaths:
    """Directories used by the serverless ADR instance."""

    installation_directory: Path
    database_directory: Path
    media_directory: Path
    static_directory: Path


@dataclass(frozen=True)
class AdrAvailability:
    """Result of the ADR availability check."""

    is_available: bool
    message: str


def check_adr_availability() -> AdrAvailability:
    """Check that ADR is configured in the environment and that its installation directory exists.

    Returns
    -------
    AdrAvailability
        Whether ADR is available and a message describing the result.
    """
    settings = _AdrSettings()

    if not settings.adr_installation_directory:
        return AdrAvailability(
            is_available=False,
            message="The ADR_INSTALLATION_DIRECTORY environment variable is not set. "
            "Set it in the .env file of the solution, for example: "
            "ADR_INSTALLATION_DIRECTORY=C:\\Program Files\\ANSYS Inc\\v271\\ADR",
        )

    installation_directory = Path(settings.adr_installation_directory)
    if not installation_directory.is_dir():
        return AdrAvailability(
            is_available=False,
            message=f"The ADR installation directory '{installation_directory}' does not exist. "
            "Check the ADR_INSTALLATION_DIRECTORY environment variable.",
        )

    if not settings.glow_project_files_directory:
        return AdrAvailability(
            is_available=False,
            message="The GLOW_PROJECT_FILES_DIRECTORY environment variable is not set. "
            "It is needed to locate the ADR database.",
        )

    return AdrAvailability(is_available=True, message=f"ADR found in '{installation_directory}'.")


def get_adr_paths() -> AdrPaths:
    """Get the directories used by the serverless ADR instance.

    Returns
    -------
    AdrPaths
        Installation, database, media, and static directories.

    Raises
    ------
    AdrNotAvailableError
        If ADR is not available.
    """
    availability = check_adr_availability()
    if not availability.is_available:
        raise AdrNotAvailableError(availability.message)

    settings = _AdrSettings()
    database_directory = Path(settings.glow_project_files_directory).parent / "adr" / "report_data"
    return AdrPaths(
        installation_directory=Path(settings.adr_installation_directory),
        database_directory=database_directory,
        media_directory=database_directory / "media",
        static_directory=database_directory.parent / "static_assets",
    )
