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
import * as fs from 'node:fs';
import * as path from 'node:path';
import { StepManagement } from '../../../src/services/StepManagement';

describe('StepManagement', () => {
  let stepManagement: StepManagement;

  const makeDir = (name: string): fs.Dirent =>
    ({
      name,
      isDirectory: () => true
    } as unknown as fs.Dirent);

  beforeEach(() => {
    stepManagement = new StepManagement();
  });

  afterEach(() => {
    sinon.restore();
  });

  describe('findSolutionDir', () => {
    it('should discover legacy path under ansys/solutions', async () => {
      const solutionRoot = '/workspace';
      const srcRoot = path.join(solutionRoot, 'src');

      sinon.stub(fs.promises, 'readdir').callsFake(async (dirPath: any): Promise<any> => {
        if (dirPath === srcRoot) {
          return [makeDir('ansys')];
        }
        if (dirPath === path.join(srcRoot, 'ansys')) {
          return [makeDir('solutions')];
        }
        if (dirPath === path.join(srcRoot, 'ansys', 'solutions')) {
          return [makeDir('legacy_solution')];
        }
        return [];
      });

      sinon.stub(fs.promises, 'access').callsFake(async (filePath: any): Promise<void> => {
        if (
          filePath ===
          path.join(srcRoot, 'ansys', 'solutions', 'legacy_solution', 'solution', 'definition.py')
        ) {
          return;
        }
        throw new Error('not found');
      });

      const result = await stepManagement.findSolutionDir(solutionRoot);

      expect(result).to.equal(path.join('ansys', 'solutions', 'legacy_solution'));
    });

    it('should discover custom namespace path', async () => {
      const solutionRoot = '/workspace';
      const srcRoot = path.join(solutionRoot, 'src');

      sinon.stub(fs.promises, 'readdir').callsFake(async (dirPath: any): Promise<any> => {
        if (dirPath === srcRoot) {
          return [makeDir('my_team')];
        }
        if (dirPath === path.join(srcRoot, 'my_team')) {
          return [makeDir('platform')];
        }
        if (dirPath === path.join(srcRoot, 'my_team', 'platform')) {
          return [makeDir('my_solution')];
        }
        return [];
      });

      sinon.stub(fs.promises, 'access').callsFake(async (filePath: any): Promise<void> => {
        if (
          filePath ===
          path.join(srcRoot, 'my_team', 'platform', 'my_solution', 'solution', 'definition.py')
        ) {
          return;
        }
        throw new Error('not found');
      });

      const result = await stepManagement.findSolutionDir(solutionRoot);

      expect(result).to.equal(path.join('my_team', 'platform', 'my_solution'));
    });

    it('should discover solution in nested directories recursively', async () => {
      const solutionRoot = '/workspace';
      const srcRoot = path.join(solutionRoot, 'src');

      sinon.stub(fs.promises, 'readdir').callsFake(async (dirPath: any): Promise<any> => {
        if (dirPath === srcRoot) {
          return [makeDir('level1')];
        }
        if (dirPath === path.join(srcRoot, 'level1')) {
          return [makeDir('level2')];
        }
        if (dirPath === path.join(srcRoot, 'level1', 'level2')) {
          return [makeDir('deep_solution')];
        }
        return [];
      });

      sinon.stub(fs.promises, 'access').callsFake(async (filePath: any): Promise<void> => {
        if (
          filePath ===
          path.join(srcRoot, 'level1', 'level2', 'deep_solution', 'solution', 'definition.py')
        ) {
          return;
        }
        throw new Error('not found');
      });

      const result = await stepManagement.findSolutionDir(solutionRoot);

      expect(result).to.equal(path.join('level1', 'level2', 'deep_solution'));
    });

    it('should skip hidden directories during recursive discovery', async () => {
      const solutionRoot = '/workspace';
      const srcRoot = path.join(solutionRoot, 'src');

      sinon.stub(fs.promises, 'readdir').callsFake(async (dirPath: any): Promise<any> => {
        if (dirPath === srcRoot) {
          return [makeDir('.hidden_ns'), makeDir('visible_ns')];
        }
        if (dirPath === path.join(srcRoot, 'visible_ns')) {
          return [makeDir('visible_solution')];
        }
        // Intentionally no traversal for .hidden_ns because it must be skipped
        return [];
      });

      sinon.stub(fs.promises, 'access').callsFake(async (filePath: any): Promise<void> => {
        if (
          filePath ===
          path.join(srcRoot, 'visible_ns', 'visible_solution', 'solution', 'definition.py')
        ) {
          return;
        }
        throw new Error('not found');
      });

      const result = await stepManagement.findSolutionDir(solutionRoot);

      expect(result).to.equal(path.join('visible_ns', 'visible_solution'));
    });

    it('should throw not-found error when no solution package is discovered', async () => {
      const solutionRoot = '/workspace';
      const srcRoot = path.join(solutionRoot, 'src');

      sinon.stub(fs.promises, 'readdir').callsFake(async (dirPath: any): Promise<any> => {
        if (dirPath === srcRoot) {
          return [makeDir('a'), makeDir('b')];
        }
        if (dirPath === path.join(srcRoot, 'a') || dirPath === path.join(srcRoot, 'b')) {
          return [makeDir('sub')];
        }
        return [];
      });

      sinon.stub(fs.promises, 'access').rejects(new Error('not found'));

      try {
        await stepManagement.findSolutionDir(solutionRoot);
        expect.fail('Expected findSolutionDir to throw');
      } catch (error: any) {
        expect(error.message).to.include('Failed to find solution directory');
        expect(error.message).to.include('Could not find solution package directory under src');
      }
    });
  });
});