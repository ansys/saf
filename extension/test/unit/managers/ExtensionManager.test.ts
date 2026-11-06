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


import { strict as assert } from 'assert';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

describe('ExtensionManager - Panel Visibility Tests', () => {
    const packageJson = JSON.parse(readFileSync(join(process.cwd(), 'package.json'), 'utf8'));

    it('package.json should define correct default panel visibility settings', () => {
        const propertiesConfig = packageJson.contributes.configuration.properties;

        assert.strictEqual(
            propertiesConfig['solutions-manager.enableSolutionsList'].default,
            true,
            'Solutions List panel should be enabled by default in package.json'
        );
    });
});