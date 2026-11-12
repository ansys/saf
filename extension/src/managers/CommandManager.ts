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
import {
    createCommands,
    CommandFactory,
} from '../commands';
import { DependencyTreeProvider } from '../providers/DependencyTreeProvider';
import { ProviderManager } from './ProviderManager';

export interface CommandContext {
    extensionContext: vscode.ExtensionContext;
    workspaceRoot: string | undefined;
    providerManager?: ProviderManager;
}

export class CommandManager {
    private commands: CommandFactory;

    constructor(private context: CommandContext) {
        this.commands = createCommands(context);

        if (context.providerManager && context.workspaceRoot) {
            const dependencyProvider = context.providerManager.getProvider<DependencyTreeProvider>('dependency');
            if (dependencyProvider) {
                this.commands.dependencyCommands.setDependencyProvider(dependencyProvider);
            }
        }
    }

    public registerAllCommands(): vscode.Disposable[] {
        const disposables: vscode.Disposable[] = [];

        // Register solution commands
        disposables.push(
            vscode.commands.registerCommand('solutions-manager.createSolution',
                () => this.commands.solutionCommands.createSolution()),
            vscode.commands.registerCommand('solutions-manager.refreshSolutionsList',
                () => this.commands.solutionCommands.refreshSolutionsList()),
            vscode.commands.registerCommand('solutions-manager.openSolution',
                (path: string) => this.commands.solutionCommands.openSolution(path))
        );

        // Register debug commands
        disposables.push(
            vscode.commands.registerCommand('solutions-manager.debugtransactionmethods',
                () => this.commands.debugCommands.debugTransactionMethods()),
            vscode.commands.registerCommand('solutions-manager.debugsolutiondashui',
                () => this.commands.debugCommands.debugSolutionDashUI())
        );

        // Register dependency commands
        disposables.push(
            vscode.commands.registerCommand('solutions-manager.addDependency',
                () => this.commands.dependencyCommands.addDependency()),
            vscode.commands.registerCommand('solutions-manager.updateDependency',
                (item: any) => this.commands.dependencyCommands.updateDependency(item)),
            vscode.commands.registerCommand('solutions-manager.removeDependency',
                (item: any) => this.commands.dependencyCommands.removeDependency(item)),
            vscode.commands.registerCommand('solutions-manager.syncDependencies',
                () => this.commands.dependencyCommands.syncDependencies())
        );

        // Register development commands
        disposables.push(
            vscode.commands.registerCommand('solutions-manager.installDevEnvironment',
                () => this.commands.developmentCommands.installDevEnvironment()),
            vscode.commands.registerCommand('solutions-manager.showEnvironmentConfig',
                (solutionName?: string, solutionPath?: string) =>
                    this.commands.developmentCommands.showEnvironmentConfig(solutionName, solutionPath)),
        );

        // Register help commands
        disposables.push(
            vscode.commands.registerCommand('solutions-manager.openExtensionHelp',
                () => this.commands.helpCommands.openExtensionHelp()),
            vscode.commands.registerCommand('solutions-manager.openVSCodeExtensionPage',
                () => this.commands.helpCommands.openVSCodeExtensionPage()),
            vscode.commands.registerCommand('solutions-manager.openGitHubIssues',
                () => this.commands.helpCommands.openGitHubIssues()),
            vscode.commands.registerCommand('solutions-manager.openGitHubRepo',
                () => this.commands.helpCommands.openGitHubRepo()),
            vscode.commands.registerCommand('solutions-manager.showQuickHelp',
                () => this.commands.helpCommands.showQuickHelp()),
            vscode.commands.registerCommand('solutions-manager.showTroubleshootingGuide',
                () => this.commands.helpCommands.showTroubleshootingGuide()),
            vscode.commands.registerCommand('solutions-manager.showAboutDialog',
                () => this.commands.helpCommands.showAboutDialog()),
            vscode.commands.registerCommand('solutions-manager.openFeedbackForm',
                () => this.commands.helpCommands.openFeedbackForm()),
        );

        return disposables;
    }

    public dispose(): void {
        // Clean up resources if needed
        this.commands.debugCommands.dispose();
        this.commands.developmentCommands.dispose();
    }

    // Utility methods for accessing specific command instances
    public getSolutionCommands() { return this.commands.solutionCommands; }
    public getDebugCommands() { return this.commands.debugCommands; }
    public getDependencyCommands() { return this.commands.dependencyCommands; }
    public getDevelopmentCommands() { return this.commands.developmentCommands; }
    public getHelpCommands() { return this.commands.helpCommands; }
}