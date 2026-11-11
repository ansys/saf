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
import { SAFSolutionsProvider } from '../SAFSolutionsProvider';
import { StorageService } from '../../services/StorageService';
import { solutionSelectionService } from '../../services/SolutionSelectionService';
import { getCurrentWorkspaceSolutionName } from '../../utils/workspaceUtils';

export interface WorkspacePromptOptions {
  [key: string]: unknown;
}

export async function handleWorkspacePrompt(
  options: WorkspacePromptOptions,
  actionFn: (solutionName: string, options: WorkspacePromptOptions) => Promise<void>
): Promise<void> {
  try {
    // Check if we have an open workspace
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    let currentWorkspaceSolution: string | undefined;

    if (workspaceFolder) {
      const solutionPath = workspaceFolder.uri.fsPath;
      currentWorkspaceSolution = getCurrentWorkspaceSolutionName(solutionPath);

      if (currentWorkspaceSolution) {
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
          const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();
          if (solutions.length === 0) {
            vscode.window.showErrorMessage('No solutions available');
            return;
          }

          const selectedSolution = await vscode.window.showQuickPick(
            solutions.map(s => ({
              label: s.name,
              description: s.displayName || undefined
            })),
            { placeHolder: 'Select a solution' }
          );

          if (!selectedSolution) {
            return;
          }

          await actionFn(selectedSolution.label, options);
        } else {
          await actionFn(currentWorkspaceSolution, options);
        }
      } else {
        const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();
        if (solutions.length === 0) {
          vscode.window.showErrorMessage('No solutions available');
          return;
        }

        const selectedSolution = await vscode.window.showQuickPick(
          solutions.map(s => ({
            label: s.name,
            description: s.displayName || undefined
          })),
          { placeHolder: 'Select a solution' }
        );

        if (!selectedSolution) {
          return;
        }

        await actionFn(selectedSolution.label, options);
      }
    }
  } catch (error) {
    vscode.window.showErrorMessage(`Failed to install the solution's environment: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

export async function loadSolutions(view: vscode.WebviewView | undefined, workspaceRoot: string | undefined): Promise<void> {
  try {
    const safSolutionsProvider = SAFSolutionsProvider.getInstance();
    safSolutionsProvider.refresh();
    const solutions = await safSolutionsProvider.getSAFSolutions();
    const selectedSolution = StorageService.getSelectedSolution(workspaceRoot);

    if (view) {
      view.webview.postMessage({
        type: 'solutions-loaded',
        solutions: solutions.map(s => ({
          name: s.name,
          displayName: s.displayName,
          rootDirectory: s.rootDirectory
        })),
        selectedSolution: selectedSolution?.name || null
      });
    }
  } catch (error) {
    console.error('Error loading solutions:', error);
  }
}

export function checkSolutionEnvironment(solutionPath: string): boolean {
  // eslint-disable-next-line security/detect-non-literal-fs-filename
  const venvExists = fs.existsSync(path.join(solutionPath, '.venv'));
  return venvExists;
}

export async function handleSelectAnotherSolution(
  view: vscode.WebviewView,
  workspaceRoot: string | undefined,
  previousSelection: string | undefined
): Promise<void> {
  const result = await solutionSelectionService.selectAndRegisterSolution(workspaceRoot);
  if (result) {
    SAFSolutionsProvider.getInstance().refresh();
    await loadSolutions(view, workspaceRoot);
    view.webview.postMessage({
      type: 'set-selected-solution',
      selectedSolution: result.name,
      displayName: result.displayName,
      rootDirectory: result.path
    });
  } else {
    view.webview.postMessage({
      type: 'revert-solution',
      previousSelection: previousSelection || ''
    });
  }
}
