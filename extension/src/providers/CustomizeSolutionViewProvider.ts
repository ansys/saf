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
import { AddStepViewProvider } from './AddStepViewProvider';

export class CustomizeSolutionViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'solutionCustomization';
  private _view: vscode.WebviewView | undefined;
  private _addStepProvider: AddStepViewProvider;

  constructor(private readonly _extensionUri: vscode.Uri) {
    this._addStepProvider = new AddStepViewProvider(_extensionUri);
  }

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    context: vscode.WebviewViewResolveContext,
    token: vscode.CancellationToken,
  ): void {
    this._view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri]
    };

    webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

    const mockWebviewView: vscode.WebviewView = {
      ...webviewView,
      webview: webviewView.webview
    };
    this._addStepProvider['resolveWebviewView'](mockWebviewView, context, token);

    // Intentionally echo messages back to the webview as a passthrough channel.
    webviewView.webview.onDidReceiveMessage(async (message) => {
      webviewView.webview.postMessage(message);
    });

    webviewView.onDidChangeVisibility(() => {
      if (webviewView.visible) {
        webviewView.webview.postMessage({ command: 'load-solutions' });
      }
    });
  }

  private _getHtmlForWebview(webview: vscode.Webview): string {
    const addStepHtml = this._addStepProvider.getHtmlForWebview(webview);
    return `<!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline' ${webview.cspSource}; script-src 'unsafe-inline';">
      <title>Customize Solution</title>
    </head>
    <body>
      <div id="add-step-section">
        ${addStepHtml}
      </div>
    </body>
    </html>`;
  }
}