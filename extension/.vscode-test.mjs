import { defineConfig } from '@vscode/test-cli';

const args = process.argv.slice(2);
const dashIndex = args.indexOf('--');
const testFile = dashIndex >= 0 && args[dashIndex + 1]
    ? args[dashIndex + 1]
    : 'out/test/integration/**/*.test.js';

export default defineConfig({
    files: testFile,
    version: 'stable',
    workspaceFolder: './test/fixtures/workspace',
    extensionDevelopmentPath: './out',
    mocha: {
        ui: 'bdd',
        timeout: 90000, // give some time to install SAF CLI
        color: true,
        reporter: 'spec',
        require: ['./out/test/integration/setup.integration.js']
    },
    launchArgs: [
        '--disable-extensions',
        '--disable-workspace-trust',
        '--enable-proposed-api', 'Ansys.solutions-manager'
    ]
});