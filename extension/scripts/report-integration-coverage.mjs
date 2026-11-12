// Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
// SPDX-License-Identifier: Apache-2.0

// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at

//     http://www.apache.org/licenses/LICENSE-2.0

// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.


import coverageLib from 'istanbul-lib-coverage';
import reportLib from 'istanbul-lib-report';
import reportersLib from 'istanbul-reports';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const nycOutputDir = resolve(__dirname, '../.nyc_output');
const reportsDir = resolve(__dirname, '../coverage/integration');

if (!existsSync(nycOutputDir)) {
  console.warn(`[coverage] No coverage data found at ${nycOutputDir}`);
  console.warn('[coverage] Skipping integration coverage report generation.');
  process.exit(0);
}

// Merge all Istanbul JSON files from .nyc_output
const coverageMap = coverageLib.createCoverageMap({});

for (const file of readdirSync(nycOutputDir)) {
  if (!file.startsWith('integration-') || !file.endsWith('.json')) continue;
  const filePath = join(nycOutputDir, file);
  const raw = JSON.parse(readFileSync(filePath, 'utf8'));
  coverageMap.merge(raw);
}

const context = reportLib.createContext({
  dir: reportsDir,
  coverageMap,
  watermarks: {
    statements: [50, 80],
    branches: [50, 80],
    functions: [50, 80],
    lines: [50, 80]
  },
  sourceFinder: (filePath) => {
    try {
      return readFileSync(filePath, 'utf8');
    } catch (err) {
      console.warn(`[sourceFinder] Could not read ${filePath}: ${err.message}`);
      return '';
    }
  }
});

for (const reporter of ['html', 'lcov']) {
  reportersLib.create(reporter).execute(context);
}

reportersLib.create('text').execute(context);
reportersLib.create('text-summary').execute(context);

console.log(`[coverage] Integration report written to ${reportsDir}`);
