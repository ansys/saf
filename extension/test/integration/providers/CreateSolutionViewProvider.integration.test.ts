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
import { CreateSolutionViewProvider } from '../../../src/providers/CreateSolutionViewProvider';
import { SAFSolutionsProvider } from '../../../src/providers/SAFSolutionsProvider';
import {
  createTempTestDir,
  generateUniqueNamespace,
  generateUniqueSolutionName,
  mockExtensionContext,
  // mochaHooks as integrationHooks
} from '../setup.integration';

describe('CreateSolutionViewProvider Integration Tests', () => {
  let messageHandler: ((message: any) => Promise<void>) | undefined;

  beforeEach(() => {
    messageHandler = undefined;
  });

  afterEach(() => {
    sinon.restore();
  });

  function createMockWebviewView(): vscode.WebviewView {
    const mockWebview = {
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

    return {
      webview: mockWebview,
      viewType: CreateSolutionViewProvider.viewType,
      visible: true,
      onDidDispose: sinon.stub().returns({ dispose: sinon.stub() }),
      onDidChangeVisibility: sinon.stub().returns({ dispose: sinon.stub() }),
      show: sinon.stub(),
      title: undefined,
      description: undefined,
      badge: undefined
    } as any;
  }

  it('pre-fills the CLI defaults in the form', async function () {
    const provider = new CreateSolutionViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
    const mockWebviewView = createMockWebviewView();

    provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

    const html = (mockWebviewView.webview as any).html as string;
    expect(html).to.match(/id="solution-name"[^>]*value="my_solution"/);
    expect(html).to.match(/id="display-name"[^>]*value="My Solution"/);
    expect(html).to.match(/id="namespace"[^>]*value="saf\.solutions"/);
    expect(html).to.include('<option value="dash" selected>dash</option>');
  });

  it('creates a solution with dash UI and user selects "Don\'t open"', async function () {
    const tempDir = createTempTestDir();
    const solutionName = generateUniqueSolutionName('webview-dash');
    const displayName = `Webview Dash ${solutionName}`;
    const namespace = generateUniqueNamespace();
    const provider = new CreateSolutionViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
    const mockWebviewView = createMockWebviewView();

    const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage')
      .resolves('Don\'t open' as any);
    const executeCommandStub = sinon.stub(vscode.commands, 'executeCommand').resolves();

    provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

    await messageHandler?.({
      command: 'create-solution',
      config: {
        name: solutionName,
        displayName,
        uiType: 'dash',
        namespace,
        targetDirectory: tempDir
      }
    });

    const solutionPath = path.join(tempDir, solutionName);
    const solutionNameDir = solutionName.replace(/-/g, '_');
    const namespaceParts = namespace.split('.');
    const definitionPath = path.join(
      solutionPath,
      'src',
      ...namespaceParts,
      solutionNameDir,
      'solution',
      'definition.py'
    );

    expect(fs.existsSync(definitionPath)).to.equal(true, 'definition.py should exist for dash solution');

    const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();
    const createdSolution = solutions.find(solution => solution.name === solutionName);

    expect(createdSolution, 'SAF solutions should include newly created solution').to.not.be.undefined;
    expect(createdSolution?.rootDirectory).to.equal(solutionPath);

    expect(showInformationMessageStub.calledOnce).to.be.true;
    expect(showInformationMessageStub.firstCall.args[0]).to.equal('Solution created successfully! Would you like to open it?');
    expect(executeCommandStub.called).to.be.false; // User chose not to open
  });

  it('creates a solution and opens it in current window', async function () {
    const tempDir = createTempTestDir();
    const solutionName = generateUniqueSolutionName('webview-current');
    const namespace = generateUniqueNamespace();
    const displayName = `Webview Current ${solutionName}`;
    const provider = new CreateSolutionViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
    const mockWebviewView = createMockWebviewView();

    const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage')
      .resolves('Open in current window' as any);
    const executeCommandStub = sinon.stub(vscode.commands, 'executeCommand').resolves();

    provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

    await messageHandler?.({
      command: 'create-solution',
      config: {
        name: solutionName,
        displayName,
        uiType: 'dash',
        namespace,
        targetDirectory: tempDir
      }
    });

    const solutionPath = path.join(tempDir, solutionName);

    expect(showInformationMessageStub.calledOnce).to.be.true;
    expect(executeCommandStub.calledOnce).to.be.true;
    expect(executeCommandStub.firstCall.args[0]).to.equal('vscode.openFolder');
    expect(executeCommandStub.firstCall.args[1].fsPath.toLowerCase()).to.equal(solutionPath.toLowerCase());
    expect(executeCommandStub.firstCall.args[2]).to.be.undefined; // No forceNewWindow option
  });

  it('creates a solution and opens it in new window', async function () {
    const tempDir = createTempTestDir();
    const solutionName = generateUniqueSolutionName('webview-new');
    const namespace = generateUniqueNamespace();
    const displayName = `Webview New ${solutionName}`;
    const provider = new CreateSolutionViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
    const mockWebviewView = createMockWebviewView();

    const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage')
      .resolves('Open in new window' as any);
    const executeCommandStub = sinon.stub(vscode.commands, 'executeCommand').resolves();

    provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

    await messageHandler?.({
      command: 'create-solution',
      config: {
        name: solutionName,
        displayName,
        uiType: 'dash',
        namespace,
        targetDirectory: tempDir
      }
    });

    const solutionPath = path.join(tempDir, solutionName);

    expect(showInformationMessageStub.calledOnce).to.be.true;
    expect(executeCommandStub.calledOnce).to.be.true;
    expect(executeCommandStub.firstCall.args[0]).to.equal('vscode.openFolder');
    expect(executeCommandStub.firstCall.args[1].fsPath.toLowerCase()).to.equal(solutionPath.toLowerCase());
    expect(executeCommandStub.firstCall.args[2]).to.deep.equal({ forceNewWindow: true });
  });

  it('creates a solution with no UI framework', async function () {
    const tempDir = createTempTestDir();
    const solutionName = generateUniqueSolutionName('webview-none');
    const namespace = generateUniqueNamespace();
    const displayName = `Webview None ${solutionName}`;
    const provider = new CreateSolutionViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
    const mockWebviewView = createMockWebviewView();

    const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage')
      .resolves('Don\'t open' as any);
    const executeCommandStub = sinon.stub(vscode.commands, 'executeCommand').resolves();

    provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

    await messageHandler?.({
      command: 'create-solution',
      config: {
        name: solutionName,
        displayName,
        uiType: 'none',
        namespace,
        targetDirectory: tempDir
      }
    });

    const solutionPath = path.join(tempDir, solutionName);
    const solutionNameDir = solutionName.replace(/-/g, '_');
    const namespaceParts = namespace.split('.');
    const definitionPath = path.join(
      solutionPath,
      'src',
      ...namespaceParts,
      solutionNameDir,
      'solution',
      'definition.py'
    );
    const uiPath = path.join(
      solutionPath,
      'src',
      ...namespaceParts,
      solutionNameDir,
      'ui'
    );

    expect(fs.existsSync(definitionPath)).to.equal(true, 'definition.py should exist for none UI solution');
    expect(fs.existsSync(uiPath)).to.equal(false, 'UI folder should not exist for none UI solution');
    expect(showInformationMessageStub.calledOnce).to.be.true;
    expect(executeCommandStub.called).to.be.false;
  });

  describe('Edge Cases - Invalid Solution Names', () => {
    it('rejects solution name with special characters', async function () {
      const tempDir = createTempTestDir();
      const invalidName = 'my@solution#test';
      const namespace = generateUniqueNamespace();
      const displayName = 'Invalid Solution';
      const provider = new CreateSolutionViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
      const mockWebviewView = createMockWebviewView();

      const showErrorMessageStub = sinon.stub(vscode.window, 'showErrorMessage').resolves();
      const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage').resolves();

      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await messageHandler?.({
        command: 'create-solution',
        config: {
          name: invalidName,
          displayName,
          uiType: 'dash',
          namespace,
          targetDirectory: tempDir
        }
      });

      expect(showErrorMessageStub.called).to.be.true;
      const errorMessage = showErrorMessageStub.firstCall.args[0];
      expect(errorMessage.toLowerCase()).to.match(/solution name can only contain letters, numbers, hyphens and underscores\./);

      const files = fs.existsSync(tempDir) ? fs.readdirSync(tempDir) : [];
      expect(files.length).to.equal(0, 'No files should be created in temp directory');
      expect(showInformationMessageStub.called).to.be.false;
    });

    it('rejects solution name with spaces', async function () {
      const tempDir = createTempTestDir();
      const invalidName = 'solution with spaces';
      const namespace = generateUniqueNamespace();
      const displayName = 'Invalid Solution';
      const provider = new CreateSolutionViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
      const mockWebviewView = createMockWebviewView();

      const showErrorMessageStub = sinon.stub(vscode.window, 'showErrorMessage').resolves();
      const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage').resolves();

      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await messageHandler?.({
        command: 'create-solution',
        config: {
          name: invalidName,
          displayName,
          uiType: 'dash',
          namespace,
          targetDirectory: tempDir
        }
      });

      expect(showErrorMessageStub.called).to.be.true;
      const errorMessage = showErrorMessageStub.firstCall.args[0];
      expect(errorMessage.toLowerCase()).to.match(/solution name can only contain letters, numbers, hyphens and underscores\./);

      const files = fs.existsSync(tempDir) ? fs.readdirSync(tempDir) : [];
      expect(files.length).to.equal(0, 'No files should be created in temp directory');
      expect(showInformationMessageStub.called).to.be.false;
    });

    it('rejects empty solution name', async function () {
      const tempDir = createTempTestDir();
      const invalidName = '';
      const namespace = generateUniqueNamespace();
      const displayName = 'Invalid Solution';
      const provider = new CreateSolutionViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
      const mockWebviewView = createMockWebviewView();

      const showErrorMessageStub = sinon.stub(vscode.window, 'showErrorMessage').resolves();
      const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage').resolves();

      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await messageHandler?.({
        command: 'create-solution',
        config: {
          name: invalidName,
          displayName,
          uiType: 'dash',
          namespace,
          targetDirectory: tempDir
        }
      });

      expect(showErrorMessageStub.called).to.be.true;
      const errorMessage = showErrorMessageStub.firstCall.args[0];
      expect(errorMessage.toLowerCase()).to.match(/invalid|error|failed|required|empty/);

      const files = fs.existsSync(tempDir) ? fs.readdirSync(tempDir) : [];
      expect(files.length).to.equal(0, 'No files should be created in temp directory');
      expect(showInformationMessageStub.called).to.be.false;
    });
  });

  describe('Edge Cases - Missing Required Fields', () => {
    it('rejects missing targetDirectory', async function () {
      const solutionName = generateUniqueSolutionName('missing-target');
      const namespace = generateUniqueNamespace();
      const displayName = 'Missing Target';
      const provider = new CreateSolutionViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
      const mockWebviewView = createMockWebviewView();

      const showErrorMessageStub = sinon.stub(vscode.window, 'showErrorMessage').resolves();
      const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage').resolves();

      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await messageHandler?.({
        command: 'create-solution',
        config: {
          name: solutionName,
          displayName,
          uiType: 'dash',
          namespace,
          targetDirectory: ''
        }
      });

      expect(showErrorMessageStub.called).to.be.true;
      const errorMessage = showErrorMessageStub.firstCall.args[0];
      expect(errorMessage.toLowerCase()).to.match(/invalid|error|failed|required|directory/);
      expect(showInformationMessageStub.called).to.be.false;
    });

    it('rejects missing displayName', async function () {
      const tempDir = createTempTestDir();
      const solutionName = generateUniqueSolutionName('missing-display');
      const namespace = generateUniqueNamespace();
      const provider = new CreateSolutionViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
      const mockWebviewView = createMockWebviewView();

      const showErrorMessageStub = sinon.stub(vscode.window, 'showErrorMessage').resolves();
      const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage').resolves();

      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await messageHandler?.({
        command: 'create-solution',
        config: {
          name: solutionName,
          displayName: '',
          uiType: 'dash',
          namespace,
          targetDirectory: tempDir
        }
      });

      expect(showErrorMessageStub.called).to.be.true;
      const errorMessage = showErrorMessageStub.firstCall.args[0];
      expect(errorMessage.toLowerCase()).to.match(/all fields are required: solution name, display name, namespace, target directory, and ui type\./);

      const files = fs.existsSync(tempDir) ? fs.readdirSync(tempDir) : [];
      expect(files.length).to.equal(0, 'No files should be created in temp directory');
      expect(showInformationMessageStub.called).to.be.false;
    });

    it('rejects missing uiType', async function () {
      const tempDir = createTempTestDir();
      const solutionName = generateUniqueSolutionName('missing-ui');
      const namespace = generateUniqueNamespace();
      const displayName = 'Missing UI Type';
      const provider = new CreateSolutionViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
      const mockWebviewView = createMockWebviewView();

      const showErrorMessageStub = sinon.stub(vscode.window, 'showErrorMessage').resolves();
      const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage').resolves();

      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await messageHandler?.({
        command: 'create-solution',
        config: {
          name: solutionName,
          displayName,
          uiType: '',
          namespace,
          targetDirectory: tempDir
        }
      });

      expect(showErrorMessageStub.called).to.be.true;
      const errorMessage = showErrorMessageStub.firstCall.args[0];
      expect(errorMessage.toLowerCase()).to.match(/all fields are required: solution name, display name, namespace, target directory, and ui type\./);

      const files = fs.existsSync(tempDir) ? fs.readdirSync(tempDir) : [];
      expect(files.length).to.equal(0, 'No files should be created in temp directory');
      expect(showInformationMessageStub.called).to.be.false;
    });
  });

  describe('Edge Cases - Non-existent Target Directory', () => {
    it('handles non-existent target directory gracefully', async function () {
      const invalidTargetDir = path.join('/', 'invalid', 'nonexistent', 'path');
      const solutionName = generateUniqueSolutionName('invalid-path');
      const namespace = generateUniqueNamespace();
      const displayName = 'Invalid Path';
      const provider = new CreateSolutionViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
      const mockWebviewView = createMockWebviewView();

      const showErrorMessageStub = sinon.stub(vscode.window, 'showErrorMessage').resolves();
      const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage').resolves();

      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await messageHandler?.({
        command: 'create-solution',
        config: {
          name: solutionName,
          displayName,
          uiType: 'dash',
          namespace,
          targetDirectory: invalidTargetDir
        }
      });

      expect(showErrorMessageStub.called).to.be.true;
      const errorMessage = showErrorMessageStub.firstCall.args[0];
      expect(errorMessage.toLowerCase()).to.match(/failed to create solution using saf cli: enoent: no such file or directory/);

      const solutionPath = path.join(invalidTargetDir, solutionName);
      expect(fs.existsSync(solutionPath)).to.equal(false, 'No solution directory should be created');
      expect(showInformationMessageStub.called).to.be.false;
    });
  });

  it('rejects invalid namespace format', async function () {
    const tempDir = createTempTestDir();
    const solutionName = generateUniqueSolutionName('invalid-namespace');
    const displayName = 'Invalid Namespace';
    const invalidNamespace = 'Invalid Namespace With Spaces';
    const provider = new CreateSolutionViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
    const mockWebviewView = createMockWebviewView();
    const showErrorMessageStub = sinon.stub(vscode.window, 'showErrorMessage').resolves();
    const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage').resolves();

    provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

    await messageHandler?.({
      command: 'create-solution',
      config: {
        name: solutionName,
        displayName,
        uiType: 'dash',
        namespace: invalidNamespace,
        targetDirectory: tempDir
      }
    });
    expect(showErrorMessageStub.called).to.be.true;
    const errorMessage = showErrorMessageStub.firstCall.args[0];
    expect(errorMessage.toLowerCase()).to.match(/each segment of the namespace must be in lowercase/);
    expect(showInformationMessageStub.called).to.be.false;
    showErrorMessageStub.restore();
    showInformationMessageStub.restore();
  });
});
