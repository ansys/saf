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
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as sinon from 'sinon';
import * as vscode from 'vscode';
import { BuildInstallerProvider } from '../../../src/providers/BuildInstallerProvider';
import * as terminalUtils from '../../../src/utils/terminalUtils';
import {
  mockExtensionContext,
  createTempTestDir,
  mochaGlobalSetup as integrationSetup,
  mochaGlobalTeardown as integrationTeardown
} from '../setup.integration';
import { createTestSolution } from '../testHelpers';

export const mochaHooks = {
  beforeAll: integrationSetup,
  afterAll: integrationTeardown
};

describe('BuildInstallerProvider Integration Tests', () => {
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
      viewType: BuildInstallerProvider.viewType,
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

  before(async function () {
    this.timeout(60000);
    originalWorkspaceFolders = vscode.workspace.workspaceFolders;

    const { solutionName, createdSolutionPath } = await createTestSolution(
      'build-int',
      'Build Installer Integration Test'
    );

    sharedSolutionName = solutionName;
    sharedSolutionPath = createdSolutionPath;

    // Fake a ready dev environment so buildInstaller() does not try to install one for real.
    // eslint-disable-next-line security/detect-non-literal-fs-filename
    fs.mkdirSync(path.join(sharedSolutionPath, '.venv'), { recursive: true });
  });

  beforeEach(() => {
    messageHandler = undefined;
    setWorkspaceFolder(sharedSolutionPath);

    sinon.stub((BuildInstallerProvider.prototype as any), '_getHtmlForWebview')
      .returns('<html>integration-test</html>');
  });

  afterEach(() => {
    sinon.restore();
    setWorkspaceFolder(originalWorkspaceFolders?.[0]?.uri.fsPath);
  });

  it('builds the saf build command with every advanced option for a registered solution', async function () {
    this.timeout(20000);

    const provider = new BuildInstallerProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
    const view = createMockWebviewView();

    const execStub = sinon.stub(terminalUtils, 'executeCommandInTerminal').resolves();
    sinon.stub(vscode.window, 'showInformationMessage').resolves(undefined);

    provider.resolveWebviewView(view, {} as any, {} as any);

    const encryptionFilePath = path.join(sharedSolutionPath, 'encrypt-list.txt');
    const envFilePath = path.join(sharedSolutionPath, 'custom.env');
    // eslint-disable-next-line security/detect-non-literal-fs-filename
    fs.writeFileSync(encryptionFilePath, 'file1.py\n');
    // eslint-disable-next-line security/detect-non-literal-fs-filename
    fs.writeFileSync(envFilePath, 'FOO=bar\n');

    await messageHandler?.({
      command: 'build-installer',
      solutionName: sharedSolutionName,
      options: {
        offlinePackage: true,
        displayConsoleWindow: true,
        pythonVersion: '3.10.12',
        excludePython: true,
        encrypt: true,
        encryptionFile: encryptionFilePath,
        encryptionKey: 'super-secret',
        obfuscate: true,
        executableAsDir: true,
        forcePythonFromSource: true,
        envFile: envFilePath,
        noExecutable: true,
        solutionEntryPoint: 'ansys.solutions.mysoln.main',
        githubToken: 'ghp_test_token',
        solutionUiFramework: 'dash'
      }
    });

    expect(execStub.calledOnce).to.be.true;
    const [, command] = execStub.firstCall.args as [vscode.Terminal, string];

    const normalizedEncryptionFilePath = encryptionFilePath.replace(/\\/g, '/');
    const normalizedEnvFilePath = envFilePath.replace(/\\/g, '/');

    expect(command).to.include(` build ${sharedSolutionName}`);
    expect(command).to.include('--offline-package');
    expect(command).to.include('--display-console-window');
    expect(command).to.include('--python-version 3.10.12');
    expect(command).to.include('--exclude-python');
    expect(command).to.include('--encrypt');
    expect(command).to.include(`--encryption-file "${normalizedEncryptionFilePath}"`);
    expect(command).to.include('--encryption-key "super-secret"');
    expect(command).to.include('--obfuscate');
    expect(command).to.include('--executable-as-dir');
    expect(command).to.include('--force-python-from-source');
    expect(command).to.include(`--env-file "${normalizedEnvFilePath}"`);
    expect(command).to.include('--no-executable');
    expect(command).to.include('--solution-entry-point "ansys.solutions.mysoln.main"');
    expect(command).to.include('--github-token "ghp_test_token"');
    expect(command).to.include('--solution-ui-framework "dash"');
  });

  it('builds the bare saf build command when no options are provided', async function () {
    this.timeout(20000);

    const provider = new BuildInstallerProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
    const view = createMockWebviewView();

    const execStub = sinon.stub(terminalUtils, 'executeCommandInTerminal').resolves();
    sinon.stub(vscode.window, 'showInformationMessage').resolves(undefined);

    provider.resolveWebviewView(view, {} as any, {} as any);

    await messageHandler?.({ command: 'build-installer', solutionName: sharedSolutionName, options: {} });

    expect(execStub.calledOnce).to.be.true;
    const [, command] = execStub.firstCall.args as [vscode.Terminal, string];
    expect(command.trim().endsWith(`build ${sharedSolutionName}`)).to.be.true;
  });

  it('prompts to install the dev environment when the solution venv is missing', async function () {
    this.timeout(60000);

    const { solutionName } = await createTestSolution('build-int-noenv', 'No Env Solution');

    const provider = new BuildInstallerProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
    const view = createMockWebviewView();

    const execStub = sinon.stub(terminalUtils, 'executeCommandInTerminal').resolves();
    const executeCommandStub = sinon.stub(vscode.commands, 'executeCommand').resolves(undefined);
    sinon.stub(vscode.window, 'showInformationMessage').resolves(undefined);

    provider.resolveWebviewView(view, {} as any, {} as any);

    await messageHandler?.({ command: 'build-installer', solutionName, options: {} });

    expect(executeCommandStub.calledWith('solutions-manager.installDevEnvironment')).to.be.true;
    expect(execStub.calledOnce).to.be.true;
  });

  it('shows an error when the requested solution is not registered', async function () {
    const provider = new BuildInstallerProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
    const view = createMockWebviewView();

    const showErrorStub = sinon.stub(vscode.window, 'showErrorMessage').resolves(undefined);
    const execStub = sinon.stub(terminalUtils, 'executeCommandInTerminal').resolves();

    provider.resolveWebviewView(view, {} as any, {} as any);

    await messageHandler?.({ command: 'build-installer', solutionName: 'does-not-exist-solution', options: {} });

    expect(showErrorStub.calledWith("Solution 'does-not-exist-solution' not found.")).to.be.true;
    expect(execStub.called).to.be.false;
  });

  it('posts env-file-selected with the chosen file path', async function () {
    const provider = new BuildInstallerProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
    const view = createMockWebviewView();

    provider.resolveWebviewView(view, {} as any, {} as any);

    const envFilePath = path.join(sharedSolutionPath, 'picker.env');
    // eslint-disable-next-line security/detect-non-literal-fs-filename
    fs.writeFileSync(envFilePath, 'FOO=bar\n');
    sinon.stub(vscode.window, 'showOpenDialog').resolves([vscode.Uri.file(envFilePath)]);

    await messageHandler?.({ command: 'browse-env-file' });

    const messages = getPostedMessages();
    const envMsg = messages.find(m => m.type === 'env-file-selected');
    expect(envMsg?.path).to.equal(vscode.Uri.file(envFilePath).fsPath);
  });

  it('posts encryption-file-selected with the chosen file path', async function () {
    const provider = new BuildInstallerProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
    const view = createMockWebviewView();

    provider.resolveWebviewView(view, {} as any, {} as any);

    const outputDir = createTempTestDir();
    const encryptionFilePath = path.join(outputDir, 'encrypt-list.txt');
    // eslint-disable-next-line security/detect-non-literal-fs-filename
    fs.writeFileSync(encryptionFilePath, 'file1.py\n');
    sinon.stub(vscode.window, 'showOpenDialog').resolves([vscode.Uri.file(encryptionFilePath)]);

    await messageHandler?.({ command: 'browse-encryption-file' });

    const messages = getPostedMessages();
    const encryptionMsg = messages.find(m => m.type === 'encryption-file-selected');
    expect(encryptionMsg?.path).to.equal(vscode.Uri.file(encryptionFilePath).fsPath);
  });
});
