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
import * as os from 'node:os';
import { systemService } from '../../../src/services/SystemService';
import { mockExtensionContext } from '../setup.integration';
import * as execModule from '../../../src/utils/exec';
import { SAF_CLI_VERSION } from '../../../src/utils/safCliVersion';

describe('Python Version Check Integration', () => {
  let execAsyncStub: sinon.SinonStub;
  let execFileAsyncStub: sinon.SinonStub;
  let showErrorMessageStub: sinon.SinonStub;
  let withProgressStub: sinon.SinonStub;
  let getInstalledSafCliVersionStub: sinon.SinonStub;
  let getManagedVenvPathStub: sinon.SinonStub;

  let testVenvPath: string;
  let originalContext: vscode.ExtensionContext | undefined;
  let originalSafCliInfo: unknown;

  before(() => {
    // Create a unique test venv path that won't conflict with the real one
    testVenvPath = path.join(os.tmpdir(), `saf-test-venv-${Date.now()}`);

    originalContext = (systemService as any).context;
    try {
      originalSafCliInfo = mockExtensionContext.globalState.get('safCliInfo');
    } catch (err) {
      console.warn('Failed to store original safCliInfo:', err);
      originalSafCliInfo = undefined;
    }
  });

  beforeEach(() => {
    // Stub getManagedVenvPath to return our test-specific path.
    // This isolates venv operations to a temporary directory, preventing deletion of the real venv
    // used by other integration tests. We use this approach because fs.rmSync and fs.existsSync
    // are non-configurable and cannot be stubbed directly with Sinon.
    getManagedVenvPathStub = sinon.stub(systemService, 'getManagedVenvPath');
    getManagedVenvPathStub.returns(testVenvPath);

    sinon.stub(vscode.window, 'showInformationMessage');
    showErrorMessageStub = sinon.stub(vscode.window, 'showErrorMessage');
    withProgressStub = sinon.stub(vscode.window, 'withProgress');
    withProgressStub.callsFake(async (_options, task) => {
      return await task({ report: () => {} }, {} as any);
    });

    getInstalledSafCliVersionStub = sinon.stub(systemService, 'getInstalledSafCliVersion');
    getInstalledSafCliVersionStub.resolves(null);

    execAsyncStub = sinon.stub(execModule, 'execAsync');
    execFileAsyncStub = sinon.stub(execModule, 'execFileAsync');
    execFileAsyncStub.resolves({ stdout: '', stderr: '' });
  });

  afterEach(async () => {
    sinon.restore();
    if (fs.existsSync(testVenvPath)) {
      try {
        fs.rmSync(testVenvPath, { recursive: true, force: true });
      } catch (error) {
        console.warn('Failed to clean up test venv:', error);
      }
    }
    try {
      await mockExtensionContext.globalState.update('safCliInfo', originalSafCliInfo as any);
    } catch (err) {
      console.warn('Failed to restore original safCliInfo:', err);
    }
  });

  after(() => {
    if (originalContext) {
      (systemService as any).context = originalContext;
    }
  });

  it('should fail installation when Python is not available', async () => {
    execAsyncStub.rejects(new Error('python: command not found'));

    await systemService.handleSAFCliInstallation();

    expect(showErrorMessageStub.called).to.be.true;
    const errorCall = showErrorMessageStub.getCalls().find(call =>
      call.args[0].includes('Failed to install ansys-saf-cli')
    );
    expect(errorCall).to.not.be.undefined;
    expect(errorCall?.args[0]).to.satisfy((msg: string) =>
      msg.includes('Failed to check Python version') &&
      msg.includes('Please ensure that a stable Python version')
    );

    expect(execAsyncStub.calledWith(sinon.match(/python -c/))).to.be.true;
    expect(execAsyncStub.calledWith(sinon.match(/python -m venv/))).to.be.false;
  });

  it('should fail installation when Python version is too old', async () => {
    execAsyncStub.withArgs(sinon.match(/python -c/)).resolves({ stdout: '3.8\n', stderr: '' });

    await systemService.handleSAFCliInstallation();

    expect(showErrorMessageStub.called).to.be.true;
    const errorCall = showErrorMessageStub.getCalls().find(call =>
      call.args[0].includes('Failed to install ansys-saf-cli')
    );
    expect(errorCall).to.not.be.undefined;
    expect(errorCall?.args[0]).to.include('Python 3.8 is not supported');
    expect(errorCall?.args[0]).to.include('>=3.11, <3.15');

    expect(execAsyncStub.calledWith(sinon.match(/python -m venv/))).to.be.false;
  });

  it('should fail installation when Python version is too new', async () => {
    execAsyncStub.withArgs(sinon.match(/python -c/)).resolves({ stdout: '3.15\n', stderr: '' });

    await systemService.handleSAFCliInstallation();

    expect(showErrorMessageStub.called).to.be.true;
    const errorCall = showErrorMessageStub.getCalls().find(call =>
      call.args[0].includes('Failed to install ansys-saf-cli')
    );
    expect(errorCall).to.not.be.undefined;
    expect(errorCall?.args[0]).to.include('Python 3.15 is not supported');
    expect(errorCall?.args[0]).to.include('>=3.11, <3.15');

    expect(execAsyncStub.calledWith(sinon.match(/python -m venv/))).to.be.false;
  });

  it('should fail installation when Python major version is not 3', async () => {
    execAsyncStub.withArgs(sinon.match(/python -c/)).resolves({ stdout: '2.7\n', stderr: '' });

    await systemService.handleSAFCliInstallation();

    expect(showErrorMessageStub.called).to.be.true;
    const errorCall = showErrorMessageStub.getCalls().find(call =>
      call.args[0].includes('Failed to install ansys-saf-cli')
    );
    expect(errorCall).to.not.be.undefined;
    expect(errorCall?.args[0]).to.include('Python 2.7 is not supported');

    expect(execAsyncStub.calledWith(sinon.match(/python -m venv/))).to.be.false;
  });

  it('should succeed at minimum Python version boundary (3.11)', async () => {
    execAsyncStub.withArgs(sinon.match(/python -c/)).resolves({ stdout: '3.11\n', stderr: '' });
    execAsyncStub.withArgs(sinon.match(/python -m venv/)).resolves({ stdout: '', stderr: '' });

    await systemService.handleSAFCliInstallation();

    const pythonErrorCall = showErrorMessageStub.getCalls().find(call =>
      call.args[0].includes('Python') && call.args[0].includes('not supported')
    );
    expect(pythonErrorCall).to.be.undefined;
    expect(execAsyncStub.calledWith(sinon.match(/python -m venv/))).to.be.true;
  });

  it('should succeed at maximum Python version boundary (3.14)', async () => {
    execAsyncStub.withArgs(sinon.match(/python -c/)).resolves({ stdout: '3.14\n', stderr: '' });
    execAsyncStub.withArgs(sinon.match(/python -m venv/)).resolves({ stdout: '', stderr: '' });

    await systemService.handleSAFCliInstallation();

    const pythonErrorCall = showErrorMessageStub.getCalls().find(call =>
      call.args[0].includes('Python') && call.args[0].includes('not supported')
    );
    expect(pythonErrorCall).to.be.undefined;
    expect(execAsyncStub.calledWith(sinon.match(/python -m venv/))).to.be.true;
  });

  it('should succeed with Python version in valid range (3.12)', async () => {
    execAsyncStub.withArgs(sinon.match(/python -c/)).resolves({ stdout: '3.12\n', stderr: '' });
    execAsyncStub.withArgs(sinon.match(/python -m venv/)).resolves({ stdout: '', stderr: '' });

    await systemService.handleSAFCliInstallation();

    const pythonErrorCall = showErrorMessageStub.getCalls().find(call =>
      call.args[0].includes('Python') && call.args[0].includes('not supported')
    );
    expect(pythonErrorCall).to.be.undefined;
    expect(execAsyncStub.calledWith(sinon.match(/python -m venv/))).to.be.true;
  });

  it('should handle malformed Python version output', async () => {
    execAsyncStub.withArgs(sinon.match(/python -c/)).resolves({ stdout: 'invalid\n', stderr: '' });

    await systemService.handleSAFCliInstallation();

    expect(showErrorMessageStub.called).to.be.true;
    const errorCall = showErrorMessageStub.getCalls().find(call =>
      call.args[0].includes('Failed to install ansys-saf-cli') &&
      call.args[0].includes('invalid')
    );
    expect(errorCall).to.not.be.undefined;
    expect(execAsyncStub.calledWith(sinon.match(/python -m venv/))).to.be.false;
  });

  it('should handle empty Python version output', async () => {
    execAsyncStub.withArgs(sinon.match(/python -c/)).resolves({ stdout: '\n', stderr: '' });

    await systemService.handleSAFCliInstallation();

    expect(showErrorMessageStub.called).to.be.true;
    expect(execAsyncStub.calledWith(sinon.match(/python -m venv/))).to.be.false;
  });

  it('should fail when venv creation fails', async () => {
    execAsyncStub.withArgs(sinon.match(/python -c/)).resolves({ stdout: '3.11\n', stderr: '' });
    execAsyncStub.withArgs(sinon.match(/python -m venv/)).rejects(new Error('venv creation failed'));

    await systemService.handleSAFCliInstallation();

    expect(showErrorMessageStub.called).to.be.true;
    const errorCall = showErrorMessageStub.getCalls().find(call =>
      call.args[0].includes('Failed to install ansys-saf-cli') &&
      call.args[0].includes('venv creation failed')
    );
    expect(errorCall).to.not.be.undefined;
  });

  it('should fail when pip upgrade fails', async () => {
    execAsyncStub.withArgs(sinon.match(/python -c/)).resolves({ stdout: '3.11\n', stderr: '' });
    execAsyncStub.withArgs(sinon.match(/python -m venv/)).resolves({ stdout: '', stderr: '' });
    execFileAsyncStub.withArgs(sinon.match.any, sinon.match.array.contains(['pip'])).rejects(new Error('pip upgrade failed'));

    await systemService.handleSAFCliInstallation();

    expect(showErrorMessageStub.called).to.be.true;
  });

  it('should fail when ansys-saf-cli package installation fails', async () => {
    execAsyncStub.withArgs(sinon.match(/python -c/)).resolves({ stdout: '3.11\n', stderr: '' });
    execAsyncStub.withArgs(sinon.match(/python -m venv/)).resolves({ stdout: '', stderr: '' });
    execFileAsyncStub.onFirstCall().resolves({ stdout: '', stderr: '' });
    execFileAsyncStub.onSecondCall().rejects(new Error('package installation failed'));

    await systemService.handleSAFCliInstallation();

    const errorCall = showErrorMessageStub.getCalls().find(call =>
      call.args[0].includes('Failed to install ansys-saf-cli') &&
      call.args[0].includes('package installation failed')
    );
    expect(errorCall).to.not.be.undefined;
  });

  it('should install the pinned ansys-saf-cli package from PyPI via pip', async () => {
    execAsyncStub.withArgs(sinon.match(/python -c/)).resolves({ stdout: '3.11\n', stderr: '' });
    execAsyncStub.withArgs(sinon.match(/python -m venv/)).resolves({ stdout: '', stderr: '' });

    await systemService.handleSAFCliInstallation();

    expect(execFileAsyncStub.calledTwice).to.be.true;

    const [pipUpgradeExec, pipUpgradeArgs, pipUpgradeOptions] = execFileAsyncStub.getCall(0).args;
    expect(pipUpgradeArgs).to.deep.equal(['-m', 'pip', 'install', '--upgrade', 'pip']);
    expect(pipUpgradeOptions).to.be.undefined;

    const [installExec, installArgs, installOptions] = execFileAsyncStub.getCall(1).args;
    expect(installExec).to.equal(pipUpgradeExec);
    expect(installArgs).to.deep.equal(['-m', 'pip', 'install', `ansys-saf-cli==${SAF_CLI_VERSION}`]);
    expect(installOptions).to.be.undefined;
  });
});
