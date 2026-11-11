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
import { DependencyService } from '../../../src/services/DependencyService';
import { systemService } from '../../../src/services/SystemService';
import * as validation from '../../../src/utils/validation';

/**
 * Unit tests for DependencyService class
 */
describe('DependencyService', () => {
  let dependencyService: DependencyService;
  let executeCommandStub: sinon.SinonStub;
  let isValidVersionConstraintStub: sinon.SinonStub;
  let originalPlatform: string;

  beforeEach(() => {
    dependencyService = new DependencyService();

    executeCommandStub = sinon.stub(systemService, 'executeCommand');
    executeCommandStub.resolves('Success');
    isValidVersionConstraintStub = sinon.stub(validation, 'isValidVersionConstraint');

    originalPlatform = process.platform;
  });

  afterEach(() => {
    sinon.restore();
    Object.defineProperty(process, 'platform', { value: originalPlatform, writable: true });
  });

  describe('getDependencies', () => {
    const projectPath = '/test/project';

    it('should handle missing pyproject.toml', async () => {
      try {
        await dependencyService.getDependencies(projectPath);
        expect.fail('Should have thrown an error');
      } catch (error: any) {
        expect(error.message).to.include('Failed to read dependencies');
      }
    });
  });

  describe('addDependency', () => {
    const projectPath = '/test/project';
    const packageName = 'numpy';
    const packageVersion = '1.20.0';

    beforeEach(() => {
      isValidVersionConstraintStub.returns(true);
    });

    it('should add dependency to main group without version', async () => {
      await dependencyService.addDependency(projectPath, packageName, '');

      const expectedExecutable = sinon.match((exe: unknown) => {
        return typeof exe === 'string' && exe.toLowerCase().includes('poetry');
      });
      const expectedArgs = sinon.match((args: string[]) => {
        const required = ['add', packageName];
        const hasRequired = required.every(part => args.includes(part));
        const hasAtVersion = args.some(part => /@/.test(part));
        return hasRequired && !hasAtVersion;
      });

      expect(
        executeCommandStub.calledWith(expectedExecutable, expectedArgs, { cwd: projectPath })
      ).to.be.true;
    });

    it('should add dependency to main group with version', async () => {
      await dependencyService.addDependency(projectPath, packageName, packageVersion);

      const expectedExecutable = sinon.match((exe: unknown) => {
        return typeof exe === 'string' && exe.toLowerCase().includes('poetry');
      });
      const expectedArgs = sinon.match((args: string[]) => {
        return args.includes('add') && args.includes(`${packageName}@${packageVersion}`);
      });

      expect(
        executeCommandStub.calledWith(expectedExecutable, expectedArgs, { cwd: projectPath })
      ).to.be.true;
    });

    it('should add dependency to specific group', async () => {
      await dependencyService.addDependency(projectPath, packageName, packageVersion, 'dev');

      const expectedExecutable = sinon.match((exe: unknown) => {
        return typeof exe === 'string' && exe.toLowerCase().includes('poetry');
      });
      const expectedArgs = sinon.match((args: string[]) => {
        const required = ['add', `${packageName}@${packageVersion}`, '--group', 'dev'];
        return required.every(part => args.includes(part));
      });

      expect(
        executeCommandStub.calledWith(expectedExecutable, expectedArgs, { cwd: projectPath })
      ).to.be.true;
    });

    it('should validate version constraint', async () => {
      isValidVersionConstraintStub.returns(false);

      try {
        await dependencyService.addDependency(projectPath, packageName, 'invalid-version');
        expect.fail('Should have thrown an error');
      } catch (error: any) {
        expect(error.message).to.include('Invalid version constraint format');
        expect(error.message).to.include('invalid-version');
      }
    });

    it('should not validate if version is empty', async () => {
      await dependencyService.addDependency(projectPath, packageName, '');

      expect(isValidVersionConstraintStub.called).to.be.false;
      expect(executeCommandStub.calledOnce).to.be.true;
    });

    it('should throw error if poetry command fails', async () => {
      executeCommandStub.rejects(new Error('Poetry failed'));

      try {
        await dependencyService.addDependency(projectPath, packageName, packageVersion);
        expect.fail('Should have thrown an error');
      } catch (error: any) {
        expect(error.message).to.include('Failed to add dependency');
        expect(error.message).to.include('Poetry failed');
      }
    });
  });

  describe('removeDependency', () => {
    const projectPath = '/test/project';
    const packageName = 'numpy';

    it('should remove dependency from main group', async () => {
      await dependencyService.removeDependency(projectPath, packageName);

      const expectedExecutable = sinon.match((exe: unknown) => {
        return typeof exe === 'string' && exe.toLowerCase().includes('poetry');
      });
      const expectedArgs = sinon.match((args: string[]) => {
        const required = ['remove', packageName];
        const hasGroupFlag = args.includes('--group');
        return required.every(part => args.includes(part)) && !hasGroupFlag;
      });

      expect(
        executeCommandStub.calledWith(expectedExecutable, expectedArgs, { cwd: projectPath })
      ).to.be.true;
    });

    it('should remove dependency from specific group', async () => {
      await dependencyService.removeDependency(projectPath, packageName, 'dev');

      const expectedExecutable = sinon.match((exe: unknown) => {
        return typeof exe === 'string' && exe.toLowerCase().includes('poetry');
      });
      const expectedArgs = sinon.match((args: string[]) => {
        const required = ['remove', packageName, '--group', 'dev'];
        return required.every(part => args.includes(part));
      });

      expect(
        executeCommandStub.calledWith(expectedExecutable, expectedArgs, { cwd: projectPath })
      ).to.be.true;
    });

    it('should throw error if poetry command fails', async () => {
      executeCommandStub.rejects(new Error('Remove failed'));

      try {
        await dependencyService.removeDependency(projectPath, packageName);
        expect.fail('Should have thrown an error');
      } catch (error: any) {
        expect(error.message).to.include('Failed to remove dependency');
        expect(error.message).to.include('Remove failed');
      }
    });
  });

  describe('updateDependency', () => {
    const projectPath = '/test/project';
    const packageName = 'numpy';

    it('should throw error if pyproject.toml not found', async () => {
      try {
        await dependencyService.updateDependency(projectPath, packageName);
        expect.fail('Should have thrown an error');
      } catch (error: any) {
        expect(error.message).to.include('pyproject.toml not found');
      }
    });
  });
});
