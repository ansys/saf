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
import { SAFSolutionsProvider } from './SAFSolutionsProvider';
import { StorageService } from '../services/StorageService';
import { handleSelectAnotherSolution, handleWorkspacePrompt, loadSolutions, WorkspacePromptOptions, checkSolutionEnvironment } from './common/providerTools';
import { executeCommandInTerminal } from '../utils/terminalUtils';
export class BuildInstallerProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'solutions-manager.buildInstaller';
  private _view?: vscode.WebviewView;
  private readonly workspaceRoot: string | undefined;
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

    this.setSelectedSolutionFromStorage();

    setTimeout(() => {
      loadSolutions(webviewView, this.workspaceRoot);
    }, 100);

    webviewView.webview.onDidReceiveMessage(async message => {
      try {
        switch (message.command) {
          case 'build-installer':
            await this.buildInstaller(message.solutionName, message.options);
            break;
          case 'build-installer-workspace-prompt':
            await handleWorkspacePrompt(message.options, (name, opts) => this.buildInstaller(name, opts));
            break;
          case 'load-solutions':
            await loadSolutions(webviewView, this.workspaceRoot);
            break;
          case 'show-error':
            vscode.window.showErrorMessage(message.message);
            break;
          case 'select-another-solution':
            await handleSelectAnotherSolution(webviewView, this.workspaceRoot, message.previousSelection);
            break;
          case 'browse-env-file':
            await this.browseEnvFile();
            break;
          case 'browse-encryption-file':
            await this.browseEncryptionFile();
            break;
        }
      } catch (error) {
        console.error('Error handling webview message:', error);
        vscode.window.showErrorMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }
    });

    webviewView.onDidChangeVisibility(() => {
      if (webviewView.visible) {
        this.setSelectedSolutionFromStorage();
        loadSolutions(webviewView, this.workspaceRoot);
      }
    });
  }

  private setSelectedSolutionFromStorage(): void {
    const selectedSolution = StorageService.getSelectedSolution(this.workspaceRoot);

    if (selectedSolution && this._view) {
      this._view.webview.postMessage({
        type: 'set-selected-solution',
        selectedSolution: selectedSolution.name,
        displayName: selectedSolution.displayName
      });
    }
  }

  private async buildInstaller(solutionName: string, options: WorkspacePromptOptions): Promise<void> {
    try {
      const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();
      const solution = solutions.find(s => s.name === solutionName);

      if (!solution) {
        vscode.window.showErrorMessage(`Solution '${solutionName}' not found.`);
        return;
      }

      if (!checkSolutionEnvironment(solution.rootDirectory)) {
        vscode.window.showInformationMessage(`Installing development environment for ${solution.name}.`);
        await vscode.commands.executeCommand('solutions-manager.installDevEnvironment');
      }

      const terminalName = `SAF Build - ${solutionName}`;
      const existingTerminal = vscode.window.terminals.find(t => t.name === terminalName);
      if (existingTerminal) {
        existingTerminal.dispose();
      }
      this.terminalInstance = vscode.window.createTerminal(terminalName);
      this.terminalInstance.show();

      const safCliExecutable = StorageService.getSafCliTerminalCommand();
      let buildCommand = safCliExecutable + ` build ${solutionName}`;

      if (options.offlinePackage) {
        buildCommand += ' --offline-package';
      }

      if (options.displayConsoleWindow) {
        buildCommand += ' --display-console-window';
      }

      if (options.pythonVersion) {
        buildCommand += ` --python-version ${options.pythonVersion}`;
      }

      if (options.excludePython) {
        buildCommand += ' --exclude-python';
      }

      if (options.encrypt) {
        buildCommand += ' --encrypt';
      }

      if (options.encryptionFile) {
        const encryptionFilePath = String(options.encryptionFile).replace(/\\/g, '/');
        buildCommand += ` --encryption-file "${encryptionFilePath}"`;
      }

      if (options.encryptionKey) {
        const encryptionKey = String(options.encryptionKey).replace(/\s+/g, '').replace(/"/g, '\\"');
        buildCommand += ` --encryption-key "${encryptionKey}"`;
      }

      if (options.obfuscate) {
        buildCommand += ' --obfuscate';
      }

      if (options.executableAsDir) {
        buildCommand += ' --executable-as-dir';
      }

      if (options.forcePythonFromSource) {
        buildCommand += ' --force-python-from-source';
      }

      if (options.envFile) {
        const envFilePath = String(options.envFile).replace(/\\/g, '/');
        buildCommand += ` --env-file "${envFilePath}"`;
      }

      if (options.noExecutable) {
        buildCommand += ' --no-executable';
      }

      if (options.solutionEntryPoint) {
        const solutionEntryPoint = String(options.solutionEntryPoint).replace(/"/g, '\\"');
        buildCommand += ` --solution-entry-point "${solutionEntryPoint}"`;
      }

      if (options.githubToken) {
        const githubToken = String(options.githubToken).replace(/\s+/g, '').replace(/"/g, '\\"');
        buildCommand += ` --github-token "${githubToken}"`;
      }

      if (options.solutionUiFramework) {
        const solutionUiFramework = String(options.solutionUiFramework).replace(/"/g, '\\"');
        buildCommand += ` --solution-ui-framework "${solutionUiFramework}"`;
      }

      await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: `Building solution installer for ${solutionName}`,
        cancellable: false
      }, async (progress) => {
        progress.report({ message: `Executing build command, it will take several minutes...` });
        await executeCommandInTerminal(this.terminalInstance!, buildCommand);

        let installerName;
        if (process.platform === 'win32') {
          installerName = `${solution.name}-installer.exe`;
        } else {
          installerName = `${solution.name}-installer`;
        }

        const installerPath = path.join(solution.rootDirectory, 'dist', installerName);

        // eslint-disable-next-line security/detect-non-literal-fs-filename
        if (fs.existsSync(installerPath)) {
          progress.report({ message: `Installer built at: ${installerPath}`, increment: 100 });
        } else {
          progress.report({
            message: `Build completed, but the installer was not found at: ${installerPath}. Check the build output in the terminal for details.`,
            increment: 100
          });
          vscode.window.showWarningMessage(
            `Expected installer not found at: ${installerPath}. Please review the build output in the terminal for possible errors.`
          );
        }
      });
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to build installer: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  private async browseEnvFile(): Promise<void> {
    try {
      const fileUris = await vscode.window.showOpenDialog({
        canSelectMany: false,
        canSelectFiles: true,
        canSelectFolders: false,
        title: 'Select Environment File'
      });

      if (fileUris && fileUris[0] && this._view) {
        this._view.webview.postMessage({
          type: 'env-file-selected',
          path: fileUris[0].fsPath
        });
      }
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to browse for environment file: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  private async browseEncryptionFile(): Promise<void> {
    try {
      const fileUris = await vscode.window.showOpenDialog({
        canSelectMany: false,
        canSelectFiles: true,
        canSelectFolders: false,
        title: 'Select Encryption File List'
      });

      if (fileUris && fileUris[0] && this._view) {
        this._view.webview.postMessage({
          type: 'encryption-file-selected',
          path: fileUris[0].fsPath
        });
      }
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to browse for encryption file: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  private _getHtmlForWebview(webview: vscode.Webview): string {
    const styleUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this._extensionUri, 'out', 'webview', 'styles', 'common.css')
    );
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this._extensionUri, 'out', 'webview', 'scripts', 'buildInstaller.js')
    );

    const htmlPath = path.join(this._extensionUri.fsPath, 'out', 'webview', 'templates', 'buildInstaller.html');
    // eslint-disable-next-line security/detect-non-literal-fs-filename
    let html = fs.readFileSync(htmlPath, 'utf8');

    html = html.replace(/\{\{cspSource\}\}/g, webview.cspSource);
    html = html.replace(/\{\{styleUri\}\}/g, styleUri.toString());
    html = html.replace(/\{\{scriptUri\}\}/g, scriptUri.toString());

    return html;
  }
}
