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

// Fails if a production npm dependency uses a license outside the allowlist.

import { execSync } from 'node:child_process';

const ALLOWED = new Set(['MIT', 'ISC', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', '0BSD']);

const output = execSync('npm query .prod', { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });

// Flat SPDX expressions only: "A OR B" needs one allowed license, "A AND B" needs all of them.
function isAllowed(expression) {
  const flat = expression.replace(/[()]/g, ' ').trim();
  if (/\sAND\s/.test(flat)) {
    return flat.split(/\s+AND\s+/).every((part) => isAllowed(part));
  }
  return flat.split(/\s+OR\s+/).some((part) => ALLOWED.has(part.trim()));
}

const violations = JSON.parse(output)
  .map((pkg) => ({ name: pkg.name, version: pkg.version, license: typeof pkg.license === 'string' ? pkg.license : '' }))
  .filter((pkg) => !pkg.license || !isAllowed(pkg.license));

if (violations.length > 0) {
  for (const { name, version, license } of violations) {
    console.error(`${name}@${version}: license '${license || 'unknown'}' is not in the allowlist`);
  }
  process.exit(1);
}
console.log(`All production dependency licenses are allowed (${[...ALLOWED].join(', ')}).`);
