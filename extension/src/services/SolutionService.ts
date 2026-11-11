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


import * as path from 'node:path';
import { SystemService } from './SystemService';
import {
    SolutionConfig,
    StepConfig,
} from '../types/solution';
import { StepManagement } from './StepManagement';
import { StorageService } from '../services/StorageService';
import { SAFSolutionsProvider } from '../providers/SAFSolutionsProvider';


export class SolutionService {
    private systemService: SystemService = new SystemService();

    public setSystemService(SystemServiceInstance: SystemService) {
        this.systemService = SystemServiceInstance;
    }

    private stepManager: StepManagement = new StepManagement();

    public setStepManager(StepManagerInstance: StepManagement) {
        this.stepManager = StepManagerInstance;
    }

    async createSolution(config: SolutionConfig): Promise<void> {
        try {
            process.chdir(config.targetDirectory);

            const safCliExecutable = StorageService.getSafCliExecutablePath();
            const args = [
                'new',
                '--solution-name', config.name,
                '--solution-display-name', config.displayName,
                '--ui-framework', config.uiType,
                '--namespace', config.namespace
            ];

            await this.systemService.executeCommand(safCliExecutable, args, { cwd: config.targetDirectory });
        } catch (error) {
            throw new Error(`Failed to create solution using SAF CLI: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }

    async addStep(config: StepConfig): Promise<void> {
        try {
            const solutions = await SAFSolutionsProvider.getInstance().getSAFSolutions();
            const solution = solutions.find(sol => sol.rootDirectory === config.solutionPath);
            if (!solution) {
                throw new Error('Solution not found for the given path');
            }
            const safCliExecutable = StorageService.getSafCliExecutablePath();
            const template = config.template?.trim() || 'calculator-step';
            const args = [
                'add-step',
                solution.name,
                '--step-name',
                config.name,
                '--ui-framework',
                config.uiFramework,
                '--template',
                template,
            ];
            await this.systemService.executeCommand(safCliExecutable, args, { cwd: config.solutionPath });
        } catch (error) {
            throw new Error(`Failed to add step: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }

    /**
     * Retrieves the list of available step templates from the SAF CLI.
     * Calls `saf templates --steps` and extracts valid step template identifiers from the output.
     * Falls back to `['calculator-step']` if the command fails, so the UI is never left empty.
     */
    async getStepTemplates(): Promise<string[]> {
        try {
            const safCliExecutable = StorageService.getSafCliExecutablePath();
            const output = await this.systemService.executeCommand(
                safCliExecutable,
                ['templates', '--steps']
            );
            const templates = output
                .split('\n')
                .map(line => line.trim())
                .map(line => line.match(/([a-z0-9][a-z0-9-_]*(?:-step|_step))\b/i)?.[1] ?? '')
                .filter(line => line.length > 0);
            return templates.length > 0 ? templates : ['calculator-step'];
        } catch (error) {
            console.error('Failed to fetch step templates:', error);
            return ['calculator-step'];
        }
    }

    async getStepFiles(solutionPath: string, stepName: string, createPage: boolean): Promise<string[]> {
        const solutionPackagePath = await this.stepManager.findSolutionDir(solutionPath);

        // Normalize step name following saf-cli logic
        let normalizedStepName = stepName.toLowerCase();
        let stepBackendName = normalizedStepName;
        if (!stepBackendName.endsWith('step')) {
            stepBackendName += '_step';
        }

        const files = [
            path.join(
                solutionPath,
                'src',
                solutionPackagePath,
                'solution',
                `${stepBackendName}.py`
            )
        ];

        if (createPage) {
            // Derive page name from step name
            let pageName = normalizedStepName.replace(/_step$/, '');
            if (!pageName.endsWith('page')) {
                pageName += '_page';
            }
            files.push(path.join(
                solutionPath,
                'src',
                solutionPackagePath,
                'ui',
                'pages',
                `${pageName}.py`
            ));
        }

        return files;
    }
}
export const solutionService = new SolutionService();