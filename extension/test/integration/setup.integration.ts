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


import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import * as vscode from 'vscode';
import { CommandContext } from '../../src/managers/CommandManager';
import { systemService } from '../../src/services/SystemService';
import { StorageService } from '../../src/services/StorageService';
import { MinimalMockExtensionContext } from '../mocks/vscode.minimal';

const repoRoot = path.resolve(__dirname, '..', '..', '..');
// Use a location with a space on the path to ensure we are correctly handling those cases in our tests
const sharedStorageRoot = path.join(os.tmpdir(), 'saf-solutions-manager-test storage');

function getSafCliDbPath(): string {
  if (process.platform === 'win32') {
    const appData = process.env.APPDATA;
    if (!appData) {
      throw new Error('APPDATA environment variable is not set');
    }
    return path.join(appData, 'ansys', 'saf', 'cli', 'solution_db.json');
  } else {
    const dataHome = process.env.XDG_DATA_HOME || path.join(os.homedir(), '.local', 'share');
    return path.join(dataHome, 'ansys', 'saf', 'cli', 'solution_db.json');
  }
}

const dbPath = getSafCliDbPath();
const backupPath = path.join(sharedStorageRoot, 'solution_db.backup.json');
let dbBackedUp = false;

export const mockExtensionContext = new MinimalMockExtensionContext();
mockExtensionContext.extensionPath = repoRoot;
mockExtensionContext.extensionUri = vscode.Uri.file(repoRoot) as any;
mockExtensionContext.globalStorageUri = vscode.Uri.file(sharedStorageRoot) as any;
mockExtensionContext.globalStoragePath = sharedStorageRoot;
mockExtensionContext.storagePath = path.join(sharedStorageRoot, 'workspace');
mockExtensionContext.logPath = path.join(sharedStorageRoot, 'logs');
mockExtensionContext.logUri = vscode.Uri.file(mockExtensionContext.logPath) as any;
const globalStateStore = new Map<string, unknown>();
mockExtensionContext.globalState.get = ((key: string) => globalStateStore.get(key)) as any;
mockExtensionContext.globalState.update = (async (key: string, value: unknown) => {
  if (typeof value === 'undefined') {
    globalStateStore.delete(key);
  } else {
    globalStateStore.set(key, value);
  }
}) as any;

export function createTempTestDir(): string {
  const parentDir = path.join(os.tmpdir(), 'solutions-manager-test');
  fs.mkdirSync(parentDir, { recursive: true });
  return fs.mkdtempSync(path.join(parentDir, 'saf-test-'));
}

export function generateUniqueSolutionName(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

export function generateUniqueNamespace(): string {
  const prefixes = ['demo', 'sample', 'example'];
  const prefix = prefixes[Math.floor(Math.random() * prefixes.length)];
  const uniqueSegment = `ns${Date.now()}${Math.random().toString(36).slice(2, 7)}`;
  return `${prefix}.${uniqueSegment}.solutions`;
}


export function createMockCommandContext(
  tempDir: string,
  extensionContext: vscode.ExtensionContext = mockExtensionContext
): CommandContext {
  return {
    extensionContext,
    workspaceRoot: tempDir
  };
}

let safCliInstalled = false;

export async function mochaGlobalSetup() {
  if (safCliInstalled) {
    return;
  }

  fs.mkdirSync(sharedStorageRoot, { recursive: true });
  fs.mkdirSync(mockExtensionContext.logPath, { recursive: true });
  fs.mkdirSync(mockExtensionContext.storagePath, { recursive: true });

  if (fs.existsSync(dbPath)) {
    fs.copyFileSync(dbPath, backupPath);
    dbBackedUp = true;
  }

  new StorageService(mockExtensionContext as unknown as vscode.ExtensionContext);
  systemService.setContext(mockExtensionContext as unknown as vscode.ExtensionContext);
  await systemService.handleSAFCliInstallation();
  safCliInstalled = true;
}

export async function mochaGlobalTeardown() {
  if (dbBackedUp && fs.existsSync(backupPath)) {
    fs.copyFileSync(backupPath, dbPath);
    fs.unlinkSync(backupPath);
    dbBackedUp = false;
  } else if (fs.existsSync(dbPath)) {
    fs.unlinkSync(dbPath);
  }

  // Dump V8/Istanbul coverage collected during the integration test run
  const coverage = (globalThis as any).__coverage__;
  if (coverage) {
    const outputDir = path.resolve(__dirname, '../../../.nyc_output');
    fs.mkdirSync(outputDir, { recursive: true });
    const outputFile = path.join(outputDir, `integration-${Date.now()}.json`);
    fs.writeFileSync(outputFile, JSON.stringify(coverage));
    console.log(`[coverage] Integration coverage written to ${outputFile}`);
  } else {
    console.log('[coverage] No __coverage__ global found, code not instrumented.');
  }
}
