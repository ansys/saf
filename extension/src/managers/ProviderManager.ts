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
import { DependencyTreeProvider } from '../providers/DependencyTreeProvider';
import { SAFSolutionsProvider } from '../providers/SAFSolutionsProvider';
import { HelpTreeProvider } from '../providers/HelpTreeProvider';
import { SolutionRunViewProvider } from '../providers/SolutionRunViewProvider';
import { ExecuteCommandProvider } from '../providers/ExecuteCommandProvider';
import { BuildInstallerProvider } from '../providers/BuildInstallerProvider';
import { CreateSolutionViewProvider } from '../providers/CreateSolutionViewProvider';
import { SolutionSetupProvider } from '../providers/SolutionSetupProvider';
import { EnvironmentService } from '../services/EnvironmentService';
import { CustomizeSolutionViewProvider } from '../providers/CustomizeSolutionViewProvider';
import { ArchiveSolutionProvider } from '../providers/ArchiveSolutionProvider';

export interface ProviderContext {
    extensionUri: vscode.Uri;
    workspaceRoot: string | undefined;
    extensionContext: vscode.ExtensionContext;
}

interface DisposableProvider {
    dispose(): void;
}

function isDisposableProvider(provider: any): provider is DisposableProvider {
    return provider !== null && provider !== undefined && typeof provider.dispose === 'function';
}

export class ProviderManager {
    private readonly providers: Map<string, any> = new Map();
    private readonly disposables: vscode.Disposable[] = [];
    private readonly environmentService: EnvironmentService;

    constructor(private readonly context: ProviderContext) {
        this.environmentService = new EnvironmentService(context.extensionContext);
    }

    public registerAllProviders(): vscode.Disposable[] {
        this.registerTreeProviders();
        this.registerWebviewProviders();
        return this.disposables;
    }

    private registerTreeProviders(): void {
        // const debuggingProvider = new SolutionTreeProvider('debugging');

        const safSolutionsProvider = SAFSolutionsProvider.getInstance();
        const helpTreeProvider = new HelpTreeProvider();

        // vscode.window.registerTreeDataProvider('debugging', debuggingProvider);
        vscode.window.registerTreeDataProvider('safSolutions', safSolutionsProvider);
        vscode.window.registerTreeDataProvider('helpAndSupport', helpTreeProvider);

        const dependencyProvider = new DependencyTreeProvider(this.context.workspaceRoot || '');
        vscode.window.registerTreeDataProvider('poetryDependencies', dependencyProvider);
        this.providers.set('dependency', dependencyProvider);

        this.providers.set('safSolutions', safSolutionsProvider);

        safSolutionsProvider.refresh();
    }

    private registerWebviewProviders(): void {
        const createSolutionProvider = new CreateSolutionViewProvider(this.context.extensionUri);
        this.disposables.push(
            vscode.window.registerWebviewViewProvider(
                CreateSolutionViewProvider.viewType,
                createSolutionProvider
            )
        );

        const solutionConfigProvider = new SolutionRunViewProvider(
            this.context.extensionUri,
            this.environmentService
        );
        this.disposables.push(
            vscode.window.registerWebviewViewProvider(
                SolutionRunViewProvider.viewType,
                solutionConfigProvider
            )
        );

        const solutionSetupProvider = new SolutionSetupProvider(this.context.extensionUri);
        this.disposables.push(
            vscode.window.registerWebviewViewProvider(
                SolutionSetupProvider.viewType,
                solutionSetupProvider
            )
        );

        const customizeSolutionProvider = new CustomizeSolutionViewProvider(this.context.extensionUri);
        this.disposables.push(
            vscode.window.registerWebviewViewProvider(
                CustomizeSolutionViewProvider.viewType,
                customizeSolutionProvider
            )
        );

        const executeCommandProvider = new ExecuteCommandProvider(this.context.extensionUri);
        this.disposables.push(
            vscode.window.registerWebviewViewProvider(
                ExecuteCommandProvider.viewType,
                executeCommandProvider
            )
        );

        const buildInstallerProvider = new BuildInstallerProvider(this.context.extensionUri);
        this.disposables.push(
            vscode.window.registerWebviewViewProvider(
                BuildInstallerProvider.viewType,
                buildInstallerProvider
            )
        );

        const archiveSolutionProvider = ArchiveSolutionProvider.getInstance(this.context.extensionUri);
        this.disposables.push(
            vscode.window.registerWebviewViewProvider(
                ArchiveSolutionProvider.viewType,
                archiveSolutionProvider
            )
        );

        this.providers.set('createSolution', createSolutionProvider);
        this.providers.set('solutionConfig', solutionConfigProvider);
        this.providers.set('solutionSetup', solutionSetupProvider);
        this.providers.set('customizeSolution', customizeSolutionProvider);
        this.providers.set('executeCommand', executeCommandProvider);
        this.providers.set('buildInstaller', buildInstallerProvider);
        this.providers.set('archiveSolution', archiveSolutionProvider);
        this.providers.set('environment', this.environmentService);
    }

    public getProvider<T>(name: string): T | undefined {
        return this.providers.get(name) as T;
    }

    public refreshProvider(name: string): void {
        const provider = this.providers.get(name);
        if (provider && typeof provider.refresh === 'function') {
            provider.refresh();
        }
    }

    public dispose(): void {
        this.disposables.forEach(disposable => disposable.dispose());

        this.providers.forEach(provider => {
            if (isDisposableProvider(provider)) {
                provider.dispose();
            }
        });

        this.providers.clear();
    }

    public getEnvironmentService(): EnvironmentService {
        return this.environmentService;
    }
}