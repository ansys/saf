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
import { systemService } from '../services/SystemService';
import { CommandContext } from '../managers/CommandManager';
import { validateWorkspaceForDevelopment } from '../utils/workspaceUtils';
import { createTerminal, disposeTerminal, executeCommandInTerminal } from '../utils/terminalUtils';
import { StorageService } from '../services/StorageService';
import { EnvironmentService } from '../services/EnvironmentService';

export class DebugCommands {
    private terminalInstance: vscode.Terminal | undefined;

    constructor(private context: CommandContext) {}

    public async debugTransactionMethods(): Promise<void> {
        try {
            const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
            if (!workspaceFolder) {
                throw new Error('No workspace folder open');
            }

            await systemService.ensureDebugConfiguration(workspaceFolder);

            const validation = validateWorkspaceForDevelopment(workspaceFolder.uri.fsPath);
            if (!validation.isValid) {
                await this.handleInvalidWorkspace(validation);
                return;
            }

            await this.startTransactionMethodsDebug(workspaceFolder);

        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Failed to start debug mode';
            vscode.window.showErrorMessage(errorMessage);
        }
    }

    public async debugSolutionDashUI(): Promise<void> {
        try {
            const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
            if (!workspaceFolder) {
                throw new Error('No workspace folder open');
            }

            await systemService.ensureDebugConfiguration(workspaceFolder);

            const validation = validateWorkspaceForDevelopment(workspaceFolder.uri.fsPath);
            if (!validation.isValid) {
                await this.handleInvalidWorkspace(validation);
                return;
            }

            await this.startDashUIDebug(workspaceFolder);

        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Failed to start UI debug mode';
            vscode.window.showErrorMessage(errorMessage);
        }
    }

    private async handleInvalidWorkspace(validation: any): Promise<void> {
        if (!validation.hasVenv || !validation.hasSAF) {
            const setupChoice = await vscode.window.showWarningMessage(
                'Environment is not set up. Install development environment first?',
                'Yes', 'No'
            );

            if (setupChoice === 'Yes') {
                await vscode.commands.executeCommand('solutions-manager.installDevEnvironment');
            }
        }
    }

    private async startTransactionMethodsDebug(workspaceFolder: vscode.WorkspaceFolder): Promise<void> {
        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: "Setting up debug environment",
            cancellable: false
        }, async (progress) => {
            progress.report({ increment: 0, message: "Starting solution in debug mode..." });

            const debugPort = await this.getDebugPort(workspaceFolder.uri.fsPath, 'GLOW_DEBUG_API_PORT', 5724);

            this.terminalInstance = createTerminal('Solutions Manager Debug', workspaceFolder.uri.fsPath);
            const safCliExecutable = StorageService.getSafCliTerminalCommand();
            await executeCommandInTerminal(this.terminalInstance, safCliExecutable + ' run --debug');

            progress.report({ increment: 50, message: "Waiting for debugger to start..." });
            await new Promise(resolve => setTimeout(resolve, 20000));

            progress.report({ increment: 75, message: "Attaching debugger..." });

            const success = await this.attachDebugger(workspaceFolder, debugPort);

            if (success) {
                progress.report({ increment: 100 });
                vscode.window.showInformationMessage(
                    `Debug mode activated on port ${debugPort}. Set breakpoints in your transaction methods and invoke them through the solution UI.`
                );
            } else {
                throw new Error(`Failed to connect to debug port ${debugPort}. Try setting the GLOW_DEBUG_API_PORT environment variable if the default port is not available.`);
            }
        });
    }

    private async startDashUIDebug(workspaceFolder: vscode.WorkspaceFolder): Promise<void> {
        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: "Setting up UI debug environment",
            cancellable: false
        }, async (progress) => {
            progress.report({ increment: 0, message: "Starting solution in UI debug mode..." });

            const dashDebugPort = await this.getDebugPort(workspaceFolder.uri.fsPath, 'GLOW_DEBUG_UI_PORT', 5725);

            this.terminalInstance = createTerminal('Solutions Manager Debug', workspaceFolder.uri.fsPath);
            const safCliExecutable = StorageService.getSafCliTerminalCommand();
            await executeCommandInTerminal(this.terminalInstance, safCliExecutable + ' run --ui-debugger');

            progress.report({ increment: 50, message: "Waiting for UI debugger to start..." });
            await new Promise(resolve => setTimeout(resolve, 10000));

            progress.report({ increment: 75, message: "Attaching debugger..." });

            const success = await this.attachDashDebugger(workspaceFolder, dashDebugPort);

            if (success) {
                progress.report({ increment: 100 });
                vscode.window.showInformationMessage(
                    `UI Debug mode activated on port ${dashDebugPort}. Set breakpoints in your Dash callbacks and interact with the UI.`
                );
            } else {
                throw new Error(`Failed to connect to UI debug port ${dashDebugPort}. Check your .env file and set GLOW_DEBUG_DASH_PORT if the default port is not available.`);
            }
        });
    }

    private async getDebugPort(workspacePath: string, envVarName: string, defaultPort: number): Promise<number> {
        // For debug commands, we use the workspace path as the solution path
        // since we're debugging the solution in the current workspace
        try {
            const envService = new EnvironmentService(this.context.extensionContext);
            await envService.loadForSolution(workspacePath);

            const value = envService.getVariableValue(envVarName);
            if (value !== undefined && value !== null) {
                const portStr = String(value);
                const parsedPort = parseInt(portStr, 10);
                if (!isNaN(parsedPort) && parsedPort > 0) {
                    return parsedPort;
                }
            }
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : 'Unknown error';
            vscode.window.showWarningMessage(
                `Failed to read ${envVarName} from environment configuration. Using default port ${defaultPort}. Error: ${errorMessage}`
            );
        }

        return defaultPort;
    }

    private async attachDebugger(workspaceFolder: vscode.WorkspaceFolder, port: number): Promise<boolean> {
        const debugConfig = {
            type: 'python',
            name: 'Python: Remote Attach',
            request: 'attach',
            connect: {
                host: 'localhost',
                port: port
            },
            pathMappings: [
                {
                    localRoot: '${workspaceFolder}',
                    remoteRoot: '${workspaceFolder}'
                }
            ],
            justMyCode: false
        };

        return await vscode.debug.startDebugging(workspaceFolder, debugConfig);
    }

    private async attachDashDebugger(workspaceFolder: vscode.WorkspaceFolder, port: number): Promise<boolean> {
        const debugConfig = {
            type: 'python',
            name: 'Python: Remote Attach Dash',
            request: 'attach',
            connect: {
                host: 'localhost',
                port: port
            },
            pathMappings: [
                {
                    localRoot: '${workspaceFolder}',
                    remoteRoot: '${workspaceFolder}'
                }
            ],
            justMyCode: false
        };

        return await vscode.debug.startDebugging(workspaceFolder, debugConfig);
    }

    public dispose(): void {
        disposeTerminal(this.terminalInstance);
        this.terminalInstance = undefined;
    }
}