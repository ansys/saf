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
import { SAFSolutionsProvider } from './SAFSolutionsProvider';
import { StorageService } from '../services/StorageService';
import { executeCommandInTerminal } from '../utils/terminalUtils';
import { getCurrentWorkspaceSolutionName} from '../utils/workspaceUtils';

export class ExecuteCommandProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'solutions-manager.executeCommand';
  private _view?: vscode.WebviewView;
  private workspaceRoot: string | undefined;
  private terminalInstance: vscode.Terminal | undefined;

  constructor(private readonly _extensionUri: vscode.Uri) {
    this.workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

    vscode.window.onDidCloseTerminal(terminal => {
      if (this.terminalInstance === terminal) {
        this.terminalInstance = undefined;
      }
    });
  }

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken,
  ): void {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri]
    };

    webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

    webviewView.webview.onDidReceiveMessage(async message => {
      try {
        switch (message.command) {
          case 'execute-command':
            await this.executeCommand(message.solutionName, message.commandText);
            break;
          case 'execute-command-workspace-prompt':
            await this.handleWorkspacePrompt(message.commandText);
            break;
          case 'load-solutions':
            await this.loadSolutions();
            break;
          case 'show-error':
            vscode.window.showErrorMessage(message.message);
            break;
        }
      } catch (error) {
        console.error('Error handling webview message:', error);
        vscode.window.showErrorMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }
    });

    // Load solutions when view becomes visible
    webviewView.onDidChangeVisibility(() => {
      if (webviewView.visible) {
        this.loadSolutions();
      }
    });
  }

  private async loadSolutions(): Promise<void> {
    try {
      const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();
      if (this._view) {
        this._view.webview.postMessage({
          type: 'solutions-loaded',
          solutions: solutions.map(s => ({
            name: s.name,
            displayName: s.displayName
          }))
        });
      }
    } catch (error) {
      console.error('Error loading solutions:', error);
    }
  }

  private async executeCommand(solutionName: string, commandText: string): Promise<void> {
    if (!commandText) {
      vscode.window.showErrorMessage('No command specified');
      return;
    }

    try {
      // Dispose any existing terminal with the same name
      if (this.terminalInstance) {
        this.terminalInstance.dispose();
      }

      this.terminalInstance = vscode.window.createTerminal(`SAF Execute - ${solutionName}`);
      this.terminalInstance.show();

      // Execute the command in the solution environment
      const escapedCommand = commandText.replace(/"/g, '\\"');
      const safCliExecutable = StorageService.getSafCliTerminalCommand();
      await executeCommandInTerminal(this.terminalInstance, safCliExecutable + ` execute ${solutionName} "${escapedCommand}"`);

      vscode.window.showInformationMessage(`Executing command in solution: ${solutionName}`);
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to execute command: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  private async handleWorkspacePrompt(commandText: string): Promise<void> {
    try {
      // Check if we have an open workspace
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      let currentWorkspaceSolution: string | undefined;

      if (workspaceFolder) {
        // check if current workspace is a solution
        const solutionPath = workspaceFolder.uri.fsPath;
        currentWorkspaceSolution = getCurrentWorkspaceSolutionName(solutionPath);
      }

      if (currentWorkspaceSolution) {
        // We have a workspace solution, ask if user wants to use it
        const action = await vscode.window.showQuickPick(
          [
            { label: `Yes, use "${currentWorkspaceSolution}"`, value: currentWorkspaceSolution },
            { label: 'No, choose another solution', value: 'choose' }
          ],
          { placeHolder: 'Use current workspace solution?' }
        );

        if (!action) {
          return;
        }

        if (action.value === 'choose') {
          // User wants to choose another solution
          const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();
          if (solutions.length === 0) {
            vscode.window.showErrorMessage('No solutions available');
            return;
          }

          const selectedSolution = await vscode.window.showQuickPick(
            solutions.map(s => ({
              label: s.name,
              description: s.displayName ? s.displayName : undefined
            })),
            { placeHolder: 'Select a solution' }
          );

          if (!selectedSolution) {
            return;
          }

          await this.executeCommand(selectedSolution.label, commandText);
        } else {
          // Use the workspace solution
          await this.executeCommand(currentWorkspaceSolution, commandText);
        }
      } else {
        // No workspace solution, ask user to select one
        const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();
        if (solutions.length === 0) {
          vscode.window.showErrorMessage('No solutions available');
          return;
        }

        const selectedSolution = await vscode.window.showQuickPick(
          solutions.map(s => ({
            label: s.name,
            description: s.displayName ? s.displayName : undefined
          })),
          { placeHolder: 'Select a solution' }
        );

        if (!selectedSolution) {
          return;
        }

        await this.executeCommand(selectedSolution.label, commandText);
      }
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to execute command: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  private _getHtmlForWebview(webview: vscode.Webview): string {
    const styleUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this._extensionUri, 'out', 'webview', 'styles', 'common.css')
    );

    return `<!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline' ${webview.cspSource}; script-src 'unsafe-inline';">
      <title>Execute Command</title>
      <link rel="stylesheet" href="${styleUri}">
      <style>
        h3 {
          margin-top: 5px;
          margin-bottom: 10px;
        }
        .section-title {
          margin-top: 15px;
          margin-bottom: 8px;
          font-weight: bold;
          font-size: 14px;
          color: var(--vscode-editor-foreground);
        }
        textarea {
          min-height: 80px;
          font-family: var(--vscode-editor-font-family);
          font-size: 12px;
          resize: vertical;
        }
      </style>
    </head>
    <body>
      <div class="container">
        <h3>Solution Execute Options</h3>

        <div class="row">
          <label for="solution-select">Solution</label>
          <select id="solution-select">
            <option value="">Select a solution...</option>
          </select>
        </div>

        <div class="row">
          <label for="command-templates">Command Templates</label>
          <select id="command-templates" class="templates-dropdown">
            <option value="">Select a template...</option>
            <option value="poetry install --only doc">Install doc dependencies</option>
            <option value="poetry install --only tests">Install tests dependencies</option>
            <option value="poetry install --only build">Install build dependencies</option>
            <option value="poetry install --only style">Install style dependencies</option>
            <option value="sphinx-build doc/source doc/build/html --color -vW -bhtml">Build documentation</option>
            <option value="poetry lock --no-update">Update poetry.lock file</option>
            <option value="pytest tests">Run pytest tests</option>
            <option value="poetry add <package-name>">Add dependency</option>
            <option value="poetry add <package-name> --source <source-name>">Add dependency from source</option>
            <option value="poetry add --source <source-name> --group <group-name>">Add dependency to group</option>
          </select>
        </div>

        <div class="row">
          <label for="command-input">Command</label>
          <textarea id="command-input" placeholder="Enter command to execute"></textarea>
        </div>

        <hr>

        <div class="row">
          <div class="section-title">Solution Execute Command</div>
          <div class="command-row">
            <div class="command-preview">
              <code id="command-preview">saf execute solution-name "command"</code>
            </div>
            <button id="copy-command-btn" title="Copy command">⧉</button>
          </div>
        </div>

        <button id="execute-btn" class="action-button">Execute Command</button>
      </div>

      <script>
        const vscode = acquireVsCodeApi();

        // State management
        const state = vscode.getState() || {
          selectedSolution: '',
          commandText: ''
        };

        // DOM Elements
        const solutionSelect = document.getElementById('solution-select');
        const commandTemplates = document.getElementById('command-templates');
        const commandInput = document.getElementById('command-input');
        const executeBtn = document.getElementById('execute-btn');
        const commandPreview = document.getElementById('command-preview');
        const copyCommandBtn = document.getElementById('copy-command-btn');

        // Restore state from previous session
        function restoreState() {
          if (state) {
            solutionSelect.value = state.selectedSolution || '';
            commandInput.value = state.commandText || '';
            updateCommandPreview();
          }
        }

        // Save current state
        function saveState() {
          state.selectedSolution = solutionSelect.value;
          state.commandText = commandInput.value;
          vscode.setState(state);
        }

        // Update the command preview
        function updateCommandPreview() {
          const solution = solutionSelect.value;
          const command = commandInput.value || 'command';

          // Escape quotes for display in preview
          const escapedCommand = command.replace(/"/g, '\\"');

          commandPreview.textContent = 'saf execute "' + escapedCommand + '"';
          if (solution) {
            commandPreview.textContent = 'saf execute ' + solution + ' "' + escapedCommand + '"';
          } else {
            // Don't show any solution placeholder when no solution is selected
            commandPreview.textContent = 'saf execute "' + escapedCommand + '"';
          }

          checkCommandOverflow();
        }

        // Check if command preview overflows and adjust styling
        function checkCommandOverflow() {
          const preview = document.querySelector('.command-preview');
          const code = document.getElementById('command-preview');
          if (code.scrollWidth > preview.clientWidth) {
            code.classList.add('overflow');
          } else {
            code.classList.remove('overflow');
          }
        }

        // Event Listeners
        commandTemplates.addEventListener('change', function() {
          if (this.value) {
            commandInput.value = this.value;
            saveState();
            updateCommandPreview();
          }
        });

        solutionSelect.addEventListener('change', function() {
          saveState();
          updateCommandPreview();
        });

        commandInput.addEventListener('input', function() {
          saveState();
          updateCommandPreview();
        });

        copyCommandBtn.addEventListener('click', function() {
          const commandText = commandPreview.textContent;
          navigator.clipboard.writeText(commandText).then(() => {
            copyCommandBtn.textContent = '✔';
            setTimeout(() => {
              copyCommandBtn.textContent = '⧉';
            }, 1200);
          }).catch(err => {
            console.error('Failed to copy command:', err);
          });
        });

        executeBtn.addEventListener('click', function() {
          const solutionName = solutionSelect.value;
          const commandText = commandInput.value.trim();

          if (!commandText) {
            vscode.postMessage({
              command: 'show-error',
              message: 'Please enter a command'
            });
            return;
          }

          if (!solutionName) {
            // No solution selected, ask about using workspace solution
            vscode.postMessage({
              command: 'execute-command-workspace-prompt',
              commandText: commandText
            });
            return;
          }

          executeBtn.disabled = true;
          executeBtn.textContent = 'Executing...';

          vscode.postMessage({
            command: 'execute-command',
            solutionName: solutionName,
            commandText: commandText
          });

          // Re-enable button after delay
          setTimeout(() => {
            executeBtn.disabled = false;
            executeBtn.textContent = 'Execute Command';
          }, 2000);
        });

        // Handle messages from extension
        window.addEventListener('message', (event) => {
          const message = event.data;

          if (message.type === 'solutions-loaded') {
            // Clear current options
            while (solutionSelect.options.length > 1) {
              solutionSelect.remove(1);
            }

            // Add new solutions
            message.solutions.forEach(solution => {
              const option = document.createElement('option');
              option.value = solution.name;
              option.text = solution.name + (solution.displayName ? ' (' + solution.displayName + ')' : '');
              solutionSelect.add(option);
            });

            // Restore selection if possible
            if (state.selectedSolution) {
              // Check if the previously selected solution exists in the new list
              const exists = Array.from(solutionSelect.options).some(
                option => option.value === state.selectedSolution
              );

              if (exists) {
                solutionSelect.value = state.selectedSolution;
              }
            }

            updateCommandPreview();
          }
        });

        // Request solutions on load
        vscode.postMessage({ command: 'load-solutions' });

        // Restore state
        restoreState();
      </script>
    </body>
    </html>`;
  }
}