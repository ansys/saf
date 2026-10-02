# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from fastmcp import FastMCP


def register_guidance_tools(app: FastMCP, workflow: str) -> None:
    @app.tool()
    def solution_workflow() -> str:  # pyright: ignore[reportUnusedFunction]
        """Step by step workflow guideline for using the Solution."""
        return workflow

    @app.tool()
    def saf_concepts() -> str:  # pyright: ignore[reportUnusedFunction]
        """Generic explanation of SAF solution concepts: projects, steps, fields, entity handles, transactions."""
        return """\
        A SAF solution is a guided simulation workflow made of the following building blocks:

        - Project: a persisted instance of the solution. All data, files, and transaction state belong to
        exactly one project. Use the "project" toolset (create_project, list_projects, delete_projects,
        import_project, export_project) to manage projects.
        - Step: a named stage of the workflow (e.g. "geometry", "mesh", "solve"). Each step owns a set of
        fields and the transactions that operate on them. Discover a solution's steps and transactions via
        the "solution_workflow" tool.
        - Field: a typed piece of data owned by a step (numbers, strings, booleans, custom pydantic models,
        or entity handles). Read and write fields with the get_fields and set_fields tools.
        - Entity handle: a field type that references file content (inputs, results, meshes, images, etc.)
        stored outside the field itself, either directly or nested in a list, dict, or custom object field.
        Read and write their bytes with download_data and upload_data.
        - Transaction: a step method that downloads some fields, does work, and uploads other fields.
        Transactions are the only supported way to mutate step data; run them with the generated
        "<step_name>__<transaction_name>" tools. Each transaction tool's description states which fields it
        downloads, which it uploads, its arguments, and its return type.
        - Long-running transaction: a transaction that keeps running after its tool call returns. Start it
        with its tool as usual, then block on completion with wait_for_longrunning_transaction.

        Typical usage: create or open a project, inspect the workflow, set input fields and upload input
        files, run transactions in the order the workflow describes, then read output fields and download
        output files.
        """
