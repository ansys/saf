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
import { ConfigurationPanel } from '../../../src/services/ConfigurationPanel';
import { MockExtensionContext } from '../../mocks/vscode.mock';
import { expectedEnvironmentVariables } from '../../fixtures/environmentVariables';
import { EnvironmentService } from '../../../src/services/EnvironmentService';

describe('ConfigurationPanel', () => {
    let panel: ConfigurationPanel;
    let mockContext: MockExtensionContext;
    let environmentService: EnvironmentService;
    let loadForSolutionSpy: sinon.SinonSpy;

    beforeEach(() => {
        mockContext = new MockExtensionContext();
        environmentService = new EnvironmentService(mockContext as any);

        loadForSolutionSpy = sinon.spy(environmentService, 'loadForSolution');

        panel = new ConfigurationPanel(mockContext as any, environmentService);
    });

    afterEach(() => {
        sinon.restore();
    });

    describe('constructor', () => {
        it('should initialize with environment service', () => {
            const variables = panel.getEnvironmentVariables();
            expect(variables).to.deep.equal(expectedEnvironmentVariables);
        });
    });

    describe('show()', () => {
        it('should load environment variables for the specified solution', async () => {
            await panel.show('my-solution', '/path/to/my-solution');

            expect(loadForSolutionSpy.calledOnce).to.be.true;
            expect(loadForSolutionSpy.firstCall.args[0]).to.equal('/path/to/my-solution');
        });

        it('should show warning when solution name is missing', async () => {
            await panel.show('', '/path/to/solution');

            expect((vscode.window.showWarningMessage as sinon.SinonStub).calledWith(
                'Please select a valid solution to configure its environment.'
            )).to.be.true;
            expect(loadForSolutionSpy.called).to.be.false;
        });

        it('should show warning when solution path is missing', async () => {
            await panel.show('my-solution', '');

            expect((vscode.window.showWarningMessage as sinon.SinonStub).calledWith(
                'Please select a valid solution to configure its environment.'
            )).to.be.true;
            expect(loadForSolutionSpy.called).to.be.false;
        });

        it('should create webview panel with solution name in title', async () => {
            await panel.show('my-solution', '/path/to/my-solution');

            expect((vscode.window.createWebviewPanel as sinon.SinonStub).calledWith(
                'safEnvironmentConfig',
                'Configure my-solution environment',
                sinon.match.any,
                sinon.match.any
            )).to.be.true;
        });

        it('should update panel title when showing different solution', async () => {
            // Show first solution
            await panel.show('solution-a', '/path/to/solution-a');

            // Get the mock panel that was created
            const mockPanel = (vscode.window.createWebviewPanel as sinon.SinonStub).returnValues[0];

            // Show second solution
            await panel.show('solution-b', '/path/to/solution-b');

            // Panel title should be updated
            expect(mockPanel.title).to.equal('Configure solution-b environment');
        });
    });
});
