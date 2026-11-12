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


import { createInstrumenter } from 'istanbul-lib-instrument';
import { readdirSync, readFileSync, writeFileSync, statSync } from 'node:fs';
import { join, extname } from 'node:path';

const instrumenter = createInstrumenter({
  esModules: false,
  compact: false,
  produceSourceMap: true,
  autoWrap: false,
  preserveComments: true
});

function instrumentDir(dir) {
  for (const entry of readdirSync(dir)) {
    const fullPath = join(dir, entry);
    const stat = statSync(fullPath);

    if (stat.isDirectory()) {
      if (entry === 'test') continue;
      instrumentDir(fullPath);
    } else if (extname(entry) === '.js') {
      const code = readFileSync(fullPath, 'utf8');
      try {
        const instrumented = instrumenter.instrumentSync(code, fullPath);
        writeFileSync(fullPath, instrumented);
      } catch (e) {
        console.warn(`[instrument] Skipped ${fullPath}: ${e.message}`);
      }
    }
  }
}

const outDir = new URL('../out', import.meta.url).pathname.replace(/^\/([A-Z]:)/, '$1');
console.log(`[instrument] Instrumenting files in ${outDir}`);
instrumentDir(outDir);
console.log('[instrument] Done.');
