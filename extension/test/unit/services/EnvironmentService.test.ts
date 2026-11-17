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
import { EnvironmentService } from '../../../src/services/EnvironmentService';
import { ENVIRONMENT_VARIABLE_DEFINITIONS } from '../../../src/services/environmentVariables';
import { MockExtensionContext } from '../../mocks/vscode.mock';

describe('EnvironmentService', () => {
    let service: EnvironmentService;
    let mockContext: MockExtensionContext;

    beforeEach(() => {
        mockContext = new MockExtensionContext();
        service = new EnvironmentService(mockContext as any);
    });

    afterEach(() => {
        sinon.restore();
    });

    describe('project migration variable', () => {
        it('should define GLOW_ENABLE_AUTOMATIC_PROJECT_MIGRATION disabled by default', () => {
            const definition = ENVIRONMENT_VARIABLE_DEFINITIONS.find(
                d => d.name === 'GLOW_ENABLE_AUTOMATIC_PROJECT_MIGRATION'
            );

            expect(definition).to.not.be.undefined;
            expect(definition?.defaultValue).to.equal(false);
            expect(definition?.category).to.equal('Project Migration');
        });

        it('should not define the legacy GLOW_ENABLE_PROJECT_MIGRATION variable', () => {
            const names = ENVIRONMENT_VARIABLE_DEFINITIONS.map(d => d.name);

            expect(names).to.not.include('GLOW_ENABLE_PROJECT_MIGRATION');
        });

        it('should ignore a value saved under the legacy name', async () => {
            mockContext.workspaceState.get.returns([
                { name: 'GLOW_ENABLE_PROJECT_MIGRATION', enabled: true, value: true }
            ]);

            await service.loadForSolution('/test/solution');

            const variables = service.getVariables();
            expect(variables.find(v => v.name === 'GLOW_ENABLE_PROJECT_MIGRATION')).to.be.undefined;
            const renamed = variables.find(v => v.name === 'GLOW_ENABLE_AUTOMATIC_PROJECT_MIGRATION');
            expect(renamed?.enabled).to.be.false;
            expect(renamed?.value).to.equal(false);
        });
    });

    describe('getStorageKey', () => {
        it('should normalize paths for consistent storage keys', async () => {
            const solutionPath1 = 'C:\\Users\\test\\my-solution';
            const solutionPath2 = 'c:\\users\\test\\my-solution';

            // Both paths should produce the same normalized key
            mockContext.workspaceState.get.returns(undefined);

            await service.loadForSolution(solutionPath1);
            const firstCallKey = mockContext.workspaceState.get.firstCall.args[0];

            await service.loadForSolution(solutionPath2);
            const secondCallKey = mockContext.workspaceState.get.secondCall.args[0];

            expect(firstCallKey).to.equal(secondCallKey);
        });

        it('should use forward slashes in storage key', async () => {
            const solutionPath = 'C:\\Users\\test\\my-solution';
            mockContext.workspaceState.get.returns(undefined);

            await service.loadForSolution(solutionPath);

            const storageKey = mockContext.workspaceState.get.firstCall.args[0];
            expect(storageKey).to.not.include('\\');
            expect(storageKey).to.include('/');
        });
    });

    describe('loadForSolution', () => {
        it('should load variables from workspace state', async () => {
            const storedVariables = [
                { name: 'GLOW_API_PORT', enabled: true, value: '9999', defaultValue: '5432', description: '', category: 'API server' }
            ];
            mockContext.workspaceState.get.returns(storedVariables);

            await service.loadForSolution('/test/solution');

            const variables = service.getVariables();
            const apiPortVar = variables.find(v => v.name === 'GLOW_API_PORT');

            expect(apiPortVar).to.not.be.undefined;
            expect(apiPortVar?.enabled).to.be.true;
            expect(apiPortVar?.value).to.equal('9999');
        });

        it('should use defaults when no stored variables exist', async () => {
            mockContext.workspaceState.get.returns(undefined);

            await service.loadForSolution('/test/solution');

            const variables = service.getVariables();
            const apiPortVar = variables.find(v => v.name === 'GLOW_API_PORT');
            expect(apiPortVar?.enabled).to.be.false;
            expect(apiPortVar?.value).to.equal('5432'); // default value
        });

        it('should throw error when solution path is empty', async () => {
            try {
                await service.loadForSolution('');
                expect.fail('Should have thrown an error');
            } catch (error) {
                expect((error as Error).message).to.equal('Solution path is required');
            }
        });

        it('should merge stored variables with current definitions', async () => {
            // Simulate stored variables with only some fields
            const storedVariables = [
                { name: 'GLOW_API_PORT', enabled: true, value: '8888' }
            ];
            mockContext.workspaceState.get.returns(storedVariables);

            await service.loadForSolution('/test/solution');

            const variables = service.getVariables();
            const apiPortVar = variables.find(v => v.name === 'GLOW_API_PORT');

            // Should have merged with definition metadata
            expect(apiPortVar?.enabled).to.be.true;
            expect(apiPortVar?.value).to.equal('8888');
            expect(apiPortVar?.category).to.equal('API server');
        });
    });

    describe('saveForSolution', () => {
        it('should save variables to workspace state', async () => {
            const variables = service.getVariables();
            const apiPortVar = variables.find(v => v.name === 'GLOW_API_PORT');
            if (apiPortVar) {
                apiPortVar.enabled = true;
                apiPortVar.value = '9999';
            }

            await service.saveForSolution('/test/solution');

            expect(mockContext.workspaceState.update.calledOnce).to.be.true;

            const savedKey = mockContext.workspaceState.update.firstCall.args[0];
            const savedVariables = mockContext.workspaceState.update.firstCall.args[1];

            expect(savedKey).to.include('environment.variables.');
            expect(savedVariables).to.be.an('array');

            const savedApiPort = savedVariables.find((v: any) => v.name === 'GLOW_API_PORT');
            expect(savedApiPort?.enabled).to.be.true;
            expect(savedApiPort?.value).to.equal('9999');
        });

        it('should throw error when solution path is empty', async () => {
            try {
                await service.saveForSolution('');
                expect.fail('Should have thrown an error');
            } catch (error) {
                expect((error as Error).message).to.equal('Solution path is required');
            }
        });

        it('should throw error when no context available', async () => {
            const serviceNoContext = new EnvironmentService();

            try {
                await serviceNoContext.saveForSolution('/test/solution');
                expect.fail('Should have thrown an error');
            } catch (error) {
                expect((error as Error).message).to.equal('Cannot save: No extension context available');
            }
        });
    });

    describe('getAsEnvironmentObject', () => {
        it('should return enabled variables as key-value pairs', async () => {
            const storedVariables = [
                { name: 'GLOW_API_PORT', enabled: true, value: '9999', defaultValue: '5432', description: '', category: 'API server' },
                { name: 'GLOW_API_HOST', enabled: true, value: 'localhost', defaultValue: '127.0.0.1', description: '', category: 'API server' },
                { name: 'GLOW_DEBUG', enabled: false, value: true, defaultValue: false, description: '', category: 'API server' }
            ];
            mockContext.workspaceState.get.returns(storedVariables);

            const envObject = await service.getAsEnvironmentObject('/test/solution');

            expect(envObject['GLOW_API_PORT']).to.equal('9999');
            expect(envObject['GLOW_API_HOST']).to.equal('localhost');
            expect(envObject['GLOW_DEBUG']).to.be.undefined; // disabled
        });

        it('should return empty object for empty solution path', async () => {
            const envObject = await service.getAsEnvironmentObject('');
            expect(envObject).to.deep.equal({});
        });

        it('should format boolean values as strings', async () => {
            const storedVariables = [
                { name: 'GLOW_DEBUG', enabled: true, value: true, defaultValue: false, description: '', category: 'API server' }
            ];
            mockContext.workspaceState.get.returns(storedVariables);

            const envObject = await service.getAsEnvironmentObject('/test/solution');

            expect(envObject['GLOW_DEBUG']).to.equal('true');
        });

        it('should reload if different solution path is requested', async () => {
            mockContext.workspaceState.get.returns([]);

            await service.getAsEnvironmentObject('/solution/a');
            await service.getAsEnvironmentObject('/solution/b');

            // Should have called get twice (once for each solution)
            expect(mockContext.workspaceState.get.callCount).to.equal(2);
        });
    });

    describe('setVariables', () => {
        it('should validate variables before setting', () => {
            const invalidVariables = [
                { name: '', enabled: true, value: 'test' }
            ];

            expect(() => service.setVariables(invalidVariables as any)).to.throw('Invalid variable: missing or invalid name');
        });

        it('should reject unknown variable names', () => {
            const unknownVariables = [
                { name: 'UNKNOWN_VAR', enabled: true, value: 'test', defaultValue: null, description: '', category: '' }
            ];

            expect(() => service.setVariables(unknownVariables as any)).to.throw('Unknown variable: UNKNOWN_VAR');
        });
    });

    describe('getVariableValue', () => {
        it('should return enabled variable value', async () => {
            const storedVariables = [
                { name: 'GLOW_API_PORT', enabled: true, value: '9999', defaultValue: '5432', description: '', category: 'API server' }
            ];
            mockContext.workspaceState.get.returns(storedVariables);

            await service.loadForSolution('/test/solution');
            const value = service.getVariableValue('GLOW_API_PORT');

            expect(value).to.equal('9999');
        });

        it('should return default value for disabled variable', async () => {
            const storedVariables = [
                { name: 'GLOW_API_PORT', enabled: false, value: '9999', defaultValue: '5432', description: '', category: 'API server' }
            ];
            mockContext.workspaceState.get.returns(storedVariables);

            await service.loadForSolution('/test/solution');
            const value = service.getVariableValue('GLOW_API_PORT');

            expect(value).to.equal('5432');
        });

        it('should return undefined for unknown variable', () => {
            const value = service.getVariableValue('UNKNOWN_VAR');
            expect(value).to.be.undefined;
        });
    });
});
