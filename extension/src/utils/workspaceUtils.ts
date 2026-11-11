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
import { SAFSolutionsProvider } from '../providers/SAFSolutionsProvider';
import { SelectedSolution } from '../services/StorageService';

/**
 * Get the current workspace root directory
 */
export function getWorkspaceRoot(): string | undefined {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

/**
 * Get the current workspace folder
 */
export function getWorkspaceFolder(): vscode.WorkspaceFolder | undefined {
    return vscode.workspace.workspaceFolders?.[0];
}

/**
 * Check if the current workspace is a valid solution
 */
export function isValidSolutionWorkspace(workspacePath?: string): boolean {
    if (!workspacePath) {
        workspacePath = getWorkspaceRoot();
    }

    if (!workspacePath) {
        return false;
    }

    // Check for pyproject.toml (standard solution indicator)
    const pyprojectPath = path.join(workspacePath, 'pyproject.toml');
    // eslint-disable-next-line security/detect-non-literal-fs-filename
    if (!fs.existsSync(pyprojectPath)) {
        return false;
    }

    return findDefinitionPySync(path.join(workspacePath, 'src'));
}

/**
 * Get the solution name from the current workspace
 */
export function getCurrentWorkspaceSolutionName(workspacePath?: string): string | undefined {
    if (!workspacePath) {
        workspacePath = getWorkspaceRoot();
    }

    if (!workspacePath || !isValidSolutionWorkspace(workspacePath)) {
        return undefined;
    }

    return findSolutionNameSync(path.join(workspacePath, 'src'));
}

/**
 * Check if virtual environment exists in workspace
 */
export function hasVirtualEnvironment(workspacePath?: string): boolean {
    if (!workspacePath) {
        workspacePath = getWorkspaceRoot();
    }

    if (!workspacePath) {
        return false;
    }

    const venvPath = path.join(workspacePath, '.venv');
    // eslint-disable-next-line security/detect-non-literal-fs-filename
    return fs.existsSync(venvPath);
}

/**
 * Check if SAF executable exists in virtual environment
 */
export function hasSAFExecutable(workspacePath?: string): boolean {
    if (!workspacePath) {
        workspacePath = getWorkspaceRoot();
    }

    if (!workspacePath) {
        return false;
    }

    const scriptsDir = process.platform === 'win32' ? 'Scripts' : 'bin';
    const safExecutable = process.platform === 'win32' ? 'saf.exe' : 'saf';
    const solutionStarterExecutable = process.platform === 'win32' ? 'solution-app-starter.exe' : 'solution-app-starter';

    const safPath = path.join(workspacePath, '.venv', scriptsDir, safExecutable);
    const solutionStarterPath = path.join(workspacePath, '.venv', scriptsDir, solutionStarterExecutable);

    // eslint-disable-next-line security/detect-non-literal-fs-filename
    return fs.existsSync(safPath) || fs.existsSync(solutionStarterPath);
}

/**
 * Get workspace folder name (used as default solution name)
 */
export function getWorkspaceFolderName(): string | undefined {
    const workspaceFolder = getWorkspaceFolder();
    return workspaceFolder?.name;
}

/**
 * Validate if a workspace can be used for solution development
 */
export function validateWorkspaceForDevelopment(workspacePath?: string): {
    isValid: boolean;
    hasVenv: boolean;
    hasSAF: boolean;
    isSolution: boolean;
    solutionName?: string;
} {
    if (!workspacePath) {
        workspacePath = getWorkspaceRoot();
    }

    const hasVenv = hasVirtualEnvironment(workspacePath);
    const hasSAF = hasSAFExecutable(workspacePath);
    const isSolution = isValidSolutionWorkspace(workspacePath);
    const solutionName = getCurrentWorkspaceSolutionName(workspacePath);

    return {
        isValid: hasVenv && hasSAF && isSolution,
        hasVenv,
        hasSAF,
        isSolution,
        solutionName
    };
}

/**
 * Get workspace solution information including name and path
 * Checks if the workspace contains a registered solution by matching against SAF CLI's solution list
 */
export async function getWorkspaceSolutionInfo(workspacePath?: string): Promise<SelectedSolution | undefined> {
    if (!workspacePath) {
        workspacePath = getWorkspaceRoot();
    }

    if (!workspacePath) {
        return undefined;
    }

    try {
        const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();

        for (const solution of solutions) {
            if (solution.rootDirectory) {
                const normalizedWorkspaceRoot = path.normalize(workspacePath).toLowerCase();
                const normalizedSolutionRoot = path.normalize(solution.rootDirectory).toLowerCase();

                if (normalizedWorkspaceRoot === normalizedSolutionRoot ||
                    normalizedWorkspaceRoot.startsWith(normalizedSolutionRoot + path.sep)) {
                    return {
                        name: solution.name,
                        displayName: solution.displayName,
                        path: solution.rootDirectory
                    };
                }
            }
        }

        const solutionName = findSolutionNameSync(path.join(workspacePath, 'src'));

        if (solutionName) {
            const matchingSolution = solutions.find(s =>
                s.name.toLowerCase().replace(/[-_]/g, '') === solutionName.toLowerCase().replace(/[-_]/g, '')
            );
            if (matchingSolution?.rootDirectory) {
                return {
                    name: matchingSolution.name,
                    displayName: matchingSolution.displayName,
                    path: matchingSolution.rootDirectory
                };
            }
        }
    } catch (error) {
        console.error('Error getting workspace solution info:', error);
    }

    return undefined;
}

function findDefinitionPySync(srcRoot: string): boolean {
    return findFirstSolutionDirSync(srcRoot) !== undefined;
}

function findSolutionNameSync(srcRoot: string): string | undefined {
    const solutionDir = findFirstSolutionDirSync(srcRoot);
    return solutionDir ? path.basename(solutionDir) : undefined;
}

function findFirstSolutionDirSync(currentDir: string): string | undefined {
    try {
        // A solution package dir contains solution/definition.py
        const definitionPath = path.join(currentDir, 'solution', 'definition.py');
        // eslint-disable-next-line security/detect-non-literal-fs-filename
        if (fs.existsSync(definitionPath)) {
            return currentDir;
        }

        // eslint-disable-next-line security/detect-non-literal-fs-filename
        const entries = fs.readdirSync(currentDir, { withFileTypes: true });

        for (const entry of entries) {
            if (!entry.isDirectory() || entry.name.startsWith('.')) {
                continue;
            }

            const childDir = path.join(currentDir, entry.name);
            const found = findFirstSolutionDirSync(childDir);
            if (found) {
                return found;
            }
        }
    } catch (error) {
        console.error(`Error while searching for solution directory in ${currentDir}:`, error);
    }

    return undefined;
}

export function hasSolutionStructure(workspacePath: string): boolean{
    const srcPath = path.join(workspacePath, 'src');
    // eslint-disable-next-line security/detect-non-literal-fs-filename
     if (!fs.existsSync(srcPath)) {
         return false;
     }
    return findDefinitionPySync(srcPath);
}
