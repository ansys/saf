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

export class HelpTreeProvider implements vscode.TreeDataProvider<HelpTreeItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<HelpTreeItem | undefined | null | void> =
        new vscode.EventEmitter<HelpTreeItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<HelpTreeItem | undefined | null | void> =
        this._onDidChangeTreeData.event;

    constructor() {}

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: HelpTreeItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: HelpTreeItem): Thenable<HelpTreeItem[]> {
        if (!element) {
            return Promise.resolve([
                new HelpTreeItem(
                    "Extension documentation",
                    "View comprehensive extension help and documentation",
                    vscode.TreeItemCollapsibleState.None,
                    {
                        command: 'solutions-manager.openExtensionHelp',
                        title: 'Open Extension Help',
                        arguments: []
                    },
                    'help-documentation',
                    new vscode.ThemeIcon('book')
                ),
                new HelpTreeItem(
                    "Report issues",
                    "Report bugs or request features on GitHub",
                    vscode.TreeItemCollapsibleState.None,
                    {
                        command: 'solutions-manager.openGitHubIssues',
                        title: 'Open GitHub Issues',
                        arguments: []
                    },
                    'help-issues',
                    new vscode.ThemeIcon('bug')
                ),
                new HelpTreeItem(
                    "GitHub repository",
                    "View the complete source code and documentation",
                    vscode.TreeItemCollapsibleState.None,
                    {
                        command: 'solutions-manager.openGitHubRepo',
                        title: 'Open GitHub Repository',
                        arguments: []
                    },
                    'help-repo',
                    new vscode.ThemeIcon('github')
                ),
                new HelpTreeItem(
                    "Feedback",
                    "Provide feedback about the extension",
                    vscode.TreeItemCollapsibleState.None,
                    {
                        command: 'solutions-manager.openFeedbackForm',
                        title: 'Open Feedback Form',
                        arguments: []
                    },
                    'help-feedback',
                    new vscode.ThemeIcon('feedback')
                )
            ]);
        }
        return Promise.resolve([]);
    }
}

export class HelpTreeItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly tooltip: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly command?: vscode.Command,
        public readonly contextValue: string = 'helpAndSupport',
        public readonly iconPath?: vscode.ThemeIcon
    ) {
        super(label, collapsibleState);
        this.tooltip = tooltip;
    }
}