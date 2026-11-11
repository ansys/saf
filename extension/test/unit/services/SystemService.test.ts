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
import * as vscode from 'vscode';
import { SystemService } from '../../../src/services/SystemService';
import { Registry } from 'winreg-ts';

/**
 * Unit tests for SystemService class
 */
describe('SystemService', () => {
  let systemService: SystemService;

  beforeEach(() => {
    systemService = new SystemService();
  });

  afterEach(() => {
    sinon.restore();
  });

  describe('getVenvPythonExecutable', () => {
    it('should return correct path format', () => {
      const venvPath = String.raw`C:\Users\test\venv`;

      const result = systemService.getVenvPythonExecutable(venvPath);

      if (process.platform === 'win32') {
        expect(result).to.equal(path.join(venvPath, 'Scripts', 'python.exe'));
      } else {
        expect(result).to.equal(path.join(venvPath, 'bin', 'python'));
      }
    });

    it('should handle paths with spaces correctly', () => {
      const venvPath = String.raw`C:\Program Files\Python Env`;

      const result = systemService.getVenvPythonExecutable(venvPath);

      if (process.platform === 'win32') {
        expect(result).to.equal(path.join(venvPath, 'Scripts', 'python.exe'));
      } else {
        expect(result).to.equal(path.join(venvPath, 'bin', 'python'));
      }
    });
  });

  describe('checkAndPromptForCredentials', () => {
    const USERNAME_ENV_KEY = 'POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_USERNAME';
    const PASSWORD_ENV_KEY = 'POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_PASSWORD'; // nosonar

    let showInputBoxStub: sinon.SinonStub;
    let showErrorMessageStub: sinon.SinonStub;
    let showWarningMessageStub: sinon.SinonStub;
    let setEnvironmentVariableStub: sinon.SinonStub;
    let validateCredentialsStub: sinon.SinonStub;
    let savedUsername: string | undefined;
    let savedPassword: string | undefined;

    const testSource = {
      name: 'my-private-pypi',
      url: 'https://pypi.example.com/simple/',
      priority: 'primary'
    };

    beforeEach(() => {
      savedUsername = process.env[USERNAME_ENV_KEY];
      savedPassword = process.env[PASSWORD_ENV_KEY];
      delete process.env[USERNAME_ENV_KEY];
      delete process.env[PASSWORD_ENV_KEY];

      showInputBoxStub = vscode.window.showInputBox as sinon.SinonStub;
      showErrorMessageStub = vscode.window.showErrorMessage as sinon.SinonStub;
      showWarningMessageStub = vscode.window.showWarningMessage as sinon.SinonStub;
      showInputBoxStub.reset();
      showErrorMessageStub.reset();
      showWarningMessageStub.reset();

      setEnvironmentVariableStub = sinon.stub(systemService, 'setEnvironmentVariable' as any).resolves();
      validateCredentialsStub = sinon.stub(systemService, 'validateCredentials').resolves(true);
    });

    afterEach(() => {
      if (savedUsername === undefined) {
        delete process.env[USERNAME_ENV_KEY];
      } else {
        process.env[USERNAME_ENV_KEY] = savedUsername;
      }
      if (savedPassword === undefined) {
        delete process.env[PASSWORD_ENV_KEY];
      } else {
        process.env[PASSWORD_ENV_KEY] = savedPassword;
      }
    });

    it('should return true when valid credentials are available in environment', async () => {
      process.env[USERNAME_ENV_KEY] = 'some-user';
      process.env[PASSWORD_ENV_KEY] = 'some-password'; // nosonar

      const result = await systemService.checkAndPromptForCredentials(testSource);

      expect(result).to.be.true;
      expect(showInputBoxStub.called).to.be.false;
      expect(setEnvironmentVariableStub.called).to.be.false;
    });

    it('should prompt for credentials when not available in environment', async () => {
      showInputBoxStub.onFirstCall().resolves('some-user');
      showInputBoxStub.onSecondCall().resolves('some-password');

      const result = await systemService.checkAndPromptForCredentials(testSource);

      expect(result).to.be.false;
      expect(showInputBoxStub.calledTwice).to.be.true;
      expect(showInputBoxStub.firstCall.args[0]).to.include({
        prompt: 'Enter your my-private-pypi username'
      });
      expect(showInputBoxStub.secondCall.args[0]).to.include({
        prompt: 'Enter your my-private-pypi password',
        password: true
      });
      expect(setEnvironmentVariableStub.calledTwice).to.be.true;
      expect(setEnvironmentVariableStub.firstCall.args).to.deep.equal([
        'POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_USERNAME',
        'some-user'
      ]);
      expect(setEnvironmentVariableStub.secondCall.args).to.deep.equal([
        'POETRY_HTTP_BASIC_MY_PRIVATE_PYPI_PASSWORD',
        'some-password'
      ]);
      expect(showWarningMessageStub.calledOnce).to.be.true;
      expect(showWarningMessageStub.firstCall.args[0]).to.include('Environment variables have been updated');
    });

    it('should handle invalid credentials and retry', async () => {
      showInputBoxStub.onCall(0).resolves('some-user');
      showInputBoxStub.onCall(1).resolves('invalid-password');
      showInputBoxStub.onCall(2).resolves('some-user');
      showInputBoxStub.onCall(3).resolves('valid-password');
      validateCredentialsStub.onFirstCall().resolves(false);
      validateCredentialsStub.onSecondCall().resolves(true);

      const result = await systemService.checkAndPromptForCredentials(testSource);

      expect(result).to.be.false;
      expect(showInputBoxStub.callCount).to.equal(4);
      expect(showErrorMessageStub.calledOnce).to.be.true;
      expect(showErrorMessageStub.firstCall.args[0]).to.include('Invalid credentials');
      expect(setEnvironmentVariableStub.calledTwice).to.be.true;
      expect(showWarningMessageStub.calledOnce).to.be.true;
    });

    it('should throw error when user cancels credential input', async () => {
      showInputBoxStub.resolves(undefined);

      try {
        await systemService.checkAndPromptForCredentials(testSource);
        expect.fail('Should have thrown an error');
      } catch (error) {
        expect(error).to.be.an('error');
        expect((error as Error).message).to.include('PyPI username or password not provided');
      }

      expect(setEnvironmentVariableStub.called).to.be.false;
    });
  });

  describe('checkWindowsLongPaths', () => {
    let showWarningMessageStub: sinon.SinonStub;
    let consoleWarnStub: sinon.SinonStub;
    let originalPlatform: string;

    beforeEach(() => {
      originalPlatform = Object.getOwnPropertyDescriptor(process, 'platform')?.value || process.platform;
      showWarningMessageStub = vscode.window.showWarningMessage as sinon.SinonStub;
      showWarningMessageStub.reset();
      consoleWarnStub = sinon.stub(console, 'warn');
    });

    afterEach(() => {
      Object.defineProperty(process, 'platform', {
        value: originalPlatform,
        writable: false,
        configurable: true
      });
    });

    it('should return true on non-Windows platforms without checking registry', async () => {
      Object.defineProperty(process, 'platform', {
        value: 'linux',
        writable: false,
        configurable: true
      });

      const result = await systemService.checkWindowsLongPaths();

      expect(result).to.be.true;
      expect(showWarningMessageStub.called).to.be.false;
      expect(consoleWarnStub.called).to.be.false;
    });

    it('should return true when Windows registry value is enabled (0x1)', async () => {
      Object.defineProperty(process, 'platform', {
        value: 'win32',
        writable: false,
        configurable: true
      });

      // Mock the Registry constructor and its get method
      const getStub = sinon.stub().callsFake(
        (_valueName: string, callback: (err: Error | null, item?: any) => void) => {
          callback(null, { value: '0x1' });
        }
      );

      sinon.stub(Registry.prototype, 'get' as any).callsFake(getStub);

      const result = await systemService.checkWindowsLongPaths();

      expect(result).to.be.true;
      expect(showWarningMessageStub.called).to.be.false;
    });

    it('should return false and show warning when Windows registry value is disabled (0x0)', async () => {
      Object.defineProperty(process, 'platform', {
        value: 'win32',
        writable: false,
        configurable: true
      });

      const getStub = sinon.stub().callsFake(
        (_valueName: string, callback: (err: Error | null, item?: any) => void) => {
          callback(null, { value: '0x0' });
        }
      );

      sinon.stub(Registry.prototype, 'get' as any).callsFake(getStub);

      const result = await systemService.checkWindowsLongPaths();

      expect(result).to.be.false;
      expect(showWarningMessageStub.calledOnce).to.be.true;
      expect(showWarningMessageStub.firstCall.args[0]).to.include('Windows Long Paths support is not enabled');
    });

    it('should return false and show warning when Windows registry value is not found', async () => {
      Object.defineProperty(process, 'platform', {
        value: 'win32',
        writable: false,
        configurable: true
      });

      const getStub = sinon.stub().callsFake(
        (_valueName: string, callback: (err: Error | null, item?: any) => void) => {
          callback(null, null);
        }
      );

      sinon.stub(Registry.prototype, 'get' as any).callsFake(getStub);

      const result = await systemService.checkWindowsLongPaths();

      expect(result).to.be.false;
      expect(showWarningMessageStub.calledOnce).to.be.true;
      expect(showWarningMessageStub.firstCall.args[0]).to.include('Windows Long Paths support is not enabled');
    });

    it('should return false and show warning when registry read fails with error', async () => {
      Object.defineProperty(process, 'platform', {
        value: 'win32',
        writable: false,
        configurable: true
      });

      // Mock the Registry constructor and its get method to throw an error
      const registryError = new Error('Registry access denied');
      const getStub = sinon.stub().callsFake(
        (_valueName: string, callback: (err: Error | null, item?: any) => void) => {
          callback(registryError);
        }
      );

      sinon.stub(Registry.prototype, 'get' as any).callsFake(getStub);

      const result = await systemService.checkWindowsLongPaths();

      expect(result).to.be.false;
      expect(consoleWarnStub.calledOnce).to.be.true;
      expect(consoleWarnStub.firstCall.args[0]).to.include('Failed to read Windows Long Paths registry key');
      expect(showWarningMessageStub.calledOnce).to.be.true;
    });
  });
});
