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


/**
 * Barrel exports for all command classes
 * This file centralizes imports and exports for better maintainability
 */

// Core command classes
export { SolutionCommands } from './solutionCommands';
export { DebugCommands } from './debugCommands';
export { DependencyCommands } from './dependencyCommands';
export { DevelopmentCommands } from './developmentCommands';
export { HelpCommands } from './helpCommands';

// Re-export common types that commands might need
export type { CommandContext } from '../managers/CommandManager';

// Command factory function for easier instantiation
import { CommandContext } from '../managers/CommandManager';
import { SolutionCommands } from './solutionCommands';
import { DebugCommands } from './debugCommands';
import { DependencyCommands } from './dependencyCommands';
import { DevelopmentCommands } from './developmentCommands';
import { HelpCommands } from './helpCommands';

/**
 * Factory interface for creating all command instances
 */
export interface CommandFactory {
    solutionCommands: SolutionCommands;
    debugCommands: DebugCommands;
    dependencyCommands: DependencyCommands;
    developmentCommands: DevelopmentCommands;
    helpCommands: HelpCommands;
}

/**
 * Creates and returns all command instances with the given context
 * @param context - The command context containing extension and workspace information
 * @returns Object containing all command instances
 */
export function createCommands(context: CommandContext): CommandFactory {
    return {
        solutionCommands: new SolutionCommands(context),
        debugCommands: new DebugCommands(context),
        dependencyCommands: new DependencyCommands(context),
        developmentCommands: new DevelopmentCommands(context),
        helpCommands: new HelpCommands(context)
    };
}

/**
 * Command registration helper
 * Maps command IDs to their corresponding methods
 */
export const COMMAND_MAPPINGS = {
    // Solution commands
    'solutions-manager.createSolution': 'solutionCommands.createSolution',
    'solutions-manager.refreshSolutionsList': 'solutionCommands.refreshSolutionsList',
    'solutions-manager.openSolution': 'solutionCommands.openSolution',

    // Debug commands
    'solutions-manager.debugtransactionmethods': 'debugCommands.debugTransactionMethods',
    'solutions-manager.debugsolutiondashui': 'debugCommands.debugSolutionDashUI',

    // Dependency commands
    'solutions-manager.addDependency': 'dependencyCommands.addDependency',
    'solutions-manager.updateDependency': 'dependencyCommands.updateDependency',
    'solutions-manager.removeDependency': 'dependencyCommands.removeDependency',

    // Development commands
    'solutions-manager.installDevEnvironment': 'developmentCommands.installDevEnvironment',
    'solutions-manager.showEnvironmentConfig': 'developmentCommands.showEnvironmentConfig',

    // Help commands
    'solutions-manager.openExtensionHelp': 'helpCommands.openExtensionHelp',
    'solutions-manager.openGitHubIssues': 'helpCommands.openGitHubIssues',
    'solutions-manager.openGitHubRepo': 'helpCommands.openGitHubRepo',
    'solutions-manager.showQuickHelp': 'helpCommands.showQuickHelp',
    'solutions-manager.showTroubleshootingGuide': 'helpCommands.showTroubleshootingGuide',
    'solutions-manager.showAboutDialog': 'helpCommands.showAboutDialog',
    'solutions-manager.openFeedbackForm': 'helpCommands.openFeedbackForm'
} as const;

/**
 * Type-safe command ID type
 */
export type CommandId = keyof typeof COMMAND_MAPPINGS;

/**
 * Utility function to validate command IDs
 */
export function isValidCommandId(commandId: string): commandId is CommandId {
    return commandId in COMMAND_MAPPINGS;
}

/**
 * Get all available command IDs
 */
export function getAllCommandIds(): CommandId[] {
    return Object.keys(COMMAND_MAPPINGS) as CommandId[];
}

/**
 * Group command IDs by category
 */
export const COMMAND_CATEGORIES = {
    solution: [
        'solutions-manager.createSolution',
        'solutions-manager.refreshSolutionsList',
        'solutions-manager.openSolution'
    ],
    debug: [
        'solutions-manager.debugtransactionmethods',
        'solutions-manager.debugsolutiondashui'
    ],
    dependency: [
        'solutions-manager.addDependency',
        'solutions-manager.updateDependency',
        'solutions-manager.removeDependency'
    ],
    development: [
        'solutions-manager.installDevEnvironment',
        'solutions-manager.showEnvironmentConfig'
    ],
    help: [
        'solutions-manager.openExtensionHelp',
        'solutions-manager.openGitHubIssues',
        'solutions-manager.openGitHubRepo',
        'solutions-manager.showQuickHelp',
        'solutions-manager.showTroubleshootingGuide',
        'solutions-manager.showAboutDialog',
        'solutions-manager.openFeedbackForm'
    ]
} as const;

/**
 * Get commands by category
 */
export function getCommandsByCategory(category: keyof typeof COMMAND_CATEGORIES): readonly CommandId[] {
    // eslint-disable-next-line security/detect-object-injection
    return COMMAND_CATEGORIES[category];
}