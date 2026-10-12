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

"""Frontend of the first page."""

import base64

from dash import dcc  # pyright: ignore[reportMissingTypeStubs]
from dash_extensions.enrich import Input, Output, State, html  # pyright: ignore[reportMissingTypeStubs]

from ansys.saf.glow.client import callback
from tests.mocks.solution_end_to_end.solution.definition import EndToEndSolution
from tests.mocks.solution_end_to_end.solution.maxwell_2d_setup_verification_step import Maxwell2DSetupVerificationStep


def layout(step: Maxwell2DSetupVerificationStep):
    # Keep websockets out of this page to avoid creating websockets every time we load the page with Selenium in any
    # test.
    """Layout of the first step UI."""
    return html.Div(
        [
            html.H1("We are in First Page"),
            html.Div(
                [
                    dcc.Upload(
                        id="aedt_project_file_uploader",
                        children=html.Button("Upload AEDT File"),
                        accept=".aedt",
                        multiple=False,
                    ),
                    html.Div(id="file_upload_completed", children="File not uploaded yet."),
                ],
            ),
        ],
    )


@callback(
    Output("file_upload_completed", "children"),
    [
        Input("aedt_project_file_uploader", "contents"),
        State("aedt_project_file_uploader", "filename"),
        State("url", "pathname"),
    ],
    prevent_initial_call=True,
)
def handle_file(contents: str, filename: str, project: EndToEndSolution):
    if contents and filename:
        content_string = contents.removeprefix("data:application/octet-stream;base64,")
        file_bytes = base64.b64decode(content_string)
        step = project.steps.maxwell_2d_verification_step
        # Store file via the storage scope at the transaction method (api-side)
        step.store_data_content_into_file_entity(file_content=file_bytes, file_name="api_" + filename)

        # Store file via the storage scope at project client
        storage_scope = project.storage_scope
        scoped_filepath = storage_scope.get_storage_root() / ("ui_" + filename)
        scoped_filepath.write_bytes(file_bytes)
        step.e2e_file_entity_ui = storage_scope.store(scoped_filepath)

        return "File uploaded."
    else:
        return "File not uploaded yet."
