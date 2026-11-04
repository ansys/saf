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
import * as fs from 'node:fs';
import * as path from 'node:path';
import { dependencyService, DependencyStatus } from '../services/DependencyService';

export class DependencyTreeProvider implements vscode.TreeDataProvider<DependencyTreeItem | DependencyStatusItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<DependencyTreeItem | DependencyStatusItem | undefined | null | void> =
        new vscode.EventEmitter<DependencyTreeItem | DependencyStatusItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<DependencyTreeItem | DependencyStatusItem | undefined | null | void> =
        this._onDidChangeTreeData.event;
    private _fileWatchers: vscode.Disposable[] = [];
    private _workspaceChangeListener: vscode.Disposable;

    constructor(private workspaceRoot: string) {
        this.setupFileWatchers();

        // Watch for workspace folder changes (set up once)
        this._workspaceChangeListener = vscode.workspace.onDidChangeWorkspaceFolders(() => {
            this.updateWorkspaceRoot();
        });
    }

    private setupFileWatchers(): void {
        if (!this.workspaceRoot) {
            return;
        }

        // Watch for changes to both pyproject.toml and poetry.lock
        const pyprojectPattern = new vscode.RelativePattern(this.workspaceRoot, 'pyproject.toml');
        const lockPattern = new vscode.RelativePattern(this.workspaceRoot, 'poetry.lock');

        const watch = (pattern: vscode.RelativePattern) => {
            const watcher = vscode.workspace.createFileSystemWatcher(pattern);
            watcher.onDidChange(() => this.refresh());
            watcher.onDidCreate(() => this.refresh());
            watcher.onDidDelete(() => this.refresh());
            return watcher;
        };

        this._fileWatchers.push(watch(pyprojectPattern));
        this._fileWatchers.push(watch(lockPattern));
    }

    private updateWorkspaceRoot(): void {
        const newRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        if (newRoot !== this.workspaceRoot) {
            this.workspaceRoot = newRoot;
            // Dispose old file watchers
            this._fileWatchers.forEach(w => w.dispose());
            this._fileWatchers = [];
            // Setup new file watchers for new workspace
            this.setupFileWatchers();
            this.refresh();
        }
    }

    private lastValidDependencies: any | undefined;
    private lastStatus: 'ok' | 'corrupt' | 'outOfSync' = 'ok';
    private refreshTimeout: NodeJS.Timeout | undefined;
    private DEBOUNCE_DELAY_MS = 500;

    private async isValidSolutionDirectory(directory: string): Promise<boolean> {
        try {
            const srcPattern = new vscode.RelativePattern(directory, 'src/**/solution/definition.py');
            const excludePattern = new vscode.RelativePattern(directory, '{**/.venv/**,**/.git/**,**/node_modules/**}');
            const matches = await vscode.workspace.findFiles(srcPattern, excludePattern, 1);
            return matches.length > 0;
        } catch (error) {
            console.error('Failed to validate solution directory:', error);
            return false;
        }
    }

    private async isPoetryInstalled(directory: string): Promise<boolean> {
        const venvPath = path.join(directory, '.venv');
        const poetryPath = process.platform === 'win32'
            ? path.join(venvPath, 'Scripts', 'poetry.exe')
            : path.join(venvPath, 'bin', 'poetry');
        try {
            await fs.promises.access(poetryPath);
            return true;
        } catch {
            return false;
        }
    }

    refresh(): void {
        if (this.refreshTimeout) {
            clearTimeout(this.refreshTimeout);
        }
        this.refreshTimeout = setTimeout(() => {
            this._onDidChangeTreeData.fire();
        }, this.DEBOUNCE_DELAY_MS);
    }

    dispose(): void {
        this._fileWatchers.forEach(w => w.dispose());
        this._fileWatchers = [];
        this._workspaceChangeListener.dispose();
    }

    getTreeItem(element: DependencyTreeItem | DependencyStatusItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: DependencyTreeItem | DependencyStatusItem): Promise<(DependencyTreeItem | DependencyStatusItem)[]> {
        try {
            if (!element) {
                return await this.getRootLevelChildren();
            } else if (element instanceof DependencyTreeItem && element.contextValue === 'group') {
                return this.getGroupChildren(element);
            }
            return [];
        } catch (error) {
            console.error('Unexpected error in getChildren:', error);
            return [];
        }
    }

    private async getRootLevelChildren(): Promise<(DependencyTreeItem | DependencyStatusItem)[]> {
        if (!this.workspaceRoot) {
            return [this.createStatusItem('Open a solution to view dependencies', 'noSolution', 'info')];
        }

        // eslint-disable-next-line security/detect-non-literal-fs-filename
        const pyprojectExists = fs.existsSync(path.join(this.workspaceRoot, 'pyproject.toml'));

        if (!pyprojectExists) {
            return await this.handleMissingPyproject();
        }

        const items: (DependencyTreeItem | DependencyStatusItem)[] = [];
        items.push(this.createSolutionInfoItem());

        if (!(await this.isPoetryInstalled(this.workspaceRoot))) {
            items.push(this.createStatusItem(
                'Development environment not installed yet',
                'noEnvironment',
                'warning'
            ));
            return items;
        }

        return await this.loadAndDisplayDependencies(items);
    }

    private async handleMissingPyproject(): Promise<DependencyStatusItem[]> {
        if (!(await this.isValidSolutionDirectory(this.workspaceRoot))) {
            return [this.createStatusItem(
                'The current directory is not a valid solution',
                'invalidSolution',
                'warning'
            )];
        }
        return [this.createStatusItem('pyproject.toml not found in this solution', 'missingPyproject', 'warning')];
    }

    private createSolutionInfoItem(): DependencyStatusItem {
        const workspaceFolder = vscode.workspace.workspaceFolders?.find(
            folder => folder.uri.fsPath === this.workspaceRoot
        );
        const solutionName = workspaceFolder?.name || this.workspaceRoot.split(/[\\/]/).pop() || 'Unknown';

        return new DependencyStatusItem(
            `Solution: ${solutionName}`,
            '',
            vscode.TreeItemCollapsibleState.None,
            'solutionInfo',
            new vscode.ThemeIcon('folder')
        );
    }

    private createStatusItem(message: string, contextValue: string, iconType: 'info' | 'warning' | 'error'): DependencyStatusItem {
        const iconConfig = {
            info: new vscode.ThemeIcon('info'),
            warning: new vscode.ThemeIcon('warning', new vscode.ThemeColor('notificationsWarningIcon.foreground')),
            error: new vscode.ThemeIcon('error', new vscode.ThemeColor('errorForeground'))
        };

        return new DependencyStatusItem(
            message,
            '',
            vscode.TreeItemCollapsibleState.None,
            contextValue,
            // eslint-disable-next-line security/detect-object-injection
            iconConfig[iconType]
        );
    }

    private async loadAndDisplayDependencies(items: (DependencyTreeItem | DependencyStatusItem)[]): Promise<(DependencyTreeItem | DependencyStatusItem)[]> {
        const status = await dependencyService.getDependencyStatus(this.workspaceRoot);

        const isLockFileMissing = status.isCorrupt &&
            status.error &&
            (status.error.includes('poetry.lock') && status.error.includes('not found'));

        if (isLockFileMissing) {
            const statusItem = this.createStatusItem(
                'Click to set up development environment',
                'lockFileMissing',
                'warning'
            );
            // Make it clickable to open the setup solution panel
            statusItem.command = {
                command: 'solutions-manager.solutionSetup.focus',
                title: 'Open Setup Panel'
            };
            items.push(statusItem);
            return items;
        }

        const currentStatus = status.isCorrupt ? 'corrupt' : (status.isOutOfSync ? 'outOfSync' : 'ok');
        this.handleStatusNotifications(currentStatus, status);
        this.lastStatus = currentStatus;

        if (status.isCorrupt) {
            items.push(this.createStatusItem(
                'Invalid pyproject.toml',
                'corrupt',
                'error'
            ));
        }

        if (status.isOutOfSync) {
            items.push(new DependencyStatusItem(
                'Click here to sync dependencies',
                '',
                vscode.TreeItemCollapsibleState.None,
                'outOfSync',
                new vscode.ThemeIcon('warning', new vscode.ThemeColor('notificationsWarningIcon.foreground'))
            ));
        }

        if (!status.isCorrupt) {
            try {
                const dependencies = await dependencyService.getDependencies(this.workspaceRoot);
                this.lastValidDependencies = dependencies;
            } catch (error) {
                console.error('Failed to update dependencies (using cache):', error);
            }
        }

        if (this.lastValidDependencies) {
            const groupItems = Object.entries(this.lastValidDependencies).map(([group, deps]) =>
                new DependencyTreeItem(
                    group,
                    deps as any,
                    vscode.TreeItemCollapsibleState.Collapsed,
                    'group',
                    undefined,
                    new vscode.ThemeIcon('package')
                )
            );
            items.push(...groupItems);
        }

        return items;
    }

    private handleStatusNotifications(currentStatus: string, status: DependencyStatus): void {
        if (currentStatus === this.lastStatus || currentStatus === 'ok') {
            return;
        }

        if (currentStatus === 'corrupt') {
            vscode.window.showErrorMessage(`Invalid pyproject.toml: ${status.error || 'Parsing failed'}`);
        } else if (currentStatus === 'outOfSync') {
            vscode.window.showWarningMessage(
                'Dependencies are out of sync with lock file.',
                'Sync Dependencies'
            ).then(selection => {
                if (selection === 'Sync Dependencies') {
                    vscode.commands.executeCommand('solutions-manager.syncDependencies');
                }
            });
        }
    }

    private getGroupChildren(element: DependencyTreeItem): DependencyTreeItem[] {
        return Object.entries(element.dependencies).map(([name, details]: [string, any]) =>
            new DependencyTreeItem(
                name,
                details,
                vscode.TreeItemCollapsibleState.None,
                'dependency',
                element.label.toString(),
                new vscode.ThemeIcon('library')
            )
        );
    }
}

export class DependencyStatusItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly details: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly contextValue: string,
        public readonly icon?: vscode.ThemeIcon
    ) {
        super(label, collapsibleState);
        this.description = details;
        this.tooltip = details;
        this.iconPath = icon;

        if (contextValue === 'outOfSync') {
            this.command = {
                command: 'solutions-manager.syncDependencies',
                title: 'Sync Dependencies'
            };
        }
    }
}

export class DependencyTreeItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly dependencies: any,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly contextValue: string,
        public readonly group?: string,
        public readonly icon?: vscode.ThemeIcon
    ) {
        super(label, collapsibleState);

        if (contextValue === 'dependency') {
            let version: string;
            let source: string | undefined;

            if (typeof dependencies === 'string') {
                version = dependencies;
            } else if (typeof dependencies === 'object') {
                version = dependencies.version || dependencies.python || 'unknown';
                source = dependencies.source;
            } else {
                version = 'unknown';
            }

            this.description = version;
            this.tooltip = new vscode.MarkdownString(`**${label}**\nVersion: ${version}`);

            if (source) {
                this.tooltip.appendMarkdown(`\nSource: ${source}`);
            }
        } else {
            this.tooltip = `${label} dependencies`;
            this.iconPath = new vscode.ThemeIcon('package');
        }
    }
}