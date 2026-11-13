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

import * as path from 'node:path';
import * as fs from 'node:fs';
import * as childProcess from 'node:child_process';
import { expect } from 'chai';
import { SolutionService } from '../../src/services/SolutionService';
import { StorageService } from '../../src/services/StorageService';
import { createTempTestDir, generateUniqueNamespace, generateUniqueSolutionName } from './setup.integration';

export async function createTestSolution(prefix: string, displayName: string) {
  const tempDir = createTempTestDir();
  const solutionName = generateUniqueSolutionName(prefix);
  const namespace = generateUniqueNamespace();

  const solutionService = new SolutionService();
  await solutionService.createSolution({
    name: solutionName,
    displayName,
    uiType: 'dash',
    namespace: namespace,
    targetDirectory: tempDir
  });

  const createdSolutionPath = path.join(tempDir, solutionName);
  expect(fs.existsSync(createdSolutionPath)).to.be.true;

  return { solutionName, createdSolutionPath };
}

export async function installTestSolutionEnv(solutionName: string, solutionPath: string, timeoutMs: number = 240000): Promise<void> {
  const safCliExecutablePath = StorageService.getSafCliExecutablePath();

  await new Promise<void>((resolve, reject) => {
    const proc = childProcess.spawn(safCliExecutablePath, ['install', solutionName], {
      cwd: solutionPath,
      stdio: 'ignore'
    });

    const timer = setTimeout(() => {
      proc.kill('SIGKILL');
      reject(new Error(`saf install timed out after ${timeoutMs}ms`));
    }, timeoutMs);

    proc.on('error', (err) => {
      clearTimeout(timer);
      reject(err);
    });

    proc.on('close', (code, signal) => {
      clearTimeout(timer);
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`saf install exited with code ${code} (signal: ${signal})`));
      }
    });
  });
}

function runCommand(executable: string, args: string[], cwd: string, timeoutMs: number): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const proc = childProcess.spawn(executable, args, { cwd, stdio: ['ignore', 'pipe', 'pipe'] });

    let output = '';
    proc.stdout?.on('data', (chunk) => { output += chunk; });
    proc.stderr?.on('data', (chunk) => { output += chunk; });

    const timer = setTimeout(() => {
      proc.kill('SIGKILL');
      reject(new Error(`${executable} ${args.join(' ')} timed out after ${timeoutMs}ms\n${output}`));
    }, timeoutMs);

    proc.on('error', (err) => {
      clearTimeout(timer);
      reject(err);
    });

    proc.on('close', (code, signal) => {
      clearTimeout(timer);
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`${executable} ${args.join(' ')} exited with code ${code} (signal: ${signal})\n${output}`));
      }
    });
  });
}

/**
 * Creates a bare `.venv` in the given solution directory and installs Poetry into it,
 * WITHOUT running the full `saf install` (which also installs the solution's
 * desktop/ui/doc/build dependency groups that are unnecessary for most tests and take
 * several minutes). `saf add-step` only requires a `poetry` executable to be present at
 * `.venv/Scripts/poetry.exe` (or `.venv/bin/poetry`) to install a non-default template's
 * own dependencies; it runs `poetry lock`/`poetry install` itself for those.
 */
export async function createSolutionVenvWithPoetry(solutionPath: string, timeoutMs: number = 120000): Promise<void> {
  await runCommand('uv', ['venv', '.venv', '--seed'], solutionPath, timeoutMs);

  const venvPythonExecutable = process.platform === 'win32'
    ? path.join(solutionPath, '.venv', 'Scripts', 'python.exe')
    : path.join(solutionPath, '.venv', 'bin', 'python');

  await runCommand(venvPythonExecutable, ['-m', 'pip', 'install', 'poetry>=2,<3'], solutionPath, timeoutMs);
}
