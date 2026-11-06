# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0

#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Where ADR lives on disk and whether it can be used at all.

The report is optional: ``ansys-dynamicreporting-core`` is only installable on Python < 3.13
and needs an Ansys installation that ships ADR. Both the backend and the UI ask
:func:`get_report_settings` rather than importing ADR, so the rest of the solution runs
unchanged when ADR is missing.
"""

import getpass
import importlib.util
from pathlib import Path
import tempfile

from pydantic_settings import BaseSettings, SettingsConfigDict


class ReportSettings(BaseSettings):
    """ADR configuration, read from the environment.

    Attributes
    ----------
    adr_installation_directory : str
        ADR folder of an Ansys installation, for example
        ``C:\\Program Files\\ANSYS Inc\\v252\\ADR``. Empty disables the report.
    adr_db_directory : str
        Folder of the ADR database. Defaults to ``adr/report_data`` next to the GLOW project
        files, so that the backend and the UI agree on it without extra configuration.
    glow_project_files_directory : str
        Folder of the GLOW project files, the anchor of the default database location.
    """

    model_config = SettingsConfigDict(extra="ignore")

    adr_installation_directory: str = ""
    adr_db_directory: str = ""
    glow_project_files_directory: str = str(Path(tempfile.gettempdir()) / f"glow_projects_{getpass.getuser()}")

    @property
    def db_directory(self) -> Path:
        """Folder of the ADR database."""
        if self.adr_db_directory:
            return Path(self.adr_db_directory)
        return Path(self.glow_project_files_directory).parent / "adr" / "report_data"

    @property
    def media_directory(self) -> Path:
        """Folder where ADR stores the images of the report items."""
        return self.db_directory / "media"

    @property
    def static_directory(self) -> Path:
        """Folder where ADR collects the CSS and JavaScript the rendered report links to."""
        return self.db_directory.parent / "static_assets"

    @property
    def is_available(self) -> bool:
        """Whether a report can be generated: ADR is installed and an installation is set."""
        return bool(self.adr_installation_directory) and importlib.util.find_spec("ansys.dynamicreporting") is not None


def get_report_settings() -> ReportSettings:
    """Read the ADR configuration from the current environment."""
    return ReportSettings()
