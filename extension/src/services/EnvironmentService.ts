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
import * as vscode from 'vscode';
import { EnvironmentVariableState } from '../types/solution';
import { ENVIRONMENT_VARIABLE_DEFINITIONS } from './environmentVariables';

/**
 * Service for managing environment variables per solution.
 * Each solution has its own isolated environment configuration stored in workspace state.
 * Solutions are identified by their root directory path (stable), not name (can change).
 */
export class EnvironmentService {
    private variables: EnvironmentVariableState[] = [];
    private currentSolutionPath?: string;

    constructor(private readonly context?: vscode.ExtensionContext) {
        this.initializeFromDefinitions();
    }

    /**
     * Get storage key for a specific solution using its path.
     * Path is normalized to ensure consistent keys across platforms.
     */
    private static getStorageKey(solutionPath: string): string {
        const normalized = path.normalize(solutionPath).toLowerCase().replace(/\\/g, '/');
        return `environment.variables.${normalized}`;
    }

    /**
     * Initialize variables from definitions with default values.
     */
    private initializeFromDefinitions(): void {
        this.variables = ENVIRONMENT_VARIABLE_DEFINITIONS.map(def => ({
            ...def,
            enabled: false,
            value: def.defaultValue,
        }));
    }

    /**
     * Load environment variables for a specific solution by its path.
     */
    public async loadForSolution(solutionPath: string): Promise<void> {
        if (!this.context) {
            console.warn('EnvironmentService: No context available, using defaults');
            return;
        }

        if (!solutionPath) {
            throw new Error('Solution path is required');
        }

        this.currentSolutionPath = solutionPath;
        this.initializeFromDefinitions();

        const storageKey = EnvironmentService.getStorageKey(solutionPath);
        const stored = this.context.workspaceState.get<EnvironmentVariableState[]>(storageKey);

        if (stored && stored.length > 0) {
            this.variables = this.mergeWithDefinitions(stored);
        }
    }

    /**
     * Save environment variables for a specific solution by its path.
     */
    public async saveForSolution(solutionPath: string): Promise<void> {
        if (!this.context) {
            throw new Error('Cannot save: No extension context available');
        }

        if (!solutionPath) {
            throw new Error('Solution path is required');
        }

        this.validateVariables();

        const storageKey = EnvironmentService.getStorageKey(solutionPath);
        await this.context.workspaceState.update(storageKey, this.variables);

        this.currentSolutionPath = solutionPath;
    }

    /**
     * Get environment variables as a plain object for terminal injection.
     * Loads variables for the specified solution if not already loaded.
     */
    public async getAsEnvironmentObject(solutionPath: string): Promise<Record<string, string>> {
        if (!solutionPath) {
            return {};
        }

        if (this.currentSolutionPath !== solutionPath) {
            await this.loadForSolution(solutionPath);
        }

        const env: Record<string, string> = {};

        for (const variable of this.variables) {
            if (variable.enabled && variable.value !== null) {
                env[variable.name] = this.formatValue(variable.value);
            }
        }

        return env;
    }

    /**
     * Merge stored variables with current definitions.
     */
    private mergeWithDefinitions(stored: EnvironmentVariableState[]): EnvironmentVariableState[] {
        const storedMap = new Map(stored.map(v => [v.name, v]));

        return ENVIRONMENT_VARIABLE_DEFINITIONS.map(def => {
            const storedVar = storedMap.get(def.name);
            if (storedVar) {
                return {
                    ...def,
                    enabled: storedVar.enabled,
                    value: storedVar.value,
                };
            }
            return {
                ...def,
                enabled: false,
                value: def.defaultValue,
            };
        });
    }

    public getVariables(): EnvironmentVariableState[] {
        return this.variables;
    }

    public setVariables(variables: EnvironmentVariableState[]): void {
        this.validateVariableArray(variables);
        this.variables = variables;
    }

    private validateVariables(): void {
        this.validateVariableArray(this.variables);
    }

    private validateVariableArray(variables: EnvironmentVariableState[]): void {
        const definitionMap = new Map(
            ENVIRONMENT_VARIABLE_DEFINITIONS.map(def => [def.name, def])
        );

        for (const variable of variables) {
            if (!variable.name || typeof variable.name !== 'string') {
                throw new Error('Invalid variable: missing or invalid name');
            }

            const definition = definitionMap.get(variable.name);
            if (!definition) {
                throw new Error(`Unknown variable: ${variable.name}`);
            }

            if (variable.enabled && variable.value !== null) {
                if (typeof definition.defaultValue === 'boolean' && typeof variable.value !== 'boolean') {
                    throw new Error(`Variable ${variable.name} must be a boolean`);
                }

                if (definition.options && typeof variable.value === 'string') {
                    if (!definition.options.includes(variable.value)) {
                        throw new Error(`Variable ${variable.name} has invalid value`);
                    }
                }
            }
        }
    }

    public getVariableValue(name: string): string | boolean | null | undefined {
        const variable = this.variables.find(v => v.name === name);
        if (!variable) {
            return undefined;
        }
        return variable.enabled ? variable.value : variable.defaultValue;
    }

    private formatValue(value: string | boolean | null): string {
        if (value === null) {return '';}
        if (typeof value === 'boolean') {return value ? 'true' : 'false';}
        return String(value);
    }
}
