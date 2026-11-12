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
import * as http from 'node:http';
import * as path from 'node:path';
import * as sinon from 'sinon';
import * as vscode from 'vscode';
import { SolutionRunViewProvider } from '../../../src/providers/SolutionRunViewProvider';
import { StorageService } from '../../../src/services/StorageService';
import { systemService } from '../../../src/services/SystemService';
import { EnvironmentService } from '../../../src/services/EnvironmentService';
import {
  mockExtensionContext,
  createTempTestDir,
  mochaGlobalSetup as integrationSetup,
  mochaGlobalTeardown as integrationTeardown
} from '../setup.integration';
import { createTestSolution, installTestSolutionEnv } from '../testHelpers';

export const mochaHooks = {
  beforeAll: integrationSetup,
  afterAll: integrationTeardown
};

describe('SolutionRunViewProvider Integration Tests', () => {
  let messageHandler: ((message: any) => Promise<void>) | undefined;
  let mockWebview: any;
  let sharedSolutionName: string;
  let sharedSolutionPath: string;
  let originalWorkspaceFolders: readonly vscode.WorkspaceFolder[] | undefined;

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
      viewType: SolutionRunViewProvider.viewType,
      visible: true,
      onDidDispose: sinon.stub().returns({ dispose: sinon.stub() }),
      onDidChangeVisibility: sinon.stub().returns({ dispose: sinon.stub() }),
      show: sinon.stub(),
      title: undefined,
      description: undefined,
      badge: undefined
    } as any;
  }

  function setWorkspaceFolder(fsPath: string | undefined): void {
    const folders = fsPath === undefined
      ? undefined
      : [
        {
          uri: vscode.Uri.file(fsPath),
          name: path.basename(fsPath),
          index: 0
        }
      ];

    Object.defineProperty(vscode.workspace, 'workspaceFolders', {
      get: () => folders,
      configurable: true,
      enumerable: true
    });
  }

  function getPostedMessages(): any[] {
    return (mockWebview.postMessage as sinon.SinonStub).getCalls().map(call => call.args[0]);
  }

  async function sleep(ms: number): Promise<void> {
    await new Promise(resolve => setTimeout(resolve, ms));
  }

  async function waitForCondition(predicate: () => boolean, timeoutMs: number, intervalMs: number = 250): Promise<void> {
    const start = Date.now();
    while (!predicate()) {
      if (Date.now() - start > timeoutMs) {
        throw new Error(`Condition not met within ${timeoutMs}ms`);
      }
      await sleep(intervalMs);
    }
  }

  async function waitForTerminalByName(name: string, timeoutMs: number): Promise<vscode.Terminal> {
    await waitForCondition(
      () => vscode.window.terminals.some(terminal => terminal.name === name),
      timeoutMs
    );

    const terminal = vscode.window.terminals.find(t => t.name === name);
    if (!terminal) {
      throw new Error(`Terminal ${name} was not found`);
    }

    return terminal;
  }

  async function waitForSolutionApiUrl(terminal: vscode.Terminal, timeoutMs: number): Promise<string> {
    return new Promise<string>((resolve, reject) => {
      let buffer = '';
      const deadline = Date.now() + timeoutMs;
      const pattern = /Solution API:\s*(http:\/\/127\.0\.0\.1:\d+\/docs)/;

      const disposable = (vscode.window as any).onDidWriteTerminalData((event: any)  => {
        if (event.terminal !== terminal) {
          return;
        }

        buffer += event.data;
        const match = buffer.match(pattern);
        if (match?.[1]) {
          clearInterval(timeout);
          disposable.dispose();
          resolve(match[1]);
        }
      });

      const timeout = setInterval(() => {
        if (Date.now() >= deadline) {
          clearInterval(timeout);
          disposable.dispose();
          reject(new Error(`Did not find Solution API URL in terminal output. Output tail: ${buffer.slice(-500)}`));
        }
      }, 500);
    });
  }

  async function getStatusCode(url: string): Promise<number> {
    return new Promise<number>((resolve, reject) => {
      const req = http.get(url, (res) => {
        resolve(res.statusCode || 0);
        res.resume();
      });

      req.on('error', reject);
      req.setTimeout(5000, () => {
        req.destroy(new Error(`Request timed out for ${url}`));
      });
    });
  }

  before(async function () {
    this.timeout(180000);
    originalWorkspaceFolders = vscode.workspace.workspaceFolders;

    new StorageService(mockExtensionContext);
    systemService.setContext(mockExtensionContext);

    const { solutionName, createdSolutionPath } = await createTestSolution(
      'run-int',
      'Solution Run Integration Test'
    );

    sharedSolutionName = solutionName;
    sharedSolutionPath = createdSolutionPath;

    await installTestSolutionEnv(sharedSolutionName, sharedSolutionPath);
  });

  beforeEach(() => {
    messageHandler = undefined;
    setWorkspaceFolder(sharedSolutionPath);

    sinon.stub((SolutionRunViewProvider.prototype as any), '_getHtmlForWebview')
      .returns('<html>integration-test</html>');
  });

  afterEach(async function () {
    const runTerminals = vscode.window.terminals.filter(terminal => terminal.name.startsWith('SAF Run - '));

    for (const terminal of runTerminals) {
      try {
        terminal.sendText('\x03');
      } catch {
        // ignore cleanup errors
      }
    }

    await sleep(500);

    for (const terminal of runTerminals) {
      try {
        terminal.dispose();
      } catch {
        // ignore cleanup errors
      }
    }

    Object.defineProperty(vscode.workspace, 'workspaceFolders', {
      get: () => originalWorkspaceFolders,
      configurable: true,
      enumerable: true
    });

    sinon.restore();
  });

  it('detects configured environment for installed solution', async function () {
    const provider = new SolutionRunViewProvider(
      vscode.Uri.file(mockExtensionContext.extensionPath),
      new EnvironmentService(mockExtensionContext)
    );

    const webviewView = createMockWebviewView();
    provider.resolveWebviewView(webviewView, {} as any, {} as any);

    await sleep(300);

    await waitForCondition(
      () => getPostedMessages().some(msg => msg.type === 'solutions-loaded'),
      10000
    );

    expect((provider as any).status).to.equal('ready');

    const messages = getPostedMessages();
    const loadedMessage = messages.find(msg => msg.type === 'solutions-loaded');
    expect(loadedMessage).to.not.equal(undefined);

    provider.dispose();
  });

  it('remains not-configured when workspace has no virtual environment', async function () {
    const noEnvDir = createTempTestDir();
    setWorkspaceFolder(noEnvDir);

    const provider = new SolutionRunViewProvider(
      vscode.Uri.file(mockExtensionContext.extensionPath),
      new EnvironmentService(mockExtensionContext)
    );

    const webviewView = createMockWebviewView();
    provider.resolveWebviewView(webviewView, {} as any, {} as any);

    await sleep(400);

    expect((provider as any).status).to.equal('not-configured');
    expect((provider as any).statusCheckInterval).to.not.equal(undefined);

    provider.dispose();
  });

  it('loads solutions through load-solutions message', async function () {
    const provider = new SolutionRunViewProvider(
      vscode.Uri.file(mockExtensionContext.extensionPath),
      new EnvironmentService(mockExtensionContext)
    );

    const webviewView = createMockWebviewView();
    provider.resolveWebviewView(webviewView, {} as any, {} as any);

    await messageHandler?.({ command: 'load-solutions' });

    const messages = getPostedMessages();
    const loadedMessages = messages.filter(msg => msg.type === 'solutions-loaded');
    expect(loadedMessages.length).to.be.greaterThan(0);

    const latestMessage = loadedMessages.at(-1);
    expect(latestMessage.solutions.some((solution: any) => solution.name === sharedSolutionName)).to.equal(true);

    provider.dispose();
  });

  it('runs shared solution and serves docs endpoint', async function () {
    this.timeout(240000);
    const provider = new SolutionRunViewProvider(
      vscode.Uri.file(mockExtensionContext.extensionPath),
      new EnvironmentService(mockExtensionContext)
    );

    const webviewView = createMockWebviewView();
    provider.resolveWebviewView(webviewView, {} as any, {} as any);

    messageHandler?.({
      command: 'run-solution',
      options: { solution: sharedSolutionName }
    });

    const terminalName = `SAF Run - ${sharedSolutionName}`;
    const terminal = await waitForTerminalByName(terminalName, 20000);
    expect(terminal).to.not.equal(undefined);

    const apiUrl = await waitForSolutionApiUrl(terminal, 30000);
    const statusCode = await getStatusCode(apiUrl);
    expect(statusCode).to.equal(200);

    provider.dispose();
  });

  it('runs selected solution from quick pick when command has no explicit selection', async function () {
    setWorkspaceFolder(undefined);

    const showQuickPickStub = sinon.stub(vscode.window, 'showQuickPick');
    showQuickPickStub.resolves({ label: sharedSolutionName } as any);

    const provider = new SolutionRunViewProvider(
      vscode.Uri.file(mockExtensionContext.extensionPath),
      new EnvironmentService(mockExtensionContext)
    );

    const webviewView = createMockWebviewView();
    provider.resolveWebviewView(webviewView, {} as any, {} as any);

    messageHandler?.({
      command: 'run-solution',
      options: {}
    });

    const terminalName = `SAF Run - ${sharedSolutionName}`;
    const terminal = await waitForTerminalByName(terminalName, 20000);

    const creationOptions = (terminal as any).creationOptions;
    expect(path.normalize(creationOptions.cwd).toLowerCase()).to.equal(path.normalize(sharedSolutionPath).toLowerCase());

    provider.dispose();
  });

  it('requests environment installation when workspace solution has no .venv', async function () {
    this.timeout(30000);

    const { solutionName: noVenvName, createdSolutionPath: noVenvPath } =
      await createTestSolution('run-no-venv', 'Run No Venv Test');

    setWorkspaceFolder(noVenvPath);

    const executeCommandStub = sinon.stub(vscode.commands, 'executeCommand').resolves(undefined);

    const provider = new SolutionRunViewProvider(
      vscode.Uri.file(mockExtensionContext.extensionPath),
      new EnvironmentService(mockExtensionContext)
    );

    const webviewView = createMockWebviewView();
    provider.resolveWebviewView(webviewView, {} as any, {} as any);

    await messageHandler?.({
      command: 'run-solution',
      options: { solution: noVenvName }
    });

    await waitForCondition(
      () => executeCommandStub.calledWith('solutions-manager.installDevEnvironment'),
      10000
    );

    expect(executeCommandStub.calledWith('solutions-manager.installDevEnvironment')).to.equal(true);
    provider.dispose();
  });
});
