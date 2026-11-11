// Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
// SPDX-License-Identifier: Apache-2.0
//
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import { expect } from 'chai';
import * as sinon from 'sinon';
import * as vscode from 'vscode';
import { ArchiveSolutionProvider } from '../../../src/providers/ArchiveSolutionProvider';
import { SAFSolutionsProvider } from '../../../src/providers/SAFSolutionsProvider';
import { StorageService } from '../../../src/services/StorageService';
import * as terminalUtils from '../../../src/utils/terminalUtils';

const STUB_HTML = '<html><body>' +
  '<div id="solution-select"></div>' +
  '<input id="output-path" />' +
  '<input id="archive-filename" />' +
  '<input id="archive-extension" />' +
  '<code id="command-preview">saf archive</code>' +
  '<button id="archive-btn">Archive solution</button>' +
  '</body></html>';

/**
 * Unit tests for ArchiveSolutionProvider
 */
describe('ArchiveSolutionProvider', () => {
  let provider: ArchiveSolutionProvider;
  let mockExtensionUri: vscode.Uri;
  let mockWebviewView: vscode.WebviewView;
  let mockWebview: any;
  let messageHandler: ((message: any) => Promise<void>) | undefined;
  let getSolutionsStub: sinon.SinonStub;
  let executeCommandInTerminalStub: sinon.SinonStub;
  let createTerminalStub: sinon.SinonStub;
  let mockTerminal: any;
  let clock: sinon.SinonFakeTimers;

  beforeEach(() => {
    clock = sinon.useFakeTimers();

    // Reset the singleton so each test gets a fresh provider
    ArchiveSolutionProvider.resetInstance();

    mockExtensionUri = vscode.Uri.file('/mock/extension');

    mockWebview = {
      html: '',
      options: {},
      onDidReceiveMessage: sinon.stub().callsFake((handler) => {
        messageHandler = handler;
        return { dispose: sinon.stub() };
      }),
      postMessage: sinon.stub().resolves(true),
      asWebviewUri: sinon.stub().callsFake((uri) => uri),
      cspSource: 'mock-csp-source'
    };

    mockWebviewView = {
      webview: mockWebview,
      viewType: ArchiveSolutionProvider.viewType,
      visible: true,
      onDidDispose: sinon.stub().returns({ dispose: sinon.stub() }),
      onDidChangeVisibility: sinon.stub().returns({ dispose: sinon.stub() }),
      show: sinon.stub(),
      title: undefined,
      description: undefined,
      badge: undefined
    } as any;

    mockTerminal = {
      show: sinon.stub(),
      dispose: sinon.stub(),
      name: 'SAF Archive - test-solution',
      sendText: sinon.stub()
    };

    createTerminalStub = vscode.window.createTerminal as sinon.SinonStub;
    createTerminalStub.reset();
    createTerminalStub.returns(mockTerminal);
    (vscode.window.terminals as any) = [];

    // Reset shared stubs from the mock
    (vscode.window.showInformationMessage as sinon.SinonStub).reset();
    (vscode.window.showErrorMessage as sinon.SinonStub).reset();
    (vscode.window.showWarningMessage as sinon.SinonStub).reset();
    (vscode.window.showWarningMessage as sinon.SinonStub).resolves('Proceed');
    (vscode.window.showOpenDialog as sinon.SinonStub).reset();
    (vscode.window.createStatusBarItem as sinon.SinonStub).reset();
    (vscode.window.createStatusBarItem as sinon.SinonStub).returns({
      text: '', tooltip: '', command: undefined,
      show: sinon.stub(), hide: sinon.stub(), dispose: sinon.stub()
    });

    getSolutionsStub = sinon.stub(SAFSolutionsProvider.getInstance(), 'getSAFSolutions').resolves([
      { name: 'test-solution', rootDirectory: '/path/to/solution', displayName: 'Test Solution' }
    ]);

    sinon.stub(StorageService, 'getSafCliTerminalCommand').returns('saf');
    sinon.stub(StorageService, 'getSelectedSolution').returns(undefined);

    executeCommandInTerminalStub = sinon.stub(terminalUtils, 'executeCommandInTerminal').resolves();

    sinon.stub((ArchiveSolutionProvider.prototype as any), '_getHtmlForWebview').returns(STUB_HTML);

    provider = ArchiveSolutionProvider.getInstance(mockExtensionUri);
  });

  afterEach(async () => {
    // Flush delayed loadSolutions callbacks scheduled during resolveWebviewView.
    await clock.runAllAsync();
    clock.restore();
    sinon.restore();
    messageHandler = undefined;
    ArchiveSolutionProvider.resetInstance();
  });

  describe('getInstance', () => {
    it('should return the same instance on subsequent calls', () => {
      const first = ArchiveSolutionProvider.getInstance(mockExtensionUri);
      const second = ArchiveSolutionProvider.getInstance();
      expect(first).to.equal(second);
    });

    it('should throw if called without extensionUri before initialization', () => {
      ArchiveSolutionProvider.resetInstance();
      expect(() => ArchiveSolutionProvider.getInstance()).to.throw(
        'ArchiveSolutionProvider: extensionUri is required on first call to getInstance()'
      );
    });
  });

  describe('resolveWebviewView', () => {
    it('should configure webview options with enableScripts', () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      expect(mockWebview.options).to.deep.include({ enableScripts: true });
      expect(mockWebview.options.localResourceRoots).to.include(mockExtensionUri);
    });

    it('should set HTML content from the webview template', () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      expect(mockWebview.html).to.equal(STUB_HTML);
    });
  });

  describe('preselectSolution', () => {
    it('should post preselect-solution message when view is active', () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      provider.preselectSolution('my-solution', '/path/to/solution');

      const call = (mockWebview.postMessage as sinon.SinonStub).getCalls().find(
        c => c.args[0]?.type === 'preselect-solution'
      );
      expect(call).to.exist;
      expect(call!.args[0].selectedSolution).to.equal('my-solution');
      expect(call!.args[0].rootDirectory).to.equal('/path/to/solution');
      expect(call!.args[0].resetFilename).to.equal(true);
      expect(call!.args[0].resetExtension).to.equal(true);
    });

    it('should not throw when view has not been resolved yet', () => {
      expect(() => provider.preselectSolution('my-solution')).to.not.throw();
    });
  });

  describe('setSelectedSolutionFromStorage', () => {
    it('should post set-selected-solution with rootDirectory when a solution is stored', () => {
      (StorageService.getSelectedSolution as sinon.SinonStub).returns({
        name: 'stored-solution',
        displayName: 'Stored Solution',
        path: '/stored/path/to/solution'
      });

      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      const calls = (mockWebview.postMessage as sinon.SinonStub).getCalls();
      const msg = calls.find(c => c.args[0]?.type === 'set-selected-solution')?.args[0];
      expect(msg).to.exist;
      expect(msg.selectedSolution).to.equal('stored-solution');
      expect(msg.displayName).to.equal('Stored Solution');
      expect(msg.rootDirectory).to.equal('/stored/path/to/solution');
    });

    it('should not post set-selected-solution when no solution is in storage', () => {
      (StorageService.getSelectedSolution as sinon.SinonStub).returns(undefined);

      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      const calls = (mockWebview.postMessage as sinon.SinonStub).getCalls();
      const msg = calls.find(c => c.args[0]?.type === 'set-selected-solution');
      expect(msg).to.not.exist;
    });
  });

  describe('archiveSolution', () => {
    it('should run the archive command with no options', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await provider.archiveSolution('test-solution', {});

      expect(executeCommandInTerminalStub.calledOnce).to.be.true;
      const [, command] = executeCommandInTerminalStub.firstCall.args;
      expect(command).to.equal('saf archive /path/to/solution');
    });

    it('should append --path when outputPath is provided', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await provider.archiveSolution('test-solution', { outputPath: '/out/dir' });

      const [, command] = executeCommandInTerminalStub.firstCall.args;
      expect(command).to.include('--path /out/dir');
    });

    it('should append --filename when filename is provided', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await provider.archiveSolution('test-solution', { filename: 'my-archive' });

      const [, command] = executeCommandInTerminalStub.firstCall.args;
      expect(command).to.include('--filename my-archive');
    });

    it('should append --extension when extension is provided', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await provider.archiveSolution('test-solution', { extension: '.zip' });

      const [, command] = executeCommandInTerminalStub.firstCall.args;
      expect(command).to.include('--extension .zip');
    });

    it('should build full args list with all options', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await provider.archiveSolution('test-solution', {
        outputPath: '/out/dir',
        filename: 'my-archive',
        extension: '.tar.gz'
      });

      const [, command] = executeCommandInTerminalStub.firstCall.args;
      expect(command).to.equal('saf archive /path/to/solution --path /out/dir --filename my-archive --extension .tar.gz');
    });

    it('should show error when solution is not found', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await provider.archiveSolution('nonexistent-solution', {});

      expect((vscode.window.showErrorMessage as sinon.SinonStub).calledOnce).to.be.true;
      const errorMsg = (vscode.window.showErrorMessage as sinon.SinonStub).firstCall.args[0];
      expect(errorMsg).to.include("'nonexistent-solution'");
      expect(executeCommandInTerminalStub.called).to.be.false;
    });

    it('should show success message after archiving', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await provider.archiveSolution('test-solution', {});

      expect((vscode.window.showInformationMessage as sinon.SinonStub).calledOnce).to.be.true;
      const msg = (vscode.window.showInformationMessage as sinon.SinonStub).firstCall.args[0];
      expect(msg).to.include('test-solution');
    });

    it('should show error message when archiving fails', async () => {
      executeCommandInTerminalStub.rejects(new Error('terminal error'));
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await provider.archiveSolution('test-solution', {});

      expect((vscode.window.showErrorMessage as sinon.SinonStub).calledOnce).to.be.true;
      const errorMsg = (vscode.window.showErrorMessage as sinon.SinonStub).firstCall.args[0];
      expect(errorMsg).to.include('Failed to archive solution');
    });

    it('should reject extension that does not start with a dot', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await provider.archiveSolution('test-solution', { extension: 'zip' });

      expect((vscode.window.showErrorMessage as sinon.SinonStub).calledOnce).to.be.true;
      const errorMsg = (vscode.window.showErrorMessage as sinon.SinonStub).firstCall.args[0];
      expect(errorMsg).to.include("Extension must start with '.'.");
      expect(executeCommandInTerminalStub.called).to.be.false;
    });

    it('should accept extension that starts with a dot', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await provider.archiveSolution('test-solution', { extension: '.saf' });

      expect(executeCommandInTerminalStub.calledOnce).to.be.true;
      const [, command] = executeCommandInTerminalStub.firstCall.args;
      expect(command).to.include('--extension .saf');
    });

    it('should dispose existing terminal with the same name before creating new one', async () => {
      const existingTerminal = { name: 'SAF Archive - test-solution', dispose: sinon.stub(), show: sinon.stub() };
      (vscode.window.terminals as any) = [existingTerminal];
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await provider.archiveSolution('test-solution', {});

      expect(existingTerminal.dispose.calledOnce).to.be.true;
      expect(createTerminalStub.calledOnce).to.be.true;
    });

    it('should prevent concurrent archiving and show warning on second call', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      // Start first call (outputPath outside root avoids the output-inside-root prompt)
      let resolveFirst!: () => void;
      executeCommandInTerminalStub.returns(new Promise<void>(res => { resolveFirst = res; }));
      const first = provider.archiveSolution('test-solution', { outputPath: '/out/dir' });

      // Second call while first is in progress
      await provider.archiveSolution('test-solution', { outputPath: '/out/dir' });

      expect((vscode.window.showWarningMessage as sinon.SinonStub).calledOnce).to.be.true;
      const warnMsg = (vscode.window.showWarningMessage as sinon.SinonStub).firstCall.args[0];
      expect(warnMsg).to.include('already in progress');
      expect(executeCommandInTerminalStub.calledOnce).to.be.true;

      resolveFirst();
      await first;
    });

    it('should send set-archiving-state true before and false after archive', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await provider.archiveSolution('test-solution', { outputPath: '/out/dir' });

      const messages = (mockWebview.postMessage as sinon.SinonStub).getCalls().map(c => c.args[0]);
      const startMsg = messages.find(m => m.type === 'set-archiving-state' && m.archiving === true);
      const doneMsg = messages.find(m => m.type === 'set-archiving-state' && m.archiving === false);
      expect(startMsg).to.exist;
      expect(doneMsg).to.exist;
    });

    it('should send set-archiving-state false even when archiving fails', async () => {
      executeCommandInTerminalStub.rejects(new Error('terminal error'));
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await provider.archiveSolution('test-solution', { outputPath: '/out/dir' });

      const messages = (mockWebview.postMessage as sinon.SinonStub).getCalls().map(c => c.args[0]);
      const doneMsg = messages.find(m => m.type === 'set-archiving-state' && m.archiving === false);
      expect(doneMsg).to.exist;
    });

    it('should warn when output path is inside the solution root and cancel if user declines', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);
      (vscode.window.showWarningMessage as sinon.SinonStub).resolves('Cancel');

      // outputPath is a subdirectory of /path/to/solution
      await provider.archiveSolution('test-solution', { outputPath: '/path/to/solution/output' });

      expect((vscode.window.showWarningMessage as sinon.SinonStub).calledOnce).to.be.true;
      expect(executeCommandInTerminalStub.called).to.be.false;
    });

    it('should warn when output path equals the solution root and proceed if user confirms', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);
      (vscode.window.showWarningMessage as sinon.SinonStub).resolves('Proceed');

      await provider.archiveSolution('test-solution', { outputPath: '/path/to/solution' });

      expect((vscode.window.showWarningMessage as sinon.SinonStub).calledOnce).to.be.true;
      expect(executeCommandInTerminalStub.calledOnce).to.be.true;
    });

    it('should not warn when output path is outside the solution root', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await provider.archiveSolution('test-solution', { outputPath: '/out/dir' });

      expect((vscode.window.showWarningMessage as sinon.SinonStub).called).to.be.false;
      expect(executeCommandInTerminalStub.calledOnce).to.be.true;
    });

    it('should create status bar item when archive starts and dispose it after success', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);
      const mockStatusBar = (vscode.window.createStatusBarItem as sinon.SinonStub).returnValues[0] ||
        (vscode.window.createStatusBarItem as sinon.SinonStub)();
      (vscode.window.createStatusBarItem as sinon.SinonStub).reset();
      const fakeStatusBar = { text: '', tooltip: '', show: sinon.stub(), dispose: sinon.stub() } as any;
      (vscode.window.createStatusBarItem as sinon.SinonStub).returns(fakeStatusBar);

      await provider.archiveSolution('test-solution', { outputPath: '/out/dir' });

      expect((vscode.window.createStatusBarItem as sinon.SinonStub).calledOnce).to.be.true;
      expect(fakeStatusBar.show.calledOnce).to.be.true;
      expect(fakeStatusBar.dispose.calledOnce).to.be.true;
    });

    it('should dispose status bar item even when archiving fails', async () => {
      executeCommandInTerminalStub.rejects(new Error('terminal error'));
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);
      const fakeStatusBar = { text: '', tooltip: '', show: sinon.stub(), dispose: sinon.stub() } as any;
      (vscode.window.createStatusBarItem as sinon.SinonStub).returns(fakeStatusBar);

      await provider.archiveSolution('test-solution', { outputPath: '/out/dir' });

      expect(fakeStatusBar.dispose.calledOnce).to.be.true;
    });

    it('should show cancellation warning and dispose terminal when progress token fires', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      (vscode.window.withProgress as sinon.SinonStub).callsFake(async (_opts: any, task: any) => {
        const progress = { report: sinon.stub() };
        let cancelHandler: (() => void) | undefined;
        const token = {
          isCancellationRequested: false,
          onCancellationRequested: (handler: () => void) => {
            cancelHandler = handler;
            return { dispose: sinon.stub() };
          }
        };
        executeCommandInTerminalStub.callsFake(() => {
          cancelHandler?.();
          return Promise.resolve();
        });
        return task(progress, token);
      });

      await provider.archiveSolution('test-solution', { outputPath: '/out/dir' });

      expect(mockTerminal.dispose.calledOnce).to.be.true;
      expect((vscode.window.showInformationMessage as sinon.SinonStub).called).to.be.false;
      expect((vscode.window.showWarningMessage as sinon.SinonStub).calledOnce).to.be.true;
      const warnArg = (vscode.window.showWarningMessage as sinon.SinonStub).firstCall.args[0];
      expect(warnArg).to.include('cancelled');
    });
  });

  describe('webview message handling', () => {
    it('should call archiveSolution when archive-solution message is received', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);
      const archiveStub = sinon.stub(provider, 'archiveSolution').resolves();

      await messageHandler?.({
        command: 'archive-solution',
        solutionName: 'test-solution',
        options: { extension: '.zip' }
      });

      expect(archiveStub.calledOnceWith('test-solution', { extension: '.zip' })).to.be.true;
    });

    it('should show error when show-error message is received', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await messageHandler?.({ command: 'show-error', message: 'Something went wrong' });

      expect((vscode.window.showErrorMessage as sinon.SinonStub).calledOnce).to.be.true;
      expect((vscode.window.showErrorMessage as sinon.SinonStub).firstCall.args[0]).to.equal('Something went wrong');
    });

    it('should call showOpenDialog when browse-output-path message is received', async () => {
      (vscode.window.showOpenDialog as sinon.SinonStub).resolves(undefined);
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await messageHandler?.({ command: 'browse-output-path' });

      expect((vscode.window.showOpenDialog as sinon.SinonStub).calledOnce).to.be.true;
      const dialogOpts = (vscode.window.showOpenDialog as sinon.SinonStub).firstCall.args[0];
      expect(dialogOpts.canSelectFolders).to.be.true;
      expect(dialogOpts.canSelectFiles).to.be.false;
    });

    it('should post output-path-selected message when folder is chosen', async () => {
      const selectedUri = vscode.Uri.file('/chosen/output');
      (vscode.window.showOpenDialog as sinon.SinonStub).resolves([selectedUri]);
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await messageHandler?.({ command: 'browse-output-path' });

      const call = (mockWebview.postMessage as sinon.SinonStub).getCalls().find(
        c => c.args[0]?.type === 'output-path-selected'
      );
      expect(call).to.exist;
      expect(call!.args[0].path).to.equal(selectedUri.fsPath);
    });
  });
});
