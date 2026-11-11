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

interface SafCliInfo {
    executablePath: string,
    version: string,
}

export interface SelectedSolution {
    name: string;
    displayName: string;
    path: string;
}

export class StorageService {
    private static instance: StorageService;
    private readonly context: vscode.ExtensionContext;

    constructor(context: vscode.ExtensionContext) {
        StorageService.instance = this;
        this.context = context;
    }

    static getInstance(): StorageService {
        if (!StorageService.instance) {
            throw new Error('StorageService is not initialized.');
        }
        return StorageService.instance;
    }

    static getSafCliInfo(): SafCliInfo | null {
        const instance = this.getInstance();
        return instance.context.globalState.get<SafCliInfo>('safCliInfo') || null;
    }

    static getSafCliExecutablePath(): string {
        const safCliInfo = this.getSafCliInfo();
        if (!safCliInfo) {
            throw new Error('SAF CLI is not installed. Please install SAF CLI to proceed.');
        };
        return safCliInfo.executablePath;
    }

    static getSafCliExecutableCommand(): string {
        const executablePath = this.getSafCliExecutablePath();
        return executablePath.includes(' ') ? `"${executablePath}"` : executablePath;
    }

    static isTerminalPowerShell(): boolean {
        const shell = vscode.env.shell?.toLowerCase() ?? '';
        return shell.includes('powershell') || shell.endsWith('pwsh') || shell.endsWith('pwsh.exe');
    }

    static getSafCliTerminalCommand(): string {
        const executablePath = this.getSafCliExecutablePath();
        if (!executablePath.includes(' ')) {
            return executablePath;
        }
        if (process.platform === 'win32' && this.isTerminalPowerShell()) {
            return `& "${executablePath}"`;
        }
        return `"${executablePath}"`;
    }

    static getSafCliVersion(): string | null {
        const safCliInfo = this.getSafCliInfo();
        return safCliInfo ? safCliInfo.version : null;
    }

    static async setSafCliInfo(executablePath: string, version: string): Promise<void> {
        const instance = this.getInstance();
        const safCliInfo: SafCliInfo = { executablePath, version };
        await instance.context.globalState.update('safCliInfo', safCliInfo);
    }

    static async clearSafCliInfo(): Promise<void> {
        const instance = this.getInstance();
        await instance.context.globalState.update('safCliInfo', undefined);
    }

    /**
     * Generate a workspace-specific storage key from workspace path.
     *
     * Required because:
     * - Each workspace needs isolated solution selection (same extension, different workspaces)
     * - VS Code globalState keys cannot contain file path characters (/, \, :, etc.)
     * - Keys must be deterministic (same workspace = same key across sessions)
     * - Keys should be reasonably short to avoid storage limits
     */
    private static getWorkspaceKey(workspacePath: string): string {
        const normalized = path.normalize(workspacePath);
        const base64 = Buffer.from(normalized).toString('base64');
        const sanitized = base64.replace(/[^a-zA-Z0-9]/g, '_').substring(0, 50);
        return `selectedSolution_${sanitized}`;
    }

    static getSelectedSolution(workspacePath: string | undefined): SelectedSolution | undefined {
        if (!workspacePath) {
            return undefined;
        }
        const instance = this.getInstance();
        const key = this.getWorkspaceKey(workspacePath);
        return instance.context.globalState.get<SelectedSolution>(key) || undefined;
    }

    static async setSelectedSolution(workspacePath: string | undefined, solution: SelectedSolution | undefined): Promise<void> {
        if (!workspacePath) {
            return;
        }
        const instance = this.getInstance();
        const key = this.getWorkspaceKey(workspacePath);
        await instance.context.globalState.update(key, solution);
    }

    static getLastTargetDirectory(): string | undefined {
        const instance = this.getInstance();
        return instance.context.globalState.get<string>('lastTargetDirectory');
    }

    static async setLastTargetDirectory(directory: string): Promise<void> {
        const instance = this.getInstance();
        await instance.context.globalState.update('lastTargetDirectory', directory);
    }
}
