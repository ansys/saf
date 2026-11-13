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
import { CreateSolutionViewProvider } from '../../../src/providers/CreateSolutionViewProvider';
import { StorageService } from '../../../src/services/StorageService';
import { solutionService } from '../../../src/services/SolutionService';
import { systemService } from '../../../src/services/SystemService';
import { SAFSolutionsProvider } from '../../../src/providers/SAFSolutionsProvider';
/**
 * Unit tests for CreateSolutionViewProvider class
 */
describe('CreateSolutionViewProvider', () => {
  let provider: CreateSolutionViewProvider;
  let mockExtensionUri: vscode.Uri;
  let mockWebviewView: vscode.WebviewView;
  let mockWebview: any;
  let messageHandler: ((message: any) => Promise<void>) | undefined;
  let storageServiceStub: sinon.SinonStub;
  let setLastTargetDirectoryStub: sinon.SinonStub;

  beforeEach(() => {
    mockExtensionUri = vscode.Uri.file('/mock/extension');

    // Create mock webview
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

    // Create mock webview view
    mockWebviewView = {
      webview: mockWebview,
      viewType: 'solutions-manager.createSolution',
      visible: true,
      onDidDispose: sinon.stub().returns({ dispose: sinon.stub() }),
      onDidChangeVisibility: sinon.stub().returns({ dispose: sinon.stub() }),
      show: sinon.stub(),
      title: undefined,
      description: undefined,
      badge: undefined
    } as any;

    // Stub StorageService methods
    storageServiceStub = sinon.stub(StorageService, 'getLastTargetDirectory');
    setLastTargetDirectoryStub = sinon.stub(StorageService, 'setLastTargetDirectory').resolves();

    provider = new CreateSolutionViewProvider(mockExtensionUri);
  });

  afterEach(() => {
    sinon.restore();
    messageHandler = undefined;
  });

  describe('resolveWebviewView', () => {
    it('should set webview options with enableScripts and localResourceRoots', () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      expect(mockWebview.options).to.deep.include({
        enableScripts: true
      });
      expect(mockWebview.options.localResourceRoots).to.include(mockExtensionUri);
    });

    it('should set webview HTML content', () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      expect(mockWebview.html).to.be.a('string');
      expect(mockWebview.html).to.include('Create new solution');
      expect(mockWebview.html).to.include('solution-name');
      expect(mockWebview.html).to.include('display-name');
    });

    it('should register message handler', () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      expect(mockWebview.onDidReceiveMessage.calledOnce).to.be.true;
      expect(messageHandler).to.not.be.undefined;
    });

    it('should include namespace command preview segment in webview script', () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      expect(mockWebview.html).to.include('if (namespace) command += \' --namespace \' + namespace;');
      expect(mockWebview.html).to.include('id="namespace"');
    });

    it('should prefill the CLI defaults in the form', () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      expect(mockWebview.html).to.match(/id="solution-name"[^>]*value="my_solution"/);
      expect(mockWebview.html).to.match(/id="display-name"[^>]*value="My Solution"/);
      expect(mockWebview.html).to.match(/id="namespace"[^>]*value="saf\.solutions"/);
      expect(mockWebview.html).to.include('<option value="dash" selected>dash</option>');
      expect(mockWebview.html).to.not.include('Select framework...');
    });

    it('should expose the defaults to the webview script', () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      expect(mockWebview.html).to.include(
        'const DEFAULTS = {"name":"my_solution","displayName":"My Solution","uiType":"dash","namespace":"saf.solutions"};'
      );
    });

    it('should restore the defaults when the form is reset', () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      expect(mockWebview.html).to.include('solutionNameInput.value = DEFAULTS.name;');
      expect(mockWebview.html).to.include('displayNameInput.value = DEFAULTS.displayName;');
      expect(mockWebview.html).to.include('uiTypeSelect.value = DEFAULTS.uiType;');
      expect(mockWebview.html).to.include('namespaceInput.value = DEFAULTS.namespace;');
      expect(mockWebview.html).to.include('displayNameManuallyEdited = false;');
    });

    it('should keep deriving the display name from the solution name until it is edited', () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      expect(mockWebview.html).to.include('if (!displayNameManuallyEdited && name) {');
      expect(mockWebview.html).to.include('name.split(/[-_]/)');
    });
  });

  describe('webview-ready message handler', () => {
    beforeEach(() => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);
    });

    it('should get last target directory from StorageService', async () => {
      storageServiceStub.returns('/saved/directory');

      await messageHandler?.({ command: 'webview-ready' });

      expect(storageServiceStub.calledOnce).to.be.true;
    });

    it('should post set-target-directory message when directory exists', async () => {
      storageServiceStub.returns('/saved/directory');

      await messageHandler?.({ command: 'webview-ready' });

      expect(mockWebview.postMessage.calledOnce).to.be.true;
      expect(mockWebview.postMessage.firstCall.args[0]).to.deep.equal({
        type: 'set-target-directory',
        path: '/saved/directory'
      });
    });

    it('should not post message when no directory is saved', async () => {
      storageServiceStub.returns(undefined);

      await messageHandler?.({ command: 'webview-ready' });

      expect(mockWebview.postMessage.called).to.be.false;
    });

    it('should handle null directory gracefully', async () => {
      storageServiceStub.returns(null);

      await messageHandler?.({ command: 'webview-ready' });

      expect(mockWebview.postMessage.called).to.be.false;
    });
  });

  describe('browse-folder message handler', () => {
    beforeEach(() => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);
      (vscode.window.showOpenDialog as sinon.SinonStub).reset();
    });

    it('should save selected directory to StorageService and post message', async () => {
      const mockUri = vscode.Uri.file('/selected/directory');
      (vscode.window.showOpenDialog as sinon.SinonStub).resolves([mockUri]);

      await messageHandler?.({ command: 'browse-folder' });

      expect(setLastTargetDirectoryStub.calledOnce).to.be.true;
      expect(setLastTargetDirectoryStub.firstCall.args[0]).to.equal('/selected/directory');
      expect(mockWebview.postMessage.calledOnce).to.be.true;
      expect(mockWebview.postMessage.firstCall.args[0]).to.deep.equal({
        type: 'set-target-directory',
        path: '/selected/directory'
      });
    });

    it('should not save or post message when user cancels dialog', async () => {
      (vscode.window.showOpenDialog as sinon.SinonStub).resolves(undefined);

      await messageHandler?.({ command: 'browse-folder' });

      expect(setLastTargetDirectoryStub.called).to.be.false;
      expect(mockWebview.postMessage.called).to.be.false;
    });
  });

  describe('message validation', () => {
    it('should validate required fields in create-solution', async () => {
        provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);
        const handleCliStub = sinon.stub(systemService, 'handleSAFCliInstallation').resolves();
        const createSolutionStub = sinon.stub(solutionService, 'createSolution').resolves();
        (vscode.window.showErrorMessage as sinon.SinonStub).reset();

        await messageHandler?.({
          command: 'create-solution',
          config: {
            name: 'test-solution',
            displayName: 'Test Solution',
            uiType: 'dash',
            targetDirectory: '/target'
          } as any
        });

        expect(handleCliStub.calledOnce).to.be.true;
        expect((vscode.window.showErrorMessage as sinon.SinonStub).calledOnce).to.be.true;

        const errorMessage = (vscode.window.showErrorMessage as sinon.SinonStub).firstCall.args[0] as string;
        expect(errorMessage).to.include('All fields are required');
        expect(errorMessage).to.include('namespace');

        expect(createSolutionStub.called).to.be.false;
    });

    it('should submit solution config', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      const handleCliStub = sinon.stub(systemService, 'handleSAFCliInstallation').resolves();
      const createSolutionStub = sinon.stub(solutionService, 'createSolution').resolves();
      const waitStub = sinon.stub(provider as any, 'waitForSolutionCreation').resolves();
      const refreshStub = sinon.stub();
      const getInstanceStub = sinon.stub(SAFSolutionsProvider, 'getInstance').returns({ refresh: refreshStub } as any);
      (vscode.window.showInformationMessage as sinon.SinonStub).resolves('Don\'t open');

      await messageHandler?.({
      command: 'create-solution',
      config: {
      name: 'test-solution',
      displayName: 'Test Solution',
      uiType: 'dash',
      namespace: 'saf.solutions',
      targetDirectory: '/target'
      }
      });

      expect(handleCliStub.calledOnce).to.be.true;
      expect(createSolutionStub.calledOnce).to.be.true;
      expect(waitStub.calledOnce).to.be.true;
      expect(getInstanceStub.calledOnce).to.be.true;
      expect(refreshStub.calledOnce).to.be.true;

      expect(createSolutionStub.firstCall.args[0]).to.deep.equal({
      name: 'test-solution',
      displayName: 'Test Solution',
      namespace: 'saf.solutions',
      uiType: 'dash',
      targetDirectory: '/target'
      });
      });

    it('should show error message from webview', async () => {
      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);
      (vscode.window.showErrorMessage as sinon.SinonStub).reset();

      await messageHandler?.({
        command: 'show-error',
        message: 'Test error message'
      });

      expect((vscode.window.showErrorMessage as sinon.SinonStub).calledOnce).to.be.true;
      expect((vscode.window.showErrorMessage as sinon.SinonStub).firstCall.args[0]).to.equal('Test error message');
    });
  });
});
