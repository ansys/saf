// Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
// SPDX-License-Identifier: Apache-2.0

// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at

//     http://www.apache.org/licenses/LICENSE-2.0

// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.


const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const srcPkg = path.join(root, 'package.json');
const outPkg = path.join(root, 'out', 'package.json');

const pkg = JSON.parse(fs.readFileSync(srcPkg, 'utf8'));
pkg.enabledApiProposals = ['terminalDataWriteEvent'];
pkg.main = './extension.js';

fs.mkdirSync(path.dirname(outPkg), { recursive: true });
fs.writeFileSync(outPkg, JSON.stringify(pkg, null, 2) + '\n', 'utf8');
