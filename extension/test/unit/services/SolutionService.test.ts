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
import * as path from 'node:path';
import { SolutionService } from '../../../src/services/SolutionService';
import { SystemService } from '../../../src/services/SystemService';
import { StepManagement } from '../../../src/services/StepManagement';
import { StorageService } from '../../../src/services/StorageService';
import { SAFSolutionsProvider } from '../../../src/providers/SAFSolutionsProvider';
import {
  SolutionConfig,
  StepConfig
} from '../../../src/types/solution';

/**
 * Unit tests for SolutionService class
 */
describe('SolutionService', () => {
  let solutionService: SolutionService;
  let systemServiceStub: sinon.SinonStubbedInstance<SystemService>;
  let stepManagementStub: sinon.SinonStubbedInstance<StepManagement>;
  let storageServiceStub: sinon.SinonStub;
  let processChdirStub: sinon.SinonStub;
  let safSolutionsProviderStub: sinon.SinonStub;
  let mockProvider: sinon.SinonStubbedInstance<SAFSolutionsProvider>;

  beforeEach(() => {
    systemServiceStub = sinon.createStubInstance(SystemService);
    stepManagementStub = sinon.createStubInstance(StepManagement);

    storageServiceStub = sinon.stub(StorageService, 'getSafCliInfo');

    processChdirStub = sinon.stub(process, 'chdir');

    mockProvider = sinon.createStubInstance(SAFSolutionsProvider);
    mockProvider.getSAFSolutions.resolves([{ rootDirectory: '/test/solution/path', name: 'test_solution', displayName: 'Test Solution' }]);

    sinon.stub(SAFSolutionsProvider, 'getInstance').returns(mockProvider);

    solutionService = new SolutionService();

    solutionService.setSystemService(systemServiceStub);
    solutionService.setStepManager(stepManagementStub);
  });

  afterEach(() => {
    sinon.restore();
  });

  describe('createSolution', () => {
    const mockConfig: SolutionConfig = {
      name: 'test-solution',
      displayName: 'Test Solution',
      uiType: 'dash',
      namespace: 'saf.solutions',
      targetDirectory: '/test/directory'
    };

    const mockExecutable = {
      executablePath: '/test/venv/bin/saf',
      version: '1.0.0'
    };

    beforeEach(() => {
      storageServiceStub.returns(mockExecutable);
      systemServiceStub.executeCommand.resolves('Success');
    });

    ['dash', 'none'].forEach((uiFramework) => {
      it('should create a solution with correct command using ' + uiFramework + ' framework', async () => {
        const config = { ...mockConfig, uiType: uiFramework };

        await solutionService.createSolution(config);

        expect(processChdirStub.calledWith(config.targetDirectory)).to.be.true;
        expect(storageServiceStub.calledOnce).to.be.true;

        const expectedExecutable = sinon.match((exe: unknown) => {
          return typeof exe === 'string' && exe.toLowerCase().includes('saf');
        });
        const expectedArgs = ['new', '--solution-name', config.name, '--solution-display-name', config.displayName, '--ui-framework', uiFramework];
        expect(systemServiceStub.executeCommand.calledWith(
          expectedExecutable,
          sinon.match((args: string[]) => expectedArgs.every(p => args.includes(p))),
          { cwd: config.targetDirectory }
        )).to.be.true;
      });
    });

    it('should change directory to target directory', async () => {
      await solutionService.createSolution(mockConfig);

      expect(processChdirStub.calledWith(mockConfig.targetDirectory)).to.be.true;
    });

    it('should throw error if StorageService fails', async () => {
      storageServiceStub.returns(null);

      try {
        await solutionService.createSolution(mockConfig);
        expect.fail('Should have thrown an error');
      } catch (error: any) {
        expect(error.message).to.include('Failed to create solution using SAF CLI');
        expect(error.message).to.include('SAF CLI is not installed. Please install SAF CLI to proceed.');
      }
    });

    it('should throw error if command execution fails', async () => {
      systemServiceStub.executeCommand.rejects(new Error('Command failed'));

      try {
        await solutionService.createSolution(mockConfig);
        expect.fail('Should have thrown an error');
      } catch (error: any) {
        expect(error.message).to.include('Failed to create solution using SAF CLI');
        expect(error.message).to.include('Command failed');
      }
    });
  });

  describe('addStep', () => {
    const mockConfig: StepConfig = {
      solutionPath: '/test/solution/path',
      name: 'test_step',
      displayName: 'Test Step',
      createPage: true,
      uiFramework: 'dash',
      template: 'calculator-step'
    };

    const mockExecutable = {
      executablePath: '/test/venv/bin/saf',
      version: '1.0.0'
    };

    const mockSolutionName = 'test_solution';

    beforeEach(() => {
      storageServiceStub.returns(mockExecutable);
      systemServiceStub.executeCommand.resolves('Success');
    });

    ['dash', 'none'].forEach((uiFramework) => {
      it('should add step with correct command using ' + uiFramework + ' framework', async () => {
        const config = { ...mockConfig, uiFramework };

        await solutionService.addStep(config);

        expect(mockProvider.getSAFSolutions.calledOnce).to.be.true;
        expect(storageServiceStub.calledOnce).to.be.true;

        const expectedExecutable = sinon.match((exe: unknown) => {
          return typeof exe === 'string' && exe.toLowerCase().includes('saf');
        });
        const expectedArgs = [
          'add-step',
          mockSolutionName,
          '--step-name',
          config.name,
          '--ui-framework',
          uiFramework,
          '--template',
          'calculator-step'
        ];
        expect(systemServiceStub.executeCommand.calledWith(
          expectedExecutable,
          sinon.match((args: string[]) => expectedArgs.every(p => args.includes(p))),
          { cwd: config.solutionPath }
        )).to.be.true;
      });
    });

    it('should default to calculator-step when no template is provided', async () => {
      const config = { ...mockConfig, template: undefined } as StepConfig;

      await solutionService.addStep(config);

      expect(systemServiceStub.executeCommand.calledWith(
        sinon.match((exe: unknown) => typeof exe === 'string' && exe.toLowerCase().includes('saf')),
        sinon.match((args: string[]) => args.includes('--template') && args.includes('calculator-step')),
        { cwd: config.solutionPath }
      )).to.be.true;
    });

    it('should throw error if solution name cannot be found', async () => {
      mockProvider.getSAFSolutions.resolves([]);

      try {
        await solutionService.addStep(mockConfig);
        expect.fail('Should have thrown an error');
      } catch (error: any) {
        expect(error.message).to.include('Failed to add step');
        expect(error.message).to.include('Solution not found for the given path');
      }
    });

    it('should throw error if StorageService fails', async () => {
      storageServiceStub.returns(null);

      try {
        await solutionService.addStep(mockConfig);
        expect.fail('Should have thrown an error');
      } catch (error: any) {
        expect(error.message).to.include('Failed to add step');
        expect(error.message).to.include('SAF CLI is not installed. Please install SAF CLI to proceed.');
      }
    });

    it('should throw error if command execution fails', async () => {
      systemServiceStub.executeCommand.rejects(new Error('Command failed'));

      try {
        await solutionService.addStep(mockConfig);
        expect.fail('Should have thrown an error');
      } catch (error: any) {
        expect(error.message).to.include('Failed to add step');
        expect(error.message).to.include('Command failed');
      }
    });
  });

  describe('getStepTemplates', () => {
    beforeEach(() => {
      storageServiceStub.returns({
        executablePath: '/test/venv/bin/saf',
        version: '1.0.0'
      });
    });

    it('should parse available step templates from CLI output', async () => {
      systemServiceStub.executeCommand.resolves('calculator-step\ncustom-template-step\nnot-a-template\n');

      const templates = await solutionService.getStepTemplates();

      expect(templates).to.deep.equal(['calculator-step', 'custom-template-step']);
    });

    it('should fall back to calculator-step when the CLI output is empty or invalid', async () => {
      systemServiceStub.executeCommand.resolves('');

      const templates = await solutionService.getStepTemplates();

      expect(templates).to.deep.equal(['calculator-step']);
    });
  });

  describe('getStepFiles', () => {
    const solutionPath = '/test/solution/path';
    const mockSolutionName = 'test_solution';

    beforeEach(() => {
      stepManagementStub.findSolutionDir.resolves(mockSolutionName);
    });

    describe('step name normalization', () => {
      const testCases = [
        {
          description: 'step name already ends with _step',
          stepName: 'test_step',
          expectedStepFile: 'test_step.py',
          expectedPageFile: 'test_page.py'
        },
        {
          description: 'step name does not end with _step',
          stepName: 'my_feature',
          expectedStepFile: 'my_feature_step.py',
          expectedPageFile: 'my_feature_page.py'
        },
        {
          description: 'simple step name',
          stepName: 'analysis',
          expectedStepFile: 'analysis_step.py',
          expectedPageFile: 'analysis_page.py'
        },
        {
          description: 'step name without underscore ending in "step"',
          stepName: 'mystep',
          expectedStepFile: 'mystep.py',
          expectedPageFile: 'mystep_page.py'
        },
        {
          description: 'step name with uppercase letters',
          stepName: 'MyStep',
          expectedStepFile: 'mystep.py',
          expectedPageFile: 'mystep_page.py'
        }
      ];

      testCases.forEach(({ description, stepName, expectedStepFile, expectedPageFile }) => {
        describe(`when ${description}`, () => {
          it('should return only step file when createPage is false', async () => {
            const files = await solutionService.getStepFiles(solutionPath, stepName, false);

            expect(files).to.have.lengthOf(1);
            expect(files[0]).to.equal(
              path.join(
                solutionPath,
                'src',
                mockSolutionName,
                'solution',
                expectedStepFile
              )
            );
          });

          it('should return both step and page files when createPage is true', async () => {
            const files = await solutionService.getStepFiles(solutionPath, stepName, true);

            expect(files).to.have.lengthOf(2);
            expect(files[0]).to.equal(
              path.join(
                solutionPath,
                'src',
                mockSolutionName,
                'solution',
                expectedStepFile
              )
            );
            expect(files[1]).to.equal(
              path.join(
                solutionPath,
                'src',
                mockSolutionName,
                'ui',
                'pages',
                expectedPageFile
              )
            );
          });
        });
      });
    });

    it('should use path separator correctly', async () => {
      const files = await solutionService.getStepFiles(solutionPath, 'test_step', true);

      files.forEach(file => {
        expect(file).to.be.a('string');
        expect(file).to.not.include(path.sep + path.sep);
      });
    });

    it('should call findSolutionDir to get solution name', async () => {
      await solutionService.getStepFiles(solutionPath, 'test_step', false);

      expect(stepManagementStub.findSolutionDir.calledOnce).to.be.true;
      expect(stepManagementStub.findSolutionDir.calledWith(solutionPath)).to.be.true;
    });

    it('should propagate error if findSolutionDir fails', async () => {
      stepManagementStub.findSolutionDir.rejects(new Error('Solution directory not found'));

      try {
        await solutionService.getStepFiles(solutionPath, 'test_step', false);
        expect.fail('Should have thrown an error');
      } catch (error: any) {
        expect(error.message).to.equal('Solution directory not found');
      }
    });

    it('should build step and page paths for legacy package path', async () => {
      const solutionPackagePath = path.join('ansys', 'solutions', 'test_solution');
      stepManagementStub.findSolutionDir.resolves(solutionPackagePath);
      const files = await solutionService.getStepFiles(solutionPath, 'test_step', true);
      expect(files).to.have.lengthOf(2);
      expect(files[0]).to.equal(
        path.join(solutionPath, 'src', solutionPackagePath, 'solution', 'test_step.py')
      );
      expect(files[1]).to.equal(
        path.join(solutionPath, 'src', solutionPackagePath, 'ui', 'pages', 'test_page.py')
      );

    });

    it('should build step and page paths for custom namespace package path', async () => {
      const solutionPackagePath = path.join('my_team', 'platform', 'test_solution');
      stepManagementStub.findSolutionDir.resolves(solutionPackagePath);
      const files = await solutionService.getStepFiles(solutionPath, 'test_step', true);
      expect(files).to.have.lengthOf(2);
      expect(files[0]).to.equal(
        path.join(solutionPath, 'src', solutionPackagePath, 'solution', 'test_step.py')
      );
      expect(files[1]).to.equal(
        path.join(solutionPath, 'src', solutionPackagePath, 'ui', 'pages', 'test_page.py')
      );
    });
  });
});