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
import * as sinon from 'sinon';
import { handleSelectAnotherSolution, handleWorkspacePrompt } from '../../../src/providers/common/providerTools';
import { SAFSolutionsProvider } from '../../../src/providers/SAFSolutionsProvider';
import { StorageService } from '../../../src/services/StorageService';
import { solutionSelectionService } from '../../../src/services/SolutionSelectionService';
import * as workspaceUtils from '../../../src/utils/workspaceUtils';

/**
 * Unit tests for shared provider tools
 */
describe('providerTools', () => {
  let postMessageStub: sinon.SinonStub;
  let mockView: any;

  beforeEach(() => {
    postMessageStub = sinon.stub().resolves(true);
    mockView = {
      webview: { postMessage: postMessageStub }
    };

    // Stub SAFSolutionsProvider side-effects used by loadSolutions
    sinon.stub(SAFSolutionsProvider.getInstance(), 'refresh');
    sinon.stub(SAFSolutionsProvider.getInstance(), 'getSAFSolutions').resolves([]);
    sinon.stub(StorageService, 'getSelectedSolution').returns(undefined);
  });

  afterEach(() => {
    sinon.restore();
  });

  describe('handleSelectAnotherSolution', () => {
    it('should post set-selected-solution with rootDirectory when a solution is selected', async () => {
      sinon.stub(solutionSelectionService, 'selectAndRegisterSolution').resolves({
        name: 'my-solution',
        displayName: 'My Solution',
        path: '/path/to/my-solution'
      });

      await handleSelectAnotherSolution(mockView, '/workspace', 'prev-solution');

      const calls = postMessageStub.getCalls();
      const setSelectedMsg = calls.find(c => c.args[0]?.type === 'set-selected-solution')?.args[0];
      expect(setSelectedMsg).to.exist;
      expect(setSelectedMsg.selectedSolution).to.equal('my-solution');
      expect(setSelectedMsg.displayName).to.equal('My Solution');
      expect(setSelectedMsg.rootDirectory).to.equal('/path/to/my-solution');
    });

    it('should post revert-solution with previousSelection when selection is cancelled', async () => {
      sinon.stub(solutionSelectionService, 'selectAndRegisterSolution').resolves(undefined);

      await handleSelectAnotherSolution(mockView, '/workspace', 'prev-solution');

      expect(postMessageStub.calledOnce).to.be.true;
      const msg = postMessageStub.firstCall.args[0];
      expect(msg.type).to.equal('revert-solution');
      expect(msg.previousSelection).to.equal('prev-solution');
    });

    it('should post revert-solution with empty string when previousSelection is undefined', async () => {
      sinon.stub(solutionSelectionService, 'selectAndRegisterSolution').resolves(undefined);

      await handleSelectAnotherSolution(mockView, '/workspace', undefined);

      const msg = postMessageStub.firstCall.args[0];
      expect(msg.type).to.equal('revert-solution');
      expect(msg.previousSelection).to.equal('');
    });
  });

  describe('handleWorkspacePrompt', () => {
    beforeEach(() => {
      (vscode.window.showQuickPick as sinon.SinonStub).reset();
      (vscode.window.showErrorMessage as sinon.SinonStub).reset();
      (vscode.workspace as any).workspaceFolders = [{ uri: { fsPath: '/workspace' } }];
    });

    it('should use current workspace solution when user selects Yes', async () => {
      const options = { forceSetup: true };
      const actionFn = sinon.stub().resolves();
      const getCurrentWorkspaceSolutionNameStub = sinon
        .stub(workspaceUtils, 'getCurrentWorkspaceSolutionName')
        .returns('ws-solution');

      (vscode.window.showQuickPick as sinon.SinonStub).onFirstCall().resolves({
        label: 'Yes, use "ws-solution"',
        value: 'ws-solution'
      });

      await handleWorkspacePrompt(options, actionFn);

      expect(getCurrentWorkspaceSolutionNameStub.calledOnceWith('/workspace')).to.be.true;
      expect((vscode.window.showQuickPick as sinon.SinonStub).calledOnce).to.be.true;
      expect(actionFn.calledOnceWith('ws-solution', options)).to.be.true;
    });

    it('should allow choosing another solution when user selects No', async () => {
      const options = { forceSetup: false };
      const actionFn = sinon.stub().resolves();
      sinon.stub(workspaceUtils, 'getCurrentWorkspaceSolutionName').returns('ws-solution');

      (SAFSolutionsProvider.getInstance().getSAFSolutions as sinon.SinonStub).resolves([
        { name: 'other-solution', displayName: 'Other Solution', rootDirectory: '/other' }
      ]);

      (vscode.window.showQuickPick as sinon.SinonStub).onFirstCall().resolves({
        label: 'No, choose another solution',
        value: 'choose'
      });
      (vscode.window.showQuickPick as sinon.SinonStub).onSecondCall().resolves({
        label: 'other-solution',
        description: 'Other Solution'
      });

      await handleWorkspacePrompt(options, actionFn);

      expect((vscode.window.showQuickPick as sinon.SinonStub).calledTwice).to.be.true;
      expect(actionFn.calledOnceWith('other-solution', options)).to.be.true;
    });

    it('should prompt to select a solution when workspace has no detected solution', async () => {
      const options = { forceSetup: true };
      const actionFn = sinon.stub().resolves();
      sinon.stub(workspaceUtils, 'getCurrentWorkspaceSolutionName').returns(undefined);

      (SAFSolutionsProvider.getInstance().getSAFSolutions as sinon.SinonStub).resolves([
        { name: 'picked-solution', displayName: 'Picked Solution', rootDirectory: '/picked' }
      ]);

      (vscode.window.showQuickPick as sinon.SinonStub).resolves({
        label: 'picked-solution',
        description: 'Picked Solution'
      });

      await handleWorkspacePrompt(options, actionFn);

      expect((vscode.window.showQuickPick as sinon.SinonStub).calledOnce).to.be.true;
      expect(actionFn.calledOnceWith('picked-solution', options)).to.be.true;
    });

    it('should show error when choosing another and no solutions are available', async () => {
      const options = { forceSetup: false };
      const actionFn = sinon.stub().resolves();
      sinon.stub(workspaceUtils, 'getCurrentWorkspaceSolutionName').returns('ws-solution');

      (SAFSolutionsProvider.getInstance().getSAFSolutions as sinon.SinonStub).resolves([]);

      (vscode.window.showQuickPick as sinon.SinonStub).onFirstCall().resolves({
        label: 'No, choose another solution',
        value: 'choose'
      });

      await handleWorkspacePrompt(options, actionFn);

      expect((vscode.window.showErrorMessage as sinon.SinonStub).calledOnceWith('No solutions available')).to.be.true;
      expect(actionFn.called).to.be.false;
    });

    it('should do nothing when user cancels the initial choose/use prompt', async () => {
      const options = { forceSetup: false };
      const actionFn = sinon.stub().resolves();
      sinon.stub(workspaceUtils, 'getCurrentWorkspaceSolutionName').returns('ws-solution');

      (vscode.window.showQuickPick as sinon.SinonStub).onFirstCall().resolves(undefined);

      await handleWorkspacePrompt(options, actionFn);

      expect(actionFn.called).to.be.false;
    });
  });
});
