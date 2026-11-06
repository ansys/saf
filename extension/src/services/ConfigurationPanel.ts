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
import { EnvironmentService } from './EnvironmentService';
import { EnvironmentVariableState } from '../types/solution';

export class ConfigurationPanel {
    private panel: vscode.WebviewPanel | undefined;
    private currentSolutionName?: string;
    private currentSolutionPath?: string;

    constructor(
        private readonly context: vscode.ExtensionContext,
        private readonly environmentService: EnvironmentService
    ) {}

    public getEnvironmentVariables(): EnvironmentVariableState[] {
        return this.environmentService.getVariables();
    }

    public async show(solutionName: string, solutionPath: string): Promise<void> {
        if (!solutionName || !solutionPath) {
            vscode.window.showWarningMessage('Please select a valid solution to configure its environment.');
            return;
        }

        this.currentSolutionName = solutionName;
        this.currentSolutionPath = solutionPath;

        try {
            await this.environmentService.loadForSolution(solutionPath);
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to load environment variables: ${error instanceof Error ? error.message : 'Unknown error'}`);
            return;
        }

        if (!this.panel) {
            this.panel = vscode.window.createWebviewPanel(
                'safEnvironmentConfig',
                `Configure ${solutionName} environment`,
                vscode.ViewColumn.One,
                { enableScripts: true, retainContextWhenHidden: true }
            );

            this.panel.onDidDispose(() => {
                this.panel = undefined;
            });

            this.panel.webview.onDidReceiveMessage(async message => {
                if (message.command === 'saveVariables') {
                    this.environmentService.setVariables(message.environmentVariables);
                    try {
                        await this.environmentService.saveForSolution(this.currentSolutionPath!);
                        vscode.window.showInformationMessage(
                            `Environment saved for ${this.currentSolutionName}. Changes will apply when you run ${this.currentSolutionName}.`
                        );
                    } catch (error) {
                        vscode.window.showErrorMessage(`Failed to save: ${error instanceof Error ? error.message : 'Unknown error'}`);
                    }
                }
            });
        } else {
            this.panel.title = `Configure ${solutionName} environment`;
        }

        this.panel.webview.html = this.getWebviewContent();
        this.panel.reveal();
    }

    private getWebviewContent(): string {
        const variables = this.environmentService.getVariables();

        // Group variables by category
        const variablesByCategory: { [key: string]: EnvironmentVariableState[] } = {};
        for (const variable of variables) {
            if (!variablesByCategory[variable.category]) {
                variablesByCategory[variable.category] = [];
            }
            variablesByCategory[variable.category].push(variable);
        }

        const categories = Object.keys(variablesByCategory).sort((a, b) => a.localeCompare(b));

        // eslint-disable-next-line security/detect-object-injection
        const categoriesHtml = categories.map(category => this.renderCategory(category, variablesByCategory[category])).join('');

        return `<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>SAF Environment Configuration</title>
            <style>
                body { font-family: var(--vscode-font-family); font-size: var(--vscode-font-size); color: var(--vscode-foreground); background-color: var(--vscode-editor-background); padding: 20px; padding-bottom: 80px; }
                h1 { font-size: 1.5em; margin-bottom: 20px; }
                h2 { font-size: 1.2em; margin-top: 30px; margin-bottom: 15px; border-bottom: 1px solid var(--vscode-panel-border); padding-bottom: 5px; }
                .variable-group { margin-bottom: 20px; }
                .variable-item { margin-bottom: 15px; padding: 10px; border-radius: 4px; background-color: var(--vscode-editor-inactiveSelectionBackground); }
                .variable-header { display: flex; align-items: center; margin-bottom: 5px; }
                .variable-name { font-weight: bold; margin-right: 10px; }
                .variable-description { margin-bottom: 10px; color: var(--vscode-descriptionForeground); }
                .variable-value { display: flex; align-items: center; margin-top: 10px; }
                label { user-select: none; display: flex; align-items: center; margin-right: 15px; }
                input[type="checkbox"] { margin-right: 5px; }
                input[type="text"] { background-color: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); padding: 4px 8px; border-radius: 2px; width: 200px; }
                input[type="text"]:disabled { opacity: 0.5; }
                button { background-color: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; padding: 6px 12px; border-radius: 2px; cursor: pointer; }
                button:hover { background-color: var(--vscode-button-hoverBackground); }
                .default-value { margin-left: 15px; font-style: italic; color: var(--vscode-descriptionForeground); }
                .option-label { margin-right: 10px; }
                select { background-color: var(--vscode-dropdown-background); color: var(--vscode-dropdown-foreground); border: 1px solid var(--vscode-dropdown-border); padding: 4px 8px; min-width: 200px; height: 28px; cursor: pointer; font-family: var(--vscode-font-family); font-size: var(--vscode-font-size); }
                select:focus, select:hover { outline: 1px solid #0e639c; }
                .search-container { margin-bottom: 20px; }
                #searchBox { width: 300px; padding: 6px 10px; margin-right: 10px; }
                .filter-container { margin-bottom: 20px; display: flex; align-items: center; }
                .filter-container label { margin-right: 10px; }
                #categoryFilter { min-width: 200px; }
                .category-heading { display: flex; align-items: center; justify-content: space-between; }
                .category-controls { display: flex; align-items: center; }
                .toggle-all { margin-left: 10px; font-size: 0.9em; text-decoration: underline; cursor: pointer; color: var(--vscode-textLink-foreground); }
                .no-results { padding: 10px; color: var(--vscode-disabledForeground); font-style: italic; display: none; }
                .save-button-container {
                    position: fixed;
                    bottom: 20px;
                    right: 20px;
                    z-index: 1000;
                }
                #saveButton {
                    padding: 10px 20px;
                    font-size: 14px;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
                }
            </style>
        </head>
        <body>
            <h1>SAF Environment Configuration</h1>
            <p>Configure environment variables for your SAF solution.</p>

            <div class="search-container">
                <input type="text" id="searchBox" placeholder="Search variables...">
                <button id="clearSearch">Clear</button>
            </div>

            <div class="filter-container">
                <label for="categoryFilter">Filter by category:</label>
                <select id="categoryFilter">
                    <option value="all">All categories</option>
                    ${categories.map(cat => `<option value="${cat}">${cat}</option>`).join('')}
                </select>
            </div>
            ${categoriesHtml}

            <div class="no-results">No variables found matching your search.</div>

            <div class="save-button-container">
                <button id="saveButton">Save Configuration</button>
            </div>

            <script>
                (function() {
                    const vscode = acquireVsCodeApi();
                    const environmentVariables = ${JSON.stringify(variables)};

                    ${this.getWebviewScript()}
                })();
            </script>
        </body>
        </html>`;
    }

    private renderCategory(category: string, variables: EnvironmentVariableState[]): string {
        return `
            <div class="category-section" data-category="${category}">
                <div class="category-heading">
                    <h2>${category}</h2>
                    <div class="category-controls">
                        <span class="toggle-all" data-action="enable-all" data-category="${category}">Enable all</span>
                        <span class="toggle-all" data-action="disable-all" data-category="${category}">Disable all</span>
                    </div>
                </div>
                <div class="variable-group">
                    ${variables.map(v => this.renderVariable(v)).join('')}
                </div>
            </div>`;
    }

    private renderVariable(variable: EnvironmentVariableState): string {
        return `
            <div class="variable-item" data-name="${variable.name}" data-category="${variable.category}">
                <div class="variable-header">
                    <div class="variable-name">${variable.name}</div>
                    <label>
                        <input type="checkbox" class="variable-enabled" ${variable.enabled ? 'checked' : ''}>
                        <span>Enabled</span>
                    </label>
                </div>
                <div class="variable-description">${variable.description.replace(/\n/g, '<br>')}</div>
                <div class="variable-value">
                    ${this.renderValueInput(variable)}
                    <div class="default-value">Default: ${variable.defaultValue ?? 'None'}</div>
                </div>
            </div>`;
    }

    private renderValueInput(variable: EnvironmentVariableState): string {
        const disabled = !variable.enabled ? 'disabled' : '';

        if (variable.options) {
            const noneOption = variable.value === null ? '<option value="None" selected>None</option>' : '';
            const options = variable.options.map(opt =>
                `<option value="${opt}" ${variable.value === opt ? 'selected' : ''}>${opt}</option>`
            ).join('');
            return `<div class="option-label">Value:</div><select class="variable-value-input" ${disabled}>${noneOption}${options}</select>`;
        }

        if (typeof variable.defaultValue === 'boolean') {
            return `<div class="option-label">Value:</div>
                <select class="variable-value-input" ${disabled}>
                    <option value="true" ${variable.value === true ? 'selected' : ''}>true</option>
                    <option value="false" ${variable.value === false ? 'selected' : ''}>false</option>
                </select>`;
        }

        return `<div class="option-label">Value:</div>
            <input type="text" class="variable-value-input" value="${variable.value ?? ''}" ${disabled}>`;
    }

    private getWebviewScript(): string {
        return `
            const searchBox = document.getElementById('searchBox');
            const categoryFilter = document.getElementById('categoryFilter');
            const noResults = document.querySelector('.no-results');

            document.querySelectorAll('.variable-enabled').forEach(checkbox => {
                checkbox.addEventListener('change', function() {
                    const container = this.closest('.variable-item');
                    const name = container.getAttribute('data-name');
                    const valueInput = container.querySelector('.variable-value-input');
                    const variable = environmentVariables.find(v => v.name === name);
                    if (variable) variable.enabled = this.checked;
                    valueInput.disabled = !this.checked;
                });
            });

            document.querySelectorAll('.variable-value-input').forEach(input => {
                input.addEventListener('change', function() {
                    const container = this.closest('.variable-item');
                    const name = container.getAttribute('data-name');
                    const variable = environmentVariables.find(v => v.name === name);
                    if (variable) {
                        const val = this.value;
                        if (val === 'None') variable.value = null;
                        else if (val === 'true') variable.value = true;
                        else if (val === 'false') variable.value = false;
                        else variable.value = val || null;
                    }
                });
            });

            document.getElementById('saveButton').addEventListener('click', () => {
                vscode.postMessage({ command: 'saveVariables', environmentVariables });
            });

            function filterVariables() {
                const searchTerm = searchBox.value.toLowerCase();
                const categoryValue = categoryFilter.value;
                let visibleCount = 0;

                document.querySelectorAll('.category-section').forEach(c => c.style.display = 'none');
                document.querySelectorAll('.variable-item').forEach(item => {
                    const name = item.getAttribute('data-name').toLowerCase();
                    const category = item.getAttribute('data-category');
                    const desc = item.querySelector('.variable-description').textContent.toLowerCase();
                    const matchesSearch = !searchTerm || name.includes(searchTerm) || desc.includes(searchTerm);
                    const matchesCategory = categoryValue === 'all' || category === categoryValue;

                    if (matchesSearch && matchesCategory) {
                        item.style.display = '';
                        visibleCount++;
                        document.querySelector('.category-section[data-category="' + category + '"]').style.display = '';
                    } else {
                        item.style.display = 'none';
                    }
                });
                noResults.style.display = visibleCount === 0 ? '' : 'none';
            }

            searchBox.addEventListener('input', filterVariables);
            categoryFilter.addEventListener('change', filterVariables);
            document.getElementById('clearSearch').addEventListener('click', () => {
                searchBox.value = '';
                categoryFilter.value = 'all';
                filterVariables();
            });

            document.querySelectorAll('.toggle-all').forEach(btn => {
                btn.addEventListener('click', function() {
                    const enable = this.getAttribute('data-action') === 'enable-all';
                    const category = this.getAttribute('data-category');
                    document.querySelectorAll('.variable-item[data-category="' + category + '"]').forEach(item => {
                        const checkbox = item.querySelector('.variable-enabled');
                        const valueInput = item.querySelector('.variable-value-input');
                        const name = item.getAttribute('data-name');
                        checkbox.checked = enable;
                        valueInput.disabled = !enable;
                        const variable = environmentVariables.find(v => v.name === name);
                        if (variable) variable.enabled = enable;
                    });
                });
            });
        `;
    }
}