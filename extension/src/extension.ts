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
import { ExtensionManager } from './managers/ExtensionManager';
import { StorageService } from './services/StorageService';
import { systemService } from './services/SystemService';
import { solutionRegistrationService } from './services/SolutionRegistrationService';

/**
 * Main extension activation function
 */
export async function activate(context: vscode.ExtensionContext): Promise<void> {
    console.log('Activating Solutions Manager extension...');

    try {
        new StorageService(context);

        systemService.setContext(context);

        const extensionManager = new ExtensionManager(context);
        await extensionManager.initialize();

        const longPathsOk = await systemService.checkWindowsLongPaths();
        if (!longPathsOk) {
            return;
        }

        await systemService.handleSAFCliInstallation();

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (workspaceFolder) {
            try {
                await solutionRegistrationService.checkAndRegisterWorkspaceSolution(workspaceFolder.uri.fsPath);
            } catch (error) {
                console.error('Failed to check workspace solution registration:', error);
            }
        }

        console.log('Solutions Manager extension activated successfully');
    } catch (error) {
        console.error('Failed to activate Solutions Manager extension:', error);
        vscode.window.showErrorMessage(
            `Failed to activate Solutions Manager: ${error instanceof Error ? error.message : 'Unknown error'}`
        );
    }
}

/**
 * Extension deactivation function
 */
export function deactivate(): void {
    console.log('Deactivating Solutions Manager extension...');
    ExtensionManager.cleanup();
}