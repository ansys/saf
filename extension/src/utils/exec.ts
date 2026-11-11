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
import { promisify } from 'node:util';

// Use `execFileAsync` when using an absolute executable path and `execAsync` when using a command name.
// `execAsync` fails with paths that include, for example, spaces. While `execFileAsync` might not be able
// to correctly resolve command names.
export const execFileAsync = promisify(childProcess.execFile);
export const execAsync = promisify(childProcess.exec);