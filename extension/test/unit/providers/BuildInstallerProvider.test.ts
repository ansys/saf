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
import { SAFSolutionsProvider } from '../../../src/providers/SAFSolutionsProvider';
import { StorageService } from '../../../src/services/StorageService';
import * as terminalUtils from '../../../src/utils/terminalUtils';
import * as providerTools from '../../../src/providers/common/providerTools';

const STUB_HTML = '<html><body>Build Installer</body></html>';

describe('BuildInstallerProvider', () => {
  let provider: BuildInstallerProvider;
  let mockExtensionUri: vscode.Uri;
  let mockWebviewView: vscode.WebviewView;
  let mockWebview: any;
  let messageHandler: ((message: any) => Promise<void>) | undefined;
  let visibilityHandler: (() => void) | undefined;
  let clock: sinon.SinonFakeTimers;

  let getSAFSolutionsStub: sinon.SinonStub;
  let getSelectedSolutionStub: sinon.SinonStub;
  let getSafCliTerminalCommandStub: sinon.SinonStub;
  let loadSolutionsStub: sinon.SinonStub;
  let checkSolutionEnvironmentStub: sinon.SinonStub;
  let handleSelectAnotherSolutionStub: sinon.SinonStub;
  let handleWorkspacePromptStub: sinon.SinonStub;
  let executeCommandInTerminalStub: sinon.SinonStub;
  let createTerminalStub: sinon.SinonStub;
  let mockTerminal: any;

  const defaultSolutions = [
    { name: 'sol-a', displayName: 'Solution A', rootDirectory: '/solutions/sol-a' },
    { name: 'sol-b', displayName: 'Solution B', rootDirectory: '/solutions/sol-b' }
  ];

  function createWebviewView(): vscode.WebviewView {
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
      viewType: BuildInstallerProvider.viewType,
      visible: true,
      onDidDispose: sinon.stub().returns({ dispose: sinon.stub() }),
      onDidChangeVisibility: sinon.stub().callsFake((handler) => {
        visibilityHandler = handler;
        return { dispose: sinon.stub() };
      }),
      show: sinon.stub(),
      title: undefined,
      description: undefined,
      badge: undefined
    } as any;

    return mockWebviewView;
  }

  function getPostedMessages(): any[] {
    return (mockWebview.postMessage as sinon.SinonStub).getCalls().map(call => call.args[0]);
  }

  beforeEach(() => {
    clock = sinon.useFakeTimers();
    mockExtensionUri = vscode.Uri.file('/mock/extension');

    (vscode.workspace as any).workspaceFolders = [
      { uri: { fsPath: '/test/workspace' } }
    ];

    (vscode.window.showInformationMessage as sinon.SinonStub).reset();
    (vscode.window.showWarningMessage as sinon.SinonStub).reset();
    (vscode.window.showErrorMessage as sinon.SinonStub).reset();
    (vscode.window.showOpenDialog as sinon.SinonStub).reset();
    (vscode.commands.executeCommand as sinon.SinonStub).reset();
    (vscode.window.terminals as any) = [];

    sinon.stub((BuildInstallerProvider.prototype as any), '_getHtmlForWebview').returns(STUB_HTML);

    getSAFSolutionsStub = sinon.stub().resolves(defaultSolutions);
    sinon.stub(SAFSolutionsProvider, 'getInstance').returns({
      getSAFSolutions: getSAFSolutionsStub,
      refresh: sinon.stub()
    } as any);

    getSelectedSolutionStub = sinon.stub(StorageService, 'getSelectedSolution').returns(undefined);
    getSafCliTerminalCommandStub = sinon.stub(StorageService, 'getSafCliTerminalCommand').returns('/venv/bin/saf');

    loadSolutionsStub = sinon.stub(providerTools, 'loadSolutions').resolves();
    checkSolutionEnvironmentStub = sinon.stub(providerTools, 'checkSolutionEnvironment').returns(true);
    handleSelectAnotherSolutionStub = sinon.stub(providerTools, 'handleSelectAnotherSolution').resolves();
    handleWorkspacePromptStub = sinon.stub(providerTools, 'handleWorkspacePrompt').resolves();

    mockTerminal = {
      name: 'Mock Terminal',
      show: sinon.stub(),
      dispose: sinon.stub(),
      sendText: sinon.stub()
    };

    createTerminalStub = vscode.window.createTerminal as sinon.SinonStub;
    createTerminalStub.reset();
    createTerminalStub.returns(mockTerminal);

    executeCommandInTerminalStub = sinon.stub(terminalUtils, 'executeCommandInTerminal').resolves();

    provider = new BuildInstallerProvider(mockExtensionUri);
  });

  afterEach(async () => {
    await clock.runAllAsync();
    clock.restore();
    (vscode.workspace as any).workspaceFolders = undefined;
    messageHandler = undefined;
    visibilityHandler = undefined;
    sinon.restore();
  });

  describe('resolveWebviewView', () => {
    it('should configure webview, set html and register handlers', () => {
      const webviewView = createWebviewView();
      getSelectedSolutionStub.returns({ name: 'sol-a', displayName: 'Solution A' });

      provider.resolveWebviewView(webviewView, {} as any, {} as any);

      expect(mockWebview.options.enableScripts).to.equal(true);
      expect(mockWebview.options.localResourceRoots).to.deep.equal([mockExtensionUri]);
      expect(mockWebview.html).to.equal(STUB_HTML);
      expect(mockWebview.onDidReceiveMessage.calledOnce).to.be.true;
      expect(messageHandler).to.not.be.undefined;
      expect(visibilityHandler).to.not.be.undefined;

      const messages = getPostedMessages();
      expect(messages.some(msg => msg.type === 'set-selected-solution')).to.be.true;

      loadSolutionsStub.resetHistory();
      clock.tick(100);
      expect(loadSolutionsStub.calledOnce).to.be.true;
    });

    it('should not post set-selected-solution when no solution is stored', () => {
      const webviewView = createWebviewView();
      provider.resolveWebviewView(webviewView, {} as any, {} as any);

      const messages = getPostedMessages();
      expect(messages.some(msg => msg.type === 'set-selected-solution')).to.be.false;
    });

    it('should refresh solutions and selected solution on visibility change', () => {
      const webviewView = createWebviewView();
      provider.resolveWebviewView(webviewView, {} as any, {} as any);

      clock.tick(100);
      loadSolutionsStub.resetHistory();

      visibilityHandler?.();

      expect(loadSolutionsStub.calledOnce).to.be.true;
    });

    it('should route select-another-solution messages to provider tools', async () => {
      const webviewView = createWebviewView();
      provider.resolveWebviewView(webviewView, {} as any, {} as any);

      await messageHandler?.({ command: 'select-another-solution', previousSelection: 'sol-a' });

      expect(handleSelectAnotherSolutionStub.calledOnce).to.be.true;
      expect(handleSelectAnotherSolutionStub.firstCall.args[2]).to.equal('sol-a');
    });

    it('should route load-solutions messages to provider tools', async () => {
      const webviewView = createWebviewView();
      provider.resolveWebviewView(webviewView, {} as any, {} as any);
      loadSolutionsStub.resetHistory();

      await messageHandler?.({ command: 'load-solutions' });

      expect(loadSolutionsStub.calledOnce).to.be.true;
    });

    it('should show an error message for show-error commands', async () => {
      const webviewView = createWebviewView();
      provider.resolveWebviewView(webviewView, {} as any, {} as any);

      await messageHandler?.({ command: 'show-error', message: 'boom' });

      expect((vscode.window.showErrorMessage as sinon.SinonStub).calledWith('boom')).to.be.true;
    });

    it('should route build-installer-workspace-prompt to provider tools', async () => {
      const webviewView = createWebviewView();
      provider.resolveWebviewView(webviewView, {} as any, {} as any);

      await messageHandler?.({ command: 'build-installer-workspace-prompt', options: { offlinePackage: true } });

      expect(handleWorkspacePromptStub.calledOnce).to.be.true;
      expect(handleWorkspacePromptStub.firstCall.args[0]).to.deep.equal({ offlinePackage: true });
    });

    it('should surface message handler failures as error messages', async () => {
      const webviewView = createWebviewView();
      loadSolutionsStub.rejects(new Error('load failed'));
      provider.resolveWebviewView(webviewView, {} as any, {} as any);

      await messageHandler?.({ command: 'load-solutions' });

      expect((vscode.window.showErrorMessage as sinon.SinonStub).called).to.be.true;
      expect((vscode.window.showErrorMessage as sinon.SinonStub).lastCall.args[0]).to.include('Error: load failed');
    });
  });

  describe('browse-env-file', () => {
    it('should post env-file-selected when a file is chosen', async () => {
      const webviewView = createWebviewView();
      provider.resolveWebviewView(webviewView, {} as any, {} as any);
      (vscode.window.showOpenDialog as sinon.SinonStub).resolves([vscode.Uri.file('/tmp/test.env')]);

      await messageHandler?.({ command: 'browse-env-file' });

      const messages = getPostedMessages();
      expect(messages.some(msg => msg.type === 'env-file-selected' && msg.path === '/tmp/test.env')).to.be.true;
    });

    it('should show error when browse-env-file fails', async () => {
      const webviewView = createWebviewView();
      provider.resolveWebviewView(webviewView, {} as any, {} as any);
      (vscode.window.showOpenDialog as sinon.SinonStub).rejects(new Error('dialog failed'));

      await messageHandler?.({ command: 'browse-env-file' });

      expect((vscode.window.showErrorMessage as sinon.SinonStub).calledOnce).to.be.true;
      expect((vscode.window.showErrorMessage as sinon.SinonStub).firstCall.args[0]).to.include('dialog failed');
    });

    it('should do nothing when the dialog is dismissed', async () => {
      const webviewView = createWebviewView();
      provider.resolveWebviewView(webviewView, {} as any, {} as any);
      (vscode.window.showOpenDialog as sinon.SinonStub).resolves(undefined);

      await messageHandler?.({ command: 'browse-env-file' });

      const messages = getPostedMessages();
      expect(messages.some(msg => msg.type === 'env-file-selected')).to.be.false;
    });
  });

  describe('browse-encryption-file', () => {
    it('should post encryption-file-selected when a file is chosen', async () => {
      const webviewView = createWebviewView();
      provider.resolveWebviewView(webviewView, {} as any, {} as any);
      (vscode.window.showOpenDialog as sinon.SinonStub).resolves([vscode.Uri.file('/tmp/encryption-list.txt')]);

      await messageHandler?.({ command: 'browse-encryption-file' });

      const messages = getPostedMessages();
      expect(messages.some(
        msg => msg.type === 'encryption-file-selected' && msg.path === '/tmp/encryption-list.txt'
      )).to.be.true;
    });

    it('should show error when browse-encryption-file fails', async () => {
      const webviewView = createWebviewView();
      provider.resolveWebviewView(webviewView, {} as any, {} as any);
      (vscode.window.showOpenDialog as sinon.SinonStub).rejects(new Error('dialog failed'));

      await messageHandler?.({ command: 'browse-encryption-file' });

      expect((vscode.window.showErrorMessage as sinon.SinonStub).calledOnce).to.be.true;
      expect((vscode.window.showErrorMessage as sinon.SinonStub).firstCall.args[0]).to.include('dialog failed');
    });
  });

  describe('build-installer command construction', () => {
    beforeEach(() => {
      const webviewView = createWebviewView();
      provider.resolveWebviewView(webviewView, {} as any, {} as any);
      loadSolutionsStub.resetHistory();
      (vscode.window.showErrorMessage as sinon.SinonStub).reset();
      (vscode.window.showInformationMessage as sinon.SinonStub).reset();
      (vscode.commands.executeCommand as sinon.SinonStub).reset();
      checkSolutionEnvironmentStub.resetHistory();
      executeCommandInTerminalStub.resetHistory();
      createTerminalStub.resetHistory();
    });

    it('should build the base command with only the solution name when no options are set', async () => {
      await messageHandler?.({ command: 'build-installer', solutionName: 'sol-a', options: {} });

      expect(executeCommandInTerminalStub.calledOnce).to.be.true;
      const [, command] = executeCommandInTerminalStub.firstCall.args;
      expect(command).to.equal('/venv/bin/saf build sol-a');
    });

    it('should append every saf build flag in the documented order when all options are set', async () => {
      await messageHandler?.({
        command: 'build-installer',
        solutionName: 'sol-a',
        options: {
          offlinePackage: true,
          displayConsoleWindow: true,
          pythonVersion: '3.10.12',
          excludePython: true,
          encrypt: true,
          encryptionFile: 'C:\\tmp\\encrypt-list.txt',
          encryptionKey: 'super-secret-key',
          obfuscate: true,
          executableAsDir: true,
          forcePythonFromSource: true,
          envFile: 'C:\\tmp\\my.env',
          noExecutable: true,
          solutionEntryPoint: 'ansys.solutions.mysoln.main',
          githubToken: 'ghp_token',
          solutionUiFramework: 'dash'
        }
      });

      expect(executeCommandInTerminalStub.calledOnce).to.be.true;
      const [, command] = executeCommandInTerminalStub.firstCall.args;
      expect(command).to.equal(
        '/venv/bin/saf build sol-a' +
        ' --offline-package' +
        ' --display-console-window' +
        ' --python-version 3.10.12' +
        ' --exclude-python' +
        ' --encrypt' +
        ' --encryption-file "C:/tmp/encrypt-list.txt"' +
        ' --encryption-key "super-secret-key"' +
        ' --obfuscate' +
        ' --executable-as-dir' +
        ' --force-python-from-source' +
        ' --env-file "C:/tmp/my.env"' +
        ' --no-executable' +
        ' --solution-entry-point "ansys.solutions.mysoln.main"' +
        ' --github-token "ghp_token"' +
        ' --solution-ui-framework "dash"'
      );
    });

    it('should strip whitespace and escape double quotes in encryption key and GitHub token values', async () => {
      await messageHandler?.({
        command: 'build-installer',
        solutionName: 'sol-a',
        options: {
          encryptionKey: 'sup er "secret" key',
          githubToken: 'ghp _to"ken'
        }
      });

      const [, command] = executeCommandInTerminalStub.firstCall.args;
      expect(command).to.equal(
        '/venv/bin/saf build sol-a' +
        ' --encryption-key "super\\"secret\\"key"' +
        ' --github-token "ghp_to\\"ken"'
      );
    });

    it('should escape double quotes in solution entry point and UI framework values', async () => {
      await messageHandler?.({
        command: 'build-installer',
        solutionName: 'sol-a',
        options: {
          solutionEntryPoint: 'ansys."mysoln".main',
          solutionUiFramework: 'da"sh'
        }
      });

      const [, command] = executeCommandInTerminalStub.firstCall.args;
      expect(command).to.equal(
        '/venv/bin/saf build sol-a' +
        ' --solution-entry-point "ansys.\\"mysoln\\".main"' +
        ' --solution-ui-framework "da\\"sh"'
      );
    });

    it('should not add flags for falsy option values', async () => {
      await messageHandler?.({
        command: 'build-installer',
        solutionName: 'sol-a',
        options: {
          offlinePackage: false,
          encrypt: false,
          encryptionFile: '',
          encryptionKey: '',
          obfuscate: false,
          executableAsDir: false,
          forcePythonFromSource: false,
          envFile: '',
          noExecutable: false,
          solutionEntryPoint: '',
          githubToken: '',
          solutionUiFramework: ''
        }
      });

      const [, command] = executeCommandInTerminalStub.firstCall.args;
      expect(command).to.equal('/venv/bin/saf build sol-a');
    });

    it('should show an error and skip the build when the solution is not found', async () => {
      await messageHandler?.({ command: 'build-installer', solutionName: 'missing-solution', options: {} });

      expect((vscode.window.showErrorMessage as sinon.SinonStub).calledWith(
        "Solution 'missing-solution' not found."
      )).to.be.true;
      expect(executeCommandInTerminalStub.called).to.be.false;
      expect(createTerminalStub.called).to.be.false;
    });

    it('should install the development environment when it is missing', async () => {
      checkSolutionEnvironmentStub.returns(false);

      await messageHandler?.({ command: 'build-installer', solutionName: 'sol-a', options: {} });

      expect((vscode.window.showInformationMessage as sinon.SinonStub).called).to.be.true;
      expect((vscode.commands.executeCommand as sinon.SinonStub).calledWith(
        'solutions-manager.installDevEnvironment'
      )).to.be.true;
    });

    it('should dispose an existing terminal with the same name before creating a new one', async () => {
      const existingTerminal = { name: 'SAF Build - sol-a', dispose: sinon.stub() };
      (vscode.window.terminals as any) = [existingTerminal];

      await messageHandler?.({ command: 'build-installer', solutionName: 'sol-a', options: {} });

      expect(existingTerminal.dispose.calledOnce).to.be.true;
      expect(createTerminalStub.calledOnceWith('SAF Build - sol-a')).to.be.true;
    });

    it('should show a warning when the built installer cannot be found', async () => {
      await messageHandler?.({ command: 'build-installer', solutionName: 'sol-a', options: {} });

      expect((vscode.window.showWarningMessage as sinon.SinonStub).called).to.be.true;
      expect((vscode.window.showWarningMessage as sinon.SinonStub).firstCall.args[0]).to.include(
        'Expected installer not found at:'
      );
    });

    it('should surface failures from the SAF solutions provider as error messages', async () => {
      getSAFSolutionsStub.rejects(new Error('lookup failed'));

      await messageHandler?.({ command: 'build-installer', solutionName: 'sol-a', options: {} });

      expect((vscode.window.showErrorMessage as sinon.SinonStub).calledOnce).to.be.true;
      expect((vscode.window.showErrorMessage as sinon.SinonStub).firstCall.args[0]).to.include(
        'Failed to build installer: lookup failed'
      );
    });
  });

  describe('build installer template', () => {
    it('should suggest a patched Python version in the placeholder', () => {
      const templatePath = path.join(process.cwd(), 'src', 'webview', 'templates', 'buildInstaller.html');
      // eslint-disable-next-line security/detect-non-literal-fs-filename
      const html = fs.readFileSync(templatePath, 'utf8');

      expect(html).to.include('id="python-version" placeholder="e.g., 3.11.14"');
    });
  });
});
