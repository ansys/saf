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
import { handleSelectAnotherSolution, handleWorkspacePrompt, loadSolutions, WorkspacePromptOptions } from './common/providerTools';
import { executeCommandInTerminal } from '../utils/terminalUtils';

export class SolutionSetupProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'solutions-manager.solutionSetup';
  private terminalInstance: vscode.Terminal | undefined;
  private readonly workspaceRoot: string | undefined;

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
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri]
    };

    webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

    this.setSelectedSolutionFromStorage(webviewView);

    setTimeout(() => {
      loadSolutions(webviewView, this.workspaceRoot);
    }, 100);

    webviewView.webview.onDidReceiveMessage(async message => {
      try {
        switch (message.command) {
          case 'setup-solution':
            await this.setupSolution(message.solutionName, message.options);
            break;
          case 'setup-solution-workspace-prompt':
            await handleWorkspacePrompt(message.options, (name, opts) => this.setupSolution(name, opts));
            break;
          case 'select-another-solution':
            await handleSelectAnotherSolution(webviewView, this.workspaceRoot, message.previousSelection);
            break;
          case 'load-solutions':
            await loadSolutions(webviewView, this.workspaceRoot);
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

  private async setupSolution(solutionName: string, options: WorkspacePromptOptions): Promise<void> {
    try {
      // Get the solution path
      const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();
      const solution = solutions.find(s => s.name === solutionName);
      if (!solution) {
          throw new Error(`Solution ${solutionName} not found`);
      }

      // Check if a terminal with this name already exists
      const terminalName = `SAF Install - ${solutionName}`;
      const existingTerminal = vscode.window.terminals.find(t => t.name === terminalName);
      if (existingTerminal) {
        existingTerminal.dispose();
      }
      this.terminalInstance = vscode.window.createTerminal(terminalName);
      this.terminalInstance.show();

      // Build the command with options
      const safCliExecutable = StorageService.getSafCliTerminalCommand();
      let setupCommand = safCliExecutable + ` install ${solutionName} -d all`;

      // basic options
      if (options.cleanVenvLock) {
          setupCommand += ' -F';
      } else if (options.cleanVenv) {
          setupCommand += ' -f';
      }
      vscode.window.showInformationMessage(`Installing ${solutionName} environment.`);

      await executeCommandInTerminal(this.terminalInstance, setupCommand);

      vscode.window.showInformationMessage(`${solutionName} environment setup completed.`);
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to install the solution's environment: ${error instanceof Error ? error.message : 'Unknown error'}`);
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
      <title>Setup Solution</title>
      <link rel="stylesheet" href="${styleUri}">
    </head>
    <body>
      <div class="container">
        <h3>Solution setup options</h3>

        <div class="row">
          <label for="solution-select">Solution</label>
          <div class="solution-selector-row">
            <select id="solution-select">
              <option value="" disabled selected>Select a solution...</option>
            </select>
            <button id="browse-solution-btn" title="Browse for solution directory">🗁</button>
          </div>
        </div>

        <label>Environment clean-up options</label>

        <div class="checkbox-row">
          <input type="radio" id="no-clean" name="clean-option" value="none" checked />
          <label for="no-clean">No clean-up</label>
        </div>

        <div class="checkbox-row">
          <input type="radio" id="clean-venv" name="clean-option" value="venv" />
          <label for="clean-venv">Clean-up solution's environment</label>
        </div>

        <div class="checkbox-row">
          <input type="radio" id="clean-venv-lock" name="clean-option" value="venv-lock" />
          <label for="clean-venv-lock">Clean-up solution's environment and poetry lock</label>
        </div>

        <hr>
        <div class="row">
          <h3>Solution setup command</h3>
          <div class="command-row">
            <div class="command-preview">
              <code id="command-preview">saf install</code>
            </div>
            <button id="copy-command-btn" title="Copy command">⧉</button>
          </div>
        </div>

        <button id="setup-btn" class="action-button">Setup solution environment</button>

      </div>

      <script>
        const vscode = acquireVsCodeApi();

        // State management
        const state = vscode.getState() || {
          selectedSolution: '',
          cleanOption: 'none'
        };

        // DOM Elements
        const solutionSelect = document.getElementById('solution-select');
        const browseSolutionBtn = document.getElementById('browse-solution-btn');
        const noCleanRadio = document.getElementById('no-clean');
        const cleanVenvRadio = document.getElementById('clean-venv');
        const cleanVenvLockRadio = document.getElementById('clean-venv-lock');
        const setupBtn = document.getElementById('setup-btn');
        const commandPreview = document.getElementById('command-preview');
        const copyCommandBtn = document.getElementById('copy-command-btn');

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

        // Restore state from previous session
        function restoreState() {
          if (state) {
            solutionSelect.value = state.selectedSolution || '';
            const cleanOption = state.cleanOption || 'none';
            if (cleanOption === 'none') {
              noCleanRadio.checked = true;
            } else if (cleanOption === 'venv') {
              cleanVenvRadio.checked = true;
            } else if (cleanOption === 'venv-lock') {
              cleanVenvLockRadio.checked = true;
            }
            updateCommandPreview();
          }
        }

        // Save current state
        function saveState() {
          state.selectedSolution = solutionSelect.value;
          if (noCleanRadio.checked) {
            state.cleanOption = 'none';
          } else if (cleanVenvRadio.checked) {
            state.cleanOption = 'venv';
          } else if (cleanVenvLockRadio.checked) {
            state.cleanOption = 'venv-lock';
          }
          vscode.setState(state);
        }

        // Update the command preview
        function updateCommandPreview() {
          const solution = solutionSelect.value;
          let command = 'saf install';

          if (solution) {
            command += ' ' + solution;
          }

          // Install all dependencies by default
          command += ' -d all';

          // Clean-up options
          if (cleanVenvRadio.checked) {
            command += ' -f';
          } else if (cleanVenvLockRadio.checked) {
            command += ' -F';
          }

          commandPreview.textContent = command;
          checkCommandOverflow();
        }

        // Event Listeners
        browseSolutionBtn.addEventListener('click', function() {
          const previousSelection = state.selectedSolution || '';
          vscode.postMessage({
            command: 'select-another-solution',
            previousSelection: previousSelection
          });
        });

        solutionSelect.addEventListener('change', function() {
          saveState();
          updateCommandPreview();
        });

        noCleanRadio.addEventListener('change', function() {
          saveState();
          updateCommandPreview();
        });

        cleanVenvRadio.addEventListener('change', function() {
          saveState();
          updateCommandPreview();
        });

        cleanVenvLockRadio.addEventListener('change', function() {
          saveState();
          updateCommandPreview();
        });

        setupBtn.addEventListener('click', function() {
          const solutionName = solutionSelect.value;
          const options = {
            cleanVenv: cleanVenvRadio.checked,
            cleanVenvLock: cleanVenvLockRadio.checked
          };

          if (!solutionName) {
            // No solution selected, ask about using workspace solution
            vscode.postMessage({
              command: 'setup-solution-workspace-prompt',
              options: options
            });
            return;
          }

          vscode.postMessage({
            command: 'setup-solution',
            solutionName: solutionName,
            options: options
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
                tempOption.text = message.selectedSolution + (message.displayName ? ' (' + message.displayName + ')' : '');
                tempOption.setAttribute('data-temp', 'true');
                solutionSelect.add(tempOption);
                solutionSelect.value = message.selectedSolution;
              }

              state.selectedSolution = message.selectedSolution;
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

            while (solutionSelect.options.length > 1) {
              solutionSelect.remove(1);
            }

            message.solutions.forEach(solution => {
              const option = document.createElement('option');
              option.value = solution.name;
              option.text = solution.name + (solution.displayName ? ' (' + solution.displayName + ')' : '');
              solutionSelect.add(option);
            });

            if (message.selectedSolution) {
              solutionSelect.value = message.selectedSolution;
              state.selectedSolution = message.selectedSolution;
              saveState();
              vscode.postMessage({ command: 'solution-changed', solution: message.selectedSolution });
            } else {
              solutionSelect.value = '';
              state.selectedSolution = undefined;
              saveState();
              vscode.postMessage({ command: 'solution-changed', solution: undefined });
            }

            updateCommandPreview();
          }
          else if (message.type === 'revert-solution') {
            solutionSelect.value = message.previousSelection || '';
            updateCommandPreview();
          }
        });

        vscode.postMessage({ command: 'load-solutions' });
        restoreState();
      </script>
    </body>
    </html>`;
  }
}
