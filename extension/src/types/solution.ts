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


export interface SolutionConfig {
    name: string;
    displayName: string;
    uiType: string;
    namespace: string;
    targetDirectory: string;
}

export interface StepConfig {
    solutionPath: string;
    name: string;
    displayName: string;
    createPage: boolean;
    uiFramework: string;
    template?: string;
}

export interface ExecutionOptions {
    solutionPath: string;
    forceSetup: boolean;
}

export interface TreeItem {
    label: string;
    collapsibleState: number;
    command?: Command;
    contextValue?: string;
    iconPath?: any;
}

export interface Command {
    command: string;
    title: string;
    arguments?: any[];
}

export interface EnvironmentVariableDefinition {
    name: string;
    defaultValue: string | boolean | null;
    description: string;
    category: string;
    options?: string[];
}

export interface EnvironmentVariableState extends EnvironmentVariableDefinition {
    enabled: boolean;
    value: string | boolean | null;
}