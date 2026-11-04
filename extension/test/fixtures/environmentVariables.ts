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


/**
 * Test fixtures for environment variables used in ConfigurationPanel
 */

import { ENVIRONMENT_VARIABLE_DEFINITIONS } from '../../src/services/environmentVariables';
import { EnvironmentVariableState } from '../../src/types/solution';

/**
 * Expected default environment variables that should be initialized
 * in ConfigurationPanel. Derived from the single source of truth.
 */
export const expectedEnvironmentVariables: EnvironmentVariableState[] =
    ENVIRONMENT_VARIABLE_DEFINITIONS.map(def => ({
        ...def,
        enabled: false,
        value: def.defaultValue,
    }));