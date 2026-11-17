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
import { SolutionSetupProvider } from '../../../src/providers/SolutionSetupProvider';
import { SAFSolutionsProvider } from '../../../src/providers/SAFSolutionsProvider';
import { StorageService } from '../../../src/services/StorageService';
import * as terminalUtils from '../../../src/utils/terminalUtils';
import * as providerTools from '../../../src/providers/common/providerTools';

describe('SolutionSetupProvider', () => {
  let provider: SolutionSetupProvider;
  let mockWebview: any;
  let mockWebviewView: vscode.WebviewView;
  let messageHandler: ((message: any) => Promise<void>) | undefined;
  let executeCommandInTerminalStub: sinon.SinonStub;
  let clock: sinon.SinonFakeTimers;

  beforeEach(() => {
    clock = sinon.useFakeTimers();

    mockWebview = {
      html: '',
      options: {},
      onDidReceiveMessage: sinon.stub().callsFake((handler) => {
        messageHandler = handler;
        return { dispose: sinon.stub() };
      }),
      postMessage: sinon.stub().resolves(true),
      asWebviewUri: sinon.stub().callsFake((uri: vscode.Uri) => uri),
      cspSource: 'mock-csp-source'
    };

    mockWebviewView = {
      webview: mockWebview,
      viewType: SolutionSetupProvider.viewType,
      visible: true,
      onDidDispose: sinon.stub().returns({ dispose: sinon.stub() }),
      onDidChangeVisibility: sinon.stub().returns({ dispose: sinon.stub() }),
      show: sinon.stub(),
      title: undefined,
      description: undefined,
      badge: undefined
    } as any;

    (vscode.window.terminals as any) = [];
    (vscode.window.showInformationMessage as sinon.SinonStub).reset();
    (vscode.window.showErrorMessage as sinon.SinonStub).reset();
    (vscode.window.createTerminal as sinon.SinonStub).reset();
    (vscode.window.createTerminal as sinon.SinonStub).returns({
      name: 'Mock Terminal',
      show: sinon.stub(),
      dispose: sinon.stub(),
      sendText: sinon.stub()
    });

    sinon.stub(SAFSolutionsProvider, 'getInstance').returns({
      getSAFSolutions: sinon.stub().resolves([
        { name: 'sol-a', displayName: 'Solution A', rootDirectory: '/solutions/sol-a' }
      ]),
      refresh: sinon.stub()
    } as any);
    sinon.stub(StorageService, 'getSelectedSolution').returns(undefined);
    sinon.stub(StorageService, 'getSafCliTerminalCommand').returns('saf');
    sinon.stub(providerTools, 'loadSolutions').resolves();
    executeCommandInTerminalStub = sinon.stub(terminalUtils, 'executeCommandInTerminal').resolves();

    provider = new SolutionSetupProvider(vscode.Uri.file('/mock/extension'));
    provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);
  });

  afterEach(async () => {
    await clock.runAllAsync();
    clock.restore();
    sinon.restore();
    messageHandler = undefined;
  });

  describe('setup command', () => {
    it('should not pass -d so the CLI default dependency groups apply', async () => {
      await messageHandler?.({ command: 'setup-solution', solutionName: 'sol-a', options: {} });

      expect(executeCommandInTerminalStub.calledOnce).to.be.true;
      expect(executeCommandInTerminalStub.firstCall.args[1]).to.equal('saf install sol-a');
    });

    it('should append -f when cleaning the environment', async () => {
      await messageHandler?.({ command: 'setup-solution', solutionName: 'sol-a', options: { cleanVenv: true } });

      expect(executeCommandInTerminalStub.firstCall.args[1]).to.equal('saf install sol-a -f');
    });

    it('should append -F when cleaning the environment and the lock file', async () => {
      await messageHandler?.({ command: 'setup-solution', solutionName: 'sol-a', options: { cleanVenvLock: true } });

      expect(executeCommandInTerminalStub.firstCall.args[1]).to.equal('saf install sol-a -F');
    });
  });

  describe('command preview', () => {
    it('should not include the -d option in the webview script', () => {
      expect(mockWebview.html).to.include('let command = \'saf install\';');
      expect(mockWebview.html).to.not.include('-d all');
      expect(mockWebview.html).to.not.match(/command \+= ' -d/);
    });
  });
});
