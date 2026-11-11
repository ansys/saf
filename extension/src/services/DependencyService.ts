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


import * as path from 'node:path';
import * as fs from 'node:fs';
import { promisify } from 'node:util';
import * as vscode from 'vscode';
import * as toml from 'toml';
import { systemService } from './SystemService';
import { isValidVersionConstraint } from '../utils/validation';

const readFile = promisify(fs.readFile);

export interface DependencyStatus {
    isCorrupt: boolean;
    error?: string;
    isOutOfSync: boolean;
    exists: boolean;
}

export class DependencyService {
    private poetryExecutable: string;

    constructor() {
        this.poetryExecutable = process.platform === 'win32'
            ? path.join('.venv', 'Scripts', 'poetry.exe')
            : path.join('.venv', 'bin', 'poetry');
    }

    async getDependencyStatus(projectPath: string): Promise<DependencyStatus> {
        try {
            const pyprojectPath = path.join(projectPath, 'pyproject.toml');

            // eslint-disable-next-line security/detect-non-literal-fs-filename
            if (!fs.existsSync(pyprojectPath)) {
                return { exists: false, isCorrupt: false, isOutOfSync: false };
            }

            return await this.validateProjectHealth(projectPath);

        } catch (err) {
            return {
                exists: true,
                isCorrupt: true,
                error: err instanceof Error ? err.message : String(err),
                isOutOfSync: false
            };
        }
    }

    private async validateProjectHealth(projectPath: string): Promise<DependencyStatus> {
        // We use Poetry as the single source of truth for validity.
        // We first check structure and lock consistency strictly
        try {
            await systemService.executeCommand(this.poetryExecutable, ['check', '--lock'], { cwd: projectPath });
            // If command succeeds, everything is perfect.
            return { exists: true, isCorrupt: false, isOutOfSync: false };
        } catch (error: any) {
            const message = error instanceof Error ? error.message : String(error);

            // If it fails, we determine WHY it failed.
            // "Error: poetry.lock is not consistent with pyproject.toml" -> OutOfSync
            // Any other error -> Corrupt / Invalid Configuration
            if (message.includes('not consistent') || message.includes('changed significantly')) {
                return { exists: true, isCorrupt: false, isOutOfSync: true };
            }

            // Clean up the error message for presentation
            const lines = message.split('\n');
            const errorLine = lines.find(line => line.trim().startsWith('Error:')) || lines[0];
            const cleanError = errorLine.replace(/^.*Command execution failed:.*Error:/, 'Error:').trim();

            return {
                exists: true,
                isCorrupt: true,
                error: cleanError,
                isOutOfSync: false
            };
        }
    }

    async getDependencies(projectPath: string): Promise<any> {
        try {
            const pyprojectPath = path.join(projectPath, 'pyproject.toml');
            const content = await readFile(pyprojectPath, 'utf8');
            const config = toml.parse(content);

            const dependencies: { [key: string]: any } = {};

            if (config.tool?.poetry?.dependencies) {
                dependencies.main = config.tool.poetry.dependencies;
            }

            if (config.tool?.poetry?.group) {
                Object.entries(config.tool.poetry.group).forEach(([groupName, groupData]: [string, any]) => {
                    if (groupData.dependencies) {
                        // eslint-disable-next-line security/detect-object-injection
                        dependencies[groupName] = groupData.dependencies;
                    }
                });
            }

            return dependencies;

        } catch (error) {
            throw new Error(`Failed to read dependencies: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }

    async installDependencies(projectPath: string): Promise<void> {
        const runInstall = () => systemService.executeCommand(this.poetryExecutable, ['install'], { cwd: projectPath });
        const runSoftRepair = () => systemService.executeCommand(this.poetryExecutable, ['lock', '--no-update'], { cwd: projectPath });
        const runFullUpdate = () => systemService.executeCommand(this.poetryExecutable, ['lock'], { cwd: projectPath });

        try {
            // We first try Standard Install
            await runInstall();
        } catch (error) {
            // If standard install fails, it's likely a lock file consistency issue.
            // We then try Auto-Repair (Soft Fix) which will update lock metadata without changing versions
            try {
                await runSoftRepair();
                await runInstall();
            } catch (softRepairError) {
                // If soft repair fails, it's likely a lock file consistency issue.
                // We cannot safely automate this as it requires a full lock update which changes versions.
                // We must ask the user for permission.
                const selection = await vscode.window.showErrorMessage(
                    "Automatic repair failed. The lock file has conflicts that require a full update (versions may change). Proceed?",
                    "Yes, Update Lock File",
                    "No, Cancel"
                );

                if (selection === "Yes, Update Lock File") {
                    try {
                        await runFullUpdate();
                        await runInstall();
                    } catch (fullUpdateError) {
                        throw new Error(`Full update failed: ${fullUpdateError instanceof Error ? fullUpdateError.message : String(fullUpdateError)}`);
                    }
                } else {
                    throw new Error("Dependency sync cancelled. Manual intervention required.");
                }
            }
        }
    }

    async addDependency(projectPath: string, name: string, version: string, group?: string): Promise<void> {
        try {
            if (version && !isValidVersionConstraint(version)) {
                throw new Error(`Invalid version constraint format: ${version}`);
            }

            const packageSpec = version ? `${name}@${version}` : name;
            const args = ['add', packageSpec];
            if (group && group !== 'main') {
                args.push('--group', group);
            }
            await systemService.executeCommand(this.poetryExecutable, args, { cwd: projectPath });
        } catch (error) {
            throw new Error(`Failed to add dependency: ${error instanceof Error ? error.message : String(error)}`);
        }
    }

    async removeDependency(projectPath: string, name: string, group?: string): Promise<void> {
        try {
            const args = ['remove', name];
            if (group && group !== 'main') {
                args.push('--group', group);
            }
            await systemService.executeCommand(this.poetryExecutable, args, { cwd: projectPath });
        } catch (error) {
            throw new Error(`Failed to remove dependency: ${error}`);
        }
    }

    async updateDependency(projectPath: string, name: string): Promise<void> {
        try {
            const pyprojectPath = path.join(projectPath, 'pyproject.toml');
            // eslint-disable-next-line security/detect-non-literal-fs-filename
            if (!fs.existsSync(pyprojectPath)) {
                throw new Error('pyproject.toml not found');
            }

            const args = ['update', name];
            await systemService.executeCommand(this.poetryExecutable, args, { cwd: projectPath });
        } catch (error) {
            throw new Error(`Failed to update dependency: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
}

export const dependencyService = new DependencyService();