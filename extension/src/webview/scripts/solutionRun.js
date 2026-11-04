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


const vscode = acquireVsCodeApi();
const existingState = vscode.getState();
const state = {
    solution: '',
    portal: false,
    debug: false,
    uiDebugger: false,
    noUi: false,
    browser: false,
    logLevel: '',
    project: '',
    envFile: ''
};

function isValidValue(value) {
    return value !== undefined && value !== null && value !== 'undefined';
}

if (existingState) {
    Object.keys(state).forEach(key => {
    // eslint-disable-next-line security/detect-object-injection
    if (isValidValue(existingState[key])) {
        // eslint-disable-next-line security/detect-object-injection
        state[key] = existingState[key];
    }
    });
}

const solutionSelect = document.getElementById('solution-select');
const browseSolutionBtn = document.getElementById('browse-solution-btn');
const portalCheckbox = document.getElementById('portal');
const browserCheckbox = document.getElementById('browser');
const debugCheckbox = document.getElementById('debug');
const uiDebuggerCheckbox = document.getElementById('uiDebugger');
const noUiCheckbox = document.getElementById('noUi');
const logLevelSelect = document.getElementById('logLevel');
const projectInput = document.getElementById('project');
const configEnvBtn = document.getElementById('config-env-btn');
const envFileInput = document.getElementById('envFile');
const browseBtn = document.getElementById('browse-btn');
const commandPreview = document.getElementById('command-preview');
const runBtn = document.getElementById('run-btn');
const copyCommandBtn = document.getElementById('copy-command-btn');

function checkCommandOverflow() {
    const preview = document.querySelector('.command-preview');
    const code = document.getElementById('command-preview');
    if (code.scrollWidth > preview.clientWidth) {
    code.classList.add('overflow');
    } else {
    code.classList.remove('overflow');
    }
}

function restoreState() {
    portalCheckbox.checked = state.portal;
    debugCheckbox.checked = state.debug;
    uiDebuggerCheckbox.checked = state.uiDebugger;
    noUiCheckbox.checked = state.noUi;
    browserCheckbox.checked = state.browser;
    logLevelSelect.value = state.logLevel;
    projectInput.value = state.project;
    envFileInput.value = state.envFile;
}

function updateDisabledStates() {
    const noUi = noUiCheckbox.checked;
    const debug = debugCheckbox.checked;
    const uiDebugger = uiDebuggerCheckbox.checked;
    const browser = browserCheckbox.checked;
    const portal = portalCheckbox.checked;
    const project = projectInput.value.trim();

    browserCheckbox.disabled = noUi;
    portalCheckbox.disabled = noUi || project.length > 0;
    uiDebuggerCheckbox.disabled = noUi;
    noUiCheckbox.disabled = browser || portal || uiDebugger;
    projectInput.disabled = portal;
}

function saveState() {
    state.solution = solutionSelect.value;
    state.portal = portalCheckbox.checked;
    state.debug = debugCheckbox.checked;
    state.uiDebugger = uiDebuggerCheckbox.checked;
    state.noUi = noUiCheckbox.checked;
    state.browser = browserCheckbox.checked;
    state.logLevel = logLevelSelect.value;
    state.project = projectInput.value;
    state.envFile = envFileInput.value;
    vscode.setState(state);
}

function updateCommandPreview() {
    let cmd = 'saf run';
    const solution = solutionSelect.value;

    if (solution) {
    cmd += ' ' + solution;
    }

    if (portalCheckbox.checked) {cmd += ' --portal';}
    if (browserCheckbox.checked) {cmd += ' --browser';}
    if (debugCheckbox.checked) {cmd += ' --debug';}
    if (uiDebuggerCheckbox.checked) {cmd += ' --ui-debugger';}
    if (noUiCheckbox.checked) {cmd += ' --no-ui';}

    const logLevel = logLevelSelect.value;
    if (logLevel) {cmd += ' --loglevel ' + logLevel;}

    const project = projectInput.value.trim();
    if (project) {cmd += ' --project "' + project + '"';}

    const envFile = envFileInput.value.trim();
    if (envFile) {cmd += ' --env-file "' + envFile + '"';}

    commandPreview.textContent = cmd;
    checkCommandOverflow();
}

solutionSelect.addEventListener('change', function() {
    saveState();
    updateCommandPreview();
    vscode.postMessage({ command: 'solution-changed', solution: this.value });
});

configEnvBtn.addEventListener('click', () => {
    vscode.postMessage({ command: 'show-env-config' });
});

projectInput.addEventListener('input', function() {
    saveState();
    updateDisabledStates();
    updateCommandPreview();
});

logLevelSelect.addEventListener('change', function() {
    saveState();
    updateCommandPreview();
});

envFileInput.addEventListener('input', function() {
    saveState();
    updateCommandPreview();
});

browseBtn.addEventListener('click', () => {
    vscode.postMessage({ command: 'browse-env-file' });
});

browseSolutionBtn.addEventListener('click', function() {
    const previousSelection = state.solution || '';
    vscode.postMessage({
    command: 'select-another-solution',
    previousSelection: previousSelection
    });
});

copyCommandBtn.addEventListener('click', () => {
    const commandText = commandPreview.textContent || '';
    navigator.clipboard.writeText(commandText).then(() => {
    copyCommandBtn.textContent = '✔';
    setTimeout(() => {
        copyCommandBtn.textContent = '⧉';
    }, 1200);
    }).catch(err => {
    console.error('Failed to copy command:', err);
    });
});

runBtn.addEventListener('click', () => {
    vscode.postMessage({
    command: 'run-solution',
    options: {
        solution: solutionSelect.value,
        portal: portalCheckbox.checked,
        debug: debugCheckbox.checked,
        uiDebugger: uiDebuggerCheckbox.checked,
        noUi: noUiCheckbox.checked,
        browser: browserCheckbox.checked,
        logLevel: logLevelSelect.value,
        project: projectInput.value.trim(),
        envFile: envFileInput.value.trim()
    }
    });
});

window.addEventListener('message', (event) => {
    const message = event.data;

    if (message.type === 'env-file-selected') {
    envFileInput.value = message.path;
    saveState();
    updateCommandPreview();
    }
    else if (message.type === 'set-selected-solution') {
    if (message.selectedSolution) {
        const optionExists = Array.from(solutionSelect.options).some(
        option => option.value === message.selectedSolution
        );

        if (optionExists) {
        solutionSelect.value = message.selectedSolution;
        } else {
        const tempOption = document.createElement('option');
        tempOption.value = message.selectedSolution;
        tempOption.text = message.selectedSolution + (message.displayName ? ' (' + message.displayName + ')' : '');
        tempOption.setAttribute('data-temp', 'true');
        solutionSelect.add(tempOption);
        solutionSelect.value = message.selectedSolution;
        }

        state.solution = message.selectedSolution;
        saveState();
        vscode.postMessage({ command: 'solution-changed', solution: message.selectedSolution });
        updateCommandPreview();
    }
    }
    else if (message.type === 'solutions-loaded') {
    const tempOption = Array.from(solutionSelect.options).find(
        opt => opt.getAttribute('data-temp') === 'true'
    );
    if (tempOption) {
        tempOption.remove();
    }

    while (solutionSelect.options.length > 1) {
        solutionSelect.remove(1);
    }

    message.solutions.forEach(solution => {
        const option = document.createElement('option');
        option.value = solution.name;
        option.text = solution.name + (solution.displayName ? ' (' + solution.displayName + ')' : '');
        solutionSelect.add(option);
    });

    if (message.selectedSolution) {
        solutionSelect.value = message.selectedSolution;
        state.solution = message.selectedSolution;
        saveState();
        vscode.postMessage({ command: 'solution-changed', solution: message.selectedSolution });
    }

    updateCommandPreview();
    }
    else if (message.type === 'revert-solution') {
    solutionSelect.value = message.previousSelection || '';
    state.solution = message.previousSelection || '';
    saveState();
    updateCommandPreview();
    }
});

['portal', 'debug', 'uiDebugger', 'noUi', 'browser'].forEach(id => {
    document.getElementById(id).addEventListener('change', () => {
    saveState();
    updateDisabledStates();
    updateCommandPreview();
    });
});

restoreState();
updateDisabledStates();
updateCommandPreview();

vscode.postMessage({ command: 'get-status' });