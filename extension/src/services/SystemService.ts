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


import * as childProcess from 'node:child_process';
import * as path from 'node:path';
import * as fs from 'node:fs';
import * as vscode from 'vscode';
import { SAF_CLI_VERSION } from '../utils/safCliVersion';
import { SAFSolutionsProvider } from '../providers/SAFSolutionsProvider';
import { EnvironmentService } from './EnvironmentService';
import { execAsync, execFileAsync } from '../utils/exec';
import { Registry } from 'winreg-ts';



export interface PythonInstallation {
    isDefault: any;
    path: string;
    version: string;
}

enum InstallationMode {
    Install = 'install',
    Update = 'update'
}

export class SystemService {
    private context?: vscode.ExtensionContext;

    setContext(context: vscode.ExtensionContext): void {
        this.context = context;
    }

    private getManagedPythonPath(): string {
        const venvPath = this.getManagedVenvPath();
        return this.getVenvPythonExecutable(venvPath);
    }

    getManagedVenvPath(): string {
        if (!this.context) {
            throw new Error('Extension context is not set in SystemService.');
        }
        return path.join(this.context.globalStorageUri.fsPath, 'saf-cli-venv');
    }

    getSafCliExecutablePath(): string {
        const venvPath = this.getManagedVenvPath();
        const isWindows = process.platform === 'win32';
        return isWindows
            ? path.join(venvPath, 'Scripts', 'saf.exe')
            : path.join(venvPath, 'bin', 'saf');
    }

    async getInstalledSafCliVersion(): Promise<string | null> {
        try {
            const venvPath = this.getManagedVenvPath();
            return await this.getSafCliVersionOnVenv(venvPath);
        } catch (error) {
            vscode.window.showErrorMessage(
                `Failed to get installed ansys-saf-cli version: ${error instanceof Error ? error.message : 'Unknown error'}`
            );
            return null;
        }
    }

    getVenvPythonExecutable(venvPath: string): string {
        if (process.platform === 'win32') {
          return path.join(venvPath, 'Scripts', 'python.exe');
        } else {
          return path.join(venvPath, 'bin', 'python');
        }
    }

    async handleSAFCliInstallation(): Promise<void> {
        if (!this.context) {
            throw new Error('Extension context is not set in SystemService.');
        }

        const installedVersion = await this.getInstalledSafCliVersion();
        if (installedVersion === SAF_CLI_VERSION) {
            await this.storeSafCliInfo(SAF_CLI_VERSION);
            return;
        }

        let installationMode: InstallationMode = installedVersion ? InstallationMode.Update : InstallationMode.Install;
        let message = installationMode === InstallationMode.Install
            ? `Proceeding to install ansys-saf-cli version ${SAF_CLI_VERSION}. It may take ~1-2 minutes.`
            : `A new version of ansys-saf-cli is available: ${SAF_CLI_VERSION}. Proceeding to update.`;

        vscode.window.showInformationMessage(message);

        const success = await this.installManagedSafCli(SAF_CLI_VERSION, installationMode);
        if (success) {
            await this.storeSafCliInfo(SAF_CLI_VERSION);
            vscode.window.showInformationMessage(
                `ansys-saf-cli ${SAF_CLI_VERSION} ${installationMode === InstallationMode.Install ? 'installed' : 'updated'} successfully.`
            );
            SAFSolutionsProvider.getInstance().refresh();
        }
    }

    async installManagedSafCli(version: string, mode: InstallationMode): Promise<boolean> {
        if (!this.context) {
            throw new Error('Extension context is not set in SystemService.');
        }

        try {
            await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Notification,
                    title: `${mode === InstallationMode.Install ? 'Installing' : 'Updating'} ansys-saf-cli ${version}`,
                    cancellable: false
                },
                async (progress) => {
                    progress.report({ message: 'Setting up virtual environment.', increment: 30 });
                    await this.createManagedVenv();

                    progress.report({ message: 'Installing ansys-saf-cli package.', increment: 30 });
                    await this.installSafCliPackage(version);

                    progress.report({ message: 'Installation done.', increment: 40 });
                }
            );
            return true;
        } catch (error) {
            vscode.window.showErrorMessage(
                `Failed to install ansys-saf-cli ${version}: ${error instanceof Error ? error.message : 'Unknown error'}`
            );
            return false;
        }
    }

    private async checkPythonVersion(): Promise<void> {
        if (!this.context) {
            throw new Error('Extension context is not set in SystemService.');
        }
        const packageJsonPath = path.join(this.context.extensionPath, 'package.json');
        // eslint-disable-next-line security/detect-non-literal-fs-filename
        const packageJsonRaw = await fs.promises.readFile(packageJsonPath, 'utf-8');
        const packageJson = JSON.parse(packageJsonRaw);
        // We assume the python range only includes major version 3.
        const minMinorPythonVersion = Number(packageJson.python?.minPythonVersion.split('.')[1]);
        const maxMinorPythonVersion = Number(packageJson.python?.maxPythonVersion.split('.')[1]);

        const pythonErrorMessage =
            `Please ensure that a stable Python version in the range (>=3.${minMinorPythonVersion}, <3.${maxMinorPythonVersion + 1}) ` +
            `is installed and available on your system's PATH environment variable`;
        try {
            const { stdout } = await execAsync(
                `python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"`
            );
            const [major, minor] = stdout.trim().split('.').map(Number);
            if (major !== 3 || minor < minMinorPythonVersion || minor > maxMinorPythonVersion) {
                throw new Error(`Python ${stdout.trim()} is not supported. ${pythonErrorMessage}`);
            }
        } catch (error) {
            if (error instanceof Error && error.message.includes('is not supported')) {
                throw error;
            }
            throw new Error(
                `Failed to check Python version: ${error instanceof Error ? error.message + `${pythonErrorMessage}`: 'Unknown error'}`
            );
        }
    }

    private async createManagedVenv(): Promise<void> {
        const venvPath = this.getManagedVenvPath();
        const parentDir = path.dirname(venvPath);
        // eslint-disable-next-line security/detect-non-literal-fs-filename
        if (!fs.existsSync(parentDir)) {
            // eslint-disable-next-line security/detect-non-literal-fs-filename
            fs.mkdirSync(parentDir, { recursive: true });
        }

        // eslint-disable-next-line security/detect-non-literal-fs-filename
        if (fs.existsSync(venvPath)) {
            fs.rmSync(venvPath, { recursive: true, force: true });
        }

        await this.checkPythonVersion();

        try {
            await execAsync(`python -m venv "${venvPath}"`);
        } catch (error) {
            throw new Error(`Failed to create virtual environment: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }

    private async installSafCliPackage(version: string): Promise<void> {
        const pythonExec = this.getManagedPythonPath();

        await execFileAsync(pythonExec, ['-m', 'pip', 'install', '--upgrade', 'pip']);

        await execFileAsync(pythonExec, [
            '-m',
            'pip',
            'install',
            `ansys-saf-cli==${version}`
        ]);
    }

    private async storeSafCliInfo(version: string): Promise<void> {
        if (!this.context) {
            throw new Error('Extension context is not set in SystemService.');
        }

        const safCliInfo = {
            executablePath: this.getSafCliExecutablePath(),
            version: version
        };

        await this.context.globalState.update('safCliInfo', safCliInfo);
    }

    async setEnvironmentVariable(key: string, value: string): Promise<void> {
        try {
            const args = [
                '-m',
                'ansys.saf.cli.integrations.solutions_manager',
                'set-env-var',
                '--key',
                key,
                '--value',
                value
            ];
            await execFileAsync(this.getManagedPythonPath(), args);
        } catch (error) {
            throw new Error(`Could not set environment variable: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }

    async validateCredentials(source: { name: string; url: string; priority: string }, username: string, password: string): Promise<boolean> {
        const escapedSourceJson = JSON.stringify(source);
        try {
            const args = [
                '-m',
                'ansys.saf.cli.integrations.solutions_manager',
                'validate-credentials',
                '--source',
                escapedSourceJson,
                '--username',
                username,
                '--password',
                password
            ];
            const { stdout } = await execFileAsync(this.getManagedPythonPath(), args);
            return stdout.trim().includes("Credentials are valid!");
        } catch (error) {
            throw new Error(`Could not validate credentials: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }

    private getPoetryEnvVarName(sourceName: string, type: "USERNAME" | "PASSWORD"): string {
        return `POETRY_HTTP_BASIC_${sourceName.toUpperCase().replace(/-/g, "_")}_${type}`;
    }

    async checkAndPromptForCredentials(source: { name: string; url: string; priority: string }): Promise<boolean> {
        const envUsername = process.env[this.getPoetryEnvVarName(source.name, "USERNAME")];
        const envPassword = process.env[this.getPoetryEnvVarName(source.name, "PASSWORD")];

        if (envUsername && envPassword) {
            const isValid = await this.validateCredentials(source, envUsername, envPassword);
            if (isValid) {
                return true;
            }
        }

        await this.promptAndValidateCredentials(source);
        return false;
    }

    private async promptAndValidateCredentials(source: { name: string; url: string; priority: string }): Promise<boolean> {
        const credentials = await this.askForCredentials(source);

        if (!credentials?.username || !credentials?.password) {
            throw new Error('PyPI username or password not provided');
        }

        const isValid = await this.validateCredentials(source, credentials.username, credentials.password);
        if (isValid) {
            await this.setEnvironmentVariable(this.getPoetryEnvVarName(source.name, "USERNAME"), credentials.username);
            await this.setEnvironmentVariable(this.getPoetryEnvVarName(source.name, "PASSWORD"), credentials.password);

            vscode.window.showWarningMessage(
                'Environment variables have been updated. To apply the changes, completely close all VS Code windows, reopen them, and run the command again.'
            );

            return false;
        }

        vscode.window.showErrorMessage('Invalid credentials. Please try again.');
        return this.promptAndValidateCredentials(source);
    }

    private async askForCredentials(source: { name: string; url: string; priority: string }): Promise<{ username: string; password: string } | null> {
        const username = await vscode.window.showInputBox({
            prompt: 'Enter your ' + source.name + ' username',
            ignoreFocusOut: true
        });

        const password = await vscode.window.showInputBox({
            prompt: 'Enter your ' + source.name + ' password',
            password: true,
            ignoreFocusOut: true
        });

        if (!username || !password) {
            return null;
        }

        return { username, password };
    }

    async executeCommand(executable: string, args: string[], options?: childProcess.ExecOptions): Promise<string> {
        try {
            const { stdout } = await execFileAsync(executable, args, options);
            return typeof stdout === 'string' ? stdout : stdout.toString();
        } catch (error) {
            throw new Error(`Command execution failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }

    async ensureDebugConfiguration(workspaceFolder: vscode.WorkspaceFolder): Promise<void> {
        const vscodeFolder = path.join(workspaceFolder.uri.fsPath, '.vscode');
        // eslint-disable-next-line security/detect-non-literal-fs-filename
        if (!fs.existsSync(vscodeFolder)) {
            // eslint-disable-next-line security/detect-non-literal-fs-filename
            fs.mkdirSync(vscodeFolder);
        }

        let debugPort = 5724;
        let dashDebugPort = 5725;

        // Use EnvironmentService to read debug ports
        // For debug configuration, we use the workspace folder path as the solution path
        try {
            const envService = new EnvironmentService(this.context);
            await envService.loadForSolution(workspaceFolder.uri.fsPath);

            const apiPortValue = envService.getVariableValue('GLOW_DEBUG_API_PORT');
            if (apiPortValue !== undefined && apiPortValue !== null) {
                const portStr = String(apiPortValue);
                const parsedPort = parseInt(portStr, 10);
                if (!isNaN(parsedPort) && parsedPort > 0) {
                    debugPort = parsedPort;
                }
            }

            const uiPortValue = envService.getVariableValue('GLOW_DEBUG_UI_PORT');
            if (uiPortValue !== undefined && uiPortValue !== null) {
                const portStr = String(uiPortValue);
                const parsedPort = parseInt(portStr, 10);
                if (!isNaN(parsedPort) && parsedPort > 0) {
                    dashDebugPort = parsedPort;
                }
            }
        } catch (err) {
            console.error('Error reading environment variables:', err);
            // Fall back to defaults if environment service fails
        }

        const launchJsonPath = path.join(vscodeFolder, 'launch.json');
        let launchJson: any;

        // If launch.json exists, read it to preserve any custom configurations
        // eslint-disable-next-line security/detect-non-literal-fs-filename
        if (fs.existsSync(launchJsonPath)) {
            try {
                // eslint-disable-next-line security/detect-non-literal-fs-filename
                const launchJsonContent = fs.readFileSync(launchJsonPath, 'utf-8');
                launchJson = JSON.parse(launchJsonContent);

                // Update or add the Python Remote Attach configuration
                let pythonRemoteAttachConfig = launchJson.configurations.find(
                    (config: any) => config.name === "Python: Remote Attach"
                );

                if (pythonRemoteAttachConfig) {
                    // Update existing configuration with new port
                    pythonRemoteAttachConfig.connect.port = debugPort;
                    pythonRemoteAttachConfig.justMyCode = false;
                } else {
                    launchJson.configurations.push({
                        "name": "Python: Remote Attach",
                        "type": "python",
                        "request": "attach",
                        "connect": {
                            "host": "localhost",
                            "port": debugPort
                        },
                        "pathMappings": [
                            {
                                "localRoot": "${workspaceFolder}",
                                "remoteRoot": "${workspaceFolder}"
                            }
                        ],
                        "justMyCode": false
                    });
                }

                // Update or add the Python Remote Attach Dash configuration
                let pythonRemoteAttachDashConfig = launchJson.configurations.find(
                    (config: any) => config.name === "Python: Remote Attach Dash"
                );

                if (pythonRemoteAttachDashConfig) {
                    pythonRemoteAttachDashConfig.connect.port = dashDebugPort;
                    pythonRemoteAttachDashConfig.justMyCode = false;
                } else {
                    // Add the configuration if it doesn't exist
                    launchJson.configurations.push({
                        "name": "Python: Remote Attach Dash",
                        "type": "python",
                        "request": "attach",
                        "connect": {
                            "host": "localhost",
                            "port": dashDebugPort
                        },
                        "pathMappings": [
                            {
                                "localRoot": "${workspaceFolder}",
                                "remoteRoot": "${workspaceFolder}"
                            }
                        ],
                        "justMyCode": false
                    });
                }
            } catch (err) {
                console.error('Error parsing existing launch.json:', err);
                launchJson = null;
            }
        }

        // If we couldn't parse the existing file or it doesn't exist, create a new one
        if (!launchJson) {
            launchJson = {
                "configurations": [
                    {
                        "name": "Python: Remote Attach",
                        "type": "python",
                        "request": "attach",
                        "connect": {
                            "host": "localhost",
                            "port": debugPort
                        },
                        "pathMappings": [
                            {
                                "localRoot": "${workspaceFolder}",
                                "remoteRoot": "${workspaceFolder}"
                            }
                        ],
                        "justMyCode": false
                    },
                    {
                        "name": "Python: Remote Attach Dash",
                        "type": "python",
                        "request": "attach",
                        "connect": {
                            "host": "localhost",
                            "port": dashDebugPort
                        },
                        "pathMappings": [
                            {
                                "localRoot": "${workspaceFolder}",
                                "remoteRoot": "${workspaceFolder}"
                            }
                        ],
                        "justMyCode": false
                    }
                ]
            };
        }


        // eslint-disable-next-line security/detect-non-literal-fs-filename
        fs.writeFileSync(launchJsonPath, JSON.stringify(launchJson, null, 4));
    }

    async isSAFCliInstalled(): Promise<boolean> {
        const version = await this.getInstalledSafCliVersion();
        return version !== null;
    }

    async checkWindowsLongPaths(): Promise<boolean> {
        if (process.platform !== 'win32') {
            return true;
        }

        try {
            const regKey = new Registry({
                hive: Registry.HKLM,
                key: String.raw`\SYSTEM\CurrentControlSet\Control\FileSystem`
            });

            return new Promise<boolean>((resolve) => {
                regKey.get('LongPathsEnabled', (err: Error | null, item?: any) => {
                    if (err) {
                        console.warn('Failed to read Windows Long Paths registry key:', err instanceof Error ? err.message : String(err));
                        this.showLongPathsDisabledWarning();
                        resolve(false);
                        return;
                    }

                    const isEnabled = !!item && item.value === '0x1';
                    if (!isEnabled) {
                        this.showLongPathsDisabledWarning();
                    }
                    resolve(isEnabled);
                });
            });
        } catch (error) {
            console.warn('Unexpected error checking Windows Long Paths:', error instanceof Error ? error.message : String(error));
            this.showLongPathsDisabledWarning();
            return false;
        }
    }

    private showLongPathsDisabledWarning(): void {
        vscode.window.showWarningMessage(
            'Windows Long Paths support is not enabled. ansys-saf-cli installation requires long paths. ' +
            'You can enable it by searching for "Enable long paths" in Windows settings. ' +
            'For more details, see: https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation?tabs=registry#registry-setting-to-enable-long-paths'
        );
    }

    async getSafCliVersionOnVenv(venvPath: string): Promise<string | null> {
        try {
            // eslint-disable-next-line security/detect-non-literal-fs-filename
            if (!fs.existsSync(venvPath)) {
                return null;
            }

            let stdout = await execFileAsync(this.getVenvPythonExecutable(venvPath), ['-m', 'pip', 'show', 'ansys-saf-cli']);
            const versionLine = stdout.stdout
            .split('\n')
            .find(line => line.toLowerCase().startsWith('version:'));

            const version = versionLine?.split(':')[1].trim();
            return version || null;
        } catch {
            return null;
        }
    }
}

export const systemService = new SystemService();