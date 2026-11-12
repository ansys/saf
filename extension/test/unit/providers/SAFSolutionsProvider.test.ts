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
import { SAFSolutionsProvider, SAFSolutionItem } from '../../../src/providers/SAFSolutionsProvider';
import { StorageService } from '../../../src/services/StorageService';
import * as execModule from '../../../src/utils/exec';
import * as fsUtils from '../../../src/utils/fsUtils';

/**
 * Unit tests for SAFSolutionsProvider class
 */
describe('SAFSolutionsProvider', () => {
  let execFileAsyncStub: sinon.SinonStub;
  let getSafCliExecutablePathStub: sinon.SinonStub;
  let fileExistsSyncStub: sinon.SinonStub;
  let showErrorMessageStub: sinon.SinonStub;

  beforeEach(() => {
    // Reset singleton before each test
    (SAFSolutionsProvider as any).instance = undefined;

    // Setup stubs
    execFileAsyncStub = sinon.stub(execModule, 'execFileAsync');
    getSafCliExecutablePathStub = sinon.stub(StorageService, 'getSafCliExecutablePath');
    fileExistsSyncStub = sinon.stub(fsUtils, 'fileExistsSync');
    showErrorMessageStub = vscode.window.showErrorMessage as sinon.SinonStub;
    showErrorMessageStub.reset();

    // Default returns
    getSafCliExecutablePathStub.returns('/test/venv/bin/saf');
    fileExistsSyncStub.returns(true);
  });

  afterEach(() => {
    sinon.restore();
  });

  describe('getSAFSolutions', () => {
    it('should return parsed array when SAF CLI executable exists and succeeds', async () => {
      const mockOutput = `my_solution
  Root Directory: /path/to/solution
  Display Name: My Solution
`;
      execFileAsyncStub.resolves({ stdout: mockOutput, stderr: '' });

      const provider = SAFSolutionsProvider.getInstance();
      const solutions = await provider.getSAFSolutions();

      expect(solutions).to.have.lengthOf(1);
      expect(solutions[0]).to.deep.equal({
        name: 'my_solution',
        rootDirectory: '/path/to/solution',
        displayName: 'My Solution'
      });
    });

    it('should handle multiple solutions in output', async () => {
      const mockOutput = `solution_one
  Root Directory: /path/one
  Display Name: Solution One
solution_two
  Root Directory: /path/two
  Display Name: Solution Two
`;
      execFileAsyncStub.resolves({ stdout: mockOutput, stderr: '' });

      const provider = SAFSolutionsProvider.getInstance();
      const solutions = await provider.getSAFSolutions();

      expect(solutions).to.have.lengthOf(2);
      expect(solutions[0].name).to.equal('solution_one');
      expect(solutions[1].name).to.equal('solution_two');
    });

    it('should return empty array when SAF CLI executable does not exist', async () => {
      fileExistsSyncStub.returns(false);

      const provider = SAFSolutionsProvider.getInstance();
      const solutions = await provider.getSAFSolutions();

      expect(solutions).to.deep.equal([]);
      expect(execFileAsyncStub.called).to.be.false;
    });

    it('should return empty array and show error message on execFileAsync failure', async () => {
      execFileAsyncStub.rejects(new Error('CLI execution failed'));

      const provider = SAFSolutionsProvider.getInstance();
      const solutions = await provider.getSAFSolutions();

      expect(solutions).to.deep.equal([]);
      expect(showErrorMessageStub.calledOnce).to.be.true;
      expect(showErrorMessageStub.firstCall.args[0]).to.include('Failed to get SAF solutions');
    });

    it('should call execFileAsync with correct arguments', async () => {
      execFileAsyncStub.resolves({ stdout: '', stderr: '' });

      const provider = SAFSolutionsProvider.getInstance();
      await provider.getSAFSolutions();

      expect(execFileAsyncStub.calledOnce).to.be.true;
      expect(execFileAsyncStub.firstCall.args[0]).to.equal('/test/venv/bin/saf');
      expect(execFileAsyncStub.firstCall.args[1]).to.deep.equal(['solutions']);
    });
  });

  describe('parseSAFOutput', () => {
    it('should parse single solution correctly', () => {
      const output = `sol1
  Root Directory: /path1
  Display Name: Sol One
`;
      const provider = SAFSolutionsProvider.getInstance();
      const solutions = (provider as any).parseSAFOutput(output);

      expect(solutions).to.have.lengthOf(1);
      expect(solutions[0]).to.deep.equal({
        name: 'sol1',
        rootDirectory: '/path1',
        displayName: 'Sol One'
      });
    });

    it('should parse multiple solutions correctly', () => {
      const output = `solution_a
  Root Directory: /path/a
  Display Name: Solution A
solution_b
  Root Directory: /path/b
  Display Name: Solution B
solution_c
  Root Directory: /path/c
  Display Name: Solution C
`;
      const provider = SAFSolutionsProvider.getInstance();
      const solutions = (provider as any).parseSAFOutput(output);

      expect(solutions).to.have.lengthOf(3);
      expect(solutions.map((s: any) => s.name)).to.deep.equal(['solution_a', 'solution_b', 'solution_c']);
    });

    it('should return empty array for empty input', () => {
      const provider = SAFSolutionsProvider.getInstance();
      const solutions = (provider as any).parseSAFOutput('');

      expect(solutions).to.deep.equal([]);
    });
  });

  describe('getTreeItem', () => {
    it('should return the element as-is', () => {
      const provider = SAFSolutionsProvider.getInstance();
      const item = new SAFSolutionItem(
        'test',
        '/test/path',
        'Test',
        vscode.TreeItemCollapsibleState.None
      );

      const result = provider.getTreeItem(item);

      expect(result).to.equal(item);
    });
  });

  describe('getChildren', () => {
    it('should return empty array when element is not undefined', async () => {
      const provider = SAFSolutionsProvider.getInstance();
      const item = new SAFSolutionItem(
        'test',
        '/test/path',
        'Test',
        vscode.TreeItemCollapsibleState.None
      );

      const children = await provider.getChildren(item);

      expect(children).to.deep.equal([]);
    });

    it('should return SAFSolutionItem array when solutions exist', async () => {
      const mockOutput = `sol1
  Root Directory: /path/1
  Display Name: Solution 1
sol2
  Root Directory: /path/2
  Display Name: Solution 2
`;
      execFileAsyncStub.resolves({ stdout: mockOutput, stderr: '' });

      const provider = SAFSolutionsProvider.getInstance();
      const children = await provider.getChildren();

      expect(children).to.have.lengthOf(2);
      expect(children[0]).to.be.instanceOf(SAFSolutionItem);
      expect(children[0].label).to.equal('sol1');
      expect(children[0].rootDirectory).to.equal('/path/1');
      expect(children[0].displayName).to.equal('Solution 1');
      expect(children[0].command?.command).to.equal('solutions-manager.openSolution');
      expect(children[0].command?.arguments).to.deep.equal(['/path/1']);
    });

    it('should return "No solutions found" item when getSAFSolutions returns empty array', async () => {
      execFileAsyncStub.resolves({ stdout: '', stderr: '' });

      const provider = SAFSolutionsProvider.getInstance();
      const children = await provider.getChildren();

      expect(children).to.have.lengthOf(1);
      expect(children[0].label).to.equal('No solutions found');
      expect(children[0].command?.command).to.equal('solutions-manager.refreshSolutionsList');
    });

    it('should show empty-state item when SAF CLI execution fails', async () => {
      execFileAsyncStub.rejects(new Error('Execution failed'));

      const provider = SAFSolutionsProvider.getInstance();
      const children = await provider.getChildren();

      expect(children).to.have.lengthOf(1);
      expect(children[0].label).to.equal('No solutions found');
      expect(children[0].command?.command).to.equal('solutions-manager.refreshSolutionsList');
    });

    it('should log error when getSAFSolutions throws', async () => {
      const consoleErrorStub = sinon.stub(console, 'error');
      execFileAsyncStub.rejects(new Error('Execution failed'));

      const provider = SAFSolutionsProvider.getInstance();
      await provider.getChildren();

      expect(consoleErrorStub.called).to.be.true;
      consoleErrorStub.restore();
    });
  });

  describe('refresh', () => {
    it('should fire onDidChangeTreeData event', () => {
      const provider = SAFSolutionsProvider.getInstance();
      const eventStub = sinon.stub();

      // Subscribe to the event
      provider.onDidChangeTreeData(eventStub);

      // Call refresh
      provider.refresh();

      // Event should have fired
      expect(eventStub.calledOnce).to.be.true;
    });
  });

  describe('SAFSolutionItem', () => {
    it('should set all properties correctly', () => {
      const command: vscode.Command = {
        command: 'test.command',
        title: 'Test',
        arguments: ['/test/arg']
      };

      const item = new SAFSolutionItem(
        'Test Item',
        '/root/dir',
        'Test Display Name',
        vscode.TreeItemCollapsibleState.None,
        command
      );

      expect(item.label).to.equal('Test Item');
      expect(item.rootDirectory).to.equal('/root/dir');
      expect(item.displayName).to.equal('Test Display Name');
      expect(item.collapsibleState).to.equal(vscode.TreeItemCollapsibleState.None);
      expect(item.command).to.deep.equal(command);
    });

    it('should set description to rootDirectory', () => {
      const item = new SAFSolutionItem(
        'Test',
        '/test/path',
        'Test',
        vscode.TreeItemCollapsibleState.None
      );

      expect(item.description).to.equal('/test/path');
    });

    it('should set tooltip with root directory and display name', () => {
      const item = new SAFSolutionItem(
        'Test',
        '/test/path',
        'Test Display',
        vscode.TreeItemCollapsibleState.None
      );

      expect(item.tooltip).to.include('Root directory: /test/path');
      expect(item.tooltip).to.include('Display Name: Test Display');
    });

    it('should set iconPath to folder theme icon', () => {
      const item = new SAFSolutionItem(
        'Test',
        '/test/path',
        'Test',
        vscode.TreeItemCollapsibleState.None
      );

      expect(item.iconPath).to.be.instanceOf(vscode.ThemeIcon);
      expect((item.iconPath as vscode.ThemeIcon).id).to.equal('folder');
    });

    it('should set contextValue to safSolution', () => {
      const item = new SAFSolutionItem(
        'Test',
        '/test/path',
        'Test',
        vscode.TreeItemCollapsibleState.None
      );

      expect(item.contextValue).to.equal('safSolution');
    });
  });
});
