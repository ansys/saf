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
import * as path from 'node:path';
import { solutionService } from '../services/SolutionService';
import { systemService } from '../services/SystemService';
import { SAFSolutionsProvider } from '../providers/SAFSolutionsProvider';
import { CommandContext } from '../managers/CommandManager';
import { validateNamespace} from '../utils/validation';

export class SolutionCommands {

    constructor(private readonly context: CommandContext) {}

    public async createSolution(): Promise<void> {
        try {
            await systemService.handleSAFCliInstallation();

            const solutionConfig = await this.getSolutionConfig();
            if (!solutionConfig) {
                return;
            }

            const solutionRootDir = await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: "Creating Solution",
                cancellable: false
            }, async (progress) => {
                progress.report({ message: 'Creating solution...' });

                await solutionService.createSolution(solutionConfig);
                return path.join(solutionConfig.targetDirectory, solutionConfig.name);
            });

            await new Promise(resolve => setTimeout(resolve, 5000));

            if (solutionRootDir) {
                vscode.window.showInformationMessage('Solution created successfully and opened!');
                await vscode.commands.executeCommand('vscode.openFolder', vscode.Uri.file(solutionRootDir));
            }

        } catch (error) {
            vscode.window.showErrorMessage(`Failed to create solution: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }

    public refreshSolutionsList(): void {
        SAFSolutionsProvider.getInstance().refresh();
    }

    public async openSolution(solutionPath: string): Promise<void> {
        try {
            if (!solutionPath) {
                throw new Error('Solution path is undefined');
            }

            const openChoice = await vscode.window.showQuickPick(
                ['Open in current window', 'Open in new window'],
                { placeHolder: 'How would you like to open this solution?' }
            );

            if (!openChoice) {
                return;
            }

            await vscode.commands.executeCommand('vscode.openFolder',
                vscode.Uri.file(solutionPath),
                { forceNewWindow: openChoice === 'Open in new window' }
            );
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to open solution: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }

    private async getSolutionConfig() {
        const solutionName = await vscode.window.showInputBox({
            prompt: 'Enter solution name',
            placeHolder: 'my-solution',
            validateInput: (value) => {
                if (!value) {
                    return 'Solution name is required';
                }
                if (!/^[a-zA-Z0-9_-]+$/.test(value)) {
                    return 'Solution name can only contain letters, numbers, hyphens and underscores';
                }
                return null;
            }
        });
        if (!solutionName) {
            return null;
        }

        const solutionDisplayName = await vscode.window.showInputBox({
            prompt: 'Enter solution display name',
            placeHolder: solutionName.split(/[-_]/).map(word =>
                word.charAt(0).toUpperCase() + word.slice(1)).join(' '),
        }) || solutionName.split(/[-_]/).map(word =>
            word.charAt(0).toUpperCase() + word.slice(1)).join(' ');

        const solutionUIOptions = [
            { label: 'dash', value: 'dash' },
            { label: 'none', value: 'none' }
        ];

        const namespace = await vscode.window.showInputBox({
            prompt: 'Enter solution namespace',
            placeHolder: 'saf.solutions',
            validateInput: (value) => {
                if (!value) {
                    return 'Namespace is required';
                }
                const namespaceError = validateNamespace(value);
                if (namespaceError) {
                    return namespaceError;
                }
                return null;
            }
        });

        if (!namespace) {
            return null;
        }

        const uiSelection = await vscode.window.showQuickPick(solutionUIOptions, {
            placeHolder: 'Select the type of solution UI'
        }) || solutionUIOptions[0];

        const folderUri = await vscode.window.showOpenDialog({
            canSelectMany: false,
            canSelectFolders: true,
            canSelectFiles: false,
            openLabel: 'Select folder for new solution'
        });
        if (!folderUri || !folderUri[0]) {
            throw new Error('You must select a folder to create the solution.');
        }

        return {
            name: solutionName,
            displayName: solutionDisplayName,
            uiType: uiSelection.value,
            namespace: namespace,
            targetDirectory: folderUri[0].fsPath
        };
    }
}