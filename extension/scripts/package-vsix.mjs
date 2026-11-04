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

// Stages the compiled extension in .vsix-staging/ and packages it into dist/.
// The user guide (extension-instructions.md) is staged as README.md so the developer README is never packaged.

import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createVSIX, listFiles, PackageManager } from '@vscode/vsce';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const staging = join(root, '.vsix-staging');
const distDir = join(root, 'dist');

const manifest = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));
const vsixPath = join(distDir, `${manifest.name}-${manifest.version}.vsix`);

for (const required of ['out/extension.js', 'out/webview', 'saf-logo.png', 'LICENSE', 'CHANGELOG.md', 'extension-instructions.md']) {
  if (!existsSync(join(root, required))) {
    throw new Error(`Missing ${required}. Run "npm run compile" first.`);
  }
}

rmSync(staging, { recursive: true, force: true });
mkdirSync(staging, { recursive: true });
mkdirSync(distDir, { recursive: true });
rmSync(vsixPath, { force: true });

// vsce rejects "files" combined with .vscodeignore, and "scripts" would run vscode:prepublish in staging.
const { scripts, devDependencies, overrides, files, ...stagedManifest } = manifest;
writeFileSync(join(staging, 'package.json'), JSON.stringify(stagedManifest, null, 2) + '\n', 'utf8');

// Only the bundle and webview assets: tsc also emits out/src and out/test, which must not ship.
mkdirSync(join(staging, 'out'), { recursive: true });
cpSync(join(root, 'out', 'extension.js'), join(staging, 'out', 'extension.js'));
cpSync(join(root, 'out', 'webview'), join(staging, 'out', 'webview'), { recursive: true });
for (const file of ['saf-logo.png', 'LICENSE', 'CHANGELOG.md', '.vscodeignore']) {
  cpSync(join(root, file), join(staging, file));
}
cpSync(join(root, 'extension-instructions.md'), join(staging, 'README.md'));

const included = (await listFiles({ cwd: staging, packageManager: PackageManager.None })).map((f) => f.replaceAll('\\', '/'));
const expected = [
  'package.json',
  'README.md',
  'LICENSE',
  'CHANGELOG.md',
  'saf-logo.png',
  'out/extension.js',
  'out/webview/styles/common.css',
  ...['archiveSolution', 'buildInstaller', 'solutionRun'].flatMap((name) => [
    `out/webview/templates/${name}.html`,
    `out/webview/scripts/${name}.js`,
  ]),
];
const missing = expected.filter((f) => !included.some((i) => i.toLowerCase() === f.toLowerCase()));
if (missing.length > 0) {
  throw new Error(`VSIX file list is missing: ${missing.join(', ')}`);
}

await createVSIX({ cwd: staging, packagePath: vsixPath, dependencies: false });
console.log(`Created ${vsixPath}`);
