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
import { SolutionRunViewProvider } from '../../../src/providers/SolutionRunViewProvider';
import { SAFSolutionsProvider } from '../../../src/providers/SAFSolutionsProvider';
import { StorageService } from '../../../src/services/StorageService';
import { EnvironmentService } from '../../../src/services/EnvironmentService';
import * as fsUtils from '../../../src/utils/fsUtils';
import * as terminalUtils from '../../../src/utils/terminalUtils';
import * as workspaceUtils from '../../../src/utils/workspaceUtils';
import * as providerTools from '../../../src/providers/common/providerTools';
import * as path from 'node:path';

describe('SolutionRunViewProvider', () => {
  let provider: SolutionRunViewProvider;
  let environmentService: EnvironmentService;
  let mockExtensionUri: vscode.Uri;
  let mockWebviewView: vscode.WebviewView;
  let mockWebview: any;
  let messageHandler: ((message: any) => Promise<void>) | undefined;
  let visibilityHandler: (() => void) | undefined;
  let clock: sinon.SinonFakeTimers;
  let originalPlatform: string;

  let fileExistsSyncStub: sinon.SinonStub;
  let getSAFSolutionsStub: sinon.SinonStub;
  let getSelectedSolutionStub: sinon.SinonStub;
  let getSafCliTerminalCommandStub: sinon.SinonStub;
  let loadSolutionsStub: sinon.SinonStub;
  let checkSolutionEnvironmentStub: sinon.SinonStub;
  let handleSelectAnotherSolutionStub: sinon.SinonStub;
  let getWorkspaceSolutionInfoStub: sinon.SinonStub;
  let createTerminalWithEnvironmentStub: sinon.SinonStub;
  let executeCommandInTerminalStub: sinon.SinonStub;
  let getAsEnvironmentObjectStub: sinon.SinonStub;
  let mockTerminal: vscode.Terminal;

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
      viewType: 'solutions-manager.solutionConfig',
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
    originalPlatform = process.platform;

    mockExtensionUri = vscode.Uri.file('/mock/extension');

    (vscode.workspace as any).workspaceFolders = [
      { uri: { fsPath: '/test/workspace' } }
    ];

    (vscode.window.showInformationMessage as sinon.SinonStub).reset();
    (vscode.window.showWarningMessage as sinon.SinonStub).reset();
    (vscode.window.showErrorMessage as sinon.SinonStub).reset();
    (vscode.window.showQuickPick as sinon.SinonStub).reset();
    (vscode.window.showOpenDialog as sinon.SinonStub).reset();
    (vscode.commands.executeCommand as sinon.SinonStub).reset();

    fileExistsSyncStub = sinon.stub(fsUtils, 'fileExistsSync').returns(false);
    sinon.stub((SolutionRunViewProvider.prototype as any), '_getHtmlForWebview')
    .callsFake(function(this: any, webview: any) {
        return `<html>${webview.cspSource}{{styleUri}}{{scriptUri}}</html>`;
    });

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

    getWorkspaceSolutionInfoStub = sinon.stub(workspaceUtils, 'getWorkspaceSolutionInfo').resolves(undefined);

    mockTerminal = {
      name: 'Mock Terminal',
      processId: Promise.resolve(1234),
      creationOptions: {},
      exitStatus: undefined,
      state: { isInteractedWith: false },
      sendText: sinon.stub(),
      show: sinon.stub(),
      hide: sinon.stub(),
      dispose: sinon.stub()
    } as any;

    createTerminalWithEnvironmentStub = sinon.stub(terminalUtils, 'createTerminalWithEnvironment').returns(mockTerminal);
    executeCommandInTerminalStub = sinon.stub(terminalUtils, 'executeCommandInTerminal').resolves();

    environmentService = new EnvironmentService();
    getAsEnvironmentObjectStub = sinon.stub(environmentService, 'getAsEnvironmentObject').resolves({});

    provider = new SolutionRunViewProvider(mockExtensionUri, environmentService);
  });

  afterEach(() => {
    if (clock) {
      clock.restore();
    }

    Object.defineProperty(process, 'platform', { value: originalPlatform, writable: true });
    (vscode.workspace as any).workspaceFolders = undefined;
    messageHandler = undefined;
    visibilityHandler = undefined;

    sinon.restore();
  });

  describe('constructor and environment checks', () => {
    it('should initialize with workspace root and check environment', () => {
      expect((provider as any).workspaceRoot).to.equal('/test/workspace');
      expect(fileExistsSyncStub.called).to.be.true;
      expect((provider as any).status).to.equal('not-configured');
    });

    it('should remain not-configured when workspace root is missing', () => {
      (vscode.workspace as any).workspaceFolders = undefined;
      fileExistsSyncStub.resetHistory();

      const providerWithoutWorkspace = new SolutionRunViewProvider(mockExtensionUri, environmentService);

      expect((providerWithoutWorkspace as any).status).to.equal('not-configured');
      expect(fileExistsSyncStub.called).to.be.false;
    });

    it('should become ready when venv, scripts and one executable exist', () => {
      fileExistsSyncStub.reset();
      fileExistsSyncStub.onCall(0).returns(true);
      fileExistsSyncStub.onCall(1).returns(true);
      fileExistsSyncStub.onCall(2).returns(true);
      fileExistsSyncStub.onCall(3).returns(false);

      (provider as any).checkEnvironment('/target/solution');

      expect((provider as any).status).to.equal('ready');
      expect(loadSolutionsStub.calledOnce).to.be.true;
    });

    it('should remain not-configured when no executable exists', () => {
      fileExistsSyncStub.reset();
      fileExistsSyncStub.onCall(0).returns(true);
      fileExistsSyncStub.onCall(1).returns(true);
      fileExistsSyncStub.onCall(2).returns(false);
      fileExistsSyncStub.onCall(3).returns(false);

      (provider as any).checkEnvironment('/target/solution');

      expect((provider as any).status).to.equal('not-configured');
      expect(loadSolutionsStub.called).to.be.false;
    });

    it('should handle file check failures and stay not-configured', () => {
      fileExistsSyncStub.reset();
      fileExistsSyncStub.throws(new Error('file check failed'));

      (provider as any).checkEnvironment('/target/solution');

      expect((provider as any).status).to.equal('not-configured');
    });

    it('should use correct executable path names per platform', () => {
      const cases = [
        { platform: 'win32', scriptDir: 'Scripts', saf: 'saf.exe', starter: 'solution-app-starter.exe' },
        { platform: 'linux', scriptDir: 'bin', saf: 'saf', starter: 'solution-app-starter' }
      ];

      cases.forEach(c => {
        Object.defineProperty(process, 'platform', { value: c.platform, writable: true });
        fileExistsSyncStub.reset();
        fileExistsSyncStub.returns(false);

        (provider as any).checkEnvironment('/target/solution');

        const paths = fileExistsSyncStub.getCalls().map(call => call.args[0] as string);
        const expectedSafSuffix = path.normalize(path.join(c.scriptDir, c.saf));
        const expectedStarterSuffix = path.normalize(path.join(c.scriptDir, c.starter));

        expect(paths.some(p => path.normalize(p).endsWith(expectedSafSuffix)), `platform ${c.platform} saf path`).to.be.true;
        expect(paths.some(p => path.normalize(p).endsWith(expectedStarterSuffix)), `platform ${c.platform} starter path`).to.be.true;
      });
    });
  });

  describe('resolveWebviewView', () => {
    it('should configure webview, set html and register handlers', () => {
      const webviewView = createWebviewView();
      getSelectedSolutionStub.returns({ name: 'sol-a', displayName: 'Solution A', path: '/solutions/sol-a' });

      provider.resolveWebviewView(webviewView, {} as any, {} as any);

      expect(mockWebview.options.enableScripts).to.equal(true);
      expect(mockWebview.options.localResourceRoots).to.deep.equal([mockExtensionUri]);
      expect(mockWebview.html).to.include('mock-csp-source');
      expect(mockWebview.onDidReceiveMessage.calledOnce).to.be.true;
      expect(messageHandler).to.not.be.undefined;
      expect(visibilityHandler).to.not.be.undefined;

      const messages = getPostedMessages();
      expect(messages.some(msg => msg.type === 'set-selected-solution')).to.be.true;

      loadSolutionsStub.resetHistory();
      clock.tick(100);
      expect(loadSolutionsStub.calledOnce).to.be.true;
    });

    it('should refresh on visibility change when view becomes visible', () => {
      const webviewView = createWebviewView();
      provider.resolveWebviewView(webviewView, {} as any, {} as any);

      // let initial resolveWebviewView scheduled load run, then clear history
      clock.tick(100);
      loadSolutionsStub.reset();
      fileExistsSyncStub.reset();

      if (visibilityHandler) {
        visibilityHandler();
      }
      clock.tick(200);

      expect(loadSolutionsStub.calledOnce).to.be.true;
      expect(fileExistsSyncStub.called).to.be.true;
    });

    it('should route select-another-solution messages to provider tools', async () => {
      const webviewView = createWebviewView();
      provider.resolveWebviewView(webviewView, {} as any, {} as any);

      await messageHandler?.({ command: 'select-another-solution', previousSelection: 'sol-a' });

      expect(handleSelectAnotherSolutionStub.calledOnce).to.be.true;
      expect(handleSelectAnotherSolutionStub.firstCall.args[2]).to.equal('sol-a');
    });

    it('should surface message handler failures as error messages', async () => {
      const webviewView = createWebviewView();
      loadSolutionsStub.rejects(new Error('load failed'));
      provider.resolveWebviewView(webviewView, {} as any, {} as any);

      await messageHandler?.({ command: 'load-solutions' });

      expect((vscode.window.showErrorMessage as sinon.SinonStub).called).to.be.true;
      const errorMessage = (vscode.window.showErrorMessage as sinon.SinonStub).lastCall.args[0] as string;
      expect(errorMessage).to.include('Error: load failed');
    });
  });

  describe('message commands', () => {
    beforeEach(() => {
      const webviewView = createWebviewView();
      provider.resolveWebviewView(webviewView, {} as any, {} as any);

      loadSolutionsStub.resetHistory();
      (vscode.window.showInformationMessage as sinon.SinonStub).reset();
      (vscode.window.showWarningMessage as sinon.SinonStub).reset();
      (vscode.window.showErrorMessage as sinon.SinonStub).reset();
      (vscode.commands.executeCommand as sinon.SinonStub).reset();
      (vscode.window.showQuickPick as sinon.SinonStub).reset();
      (vscode.window.showOpenDialog as sinon.SinonStub).reset();
      createTerminalWithEnvironmentStub.resetHistory();
      executeCommandInTerminalStub.resetHistory();
      checkSolutionEnvironmentStub.resetHistory();
      getWorkspaceSolutionInfoStub.resetHistory();
      getSAFSolutionsStub.resetHistory();
      getAsEnvironmentObjectStub.resetHistory();
    });

    it('should update selected solution on solution-changed', async () => {
      await messageHandler?.({ command: 'solution-changed', solution: 'sol-b' });

      expect((provider as any).selectedSolution).to.deep.equal({
        name: 'sol-b',
        displayName: 'Solution B',
        path: '/solutions/sol-b'
      });
    });

    it('should clear selected solution when solution-changed is empty', async () => {
      await messageHandler?.({ command: 'solution-changed', solution: 'sol-b' });
      await messageHandler?.({ command: 'solution-changed', solution: '' });

      expect((provider as any).selectedSolution).to.equal(undefined);
    });

    it('should show warning for show-env-config when no selected solution exists', async () => {
      await messageHandler?.({ command: 'show-env-config' });

      expect((vscode.window.showWarningMessage as sinon.SinonStub).calledOnce).to.be.true;
      expect((vscode.commands.executeCommand as sinon.SinonStub).called).to.be.false;
    });

    it('should execute showEnvironmentConfig command when selected solution exists', async () => {
      await messageHandler?.({ command: 'solution-changed', solution: 'sol-a' });
      await messageHandler?.({ command: 'show-env-config' });

      expect((vscode.commands.executeCommand as sinon.SinonStub).calledOnce).to.be.true;
      expect((vscode.commands.executeCommand as sinon.SinonStub).firstCall.args).to.deep.equal([
        'solutions-manager.showEnvironmentConfig',
        'sol-a',
        '/solutions/sol-a'
      ]);
    });

    it('should post selected env file when browse-env-file succeeds', async () => {
      (vscode.window.showOpenDialog as sinon.SinonStub).resolves([vscode.Uri.file('/tmp/test.env')]);

      await messageHandler?.({ command: 'browse-env-file' });

      const messages = getPostedMessages();
      expect(messages.some(msg => msg.type === 'env-file-selected' && msg.path === '/tmp/test.env')).to.be.true;
    });

    it('should show error when browse-env-file fails', async () => {
      (vscode.window.showOpenDialog as sinon.SinonStub).rejects(new Error('dialog failed'));

      await messageHandler?.({ command: 'browse-env-file' });

      expect((vscode.window.showErrorMessage as sinon.SinonStub).calledOnce).to.be.true;
      expect((vscode.window.showErrorMessage as sinon.SinonStub).firstCall.args[0]).to.include('dialog failed');
    });

    it('should run explicit solution with all options in happy path', async () => {
      await messageHandler?.({
        command: 'run-solution',
        options: {
          solution: 'sol-a',
          portal: true,
          browser: true,
          debug: true,
          uiDebugger: true,
          noUi: true,
          logLevel: 'debug',
          project: 'demo',
          envFile: 'C:\\tmp\\my.env'
        }
      });

      expect(checkSolutionEnvironmentStub.calledOnceWith('/solutions/sol-a')).to.be.true;
      expect(createTerminalWithEnvironmentStub.calledOnce).to.be.true;
      expect(createTerminalWithEnvironmentStub.firstCall.args[0]).to.equal('SAF Run - sol-a');
      expect(createTerminalWithEnvironmentStub.firstCall.args[1]).to.deep.equal({});
      expect(createTerminalWithEnvironmentStub.firstCall.args[2]).to.equal('/solutions/sol-a');
      expect(executeCommandInTerminalStub.calledOnce).to.be.true;

      const command = executeCommandInTerminalStub.firstCall.args[1] as string;
      expect(command).to.include('/venv/bin/saf run sol-a');
      expect(command).to.include('--portal');
      expect(command).to.include('--browser');
      expect(command).to.include('--debug');
      expect(command).to.include('--ui-debugger');
      expect(command).to.include('--no-ui');
      expect(command).to.include('--loglevel debug');
      expect(command).to.include('--project "demo"');
      expect(command).to.include('--env-file "C:/tmp/my.env"');
    });

    it('should install environment if solution environment is missing', async () => {
      checkSolutionEnvironmentStub.returns(false);

      await messageHandler?.({
        command: 'run-solution',
        options: {
          solution: 'sol-a'
        }
      });

      expect((vscode.commands.executeCommand as sinon.SinonStub).calledWith('solutions-manager.installDevEnvironment')).to.be.true;
    });

    it('should use workspace solution when user confirms quick pick', async () => {
      getWorkspaceSolutionInfoStub.resolves({
        name: 'workspace-sol',
        displayName: 'Workspace Solution',
        path: '/workspace/solution'
      });
      (vscode.window.showQuickPick as sinon.SinonStub).resolves('Yes');

      await messageHandler?.({ command: 'run-solution', options: {} });

      const command = executeCommandInTerminalStub.firstCall.args[1] as string;
      expect(command).to.include('run workspace-sol');
      expect(createTerminalWithEnvironmentStub.firstCall.args[2]).to.equal('/workspace/solution');
    });

    it('should show error when no solutions are available', async () => {
      getSAFSolutionsStub.resolves([]);

      await messageHandler?.({ command: 'run-solution', options: {} });

      expect((vscode.window.showErrorMessage as sinon.SinonStub).calledOnce).to.be.true;
      expect((vscode.window.showErrorMessage as sinon.SinonStub).firstCall.args[0]).to.include('No solutions available');
      expect(executeCommandInTerminalStub.called).to.be.false;
    });

    it('should return when user cancels solution picker', async () => {
      getWorkspaceSolutionInfoStub.resolves(undefined);
      (vscode.window.showQuickPick as sinon.SinonStub).resolves(undefined);

      await messageHandler?.({ command: 'run-solution', options: {} });

      expect(executeCommandInTerminalStub.called).to.be.false;
    });

    it('should show error when runSolution throws unexpectedly', async () => {
      getSafCliTerminalCommandStub.throws(new Error('missing executable'));

      await messageHandler?.({ command: 'run-solution', options: { solution: 'sol-a' } });

      expect((vscode.window.showErrorMessage as sinon.SinonStub).calledOnce).to.be.true;
      expect((vscode.window.showErrorMessage as sinon.SinonStub).firstCall.args[0]).to.include('Failed to run solution');
    });
  });

  describe('polling and dispose', () => {
    it('should start status polling when view resolves in not-configured state', () => {
      const webviewView = createWebviewView();
      provider.resolveWebviewView(webviewView, {} as any, {} as any);

      expect((provider as any).status).to.equal('not-configured');
      expect((provider as any).statusCheckInterval).to.not.equal(undefined);
    });

    it('should clear polling interval when status becomes ready', () => {
      const webviewView = createWebviewView();
      provider.resolveWebviewView(webviewView, {} as any, {} as any);

      fileExistsSyncStub.resetBehavior();
      fileExistsSyncStub.returns(true);

      clock.tick(2000);

      expect((provider as any).status).to.equal('ready');
      expect((provider as any).statusCheckInterval).to.equal(undefined);
    });

    it('should stop polling on dispose', () => {
      const webviewView = createWebviewView();
      provider.resolveWebviewView(webviewView, {} as any, {} as any);

      provider.dispose();

      expect((provider as any).statusCheckInterval).to.equal(undefined);
    });
  });
});
