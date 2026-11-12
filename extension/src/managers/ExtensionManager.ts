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
import { CommandManager, CommandContext } from './CommandManager';
import { ProviderManager, ProviderContext } from './ProviderManager';
import { ConfigurationPanel } from '../services/ConfigurationPanel';
import { getWorkspaceRoot } from '../utils/workspaceUtils';

export class ExtensionManager {
    private static instance: ExtensionManager | undefined;
    private commandManager: CommandManager | undefined;
    private providerManager: ProviderManager | undefined;
    private configPanel: ConfigurationPanel | undefined;

    constructor(private context: vscode.ExtensionContext) {
        ExtensionManager.instance = this;
    }

    public async initialize(): Promise<void> {
        const workspaceRoot = getWorkspaceRoot();

        // Initialize managers
        await this.initializeProviders(workspaceRoot);
        await this.initializeCommands(workspaceRoot, this.providerManager);

        // Setup additional services
        this.setupPanelVisibilityFromSettings();

        console.log('Extension managers initialized successfully');
    }

    private async initializeProviders(workspaceRoot: string | undefined): Promise<void> {
        const providerContext: ProviderContext = {
            extensionUri: this.context.extensionUri,
            workspaceRoot,
            extensionContext: this.context
        };

        this.providerManager = new ProviderManager(providerContext);
        const providerDisposables = this.providerManager.registerAllProviders();

        this.context.subscriptions.push(...providerDisposables);

        console.log('Providers initialized');
    }

    private async initializeCommands(workspaceRoot: string | undefined, providerManager: ProviderManager | undefined): Promise<void> {
        const commandContext: CommandContext = {
            extensionContext: this.context,
            workspaceRoot,
            providerManager
        };

        this.commandManager = new CommandManager(commandContext);
        const commandDisposables = this.commandManager.registerAllCommands();

        this.context.subscriptions.push(...commandDisposables);

        console.log('Commands registered');
    }

    private setupPanelVisibilityFromSettings(): void {
        this.applyPanelVisibilitySettings();

        this.context.subscriptions.push(
            vscode.workspace.onDidChangeConfiguration(e => {
                if (e.affectsConfiguration('solutions-manager')) {
                    this.applyPanelVisibilitySettings();
                }
            })
        );
    }

    private async applyPanelVisibilitySettings(): Promise<void> {
        const config = vscode.workspace.getConfiguration('solutions-manager');

        await this.applyPanelVisibilitySetting(
            config,
            'enableSolutionsList',
            'solutionsManager.panel.safSolutions.visible',
            'Solutions List'
        );
    }

    private async applyPanelVisibilitySetting(
        config: vscode.WorkspaceConfiguration,
        settingName: string,
        contextKey: string,
        panelName: string
    ): Promise<void> {
        const isEnabled = config.get<boolean>(settingName);
        try {
            await vscode.commands.executeCommand('setContext', contextKey, isEnabled);
        } catch (error) {
            vscode.window.showErrorMessage(
                `Failed to apply ${panelName} panel visibility setting: ${error instanceof Error ? error.message : String(error)}`
            );
            return;
        }
    }

    public static cleanup(): void {
        if (ExtensionManager.instance) {
            ExtensionManager.instance.dispose();
            ExtensionManager.instance = undefined;
        }
    }

    private dispose(): void {
        try {
            this.commandManager?.dispose();
            this.providerManager?.dispose();
            console.log('Extension cleanup completed');
        } catch (error) {
            console.error('Error during extension cleanup:', error);
        }
    }

    // Utility methods for accessing managers
    public getCommandManager(): CommandManager | undefined {
        return this.commandManager;
    }

    public getProviderManager(): ProviderManager | undefined {
        return this.providerManager;
    }

    public getConfigurationPanel(): ConfigurationPanel | undefined {
        return this.configPanel;
    }

    public static getInstance(): ExtensionManager | undefined {
        return ExtensionManager.instance;
    }
}