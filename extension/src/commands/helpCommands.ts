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
import { CommandContext } from '../managers/CommandManager';

export class HelpCommands {
    private readonly githubRepoUrl = 'https://github.com/ansys/saf';
    private readonly githubIssuesUrl = 'https://github.com/ansys/saf/issues/new/choose';
    private readonly extensionId = 'ansys.solutions-manager';
    private readonly marketplaceUrl = `https://marketplace.visualstudio.com/items?itemName=${this.extensionId}`;
    private readonly feedbackUrl = 'https://forms.office.com/r/K0bgjtbqSx';

    constructor(private context: CommandContext) {}

    public async openVSCodeExtensionPage(): Promise<void> {
        try {
            // Method 1: Direct extension open command
            await vscode.commands.executeCommand('extension.open', this.extensionId);

        } catch (error) {
            // Method 2: Open extensions view and show search instruction
            try {
                await vscode.commands.executeCommand('workbench.view.extensions');

                // Use VS Code's built-in search command
                setTimeout(async () => {
                    try {
                        await vscode.commands.executeCommand('workbench.extensions.search', this.extensionId);
                    } catch (searchError) {
                        console.log('Search command failed:', searchError);
                    }
                }, 500);

                vscode.window.showInformationMessage(
                    'Extensions view opened. The Solutions Manager extension should be visible.',
                    'OK'
                );

            } catch (viewError) {
                // Method 3: Provide manual instructions
                const message = `To access the extension documentation:
1. Open Extensions view (Ctrl+Shift+X)
2. Search for "Solutions Manager" or "${this.extensionId}"
3. Click on the extension to see its details and documentation`;

                const action = await vscode.window.showInformationMessage(
                    message,
                    { modal: true },
                    'Open Extensions View',
                    'Open GitHub Docs',
                    'Close'
                );

                switch (action) {
                    case 'Open Extensions View':
                        await vscode.commands.executeCommand('workbench.view.extensions');
                        break;
                    case 'Open GitHub Docs':
                        await this.openGitHubRepo();
                        break;
                }
            }
        }
    }

    public async openExtensionHelp(): Promise<void> {
        try {
            const extensionId = 'ansys.solutions-manager';

            await vscode.commands.executeCommand('extension.open', extensionId);

        } catch (error) {
            vscode.window.showErrorMessage(`Failed to open extension help: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }

    public async openGitHubIssues(): Promise<void> {
        const success = await vscode.env.openExternal(vscode.Uri.parse(this.githubIssuesUrl));

        if (!success) {
            throw new Error('Failed to open GitHub issues URL');
        }

        vscode.window.showInformationMessage(
            'GitHub Issues page opened.'
        );
    }

    public async openGitHubRepo(): Promise<void> {
        const success = await vscode.env.openExternal(vscode.Uri.parse(this.githubRepoUrl));

        if (!success) {
            throw new Error('Failed to open GitHub repository URL');
        }

        vscode.window.showInformationMessage(
            'GitHub repository opened.'
        );
    }

    public async showAboutDialog(): Promise<void> {
        const extensionInfo = vscode.extensions.getExtension(this.extensionId);
        const version = extensionInfo?.packageJSON?.version || 'Unknown';

        const aboutMessage = `
**Solutions Manager Extension**

Version: ${version}
Publisher: Ansys

A comprehensive Visual Studio Code extension for managing and developing Solution Applications.

**Features:**
• Solution creation and management
• Development environment setup
• Dependency management
• Debug support

**Support:**
• Documentation: GitHub Repository
• Issues & Feedback: GitHub Issues
• Extension Marketplace: VS Code Extensions
        `.trim();

        const action = await vscode.window.showInformationMessage(
            aboutMessage,
            { modal: true },
            'Open GitHub Repository',
            'Report Issue',
            'Rate Extension'
        );

        switch (action) {
            case 'Open GitHub Repository':
                await this.openGitHubRepo();
                break;
            case 'Report Issue':
                await this.openGitHubIssues();
                break;
            case 'Rate Extension':
                await this.openExtensionMarketplace();
                break;
        }
    }

    public async showQuickHelp(): Promise<void> {
        const quickHelpItems = [
            {
                label: '$(rocket) Create New Solution',
                description: 'Create a new SAF solution',
                command: 'solutions-manager.createSolution'
            },
            {
                label: '$(gear) Install Dev Environment',
                description: 'Set up development environment for current solution',
                command: 'solutions-manager.installDevEnvironment'
            },
            {
                label: '$(play) Run Solution',
                description: 'Configure and run solution with various options',
                command: 'workbench.view.extension.solutions-manager'
            },
            {
                label: '$(bug) Debug Transaction Methods',
                description: 'Start debugging transaction methods',
                command: 'solutions-manager.debugtransactionmethods'
            },
            {
                label: '$(package) Manage Dependencies',
                description: 'Add, update, or remove Poetry dependencies',
                command: 'workbench.view.extension.solutions-manager'
            },
            {
                label: '$(settings-gear) Environment Configuration',
                description: 'Configure SAF environment variables',
                command: 'solutions-manager.showEnvironmentConfig'
            },
            {
                label: '$(book) Documentation',
                description: 'Open extension documentation',
                command: 'solutions-manager.openExtensionHelp'
            },
            {
                label: '$(issues) Report Issue',
                description: 'Report a bug or request a feature',
                command: 'solutions-manager.openGitHubIssues'
            }
        ];

        const selectedItem = await vscode.window.showQuickPick(quickHelpItems, {
            placeHolder: 'Select an action or get help',
            title: 'Solutions Manager - Quick Help',
            matchOnDescription: true
        });

        if (selectedItem) {
            await vscode.commands.executeCommand(selectedItem.command);
        }
    }

    public async showTroubleshootingGuide(): Promise<void> {
        const troubleshootingPanel = vscode.window.createWebviewPanel(
            'solutionsTroubleshooting',
            'Solutions Manager - Troubleshooting',
            vscode.ViewColumn.One,
            { enableScripts: false }
        );

        troubleshootingPanel.webview.html = this.getTroubleshootingHtml();
    }

    private async openExtensionMarketplace(): Promise<void> {
        const success = await vscode.env.openExternal(vscode.Uri.parse(this.marketplaceUrl));

        if (!success) {
            throw new Error('Failed to open extension marketplace');
        }

        vscode.window.showInformationMessage(
            'Extension marketplace page opened.'
        );
    }

    public async openFeedbackForm(): Promise<void> {
        const success = await vscode.env.openExternal(vscode.Uri.parse(this.feedbackUrl));

        if (!success) {
            throw new Error('Failed to open feedback form URL');
        }

        vscode.window.showInformationMessage(
            'Feedback form opened.'
        );
    }

    private getTroubleshootingHtml(): string {
        return `<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Troubleshooting Guide</title>
            <style>
                body {
                    font-family: var(--vscode-font-family);
                    color: var(--vscode-foreground);
                    background-color: var(--vscode-editor-background);
                    padding: 20px;
                    line-height: 1.6;
                }
                h1, h2, h3 {
                    color: var(--vscode-editor-foreground);
                }
                .section {
                    margin-bottom: 30px;
                    padding: 15px;
                    border-radius: 5px;
                    background-color: var(--vscode-editor-inactiveSelectionBackground);
                }
                .problem {
                    font-weight: bold;
                    color: var(--vscode-editorWarning-foreground);
                }
                .solution {
                    margin-top: 10px;
                    padding-left: 20px;
                }
                code {
                    background-color: var(--vscode-textBlockQuote-background);
                    padding: 2px 4px;
                    border-radius: 3px;
                    font-family: var(--vscode-editor-font-family);
                }
                ul {
                    padding-left: 20px;
                }
                .note {
                    padding: 10px;
                    border-left: 4px solid var(--vscode-notificationsInfoIcon-foreground);
                    background-color: var(--vscode-textBlockQuote-background);
                    margin: 10px 0;
                }
            </style>
        </head>
        <body>
            <h1>Solutions Manager - Troubleshooting Guide</h1>

            <div class="section">
                <h2>🔧 Environment Setup Issues</h2>

                <div class="problem">Problem: "Environment is not set up" message</div>
                <div class="solution">
                    <strong>Solutions:</strong>
                    <ul>
                        <li>Ensure Python 3.10+ is installed and accessible</li>
                        <li>Verify network connection to your configured package index</li>
                        <li>Try running "Install Dev Environment" command</li>
                    </ul>
                </div>

                <div class="problem">Problem: Python installation not detected</div>
                <div class="solution">
                    <strong>Solutions:</strong>
                    <ul>
                        <li>Install Python from <a href="https://www.python.org/downloads/">python.org</a></li>
                        <li>Ensure Python is added to system PATH</li>
                        <li>On Windows, try using Python Launcher: <code>py --list</code></li>
                        <li>Restart VS Code after Python installation</li>
                    </ul>
                </div>
            </div>

            <div class="section">
                <h2>🐛 Debug Connection Problems</h2>

                <div class="problem">Problem: Cannot connect to debug port</div>
                <div class="solution">
                    <strong>Solutions:</strong>
                    <ul>
                        <li>Verify Python extension is installed and configured</li>
                        <li>Check if ports 5724/5725 are available</li>
                        <li>Ensure solution is running in debug mode</li>
                        <li>Try setting custom debug ports in .env file:
                            <code>GLOW_DEBUG_API_PORT=5724</code><br>
                            <code>GLOW_DEBUG_UI_PORT=5725</code>
                        </li>
                    </ul>
                </div>

                <div class="problem">Problem: Breakpoints not hit</div>
                <div class="solution">
                    <strong>Solutions:</strong>
                    <ul>
                        <li>Ensure breakpoints are set in transaction methods</li>
                        <li>Verify debugger is attached (check debug console)</li>
                        <li>Try interacting with solution UI to trigger methods</li>
                        <li>Check that <code>justMyCode</code> is set to false in debug config</li>
                    </ul>
                </div>
            </div>

            <div class="section">
                <h2>📦 Dependency Management Issues</h2>

                <div class="problem">Problem: Invalid version constraint</div>
                <div class="solution">
                    <strong>Valid formats:</strong>
                    <ul>
                        <li>Exact: <code>1.0.0</code></li>
                        <li>Caret: <code>^1.0.0</code></li>
                        <li>Tilde: <code>~1.0.0</code></li>
                        <li>Range: <code>>=1.0.0</code>, <code><=2.0.0</code></li>
                        <li>Development: <code>1.0dev1</code></li>
                    </ul>
                </div>

                <div class="problem">Problem: Poetry command fails</div>
                <div class="solution">
                    <strong>Solutions:</strong>
                    <ul>
                        <li>Ensure virtual environment is activated</li>
                        <li>Check Poetry is installed in virtual environment</li>
                        <li>Verify pyproject.toml file exists and is valid</li>
                        <li>Try running poetry command manually in terminal</li>
                    </ul>
                </div>
            </div>

            <div class="section">
                <h2>🐳 Docker/HPS Issues</h2>

                <div class="problem">Problem: Docker not found or not running</div>
                <div class="solution">
                    <strong>Solutions:</strong>
                    <ul>
                        <li>Install Docker Desktop from <a href="https://www.docker.com/products/docker-desktop">docker.com</a></li>
                        <li>Start Docker Desktop application</li>
                        <li>Verify Docker is running: <code>docker --version</code></li>
                        <li>Check Docker daemon is accessible</li>
                    </ul>
                </div>

                <div class="problem">Problem: HPS services not starting</div>
                <div class="solution">
                    <strong>Solutions:</strong>
                    <ul>
                        <li>Ensure Docker has sufficient resources (4GB+ RAM)</li>
                        <li>Check if required ports are available (8443)</li>
                        <li>Verify HPS core services archive is properly extracted</li>
                        <li>Check Docker login credentials for private registry</li>
                    </ul>
                </div>
            </div>

            <div class="section">
                <h2>🔍 General Troubleshooting</h2>

                <div class="note">
                    <strong>Getting More Help:</strong><br>
                    • Check VS Code Output panel for extension logs<br>
                    • Review terminal output for detailed error messages<br>
                    • Verify solution structure follows expected conventions<br>
                    • Ensure all required files exist in solution directory<br>
                    • Try restarting VS Code if issues persist
                </div>

                <div class="problem">Problem: Extension commands not working</div>
                <div class="solution">
                    <strong>Solutions:</strong>
                    <ul>
                        <li>Reload VS Code window: <code>Ctrl+Shift+P</code> → "Developer: Reload Window"</li>
                        <li>Check extension is enabled in Extensions panel</li>
                        <li>Verify workspace contains valid solution structure</li>
                        <li>Check VS Code developer console for errors</li>
                    </ul>
                </div>
            </div>

            <div class="section">
                <h2>📞 Getting Support</h2>
                <p>If you continue to experience issues:</p>
                <ul>
                    <li><strong>Report bugs:</strong> <a href="${this.githubIssuesUrl}">GitHub Issues</a></li>
                    <li><strong>Documentation:</strong> <a href="${this.githubRepoUrl}">GitHub Repository</a></li>
                    <li><strong>Feature requests:</strong> <a href="${this.githubIssuesUrl}">GitHub Issues</a></li>
                </ul>

                <div class="note">
                    When reporting issues, please include:
                    <ul>
                        <li>VS Code version and operating system</li>
                        <li>Extension version</li>
                        <li>Steps to reproduce the problem</li>
                        <li>Error messages from Output panel</li>
                        <li>Solution structure (if relevant)</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>`;
    }
}