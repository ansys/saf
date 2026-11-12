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
  offlinePackage: false,
  displayConsoleWindow: false,
  pythonVersion: '',
  excludePython: false,
  encrypt: false,
  encryptionFile: '',
  encryptionKey: '',
  obfuscate: false,
  executableAsDir: false,
  forcePythonFromSource: false,
  envFile: '',
  noExecutable: false,
  solutionEntryPoint: '',
  githubToken: '',
  solutionUiFramework: ''
};

// Secrets must never be written to or read back from vscode.setState(), since
// that data is persisted to disk and would leak sensitive values.
const SENSITIVE_STATE_KEYS = ['encryptionKey', 'githubToken'];

function isValidValue(value) {
  return value !== undefined && value !== null && value !== 'undefined';
}

if (existingState) {
  Object.keys(state).forEach(key => {
    if (SENSITIVE_STATE_KEYS.includes(key)) {
      return;
    }
    // eslint-disable-next-line security/detect-object-injection
    if (isValidValue(existingState[key])) {
      // eslint-disable-next-line security/detect-object-injection
      state[key] = existingState[key];
    }
  });
}

function normalizePath(value) {
  return value.replace(/\\/g, '/');
}

// Encryption keys and GitHub tokens must never contain whitespace; strip it as the user types.
function stripWhitespace(input) {
  const sanitized = input.value.replace(/\s+/g, '');
  if (sanitized !== input.value) {
    input.value = sanitized;
  }
}

const NO_WHITESPACE_INPUTS = [];

// DOM Elements
const solutionSelect = document.getElementById('solution-select');
const browseSolutionBtn = document.getElementById('browse-solution-btn');
const offlinePackageCheckbox = document.getElementById('offline-package');
const displayConsoleWindowCheckbox = document.getElementById('display-console-window');
const pythonVersionInput = document.getElementById('python-version');
const excludePythonCheckbox = document.getElementById('exclude-python');
const encryptCheckbox = document.getElementById('encrypt');
const encryptionFileInput = document.getElementById('encryption-file');
const browseEncryptionFileBtn = document.getElementById('browse-encryption-file-btn');
const encryptionKeyInput = document.getElementById('encryption-key');
const obfuscateCheckbox = document.getElementById('obfuscate');
const executableAsDirCheckbox = document.getElementById('executable-as-dir');
const forcePythonFromSourceCheckbox = document.getElementById('force-python-from-source');
const envFileInput = document.getElementById('env-file');
const browseEnvFileBtn = document.getElementById('browse-env-file-btn');
const noExecutableCheckbox = document.getElementById('no-executable');
const solutionEntryPointInput = document.getElementById('solution-entry-point');
const githubTokenInput = document.getElementById('github-token');
const solutionUiFrameworkInput = document.getElementById('solution-ui-framework');
const buildBtn = document.getElementById('build-btn');
const commandPreview = document.getElementById('command-preview');
const copyCommandBtn = document.getElementById('copy-command-btn');

NO_WHITESPACE_INPUTS.push(encryptionKeyInput, githubTokenInput);

copyCommandBtn.addEventListener('click', function() {
  const command = commandPreview.textContent;
  navigator.clipboard.writeText(command).then(() => {
    copyCommandBtn.textContent = '✔';
    setTimeout(() => {
      copyCommandBtn.textContent = '⧉';
    }, 1200);
  });
});

function checkCommandOverflow() {
  const preview = document.querySelector('.command-preview');
  const code = document.getElementById('command-preview');
  if (code.scrollWidth > preview.clientWidth) {
    code.classList.add('overflow');
  } else {
    code.classList.remove('overflow');
  }
}

// Restore state from previous session
function restoreState() {
  solutionSelect.value = state.selectedSolution || '';
  offlinePackageCheckbox.checked = state.offlinePackage || false;
  displayConsoleWindowCheckbox.checked = state.displayConsoleWindow || false;
  pythonVersionInput.value = state.pythonVersion || '';
  excludePythonCheckbox.checked = state.excludePython || false;
  encryptCheckbox.checked = state.encrypt || false;
  encryptionFileInput.value = state.encryptionFile || '';
  encryptionKeyInput.value = '';
  obfuscateCheckbox.checked = state.obfuscate || false;
  executableAsDirCheckbox.checked = state.executableAsDir || false;
  forcePythonFromSourceCheckbox.checked = state.forcePythonFromSource || false;
  envFileInput.value = state.envFile || '';
  noExecutableCheckbox.checked = state.noExecutable || false;
  solutionEntryPointInput.value = state.solutionEntryPoint || '';
  githubTokenInput.value = '';
  solutionUiFrameworkInput.value = state.solutionUiFramework || '';
  updateCommandPreview();
}

// Save current state
function saveState() {
  state.selectedSolution = solutionSelect.value;
  state.offlinePackage = offlinePackageCheckbox.checked;
  state.displayConsoleWindow = displayConsoleWindowCheckbox.checked;
  state.pythonVersion = pythonVersionInput.value;
  state.excludePython = excludePythonCheckbox.checked;
  state.encrypt = encryptCheckbox.checked;
  state.encryptionFile = encryptionFileInput.value;
  state.encryptionKey = '';
  state.obfuscate = obfuscateCheckbox.checked;
  state.executableAsDir = executableAsDirCheckbox.checked;
  state.forcePythonFromSource = forcePythonFromSourceCheckbox.checked;
  state.envFile = envFileInput.value;
  state.noExecutable = noExecutableCheckbox.checked;
  state.solutionEntryPoint = solutionEntryPointInput.value;
  state.githubToken = '';
  state.solutionUiFramework = solutionUiFrameworkInput.value;
  vscode.setState(state);
}

// Update the command preview
function updateCommandPreview() {
  const solution = solutionSelect.value;
  let command = 'saf build';

  if (solution) {
    command += ' ' + solution;
  }

  // Basic options
  if (offlinePackageCheckbox.checked) {
    command += ' --offline-package';
  }

  if (displayConsoleWindowCheckbox.checked) {
    command += ' --display-console-window';
  }

  // Python options
  const pythonVersion = pythonVersionInput.value.trim();
  if (pythonVersion) {
    command += ' --python-version ' + pythonVersion;
  }

  if (excludePythonCheckbox.checked) {
    command += ' --exclude-python';
  }

  // Advanced options
  if (encryptCheckbox.checked) {
    command += ' --encrypt';
  }

  const encryptionFile = encryptionFileInput.value.trim();
  if (encryptionFile) {
    command += ' --encryption-file "' + normalizePath(encryptionFile) + '"';
  }

  const encryptionKey = encryptionKeyInput.value.trim();
  if (encryptionKey) {
    command += ' --encryption-key "********"';
  }

  if (obfuscateCheckbox.checked) {
    command += ' --obfuscate';
  }

  if (executableAsDirCheckbox.checked) {
    command += ' --executable-as-dir';
  }

  if (forcePythonFromSourceCheckbox.checked) {
    command += ' --force-python-from-source';
  }

  const envFile = envFileInput.value.trim();
  if (envFile) {
    command += ' --env-file "' + normalizePath(envFile) + '"';
  }

  if (noExecutableCheckbox.checked) {
    command += ' --no-executable';
  }

  const solutionEntryPoint = solutionEntryPointInput.value.trim();
  if (solutionEntryPoint) {
    command += ' --solution-entry-point ' + solutionEntryPoint;
  }

  const githubToken = githubTokenInput.value.trim();
  if (githubToken) {
    command += ' --github-token "********"';
  }

  const solutionUiFramework = solutionUiFrameworkInput.value.trim();
  if (solutionUiFramework) {
    command += ' --solution-ui-framework ' + solutionUiFramework;
  }

  commandPreview.textContent = command;
  checkCommandOverflow();
}

browseSolutionBtn.addEventListener('click', function() {
  const previousSelection = state.selectedSolution || '';
  vscode.postMessage({
    command: 'select-another-solution',
    previousSelection: previousSelection
  });
});

browseEncryptionFileBtn.addEventListener('click', function() {
  vscode.postMessage({ command: 'browse-encryption-file' });
});

browseEnvFileBtn.addEventListener('click', function() {
  vscode.postMessage({ command: 'browse-env-file' });
});

// Event Listeners - Basic Options
solutionSelect.addEventListener('change', function() {
  saveState();
  updateCommandPreview();
});

offlinePackageCheckbox.addEventListener('change', function() {
  saveState();
  updateCommandPreview();
});

displayConsoleWindowCheckbox.addEventListener('change', function() {
  saveState();
  updateCommandPreview();
});

// Event Listeners - Python Options
pythonVersionInput.addEventListener('input', function() {
  saveState();
  updateCommandPreview();
});

excludePythonCheckbox.addEventListener('change', function() {
  saveState();
  updateCommandPreview();
});

// Event Listeners - Advanced Options
[
  encryptCheckbox,
  obfuscateCheckbox,
  executableAsDirCheckbox,
  forcePythonFromSourceCheckbox,
  noExecutableCheckbox
].forEach(checkbox => {
  checkbox.addEventListener('change', function() {
    saveState();
    updateCommandPreview();
  });
});

[
  encryptionFileInput,
  encryptionKeyInput,
  envFileInput,
  solutionEntryPointInput,
  githubTokenInput,
  solutionUiFrameworkInput
].forEach(input => {
  input.addEventListener('input', function() {
    if (NO_WHITESPACE_INPUTS.includes(input)) {
      stripWhitespace(input);
    }
    saveState();
    updateCommandPreview();
  });
});

buildBtn.addEventListener('click', function() {
  const solutionName = solutionSelect.value;
  const options = {
    offlinePackage: offlinePackageCheckbox.checked,
    displayConsoleWindow: displayConsoleWindowCheckbox.checked,
    pythonVersion: pythonVersionInput.value.trim(),
    excludePython: excludePythonCheckbox.checked,
    encrypt: encryptCheckbox.checked,
    encryptionFile: encryptionFileInput.value.trim(),
    encryptionKey: encryptionKeyInput.value.trim(),
    obfuscate: obfuscateCheckbox.checked,
    executableAsDir: executableAsDirCheckbox.checked,
    forcePythonFromSource: forcePythonFromSourceCheckbox.checked,
    envFile: envFileInput.value.trim(),
    noExecutable: noExecutableCheckbox.checked,
    solutionEntryPoint: solutionEntryPointInput.value.trim(),
    githubToken: githubTokenInput.value.trim(),
    solutionUiFramework: solutionUiFrameworkInput.value.trim()
  };

  if (!solutionName) {
    // No solution selected, ask about using workspace solution
    vscode.postMessage({
      command: 'build-installer-workspace-prompt',
      options: options
    });
    return;
  }

  vscode.postMessage({
    command: 'build-installer',
    solutionName: solutionName,
    options: options
  });
});

// Handle messages from extension
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

      state.selectedSolution = message.selectedSolution;
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
      state.selectedSolution = message.selectedSolution;
      saveState();
      vscode.postMessage({ command: 'solution-changed', solution: message.selectedSolution });
    }

    updateCommandPreview();
  }
  else if (message.type === 'revert-solution') {
    solutionSelect.value = message.previousSelection || '';
    state.selectedSolution = message.previousSelection || '';
    saveState();
    updateCommandPreview();
  }
  else if (message.type === 'encryption-file-selected') {
    encryptionFileInput.value = message.path;
    saveState();
    updateCommandPreview();
  }
  else if (message.type === 'env-file-selected') {
    envFileInput.value = message.path;
    saveState();
    updateCommandPreview();
  }
});

vscode.postMessage({ command: 'load-solutions' });
restoreState();
