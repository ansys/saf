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
import { handleSelectAnotherSolution, loadSolutions } from './common/providerTools';
import { solutionService } from '../services/SolutionService';
import { SAFSolutionsProvider } from './SAFSolutionsProvider';
import { StorageService } from '../services/StorageService';

interface AddStepMessage {
  command: 'add-step' | 'load-solutions' | 'load-templates' | 'select-another-solution' | 'show-error' | 'webview-ready';
  solutionName?: string;
  stepName?: string;
  uiFramework?: string;
  template?: string;
  message?: string;
  previousSelection?: string;
}

export class AddStepViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'solutions-manager.addStep';
  private readonly workspaceRoot: string | undefined;

  private static readonly SOLUTION_CREATION_TIMEOUT_MS = 10000;
  private static readonly FILE_CHECK_INTERVAL_MS = 200;

  constructor(private readonly _extensionUri: vscode.Uri) {
    this.workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  }

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken,
  ): void {
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri]
    };

    webviewView.webview.html = this.getHtmlForWebview(webviewView.webview);

    setTimeout(() => {
      loadSolutions(webviewView, this.workspaceRoot);
    }, 100);

    webviewView.webview.onDidReceiveMessage(async (message: AddStepMessage) => {
      try {
        switch (message.command) {
          case 'webview-ready':
            this.setSelectedSolutionFromStorage(webviewView);
            break;
          case 'add-step':
            if (!message.solutionName || !message.stepName || !message.uiFramework || !message.template) {
              vscode.window.showErrorMessage('Please fill out all fields before adding a step.');
              return;
            }
            await this.addStep(message.solutionName, message.stepName, message.uiFramework, message.template);
            break;
          case 'load-solutions':
            await loadSolutions(webviewView, this.workspaceRoot);
            break;
          case 'load-templates':
            await this.loadTemplates(webviewView);
            break;
          case 'show-error':
            if (message.message) {
              vscode.window.showErrorMessage(message.message);
            }
            break;
          case 'select-another-solution':
            await handleSelectAnotherSolution(webviewView, this.workspaceRoot, message.previousSelection);
            break;
        }
      } catch (error) {
        console.error('Error handling webview message:', error);
        vscode.window.showErrorMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }
    });

    webviewView.onDidChangeVisibility(() => {
      if (webviewView.visible) {
        this.setSelectedSolutionFromStorage(webviewView);
        loadSolutions(webviewView, this.workspaceRoot);
      }
    });
  }

  private setSelectedSolutionFromStorage(webviewView: vscode.WebviewView): void {
    const selectedSolution = StorageService.getSelectedSolution(this.workspaceRoot);

    if (selectedSolution) {
      webviewView.webview.postMessage({
        type: 'set-selected-solution',
        selectedSolution: selectedSolution.name,
        displayName: selectedSolution.displayName
      });
    }
  }

  private async addStep(solutionName: string, stepName: string, uiFramework: string, template: string): Promise<void> {
    try {
      const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();
      const solution = solutions.find(s => s.name === solutionName);
      if (!solution) {
        throw new Error(`Solution ${solutionName} not found`);
      }

      await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: 'Creating new step',
        cancellable: false
      }, async (progress) => {
        progress.report({
          message: `Adding step ${stepName} with ${uiFramework} framework`
        });

        await solutionService.addStep({
          solutionPath: solution.rootDirectory,
          name: stepName,
          displayName: '',
          createPage: true,
          uiFramework,
          template
        });

        const expectedFiles = await solutionService.getStepFiles(
          solution.rootDirectory,
          stepName,
          uiFramework !== 'none'
        );

        await this.waitForStepCreation(expectedFiles);

        if (this.isSolutionOpenInWorkspace(solution.rootDirectory)) {
          await this.openStepFiles(expectedFiles);
        }
      });

      vscode.window.showInformationMessage(
        `Step ${stepName} created successfully with ${uiFramework} framework (template: ${template})`
      );
    } catch (error) {
      vscode.window.showErrorMessage(
        `Failed to create step: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  }

  private async loadTemplates(webviewView: vscode.WebviewView): Promise<void> {
    try {
      const templates = await solutionService.getStepTemplates();
      webviewView.webview.postMessage({
        type: 'templates-loaded',
        templates
      });
    } catch (error) {
      console.error('Failed to load step templates:', error);
      webviewView.webview.postMessage({
        type: 'templates-loaded',
        templates: ['calculator-step']
      });
    }
  }

  private async waitForStepCreation(expectedFiles: string[]): Promise<void> {
    const maxWaitTime = AddStepViewProvider.SOLUTION_CREATION_TIMEOUT_MS;
    const checkInterval = AddStepViewProvider.FILE_CHECK_INTERVAL_MS;

    for (let elapsed = 0; elapsed < maxWaitTime; elapsed += checkInterval) {
      try {
        // Check that all expected files exist
        for (const filePath of expectedFiles) {
          await vscode.workspace.fs.stat(vscode.Uri.file(filePath));
        }

        return;
      } catch {
        // Files don't exist yet, wait and check again
        await new Promise(resolve => setTimeout(resolve, checkInterval));
      }
    }

    throw new Error('Step creation timed out after waiting for files to be created');
  }

  private isSolutionOpenInWorkspace(solutionPath: string): boolean {
    const folders = vscode.workspace.workspaceFolders;
    if (!folders || folders.length === 0) {
      return false;
    }

    const normalizedSolutionPath = vscode.Uri.file(solutionPath).fsPath.toLowerCase();
    return folders.some(folder => folder.uri.fsPath.toLowerCase() === normalizedSolutionPath);
  }

  private async openStepFiles(files: string[]): Promise<void> {
    for (const [index, file] of files.entries()) {
      // eslint-disable-next-line security/detect-non-literal-fs-filename
      if (fs.existsSync(file)) {
        const document = await vscode.workspace.openTextDocument(file);
        await vscode.window.showTextDocument(
          document,
          index === 0 ? vscode.ViewColumn.Active : vscode.ViewColumn.Beside
        );
      }
    }
  }

  public getHtmlForWebview(webview: vscode.Webview): string {
    const styleUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this._extensionUri, 'out', 'webview', 'styles', 'common.css')
    );

    return `<!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline' ${webview.cspSource}; script-src 'unsafe-inline';">
      <title>Add Step</title>
      <link rel="stylesheet" href="${styleUri}">
    </head>
    <body>
      <div class="container">
        <h3>Add step</h3>

        <div class="row">
            <label for="solution-select">Solution</label>
            <div class="solution-selector-row">
              <select id="solution-select">
                <option value="" disabled selected>Select a solution...</option>
              </select>
              <button id="browse-solution-btn" title="Browse for solution directory">🗁</button>
            </div>
            <div id="solution-error" class="validation-error" style="display: none;"></div>
          </div>

          <div class="row">
            <label for="step-name">Step name</label>
            <input type="text" id="step-name" placeholder="my_step" />
            <div class="help-text">Letters, numbers and underscores only</div>
            <div id="step-name-error" class="validation-error" style="display: none;"></div>
          </div>

          <div class="row">
            <label for="ui-framework">UI framework</label>
            <select id="ui-framework">
              <option value="" disabled selected>Select framework...</option>
              <option value="dash">dash</option>
              <option value="none">none</option>
            </select>
            <div id="ui-framework-error" class="validation-error" style="display: none;"></div>
          </div>
          <div class="row">
            <label for="step-template">Step template</label>
            <select id="step-template">
              <option value="" disabled selected>Loading templates...</option>
            </select>
            <div id="step-template-error" class="validation-error" style="display: none;"></div>
          </div>
          <hr>
          <div class="row">
            <h3>Add step command</h3>
            <div class="command-row">
              <div class="command-preview">
                <code id="command-preview">saf add-step</code>
              </div>
              <button id="copy-command-btn" title="Copy command">⧉</button>
            </div>
          </div>

          <button id="add-btn" class="action-button">Add step</button>
        </div>

      <script>
        const vscode = acquireVsCodeApi();

        // State management
        const state = vscode.getState() || {
          solutionName: '',
          stepName: '',
          uiFramework: '',
          template: ''
        };

        // DOM Elements
        const solutionSelect = document.getElementById('solution-select');
        const browseSolutionBtn = document.getElementById('browse-solution-btn');
        const stepNameInput = document.getElementById('step-name');
        const uiFrameworkSelect = document.getElementById('ui-framework');
        const addBtn = document.getElementById('add-btn');
        const stepTemplateSelect = document.getElementById('step-template');
        const solutionError = document.getElementById('solution-error');
        const stepNameError = document.getElementById('step-name-error');
        const uiFrameworkError = document.getElementById('ui-framework-error');
        const stepTemplateError = document.getElementById('step-template-error');
        const commandPreview = document.getElementById('command-preview');
        const copyCommandBtn = document.getElementById('copy-command-btn');

        browseSolutionBtn.addEventListener('click', function() {
          const previousSelection = state.solutionName || '';
          vscode.postMessage({
            command: 'select-another-solution',
            previousSelection: previousSelection
          });
        });

        copyCommandBtn.addEventListener('click', function() {
          const command = commandPreview.textContent;
          navigator.clipboard.writeText(command).then(() => {
            copyCommandBtn.textContent = '✔';
            setTimeout(() => {
              copyCommandBtn.textContent = '⧉';
            }, 1200);
          });
        });

        function checkCommandOverflow() {
          const preview = document.querySelector('.command-preview');
          const code = document.getElementById('command-preview');
          if (code.scrollWidth > preview.clientWidth) {
            code.classList.add('overflow');
          } else {
            code.classList.remove('overflow');
          }
        }

        // Convert a template identifier (e.g. "calculator-step") into a
        // human-readable display name (e.g. "Calculator step")
        function formatTemplateLabel(value) {
          const words = value
            .split(/[-_]+/)
            .filter(Boolean)
            .map(function(word) {
              return word.toLowerCase();
            });
          const label = words.join(' ');
          return label.charAt(0).toUpperCase() + label.slice(1);
        }

        function restoreState() {
          // Don't restore solutionSelect here - it will be restored when solutions are loaded
          stepNameInput.value = state.stepName || '';
          uiFrameworkSelect.value = state.uiFramework || '';
          stepTemplateSelect.value = state.template || '';
        }

        // Load solutions on initialization
        function loadSolutions() {
          vscode.postMessage({ command: 'load-solutions' });
        }

        // Load templates on initialization
        function loadTemplates() {
          vscode.postMessage({ command: 'load-templates' });
        }

        // Update command preview
        function updateCommandPreview() {
          const solution = solutionSelect.value;
          const stepName = stepNameInput.value.trim();
          const uiFramework = uiFrameworkSelect.value;
          const template = stepTemplateSelect.value;

          let command = 'saf add-step';
          if (solution) command += ' ' + solution;
          if (stepName) command += ' --step-name ' + stepName;
          if (uiFramework) command += ' --ui-framework ' + uiFramework;
          if (template) command += ' --template ' + template;

          commandPreview.textContent = command;
          checkCommandOverflow();
        }

        // Validate solution
        function validateSolution() {
          if (solutionSelect.value === '') {
            solutionError.textContent = 'Solution is required';
            solutionError.style.display = 'block';
            return false;
          }
          solutionError.style.display = 'none';
          return true;
        }

        // Validate step name
        function validateStepName() {
          const name = stepNameInput.value.trim();
          if (!name) {
            stepNameError.textContent = 'Step name is required';
            stepNameError.style.display = 'block';
            return false;
          }
          if (!/^[a-zA-Z0-9_]+$/.test(name)) {
            stepNameError.textContent = 'Step name can only contain letters, numbers and underscores';
            stepNameError.style.display = 'block';
            return false;
          }
          stepNameError.style.display = 'none';
          return true;
        }

        // Validate UI framework
        function validateUIFramework() {
          if (uiFrameworkSelect.value === '') {
            uiFrameworkError.textContent = 'UI framework is required';
            uiFrameworkError.style.display = 'block';
            return false;
          }
          uiFrameworkError.style.display = 'none';
          return true;
        }

        // Validate step template
        function validateTemplate() {
          if (stepTemplateSelect.value === '') {
            stepTemplateError.textContent = 'Step template is required';
            stepTemplateError.style.display = 'block';
            return false;
          }
          stepTemplateError.style.display = 'none';
          return true;
        }

        // Event listeners
        solutionSelect.addEventListener('change', function() {
          validateSolution();
          updateCommandPreview();
          saveState();
        });

        stepNameInput.addEventListener('input', function() {
          validateStepName();
          updateCommandPreview();
          saveState();
        });

        uiFrameworkSelect.addEventListener('change', function() {
          validateUIFramework();
          updateCommandPreview();
          saveState();
        });

        stepTemplateSelect.addEventListener('change', function() {
          validateTemplate();
          updateCommandPreview();
          saveState();
        });

        addBtn.addEventListener('click', function() {
          const isSolutionValid = validateSolution();
          const isStepNameValid = validateStepName();
          const isUIFrameworkValid = validateUIFramework();
          const isTemplateValid = validateTemplate();

          if (!isSolutionValid || !isStepNameValid || !isUIFrameworkValid || !isTemplateValid) {
            return;
          }

          vscode.postMessage({
            command: 'add-step',
            solutionName: solutionSelect.value,
            stepName: stepNameInput.value.trim(),
            uiFramework: uiFrameworkSelect.value,
            template: stepTemplateSelect.value
          });
        });

        // Handle messages from extension
        window.addEventListener('message', (event) => {
          const message = event.data;

          if (message.type === 'set-selected-solution') {
            if (message.selectedSolution) {
              const optionExists = Array.from(solutionSelect.options).some(
                option => option.value === message.selectedSolution
              );

              if (optionExists) {
                solutionSelect.value = message.selectedSolution;
              } else {
                const tempOption = document.createElement('option');
                tempOption.value = message.selectedSolution;
                tempOption.textContent = message.selectedSolution + (message.displayName ? ' (' + message.displayName + ')' : '');
                tempOption.setAttribute('data-temp', 'true');
                solutionSelect.add(tempOption);
                solutionSelect.value = message.selectedSolution;
              }

              state.solutionName = message.selectedSolution;
              saveState();
              vscode.postMessage({ command: 'solution-changed', solution: message.selectedSolution });
              updateCommandPreview();
            }
          }
          else if (message.type === 'solutions-loaded') {
            const tempOption = Array.from(solutionSelect.options).find(
              opt => opt.getAttribute('data-temp') === 'true'
            );
            if (tempOption) {
              tempOption.remove();
            }

            solutionSelect.innerHTML = '<option value="" disabled selected>Select a solution...</option>';
            if (message.solutions && message.solutions.length > 0) {
              message.solutions.forEach(solution => {
                const option = document.createElement('option');
                option.value = solution.name;
                option.textContent = solution.name + (solution.displayName ? ' (' + solution.displayName + ')' : '');
                solutionSelect.appendChild(option);
              });

              if (message.selectedSolution) {
                solutionSelect.value = message.selectedSolution;
                state.solutionName = message.selectedSolution;
                saveState();
                vscode.postMessage({ command: 'solution-changed', solution: message.selectedSolution });
              }
              updateCommandPreview();
            }
          }
          else if (message.type === 'revert-solution') {
            solutionSelect.value = message.previousSelection || '';
            state.solutionName = message.previousSelection || '';
            saveState();
            updateCommandPreview();
          }
          else if (message.type === 'templates-loaded') {
            stepTemplateSelect.innerHTML = '<option value="" disabled selected>Select template...</option>';
            if (message.templates && message.templates.length > 0) {
              message.templates.forEach(function(tpl) {
                const option = document.createElement('option');
                option.value = tpl;
                option.textContent = formatTemplateLabel(tpl);
                stepTemplateSelect.appendChild(option);
              });
              // Restore previously saved template selection
              if (state.template && stepTemplateSelect.querySelector('option[value="' + state.template + '"]')) {
                stepTemplateSelect.value = state.template;
              } else if (message.templates.length > 0) {
                // Default to first available template
                stepTemplateSelect.value = message.templates[0];
                state.template = message.templates[0];
                saveState();
              }
              updateCommandPreview();
            }
          }
        });

        // Save state
        function saveState() {
          state.solutionName = solutionSelect.value;
          state.stepName = stepNameInput.value;
          state.uiFramework = uiFrameworkSelect.value;
          state.template = stepTemplateSelect.value;
          vscode.setState(state);
        }

        // Initialize
        loadSolutions();
        loadTemplates();
        restoreState();
        updateCommandPreview();

        vscode.postMessage({ command: 'webview-ready' });
      </script>
    </body>
    </html>`;
  }
}
