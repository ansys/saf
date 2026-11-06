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
import { SolutionRegistrationService } from '../../../src/services/SolutionRegistrationService';
import { SAFSolutionsProvider } from '../../../src/providers/SAFSolutionsProvider';
import { StorageService, SelectedSolution } from '../../../src/services/StorageService';
import * as workspaceUtils from '../../../src/utils/workspaceUtils';
import * as execModule from '../../../src/utils/exec';

describe('SolutionRegistrationService', () => {
  let service: SolutionRegistrationService;
  let getSAFSolutionsStub: sinon.SinonStub;
  let safSolutionsProviderStub: sinon.SinonStubbedInstance<SAFSolutionsProvider>;
  let getWorkspaceSolutionInfoStub: sinon.SinonStub;
  let isValidSolutionWorkspaceStub: sinon.SinonStub;
  let setSelectedSolutionStub: sinon.SinonStub;
  let getSafCliExecutableCommandStub: sinon.SinonStub;
  let execAsyncStub: sinon.SinonStub;
  let showInformationMessageStub: sinon.SinonStub;
  let showWarningMessageStub: sinon.SinonStub;
  let showErrorMessageStub: sinon.SinonStub;
  let executeCommandStub: sinon.SinonStub;
  let withProgressStub: sinon.SinonStub;

  const mockSolutionInfo: SelectedSolution = {
    name: 'test_solution',
    displayName: 'Test Solution',
    path: '/test/path'
  };

  beforeEach(() => {
    service = new SolutionRegistrationService();

    // SAFSolutionsProvider mocks
    safSolutionsProviderStub = sinon.createStubInstance(SAFSolutionsProvider);
    getSAFSolutionsStub = safSolutionsProviderStub.getSAFSolutions as sinon.SinonStub;
    getSAFSolutionsStub.resolves([]);
    sinon.stub(SAFSolutionsProvider, 'getInstance').returns(safSolutionsProviderStub);

    // WorkspaceUtils mocks
    getWorkspaceSolutionInfoStub = sinon.stub(workspaceUtils, 'getWorkspaceSolutionInfo');
    isValidSolutionWorkspaceStub = sinon.stub(workspaceUtils, 'isValidSolutionWorkspace');

    // StorageService mocks
    setSelectedSolutionStub = sinon.stub(StorageService, 'setSelectedSolution');
    getSafCliExecutableCommandStub = sinon.stub(StorageService, 'getSafCliExecutableCommand');
    getSafCliExecutableCommandStub.returns('/test/bin/saf');

    // Exec mocks
    execAsyncStub = sinon.stub(execModule, 'execAsync');

    // VS Code mocks (reuse pre-stubbed global mocks)
    showInformationMessageStub = vscode.window.showInformationMessage as sinon.SinonStub;
    showInformationMessageStub.reset();
    showWarningMessageStub = vscode.window.showWarningMessage as sinon.SinonStub;
    showWarningMessageStub.reset();
    showErrorMessageStub = vscode.window.showErrorMessage as sinon.SinonStub;
    showErrorMessageStub.reset();
    executeCommandStub = vscode.commands.executeCommand as sinon.SinonStub;
    executeCommandStub.reset();
    withProgressStub = vscode.window.withProgress as sinon.SinonStub;
    withProgressStub.reset();
    withProgressStub.callsFake(async (_options, task) => {
      return await task({ report: () => {} }, {} as any);
    });
  });

  afterEach(() => {
    sinon.restore();
  });

  describe('waitForSolutionRegistration (private)', () => {
    it('should return true when solution is found on first attempt', async () => {
      getSAFSolutionsStub.resolves([
        { name: 'test_solution', rootDirectory: '/test', displayName: 'Test' }
      ]);

      const result = await (service as any).waitForSolutionRegistration('test_solution', 1, 100);

      expect(result).to.be.true;
      expect(getSAFSolutionsStub.callCount).to.equal(1);
    });

    it('should return true when solution is found after retries', async () => {
      getSAFSolutionsStub.onFirstCall().resolves([]);
      getSAFSolutionsStub.onSecondCall().resolves([
        { name: 'test_solution', rootDirectory: '/test', displayName: 'Test' }
      ]);

      const result = await (service as any).waitForSolutionRegistration('test_solution', 3, 50);

      expect(result).to.be.true;
      expect(getSAFSolutionsStub.callCount).to.equal(2);
    });

    it('should return false after max retries with no match', async () => {
      getSAFSolutionsStub.resolves([]);

      const result = await (service as any).waitForSolutionRegistration('test_solution', 2, 50);

      expect(result).to.be.false;
      expect(getSAFSolutionsStub.callCount).to.equal(2);
    });

    it('should handle case-insensitive matching with normalized dashes/underscores', async () => {
      getSAFSolutionsStub.resolves([
        { name: 'test-solution', rootDirectory: '/test', displayName: 'Test' }
      ]);

      const result = await (service as any).waitForSolutionRegistration('test_solution', 1, 100);

      expect(result).to.be.true;
    });

    it('should handle errors from getSAFSolutions gracefully', async () => {
      getSAFSolutionsStub.rejects(new Error('SAF CLI error'));

      const result = await (service as any).waitForSolutionRegistration('test_solution', 2, 50);

      expect(result).to.be.false;
    });
  });

  describe('registerSolution - Already Registered', () => {
    beforeEach(() => {
      getWorkspaceSolutionInfoStub.resolves(mockSolutionInfo);
    });

    it('should return existing solution info if already registered', async () => {
      const result = await service.registerSolution('/test/path', '/workspace', true);

      expect(result).to.deep.equal(mockSolutionInfo);
      expect(execAsyncStub.called).to.be.false;
    });

    it('should call setSelectedSolution when autoSelect=true', async () => {
      await service.registerSolution('/test/path', '/workspace', true);

      expect(setSelectedSolutionStub.calledOnceWith('/workspace', mockSolutionInfo)).to.be.true;
    });

    it('should not call setSelectedSolution when autoSelect=false', async () => {
      await service.registerSolution('/test/path', '/workspace', false);

      expect(setSelectedSolutionStub.called).to.be.false;
    });
  });

  describe('registerSolution - Invalid Workspace', () => {
    beforeEach(() => {
      getWorkspaceSolutionInfoStub.resolves(undefined);
      isValidSolutionWorkspaceStub.returns(false);
    });

    it('should throw error when isValidSolutionWorkspace returns false', async () => {
      try {
        await service.registerSolution('/invalid/path', '/workspace', true);
        expect.fail('Should have thrown an error');
      } catch (error: any) {
        expect(error.message).to.equal('The selected directory is not a valid solution workspace.');
      }
    });
  });

  describe('registerSolution - Successful Registration', () => {
    beforeEach(() => {
      getWorkspaceSolutionInfoStub.onFirstCall().resolves(undefined);
      getWorkspaceSolutionInfoStub.onSecondCall().resolves(mockSolutionInfo);
      isValidSolutionWorkspaceStub.returns(true);
      execAsyncStub.resolves();
      getSAFSolutionsStub.resolves([
        { name: 'test_solution', rootDirectory: '/test/path', displayName: 'Test Solution' }
      ]);
    });

    it('should execute saf command with correct path', async () => {
      await service.registerSolution('/test/path', '/workspace', true);

      expect(execAsyncStub.calledOnce).to.be.true;
      expect(execAsyncStub.firstCall.args[0]).to.include('execute');
      expect(execAsyncStub.firstCall.args[0]).to.include('/test/path');
      expect(execAsyncStub.firstCall.args[0]).to.include('python --version');
    });

    it('should wait for registration polling and find solution', async () => {
      const result = await service.registerSolution('/test/path', '/workspace', true);

      expect(result).to.deep.equal(mockSolutionInfo);
      expect(getSAFSolutionsStub.called).to.be.true;
    });

    it('should set selected solution when autoSelect=true', async () => {
      await service.registerSolution('/test/path', '/workspace', true);

      expect(setSelectedSolutionStub.calledWith('/workspace', mockSolutionInfo)).to.be.true;
    });

    it('should not set selected solution when autoSelect=false', async () => {
      getWorkspaceSolutionInfoStub.onFirstCall().resolves(undefined);
      getWorkspaceSolutionInfoStub.onSecondCall().resolves(mockSolutionInfo);
      getSAFSolutionsStub.resolves([
        { name: 'test_solution', rootDirectory: '/test/path', displayName: 'Test Solution' }
      ]);

      await service.registerSolution('/test/path', '/workspace', false);

      expect(setSelectedSolutionStub.called).to.be.false;
    });

    it('should call refresh on SAFSolutionsProvider', async () => {
      await service.registerSolution('/test/path', '/workspace', true);

      expect(safSolutionsProviderStub.refresh.calledOnce).to.be.true;
    });

    it('should show success message', async () => {
      await service.registerSolution('/test/path', '/workspace', true);

      expect(showInformationMessageStub.calledWith('Solution "test_solution" registered successfully.')).to.be.true;
    });
  });

  describe('registerSolution - Registration Failure', () => {
    beforeEach(() => {
      getWorkspaceSolutionInfoStub.onFirstCall().resolves(undefined);
      getWorkspaceSolutionInfoStub.onSecondCall().resolves(mockSolutionInfo);
      isValidSolutionWorkspaceStub.returns(true);
      showWarningMessageStub.resolves('No');
    });

    it('should show warning message on execAsync error', async () => {
      execAsyncStub.rejects(new Error('Registration failed'));

      const result = await service.registerSolution('/test/path', '/workspace', true);

      expect(showWarningMessageStub.called).to.be.true;
      expect(result).to.be.undefined;
    });

    it('should show specific message for "python not found" error', async () => {
      execAsyncStub.rejects(new Error('Executable \'python\' not found in solution'));

      await service.registerSolution('/test/path', '/workspace', true);

      expect(showWarningMessageStub.firstCall.args[0]).to.include('development environment for the solution is not installed');
    });

    it('should set solution anyway when autoSelect=true (even on error)', async () => {
      execAsyncStub.rejects(new Error('Registration failed'));

      await service.registerSolution('/test/path', '/workspace', true);

      expect(setSelectedSolutionStub.calledWith('/workspace', mockSolutionInfo)).to.be.true;
    });

    it('should prompt user for dev environment installation', async () => {
      execAsyncStub.rejects(new Error('Registration failed'));

      await service.registerSolution('/test/path', '/workspace', true);

      expect(showWarningMessageStub.calledWith(
        sinon.match.string,
        'Yes', 'No'
      )).to.be.true;
    });

    it('should execute installDevEnvironment command when user clicks "Yes"', async () => {
      execAsyncStub.rejects(new Error('Registration failed'));
      showWarningMessageStub.resolves('Yes');
      executeCommandStub.resolves();

      await service.registerSolution('/test/path', '/workspace', true);

      expect(withProgressStub.called).to.be.true;

      await withProgressStub.returnValues[0];
      expect(executeCommandStub.calledWith('solutions-manager.installDevEnvironment')).to.be.true;
    });

    it('should return undefined on error', async () => {
      execAsyncStub.rejects(new Error('Registration failed'));

      const result = await service.registerSolution('/test/path', '/workspace', true);

      expect(result).to.be.undefined;
    });
  });

  describe('checkAndRegisterWorkspaceSolution', () => {
    it('should set selected solution if already registered', async () => {
      getWorkspaceSolutionInfoStub.resolves(mockSolutionInfo);

      await service.checkAndRegisterWorkspaceSolution('/test/path');

      expect(setSelectedSolutionStub.calledOnceWith('/test/path', mockSolutionInfo)).to.be.true;
      expect(isValidSolutionWorkspaceStub.called).to.be.false;
    });

    it('should call registerSolution if valid but not registered', async () => {
      getWorkspaceSolutionInfoStub.onFirstCall().resolves(undefined);
      getWorkspaceSolutionInfoStub.onSecondCall().resolves(undefined);
      getWorkspaceSolutionInfoStub.onThirdCall().resolves(mockSolutionInfo);
      isValidSolutionWorkspaceStub.returns(true);
      execAsyncStub.resolves();
      getSAFSolutionsStub.resolves([{ name: 'test_solution', rootDirectory: '/test/path', displayName: 'Test' }]);

      await service.checkAndRegisterWorkspaceSolution('/test/path');

      expect(execAsyncStub.called).to.be.true;
      expect(isValidSolutionWorkspaceStub.calledWith('/test/path')).to.be.true;
    });

    it('should clear selection if invalid workspace', async () => {
      getWorkspaceSolutionInfoStub.resolves(undefined);
      isValidSolutionWorkspaceStub.returns(false);

      await service.checkAndRegisterWorkspaceSolution('/test/path');

      expect(setSelectedSolutionStub.calledOnceWith('/test/path', undefined)).to.be.true;
    });

    it('should show error message on exception', async () => {
      getWorkspaceSolutionInfoStub.rejects(new Error('Test error'));

      await service.checkAndRegisterWorkspaceSolution('/test/path');

      expect(showErrorMessageStub.calledWith(
        'An error occurred while trying to register the workspace solution: Test error'
      )).to.be.true;
    });
  });

  describe('recursive workspace discovery behavior (workspaceUtils-driven)', () => {
  it('should short-circuit registration when recursively discovered solution is already registered', async () => {
    const recursiveSolutionInfo: SelectedSolution = {
      name: 'deep_solution',
      displayName: 'Deep Solution',
      path: '/repo'
    };

    getWorkspaceSolutionInfoStub.resolves(recursiveSolutionInfo);

    const result = await service.registerSolution('/repo', '/workspace', true);

    expect(result).to.deep.equal(recursiveSolutionInfo);
    expect(isValidSolutionWorkspaceStub.called).to.be.false;
    expect(execAsyncStub.called).to.be.false;
    expect(setSelectedSolutionStub.calledOnceWith('/workspace', recursiveSolutionInfo)).to.be.true;
  });

  it('should complete registration when recursive discovery finds solution after saf execute', async () => {
    const recursiveSolutionInfo: SelectedSolution = {
      name: 'team_solution',
      displayName: 'Team Solution',
      path: '/repo'
    };

    // before execute: not registered yet; after execute: discovered via recursive lookup
    getWorkspaceSolutionInfoStub.onFirstCall().resolves(undefined);
    getWorkspaceSolutionInfoStub.onSecondCall().resolves(recursiveSolutionInfo);

    isValidSolutionWorkspaceStub.returns(true);
    execAsyncStub.resolves();

    // waitForSolutionRegistration normalizes dash/underscore
    getSAFSolutionsStub.resolves([
      { name: 'team-solution', rootDirectory: '/repo', displayName: 'Team Solution' }
    ]);

    const result = await service.registerSolution('/repo', '/workspace', true);

    expect(result).to.deep.equal(recursiveSolutionInfo);
    expect(execAsyncStub.calledOnce).to.be.true;
    expect(safSolutionsProviderStub.refresh.calledOnce).to.be.true;
    expect(showInformationMessageStub.calledWith('Solution "team_solution" registered successfully.')).to.be.true;
  });

  it('should call registerSolution from checkAndRegisterWorkspaceSolution when recursive validation says workspace is valid', async () => {
    getWorkspaceSolutionInfoStub.resolves(undefined);
    isValidSolutionWorkspaceStub.returns(true);

    const registerSolutionStub = sinon.stub(service, 'registerSolution').resolves(undefined);

    await service.checkAndRegisterWorkspaceSolution('/repo');

    expect(registerSolutionStub.calledOnceWith('/repo', '/repo', true)).to.be.true;
    expect(setSelectedSolutionStub.called).to.be.false;
  });

  it('should not call registerSolution from checkAndRegisterWorkspaceSolution when recursive discovery already returns workspace solution', async () => {
    const recursiveSolutionInfo: SelectedSolution = {
      name: 'platform_solution',
      displayName: 'Platform Solution',
      path: '/repo'
    };

    getWorkspaceSolutionInfoStub.resolves(recursiveSolutionInfo);
    const registerSolutionStub = sinon.stub(service, 'registerSolution').resolves(undefined);

    await service.checkAndRegisterWorkspaceSolution('/repo');

    expect(setSelectedSolutionStub.calledOnceWith('/repo', recursiveSolutionInfo)).to.be.true;
    expect(registerSolutionStub.called).to.be.false;
    expect(isValidSolutionWorkspaceStub.called).to.be.false;
  });
});
});