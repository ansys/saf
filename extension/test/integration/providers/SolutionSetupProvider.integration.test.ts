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
import * as terminalUtils from '../../../src/utils/terminalUtils';
import {
  mockExtensionContext,
  mochaGlobalSetup as integrationSetup,
  mochaGlobalTeardown as integrationTeardown
} from '../setup.integration';
import { createTestSolution } from '../testHelpers';

export const mochaHooks = {
  beforeAll: integrationSetup,
  afterAll: integrationTeardown
};

describe('SolutionSetupProvider Integration Tests', () => {
  let messageHandler: ((message: any) => Promise<void>) | undefined;
  let mockWebview: any;
  let sharedSolutionName: string;

  function createMockWebviewView(): vscode.WebviewView {
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

    return {
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
  }

  before(async function () {
    this.timeout(60000);
    const { solutionName } = await createTestSolution('setup-int', 'Setup Integration Test');
    sharedSolutionName = solutionName;
  });

  beforeEach(() => {
    messageHandler = undefined;
  });

  afterEach(() => {
    sinon.restore();
  });

  it('runs saf install without -d for a registered solution', async function () {
    this.timeout(20000);

    const provider = new SolutionSetupProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
    const view = createMockWebviewView();

    const execStub = sinon.stub(terminalUtils, 'executeCommandInTerminal').resolves();
    sinon.stub(vscode.window, 'showInformationMessage').resolves(undefined);

    provider.resolveWebviewView(view, {} as any, {} as any);

    await messageHandler?.({ command: 'setup-solution', solutionName: sharedSolutionName, options: {} });

    expect(execStub.calledOnce).to.be.true;
    const [, command] = execStub.firstCall.args as [vscode.Terminal, string];
    expect(command.trim().endsWith(`install ${sharedSolutionName}`)).to.be.true;
    expect(command).to.not.include(' -d ');
  });

  it('adds only the clean-up flag when cleaning the environment', async function () {
    this.timeout(20000);

    const provider = new SolutionSetupProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
    const view = createMockWebviewView();

    const execStub = sinon.stub(terminalUtils, 'executeCommandInTerminal').resolves();
    sinon.stub(vscode.window, 'showInformationMessage').resolves(undefined);

    provider.resolveWebviewView(view, {} as any, {} as any);

    await messageHandler?.({
      command: 'setup-solution',
      solutionName: sharedSolutionName,
      options: { cleanVenv: true }
    });

    const [, command] = execStub.firstCall.args as [vscode.Terminal, string];
    expect(command.trim().endsWith(`install ${sharedSolutionName} -f`)).to.be.true;
    expect(command).to.not.include(' -d ');
  });
});
