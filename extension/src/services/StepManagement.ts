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


import * as fs from 'node:fs';
import * as path from 'node:path';

export class StepManagement {
    public async findSolutionDir(solutionPath: string): Promise<string> {
        const srcRoot = path.join(solutionPath, 'src');

        try {
            const queue: string[] = [srcRoot];
            let queueIndex = 0;

            while (queueIndex < queue.length) {
                const currentDir = queue[queueIndex++]!;
                // eslint-disable-next-line security/detect-non-literal-fs-filename
                const items = await fs.promises.readdir(currentDir, { withFileTypes: true });

                for (const item of items) {
                    if (!item.isDirectory() || item.name.startsWith('.')) {
                        continue;
                    }

                    const dirPath = path.join(currentDir, item.name);
                    const definitionFile = path.join(dirPath, 'solution', 'definition.py');

                    if (await this.pathExists(definitionFile)) {
                        // Example return values:
                        // old: ansys/solutions/my_solution
                        // new: my_namespace/my_solution or my/ns/my_solution
                        return path.relative(srcRoot, dirPath);
                    }

                    queue.push(dirPath);
                }
            }

            throw new Error('Could not find solution package directory under src');
        } catch (error) {
            throw new Error(
                `Failed to find solution directory: ${error instanceof Error ? error.message : 'Unknown error'}`
            );
        }
    }

    private async pathExists(filePath: string): Promise<boolean> {
        try {
            await fs.promises.access(filePath, fs.constants.F_OK);
            return true;
        } catch {
            return false;
        }
    }
}
