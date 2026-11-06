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
import { SelectedSolution, StorageService } from '../services/StorageService';
import { EnvironmentService } from '../services/EnvironmentService';
import { executeCommandInTerminal, createTerminalWithEnvironment } from '../utils/terminalUtils';
import { getWorkspaceSolutionInfo } from '../utils/workspaceUtils';
import { fileExistsSync } from '../utils/fsUtils';
import { checkSolutionEnvironment, handleSelectAnotherSolution, loadSolutions } from './common/providerTools';

export class SolutionRunViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'solutions-manager.solutionConfig';
  private _view?: vscode.WebviewView;
  private readonly workspaceRoot: string | undefined;
  private status: 'ready' | 'not-configured' = 'not-configured';
  private statusCheckInterval: NodeJS.Timeout | undefined;
  private selectedSolution?: SelectedSolution;

  constructor(
    private readonly _extensionUri: vscode.Uri,
    private readonly environmentService: EnvironmentService
  ) {
    this.workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

    this.checkEnvironment();

    this.updateWebviewStatus();
    setTimeout(() => {
      this.checkEnvironment();
    }, 500);
  }

  private checkEnvironment(targetPath?: string): void {
    const pathToCheck = targetPath || this.workspaceRoot;

    if (!pathToCheck) {
      this.status = 'not-configured';
      this.updateWebviewStatus();
      return;
    }

    try {
      const scriptsDir = process.platform === 'win32' ? 'Scripts' : 'bin';
      const venvDir = path.join(pathToCheck, '.venv');
      const scriptsPath = path.join(pathToCheck, '.venv', scriptsDir);

      const safExecutable = process.platform === 'win32' ? 'saf.exe' : 'saf';
      const solutionStarterExecutable = process.platform === 'win32' ? 'solution-app-starter.exe' : 'solution-app-starter';

      const safPath = path.join(pathToCheck, '.venv', scriptsDir, safExecutable);
      const solutionStarterPath = path.join(pathToCheck, '.venv', scriptsDir, solutionStarterExecutable);

      const venvExists = fileExistsSync(venvDir);
      const scriptsExists = fileExistsSync(scriptsPath);
      const safExists = fileExistsSync(safPath);
      const solutionStarterExists = fileExistsSync(solutionStarterPath);
      const hasExecutable = safExists || solutionStarterExists;

      const isVenvSetup = venvExists && scriptsExists && hasExecutable;

      const newStatus = isVenvSetup ? 'ready' : 'not-configured';

      if (newStatus !== this.status) {
        this.status = newStatus;
        this.updateWebviewStatus();

        if (this.status === 'ready') {
          this.loadSolutions();
        }
      } else {
        this.updateWebviewStatus();
      }

    } catch (error) {
      console.error('Error checking environment:', error);
      this.status = 'not-configured';
      this.updateWebviewStatus();
    }
  }

  private updateWebviewStatus(): void {
    if (this._view) {
      const message = {
        type: 'status-update',
        status: this.status
      };
      this._view.webview.postMessage(message);
    }
  }

  private startStatusPolling(): void {
    if (this.statusCheckInterval) {
      clearInterval(this.statusCheckInterval);
    }

    if (this.status === 'not-configured') {
      this.statusCheckInterval = setInterval(() => {
        this.checkEnvironment();

        if (this.status === 'ready' && this.statusCheckInterval) {
          clearInterval(this.statusCheckInterval);
          this.statusCheckInterval = undefined;
        }
      }, 2000);
    }
  }

  private stopStatusPolling(): void {
    if (this.statusCheckInterval) {
      clearInterval(this.statusCheckInterval);
      this.statusCheckInterval = undefined;
    }
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
      this.loadSolutions();
    }, 100);

    webviewView.webview.onDidReceiveMessage(async message => {
      try {
        switch (message.command) {
          case 'run-solution':
            await this.runSolution(message.options);
            break;
          case 'solution-changed':
            await this.handleSolutionChanged(message.solution);
            break;
          case 'show-env-config':
            await this.showEnvironmentConfig();
            break;
          case 'browse-env-file':
            await this.browseEnvFile();
            break;
          case 'get-status':
            this.checkEnvironment();
            break;
          case 'load-solutions':
            await this.loadSolutions();
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

    this.checkEnvironment();

    webviewView.onDidChangeVisibility(() => {
      if (webviewView.visible) {
        setTimeout(() => {
          this.checkEnvironment();
          this.setSelectedSolutionFromStorage();
          this.loadSolutions();
        }, 200);
      }
    });

    if (this.status === 'not-configured') {
      this.startStatusPolling();
    }
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

  private async handleSolutionChanged(solutionName: string): Promise<void> {
    if (!solutionName) {
      this.selectedSolution = undefined;
      return;
    }

    const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();
    const solution = solutions.find(s => s.name === solutionName);

    if (solution?.rootDirectory) {
      this.selectedSolution = {
        name: solution.name,
        displayName: solution.displayName,
        path: solution.rootDirectory
      };
    } else {
      this.selectedSolution = undefined;
    }
  }

  private async showEnvironmentConfig(): Promise<void> {
    if (!this.selectedSolution) {
      vscode.window.showWarningMessage('Please select a solution first to configure its environment.');
      return;
    }

    await vscode.commands.executeCommand(
      'solutions-manager.showEnvironmentConfig',
      this.selectedSolution.name,
      this.selectedSolution.path
    );
  }

  private async loadSolutions(): Promise<void> {
    await loadSolutions(this._view, this.workspaceRoot);
  }

  private async browseEnvFile(): Promise<void> {
    try {
      const fileUris = await vscode.window.showOpenDialog({
        canSelectMany: false,
        canSelectFiles: true,
        canSelectFolders: false,
        filters: { 'Environment Files': ['env'] },
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

  private async runSolution(options: any): Promise<void> {
    try {
      let solutionToRun: { name: string; path: string } | undefined;

      // Use selected solution if available
      if (options.solution) {
        const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();
        const solution = solutions.find(s => s.name === options.solution);
        if (solution?.rootDirectory) {
          solutionToRun = { name: solution.name, path: solution.rootDirectory };
        }
      }

      // Fall back to workspace solution if no solution selected
      if (!solutionToRun && this.workspaceRoot) {
        const currentSolution = await getWorkspaceSolutionInfo(this.workspaceRoot);
        if (currentSolution) {
          const useWorkspace = await vscode.window.showQuickPick(
            ['Yes', 'No'],
            { placeHolder: `Run solution in current workspace (${currentSolution.name})?` }
          );
          if (useWorkspace === 'Yes') {
            solutionToRun = currentSolution;
          }
        }
      }

      // Prompt user to select if still no solution
      if (!solutionToRun) {
        const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();
        if (solutions.length === 0) {
          vscode.window.showErrorMessage('No solutions available. Create a solution first.');
          return;
        }

        const selected = await vscode.window.showQuickPick(
          solutions.map(s => ({ label: s.name, description: s.displayName })),
          { placeHolder: 'Select a solution to run' }
        );

        if (!selected) {
          return;
        }

        const solution = solutions.find(s => s.name === selected.label);
        if (solution?.rootDirectory) {
          solutionToRun = { name: solution.name, path: solution.rootDirectory };
        } else {
          vscode.window.showErrorMessage(`Solution ${selected.label} path not found.`);
          return;
        }
      }

      if (!checkSolutionEnvironment(solutionToRun.path)) {
        vscode.window.showInformationMessage(`Installing development environment for ${solutionToRun.name}.`);
        await vscode.commands.executeCommand('solutions-manager.installDevEnvironment');
      }

      const safCliExecutables = StorageService.getSafCliTerminalCommand();
      let runCommand = safCliExecutables + ` run ${solutionToRun.name}`;

      if (options.portal) {runCommand += ' --portal';}
      if (options.browser) {runCommand += ' --browser';}
      if (options.debug) {runCommand += ' --debug';}
      if (options.uiDebugger) {runCommand += ' --ui-debugger';}
      if (options.noUi) {runCommand += ' --no-ui';}
      if (options.logLevel) {runCommand += ` --loglevel ${options.logLevel}`;}
      if (options.project) {runCommand += ` --project "${options.project}"`;}
      if (options.envFile) {
        const envFilePath = options.envFile.replace(/\\/g, '/');
        runCommand += ` --env-file "${envFilePath}"`;
      }

      const optionsEnabled = [];
      if (options.portal) {optionsEnabled.push('Portal Mode');}
      if (options.browser) {optionsEnabled.push('Browser Mode');}
      if (options.debug) {optionsEnabled.push('Debug Mode');}
      if (options.uiDebugger) {optionsEnabled.push('UI Debugger');}
      if (options.noUi) {optionsEnabled.push('No UI');}
      if (options.logLevel) {optionsEnabled.push(`Log Level: ${options.logLevel}`);}
      if (options.project) {optionsEnabled.push(`Project: ${options.project}`);}

      const baseMessage = `Running solution ${solutionToRun.name}`;
      const message = optionsEnabled.length > 0
        ? `${baseMessage} with ${optionsEnabled.join(', ')}`
        : baseMessage;

      vscode.window.showInformationMessage(message);

      const envVars = await this.environmentService.getAsEnvironmentObject(solutionToRun.path);

      const terminalInstance = createTerminalWithEnvironment(
        `SAF Run - ${solutionToRun.name}`,
        envVars,
        solutionToRun.path
      );

      await executeCommandInTerminal(terminalInstance, runCommand);
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to run solution: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  public dispose(): void {
    this.stopStatusPolling();
  }

  private _getHtmlForWebview(webview: vscode.Webview): string {
    const styleUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this._extensionUri, 'out', 'webview', 'styles', 'common.css')
    );
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this._extensionUri, 'out', 'webview', 'scripts', 'solutionRun.js')
    );

    const htmlPath = path.join(this._extensionUri.fsPath, 'out', 'webview', 'templates', 'solutionRun.html');
    // eslint-disable-next-line security/detect-non-literal-fs-filename
    let html = fs.readFileSync(htmlPath, 'utf8');

    html = html.replace(/\{\{cspSource\}\}/g, webview.cspSource);
    html = html.replace(/\{\{styleUri\}\}/g, styleUri.toString());
    html = html.replace(/\{\{scriptUri\}\}/g, scriptUri.toString());

    return html;
  }
}