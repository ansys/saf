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
import { DependencyCommands } from '../../../src/commands/dependencyCommands';
import { DependencyTreeProvider } from '../../../src/providers/DependencyTreeProvider';
import { dependencyService } from '../../../src/services/DependencyService';
import { CommandContext } from '../../../src/managers/CommandManager';
import { MockExtensionContext } from '../../mocks/vscode.mock';

/**
 * Unit tests for DependencyCommands class
 */
describe('DependencyCommands', () => {
    let commands: DependencyCommands;
    let mockContext: MockExtensionContext;
    let commandContext: CommandContext;
    let mockProvider: DependencyTreeProvider;
    let refreshStub: sinon.SinonStub;
    let addDependencyStub: sinon.SinonStub;
    let updateDependencyStub: sinon.SinonStub;
    let removeDependencyStub: sinon.SinonStub;

    beforeEach(() => {
        mockContext = new MockExtensionContext();
        commandContext = {
            extensionContext: mockContext as any,
            workspaceRoot: '/mock/workspace'
        };

        // Create mock provider with refresh as a stub
        refreshStub = sinon.stub();
        mockProvider = {
            refresh: refreshStub
        } as any;

        // Stub dependency service methods
        addDependencyStub = sinon.stub(dependencyService, 'addDependency').resolves();
        updateDependencyStub = sinon.stub(dependencyService, 'updateDependency').resolves();
        removeDependencyStub = sinon.stub(dependencyService, 'removeDependency').resolves();

        // Reset VS Code window method stubs (they're already stubbed in the mock)
        (vscode.window.showInputBox as sinon.SinonStub).reset();
        (vscode.window.showQuickPick as sinon.SinonStub).reset();
        (vscode.window.showWarningMessage as sinon.SinonStub).reset();
        (vscode.window.showInformationMessage as sinon.SinonStub).reset();
        (vscode.window.showErrorMessage as sinon.SinonStub).reset();
        (vscode.window.withProgress as sinon.SinonStub).reset();

        commands = new DependencyCommands(commandContext);
    });

    afterEach(() => {
        sinon.restore();
    });

    describe('refreshDependencyProvider', () => {
        it('should call refresh on provider when set', () => {
            commands.setDependencyProvider(mockProvider);
            commands['refreshDependencyProvider']();

            expect(refreshStub.calledOnce).to.be.true;
        });

        it('should not throw when provider is not set', () => {
            expect(() => commands['refreshDependencyProvider']()).to.not.throw();
        });
    });

    describe('addDependency', () => {
        it('should call refreshDependencyProvider after adding dependency', async () => {
            // Setup workspace folder mock
            (vscode.workspace.workspaceFolders as any) = [{ uri: { fsPath: '/mock/workspace' } }];

            // Setup mocks using existing stubs
            (vscode.window.showInputBox as sinon.SinonStub)
                .onFirstCall().resolves('test-package')
                .onSecondCall().resolves('^1.0.0');
            (vscode.window.showQuickPick as sinon.SinonStub).resolves({ label: 'main' } as any);
            (vscode.window.withProgress as sinon.SinonStub).callsFake(async (_, callback) => {
                const progress = { report: sinon.stub() } as any;
                const token = { isCancellationRequested: false, onCancellationRequested: sinon.stub() } as any;
                return callback(progress, token);
            });

            commands.setDependencyProvider(mockProvider);
            const refreshSpy = sinon.spy(commands as any, 'refreshDependencyProvider');

            await commands.addDependency();

            expect(addDependencyStub.called).to.be.true;
            expect(refreshSpy.called).to.be.true;
        });
    });

    describe('updateDependency', () => {
        it('should call refreshDependencyProvider after updating dependency', async () => {
            // Setup workspace folder mock
            (vscode.workspace.workspaceFolders as any) = [{ uri: { fsPath: '/mock/workspace' } }];

            const mockItem = {
                label: 'test-package',
                group: 'main'
            } as any;

            (vscode.window.showInputBox as sinon.SinonStub).resolves('^2.0.0');
            (vscode.window.withProgress as sinon.SinonStub).callsFake(async (_, callback) => {
                const progress = { report: sinon.stub() } as any;
                const token = { isCancellationRequested: false, onCancellationRequested: sinon.stub() } as any;
                return callback(progress, token);
            });

            commands.setDependencyProvider(mockProvider);
            const refreshSpy = sinon.spy(commands as any, 'refreshDependencyProvider');

            await commands.updateDependency(mockItem);

            expect(updateDependencyStub.called).to.be.true;
            expect(refreshSpy.called).to.be.true;
        });
    });

    describe('removeDependency', () => {
        it('should call refreshDependencyProvider after removing dependency', async () => {
            // Setup workspace folder mock
            (vscode.workspace.workspaceFolders as any) = [{ uri: { fsPath: '/mock/workspace' } }];

            const mockItem = {
                label: 'test-package',
                group: 'main'
            } as any;

            (vscode.window.showWarningMessage as sinon.SinonStub).resolves('Yes' as any);
            (vscode.window.withProgress as sinon.SinonStub).callsFake(async (_, callback) => {
                const progress = { report: sinon.stub() } as any;
                const token = { isCancellationRequested: false, onCancellationRequested: sinon.stub() } as any;
                return callback(progress, token);
            });

            commands.setDependencyProvider(mockProvider);
            const refreshSpy = sinon.spy(commands as any, 'refreshDependencyProvider');

            await commands.removeDependency(mockItem);

            expect(removeDependencyStub.called).to.be.true;
            expect(refreshSpy.called).to.be.true;
        });
    });
});
