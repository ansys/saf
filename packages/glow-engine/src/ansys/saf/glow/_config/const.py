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

from enum import Enum

# the following should match the names of the fields of Settings
GLOW_DEBUG = "GLOW_DEBUG"
GLOW_API_HOT_RELOAD = "GLOW_API_HOT_RELOAD"
GLOW_UI_PYTHON_DEBUGGING = "GLOW_UI_PYTHON_DEBUGGING"
GLOW_DEBUG_API_PORT = "GLOW_DEBUG_API_PORT"
GLOW_DEBUG_UI_PORT = "GLOW_DEBUG_UI_PORT"
GLOW_DEPLOYMENT = "GLOW_DEPLOYMENT"
GLOW_LOGGING_LEVEL = "GLOW_LOGGING_LEVEL"
GLOW_LOG_CONFIG = "GLOW_LOG_CONFIG"
GLOW_UI_LOG_CONFIG = "GLOW_UI_LOG_CONFIG"
GLOW_METHOD_LOG_CONFIG = "GLOW_METHOD_LOG_CONFIG"
GLOW_SOLUTION_DEFINITION = "GLOW_SOLUTION_DEFINITION"
GLOW_UI_MODULE = "GLOW_UI_MODULE"
GLOW_CORS_ORIGINS = "GLOW_CORS_ORIGINS"
GLOW_PROJECT_FILES_DIRECTORY = "GLOW_PROJECT_FILES_DIRECTORY"
GLOW_UI_PROJECT_FILES_DIRECTORY = "GLOW_UI_PROJECT_FILES_DIRECTORY"
OTEL_EXPORTER_OTLP_ENDPOINT = "OTEL_EXPORTER_OTLP_ENDPOINT"
GLOW_DATABASE_TYPE = "GLOW_DATABASE_TYPE"
GLOW_DATABASE_LOCATION = "GLOW_DATABASE_LOCATION"
GLOW_PRODUCT_INSTANCE_SYSTEM = "GLOW_PRODUCT_INSTANCE_SYSTEM"
GLOW_API_HOST = "GLOW_API_HOST"
GLOW_API_PORT = "GLOW_API_PORT"
GLOW_PRODUCT_INSTANCE_SYSTEM_HOST = "GLOW_PRODUCT_INSTANCE_SYSTEM_HOST"
GLOW_PRODUCT_INSTANCE_SYSTEM_PORT = "GLOW_PRODUCT_INSTANCE_SYSTEM_PORT"
GLOW_PRODUCT_INSTANCE_SYSTEM_PROJECT_FILES_DIRECTORY = "GLOW_PRODUCT_INSTANCE_SYSTEM_PROJECT_FILES_DIRECTORY"
GLOW_PRODUCT_INSTANCE_SYSTEM_PLATFORM = "GLOW_PRODUCT_INSTANCE_SYSTEM_PLATFORM"
GLOW_UI_HOST = "GLOW_UI_HOST"
GLOW_UI_PORT = "GLOW_UI_PORT"
GLOW_HPS_HOST = "GLOW_HPS_HOST"
GLOW_HPS_PORT = "GLOW_HPS_PORT"
GLOW_HPS_USERNAME = "GLOW_HPS_USERNAME"
GLOW_HPS_PASSWORD = "GLOW_HPS_PASSWORD"  # noqa: S105 #nosec
GLOW_HPS_CLIENT_ID = "GLOW_HPS_CLIENT_ID"
GLOW_DATA_REPOSITORY_TYPE = "GLOW_DATA_REPOSITORY_TYPE"
GLOW_DATA_REPOSITORY_UPLOAD_ROOT = "GLOW_DATA_REPOSITORY_UPLOAD_ROOT"
GLOW_LONG_RUNNING_EXECUTOR_TYPE = "GLOW_LONG_RUNNING_EXECUTOR_TYPE"
GLOW_METHOD_CLEANUP_CHILD_PROCS = "GLOW_METHOD_CLEANUP_CHILD_PROCS"
ANSYS_GRPC_CERTIFICATES = "ANSYS_GRPC_CERTIFICATES"
GLOW_PIM_SOCKET_PATH = "GLOW_PIM_SOCKET_PATH"  # for pim under linux
GLOW_PRODUCT_HOST = "GLOW_PRODUCT_HOST"  # For host of product instances, and not the product instance system itself
GLOW_PRODUCT_BINDING_HOST = "GLOW_PRODUCT_BINDING_HOST"
GLOW_EXTERNAL_API_URL = "GLOW_EXTERNAL_API_URL"  # To access the API container from outside (e.g. a browser)
GLOW_AUTH_ISSUER_URL = "GLOW_AUTH_ISSUER_URL"
GLOW_AUTH_CLIENT_ID = "GLOW_AUTH_CLIENT_ID"
GLOW_AUTH_DISABLED = "GLOW_AUTH_DISABLED"
GLOW_AUTH_REQUIRED_ROLES = "GLOW_AUTH_REQUIRED_ROLES"
GLOW_AUTH_BYPASS_ROLES = "GLOW_AUTH_BYPASS_ROLES"
GLOW_API_KEY = "GLOW_API_KEY"
GLOW_API_KEY_FILE = "GLOW_API_KEY_FILE"
GLOW_MCP_DISABLED = "GLOW_MCP_DISABLED"
GLOW_MCP_PATH = "GLOW_MCP_PATH"
GLOW_MCP_TRANSPORT_MODE = "GLOW_MCP_TRANSPORT_MODE"

# other environment variables used acrrors the codebase, outside Settings
GLOW_API_URL = "GLOW_API_URL"  # kept out of Settings to avoid confusion with api_host/port
GLOW_PORTAL_URL = "GLOW_PORTAL_URL"
# For the Dash UI on the browser to be able to connect to the API websockets,
# as the browser doesn't have access to Docker Compose network hostnames.
GLOW_WS_EVENTS_ADDR = "GLOW_WS_EVENTS_ADDR"
# Used to allow solution configuration overwrite when the new configuration introduces breaking changes.
# It is a temporary env var.
GLOW_OVERWRITE_SOLUTION_CONFIG = "GLOW_OVERWRITE_SOLUTION_CONFIG"
# Used in gql, both API and Client
GLOW_GRAPHQL_POOL_SIZE = "GLOW_GRAPHQL_POOL_SIZE"
LOCALHOST_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

# other constants used across the codebase
DEFAULT_DATABASE_FILE = "glow.db"
DEFAULT_DB_TABLE_NAME = "glow"
# For launching API
DEFAULT_DEBUG_PORT = 5724
# For launching UI
DEFAULT_SOLUTION_API_URL = "http://127.0.0.1:5432"
DEFAULT_UI_DEBUG_PORT = 5725
# Service names
GLOW_API_SERVICE_NAME = "GLOW API"
GLOW_UI_SERVICE_NAME = "GLOW UI"
GLOW_METHOD_RUNNER_SERVICE_NAME = "GLOW METHOD RUNNER"
# For finding instance configurations
PRODUCT_INSTANCE_CONFIGS_DIR_NAME = "product_instance_configs"
# For the automatic configuration of HPS authorization
DEFAULT_GLOW_HPS_CLIENT_ID = "rep-jms-web"
# For authorization
DEFAULT_GLOW_AUTH_DISABLED = "True"
# For HPS instances
JOB_DEFAULT_MAX_RUNNING_TIME = 7200
INSTANCES_USED_BY_METHOD_ATTRIBUTE_STRING = "_instances_used_by_method"
# For multiple workers
DEFAULT_GLOW_API_NUMBER_OF_WORKERS = (
    4  # no override except on uvicorn cmd line, all internal invocations using postgres on uvicorn use this value
)
# For caching HPS Client
TEST_HPS_CLIENT_CACHE_TTL_SECONDS = "TEST_HPS_CLIENT_CACHE_TTL_SECONDS"
DEFAULT_HPS_CLIENT_CACHE_TTL_SECONDS = 60.0
AUTH_SCRIPT_MARKER = "// GLOW Authentication Refresh Handler"
DEFAULT_SOLUTION_MD_FILENAME = "SOLUTION.md"


class Deployment(Enum):
    """Categories of deployments for the GLOW server."""

    Desktop = "Desktop"
    DockerCompose = "DockerCompose"
    Unknown = "Unknown"


class LoggingLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DatabaseType(Enum):
    Sqlite = "sqlite"
    PostgreSql = "postgresql"


class ProductInstanceSystemType(Enum):
    PIM = "PIM"
    HPS = "HPS"
    _MOCK = "_MOCK"


class ExecutorType(Enum):
    Process = "Process"
    Thread = "Thread"
