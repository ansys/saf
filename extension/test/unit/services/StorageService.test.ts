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
import { StorageService } from '../../../src/services/StorageService';

describe('StorageService', () => {
  let mockContext: vscode.ExtensionContext;
  let globalStateStub: sinon.SinonStubbedInstance<vscode.Memento>;

  beforeEach(() => {
    globalStateStub = {
      get: sinon.stub(),
      update: sinon.stub().resolves(),
      keys: sinon.stub().returns([]),
      setKeysForSync: sinon.stub()
    } as unknown as sinon.SinonStubbedInstance<vscode.Memento>;

    mockContext = {
      globalState: globalStateStub
    } as unknown as vscode.ExtensionContext;

    // Reset the singleton instance before each test
    (StorageService as any).instance = undefined;
  });

  afterEach(() => {
    sinon.restore();
  });

  describe('singleton instance', () => {
    it('should always return the same StorageService instance', () => {
      const service1 = new StorageService(mockContext);
      const service2 = StorageService.getInstance();
      expect(service1).to.equal(service2);

      // Even if we try to create another instance, getInstance should return the latest one
      const newMockContext = { globalState: globalStateStub } as any;
      const service3 = new StorageService(newMockContext);
      const service4 = StorageService.getInstance();
      expect(service3).to.equal(service4);
      expect(service1).to.not.equal(service3);
    });

    it('should throw an error when not initialized', () => {
      expect(() => StorageService.getInstance()).to.throw('StorageService is not initialized.');
    });
  });

  describe('getSafCliInfo', () => {
    it('should return SAF CLI info when it exists', () => {
      const safCliInfo = { executablePath: '/path/to/saf', version: '1.0.0' };
      globalStateStub.get.withArgs('safCliInfo').returns(safCliInfo);
      new StorageService(mockContext);

      const result = StorageService.getSafCliInfo();

      expect(result).to.deep.equal(safCliInfo);
      expect(globalStateStub.get.calledWith('safCliInfo')).to.be.true;
    });

    it('should return null when SAF CLI info does not exist', () => {
      globalStateStub.get.withArgs('safCliInfo').returns(undefined);
      new StorageService(mockContext);

      const result = StorageService.getSafCliInfo();

      expect(result).to.be.null;
    });
  });

  describe('getSafCliExecutablePath', () => {
    it('should return the executable path when SAF CLI info exists', () => {
      const safCliInfo = { executablePath: '/path/to/saf', version: '1.0.0' };
      globalStateStub.get.withArgs('safCliInfo').returns(safCliInfo);
      new StorageService(mockContext);

      const result = StorageService.getSafCliExecutablePath();

      expect(result).to.equal('/path/to/saf');
    });

    it('should throw an error when SAF CLI info does not exist', () => {
      globalStateStub.get.withArgs('safCliInfo').returns(undefined);
      new StorageService(mockContext);

      expect(() => StorageService.getSafCliExecutablePath()).to.throw(
        'SAF CLI is not installed. Please install SAF CLI to proceed.'
      );
    });
  });

  describe('getSafCliExecutableCommand', () => {
    it('should return quoted executable path when it contains spaces', () => {
      const safCliInfo = { executablePath: 'C:\\My User\\saf.exe', version: '1.0.0' };
      globalStateStub.get.withArgs('safCliInfo').returns(safCliInfo);
      new StorageService(mockContext);

      const result = StorageService.getSafCliExecutableCommand();

      expect(result).to.equal('"C:\\My User\\saf.exe"');
    });

    it('should return raw executable path when it contains no spaces', () => {
      const safCliInfo = { executablePath: 'C:\\MyUser\\saf.exe', version: '1.0.0' };
      globalStateStub.get.withArgs('safCliInfo').returns(safCliInfo);
      new StorageService(mockContext);

      const result = StorageService.getSafCliExecutableCommand();

      expect(result).to.equal('C:\\MyUser\\saf.exe');
    });
  });

  describe('getSafCliVersion', () => {
    it('should return the version when SAF CLI info exists', () => {
      const safCliInfo = { executablePath: '/path/to/saf', version: '1.0.0' };
      globalStateStub.get.withArgs('safCliInfo').returns(safCliInfo);
      new StorageService(mockContext);

      const result = StorageService.getSafCliVersion();

      expect(result).to.equal('1.0.0');
    });

    it('should return null when SAF CLI info does not exist', () => {
      globalStateStub.get.withArgs('safCliInfo').returns(undefined);
      new StorageService(mockContext);

      const result = StorageService.getSafCliVersion();

      expect(result).to.be.null;
    });
  });

  describe('setSafCliInfo', () => {
    it('should store SAF CLI info in global state', async () => {
      new StorageService(mockContext);

      await StorageService.setSafCliInfo('/path/to/saf', '1.0.0');

      expect(globalStateStub.update.calledWith('safCliInfo', {
        executablePath: '/path/to/saf',
        version: '1.0.0'
      })).to.be.true;
    });

    it('should update existing SAF CLI info', async () => {
      globalStateStub.get.withArgs('safCliInfo').returns({
        executablePath: '/old/path',
        version: '0.9.0'
      });
      new StorageService(mockContext);

      await StorageService.setSafCliInfo('/new/path', '1.1.0');

      expect(globalStateStub.update.calledWith('safCliInfo', {
        executablePath: '/new/path',
        version: '1.1.0'
      })).to.be.true;
    });
  });

  describe('clearSafCliInfo', () => {
    it('should clear SAF CLI info from global state', async () => {
      new StorageService(mockContext);

      await StorageService.clearSafCliInfo();

      expect(globalStateStub.update.calledWith('safCliInfo', undefined)).to.be.true;
    });
  });

  describe('getLastTargetDirectory', () => {
    it('should return the last target directory when it exists', () => {
      globalStateStub.get.withArgs('lastTargetDirectory').returns('/path/to/directory');
      new StorageService(mockContext);

      const result = StorageService.getLastTargetDirectory();

      expect(result).to.equal('/path/to/directory');
      expect(globalStateStub.get.calledWith('lastTargetDirectory')).to.be.true;
    });

    it('should return undefined when no target directory is stored', () => {
      globalStateStub.get.withArgs('lastTargetDirectory').returns(undefined);
      new StorageService(mockContext);

      const result = StorageService.getLastTargetDirectory();

      expect(result).to.be.undefined;
    });
  });

  describe('setLastTargetDirectory', () => {
    it('should store the target directory in global state', async () => {
      new StorageService(mockContext);

      await StorageService.setLastTargetDirectory('/new/target/directory');

      expect(globalStateStub.update.calledWith('lastTargetDirectory', '/new/target/directory')).to.be.true;
    });

    it('should update existing target directory', async () => {
      globalStateStub.get.withArgs('lastTargetDirectory').returns('/old/directory');
      new StorageService(mockContext);

      await StorageService.setLastTargetDirectory('/updated/directory');

      expect(globalStateStub.update.calledWith('lastTargetDirectory', '/updated/directory')).to.be.true;
    });
  });

  describe('isTerminalPowerShell', () => {
    afterEach(() => {
        (vscode as any).env.shell = '';
    });

    it('should return true for Windows PowerShell (powershell.exe)', () => {
        (vscode as any).env.shell = 'C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe';
        expect(StorageService.isTerminalPowerShell()).to.be.true;
    });

    it('should return true for PowerShell 7 (pwsh.exe)', () => {
        (vscode as any).env.shell = 'C:\\Program Files\\PowerShell\\7\\pwsh.exe';
        expect(StorageService.isTerminalPowerShell()).to.be.true;
    });

    it('should return true for pwsh on non-windows', () => {
        (vscode as any).env.shell = '/usr/bin/pwsh';
        expect(StorageService.isTerminalPowerShell()).to.be.true;
    });

    it('should return false for cmd.exe', () => {
        (vscode as any).env.shell = 'C:\\Windows\\System32\\cmd.exe';
        expect(StorageService.isTerminalPowerShell()).to.be.false;
    });

    it('should return false for git bash', () => {
        (vscode as any).env.shell = 'C:\\Program Files\\Git\\bin\\bash.exe';
        expect(StorageService.isTerminalPowerShell()).to.be.false;
    });

    it('should return false for bash on non-windows', () => {
        (vscode as any).env.shell = '/bin/bash';
        expect(StorageService.isTerminalPowerShell()).to.be.false;
    });

    it('should return false when shell is empty', () => {
        (vscode as any).env.shell = '';
        expect(StorageService.isTerminalPowerShell()).to.be.false;
    });
});

describe('getSafCliTerminalCommand', () => {
    const originalPlatform = process.platform;
    let isTerminalPowerShellStub: sinon.SinonStub;

    beforeEach(() => {
        isTerminalPowerShellStub = sinon.stub(StorageService, 'isTerminalPowerShell').returns(false);
    });

    afterEach(() => {
        Object.defineProperty(process, 'platform', { value: originalPlatform, writable: true });
    });

    it('should return raw executable path when it contains no spaces', () => {
        const safCliInfo = { executablePath: 'C:\\MyUser\\saf.exe', version: '1.0.0' };
        globalStateStub.get.withArgs('safCliInfo').returns(safCliInfo);
        new StorageService(mockContext);

        const result = StorageService.getSafCliTerminalCommand();

        expect(result).to.equal('C:\\MyUser\\saf.exe');
    });

    it('should return PowerShell call operator command on windows when executable path contains spaces', () => {
        Object.defineProperty(process, 'platform', { value: 'win32', writable: true });
        isTerminalPowerShellStub.returns(true);
        const safCliInfo = { executablePath: 'C:\\My User\\saf.exe', version: '1.0.0' };
        globalStateStub.get.withArgs('safCliInfo').returns(safCliInfo);
        new StorageService(mockContext);

        const result = StorageService.getSafCliTerminalCommand();

        expect(result).to.equal('& "C:\\My User\\saf.exe"');
    });

    it('should return quoted command on windows with cmd.exe when executable path contains spaces', () => {
        Object.defineProperty(process, 'platform', { value: 'win32', writable: true });
        isTerminalPowerShellStub.returns(false);
        const safCliInfo = { executablePath: 'C:\\My User\\saf.exe', version: '1.0.0' };
        globalStateStub.get.withArgs('safCliInfo').returns(safCliInfo);
        new StorageService(mockContext);

        const result = StorageService.getSafCliTerminalCommand();

        expect(result).to.equal('"C:\\My User\\saf.exe"');
    });

    it('should return quoted command on windows with git bash when executable path contains spaces', () => {
        Object.defineProperty(process, 'platform', { value: 'win32', writable: true });
        isTerminalPowerShellStub.returns(false);
        const safCliInfo = { executablePath: 'C:\\My User\\saf.exe', version: '1.0.0' };
        globalStateStub.get.withArgs('safCliInfo').returns(safCliInfo);
        new StorageService(mockContext);

        const result = StorageService.getSafCliTerminalCommand();

        expect(result).to.equal('"C:\\My User\\saf.exe"');
    });

    it('should return quoted command on non-windows when executable path contains spaces', () => {
        Object.defineProperty(process, 'platform', { value: 'linux', writable: true });
        const safCliInfo = { executablePath: '/home/my user/saf', version: '1.0.0' };
        globalStateStub.get.withArgs('safCliInfo').returns(safCliInfo);
        new StorageService(mockContext);

        const result = StorageService.getSafCliTerminalCommand();

        expect(result).to.equal('"/home/my user/saf"');
    });
  });
});
