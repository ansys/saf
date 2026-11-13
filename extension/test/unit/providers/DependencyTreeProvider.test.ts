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
import * as fs from 'node:fs';
import { DependencyTreeProvider, DependencyTreeItem } from '../../../src/providers/DependencyTreeProvider';
import { dependencyService } from '../../../src/services/DependencyService';

/**
 * Unit tests for DependencyTreeProvider class
 */
describe('DependencyTreeProvider', () => {
    let provider: DependencyTreeProvider;
    let mockFileWatcher: vscode.FileSystemWatcher;
    let onDidChangeHandler: (() => void) | undefined;
    let onDidCreateHandler: (() => void) | undefined;
    let onDidDeleteHandler: (() => void) | undefined;
    let clock: sinon.SinonFakeTimers;
    const workspaceRoot = '/mock/workspace';

    beforeEach(() => {
        clock = sinon.useFakeTimers();

        // Create mock file watcher
        mockFileWatcher = {
            onDidChange: sinon.stub().callsFake((handler) => {
                onDidChangeHandler = handler;
                return { dispose: sinon.stub() };
            }),
            onDidCreate: sinon.stub().callsFake((handler) => {
                onDidCreateHandler = handler;
                return { dispose: sinon.stub() };
            }),
            onDidDelete: sinon.stub().callsFake((handler) => {
                onDidDeleteHandler = handler;
                return { dispose: sinon.stub() };
            }),
            dispose: sinon.stub()
        } as any;

        // Reset and configure VS Code workspace API stubs (they're already stubbed in the mock)
        (vscode.workspace.createFileSystemWatcher as sinon.SinonStub).reset();
        (vscode.workspace.createFileSystemWatcher as sinon.SinonStub).returns(mockFileWatcher);
        (vscode.workspace.findFiles as sinon.SinonStub).reset();
        (vscode.workspace.findFiles as sinon.SinonStub).resolves([]);

        provider = new DependencyTreeProvider(workspaceRoot);
    });

    afterEach(() => {
        if (clock) {
            clock.restore();
        }
        sinon.restore();
        onDidChangeHandler = undefined;
        onDidCreateHandler = undefined;
        onDidDeleteHandler = undefined;
    });

    describe('constructor', () => {
        it('should create file watchers for pyproject.toml and poetry.lock', () => {
            expect((vscode.workspace.createFileSystemWatcher as sinon.SinonStub).called).to.be.true;
            // It creates 2 watchers: one for pyproject.toml, one for poetry.lock
            expect((vscode.workspace.createFileSystemWatcher as sinon.SinonStub).callCount).to.be.at.least(2);
        });

        it('should register file change handlers', () => {
            expect((mockFileWatcher.onDidChange as sinon.SinonStub).called).to.be.true;
            expect((mockFileWatcher.onDidCreate as sinon.SinonStub).called).to.be.true;
            expect((mockFileWatcher.onDidDelete as sinon.SinonStub).called).to.be.true;
        });
    });

    describe('file watcher', () => {
        it('should refresh when pyproject.toml changes', () => {
            const refreshSpy = sinon.spy(provider, 'refresh');

            if (onDidChangeHandler) {
                onDidChangeHandler();
            }

            expect(refreshSpy.calledOnce).to.be.true;
        });

        it('should refresh when pyproject.toml is created', () => {
            const refreshSpy = sinon.spy(provider, 'refresh');

            if (onDidCreateHandler) {
                onDidCreateHandler();
            }

            expect(refreshSpy.calledOnce).to.be.true;
        });

        it('should refresh when pyproject.toml is deleted', () => {
            const refreshSpy = sinon.spy(provider, 'refresh');

            if (onDidDeleteHandler) {
                onDidDeleteHandler();
            }

            expect(refreshSpy.calledOnce).to.be.true;
        });
    });

    describe('dispose', () => {
        it('should dispose file watchers', () => {
            provider.dispose();
            // Should be called at least twice (one for each watcher)
            expect((mockFileWatcher.dispose as sinon.SinonStub).callCount).to.be.at.least(2);
        });

        it('should handle dispose when watcher is undefined', () => {
            const providerWithoutWatcher = new DependencyTreeProvider(workspaceRoot);
            // Manually set watcher to undefined to test edge case
            (providerWithoutWatcher as any).fileWatcher = undefined;

            expect(() => providerWithoutWatcher.dispose()).to.not.throw();
        });
    });

    describe('refresh', () => {
        it('should fire onDidChangeTreeData event', () => {
            let eventFired = false;
            const disposable = provider.onDidChangeTreeData(() => {
                eventFired = true;
            });

            provider.refresh();
            // Advance clock to trigger debounce
            clock.tick(550);

            expect(eventFired).to.be.true;
            disposable.dispose();
        });
    });

    describe('getChildren', () => {
        it('should return helpful message when no workspace root', async () => {
            const providerWithoutRoot = new DependencyTreeProvider('');
            const children = await providerWithoutRoot.getChildren();

            expect(children).to.have.length(1);
            expect(children[0].label).to.equal('Open a solution to view dependencies');
            expect(children[0].contextValue).to.equal('noSolution');
        });

        it('should return "no solution" when pyproject.toml missing and valid solution directory', async () => {
            (vscode.workspace.findFiles as sinon.SinonStub).resolves([vscode.Uri.file('/mock/workspace/src/my_ns/my_solution/solution/definition.py')]);

            const children = await provider.getChildren();

            expect(children).to.have.length(1);
            expect(children[0].label).to.equal('pyproject.toml not found in this solution');
            expect(children[0].contextValue).to.equal('missingPyproject');
        });

        it('should return "invalid solution" when pyproject.toml missing and invalid solution directory', async () => {
            (vscode.workspace.findFiles as sinon.SinonStub).resolves([]);

            const children = await provider.getChildren();

            expect(children).to.have.length(1);
            expect(children[0].label).to.equal('The current directory is not a valid solution');
            expect(children[0].contextValue).to.equal('invalidSolution');
        });

        it('should return dependencies for a group', async () => {
            const mockGroupItem = new DependencyTreeItem(
                'main',
                { 'package1': '^1.0.0', 'package2': '^2.0.0' },
                vscode.TreeItemCollapsibleState.Collapsed,
                'group'
            );

            sinon.stub(dependencyService, 'getDependencyStatus').resolves({
                exists: true,
                isCorrupt: false,
                isOutOfSync: false
            } as any);

            const children = await provider.getChildren(mockGroupItem);

            expect(children).to.have.length(2);
            expect(children[0]).to.be.instanceOf(DependencyTreeItem);
            expect(children[0].contextValue).to.equal('dependency');
        });

        it('should handle errors gracefully', async () => {
            // pyproject.toml doesn't exist in mock workspace but solution directory is valid
            (vscode.workspace.findFiles as sinon.SinonStub).resolves([vscode.Uri.file('/mock/workspace/src/my_ns/my_solution/solution/definition.py')]);

            const children = await provider.getChildren();

            // Since pyproject.toml doesn't exist but directory is valid, returns "missing pyproject"
            expect(children.length).to.equal(1);
            expect(children[0].label).to.equal('pyproject.toml not found in this solution');
            expect(children[0].contextValue).to.equal('missingPyproject');
        });
    });

    describe('getTreeItem', () => {
        it('should return the element as-is', () => {
            const item = new DependencyTreeItem(
                'test',
                {},
                vscode.TreeItemCollapsibleState.None,
                'dependency'
            );

            const result = provider.getTreeItem(item);

            expect(result).to.equal(item);
        });
    });

    describe('workspace folder changes', () => {
        it('should update workspace root when workspace folders change', () => {
            // Store the handler from the constructor
            const workspaceChangeStub = vscode.workspace.onDidChangeWorkspaceFolders as sinon.SinonStub;
            const handler = workspaceChangeStub.lastCall?.args[0];

            expect(handler).to.exist;

            if (handler) {
                const newWorkspaceRoot = '/new/workspace';
                (vscode.workspace.workspaceFolders as any) = [{
                    uri: { fsPath: newWorkspaceRoot },
                    name: 'new-solution'
                }];

                const refreshSpy = sinon.spy(provider, 'refresh');

                // Call the handler
                handler();

                // Advance clock to trigger debounce
                clock.tick(550);

                expect(refreshSpy.called).to.be.true;
            }
        });
    });
});
