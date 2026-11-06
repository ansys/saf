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


import * as vscode from 'vscode';
import { dependencyService } from '../services/DependencyService';
import { DependencyTreeItem, DependencyTreeProvider } from '../providers/DependencyTreeProvider';
import { isValidVersionConstraint } from '../utils/validation';
import { CommandContext } from '../managers/CommandManager';

export class DependencyCommands {
    private dependencyProvider: DependencyTreeProvider | undefined;

    constructor(private context: CommandContext) { }

    public async addDependency(): Promise<void> {
        try {
            const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
            if (!workspaceFolder) {
                throw new Error('No workspace folder open');
            }

            const dependencyConfig = await this.getDependencyConfig();
            if (!dependencyConfig) {
                return;
            }

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: "Adding dependency",
                cancellable: false
            }, async (progress) => {
                const versionInfo = dependencyConfig.version ? `@${dependencyConfig.version}` : '';
                const groupInfo = dependencyConfig.group ?? 'main';

                progress.report({
                    message: `Adding ${dependencyConfig.name}${versionInfo} to ${groupInfo} dependencies...`
                });

                await dependencyService.addDependency(
                    workspaceFolder.uri.fsPath,
                    dependencyConfig.name,
                    dependencyConfig.version ?? '',
                    dependencyConfig.group ?? undefined
                );

                this.refreshDependencyProvider();
            });

            vscode.window.showInformationMessage(
                `Successfully added ${dependencyConfig.name}${dependencyConfig.version ? `@${dependencyConfig.version}` : ''} to ${dependencyConfig.group || 'main'} dependencies`
            );

        } catch (error) {
            vscode.window.showErrorMessage(
                `Failed to add dependency: ${error instanceof Error ? error.message : 'Unknown error'}`
            );
        }
    }

    public async updateDependency(item: DependencyTreeItem): Promise<void> {
        try {
            const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
            if (!workspaceFolder) {
                throw new Error('No workspace folder open');
            }

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: "Updating dependency",
                cancellable: false
            }, async (progress) => {
                progress.report({
                    message: `Updating ${item.label} to latest allowed version...`
                });

                await dependencyService.updateDependency(
                    workspaceFolder.uri.fsPath,
                    item.label.toString()
                );

                this.refreshDependencyProvider();
            });

            vscode.window.showInformationMessage(
                `Successfully updated ${item.label} to latest allowed version`
            );

        } catch (error) {
            vscode.window.showErrorMessage(
                `Failed to update dependency: ${error instanceof Error ? error.message : 'Unknown error'}`
            );
        }
    }

    public async removeDependency(item: DependencyTreeItem): Promise<void> {
        try {
            const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
            if (!workspaceFolder) {
                throw new Error('No workspace folder open');
            }

            const confirm = await vscode.window.showWarningMessage(
                `Are you sure you want to remove ${item.label}?`,
                'Yes', 'No'
            );

            if (confirm !== 'Yes') {
                return;
            }

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: "Removing dependency",
                cancellable: false
            }, async () => {
                await dependencyService.removeDependency(
                    workspaceFolder.uri.fsPath,
                    item.label.toString(),
                    item.group
                );

                this.refreshDependencyProvider();
            });

            vscode.window.showInformationMessage(
                `Successfully removed ${item.label}`
            );

        } catch (error) {
            vscode.window.showErrorMessage(
                `Failed to remove dependency: ${error instanceof Error ? error.message : 'Unknown error'}`
            );
        }
    }

    public async syncDependencies(): Promise<void> {
        try {
            const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
            if (!workspaceFolder) {
                throw new Error('No workspace folder open');
            }

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: "Syncing dependencies",
                cancellable: false
            }, async (progress) => {
                progress.report({ message: "Running poetry install..." });
                await dependencyService.installDependencies(workspaceFolder.uri.fsPath);
                this.refreshDependencyProvider();
            });

            vscode.window.showInformationMessage("Dependencies synced successfully");

        } catch (error) {
            vscode.window.showErrorMessage(
                `Failed to sync dependencies: ${error instanceof Error ? error.message : 'Unknown error'}`
            );
        }
    }

    private async getDependencyConfig(): Promise<{
        name: string;
        version?: string;
        group?: string;
    } | null> {
        const name = await vscode.window.showInputBox({
            prompt: 'Enter package name',
            placeHolder: 'package-name',
            validateInput: (value) => {
                if (!value || value.trim() === '') {
                    return 'Package name is required';
                }
                return null;
            }
        });
        if (!name) {
            return null;
        }

        const version = await vscode.window.showInputBox({
            prompt: 'Enter version constraint (optional)',
            placeHolder: '1.0, 1.0.0, ^1.0.0, ~1.0.0, >=1.0.0, 0.1dev1',
            validateInput: (value) => {
                if (!value) {
                    return null; // Empty is allowed
                }
                if (!isValidVersionConstraint(value)) {
                    return 'Invalid version constraint format.';
                }
                return null;
            }
        });

        const group = await vscode.window.showQuickPick(
            [
                { label: 'main', description: 'Main runtime dependencies' },
                { label: 'ui', description: 'User interface dependencies' },
                { label: 'doc', description: 'Documentation dependencies' },
                { label: 'tests', description: 'Testing dependencies' },
                { label: 'build', description: 'Build dependencies' },
                { label: 'style', description: 'Code style dependencies' }
            ],
            {
                placeHolder: 'Select dependency group',
                title: 'Dependency Group Selection'
            }
        );

        return {
            name: name.trim(),
            version: version?.trim() || undefined,
            group: group?.label
        };
    }

    private refreshDependencyProvider(): void {
        if (this.dependencyProvider) {
            this.dependencyProvider.refresh();
        }
    }

    public setDependencyProvider(provider: DependencyTreeProvider): void {
        this.dependencyProvider = provider;
    }
}