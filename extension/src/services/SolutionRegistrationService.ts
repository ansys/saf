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
import { SAFSolutionsProvider } from '../providers/SAFSolutionsProvider';
import { SelectedSolution, StorageService } from './StorageService';
import {
    isValidSolutionWorkspace,
    getWorkspaceSolutionInfo
} from '../utils/workspaceUtils';
import { execAsync } from '../utils/exec';

export class SolutionRegistrationService {
    private async waitForSolutionRegistration(
        solutionName: string,
        maxRetries: number = 5,
        delayMs: number = 2000
    ): Promise<boolean> {
        for (let attempt = 0; attempt < maxRetries; attempt++) {
            if (attempt > 0) {
                await new Promise(resolve => setTimeout(resolve, delayMs));
            }

            try {
                const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();
                const found = solutions.some(s =>
                    s.name.toLowerCase().replaceAll(/[-_]/g, '') === solutionName.toLowerCase().replaceAll(/[-_]/g, '')
                );

                if (found) {
                    return true;
                }
            } catch (error) {
                console.error('Error checking solution registration:', error);
            }
        }

        return false;
    }

    /**
     * Register a solution by executing a dummy command
     * @param solutionPath Path to the solution directory
     * @param workspaceContext Context for storing the solution (typically workspace root)
     * @param autoSelect Whether to automatically set this as the selected solution in storage
     * @returns Solution info if registered, undefined otherwise
     */
    public async registerSolution(
        solutionPath: string,
        workspaceContext: string | undefined,
        autoSelect: boolean = true
    ): Promise<SelectedSolution | undefined> {
        // 1: Check if already registered
        const existingSolutionInfo = await getWorkspaceSolutionInfo(solutionPath);
        if (existingSolutionInfo) {
            if (autoSelect) {
                await StorageService.setSelectedSolution(workspaceContext, existingSolutionInfo);
            }
            return existingSolutionInfo;
        }

        // 2: Validate solution structure
        if (!isValidSolutionWorkspace(solutionPath)) {
            throw new Error('The selected directory is not a valid solution workspace.');
        }

        // 3: Try to register using saf execute
        try {
            const safCliExecutable = StorageService.getSafCliExecutableCommand();
            await execAsync(safCliExecutable + ` execute "${solutionPath}" "python --version"`);

            const solutionInfo = await getWorkspaceSolutionInfo(solutionPath);
            if (solutionInfo) {
                const registered = await this.waitForSolutionRegistration(solutionInfo.name);
                if (registered) {
                    if (autoSelect) {
                        await StorageService.setSelectedSolution(workspaceContext, solutionInfo);
                    }
                    SAFSolutionsProvider.getInstance().refresh();
                    vscode.window.showInformationMessage(`Solution "${solutionInfo.name}" registered successfully.`);
                    return solutionInfo;
                }
            }
        } catch (error: any) {
            let warningMessage = 'Failed to register the solution. Reinstalling the development environment might fix this issue. Do you want to proceed with the installation?';
            if (error.message.includes('Executable \'python\' not found in solution')) {
                warningMessage = 'The development environment for the solution is not installed. Do you want to install it now?';
            }

            // Set in case the Setup Solution panel was opened and the user clicks "No" on the warning.
            if (autoSelect) {
                const solutionInfo = await getWorkspaceSolutionInfo(solutionPath);
                await StorageService.setSelectedSolution(workspaceContext, solutionInfo);
            }

            const choice = await vscode.window.showWarningMessage(
                warningMessage,
                'Yes', 'No'
            );

            if (choice === 'Yes') {
                vscode.window.withProgress(
                    {
                        location: vscode.ProgressLocation.Notification,
                        title: 'Installing development environment...',
                        cancellable: false
                    },
                    async () => {
                        try {
                            await vscode.commands.executeCommand('solutions-manager.installDevEnvironment');
                            vscode.window.showInformationMessage('Development environment installation completed.');
                        } catch (error: any) {
                            vscode.window.showErrorMessage('Development environment installation failed: ' + error.message);
                        }
                    }
                );
            }
            return undefined;
        }

        return undefined;
    }

    public async checkAndRegisterWorkspaceSolution(workspacePath: string): Promise<void> {
        try {
            // Check if already registered
            const solutionInfo = await getWorkspaceSolutionInfo(workspacePath);
            if (solutionInfo) {
                await StorageService.setSelectedSolution(workspacePath, solutionInfo);
                return;
            }

            // If valid solution structure but not registered, use registerSolution with autoSelect=true
            if (isValidSolutionWorkspace(workspacePath)) {
                await this.registerSolution(workspacePath, workspacePath, true);
                return;
            }

            // No solution found or registered, clear selection
            await StorageService.setSelectedSolution(workspacePath, undefined);
        } catch (error: any) {
            vscode.window.showErrorMessage('An error occurred while trying to register the workspace solution: ' + error.message);
        }
    }
}

export const solutionRegistrationService = new SolutionRegistrationService();
