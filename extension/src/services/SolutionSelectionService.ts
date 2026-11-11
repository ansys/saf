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
import { solutionRegistrationService } from './SolutionRegistrationService';
import { SelectedSolution } from './StorageService';

export class SolutionSelectionService {
    /**
     * Opens a folder dialog for the user to select a solution directory,
     * validates it, and registers it (without auto-selecting it in storage)
     * @param workspaceContext Context for storing the solution (typically workspace root)
     * @returns Solution info if successfully selected and registered, undefined if cancelled or failed
     */
    public async selectAndRegisterSolution(workspaceContext: string | undefined): Promise<SelectedSolution | undefined> {
        const homeDir = process.env.HOME || process.env.USERPROFILE;
        const selectedUri = await vscode.window.showOpenDialog({
            canSelectFiles: false,
            canSelectFolders: true,
            canSelectMany: false,
            openLabel: 'Choose solution',
            defaultUri: homeDir ? vscode.Uri.file(homeDir) : undefined
        });

        // User cancelled
        if (!selectedUri || selectedUri.length === 0) {
            return undefined;
        }

        const solutionPath = selectedUri[0].fsPath;

        return await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: 'Registering solution...',
                cancellable: false
            },
            async () => {
                try {
                    const solutionInfo = await solutionRegistrationService.registerSolution(
                        solutionPath,
                        workspaceContext,
                        false  // Don't auto-select, let the webview handle selection
                    );
                    return solutionInfo;
                } catch (error: any) {
                    vscode.window.showErrorMessage('Failed to register solution: ' + error.message);
                    return undefined;
                }
            }
        );
    }
}

export const solutionSelectionService = new SolutionSelectionService();
