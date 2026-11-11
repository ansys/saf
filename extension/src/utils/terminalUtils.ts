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


import * as vscode from 'vscode';

/**
 * Create a terminal with custom environment variables injected.
 * Used for running SAF commands with configured environment variables.
 */
export function createTerminalWithEnvironment(
    name: string,
    environmentVariables: Record<string, string>,
    cwd?: string
): vscode.Terminal {
    // Merge process.env with injected environment variables
    // Injected variables take priority over process.env
    const mergedEnv = {
        ...process.env,
        ...environmentVariables
    };

    const options: vscode.TerminalOptions = {
        name,
        cwd,
        env: mergedEnv
    };

    const terminal = vscode.window.createTerminal(options);
    terminal.show();

    return terminal;
}

/**
 * Create a new terminal with the given name and working directory
 */
export function createTerminal(name: string, cwd?: string): vscode.Terminal {
    // Dispose existing terminal with same name
    const existingTerminal = vscode.window.terminals.find(terminal => terminal.name === name);
    if (existingTerminal) {
        existingTerminal.dispose();
    }

    const options: vscode.TerminalOptions = {
        name,
        cwd
    };

    const terminal = vscode.window.createTerminal(options);
    terminal.show();

    return terminal;
}

/**
 * Create a terminal with specific shell for cross-platform compatibility
 */
export function createTerminalWithShell(name: string, cwd?: string, useWSL: boolean = false): vscode.Terminal {
    const existingTerminal = vscode.window.terminals.find(terminal => terminal.name === name);
    if (existingTerminal) {
        existingTerminal.dispose();
    }

    let options: vscode.TerminalOptions = {
        name,
        cwd
    };

    if (process.platform === 'win32' && useWSL) {
        options.shellPath = 'wsl.exe';
    } else if (process.platform === 'win32') {
        options.shellPath = 'cmd.exe';
    } else {
        options.shellPath = '/bin/bash';
    }

    const terminal = vscode.window.createTerminal(options);
    terminal.show();

    return terminal;
}

/**
 * Safely dispose a terminal if it exists
 */
export function disposeTerminal(terminal: vscode.Terminal | undefined): void {
    if (terminal && terminal.exitStatus === undefined) {
        terminal.dispose();
    }
}

/**
 * Execute a command in the given terminal using shell integration for reliability
 */
export async function executeCommandInTerminal(terminal: vscode.Terminal, command: string): Promise<void> {
    return new Promise<void>((resolve, reject) => {
        let executed = false;
        let timeoutId: NodeJS.Timeout | undefined;
        let shellIntegrationDisposable: vscode.Disposable | undefined;
        let closeDisposable: vscode.Disposable | undefined;

        const disposeListeners = () => {
            shellIntegrationDisposable?.dispose();
            shellIntegrationDisposable = undefined;
            closeDisposable?.dispose();
            closeDisposable = undefined;
        };

        const executeAndWait = async (shellIntegration: vscode.TerminalShellIntegration) => {
            try {
                const execution = shellIntegration.executeCommand(command);
                for await (const chunk of execution.read()) {
                    // consume output until command completes
                }
                clearTimeout(timeoutId);
                if (!executed) {
                    executed = true;
                    resolve();
                }
            } catch (error) {
                clearTimeout(timeoutId);
                if (!executed) {
                    executed = true;
                    reject(error);
                }
            } finally {
                disposeListeners();
            }
        };

        if (terminal.shellIntegration) {
            executeAndWait(terminal.shellIntegration).catch(reject);
        } else {
            shellIntegrationDisposable = vscode.window.onDidChangeTerminalShellIntegration(({terminal: t, shellIntegration}) => {
                if (t === terminal) {
                    clearTimeout(timeoutId);
                    executeAndWait(shellIntegration).catch(reject);
                    shellIntegrationDisposable?.dispose();
                }
            });

            // Resolve early if the terminal is closed before the fallback timer fires
            closeDisposable = vscode.window.onDidCloseTerminal(closedTerminal => {
                if (closedTerminal === terminal) {
                    clearTimeout(timeoutId);
                    shellIntegrationDisposable?.dispose();
                    closeDisposable?.dispose();
                    if (!executed) {
                        executed = true;
                        resolve();
                    }
                }
            });
            // Fallback to sendText if integration doesn't activate within 3s
            timeoutId = setTimeout(() => {
                if (executed) {
                    return;
                }

                shellIntegrationDisposable?.dispose();

                if (!terminal.shellIntegration) {
                    if (terminal.exitStatus !== undefined) {
                        clearTimeout(timeoutId);
                        closeDisposable?.dispose();
                        executed = true;
                        resolve();
                        return;
                    }

                    try {
                        terminal.sendText(command);
                        // closeDisposable remains active — it resolves the promise when the terminal exits
                        return;
                    } catch {
                        // sendText threw, terminal is already dead — resolve immediately
                        clearTimeout(timeoutId);
                        closeDisposable?.dispose();
                        if (!executed) {
                            executed = true;
                            resolve();
                        }
                        return;
                    }
                }
            }, 3000);
        }
    });
}

export function isTerminalActive(name: string): boolean {
    const terminal = vscode.window.terminals.find(t => t.name === name);
    return terminal !== undefined && terminal.exitStatus === undefined;
}

/**
 * Get or create a terminal with the given name
 */
export function getOrCreateTerminal(name: string, cwd?: string): vscode.Terminal {
    const existingTerminal = vscode.window.terminals.find(terminal =>
        terminal.name === name && terminal.exitStatus === undefined
    );

    if (existingTerminal) {
        return existingTerminal;
    }

    return createTerminal(name, cwd);
}

/**
 * Terminal pool manager for reusing terminals
 */
export class TerminalPool {
    private static terminals: Map<string, vscode.Terminal> = new Map();

    static getTerminal(name: string, cwd?: string): vscode.Terminal {
        const existing = this.terminals.get(name);

        if (existing && existing.exitStatus === undefined) {
            return existing;
        }

        const newTerminal = createTerminal(name, cwd);
        this.terminals.set(name, newTerminal);

        // Clean up when terminal exits
        vscode.window.onDidCloseTerminal(closedTerminal => {
            if (closedTerminal === newTerminal) {
                this.terminals.delete(name);
            }
        });

        return newTerminal;
    }

    static disposeAll(): void {
        this.terminals.forEach(terminal => {
            if (terminal.exitStatus === undefined) {
                terminal.dispose();
            }
        });
        this.terminals.clear();
    }

    static dispose(name: string): void {
        const terminal = this.terminals.get(name);
        if (terminal) {
            terminal.dispose();
            this.terminals.delete(name);
        }
    }
}