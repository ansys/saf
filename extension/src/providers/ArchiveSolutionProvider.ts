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
import { handleSelectAnotherSolution, loadSolutions } from './common/providerTools';
import { executeCommandInTerminal } from '../utils/terminalUtils';

export interface ArchiveOptions {
  outputPath?: string;
  filename?: string;
  extension?: string;
}

export class ArchiveSolutionProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'solutions-manager.archiveSolution';
  private static instance: ArchiveSolutionProvider | undefined;
  private _view?: vscode.WebviewView;
  private readonly workspaceRoot: string | undefined;
  private initialLoadTimeout: NodeJS.Timeout | undefined;
  private terminalInstance: vscode.Terminal | undefined;
  private isArchiving = false;
  private statusBarItem: vscode.StatusBarItem | undefined;
  private pendingSelection?: { solutionName: string; rootDirectory?: string };

  constructor(private readonly _extensionUri: vscode.Uri) {
    this.workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    vscode.window.onDidCloseTerminal(terminal => {
      if (this.terminalInstance === terminal) {
        this.terminalInstance = undefined;
      }
    });
  }

  public static getInstance(extensionUri?: vscode.Uri): ArchiveSolutionProvider {
    if (!ArchiveSolutionProvider.instance) {
      if (!extensionUri) {
        throw new Error('ArchiveSolutionProvider: extensionUri is required on first call to getInstance()');
      }
      ArchiveSolutionProvider.instance = new ArchiveSolutionProvider(extensionUri);
    }
    return ArchiveSolutionProvider.instance;
  }

  public static resetInstance(): void {
    ArchiveSolutionProvider.instance?.dispose();
    ArchiveSolutionProvider.instance = undefined;
  }

  private clearInitialLoadTimeout(): void {
    if (this.initialLoadTimeout) {
      clearTimeout(this.initialLoadTimeout);
      this.initialLoadTimeout = undefined;
    }
  }

  public dispose(): void {
    this.clearInitialLoadTimeout();
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

    if (this.pendingSelection) {
      webviewView.webview.postMessage({
        type: 'preselect-solution',
        selectedSolution: this.pendingSelection.solutionName,
        rootDirectory: this.pendingSelection.rootDirectory,
        resetFilename: true,
        resetExtension: true
      });
      this.pendingSelection = undefined;
    }

    this.clearInitialLoadTimeout();
    this.initialLoadTimeout = setTimeout(() => {
      loadSolutions(webviewView, this.workspaceRoot);
    }, 100);

    webviewView.webview.onDidReceiveMessage(async message => {
      try {
        switch (message.command) {
          case 'archive-solution':
            await this.archiveSolution(message.solutionName, message.options);
            break;
          case 'browse-output-path':
            await this.browseOutputPath();
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

    webviewView.onDidDispose(() => {
      this.clearInitialLoadTimeout();
      if (this._view === webviewView) {
        this._view = undefined;
      }
    });
  }

  public preselectSolution(solutionName: string, rootDirectory?: string): void {
    if (this._view) {
      this._view.webview.postMessage({
        type: 'preselect-solution',
        selectedSolution: solutionName,
        rootDirectory,
        resetFilename: true,
        resetExtension: true
      });
      return;
    }

    this.pendingSelection = { solutionName, rootDirectory };
  }

  private setSelectedSolutionFromStorage(): void {
    const selectedSolution = StorageService.getSelectedSolution(this.workspaceRoot);
    if (selectedSolution && this._view) {
      this._view.webview.postMessage({
        type: 'set-selected-solution',
        selectedSolution: selectedSolution.name,
        displayName: selectedSolution.displayName,
        rootDirectory: selectedSolution.path
      });
    }
  }

  public async archiveSolution(solutionName: string, options: ArchiveOptions): Promise<void> {
    if (this.isArchiving) {
      vscode.window.showWarningMessage('An archive operation is already in progress. Please wait for it to complete.');
      return;
    }

    this.isArchiving = true;
    this._view?.webview.postMessage({ type: 'set-archiving-state', archiving: true });

    try {
      const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();
      const solution = solutions.find(s => s.name === solutionName);

      if (!solution) {
        vscode.window.showErrorMessage(`Solution '${solutionName}' not found.`);
        return;
      }

      if (options.extension && !options.extension.startsWith('.')) {
        vscode.window.showErrorMessage("Extension must start with '.'.");
        return;
      }

      const solutionRoot = path.resolve(solution.rootDirectory);
      const outputDir = path.resolve(options.outputPath ?? solution.rootDirectory);
      if (outputDir.startsWith(solutionRoot)) {
        const choice = await vscode.window.showWarningMessage(
          `The output directory is inside the solution root. Repeated archives will embed previous archive files inside new ones. Proceed anyway?`,
          'Proceed',
          'Cancel'
        );
        if (choice !== 'Proceed') {
          return;
        }
      }

      const terminalName = `SAF Archive - ${solutionName}`;
      const existingTerminal = vscode.window.terminals.find(t => t.name === terminalName);
      if (existingTerminal) {
        existingTerminal.dispose();
      }

      this.terminalInstance = vscode.window.createTerminal(terminalName);
      const terminal = this.terminalInstance;
      terminal.show();

      const safCliExecutable = StorageService.getSafCliTerminalCommand();
      const args: string[] = ['archive', solution.rootDirectory];

      if (options.outputPath) {
        args.push('--path', options.outputPath);
      }

      if (options.filename) {
        args.push('--filename', options.filename);
      }

      if (options.extension) {
        args.push('--extension', options.extension);
      }

      const command = [safCliExecutable, ...args.map(a => /\s/.test(a) ? `"${a}"` : a)].join(' ');

      this.statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
      this.statusBarItem.text = `$(sync~spin) Archiving "${solutionName}"`;
      this.statusBarItem.tooltip = `Archiving solution "${solutionName}". Close the terminal to cancel.`;
      this.statusBarItem.show();

      let archiveCancelled = false;
      await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: `Archiving solution "${solutionName}"`,
        cancellable: true
      }, async (progress, token) => {
        token.onCancellationRequested(() => {
          archiveCancelled = true;
          terminal.dispose();
        });
        progress.report({ message: 'Running saf archive...' });
        await executeCommandInTerminal(terminal, command);
      });

      if (!archiveCancelled) {
        SAFSolutionsProvider.getInstance().refresh();
        vscode.window.showInformationMessage(`Solution "${solutionName}" has been archived.`);
      } else {
        vscode.window.showWarningMessage(`Archive of "${solutionName}" was cancelled.`);
      }
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to archive solution: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      this.isArchiving = false;
      this.statusBarItem?.dispose();
      this.statusBarItem = undefined;
      this._view?.webview.postMessage({ type: 'set-archiving-state', archiving: false });
    }
  }

  private async browseOutputPath(): Promise<void> {
    try {
      const folderUris = await vscode.window.showOpenDialog({
        canSelectMany: false,
        canSelectFolders: true,
        canSelectFiles: false,
        title: 'Select output directory'
      });

      if (folderUris?.[0] && this._view) {
        this._view.webview.postMessage({
          type: 'output-path-selected',
          path: folderUris[0].fsPath
        });
      }
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to browse for directory: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  private _getHtmlForWebview(webview: vscode.Webview): string {
    const styleUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this._extensionUri, 'out', 'webview', 'styles', 'common.css')
    );
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this._extensionUri, 'out', 'webview', 'scripts', 'archiveSolution.js')
    );

    const htmlPath = path.join(this._extensionUri.fsPath, 'out', 'webview', 'templates', 'archiveSolution.html');
    // eslint-disable-next-line security/detect-non-literal-fs-filename
    let html = fs.readFileSync(htmlPath, 'utf8');

    html = html.replace(/\{\{cspSource\}\}/g, webview.cspSource);
    html = html.replace(/\{\{styleUri\}\}/g, styleUri.toString());
    html = html.replace(/\{\{scriptUri\}\}/g, scriptUri.toString());

    return html;
  }

}
