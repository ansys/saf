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
import * as fs from 'node:fs';
import * as path from 'node:path';
import { AddStepViewProvider } from '../../../src/providers/AddStepViewProvider';
import { CreateSolutionViewProvider } from '../../../src/providers/CreateSolutionViewProvider';
import { SAFSolutionsProvider } from '../../../src/providers/SAFSolutionsProvider';
import { solutionService } from '../../../src/services/SolutionService';

// Helper to generate a short, unique, dash-free string for test step names
function randomString(length = 10): string {
  // crypto.randomUUID() may contain dashes, so replace them with underscores
  return crypto.randomUUID().replace(/-/g, '_').substring(0, length);
}
import {
  createTempTestDir,
  generateUniqueSolutionName,
  mockExtensionContext,
  mochaGlobalSetup as integrationSetup,
  mochaGlobalTeardown as integrationTeardown,
  generateUniqueNamespace
} from '../setup.integration';
import { createTestSolution, createSolutionVenvWithPoetry } from '../testHelpers';

export const mochaHooks = {
  beforeAll: integrationSetup,
  afterAll: integrationTeardown
};

// A non-default step template used to verify that selecting anything other than
// the default (first) template actually results in the corresponding template's
// content being applied. Unlike calculator-step, this template declares extra
// dependencies, so it requires the solution's own Poetry environment to be
// installed (see the 'Non-default Template Selection' describe block below).
const NON_DEFAULT_TEMPLATE = 'hps-simple-job-step';

describe('AddStepViewProvider Integration Tests', () => {
  let messageHandler: ((message: any) => Promise<void>) | undefined;
  let sharedSolutionName: string;
  let sharedSolutionPath: string;
  let sharedTempDir: string;

  function createMockWebviewView(): vscode.WebviewView {
    const mockWebview = {
      html: '',
      options: {},
      onDidReceiveMessage: sinon.stub().callsFake((handler) => {
        messageHandler = handler;
        return { dispose: sinon.stub() };
      }),
      postMessage: sinon.stub().resolves(true),
      asWebviewUri: sinon.stub().callsFake((uri) => uri),
      cspSource: 'mock-csp-source'
    };

    return {
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
  }

  before(async function () {
    this.timeout(30000);

    sharedTempDir = createTempTestDir();
    sharedSolutionName = generateUniqueSolutionName('addstep-shared');
    const displayName = `AddStep Shared ${sharedSolutionName}`;
    const namespace = generateUniqueNamespace();
    const createProvider = new CreateSolutionViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
    const mockWebviewView = createMockWebviewView();

    const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage')
      .resolves('Don\'t open' as any);

    createProvider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

    await messageHandler?.({
      command: 'create-solution',
      config: {
        name: sharedSolutionName,
        displayName,
        uiType: 'dash',
        namespace,
        targetDirectory: sharedTempDir
      }
    });

    sharedSolutionPath = path.join(sharedTempDir, sharedSolutionName);

    showInformationMessageStub.restore();
    messageHandler = undefined;

    const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();
    const createdSolution = solutions.find(solution => solution.name === sharedSolutionName);
    expect(createdSolution, 'Shared solution should be created for AddStep tests').to.not.be.undefined;
  });

  beforeEach(() => {
    messageHandler = undefined;
  });

  afterEach(() => {
    sinon.restore();
  });

  describe('Step Creation', () => {
    const stepCases = [
      { label: 'my_step' },
      { label: 'mystep' },
      { label: 'analysis_result' }
    ];

    const uiFrameworks = ['dash', 'none'] as const;

    stepCases.forEach(({ label }) => {
      uiFrameworks.forEach((uiFramework) => {
        it(`creates a step for ${label} with ${uiFramework} UI`, async function () {
          this.timeout(15000);
          const stepName = `${randomString()}_${label}`;
          const provider = new AddStepViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
          const mockWebviewView = createMockWebviewView();

          const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage').resolves();
          const withProgressStub = sinon.stub(vscode.window, 'withProgress');
          withProgressStub.callsFake(async (_options, task) => {
            return await task({ report: () => {} }, {} as any);
          });

          provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

          await messageHandler?.({
            command: 'add-step',
            solutionName: sharedSolutionName,
            stepName,
            uiFramework,
            template: 'calculator-step'
          });

          const stepFiles = await solutionService.getStepFiles(sharedSolutionPath, stepName, uiFramework !== 'none');
          const stepFilePath = stepFiles[0];
          const pageFilePath = stepFiles[1];

          expect(fs.existsSync(stepFilePath)).to.equal(true, `Step file should exist: ${stepFilePath}`);
          if (uiFramework !== 'none') {
            expect(pageFilePath).to.exist;
            expect(fs.existsSync(pageFilePath!)).to.equal(true, `Page file should exist: ${pageFilePath}`);
          } else {
            expect(pageFilePath).to.be.undefined;
          }
          expect(showInformationMessageStub.calledOnce).to.be.true;
          expect(showInformationMessageStub.firstCall.args[0]).to.include(`Step ${stepName} created successfully`);
        });
      });
    });
  });

  describe('File Opening After Creation', () => {
    const testCases = [
      { description: 'step name without _step suffix (analysis_result)', stepNameSuffix: 'analysis_result' },
      { description: 'step name ending in _step (no double suffix)', stepNameSuffix: 'my_step' },
      { description: 'step name without underscore ending in "step"', stepNameSuffix: 'mystep' },
      { description: 'step name with uppercase letters', stepNameSuffix: 'MyStep' }
    ];

    testCases.forEach(({ description, stepNameSuffix }) => {
      it(`opens step and page files when solution is open in workspace (${description})`, async function () {
        this.timeout(15000);
        const stepName = `${randomString()}_${stepNameSuffix}`;
        const provider = new AddStepViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
        const mockWebviewView = createMockWebviewView();

        sinon.stub(provider as any, 'isSolutionOpenInWorkspace').returns(true);
        const openTextDocumentStub = sinon.stub(vscode.workspace, 'openTextDocument').resolves({} as any);
        const showTextDocumentStub = sinon.stub(vscode.window, 'showTextDocument').resolves({} as any);
        const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage').resolves();
        const withProgressStub = sinon.stub(vscode.window, 'withProgress');
        withProgressStub.callsFake(async (_options, task) => {
          return await task({ report: () => {} }, {} as any);
        });

        provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

        await messageHandler?.({
          command: 'add-step',
          solutionName: sharedSolutionName,
          stepName,
          uiFramework: 'dash',
          template: 'calculator-step'
        });

        const stepFiles = await solutionService.getStepFiles(sharedSolutionPath, stepName, true);
        const stepFilePath = stepFiles[0];
        const pageFilePath = stepFiles[1];

        expect(fs.existsSync(stepFilePath)).to.equal(true, `Step file should exist: ${stepFilePath}`);
        expect(fs.existsSync(pageFilePath)).to.equal(true, `Page file should exist: ${pageFilePath}`);

        expect(openTextDocumentStub.callCount).to.equal(2, 'Should open both step and page files');
        expect(openTextDocumentStub.firstCall.args[0]).to.equal(stepFilePath);
        expect(openTextDocumentStub.secondCall.args[0]).to.equal(pageFilePath);

        expect(showTextDocumentStub.callCount).to.equal(2, 'Should show both step and page documents');
        expect(showInformationMessageStub.calledOnce).to.be.true;
      });
    });
  });

  describe('Template Selection', () => {
    it('loads templates and uses the first template by default', async function () {
      const provider = new AddStepViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
      const mockWebviewView = createMockWebviewView();

      const postMessageStub = mockWebviewView.webview.postMessage as sinon.SinonStub;
      const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage').resolves();
      const withProgressStub = sinon.stub(vscode.window, 'withProgress');
      withProgressStub.callsFake(async (_options, task) => {
        return await task({ report: () => {} }, {} as any);
      });

      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await messageHandler?.({
        command: 'load-templates'
      });

      const templatesLoadedCall = postMessageStub.getCalls()
        .find(call => call.args[0]?.type === 'templates-loaded');
      expect(templatesLoadedCall, 'templates-loaded message should be posted').to.not.be.undefined;
      expect(templatesLoadedCall!.args[0].templates).to.be.an('array').that.includes('calculator-step');

      // Templates are posted as raw CLI identifiers (e.g. "calculator-step"); the
      // webview is responsible for deriving a human-readable display label from
      // these values, so the extension side must never send pre-formatted labels.
      (templatesLoadedCall!.args[0].templates as string[]).forEach(tpl => {
        expect(tpl).to.match(/^[a-z0-9]+([-_][a-z0-9]+)*$/, `template "${tpl}" should be a raw lowercase CLI identifier`);
      });

      const templateMessage = {
        command: 'add-step',
        solutionName: sharedSolutionName,
        stepName: `${randomString()}_template_step`,
        uiFramework: 'dash',
        template: 'calculator-step'
      };

      await messageHandler?.(templateMessage);
      expect(showInformationMessageStub.calledWithMatch(sinon.match(/template: calculator-step/))).to.be.true;
    });

    it(`includes the non-default template "${NON_DEFAULT_TEMPLATE}" among the loaded templates`, async function () {
      const provider = new AddStepViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
      const mockWebviewView = createMockWebviewView();
      const postMessageStub = mockWebviewView.webview.postMessage as sinon.SinonStub;

      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await messageHandler?.({
        command: 'load-templates'
      });

      const templatesLoadedCall = postMessageStub.getCalls()
        .find(call => call.args[0]?.type === 'templates-loaded');
      expect(templatesLoadedCall, 'templates-loaded message should be posted').to.not.be.undefined;

      const templates = templatesLoadedCall!.args[0].templates as string[];
      expect(templates.length).to.be.greaterThan(1, 'Expected more than one template to be available for selection');

      const defaultTemplate = templates[0];
      const nonDefaultTemplates = templates.filter(tpl => tpl !== defaultTemplate);
      expect(nonDefaultTemplates.length).to.be.greaterThan(0, 'Expected at least one non-default template option');
      expect(nonDefaultTemplates).to.include(NON_DEFAULT_TEMPLATE);
    });
  });

  describe('Step Creation Using a Non-Default Template', () => {
    let nonDefaultSolutionName: string;
    let nonDefaultSolutionPath: string;

    before(async function () {
      this.timeout(120000);

      const { solutionName, createdSolutionPath } = await createTestSolution(
        'addstep-nondefault',
        'AddStep Non-default Template'
      );
      nonDefaultSolutionName = solutionName;
      nonDefaultSolutionPath = createdSolutionPath;

      // Non-default templates (anything other than calculator-step) declare extra
      // dependencies, and `saf add-step` requires a `poetry` executable to already
      // be present in the solution's own `.venv` to install them. Running the full
      // `saf install` here would also install unrelated desktop/ui/doc/build
      // dependency groups, adding several minutes for no benefit to this test, so
      // just create a bare venv with Poetry instead; `saf add-step` installs the
      // template's actual dependencies itself via `poetry lock`/`poetry install`.
      await createSolutionVenvWithPoetry(nonDefaultSolutionPath);
    });

    it(`creates a step using the template "${NON_DEFAULT_TEMPLATE}" and generates its expected file content`, async function () {
      // `saf add-step` installs the template's dependencies (main + template-specific
      // group) via Poetry on first use here. This is usually fast (a couple seconds)
      // when Poetry/pip's local package cache is already warm, but a cold cache (e.g.
      // a fresh CI runner) requires downloading those packages over the network, so
      // allow generous headroom for that case.
      this.timeout(180000);
      const stepName = `${randomString()}_hps_step`;
      const provider = new AddStepViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
      const mockWebviewView = createMockWebviewView();

      const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage').resolves();
      const withProgressStub = sinon.stub(vscode.window, 'withProgress');
      withProgressStub.callsFake(async (_options, task) => {
        return await task({ report: () => {} }, {} as any);
      });

      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await messageHandler?.({
        command: 'add-step',
        solutionName: nonDefaultSolutionName,
        stepName,
        uiFramework: 'none',
        template: NON_DEFAULT_TEMPLATE
      });

      const stepFiles = await solutionService.getStepFiles(nonDefaultSolutionPath, stepName, false);
      const stepFilePath = stepFiles[0];

      expect(fs.existsSync(stepFilePath)).to.equal(true, `Step file should exist: ${stepFilePath}`);

      const stepFileContent = fs.readFileSync(stepFilePath, 'utf-8');
      // The hps-simple-job-step template generates a step backed by an HPS project.
      // This content is distinct from the default calculator-step template and
      // confirms that the *selected* (non-default) template was actually applied,
      // rather than the extension silently falling back to the default one.
      expect(stepFileContent).to.include('from ansys.saf.glow.solution.hps import');
      expect(stepFileContent).to.include('HpsSimpleProject');
      expect(stepFileContent).to.not.include('def calculate(self)');

      expect(showInformationMessageStub.calledOnce).to.be.true;
      expect(showInformationMessageStub.firstCall.args[0]).to.include(`Step ${stepName} created successfully`);
      expect(showInformationMessageStub.firstCall.args[0]).to.include(`template: ${NON_DEFAULT_TEMPLATE}`);
    });
  });

  describe('Edge Cases - Missing Required Fields', () => {
    it('rejects missing solutionName', async function () {
      const stepName = `${randomString()}_test_step`;
      const provider = new AddStepViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
      const mockWebviewView = createMockWebviewView();

      const showErrorMessageStub = sinon.stub(vscode.window, 'showErrorMessage').resolves();
      const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage').resolves();

      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await messageHandler?.({
        command: 'add-step',
        solutionName: undefined,
        stepName,
        uiFramework: 'dash',
        template: 'calculator-step'
      });

      expect(showErrorMessageStub.calledOnce).to.be.true;
      expect(showErrorMessageStub.firstCall.args[0]).to.equal('Please fill out all fields before adding a step.');
      expect(showInformationMessageStub.called).to.be.false;

      const expectedStepFiles = await solutionService.getStepFiles(sharedSolutionPath, stepName, true);
      expect(fs.existsSync(expectedStepFiles[0])).to.equal(false, 'No step files should be created');
    });

    it('rejects missing stepName', async function () {
      const provider = new AddStepViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
      const mockWebviewView = createMockWebviewView();

      const showErrorMessageStub = sinon.stub(vscode.window, 'showErrorMessage').resolves();
      const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage').resolves();

      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await messageHandler?.({
        command: 'add-step',
        solutionName: sharedSolutionName,
        stepName: undefined,
        uiFramework: 'dash',
        template: 'calculator-step'
      });

      expect(showErrorMessageStub.calledOnce).to.be.true;
      expect(showErrorMessageStub.firstCall.args[0]).to.equal('Please fill out all fields before adding a step.');
      expect(showInformationMessageStub.called).to.be.false;
    });

    it('rejects missing uiFramework', async function () {
      const stepName = `${randomString()}_test_step`;
      const provider = new AddStepViewProvider(vscode.Uri.file(mockExtensionContext.extensionPath));
      const mockWebviewView = createMockWebviewView();

      const showErrorMessageStub = sinon.stub(vscode.window, 'showErrorMessage').resolves();
      const showInformationMessageStub = sinon.stub(vscode.window, 'showInformationMessage').resolves();

      provider.resolveWebviewView(mockWebviewView, {} as any, {} as any);

      await messageHandler?.({
        command: 'add-step',
        solutionName: sharedSolutionName,
        stepName,
        uiFramework: undefined,
        template: 'calculator-step'
      });

      expect(showErrorMessageStub.calledOnce).to.be.true;
      expect(showErrorMessageStub.firstCall.args[0]).to.equal('Please fill out all fields before adding a step.');
      expect(showInformationMessageStub.called).to.be.false;

      const expectedStepFiles = await solutionService.getStepFiles(sharedSolutionPath, stepName, true);
      expect(fs.existsSync(expectedStepFiles[0])).to.equal(false, 'No step files should be created');
    });
  });
});
