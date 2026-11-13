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


export class MinimalMockExtensionContext implements vscode.ExtensionContext {
  secrets: vscode.SecretStorage = {
    get: async (_key: string) => undefined,
    store: async (_key: string, _value: string) => {},
    delete: async (_key: string) => {},
    keys: async () => [],
    onDidChange: (_listener: any) => ({ dispose: () => {} })
  } as any;
  languageModelAccessInformation: vscode.LanguageModelAccessInformation = undefined as any;
  subscriptions: { dispose(): any }[] = [];
  extensionPath = '';
  extensionUri = vscode.Uri.file('');
  globalStorageUri = vscode.Uri.file('');
  globalStoragePath = '';
  storagePath = '';
  logPath = '';
  logUri = vscode.Uri.file('');
  globalState = {
    get: (_key: string) => undefined,
  update: async (_key: string, _value: unknown) => {},
    keys: () => [],
    setKeysForSync: () => {}
  } as any;
  workspaceState = {
    get: (_key: string) => undefined,
    update: async (_key: string, _value: unknown) => {},
    keys: () => []
  } as any;
  asAbsolutePath = (relativePath: string) => relativePath;
  extensionMode = 3;
  environmentVariableCollection = {} as any;
  storageUri = undefined;
  workspaceStateUri = undefined;
  extension = {
    id: 'mock.extension.id',
    extensionUri: vscode.Uri.file(''),
    extensionPath: '',
    isActive: true,
    packageJSON: {},
    extensionKind: 1,
    exports: undefined,
    activate: async () => {}
  } as vscode.Extension<any>;
}
