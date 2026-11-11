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
import { StorageService } from '../services/StorageService';
import { execFileAsync } from '../utils/exec';
import { fileExistsSync } from '../utils/fsUtils';

export interface SAFSolution {
    name: string;
    rootDirectory: string;
    displayName: string;
}

export class SAFSolutionsProvider implements vscode.TreeDataProvider<SAFSolutionItem> {
    private static instance: SAFSolutionsProvider;
    private _onDidChangeTreeData: vscode.EventEmitter<SAFSolutionItem | undefined | null | void> =
        new vscode.EventEmitter<SAFSolutionItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<SAFSolutionItem | undefined | null | void> =
        this._onDidChangeTreeData.event;

    // Private constructor to enforce the singleton pattern; use getInstance() to access the single provider instance.
    private constructor() {}

    static getInstance(): SAFSolutionsProvider {
        if (!SAFSolutionsProvider.instance) {
            SAFSolutionsProvider.instance = new SAFSolutionsProvider();
        }
        return SAFSolutionsProvider.instance;
    }

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: SAFSolutionItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: SAFSolutionItem): Promise<SAFSolutionItem[]> {
        if (element) {
            return [];
        }

        try {
            const solutions = await this.getSAFSolutions();

            if (solutions.length === 0) {
                // Return an empty array - the viewsWelcome will be shown
                return [
                    new SAFSolutionItem(
                        'No solutions found',
                        '',
                        'Click to refresh',
                        vscode.TreeItemCollapsibleState.None,
                        {
                            command: 'solutions-manager.refreshSolutionsList',
                            title: 'Refresh',
                            arguments: []
                        }
                    )
                ];
            }

            return solutions.map(solution =>
                new SAFSolutionItem(
                    solution.name,
                    solution.rootDirectory,
                    solution.displayName,
                    vscode.TreeItemCollapsibleState.None,
                    {
                        command: 'solutions-manager.openSolution',
                        title: 'Open Solution',
                        arguments: [solution.rootDirectory]
                    }
                )
            );
        } catch (error) {
            console.error('Error getting SAF solutions:', error);

            // Create a special tree item to display the error
            return [
                new SAFSolutionItem(
                    'Error retrieving solutions',
                    '',
                    'Click to retry',
                    vscode.TreeItemCollapsibleState.None,
                    {
                        command: 'solutions-manager.refreshSolutionsList',
                        title: 'Refresh',
                        arguments: []
                    }
                )
            ];
        }
    }

    public async getSAFSolutions(): Promise<SAFSolution[]> {
        try {

            // Run the command
            const safCliExecutable = StorageService.getSafCliExecutablePath();
            if (fileExistsSync(safCliExecutable)) {
                const { stdout } = await execFileAsync(safCliExecutable, ["solutions"]);
                // Parse the output
                return this.parseSAFOutput(stdout);
            } else {
                return [];
            }

        } catch (error) {
            console.error(`Failed to get SAF solutions: ${error}`);

            // Show a more user-friendly error
            vscode.window.showErrorMessage(
                `Failed to get SAF solutions. Make sure SAF CLI is installed and solutions have been created.`
            );

            return [];
        }
    }

    private parseSAFOutput(output: string): SAFSolution[] {
        const solutions: SAFSolution[] = [];
        let currentSolutionName: string | undefined;
        let currentSolutionDisplayName: string | undefined;
        let currentSolutionRootDirectory: string | undefined;

        // Split the output by lines
        const lines = output.split('\n');

        for (const line of lines) {
            if (!line.trim()) {
                continue;
            } else if (!line.startsWith(' ') && !line.startsWith('\t')) {
                currentSolutionName = line.trim();
            } else if (/Root\s+[Dd]irectory:/.test(line)) {
                const match = line.match(/Root\s+[Dd]irectory:\s*(.*)/);
                if (match && match[1]) {
                    currentSolutionRootDirectory = match[1].trim();
                }
            } else if (/Display\s+[Nn]ame:/.test(line)) {
                const match = line.match(/Display\s+[Nn]ame:\s*(.*)/);
                if (match && match[1]) {
                    currentSolutionDisplayName = match[1].trim();
                }

                if (currentSolutionName && currentSolutionRootDirectory && currentSolutionDisplayName) {
                    solutions.push({
                        name: currentSolutionName,
                        rootDirectory: currentSolutionRootDirectory,
                        displayName: currentSolutionDisplayName
                    });
                }
            }
        }

        return solutions;
    }
}

export class SAFSolutionItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly rootDirectory: string,
        public readonly displayName: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly command?: vscode.Command
    ) {
        super(label, collapsibleState);
        this.description = rootDirectory;
        this.tooltip = `Root directory: ${this.rootDirectory}\nDisplay Name: ${this.displayName}`;
        this.iconPath = new vscode.ThemeIcon('folder');
        this.contextValue = 'safSolution';
    }
}
