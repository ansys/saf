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
import * as fs from 'node:fs';
import { systemService } from '../services/SystemService';
import { ConfigurationPanel } from '../services/ConfigurationPanel';
import { SAFSolutionsProvider } from '../providers/SAFSolutionsProvider';
import { CommandContext } from '../managers/CommandManager';
import { TerminalPool, executeCommandInTerminal } from '../utils/terminalUtils';
import { StorageService } from '../services/StorageService';
import * as toml from 'toml';

export class DevelopmentCommands {
    private configPanel: ConfigurationPanel | undefined;

    constructor(private context: CommandContext) {}

    public async installDevEnvironment(): Promise<void> {
        try {
            const { solutionName, solutionRootDir, isWorkspaceSolution } = await this.getSolutionForInstallation();
            if (!solutionName) {
                return;
            }

            const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
            const installConfig = await this.getInstallationConfig(workspaceFolder);
            if (!installConfig) {
                return;
            }

            if (!await this.checkPrivateSources(solutionRootDir)) {
                return;
            }

            await this.executeInstallation(solutionName, solutionRootDir, installConfig, isWorkspaceSolution);

        } catch (error) {
            vscode.window.showErrorMessage(
                `Failed to install solution: ${error instanceof Error ? error.message : 'Unknown error'}`
            );
        }
    }

    public async showEnvironmentConfig(solutionName?: string, solutionPath?: string): Promise<void> {
        try {
            if (!solutionName || !solutionPath) {
                vscode.window.showWarningMessage('Please select a solution first to configure its environment.');
                return;
            }

            if (!this.configPanel) {
                const environmentService = this.context.providerManager?.getEnvironmentService();
                if (!environmentService) {
                    throw new Error('Environment service not available');
                }
                this.configPanel = new ConfigurationPanel(
                    this.context.extensionContext,
                    environmentService
                );
            }
            await this.configPanel.show(solutionName, solutionPath);
        } catch (error) {
            vscode.window.showErrorMessage(
                `Failed to open environment configuration: ${error instanceof Error ? error.message : 'Unknown error'}`
            );
        }
    }


    private async getSolutionForInstallation(): Promise<{
        solutionName: string | undefined;
        solutionRootDir: string;
        isWorkspaceSolution: boolean;
    }> {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        let solutionName: string | undefined;
        let solutionRootDir: string;
        let isWorkspaceSolution = false;

        if (workspaceFolder) {
            const pyprojectPath = path.join(workspaceFolder.uri.fsPath, 'pyproject.toml');
            // eslint-disable-next-line security/detect-non-literal-fs-filename
            if (fs.existsSync(pyprojectPath)) {
                const useWorkspace = await vscode.window.showQuickPick(
                    ['Yes', 'No'],
                    {
                        placeHolder: `Use currently opened solution in workspace? (${workspaceFolder.name})`,
                        title: 'Install Development Environment'
                    }
                );

                if (useWorkspace === 'Yes') {
                    isWorkspaceSolution = true;
                    solutionName = workspaceFolder.name;
                    solutionRootDir = workspaceFolder.uri.fsPath;
                    return { solutionName, solutionRootDir, isWorkspaceSolution };
                } else if (useWorkspace === 'No') {
                    // Continue to solution selection
                } else {
                    return { solutionName: undefined, solutionRootDir: '', isWorkspaceSolution: false };
                }
            }
        }

        // Get solution from SAF list or manual input
        const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();

        if (solutions.length > 0) {
            const selectedSolution = await vscode.window.showQuickPick(
                solutions.map(s => ({
                    label: s.name,
                    description: s.displayName,
                    detail: `Root directory: ${s.rootDirectory}`
                })),
                {
                    placeHolder: 'Select a solution',
                    title: 'Install Development Environment'
                }
            );

            if (selectedSolution) {
                const solution = solutions.find(s => s.name === selectedSolution.label);
                solutionName = selectedSolution.label;
                solutionRootDir = solution?.rootDirectory || process.cwd();
            } else {
                return { solutionName: undefined, solutionRootDir: '', isWorkspaceSolution: false };
            }
        } else {
            solutionName = await vscode.window.showInputBox({
                prompt: 'Enter solution name to install',
                placeHolder: 'solution-name',
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
                return { solutionName: undefined, solutionRootDir: '', isWorkspaceSolution: false };
            }

            solutionRootDir = process.cwd();
        }

        return { solutionName, solutionRootDir, isWorkspaceSolution };
    }

    private async getInstallationConfig(workspaceFolder?: vscode.WorkspaceFolder) {
        const dependencyOptions = [
            {
                label: 'All Dependencies',
                description: 'Install all dependency groups',
                detail: 'Recommended for full development setup',
                value: ['all']
            },
            {
                label: 'Standard Setup (desktop, ui, doc)',
                description: 'Common setup for desktop solutions',
                detail: 'Includes desktop, UI, and documentation dependencies',
                value: ['desktop', 'ui', 'doc']
            },
            {
                label: 'Custom Dependency Groups',
                description: 'Select specific dependency groups',
                detail: 'Choose individual groups manually',
                value: ['custom']
            }
        ];

        const selectedDeps = await vscode.window.showQuickPick(
            dependencyOptions,
            {
                placeHolder: 'Select dependencies to install',
                title: 'Dependency Selection'
            }
        );

        if (!selectedDeps) {
            return null;
        }

        let dependencyGroups: string[];

        if (selectedDeps.value[0] === 'custom') {
            const customOptions = [
                { label: 'all', description: 'All dependency groups' },
                { label: 'tests', description: 'Testing dependencies' },
                { label: 'doc', description: 'Documentation dependencies' },
                { label: 'build', description: 'Build dependencies' },
                { label: 'style', description: 'Styling dependencies' },
                { label: 'desktop', description: 'Desktop application dependencies' },
                { label: 'ui', description: 'User interface dependencies' }
            ];

            const customSelected = await vscode.window.showQuickPick(
                customOptions,
                {
                    canPickMany: true,
                    placeHolder: 'Select dependency groups to install',
                    title: 'Custom Dependency Groups'
                }
            );

            if (!customSelected || customSelected.length === 0) {
                return null;
            }

            dependencyGroups = customSelected.map(item => item.label);
        } else {
            dependencyGroups = selectedDeps.value;
        }

        // Check for existing virtual environment
        let forceInstall = false;
        if (workspaceFolder) {
            const venvPath = path.join(workspaceFolder.uri.fsPath, '.venv', 'Scripts', 'solution-app-starter.exe');
            // eslint-disable-next-line security/detect-non-literal-fs-filename
            if (fs.existsSync(venvPath)) {
                const forceChoice = await vscode.window.showQuickPick(
                    ['Yes', 'No'],
                    {
                        placeHolder: 'Force installation? (This will delete the existing virtual environment)',
                        title: 'Force Installation'
                    }
                );

                if (!forceChoice) {
                    return null;
                }
                forceInstall = forceChoice === 'Yes';
            }
        }

        return { dependencyGroups, forceInstall };
    }

    private async checkPrivateSources(solutionRootDir: string): Promise<boolean> {
        const pyprojectPath = path.join(solutionRootDir, 'pyproject.toml');
        // eslint-disable-next-line security/detect-non-literal-fs-filename
        if (!fs.existsSync(pyprojectPath)) {
            vscode.window.showWarningMessage('pyproject.toml not found in selected workspace folder.');
            return false;
        }

        // eslint-disable-next-line security/detect-non-literal-fs-filename
        const data = toml.parse(fs.readFileSync(pyprojectPath, 'utf-8'));
        let validInitialCredentials = true;
        for (const source of data['tool']?.['poetry']?.['source'] || []) {
            if (source.url) {
                const sourceValidInitialCredentials = await systemService.checkAndPromptForCredentials(source);
                if (!sourceValidInitialCredentials) {
                    validInitialCredentials = false;
                }
            }
        }

        return validInitialCredentials;
    }

    private async executeInstallation(
        solutionName: string,
        solutionRootDir: string,
        config: { dependencyGroups: string[]; forceInstall: boolean },
        isWorkspaceSolution: boolean
    ): Promise<void> {
        // For workspace solutions (cloned repos), install from current directory without solution name
        // For registered solutions, install with solution name
        let command: string;
        let safCliExecutable = StorageService.getSafCliTerminalCommand();
        if (isWorkspaceSolution) {
            command = safCliExecutable + ' install';
        } else {
            command = safCliExecutable + ` install ${solutionName}`;  // Install named solution
        }

        if (config.dependencyGroups.length > 0) {
            command += ` -d ${config.dependencyGroups.join(',')}`;
        }

        if (config.forceInstall) {
            command += ' -f';
        }

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        const terminalName = isWorkspaceSolution
            ? `SAF Install - ${workspaceFolder?.name || 'Workspace'}`
            : `SAF Install - ${solutionName}`;

        const terminal = TerminalPool.getTerminal(terminalName, solutionRootDir);
        await executeCommandInTerminal(terminal, command);

        const messageTarget = isWorkspaceSolution
            ? `workspace solution (${workspaceFolder?.name})`
            : solutionName;

        vscode.window.showInformationMessage(
            `Installing ${messageTarget} with dependencies: ${config.dependencyGroups.join(',')}`
        );
    }


    private async handleInvalidWorkspace(validation: any): Promise<void> {
        if (!validation.hasVenv || !validation.hasSAF) {
            const setupChoice = await vscode.window.showWarningMessage(
                'Environment is not set up. Install development environment first?',
                'Yes', 'No'
            );

            if (setupChoice === 'Yes') {
                await this.installDevEnvironment();
            }
        }
    }

    public dispose(): void {
        // Clean up any resources if needed
    }
}