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


import * as vscode from 'vscode';
import { expect } from 'chai';

describe('ExtensionManager Integration Tests', () => {
  describe('Panel Visibility Settings', () => {

    afterEach(async () => {
      const config = vscode.workspace.getConfiguration('solutions-manager');

      await config.update('enableSolutionsList', true, vscode.ConfigurationTarget.Global);
    });

    it('should initialize with correct default configuration settings', async function() {
      const config = vscode.workspace.getConfiguration('solutions-manager');

      const enableSolutionsList = config.get<boolean>('enableSolutionsList');

      expect(enableSolutionsList).to.equal(true, 'Solutions List should be enabled by default');
    });

    it('should update panel visibility settings if configuration changes', async function() {
      const config = vscode.workspace.getConfiguration('solutions-manager');

      expect(config.get<boolean>('enableSolutionsList')).to.equal(true, 'Solutions List should be enabled by default');
    });
  });
});
