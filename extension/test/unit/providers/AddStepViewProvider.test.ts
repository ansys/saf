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

import { expect } from 'chai';
import * as sinon from 'sinon';
import * as vscode from 'vscode';
import { AddStepViewProvider } from '../../../src/providers/AddStepViewProvider';
import { solutionService } from '../../../src/services/SolutionService';

/**
 * Extracts the client-side `formatTemplateLabel` function embedded in the
 * webview HTML and returns it as a callable so it can be unit tested in
 * isolation, without needing a DOM/browser environment.
 */
function extractFormatTemplateLabel(html: string): (value: string) => string {
  const marker = 'function formatTemplateLabel(value) {';
  const start = html.indexOf(marker);
  if (start === -1) {
    throw new Error('formatTemplateLabel function not found in generated HTML');
  }

  let depth = 0;
  let end = -1;
  for (let i = start; i < html.length; i++) {
    if (html[i] === '{') {
      depth++;
    } else if (html[i] === '}') {
      depth--;
      if (depth === 0) {
        end = i;
        break;
      }
    }
  }
  if (end === -1) {
    throw new Error('Could not find end of formatTemplateLabel function body');
  }

  const functionSource = html.substring(start, end + 1);
  // eslint-disable-next-line no-new-func -- intentional sandboxed evaluation of extracted webview script
  return new Function(`return (${functionSource});`)();
}

describe('AddStepViewProvider', () => {
  let provider: AddStepViewProvider;
  let mockExtensionUri: vscode.Uri;
  let mockWebviewView: vscode.WebviewView;
  let mockWebview: any;
  let messageHandler: ((message: any) => Promise<void>) | undefined;

  beforeEach(() => {
    mockExtensionUri = vscode.Uri.file('/mock/extension');

    mockWebview = {
      html: '',
      options: {},
      onDidReceiveMessage: sinon.stub().callsFake((handler) => {
        messageHandler = handler;
        return { dispose: sinon.stub() };
      }),
      postMessage: sinon.stub().resolves(true),
      asWebviewUri: sinon.stub().callsFake((uri: any) => uri),
      cspSource: 'mock-csp-source'
    };

    mockWebviewView = {
      webview: mockWebview,
      viewType: AddStepViewProvider.viewType,
      visible: true,
      onDidDispose: sinon.stub().returns({ dispose: sinon.stub() }),
      onDidChangeVisibility: sinon.stub().returns({ dispose: sinon.stub() }),
      show: sinon.stub(),
      title: undefined,
      description: undefined,
      badge: undefined
    } as any;

    provider = new AddStepViewProvider(mockExtensionUri);
  });

  afterEach(() => {
    sinon.restore();
    messageHandler = undefined;
  });

  describe('formatTemplateLabel (step template display name)', () => {
    let formatTemplateLabel: (value: string) => string;

    beforeEach(() => {
      const html = provider.getHtmlForWebview(mockWebview);
      formatTemplateLabel = extractFormatTemplateLabel(html);
    });

    it('converts a hyphenated template id into a sentence-cased display name', () => {
      expect(formatTemplateLabel('calculator-step')).to.equal('Calculator step');
    });

    it('converts an underscored template id into a sentence-cased display name', () => {
      expect(formatTemplateLabel('custom_step')).to.equal('Custom step');
    });

    it('normalizes mixed-case template ids', () => {
      expect(formatTemplateLabel('MULTI-word_TEMPLATE')).to.equal('Multi word template');
    });

    it('handles a single-word template id', () => {
      expect(formatTemplateLabel('stepname')).to.equal('Stepname');
    });

    it('collapses repeated separators', () => {
      expect(formatTemplateLabel('calculator--step__extra')).to.equal('Calculator step extra');
    });
  });

  describe('getHtmlForWebview', () => {
    it('renders the step template select element', () => {
      const html = provider.getHtmlForWebview(mockWebview);
      expect(html).to.include('id="step-template"');
      expect(html).to.include('Select template...');
    });
  });

  describe('load-templates message handling', () => {
    it('posts the raw (unformatted) template identifiers to the webview', async () => {
      const getStepTemplatesStub = sinon.stub(solutionService, 'getStepTemplates').resolves(['calculator-step', 'custom_step']);

      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await messageHandler?.({ command: 'load-templates' });

      expect(getStepTemplatesStub.calledOnce).to.be.true;
      expect((mockWebview.postMessage as sinon.SinonStub).calledWithMatch({
        type: 'templates-loaded',
        templates: ['calculator-step', 'custom_step']
      })).to.be.true;
    });

    it('falls back to the default template when loading fails', async () => {
      sinon.stub(solutionService, 'getStepTemplates').rejects(new Error('CLI unavailable'));

      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await messageHandler?.({ command: 'load-templates' });

      expect((mockWebview.postMessage as sinon.SinonStub).calledWithMatch({
        type: 'templates-loaded',
        templates: ['calculator-step']
      })).to.be.true;
    });
  });
});
