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

from __future__ import annotations

import importlib
import os
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
import platform
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import (
    Discriminator,
    Field,
    PostgresDsn,
    Tag,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

from ansys.saf.glow._bdm.datarepo import DEFAULT_GLOW_DATA_REPOSITORY_UPLOAD_ROOT, DataRepositoryType
from ansys.saf.glow._config.const import (
    ANSYS_GRPC_CERTIFICATES,
    DEFAULT_DATABASE_FILE,
    DEFAULT_GLOW_API_NUMBER_OF_WORKERS,
    DEFAULT_GLOW_HPS_CLIENT_ID,
    GLOW_API_KEY,
    GLOW_API_KEY_FILE,
    GLOW_PIM_SOCKET_PATH,
    GLOW_PRODUCT_INSTANCE_SYSTEM_HOST,
    GLOW_PRODUCT_INSTANCE_SYSTEM_PORT,
    LOCALHOST_HOSTS,
    DatabaseType,
    Deployment,
    ExecutorType,
    LoggingLevel,
    ProductInstanceSystemType,
)
from ansys.saf.glow._utilities.solution_modules import (
    find_solution,
    find_solution_name,
    get_autodiscovery_definition_module_str,
    get_autodiscovery_ui_module_str,
)

if TYPE_CHECKING:
    from types import ModuleType
    from typing import Self

    from ansys.saf.glow._core.solution import Solution


class Settings(BaseSettings):
    """Configuration variables read from the environment from within
    GLOW containers. Currently this is only used for parsing
    environment variables in the method, UI and API server containers
    (other containers may follow). It is also used (but not parsed) in
    the orchestrator to help to the process of setting up the
    environments of the above containers.

    See: https://pydantic-docs.helpmanual.io/usage/settings/
    and https://fastapi.tiangolo.com/advanced/settings/#environment-variables
    """

    model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8", extra="allow")

    glow_solution_definition: str = Field(
        default_factory=get_autodiscovery_definition_module_str,
        description="The solution definition module",
    )
    glow_ui_module: str | None = Field(
        default_factory=get_autodiscovery_ui_module_str,
        description="The UI definition module",
    )
    glow_deployment: Deployment = Field(default=Deployment.Desktop, description="The deployment GLOW is running in.")
    glow_debug: bool | None = Field(
        default=False,
        description=("Whether to enable debugging in GLOW."),
    )
    glow_api_hot_reload: bool = Field(
        default=True,
        description=("Whether to enable Uvicorn hot reload. Only has an effect if debug mode is activated."),
    )
    glow_ui_python_debugging: bool | None = Field(
        default=False,
        description=(
            "Whether to enable python debugging in GLOW UI. "
            "Setting it to True implies that debugpy.listen is invoked by the ui server process "
            "and the debug functionality of Dash / Flask is disabled"
        ),
    )
    glow_api_host: str = Field(
        default="127.0.0.1",
        description="The host where the solution API server will be running.",
    )
    glow_api_port: int = Field(default=5432, description="The port where the solution API server will be running.")
    glow_ui_host: str = Field(default="127.0.0.1", description="The host where the solution UI server will be running.")
    glow_ui_port: int = Field(default=5433, description="The port where the solution UI server will be running.")
    glow_product_instance_system_host: str = Field(
        default="127.0.0.1",
        description="The host where the product instance management system (PIM or HPS) will be running.",
    )
    glow_product_instance_system_port: int | None = Field(
        default=None,
        description="The port where the product instance management system (PIM or HPS) will be running.",
    )
    glow_pim_socket_path: Path | None = Field(
        default=None,
        description="The linux socket path used by PIM for secured connection.",
    )
    glow_product_instance_system: ProductInstanceSystemType = Field(
        default=ProductInstanceSystemType.PIM,
        description="The product instance management system to be used: PIM, HPS. By default, PIM is used.",
    )
    glow_product_instance_system_project_files_directory: str | None = Field(
        default=None,
        description=(
            "For deployments where the Product Instance Manager system is running in a different system "
            "than the GLOW API server. It is the absolute path to the project files directory that is shared with "
            "the GLOW API server, in a form accessible to the product."
        ),
    )
    glow_product_instance_system_platform: Literal["Windows", "Linux"] | None = Field(
        default=None,
        description=(
            "For deployments where the Product Instance Manager system is running in a different system "
            "than the GLOW API server. It is the platform type where the system is running: Windows or Linux."
        ),
    )
    glow_product_host: str | None = Field(
        default=None,
        description="The host where the product instance is running.",
    )
    glow_hps_host: str = Field(
        default="127.0.0.1",
        description="The host where the HPS where the application to submit jobs to HPS will be running.",
    )
    glow_hps_port: int | None = Field(
        default=None,
        description="The port where the HPS where the application to submit jobs to HPS will be running.",
    )
    glow_hps_username: str = Field(
        default="",
        description="HPS username for username-password authorization.",
    )
    glow_hps_password: str = Field(
        default="",
        description="HPS password for username-password authorization.",
    )
    glow_hps_client_id: str = Field(
        default=DEFAULT_GLOW_HPS_CLIENT_ID,
        description="HPS client id for the configuration of the interactive authorization",
    )
    glow_auth_service_account_client_id: str | None = Field(
        default=None,
        description="Client id of the service account.",
    )
    glow_auth_service_account_client_secret: str | None = Field(
        default=None,
        description="Client secret of the service account.",
    )
    glow_auth_issuer_url: str | None = Field(
        default=None,
        description="Address of the Identity Provider for authenticated access to the GLOW API.",
    )
    glow_auth_client_id: str | None = Field(
        default=None,
        description="The public oauth2 identifier of the solution api.",
    )
    glow_auth_disabled: bool = Field(
        default=True,  # Disabled by default.
        description="Specifies whether authorization should be disabled or not.",
    )
    glow_auth_required_roles: str | None = Field(
        default=None,
        description=(
            "Comma-separated client roles (of glow_auth_client_id) the user must all hold. "
            "Only enforced when authorization is enabled."
        ),
    )
    glow_auth_bypass_roles: str | None = Field(
        default=None,
        description="Comma-separated client roles (of glow_auth_client_id) that exempt the user from required roles.",
    )
    glow_api_key: str | None = Field(
        default=None,
        description="API key for authenticating local requests to the API server.",
    )
    glow_api_key_file: Path | None = Field(
        default=None,
        description="Path to a file containing the API key for authenticating local requests to the API server.",
    )
    # A value of -1 disables debugpy. Leaving it unconfigured will dynamically find a free port starting
    # with DEFAULT_DEBUG_API_PORT. This behaviour is consistent with other port configurations in GLOW.
    glow_debug_api_port: int | None = Field(default=None, description="The Python debugger port for this process.")
    # A value of -1 disables debugpy. Leaving it unconfigured will dynamically find a free port starting
    # with DEFAULT_DEBUG_UI_PORT. This behaviour is consistent with other port configurations in GLOW.
    glow_debug_ui_port: int | None = Field(default=None, description="The Python debugger port for the UI process.")
    glow_log_config: Path | None = Field(
        default=None,
        description="The full OS file system path to the ``YAML`` logging configuration file for the API service.",
    )
    glow_ui_log_config: Path | None = Field(
        default=None,
        description="The full OS file system path to the ``YAML`` logging configuration file for the UI service.",
    )
    glow_method_log_config: Path | None = Field(
        default=None,
        description="The full OS file system path to the ``YAML`` logging configuration file for the Method Runner.",
    )
    glow_logging_level: LoggingLevel | None = Field(default=None, description="Logging level.")
    glow_project_files_directory: Path | None = Field(
        default=None,
        description="The full OS file system path to the directory where project files are stored "
        "(by default, project files are stored in %APPDATA%/ansys/glow/SOLUTION_NAME/project_files/).",
    )
    glow_ui_project_files_directory: Path | None = Field(
        default=None,
        description="For deployments where the UI is running in a different system "
        "than the GLOW API server. It is the absolute path to the project files directory that is shared with "
        "the GLOW API server.",
    )
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None,
        description=(
            "The endpoint for the OTLP exporters (traces, logs, and metrics). Non-URL values enable export to stderr."
        ),
    )
    glow_database_type: DatabaseType = Field(
        default=DatabaseType.Sqlite,
        description="The type of database to be used: sqlite, postgresql. By default, sqlite is used.",
    )
    glow_database_location: (
        Annotated[
            Annotated[Path, Tag("path")] | Annotated[PostgresDsn, Tag("postgres")],
            Discriminator(lambda v: "postgres" if str(v).startswith("postgres") else "path"),
        ]
        | None
    ) = Field(
        default=None,
        description=(
            "The location of the database. It can be a file path (for sqlite) or a Postgres connection URI of"
            "the form 'postgresql://username:password@host:port'. "
            "(by default, database location is at %APPDATA%/ansys/glow/SOLUTION_NAME/glow.db)."
        ),
    )
    glow_cors_origins: list[str] | None = Field(
        default=None,
        description="A list of origins that should be permitted to make cross-origin requests.",
    )
    glow_data_repository_type: DataRepositoryType | None = Field(
        default=None,
        description="The type of data repository to be used: FileSystem, Minerva. By default, none is used.",
    )
    glow_data_repository_upload_root: str = Field(
        default=DEFAULT_GLOW_DATA_REPOSITORY_UPLOAD_ROOT,
        description=(
            "The path in the subsidiary system to which a relative path is appended when uploading data. "
            "If the upload path is an absolute path, the upload path is used."
        ),
    )
    glow_bdm_gc_disabled: bool = Field(
        default=False,
        description="Whether to disable the BDM garbage collection.",
    )
    glow_enable_automatic_project_migration: bool = Field(
        default=False,
        description="Whether to activate automatic migration for existing projects.",
    )
    # The following config is undocumented on purpose, since its usage is for testing purposes only for the time being.
    # Note that this is not actually turning long-running methods into synchronous-blocking ones, it's only changing the
    # backend used for executing long-running, but they are still long-running (and thus, executed in background, etc.).
    glow_long_running_executor_type: ExecutorType = Field(
        default=ExecutorType.Process,
        description="The type of executor to be used for long-running methods: Process, Thread. By default, Process.",
    )
    glow_method_cleanup_child_procs: bool = Field(
        default=True,
        description="Whether to kill child processes spawned by a long-running transaction method after it completes. "
        "If set to False, child processes are not killed and a warning is logged with the list of PIDs still alive.",
    )
    glow_api_number_of_workers: int | None = Field(
        default=None,
        description="Number of uvicorn workers for the API server when the API server is launched via the GLOW CLI. "
        "If set to None, the default value, then an a number of workers appropriate to the selected database are used "
        f"(1 for Sqlite, {DEFAULT_GLOW_API_NUMBER_OF_WORKERS} for PostgreSql). "
        "This setting is ignored if the API server is launched directly using the uvicorn CLI.",
    )

    glow_api_hot_reload_monitoring_dir: Path | None = Field(
        default=None,
        description="Directory to be monitored for hot-reload. If set to None then parent of the solution definition "
        "module is used.",
    )

    ansys_grpc_certificates: Path | None = Field(
        default=None,
        description="The directory where Ansys certificates used for gRPC mTLS transport are placed.",
    )

    glow_external_api_url: str | None = Field(
        default=None,
        description="The external URL for the GLOW API service.",
    )

    glow_ws_event_poll_interval: float = Field(
        default=1.0,
        description=(
            "The interval in seconds between a query for new events and transmitting the events on a websocket."
        ),
    )
    glow_mcp_disabled: bool = Field(
        default=True,
        description="Whether MCP mounting into the API server should be disabled.",
    )
    glow_mcp_transport_mode: Literal["http", "streamable-http", "sse"] = Field(
        default="http",  # default transport of FastMCP.http_app()
        description="Transport mode for MCP. Accepted values: 'http', 'streamable-http', 'sse'.",
    )
    glow_mcp_path: str = Field(
        default="/sse",  # path accepted by internal policies for development/testing
        description="Mount path for MCP endpoints when MCP is enabled.",
    )

    @property
    def computed_database_location(self) -> Path | PostgresDsn:
        if self.glow_database_type == DatabaseType.Sqlite:
            if self.glow_database_location and isinstance(self.glow_database_location, Path):
                # should always be a path after the validator, but just to avoid pyright complaints
                return self.glow_database_location.expanduser().resolve()
            return self.computed_solution_appdata_directory / DEFAULT_DATABASE_FILE
        else:
            if self.glow_database_location is None:
                # so pyright doesn't complain and as a fail-safe check. it shouldn't happen after the validator, though.
                raise RuntimeError(f"Missing database location for database type {self.glow_database_type}.")
            return self.glow_database_location

    # Pydantic recommends to use a model_validator when requiring access to other fields
    # https://docs.pydantic.dev/latest/concepts/validators/#field-validators
    @model_validator(mode="after")
    def validate_database_location(self) -> Self:
        if self.glow_database_type == DatabaseType.Sqlite:
            if self.glow_database_location and not isinstance(self.glow_database_location, Path):
                raise ValueError(
                    f"Invalid database location for Sqlite database: '{self.glow_database_location}'. "
                    "Expected a file path.",
                )
            elif isinstance(self.glow_database_location, Path) and not self.glow_database_location.parent.exists():
                # glow_database_location is the full path to the db file, not only the parent directory. We only require
                # the directory to exist. Sqlite will create the db file if it doesn't exist.
                raise ValueError(
                    f"The system cannot find directory for the Sqlite DB file '{self.glow_database_location}'.",
                )
        elif self.glow_database_type == DatabaseType.PostgreSql and not isinstance(
            self.glow_database_location,
            MultiHostUrl | PostgresDsn,
        ):
            # Until recently, we needed to use MultiHostUrl because PostgresDsn was a subscripted generic,
            # and MultiHostUrl was the real type if checked with type(). However, that seems to have changed recently.
            # Supporting both for the time being.
            raise ValueError(
                f"Invalid database location for PostgreSql database: '{self.glow_database_location}'. "
                "Expected a PostgresDsn.",
            )
        return self

    @model_validator(mode="after")
    def validate_api_key_source(self) -> Self:
        if self.glow_api_key and self.glow_api_key_file:
            raise ValueError(
                f"Conflicting API key configuration detected: configure either {GLOW_API_KEY} or {GLOW_API_KEY_FILE}, "
                "but not both.",
            )
        if self.glow_api_key_file is None:
            return self

        if not self.glow_api_key_file.is_absolute():
            raise ValueError(f"The API key file path must be absolute: '{self.glow_api_key_file}'")
        if not self.glow_api_key_file.is_file():
            raise ValueError(f"The system cannot find the API key file '{self.glow_api_key_file}'.")

        try:
            # trying to set here self.glow_api_key with the content of self.glow_api_key_file causes issues in future
            # calls where settings has then both fields set and raises the conflicting value error at the beginning.
            # Still reading here just to have early validation and be able to raise error on startup.
            _ = self.glow_api_key_file.read_text(encoding="utf-8").rstrip()
        except OSError as exc:
            raise ValueError(f"Failed to read API key file '{self.glow_api_key_file}': {exc}") from None

        return self

    @property
    def computed_api_key(self) -> str | None:
        if self.glow_api_key:
            return self.glow_api_key
        elif self.glow_api_key_file:
            return self.glow_api_key_file.read_text(encoding="utf-8").rstrip()
        return None

    @property
    def computed_api_hot_reload_monitoring_dir(self) -> Path:
        if self.glow_api_hot_reload_monitoring_dir:
            return self.glow_api_hot_reload_monitoring_dir
        raw_def_module_file = self.computed_definition_module.__file__
        if raw_def_module_file:
            solution_dir = Path(raw_def_module_file).parent
            if solution_dir.is_absolute():
                return solution_dir
        return Path().cwd()

    @property
    def computed_number_of_workers(self) -> int:
        """
        Returns the number of workers to be used by uvicorn for the API server
        when starting uvicorn via the GLOW CLI.
        This value is ignored if the API server is launched directly using the uvicorn CLI.
        If glow_api_number_of_workers is set, it returns that value.
        Otherwise, it returns a value appropriate to the database server.
        """
        if self.glow_api_number_of_workers is not None:
            return self.glow_api_number_of_workers
        if self.glow_database_type == DatabaseType.Sqlite:
            return 1  # sqlite doesn't support row locking so we use only one worker
        return DEFAULT_GLOW_API_NUMBER_OF_WORKERS

    @property
    def computed_definition_module(self) -> ModuleType:
        return importlib.import_module(self.glow_solution_definition)

    @property
    def computed_solution_name(self) -> str:
        return find_solution_name(self.glow_solution_definition)

    @property
    def computed_solution_type(self) -> type[Solution]:
        return find_solution(self.computed_definition_module)

    @property
    def computed_project_files_directory(self) -> Path:
        return self.glow_project_files_directory or self.computed_solution_appdata_directory / "project_files"

    @property
    def computed_ui_project_files_directory(self) -> Path:
        return self.glow_ui_project_files_directory or self.computed_project_files_directory

    @property
    def computed_solution_appdata_directory(self) -> Path:
        return self.glow_appdata_directory() / self.computed_solution_name

    @property
    def computed_glow_product_instance_system_host(self) -> str:
        if self.glow_product_instance_system_port:
            return self.glow_product_instance_system_host
        elif self.glow_product_instance_system == ProductInstanceSystemType.HPS and self.glow_hps_port:
            return self.glow_hps_host
        else:
            return ""

    @property
    def computed_glow_product_instance_system_port(self) -> int | None:
        if self.glow_product_instance_system_port:
            return self.glow_product_instance_system_port
        elif self.glow_product_instance_system == ProductInstanceSystemType.HPS and self.glow_hps_port:
            return self.glow_hps_port
        else:
            return None

    @property
    def computed_glow_product_instance_system_uri(self) -> str | None:
        if self.glow_product_instance_system == ProductInstanceSystemType.HPS:
            if self.computed_glow_product_instance_system_host and self.computed_glow_product_instance_system_port:
                return f"https://{self.computed_glow_product_instance_system_host}:{self.computed_glow_product_instance_system_port}/hps"
            else:
                return None
        elif self.glow_product_instance_system == ProductInstanceSystemType.PIM:
            if self.computed_glow_product_instance_system_host and self.computed_glow_product_instance_system_port:
                # covers:
                # - Windows secure (localhost and external)
                # - Linux secure (external)
                # - Linux insecure (localhost)
                return f"{self.computed_glow_product_instance_system_host}:{self.computed_glow_product_instance_system_port}"  # noqa: E501
            elif self.glow_pim_socket_path:
                # covers: Linux secure (localhost)
                return f"unix:{self.glow_pim_socket_path}"
            else:
                return None
        else:
            return None

    @property
    def computed_glow_hps_host(self) -> str:
        if self.glow_hps_port:
            return self.glow_hps_host
        elif (
            self.glow_product_instance_system == ProductInstanceSystemType.HPS
            and self.glow_product_instance_system_port
        ):
            return self.glow_product_instance_system_host
        else:
            return ""

    @property
    def computed_glow_hps_port(self) -> int | None:
        if self.glow_hps_port:
            return self.glow_hps_port
        elif (
            self.glow_product_instance_system == ProductInstanceSystemType.HPS
            and self.glow_product_instance_system_port
        ):
            return self.glow_product_instance_system_port
        else:
            return None

    @property
    def computed_glow_hps_url(self) -> str | None:
        if self.computed_glow_hps_host and self.computed_glow_hps_port:
            return f"https://{self.computed_glow_hps_host}:{self.computed_glow_hps_port}/hps"
        return None

    @property
    def computed_external_api_url(self) -> str:
        return (
            f"http://{self.glow_api_host}:{self.glow_api_port}"
            if self.glow_external_api_url is None
            else self.glow_external_api_url
        )

    @model_validator(mode="after")
    def validate_product_instance_system_directory(self) -> Self:
        if self.glow_product_instance_system_project_files_directory:
            project_path: PurePath | None = None
            if not self.glow_product_instance_system_platform:
                raise ValueError(
                    "Project files directory in product instance system is configured "
                    "but not the product instance system platform.",
                )
            elif self.glow_product_instance_system_platform == "Windows":
                project_path = PureWindowsPath(self.glow_product_instance_system_project_files_directory)
            elif self.glow_product_instance_system_platform == "Linux":
                project_path = PurePosixPath(self.glow_product_instance_system_project_files_directory)
            if project_path and not project_path.is_absolute():
                raise ValueError(f"Project files directory should be an absolute path: {project_path}.")
        return self

    @field_validator(
        "glow_project_files_directory",
        "glow_ui_project_files_directory",
    )
    @classmethod
    def validate_directory(cls, path: Path | None) -> Path | None:
        if path is None:
            return path
        if not path.is_absolute():
            raise ValueError(f"Directory should be an absolute path: {path}.")
        resolved_path = path.expanduser().resolve()
        if not resolved_path.exists():
            resolved_path.mkdir(parents=True)
        return resolved_path

    @field_validator(
        "glow_log_config",
        "glow_ui_log_config",
        "glow_method_log_config",
        "glow_api_hot_reload_monitoring_dir",
    )
    @classmethod
    def validate_path(cls, path: Path | None, info: ValidationInfo) -> Path | None:
        if path is None:
            return path
        field_name = "setting referring to path" if info.field_name is None else info.field_name.upper()
        if not path.is_absolute():
            raise ValueError(f"{field_name} should be an absolute path not '{path}'.")
        resolved_path = path.expanduser().resolve()
        if not resolved_path.exists():
            raise ValueError(f"The system cannot find the path '{path}' specified by {field_name}")
        return resolved_path

    def glow_appdata_directory(self) -> Path:
        if platform.system() == "Windows":
            directory = os.environ["APPDATA"]
        else:
            directory = os.getenv("XDG_DATA_HOME", "~/.local/share")
        return Path(directory).expanduser().resolve() / "ansys" / "glow"

    @model_validator(mode="after")
    def validate_pim_grpc_certificates(self) -> Self:
        if self.glow_product_instance_system != ProductInstanceSystemType.PIM:
            return self

        if (
            self.computed_glow_product_instance_system_host not in LOCALHOST_HOSTS
            and self.computed_glow_product_instance_system_port
        ):
            if self.ansys_grpc_certificates is None:
                raise ValueError(
                    f"Missing Ansys gRPC certificates directory ({ANSYS_GRPC_CERTIFICATES}) for "
                    "non-localhost connections to PIM Light Server.",
                )

            cert_file = self.ansys_grpc_certificates / "client.crt"
            key_file = self.ansys_grpc_certificates / "client.key"
            ca_file = self.ansys_grpc_certificates / "ca.crt"
            missing = [f.as_posix() for f in (cert_file, key_file, ca_file) if not f.is_file()]
            if missing:
                raise ValueError(f"Missing required TLS file(s) for mutual TLS: {', '.join(missing)}")

        return self

    @model_validator(mode="after")
    def validate_pim_unix_socket_path(self) -> Self:
        if self.glow_product_instance_system != ProductInstanceSystemType.PIM or platform.system() != "Linux":
            return self

        if (
            self.computed_glow_product_instance_system_host in LOCALHOST_HOSTS
            and self.computed_glow_product_instance_system_port
        ):
            if self.glow_pim_socket_path is None:
                raise ValueError(f"Missing socket path ({GLOW_PIM_SOCKET_PATH}) for localhost connections on Linux.")
            else:
                raise ValueError(
                    f"Conflicting PIM configuration detected: both socket path ({GLOW_PIM_SOCKET_PATH}) and "
                    f"host/port ({GLOW_PRODUCT_INSTANCE_SYSTEM_HOST}/{GLOW_PRODUCT_INSTANCE_SYSTEM_PORT}) "
                    f"are provided. For localhost connections on Linux, please use only {GLOW_PIM_SOCKET_PATH}.",
                )

        return self
