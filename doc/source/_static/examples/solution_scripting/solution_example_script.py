# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Perform required imports
from pathlib import Path

from ansys.saf.glow.client import Client  # pyright: ignore[reportMissingImports]
from ansys.solutions.my_solution.solution.definition import (  # type: ignore  # pyright: reportMissingImports=false
    MySolution,
)

# ----

# Define the GLOW API server URL
GLOW_API_SERVER_URL = "http://localhost:50000"
# ----

# Create a GLOW Client
client = Client(MySolution, GLOW_API_SERVER_URL)
# ----

# List existing projects
all_projects = client.list_projects()
# ----

# Get an existing project
project_a = client.get_project("projects/6638ce7177e87f72ac4bbab3")
# ----

# Upgrade an existing project
project_a = client.upgrade_project("projects/6638ce7177e87f72ac4bbab3")
# ----

# Delete an existing project
client.delete_project("projects/6638ce7177e87f72ac4bbab3")
# ----

# Create a new project
project_a = client.create_project("Project A")
# ----

# Get step fields
print(f"first_arg: {project_a.steps.first_step.first_arg}")
print(f"second_arg: {project_a.steps.first_step.second_arg}")
# ----

# Set step fields
project_a.steps.first_step.first_arg = 1
project_a.steps.first_step.second_arg = 2
# ----

# Run the calculate method from the first step
project_a.steps.first_step.calculate()
# ----

# Get the result
print(f"result: {project_a.steps.first_step.result}")
# ----

# Export the project
project_a.export(destination=Path.cwd())
# ----

# Delete the project
project_a.delete()
# ----

# Import the project
project_b = client.import_project(safx_path=Path.cwd() / "Project A.safx", display_name="Project B")
# ----

# Access the project properties
# Get the project URL
print(f"Project URL: {project_b.url}")
# Get the creation date of the project
print(f"Project creation date: {project_b.date_created}")
# Get the last modification date of the project
print(f"Project last modification date: {project_b.date_modified}")
# ----

# Modify the project display name
project_b.modify_project_display_name(display_name="Project C")
# ----

# Delete the imported project
project_b.delete()
# ----

# Create a matrix of projects with different arguments
PROJECT_MATRIX = {
    "Project A": {"first_arg": 1, "second_arg": 2, "result": None, "name": None},
    "Project B": {"first_arg": 10, "second_arg": 25, "result": None, "name": None},
    "Project C": {"first_arg": 5, "second_arg": 3, "result": None, "name": None},
}
# ----

# Create multiple projects using a loop
for project_display_name, args in PROJECT_MATRIX.items():
    # Create the project
    project = client.create_project(project_display_name)
    # Set the step fields
    project.steps.first_step.first_arg = args["first_arg"]
    project.steps.first_step.second_arg = args["second_arg"]

    # Run the calculate method
    project.steps.first_step.calculate()

    # Store the result
    args["result"] = project.steps.first_step.result

    # Store the project name for later use
    args["name"] = "projects/" + project.url.split("/")[-1]
# ----

# Print the results of all project calculations
for project_display_name, args in PROJECT_MATRIX.items():
    print(f"{project_display_name} result: {args['result']}")
# ----

# Getting the available projects list
projects = client.list_projects()
# ----

# Delete all created projects
for args in PROJECT_MATRIX.values():
    project = client.get_project(args["name"])
    project.delete()
# ----
