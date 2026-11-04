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

export class SolutionTreeProvider implements vscode.TreeDataProvider<SolutionTreeItem> {
    constructor(private readonly context: string) {}

    getTreeItem(element: SolutionTreeItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: SolutionTreeItem): Thenable<SolutionTreeItem[]> {
        if (!element) {
            switch (this.context) {
                case 'debugging':
                    return Promise.resolve(this.getDebuggingItems());
                case 'solutionCustomization':
                    return Promise.resolve(this.getSolutionCustomizationItems());
                default:
                    return Promise.resolve([]);
            }
        }
        return Promise.resolve([]);
    }

    private getDebuggingItems(): SolutionTreeItem[] {
        return [
            new SolutionTreeItem(
                'Debug transaction methods',
                vscode.TreeItemCollapsibleState.None,
                {
                    command: 'solutions-manager.debugtransactionmethods',
                    title: 'Debug transaction methods'
                },
                new vscode.ThemeIcon('debug')
            ),
            new SolutionTreeItem(
                'Debug solution dash UI',
                vscode.TreeItemCollapsibleState.None,
                {
                    command: 'solutions-manager.debugsolutiondashui',
                    title: 'Debug solution dash UI'
                },
                new vscode.ThemeIcon('debug')
            )
        ];
    }

    private getSolutionCustomizationItems(): SolutionTreeItem[] {
        return [
            new SolutionTreeItem(
                'Add step',
                vscode.TreeItemCollapsibleState.None,
                {
                    command: 'solutions-manager.addStep',
                    title: 'Add step'
                },
                new vscode.ThemeIcon('add')
            )
        ];
    }
}

export class SolutionTreeItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly command?: vscode.Command,
        public readonly iconPath?: vscode.ThemeIcon
    ) {
        super(label, collapsibleState);
        this.tooltip = label;
        this.description = '';
    }
}