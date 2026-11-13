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
import { SAFSolutionsProvider, SAFSolutionItem } from '../../../src/providers/SAFSolutionsProvider';
import { StorageService } from '../../../src/services/StorageService';
import { systemService } from '../../../src/services/SystemService';
import { mockExtensionContext } from '../setup.integration';
import { createTestSolution } from '../testHelpers';



describe('SAFSolutionsProvider Integration Tests', () => {
  before(() => {
    new StorageService(mockExtensionContext);
    systemService.setContext(mockExtensionContext);
  });

  beforeEach(() => {
    (SAFSolutionsProvider as any).instance = undefined;
  });

  it('getSAFSolutions returns structured solutions', async function () {
    const provider = SAFSolutionsProvider.getInstance();
    const { solutionName, createdSolutionPath } = await createTestSolution(
      'int-test',
      'Integration Test Solution'
    );

    // Allow provider to pick up the new solution
    provider.refresh();
    const solutions = await provider.getSAFSolutions();

    expect(solutions).to.be.an('array');

    const found = solutions.find(s => s.name === solutionName || s.rootDirectory === createdSolutionPath);
    expect(found).to.not.be.undefined;
    expect(found?.displayName).to.equal('Integration Test Solution');
    expect(found?.rootDirectory).to.equal(createdSolutionPath);
  });

  it('getChildren reflects getSAFSolutions', async function () {
    const provider = SAFSolutionsProvider.getInstance();
    const { solutionName, createdSolutionPath } = await createTestSolution(
      'int-child-test',
      'Children Mapping Test Solution'
    );

    provider.refresh();
    const solutions = await provider.getSAFSolutions();
    const children = await provider.getChildren();

    const foundSolution = solutions.find(s => s.name === solutionName || s.rootDirectory === createdSolutionPath);
    expect(foundSolution).to.not.be.undefined;

    const foundChild = (children as SAFSolutionItem[]).find(c => c.rootDirectory === foundSolution!.rootDirectory) as SAFSolutionItem | undefined;
    expect(foundChild).to.not.be.undefined;
    expect(foundChild).to.be.instanceOf(SAFSolutionItem);
    expect(foundChild!.label).to.equal(foundSolution!.name);
    expect(foundChild!.rootDirectory).to.equal(foundSolution!.rootDirectory);
  });
});
