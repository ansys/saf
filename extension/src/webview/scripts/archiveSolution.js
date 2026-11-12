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
    selectedSolution: '',
    outputPath: '',
    archiveFilename: '',
    archiveExtension: '.saf'
};

if (existingState) {
    Object.keys(state).forEach(key => {
        // eslint-disable-next-line security/detect-object-injection
        const value = existingState[key];
        if (value !== undefined && value !== null) {
            // eslint-disable-next-line security/detect-object-injection
            state[key] = value;
        }
    });
}

const solutionSelect = document.getElementById('solution-select');
const browseSolutionBtn = document.getElementById('browse-solution-btn');
const outputPathInput = document.getElementById('output-path');
const browseOutputBtn = document.getElementById('browse-output-btn');
const archiveFilenameInput = document.getElementById('archive-filename');
const archiveExtensionInput = document.getElementById('archive-extension');
const archiveBtn = document.getElementById('archive-btn');
const commandPreview = document.getElementById('command-preview');
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
    solutionSelect.value = state.selectedSolution || '';
    outputPathInput.value = state.outputPath || '';
    archiveFilenameInput.value = state.archiveFilename || '';
    archiveExtensionInput.value = state.archiveExtension || '.saf';
    updateCommandPreview();
}

function saveState() {
    state.selectedSolution = solutionSelect.value;
    state.outputPath = outputPathInput.value;
    state.archiveFilename = archiveFilenameInput.value;
    state.archiveExtension = archiveExtensionInput.value;
    vscode.setState(state);
}

function getSelectedRootDir() {
    const option = solutionSelect.options[solutionSelect.selectedIndex];
    return option ? option.getAttribute('data-root-directory') : '';
}

function updateCommandPreview() {
    const solution = solutionSelect.value;
    let command = 'saf archive';

    if (solution) {
        const rootDir = getSelectedRootDir();
        command += rootDir ? ' "' + rootDir + '"' : ' "<solution root>"';
    }

    const outputPath = outputPathInput.value.trim();
    if (outputPath) {
        command += ' --path "' + outputPath + '"';
    }

    const filename = archiveFilenameInput.value.trim();
    if (filename) {
        command += ' --filename "' + filename + '"';
    }

    const extension = archiveExtensionInput.value.trim();
    if (extension) {
        command += ' --extension ' + extension;
    }

    commandPreview.textContent = command;
    checkCommandOverflow();
}

copyCommandBtn.addEventListener('click', function() {
    navigator.clipboard.writeText(commandPreview.textContent).then(() => {
        copyCommandBtn.textContent = '✔';
        setTimeout(() => { copyCommandBtn.textContent = '⧉'; }, 1200);
    }).catch(() => {
        vscode.postMessage({ command: 'show-error', message: 'Failed to copy command to clipboard.' });
    });
});

browseSolutionBtn.addEventListener('click', function() {
    const previousSelection = state.selectedSolution || '';
    vscode.postMessage({ command: 'select-another-solution', previousSelection });
});

browseOutputBtn.addEventListener('click', function() {
    vscode.postMessage({ command: 'browse-output-path' });
});

solutionSelect.addEventListener('change', function() {
    const solutionName = solutionSelect.value;
    const rootDir = getSelectedRootDir();
    if (solutionName) {
        outputPathInput.value = rootDir || '';
        archiveFilenameInput.value = solutionName;
    }
    saveState();
    updateCommandPreview();
});

outputPathInput.addEventListener('input', function() {
    saveState();
    updateCommandPreview();
});

archiveFilenameInput.addEventListener('input', function() {
    saveState();
    updateCommandPreview();
});

archiveExtensionInput.addEventListener('input', function() {
    saveState();
    updateCommandPreview();
});

archiveBtn.addEventListener('click', function() {
    const solutionName = solutionSelect.value;
    if (!solutionName) {
        vscode.postMessage({ command: 'show-error', message: 'Please select a solution to archive.' });
        return;
    }

    const extension = archiveExtensionInput.value.trim();
    if (extension && !extension.startsWith('.')) {
        vscode.postMessage({ command: 'show-error', message: "Extension must start with '.'." });
        return;
    }

    const options = {
        outputPath: outputPathInput.value.trim() || undefined,
        filename: archiveFilenameInput.value.trim() || undefined,
        extension: extension || undefined
    };

    vscode.postMessage({ command: 'archive-solution', solutionName, options });
});

window.addEventListener('message', (event) => {
    const message = event.data;

    if (message.type === 'set-selected-solution') {
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

            if (message.rootDirectory) {
                outputPathInput.value = message.rootDirectory;
                archiveFilenameInput.value = message.selectedSolution;
                state.outputPath = message.rootDirectory;
                state.archiveFilename = message.selectedSolution;
            }

            state.selectedSolution = message.selectedSolution;
            saveState();
            updateCommandPreview();
        }
    }
    else if (message.type === 'preselect-solution') {
        if (message.selectedSolution) {
            const optionExists = Array.from(solutionSelect.options).some(
                option => option.value === message.selectedSolution
            );

            if (optionExists) {
                solutionSelect.value = message.selectedSolution;
            } else {
                const tempOption = document.createElement('option');
                tempOption.value = message.selectedSolution;
                tempOption.text = message.selectedSolution;
                if (message.rootDirectory) {
                    tempOption.setAttribute('data-root-directory', message.rootDirectory);
                }
                tempOption.setAttribute('data-temp', 'true');
                solutionSelect.add(tempOption);
                solutionSelect.value = message.selectedSolution;
            }

            if (message.rootDirectory) {
                outputPathInput.value = message.rootDirectory;
            }

            if (message.resetFilename) {
                archiveFilenameInput.value = message.selectedSolution;
            }

            if (message.resetExtension) {
                archiveExtensionInput.value = '.saf';
            }

            state.selectedSolution = message.selectedSolution;
            state.outputPath = outputPathInput.value;
            state.archiveFilename = archiveFilenameInput.value;
            state.archiveExtension = archiveExtensionInput.value;
            saveState();
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
            if (solution.rootDirectory) {
                option.setAttribute('data-root-directory', solution.rootDirectory);
            }
            solutionSelect.add(option);
        });

        if (state.selectedSolution) {
            const selectedOption = Array.from(solutionSelect.options).find(
                opt => opt.value === state.selectedSolution
            );
            if (selectedOption) {
                solutionSelect.value = state.selectedSolution;
                const rootDir = selectedOption.getAttribute('data-root-directory');
                if (!state.outputPath && rootDir) {
                    outputPathInput.value = rootDir;
                    state.outputPath = rootDir;
                }
                if (!state.archiveFilename) {
                    archiveFilenameInput.value = state.selectedSolution;
                    state.archiveFilename = state.selectedSolution;
                }
            }
        } else if (message.selectedSolution) {
            solutionSelect.value = message.selectedSolution;
            state.selectedSolution = message.selectedSolution;

            const selectedOption = Array.from(solutionSelect.options).find(
                opt => opt.value === message.selectedSolution
            );
            const rootDir = selectedOption ? selectedOption.getAttribute('data-root-directory') : '';

            if (!state.outputPath && rootDir) {
                outputPathInput.value = rootDir;
                state.outputPath = rootDir;
            }
            if (!state.archiveFilename) {
                archiveFilenameInput.value = message.selectedSolution;
                state.archiveFilename = message.selectedSolution;
            }
        }

        saveState();
        updateCommandPreview();
    }
    else if (message.type === 'revert-solution') {
        solutionSelect.value = message.previousSelection || '';
        state.selectedSolution = message.previousSelection || '';
        saveState();
        updateCommandPreview();
    }
    else if (message.type === 'output-path-selected') {
        outputPathInput.value = message.path;
        saveState();
        updateCommandPreview();
    }
    else if (message.type === 'set-archiving-state') {
        archiveBtn.disabled = message.archiving;
        archiveBtn.textContent = message.archiving ? 'Archiving...' : 'Archive solution';
    }
});

vscode.postMessage({ command: 'load-solutions' });
restoreState();
