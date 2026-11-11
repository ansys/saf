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


import * as sinon from 'sinon';
import { EventEmitter } from 'events';

/**
 * Mock ExtensionContext for testing
 *
 * Why needed:
 * - Used by StorageService to persist venv paths and configuration (globalState, workspaceState)
 * - Used by ConfigurationPanel to access extension resources and storage
 * - Required by extension.ts activate() function
 */
export class MockExtensionContext {
  subscriptions: any[] = [];
  workspaceState = {
    get: sinon.stub(),
    update: sinon.stub().resolves(),
    keys: sinon.stub().returns([])
  };
  globalState = {
    get: sinon.stub(),
    update: sinon.stub().resolves(),
    keys: sinon.stub().returns([]),
    setKeysForSync: sinon.stub()
  };
  secrets = {
    get: sinon.stub().resolves(undefined),
    store: sinon.stub().resolves(),
    delete: sinon.stub().resolves(),
    keys: sinon.stub().resolves([]),
    onDidChange: sinon.stub().returns({ dispose: sinon.stub() })
  };
  extensionPath = '/mock/extension/path';
  extensionUri = {
    fsPath: '/mock/extension/path',
    path: '/mock/extension/path',
    scheme: 'file',
    authority: '',
    query: '',
    fragment: '',
    with: sinon.stub(),
    toJSON: sinon.stub()
  } as any;
  storagePath = '/mock/storage';
  globalStoragePath = '/mock/global/storage';
  logPath = '/mock/logs';
  extensionMode = 3;
  asAbsolutePath = sinon.stub().callsFake((p: string) => `/mock/extension/path/${p}`);
  storageUri = undefined;
  globalStorageUri = { fsPath: '/mock/global/storage' } as any;
  logUri = { fsPath: '/mock/logs' } as any;
  environmentVariableCollection = {
    persistent: true,
    replace: sinon.stub(),
    append: sinon.stub(),
    prepend: sinon.stub(),
    get: sinon.stub(),
    forEach: sinon.stub(),
    delete: sinon.stub(),
    clear: sinon.stub()
  } as any;
  extension = {
    id: 'mock.extension.id',
    extensionUri: { fsPath: '/mock/extension/path' } as any,
    extensionPath: '/mock/extension/path',
    isActive: true,
    packageJSON: {},
    extensionKind: 1,
    exports: undefined,
    activate: sinon.stub().resolves()
  } as any;
  languageModelAccessInformation = {
    onDidChange: sinon.stub().returns({ dispose: sinon.stub() }),
    canSendRequest: sinon.stub().returns(undefined)
  } as any;
}

/**
 * Mock OutputChannel for testing
 *
 * Why needed:
 * - Created by window.createOutputChannel() in various services
 * - Used for logging command execution, errors, and debugging information
 * - Provides a way to display text output to users without blocking UI
 */
export class MockOutputChannel {
  name = 'Mock Output Channel';
  append = sinon.stub();
  appendLine = sinon.stub();
  clear = sinon.stub();
  show = sinon.stub();
  hide = sinon.stub();
  dispose = sinon.stub();
  replace = sinon.stub();
}

/**
 * Mock WebviewPanel for testing
 *
 * Why needed:
 * - Created by ConfigurationPanel.show() to display environment variable configuration UI
 * - Provides HTML-based UI within VS Code (webview.html property)
 * - Handles bidirectional messaging between extension and webview (postMessage, onDidReceiveMessage)
 */
export class MockWebviewPanel {
  webview: any;
  viewType = 'mockView';
  title = 'Mock Panel';
  options = {};
  viewColumn = 1;
  active = true;
  visible = true;
  onDidDispose = sinon.stub().returns({ dispose: sinon.stub() });
  onDidChangeViewState = sinon.stub().returns({ dispose: sinon.stub() });
  dispose = sinon.stub();
  reveal = sinon.stub();

  constructor() {
    this.webview = {
      html: '',
      options: {},
      onDidReceiveMessage: sinon.stub().returns({ dispose: sinon.stub() }),
      postMessage: sinon.stub().resolves(true),
      asWebviewUri: sinon.stub().callsFake((uri: any) => uri),
      cspSource: 'mock-csp'
    };
  }
}

/**
 * Mock Terminal for testing
 *
 * Why needed:
 * - Used for interactive command execution that requires user visibility
 * - Provides sendText() to execute shell commands in the terminal
 */
export class MockTerminal {
  name = 'Mock Terminal';
  processId = Promise.resolve(1234);
  creationOptions = {};
  exitStatus = undefined;
  state = { isInteractedWith: false };
  sendText = sinon.stub();
  show = sinon.stub();
  hide = sinon.stub();
  dispose = sinon.stub();
}




/**
 * Creates a minimal mock of the VS Code API with only the properties actually used in the codebase
 *
 * This mock is globally injected via setup.ts to intercept all 'vscode' imports during testing.
 * It allows source code to run in Node.js (where the real VS Code API doesn't exist) by providing
 * stub implementations of the VS Code API surface that the extension uses.
 */
export const createMockVSCode = () => ({
  window: {
    showInformationMessage: sinon.stub().resolves(undefined),
    showWarningMessage: sinon.stub().resolves(undefined),
    showErrorMessage: sinon.stub().resolves(undefined),
    showQuickPick: sinon.stub().resolves(undefined),
    showInputBox: sinon.stub().resolves(undefined),
    showOpenDialog: sinon.stub().resolves(undefined),
    createOutputChannel: sinon.stub().returns(new MockOutputChannel()),
    createWebviewPanel: sinon.stub().returns(new MockWebviewPanel()),
    createTerminal: sinon.stub().returns({
      show: sinon.stub(),
      dispose: sinon.stub(),
      name: 'mock-terminal',
      sendText: sinon.stub()
    }),
    terminals: [] as any[],
    onDidCloseTerminal: sinon.stub().returns({ dispose: sinon.stub() }),
    withProgress: sinon.stub().callsFake(async (_, task) => {
      const progress = {
        report: sinon.stub()
      };
      const token = {
        isCancellationRequested: false,
        onCancellationRequested: sinon.stub().returns({ dispose: sinon.stub() })
      };
      return await task(progress, token);
    }),
    createStatusBarItem: sinon.stub().returns({
      text: '',
      tooltip: '',
      command: undefined,
      show: sinon.stub(),
      hide: sinon.stub(),
      dispose: sinon.stub()
    }),
  },

  workspace: {
    workspaceFolders: undefined,
    getConfiguration: sinon.stub().returns({
      get: sinon.stub(),
      has: sinon.stub().returns(true),
      inspect: sinon.stub(),
      update: sinon.stub().resolves()
    }),
    createFileSystemWatcher: sinon.stub().returns({
      onDidChange: sinon.stub().returns({ dispose: sinon.stub() }),
      onDidCreate: sinon.stub().returns({ dispose: sinon.stub() }),
      onDidDelete: sinon.stub().returns({ dispose: sinon.stub() }),
      dispose: sinon.stub()
    }),
    onDidChangeWorkspaceFolders: sinon.stub().returns({ dispose: sinon.stub() }),
    onDidChangeConfiguration: sinon.stub().returns({ dispose: sinon.stub() }),
    findFiles: sinon.stub().resolves([])
  },

  RelativePattern: class MockRelativePattern {
    constructor(public base: string, public pattern: string) {}
  },

  commands: {
    registerCommand: sinon.stub().returns({ dispose: sinon.stub() }),
    registerTextEditorCommand: sinon.stub().returns({ dispose: sinon.stub() }),
    executeCommand: sinon.stub().resolves(),
    getCommands: sinon.stub().resolves([])
  },

  Uri: {
    parse: sinon.stub().callsFake((str: string) => ({
      fsPath: str,
      path: str,
      scheme: 'file',
      authority: '',
      query: '',
      fragment: '',
      toString: () => str,
      toJSON: () => ({ fsPath: str }),
      with: sinon.stub()
    })),
    file: sinon.stub().callsFake((path: string) => ({
      fsPath: path,
      path: path,
      scheme: 'file',
      authority: '',
      query: '',
      fragment: '',
      toString: () => path,
      toJSON: () => ({ fsPath: path }),
      with: sinon.stub()
    })),
    joinPath: sinon.stub().callsFake((base: any, ...paths: string[]) => ({
      fsPath: `${base.fsPath}/${paths.join('/')}`,
      path: `${base.path}/${paths.join('/')}`,
      scheme: base.scheme,
      authority: base.authority,
      query: base.query,
      fragment: base.fragment,
      toString: () => `${base.fsPath}/${paths.join('/')}`,
      toJSON: () => ({ fsPath: `${base.fsPath}/${paths.join('/')}` }),
      with: sinon.stub()
    })),
    from: sinon.stub()
  },

  env: {
    openExternal: sinon.stub().resolves(true),
    clipboard: {
      writeText: sinon.stub().resolves(),
      readText: sinon.stub().resolves('')
    }
  },

  ProgressLocation: {
    SourceControl: 1,
    Window: 10,
    Notification: 15
  },

  ViewColumn: {
    Active: -1,
    Beside: -2,
    One: 1,
    Two: 2,
    Three: 3,
    Four: 4,
    Five: 5,
    Six: 6,
    Seven: 7,
    Eight: 8,
    Nine: 9
  },

  TreeItemCollapsibleState: {
    None: 0,
    Collapsed: 1,
    Expanded: 2
  },

  StatusBarAlignment: {
    Left: 1,
    Right: 2
  },

  EventEmitter: class MockEventEmitter {
    emitter = new EventEmitter();
    fire(data: any) {
      this.emitter.emit('event', data);
    }
    get event() {
      return (listener: any) => {
        this.emitter.on('event', listener);
        return { dispose: () => this.emitter.removeListener('event', listener) };
      };
    }
    dispose() {
      this.emitter.removeAllListeners();
    }
  },

  TreeItem: class MockTreeItem {
    constructor(
      public label: string,
      public collapsibleState?: number
    ) {}
    iconPath?: any;
    command?: any;
    contextValue?: string;
    tooltip?: string;
  },

  ThemeIcon: class MockThemeIcon {
    constructor(public id: string, public color?: any) {}
  },

  ThemeColor: class MockThemeColor {
    constructor(public id: string) {}
  },

  MarkdownString: class MockMarkdownString {
    public value: string = '';
    public isTrusted?: boolean;
    public supportThemeIcons?: boolean;
    public supportHtml?: boolean;

    constructor(value?: string) {
      this.value = value || '';
    }

    appendText(value: string): MockMarkdownString {
      this.value += value;
      return this;
    }

    appendMarkdown(value: string): MockMarkdownString {
      this.value += value;
      return this;
    }
  },

  ExtensionMode: {
    Production: 1,
    Development: 2,
    Test: 3
  }
});

export type MockVSCode = ReturnType<typeof createMockVSCode>;
