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
import { solutionService } from '../services/SolutionService';
import { systemService } from '../services/SystemService';
import { SAFSolutionsProvider } from './SAFSolutionsProvider';
import { StorageService } from '../services/StorageService';
import { validateNamespace } from '../utils/validation';

interface SolutionCreationConfig {
  name: string;
  displayName: string;
  uiType: string;
  namespace: string;
  targetDirectory: string;
}

export class CreateSolutionViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'solutions-manager.createSolution';
  private _view?: vscode.WebviewView;
  private readonly workspaceRoot: string | undefined;
  private static readonly SOLUTION_CREATION_TIMEOUT_MS = 10000;
  private static readonly FILE_CHECK_INTERVAL_MS = 200;
  // Mirrors the defaults in packages/saf-cli/src/ansys/saf/cli/_config/const.py
  private static readonly DEFAULTS = {
    name: 'my_solution',
    displayName: 'My Solution',
    uiType: 'dash',
    namespace: 'saf.solutions'
  };

  constructor(private readonly _extensionUri: vscode.Uri) {
    this.workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
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
          case 'webview-ready': {
            const lastTargetDirectory = StorageService.getLastTargetDirectory();
            if (lastTargetDirectory && this._view) {
              this._view.webview.postMessage({
                type: 'set-target-directory',
                path: lastTargetDirectory
              });
            }
            break;
          }
          case 'create-solution':
            await this.createSolution(message.config);
            break;
          case 'browse-folder':
            await this.browseFolder();
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
  }

  private async waitForSolutionCreation(expectedDefinitionPath: string): Promise<void> {
    const maxWaitTime = CreateSolutionViewProvider.SOLUTION_CREATION_TIMEOUT_MS;
    const checkInterval = CreateSolutionViewProvider.FILE_CHECK_INTERVAL_MS;

    for (let elapsed = 0; elapsed < maxWaitTime; elapsed += checkInterval) {
      const exists = await this.pathExistsUsingWorkspaceFs(expectedDefinitionPath);

      if (exists) {
        return;
      }
      await new Promise(resolve => setTimeout(resolve, checkInterval));
    }

    throw new Error('Solution creation timed out after waiting for files to be created');
  }

  private async pathExistsUsingWorkspaceFs(filePath: string): Promise<boolean> {
    try {
      await vscode.workspace.fs.stat(vscode.Uri.file(filePath));
      return true;
    } catch {
      return false;
    }
  }

  private async browseFolder(): Promise<void> {
    try {
      // Default to user home directory
      let defaultUri: vscode.Uri | undefined;
      const homeDir = process.env.HOME || process.env.USERPROFILE;
      if (homeDir) {
        defaultUri = vscode.Uri.file(homeDir);
      }

      const folderUris = await vscode.window.showOpenDialog({
        canSelectMany: false,
        canSelectFolders: true,
        canSelectFiles: false,
        openLabel: 'Select new solution directory',
        defaultUri: defaultUri
      });

      if (folderUris?.[0] && this._view) {
        const selectedPath = folderUris[0].fsPath;
        await StorageService.setLastTargetDirectory(selectedPath);
        this._view.webview.postMessage({
          type: 'set-target-directory',
          path: selectedPath
        });
      }
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to browse for directory: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  private async createSolution(config: SolutionCreationConfig): Promise<void> {
    try {
      // Ensure SAF CLI is installed
      await systemService.handleSAFCliInstallation();

      // Validate configuration
      if (!config.name || !config.displayName || !config.namespace || !config.targetDirectory || !config.uiType) {
        vscode.window.showErrorMessage('All fields are required: solution name, display name, namespace, target directory, and UI type.');
        return;
      }

      if (!/^[a-zA-Z0-9_-]+$/.test(config.name)) {
        vscode.window.showErrorMessage('Solution name can only contain letters, numbers, hyphens and underscores.');
        return;
      }

      const namespaceErrorMessage = validateNamespace(config.namespace);
      if (namespaceErrorMessage) {
        vscode.window.showErrorMessage(namespaceErrorMessage);
        return;
      }

      const solutionConfig = {
        name: config.name,
        displayName: config.displayName,
        namespace: config.namespace,
        uiType: config.uiType || 'dash',
        targetDirectory: config.targetDirectory
      };

      // Calculate the solution path
      const folderName = config.name;
      const solutionPath = path.join(config.targetDirectory, folderName);
      const solutionNameDir = config.name.replace(/-/g, '_');
      const namespaceParts = config.namespace.split('.');
      const expectedDefinitionPath = path.join(
        solutionPath,
        'src',
        ...namespaceParts,
        solutionNameDir,
        'solution',
        'definition.py'
      );

      await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Creating Solution",
        cancellable: false
      }, async (progress) => {
        progress.report({ message: 'Creating solution...' });

        await solutionService.createSolution(solutionConfig);

        progress.report({ message: 'Waiting for solution files to be created...' });

        // Wait for definition.py to be created to ensure solution is ready
        await this.waitForSolutionCreation(expectedDefinitionPath);

        // Clear the form
        if (this._view) {
          this._view.webview.postMessage({
            type: 'solution-created'
          });
        }
      });

      SAFSolutionsProvider.getInstance().refresh();

      const openChoice = await vscode.window.showInformationMessage(
        'Solution created successfully! Would you like to open it?',
        'Open in current window',
        'Open in new window',
        'Don\'t open'
      );

      if (openChoice === 'Open in current window') {
        await vscode.commands.executeCommand('vscode.openFolder', vscode.Uri.file(solutionPath));
      } else if (openChoice === 'Open in new window') {
        await vscode.commands.executeCommand('vscode.openFolder', vscode.Uri.file(solutionPath), { forceNewWindow: true });
      }
    } catch (error) {
      // Re-enable the button on error
      if (this._view) {
        this._view.webview.postMessage({
          type: 'solution-creation-failed'
        });
      }
      vscode.window.showErrorMessage(`Failed to create solution: ${error instanceof Error ? error.message : 'Unknown error'}`);
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
      <title>Create Solution</title>
      <link rel="stylesheet" href="${styleUri}">
    </head>
    <body>
      <div class="container">
        <h3>Create new solution</h3>
        <div>
          <div class="row">
            <label for="solution-name">Solution name</label>
            <input type="text" id="solution-name" placeholder="${CreateSolutionViewProvider.DEFAULTS.name}" value="${CreateSolutionViewProvider.DEFAULTS.name}" />
            <div class="help-text">Letters, numbers, hyphens and underscores only</div>
            <div id="name-error" class="validation-error" style="display: none;"></div>
          </div>

          <div class="row">
            <label for="display-name">Display name</label>
            <input type="text" id="display-name" placeholder="${CreateSolutionViewProvider.DEFAULTS.displayName}" value="${CreateSolutionViewProvider.DEFAULTS.displayName}" />
            <div class="help-text">Human-readable name for the solution</div>
            <div id="display-name-error" class="validation-error" style="display: none;"></div>
          </div>

          <div class="row">
            <label for="ui-type">UI framework</label>
            <select id="ui-type">
              <option value="dash" selected>dash</option>
              <option value="none">none</option>
            </select>
            <div id="ui-type-error" class="validation-error" style="display: none;"></div>
          </div>

          <div class="row">
            <label for="namespace">Namespace</label>
            <input type="text" id="namespace" placeholder="${CreateSolutionViewProvider.DEFAULTS.namespace}" value="${CreateSolutionViewProvider.DEFAULTS.namespace}" />
            <div class="help-text">Namespace for the solution</div>
            <div id="namespace-error" class="validation-error" style="display: none;"></div>
          </div>

          <div class="row">
            <label for="target-directory">Target directory</label>
            <div class="file-row">
              <input type="text" id="target-directory" placeholder="Select directory..." readonly />
              <button id="browse-btn">...</button>
            </div>
            <div class="help-text">Directory where the solution will be created</div>
            <div id="directory-error" class="validation-error" style="display: none;"></div>
          </div>
          <hr>
          <div class="row">
            <h3>Create solution command</h3>
            <div class="command-row">
              <div class="command-preview">
                <code id="command-preview">saf new</code>
              </div>
              <button id="copy-command-btn" title="Copy command">⧉</button>
            </div>
          </div>
        </div>

        <button id="create-btn" class="action-button">Create solution</button>
      </div>

      <script>
        const vscode = acquireVsCodeApi();
        const DEFAULTS = ${JSON.stringify(CreateSolutionViewProvider.DEFAULTS)};

        // State management
        const state = vscode.getState() || {
          solutionName: DEFAULTS.name,
          displayName: DEFAULTS.displayName,
          namespace: DEFAULTS.namespace,
          uiType: DEFAULTS.uiType,
          targetDirectory: ''
        };

        // DOM Elements
        const solutionNameInput = document.getElementById('solution-name');
        const displayNameInput = document.getElementById('display-name');
        const namespaceInput = document.getElementById('namespace');
        const uiTypeSelect = document.getElementById('ui-type');
        const targetDirectoryInput = document.getElementById('target-directory');
        const browseBtn = document.getElementById('browse-btn');
        const createBtn = document.getElementById('create-btn');
        const nameError = document.getElementById('name-error');
        const displayNameError = document.getElementById('display-name-error');
        const namespaceError = document.getElementById('namespace-error');
        const directoryError = document.getElementById('directory-error');
        const uiTypeError = document.getElementById('ui-type-error');
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

        function updateCommandPreview() {
          const name = solutionNameInput.value.trim();
          const displayName = displayNameInput.value.trim();
          const uiType = uiTypeSelect.value;
          const namespace = namespaceInput.value.trim();

          let command = 'saf new';
          if (name) command += ' --solution-name ' + name;
          if (displayName) command += ' --solution-display-name "' + displayName + '"';
          if (uiType) command += ' --ui-framework ' + uiType;
          if (namespace) command += ' --namespace ' + namespace;

          commandPreview.textContent = command;
          checkCommandOverflow();
        }

        // Reset form fields with optional exclusions
        function resetInputValues(options) {
          const keepTargetDirectory = options?.keepTargetDirectory ?? false;

          solutionNameInput.value = DEFAULTS.name;
          displayNameInput.value = DEFAULTS.displayName;
          uiTypeSelect.value = DEFAULTS.uiType;
          namespaceInput.value = DEFAULTS.namespace;
          if (!keepTargetDirectory) {
            targetDirectoryInput.value = '';
          }
        }

        // Save current state
        function saveState() {
          state.solutionName = solutionNameInput.value;
          state.displayName = displayNameInput.value;
          state.uiType = uiTypeSelect.value;
          state.namespace = namespaceInput.value;
          state.targetDirectory = targetDirectoryInput.value;
          vscode.setState(state);
        }

        // Validate solution name
        function validateSolutionName() {
          const name = solutionNameInput.value.trim();
          if (!name) {
            nameError.textContent = 'Solution name is required';
            nameError.style.display = 'block';
            return false;
          }
          if (!/^[a-zA-Z0-9_-]+$/.test(name)) {
            nameError.textContent = 'Solution name can only contain letters, numbers, hyphens and underscores';
            nameError.style.display = 'block';
            return false;
          }
          nameError.style.display = 'none';
          return true;
        }

        // Validate display name
        function validateDisplayName() {
          const displayName = displayNameInput.value.trim();
          if (!displayName) {
            displayNameError.textContent = 'Display name is required';
            displayNameError.style.display = 'block';
            return false;
          }
          displayNameError.style.display = 'none';
          return true;
        }


        function showError(message) {
          namespaceError.textContent = message;
          namespaceError.style.display = 'block';
        }

        // Validate namespace (mirrors validateNamespace in validation.ts)
        function validateNamespace() {
          const value = namespaceInput.value.trim();

          if (!value) {
            showError('Namespace cannot be empty or just whitespace');
            return false;
          }

          if (value.startsWith('.') || value.endsWith('.')) {
            showError('Namespace cannot start or end with a dot');
            return false;
          }

          if (value.includes('..')) {
            showError('Namespace cannot contain empty segments (for example: a..b)');
            return false;
          }

          const segmentPattern = /^[a-z_][a-z0-9_]*$/;
          const segments = value.split('.');

          if (segments.some(segment => segment.trim() === '')) {
            showError('Namespace cannot contain empty segments (for example: a..b)');
            return false;
          }

          for (const segment of segments) {
            if (segment !== segment.toLowerCase()) {
              showError('Each segment of the namespace must be in lowercase');
              return false;
            }
            if (/^[0-9]/.test(segment)) {
              showError('Each segment of the namespace must not start with a number');
              return false;
            }
            if (!segmentPattern.test(segment)) {
              showError('Each segment of the namespace must start with a letter or underscore and contain only lowercase letters, numbers, and underscores');
              return false;
            }
          }

          namespaceError.style.display = 'none';
          return true;
        }


        // Validate target directory
        function validateTargetDirectory() {
          const directory = targetDirectoryInput.value.trim();
          if (!directory) {
            directoryError.textContent = 'Target directory is required';
            directoryError.style.display = 'block';
            return false;
          }
          directoryError.style.display = 'none';
          return true;
        }

        // Validate UI type
        function validateUIType() {
          if (uiTypeSelect.value === '') {
            uiTypeError.textContent = 'UI Framework is required';
            uiTypeError.style.display = 'block';
            return false;
          }
          uiTypeError.style.display = 'none';
          return true;
        }

        // Track if display name was manually edited
        let displayNameManuallyEdited = false;

        // Auto-generate display name from solution name
        solutionNameInput.addEventListener('input', function() {
          const name = this.value.trim();

          // Auto-generate display name only if it hasn't been manually edited
          if (!displayNameManuallyEdited && name) {
            const generatedName = name.split(/[-_]/)
              .map(word => word.charAt(0).toUpperCase() + word.slice(1))
              .join(' ');
            displayNameInput.value = generatedName;
          }

          validateSolutionName();
          saveState();
          updateCommandPreview(); // Add this
        });

        // Mark display name as manually edited when user types in it
        displayNameInput.addEventListener('input', function() {
          displayNameManuallyEdited = true;
          validateDisplayName();
          saveState();
          updateCommandPreview(); // Add this
        });

        displayNameInput.addEventListener('blur', validateDisplayName);
        uiTypeSelect.addEventListener('change', function() {
          saveState();
          updateCommandPreview(); // Add this
        });

        namespaceInput.addEventListener('input', function() {
          validateNamespace();
          saveState();
          updateCommandPreview();
        });

        namespaceInput.addEventListener('blur', validateNamespace);
        browseBtn.addEventListener('click', function() {
          vscode.postMessage({ command: 'browse-folder' });
        });

        targetDirectoryInput.addEventListener('input', updateCommandPreview); // Add this

        createBtn.addEventListener('click', function() {
          const isNameValid = validateSolutionName();
          const isDisplayNameValid = validateDisplayName();
          const isUITypeValid = validateUIType();
          const isNamespaceValid = validateNamespace();
          const isDirectoryValid = validateTargetDirectory();

          if (!isNameValid || !isDisplayNameValid || !isUITypeValid || !isNamespaceValid || !isDirectoryValid) {
            return;
          }

          createBtn.disabled = true;
          createBtn.textContent = 'Creating...';

          vscode.postMessage({
            command: 'create-solution',
            config: {
              name: solutionNameInput.value.trim(),
              displayName: displayNameInput.value.trim(),
              uiType: uiTypeSelect.value,
              namespace: namespaceInput.value.trim(),
              targetDirectory: targetDirectoryInput.value.trim()
            }
          });
        });

        // Handle messages from extension
        window.addEventListener('message', (event) => {
          const message = event.data;

          if (message.type === 'set-target-directory') {
            targetDirectoryInput.value = message.path;
            validateTargetDirectory();
            saveState();
            updateCommandPreview();
          }

          if (message.type === 'solution-created') {
            // Re-enable the button
            createBtn.disabled = false;
            createBtn.textContent = 'Create solution';

            // Clear the form but keep target directory for next solution
            resetInputValues({ keepTargetDirectory: true });
            nameError.style.display = 'none';
            displayNameError.style.display = 'none';
            namespaceError.style.display = 'none';
            directoryError.style.display = 'none';
            uiTypeError.style.display = 'none';
            displayNameManuallyEdited = false;
            saveState();
            updateCommandPreview();
          }

          if (message.type === 'solution-creation-failed') {
            // Re-enable the button on failure
            createBtn.disabled = false;
            createBtn.textContent = 'Create solution';
          }
        });

        updateCommandPreview();
        vscode.postMessage({ command: 'webview-ready' });
      </script>
    </body>
    </html>`;
  }
}
