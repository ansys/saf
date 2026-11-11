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

import { expect } from 'chai';
import * as sinon from 'sinon';
import * as vscode from 'vscode';
import * as path from 'node:path';
import * as fs from 'node:fs';
import { SolutionRegistrationService, solutionRegistrationService } from '../../../src/services/SolutionRegistrationService';
import { SAFSolutionsProvider } from '../../../src/providers/SAFSolutionsProvider';
import { StorageService } from '../../../src/services/StorageService';
import { createTempTestDir } from '../setup.integration';
import { createTestSolution } from '../testHelpers';

describe('SolutionRegistrationService Integration Tests', function () {
  let showInformationMessageStub: sinon.SinonStub;
  let withProgressStub: sinon.SinonStub;

  beforeEach(() => {
    showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage');
    sinon.stub(vscode.window, 'showWarningMessage');
    sinon.stub(vscode.window, 'showErrorMessage');
    sinon.stub(vscode.commands, 'executeCommand');
    withProgressStub = sinon.stub(vscode.window, 'withProgress');
    withProgressStub.callsFake(async (_options, task) => {
      return await task({ report: () => {} }, {} as any);
    });
  });

  afterEach(() => {
    sinon.restore();
  });

  describe('registerSolution', () => {
    it('should register a newly created solution and verify via getSAFSolutions', async function () {
        const { solutionName, createdSolutionPath: solutionPath } = await createTestSolution('reg-test', 'Registration Test Solution');

        showInformationMessageStub.resolves('Don\'t open');

        const service = new SolutionRegistrationService();
        const result = await service.registerSolution(solutionPath, solutionPath, true);

        expect(result).to.not.be.undefined;
        expect(result?.name).to.equal(solutionName);

        const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();
        const foundSolution = solutions.find(s => s.name === solutionName);
        expect(foundSolution).to.not.be.undefined;
        expect(foundSolution?.displayName).to.equal('Registration Test Solution');

        const selectedSolution = StorageService.getSelectedSolution(solutionPath);
        expect(selectedSolution?.name).to.equal(solutionName);
    });
  });

  describe('checkAndRegisterWorkspaceSolution', () => {
    it('should clear selection for invalid workspace', async function () {
        const tempDir = createTempTestDir();

        const invalidDir = path.join(tempDir, 'not-a-solution');
        fs.mkdirSync(invalidDir, { recursive: true });

        await solutionRegistrationService.checkAndRegisterWorkspaceSolution(invalidDir);

        const selectedSolution = StorageService.getSelectedSolution(invalidDir);
        expect(selectedSolution).to.be.undefined;
    });
  });
});