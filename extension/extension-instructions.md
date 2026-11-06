# Solutions Manager Extension

The Solutions Manager Extension is a Visual Studio Code extension designed to
streamline the development and management of Solution Applications.
This tool provides a comprehensive set of features accessible through
an intuitive sidebar interface.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Features](#features)
    1. [Create Solution](#create-solution-️)
    2. [Setup Solution](#setup-solution-️)
    3. [Run Solution Configuration](#run-solution-configuration-)
    4. [Customize Solution](#customize-solution-️)
    5. [Dependency Management](#dependency-management-)
4. [User's Guide](#users-guide)
    1. [Creating a New Solution](#creating-a-new-solution)
    2. [Setting Up Environment](#installing-dev-environment)
    3. [Running a Solution](#running-a-solution)
    4. [Adding Solution Steps](#adding-solution-steps)
    5. [Managing Dependencies](#managing-dependencies)
    6. [Configuring Environment Variables](#configuring-environment-variables)
5. [Troubleshooting](#troubleshooting)

## Prerequisites

- VS Code (1.109.0 or higher)
- Python 3.11-3.14 (>=3.11, <3.15)

- On Windows, long path support must be enabled. It can be enabled by searching for the "Enable long paths" setting.
  For more information, see the official Microsoft documentation:
  [Maximum file path limitation](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation?tabs=registry).

## Installation

### Get the Extension Package

1. Go to the SAF GitHub releases page: [SAF Releases](https://github.com/ansys/saf/releases)
2. Open the latest release whose tag starts with `saf-solutions-manager-v`
3. Download the release asset named `solutions-manager-extension-<version>.vsix`

### Install in Visual Studio Code

1. Open Visual Studio Code
2. Access the Extensions menu using one of these methods:
    - Click the Extensions icon in the Activity Bar (Ctrl+Shift+X)
    - Select View → Extensions from the menu bar
3. Click the "..." (More Actions) button in the Extensions panel
4. Select "Install from VSIX..."
5. Navigate to and select the downloaded .vsix file
6. Click "Install"
7. When prompted, click "Restart" to reload VS Code

## Features

The Solutions Manager extension provides several key features organized in
different views:

### Create Solution 🏗️

#### Create Standard Solution

Easily create new solution applications using SAF CLI

- Configure solution name and display name
- Select the solution type (Dash, no UI)
- Automatic project structure generation
- Post-creation option to open the solution in a new window

### Setup Solution ⚙️

#### Install Dev Environment

Configure the Python virtual environment for the solution

- Select the solution
- Choose among:
  - No environment clean-up (keep existing environment)
  - Clean-up solution's environment
  - Clean-up solution's environment and ``poetry.lock`` file
- Real-time command preview

### Run Solution Configuration 🚀

#### Interactive Run Panel

- Configure and run solutions directly from VS Code
- Customizable run options:

  - Solution selection
  - Portal toggle
  - Browser toggle
  - Debug mode toggle
  - UI debugger toggle
  - No UI mode toggle
  - Log level selection
  - Project name specification
  - View and edit all available SAF environment variables
  - Environment file selection

- Real-time command preview
- One-click environment setup when needed
- Integrated terminal output for solution execution

#### Environment Variables Configuration

- Manage SAF environment variables through an intuitive UI
- Features:
  - View and edit all available SAF environment variables
  - Organize variables by category
  - Enable/disable specific variables
  - Set custom values for variables
  - Save configurations to .env file
  - Search and filter functionality
  - Bulk enable/disable variables by category

### Customize Solution ⚙️

#### Add Step

- Add new steps to existing solutions
- Configure:
  - Step name
  - Framework type (Dash, no UI)
- Automatic:
  - Python file generation
  - Step registration in solution definition
  - Page file creation (if selected)
  - Integration with navigation system
  - File opening in editor

### Dependency Management 📦

#### Poetry Dependencies View

- Visualize solution dependencies by group (main, ui, doc, tests, etc.)
- Contextual actions for each dependency:

  - Update dependency versions
  - Remove dependencies
  - Add new dependencies with version constraints
- Support for private package sources

## User's Guide

1. Access the Solutions Manager through the activity bar (look for the SAF icon)
2. Use the tree view to access different functionalities
3. Follow the interactive prompts for each operation

### Creating a New Solution

#### Standard Solution

1. Select "Create Solution" from the Solutions Creation view
2. Enter a solution name (lowercase letters, numbers, hyphens, and underscores only)
3. Enter a display name for your solution
4. Select the UI type (dash, no UI)
5. Select the target directory

### Installing Dev Environment

1. With your solution open in VS Code, select "Install Dev Environment" from
  the Setup Solution view
2. If a virtual environment already exists, choose whether to use it or
  create a new one
3. Wait for the setup process to complete

### Running a Solution

1. Open the Run Solution panel from the Explorer view
2. Configure run options:
    - Select the solution to run from the dropdown
    - Toggle Portal to run the solution with the Portal
    - Toggle Browser to open the solution in a web browser
    - Toggle Debug Mode to run the solution in debug mode
    - Toggle UI Debugger to run the solution with UI debugging enabled
    - Toggle No UI to run only the solution backend
      (without the solution UI and the Portal)
    - Select log level for output verbosity
    - Specify a project name (optional) to create and open the solution UI of a
      new project, if it does not exist. If the solution UI does exist, then
      opens the UI. If the UI is not available,
      then shows project information in the orchestrator
    - Select or browse for an environment file (optional)

3. View the generated command in the preview area
4. Click "Run Solution" to execute
5. If the Dev environment isn't installed, use the "Install Now"
button to set it up

### Adding Solution Steps

1. Select "Add Step" from the Solution Customization view
2. Enter a step name (lowercase letters, numbers, and underscores only)
3. Enter a display name for the step (optional)
4. Choose whether to create a corresponding UI page
5. The new step files will be opened in the editor

### Managing Dependencies

Dependencies are displayed in the Poetry Dependencies view:

#### Adding a Dependency

1. Right-click in the Poetry Dependencies view and select "Add Dependency"
2. Enter the package name
3. Enter the version constraint (for example, 1.0.0, ^1.0.0, ~1.0.0, >=1.0.0)
4. Select the dependency group (main, ui, doc, tests, build, style)

#### Updating a Dependency

1. Right-click on a dependency in the Poetry Dependencies view
2. Select "Update Dependency"
3. Enter the new version constraint or leave empty to update to the latest version

#### Removing a Dependency

1. Right-click on a dependency in the Poetry Dependencies view
2. Select "Remove Dependency"
3. Confirm the removal

### Configuring Environment Variables

1. Select "Configure solution environment" from the Run Solution view
2. The Environment Configuration panel will open, showing all
  available SAF environment variables
3. Use the interface to:
    - Search for specific variables using the search box
    - Filter variables by category using the dropdown
    - Enable/disable variables by checking/unchecking the "Enabled" checkbox
    - Set custom values for enabled variables
    - Use the "Enable all" or "Disable all" buttons to quickly
      manage variables by category

4. Click the "Save Configuration" button to save your changes to a
  .env file in your workspace
5. The saved configuration will be automatically loaded when you run your solution

## Troubleshooting

### Environment Setup Issues

- Ensure Python is properly installed and accessible
- For private package sources, check that the `POETRY_HTTP_BASIC_<SOURCE_NAME>_USERNAME` and
  `POETRY_HTTP_BASIC_<SOURCE_NAME>_PASSWORD` environment variables are set
- Verify network connection to your configured package index

### Dependency Management Issues

- Check for valid version constraints when adding/updating dependencies
- Ensure Poetry is properly installed in your virtual environment

### General Troubleshooting

- Check the VS Code output panel for extension logs
- Verify solution structure follows expected conventions
- Ensure all required files exist in the solution directory

## Support

Report issues or request features in the [SAF issue tracker](https://github.com/ansys/saf/issues/new/choose).

