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


import * as sinon from 'sinon';
import { createMockVSCode } from './mocks/vscode.mock';

/**
 * Global test setup file
 * This file is loaded before all tests run
 */

// Mock the vscode module globally for all tests
// This is required because many of our source files import 'vscode'
// but unit tests run in Node.js where the vscode module doesn't exist
const mockVSCode = createMockVSCode();

// Use require.cache to inject our mock before any real imports happen
const Module = require('module');
const originalRequire = Module.prototype.require;

Module.prototype.require = function (id: string) {
  if (id === 'vscode') {
    return mockVSCode;
  }
  return originalRequire.apply(this, arguments as any);
};

process.env.MOCHA_TIMEOUT = '90000'; // give some time to install SAF CLI

export const mochaHooks = {
  // Runs before each test
  beforeEach() {
  },

  // Runs after each test
  afterEach() {
    sinon.restore();
  },

  // Runs after all tests complete
  afterAll() {
  }
};

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});
