// Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
// SPDX-License-Identifier: Apache-2.0
//

// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at

//     http://www.apache.org/licenses/LICENSE-2.0

// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.


import { EnvironmentVariableDefinition } from '../types/solution';

/**
 * Definitions for all SAF/GLOW environment variables.
 * This is the single source of truth for variable metadata.
 */
export const ENVIRONMENT_VARIABLE_DEFINITIONS: EnvironmentVariableDefinition[] = [
    // API server
    { name: 'GLOW_API_HOST', defaultValue: '127.0.0.1', description: 'The host where the solution API server will be running.', category: 'API server' },
    { name: 'GLOW_API_PORT', defaultValue: '5432', description: 'The port where the solution API server will be running.', category: 'API server' },
    { name: 'GLOW_SOLUTION_DEFINITION', defaultValue: null, description: 'The solution definition module. Used to specify the module when launching the API application directly via a production server instead of GLOW\'s CLI.\n\n Example: ansys.solutions.my_solution.solution.definition.', category: 'API server' },

    // UI server
    { name: 'GLOW_UI_HOST', defaultValue: '127.0.0.1', description: 'The host where the solution UI server will be running.', category: 'UI server' },
    { name: 'GLOW_UI_PORT', defaultValue: '5433', description: 'The port where the solution UI server will be running.', category: 'UI server' },
    { name: 'GLOW_API_URL', defaultValue: 'http://127.0.0.1:5432', description: 'The URL of the solution API server.', category: 'UI server' },
    { name: 'GLOW_EXTERNAL_API_URL', defaultValue: null, description: 'The URL of the GLOW API server in a form accessible to the user machine (for example, http://127.0.0.1:5432).\nEnables the access to the content of an entity handle or a file reference from the user machine (for example, from a browser).\n\nIn desktop deployments, it automatically takes the value of GLOW_API_URL. \nIn on-premises deployments, it is mandatory to set it because GLOW_API_URL contains a URL accessible only from within the UI container (for example, http://my-solution-api:50000).', category: 'UI server' },
    { name: 'GLOW_PORTAL_URL', defaultValue: null, description: 'The URL of the Portal server.', category: 'UI server' },
    { name: 'GLOW_UI_PROJECT_FILES_DIRECTORY', defaultValue: null, description: 'For deployments where the UI server is running in a different system than the GLOW API server. The absolute path to the project files directory that is shared with the GLOW API server in a form accessible to the UI server.', category: 'UI server' },
    { name: 'GLOW_WS_EVENTS_ADDR', defaultValue: 'ws://127.0.0.1:5432', description: 'The URL of the GLOW API server in a form accessible to the host machine (for example, http://127.0.0.1:5432) prefixed with the websocket protocol (for example, ws://127.0.0.1:5432 or wss://127.0.0.1:5432). Enables websockets created within Dash client to connect to the websocket endpoint within the GLOW API server.\n\nIn desktop deployments, automatically resolves from GLOW_API_URL.\nIn on-premises deployments, it is mandatory to set it because GLOW_API_URL contains a URL accessible only from within the UI container (for example, http://my-solution-api:50000).', category: 'UI server' },
    { name: 'GLOW_GRAPHQL_POOL_SIZE', defaultValue: '3', description: 'The number of available GraphQL clients that can be used concurrently.\n\n(DashClient is using GraphQL internally to communicate with the GLOW API. Therefore, a small pool size may impact the performance for a solution used by many concurrent users.)', category: 'UI server' },
    { name: 'GLOW_UI_MODULE', defaultValue: null, description: 'The module containing the UI\'s Dash application.\n\nUsed to specify the module when launching the UI application directly via a production server instead of GLOW\'s CLI.\n\nExample: ansys.solutions.my_solution.ui.app', category: 'UI server' },

    // Product Instance Manager
    { name: 'GLOW_PRODUCT_INSTANCE_SYSTEM_HOST', defaultValue: '127.0.0.1', description: 'The host where the Product Instance Manager system is running.', category: 'Product Instance Manager' },
    { name: 'GLOW_PRODUCT_INSTANCE_SYSTEM_PORT', defaultValue: null, description: 'The port where the Product Instance Manager system is running.', category: 'Product Instance Manager' },
    { name: 'GLOW_PRODUCT_INSTANCE_SYSTEM', defaultValue: 'PIM', description: 'The Product Instance Manager system to be used. Permitted values: PIM, HPS', category: 'Product Instance Manager', options: ['PIM', 'HPS'] },
    { name: 'GLOW_PRODUCT_HOST', defaultValue: null, description: 'The host where the product is running (not the manager system).\n\nFor HPS, must be set in the environment where the product instance is running, not in the GLOW API environment.\nFor PIM, set it in the GLOW API environment. Overrides the value retrieved automatically from the Product Instance Manager system.', category: 'Product Instance Manager' },
    { name: 'GLOW_PRODUCT_INSTANCE_SYSTEM_PROJECT_FILES_DIRECTORY', defaultValue: null, description: 'For deployments where the Product Instance Manager system is running in a different system than the GLOW API server. The absolute path to the project files directory that is shared with the GLOW API server in a form accessible to the product.', category: 'Product Instance Manager' },
    { name: 'GLOW_PRODUCT_INSTANCE_SYSTEM_PLATFORM', defaultValue: null, description: 'For deployments where the Product Instance Manager system is running in a different system than the GLOW API server. The platform type where the system is running.\n\nPermitted values: Windows, Linux', category: 'Product Instance Manager', options: ['Windows', 'Linux'] },

    // HPS System
    { name: 'GLOW_HPS_HOST', defaultValue: '127.0.0.1', description: 'The host where the HPS system is running.', category: 'HPS System' },
    { name: 'GLOW_HPS_PORT', defaultValue: null, description: 'The port where the HPS system is running.', category: 'HPS System' },

    // Authentication
    { name: 'GLOW_AUTH_ISSUER_URL', defaultValue: 'https://localhost:8443/hps/auth/realms/rep', description: 'The address of the Identity Provider (usually Keycloak) for authenticated access to the GLOW API.', category: 'Authentication' },
    { name: 'GLOW_AUTH_CLIENT_ID', defaultValue: 'rep-jms-web', description: 'The public oauth2 identifier of the solution API.\n\nExample: my-solution-api.', category: 'Authentication' },
    { name: 'GLOW_AUTH_DISABLED', defaultValue: false, description: 'Whether the API requires authorization or not.', category: 'Authentication' },

    // HPS Authentication
    { name: 'GLOW_HPS_CLIENT_ID', defaultValue: 'rep-jms-web', description: 'For Keycloak-based authentication, the client ID of the HPS system in Keycloak.', category: 'HPS Authentication' },
    { name: 'GLOW_HPS_KC_REALM', defaultValue: 'rep', description: 'For using Keycloak-based authentication, realm of the HPS system in Keycloak.', category: 'HPS Authentication' },
    { name: 'GLOW_HPS_KC_RELATIVE_PATH', defaultValue: 'hps/auth', description: 'For using Keycloak-based authentication, relative path to the authorization endpoint.', category: 'HPS Authentication' },
    { name: 'GLOW_HPS_USERNAME', defaultValue: null, description: 'For using username/password authentication, username to login to the HPS system. Example: repadmin', category: 'HPS Authentication' },
    { name: 'GLOW_HPS_PASSWORD', defaultValue: null, description: 'For using username/password authentication, password to login to the HPS system. Example: repadmin', category: 'HPS Authentication' },

    // Solution Configuration
    { name: 'GLOW_OVERWRITE_SOLUTION_CONFIG', defaultValue: null, description: 'To allow overwriting the persisted solution configuration when there is a version update.', category: 'Solution Configuration' },

    // Directories
    { name: 'GLOW_METHOD_EXECUTION_DIRECTORY', defaultValue: 'Subdirectory within the OS temporary directory', description: 'The full OS file system path to the directory for temporary method execution file spaces.', category: 'Directories' },
    { name: 'GLOW_PROJECT_FILES_DIRECTORY', defaultValue: '%APPDATA%/ansys/glow/SOLUTION_NAME/project_files/', description: 'The full OS file system path to the directory for storing the project files.', category: 'Directories' },

    // Transaction method files
    { name: 'GLOW_KEEP_TRANSACTION_FILES', defaultValue: false, description: 'Whether to keep the transaction method files after GLOW is shutdown.', category: 'Transaction method files' },

    // Database
    { name: 'GLOW_DATABASE_TYPE', defaultValue: 'sqlite', description: 'The type of database to be used. Permitted values: sqlite, postgresql', category: 'Database', options: ['sqlite', 'postgresql'] },
    { name: 'GLOW_DATABASE_LOCATION', defaultValue: '%APPDATA%/ansys/glow/SOLUTION_NAME/glow.db', description: 'The location of the database. It can be a file path (for sqlite) or a postgres connection URI.', category: 'Database' },

    // Data Repository
    { name: 'GLOW_DATA_REPOSITORY_TYPE', defaultValue: null, description: 'The type of data repository to be used. Permitted values: FileSystem (only for development), Minerva', category: 'Data Repository', options: ['FileSystem', 'Minerva'] },
    { name: 'GLOW_DATA_REPOSITORY_UPLOAD_ROOT', defaultValue: '/Data', description: 'The absolute path in the data repository to which a relative upload path is appended when uploading data.', category: 'Data Repository' },

    // Project Migration
    { name: 'GLOW_ENABLE_PROJECT_MIGRATION', defaultValue: false, description: 'Whether to activate automatic project migration. This environment variable should only be enabled for development, never in a production environment.', category: 'Project Migration' },

    // Telemetry
    { name: 'OTEL_EXPORTER_OTLP_ENDPOINT', defaultValue: null, description: 'The endpoint for the OTLP exporters (traces, logs, and metrics).', category: 'Telemetry' },
    { name: 'SAF_DESKTOP_LOG_TO_FILES', defaultValue: false, description: 'Log to files under $APPDATA/ansys/glow/<MySolution>/logs/ and disable OTEL dashboard. This option is mutually exclusive with OTEL_EXPORTER_OTLP_ENDPOINT: if both environment variables are set, an error will be raised. (Note that this sets the GLOW environment variables for log configuration files, overriding any existing value)', category: 'Telemetry' },

    // Logging
    { name: 'GLOW_LOG_CONFIG', defaultValue: null, description: 'The full OS file system path to the YAML logging configuration file for the API service.', category: 'Logging' },
    { name: 'GLOW_UI_LOG_CONFIG', defaultValue: null, description: 'The full OS file system path to the YAML logging configuration file for the UI service.', category: 'Logging' },
    { name: 'GLOW_METHOD_LOG_CONFIG', defaultValue: null, description: 'The full OS file system path to the YAML logging configuration file for the Method Runner.', category: 'Logging' },
    { name: 'GLOW_LOGGING_LEVEL', defaultValue: 'INFO', description: 'Logging level for ansys loggers. Overwrites values from log configurations.', category: 'Logging' },

    // Debugging
    { name: 'GLOW_DEBUG', defaultValue: false, description: 'Whether to enable debugging in GLOW.', category: 'Debugging' },
    { name: 'GLOW_API_HOT_RELOAD', defaultValue: true, description: 'Whether to enable API hot reload. Only works if debug mode is activated.', category: 'Debugging' },
    { name: 'GLOW_UI_PYTHON_DEBUGGING', defaultValue: false, description: 'Whether to enable python debugging in GLOW UI.', category: 'Debugging' },
    { name: 'GLOW_DEBUG_API_PORT', defaultValue: '5724', description: 'The Python debugger port for the GLOW API service.', category: 'Debugging' },
    { name: 'GLOW_DEBUG_UI_PORT', defaultValue: '5725', description: 'The Python debugger port for the GLOW UI service.', category: 'Debugging' },
    { name: 'PORTAL_ENABLE_DEBUG', defaultValue: false, description: 'Whether to enable debugging in Portal.', category: 'Debugging' },

    // Services
    { name: 'SAF_DESKTOP_HEALTH_CHECK_TIMEOUT', defaultValue: '25 seconds', description: 'Specifies the maximum duration (in seconds) to wait for a service (for example, API, UI, Portal, or PIM) to become healthy after it has been started.', category: 'Services' },

    // Portal API
    { name: 'PORTAL_API_VERSION', defaultValue: 'v1', description: 'API version of Portal used to communicate with it.', category: 'Portal API' },

    // Portal UI
    { name: 'PORTAL_UI_HOST', defaultValue: '127.0.0.1', description: 'The host where the Portal UI server will be running.', category: 'Portal UI' },
    { name: 'PORTAL_UI_PORT', defaultValue: null, description: 'The port where the Portal UI server will be running.', category: 'Portal UI' },

    // Deployment
    { name: 'GLOW_DEPLOYMENT', defaultValue: 'Desktop', description: 'The deployment GLOW is running in. Permitted values: Desktop, DockerCompose', category: 'Deployment', options: ['Desktop', 'DockerCompose'] },
];
