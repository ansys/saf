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
import * as childProcess from 'node:child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as sinon from 'sinon';
import * as vscode from 'vscode';
import { ArchiveSolutionProvider } from '../../../src/providers/ArchiveSolutionProvider';
import { StorageService } from '../../../src/services/StorageService';
import * as terminalUtils from '../../../src/utils/terminalUtils';
import {
  createTempTestDir,
  mockExtensionContext,
  mochaGlobalSetup as integrationSetup,
  mochaGlobalTeardown as integrationTeardown
} from '../setup.integration';
import { createTestSolution } from '../testHelpers';

export const mochaHooks = {
  beforeAll: integrationSetup,
  afterAll: integrationTeardown
};

describe('ArchiveSolutionProvider Integration Tests', () => {
  let messageHandler: ((message: any) => Promise<void>) | undefined;
  let sharedSolutionName: string;
  let sharedSolutionPath: string;

  function createMockWebviewView(): vscode.WebviewView {
    const mockWebview = {
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
      viewType: ArchiveSolutionProvider.viewType,
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
    this.timeout(30000);

    const { solutionName, createdSolutionPath } = await createTestSolution(
      'archive-shared',
      'Archive Shared Solution'
    );
    sharedSolutionName = solutionName;
    sharedSolutionPath = createdSolutionPath;
  });

  afterEach(() => {
    sinon.restore();
    messageHandler = undefined;
    ArchiveSolutionProvider.resetInstance();
  });

  it('executes archive command with selected options', async function () {
    this.timeout(15000);
    const provider = ArchiveSolutionProvider.getInstance(vscode.Uri.file(mockExtensionContext.extensionPath));
    const view = createMockWebviewView();

    const execStub = sinon.stub(terminalUtils, 'executeCommandInTerminal').resolves();
    sinon.stub(vscode.window, 'showInformationMessage').resolves(undefined);

    provider.resolveWebviewView(view, {} as any, {} as any);

    await messageHandler?.({
      command: 'archive-solution',
      solutionName: sharedSolutionName,
      options: {
        outputPath: path.join(path.dirname(sharedSolutionPath), 'archive out dir'),
        filename: 'artifact name',
        extension: '.zip'
      }
    });

    expect(execStub.calledOnce).to.be.true;
    const [, command] = execStub.firstCall.args as [vscode.Terminal, string];
    expect(command).to.include(` archive ${sharedSolutionPath}`);
    expect(command).to.include('--path');
    expect(command).to.include('out dir');
    expect(command).to.include('--filename');
    expect(command).to.include('artifact name');
    expect(command).to.include('--extension .zip');
  });

  it('queues preselectSolution before resolve and posts when view resolves', () => {
    const provider = ArchiveSolutionProvider.getInstance(vscode.Uri.file(mockExtensionContext.extensionPath));
    const view = createMockWebviewView();

    provider.preselectSolution(sharedSolutionName, sharedSolutionPath);
    provider.resolveWebviewView(view, {} as any, {} as any);

    const postCalls = (view.webview.postMessage as sinon.SinonStub).getCalls();
    const preselectCall = postCalls.find(c => c.args[0]?.type === 'preselect-solution');
    expect(preselectCall).to.not.be.undefined;
    expect(preselectCall?.args[0].selectedSolution).to.equal(sharedSolutionName);
    expect(preselectCall?.args[0].rootDirectory).to.equal(sharedSolutionPath);
  });

  it('posts output-path-selected when browse-output-path chooses a folder', async () => {
    const provider = ArchiveSolutionProvider.getInstance(vscode.Uri.file(mockExtensionContext.extensionPath));
    const view = createMockWebviewView();
    const selectedUri = vscode.Uri.file(path.join(sharedSolutionPath, 'selected-output'));

    sinon.stub(vscode.window, 'showOpenDialog').resolves([selectedUri]);

    provider.resolveWebviewView(view, {} as any, {} as any);
    await messageHandler?.({ command: 'browse-output-path' });

    const postCalls = (view.webview.postMessage as sinon.SinonStub).getCalls();
    const outputCall = postCalls.find(c => c.args[0]?.type === 'output-path-selected');
    expect(outputCall).to.not.be.undefined;
    expect(outputCall?.args[0].path).to.equal(selectedUri.fsPath);
  });

  it('posts set-selected-solution with rootDirectory when a solution is stored', () => {
    const provider = ArchiveSolutionProvider.getInstance(vscode.Uri.file(mockExtensionContext.extensionPath));
    const view = createMockWebviewView();

    sinon.stub(StorageService, 'getSelectedSolution').returns({
      name: sharedSolutionName,
      displayName: `Archive Shared ${sharedSolutionName}`,
      path: sharedSolutionPath
    });

    provider.resolveWebviewView(view, {} as any, {} as any);

    const postCalls = (view.webview.postMessage as sinon.SinonStub).getCalls();
    const setSelectedCall = postCalls.find(c => c.args[0]?.type === 'set-selected-solution');
    expect(setSelectedCall).to.not.be.undefined;
    expect(setSelectedCall?.args[0].selectedSolution).to.equal(sharedSolutionName);
    expect(setSelectedCall?.args[0].rootDirectory).to.equal(sharedSolutionPath);
  });

  it('archives the solution and creates the archive file on disk', async function () {
    this.timeout(30000);

    const outputDir = createTempTestDir();
    const filename = 'workflow-test-archive';
    const extension = '.zip';

    const provider = ArchiveSolutionProvider.getInstance(vscode.Uri.file(mockExtensionContext.extensionPath));
    const view = createMockWebviewView();

    sinon.stub(terminalUtils, 'executeCommandInTerminal').callsFake(async (_terminal, command) => {
      await new Promise<void>((resolve, reject) => {
        const [shell, flag] = process.platform === 'win32'
          ? ['pwsh', '-Command']
          : ['bash', '-c'];
        const proc = childProcess.spawn(shell, [flag, command], { stdio: 'pipe' });
        proc.on('error', reject);
        proc.on('close', code => code === 0 ? resolve() : reject(new Error(`archive command exited with code ${code}`)));
      });
    });

    sinon.stub(vscode.window, 'showInformationMessage').resolves(undefined);
    provider.resolveWebviewView(view, {} as any, {} as any);

    await messageHandler?.({
      command: 'archive-solution',
      solutionName: sharedSolutionName,
      options: { outputPath: outputDir, filename, extension }
    });

    expect(fs.existsSync(path.join(outputDir, `${filename}${extension}`))).to.be.true;
  });

});
