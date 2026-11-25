# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
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

"""Unit tests for the resources the package declares to Dash."""

from pathlib import Path
import re

from dash import Dash, html
import pytest

import ansys_saf_projects_dashboard
from ansys_saf_projects_dashboard import ProjectsDashboard

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
COMPONENT_SUITE_URL = "/_dash-component-suites/ansys_saf_projects_dashboard"


@pytest.fixture
def client():
    """Return a test client of a production app whose index page has registered the package resources."""
    app = Dash(__name__)
    app.layout = html.Div(ProjectsDashboard(id="dashboard"))
    client = app.server.test_client()
    index = client.get("/")
    assert index.status_code == 200
    return client, index.get_data(as_text=True)


def test_proptypes_script_is_not_served_outside_debug_mode(client):
    _, index_html = client
    assert "proptypes" not in index_html


@pytest.mark.parametrize("font", ["SourceSans3.ttf", "SourceCodePro.ttf"])
def test_fonts_of_the_bundle_styles_are_served(client, font):
    test_client, _ = client
    response = test_client.get(f"{COMPONENT_SUITE_URL}/assets/fonts/{font}")
    assert response.status_code == 200
    assert response.data


def test_every_python_component_is_exported_by_the_bundle_entry_point():
    # proptypes.js and Dash look up each component in the bundle namespace.
    index_ts = (PACKAGE_ROOT / "src" / "ts" / "index.ts").read_text(encoding="utf-8")
    export_block = re.search(r"export \{(.*?)\};", index_ts, re.DOTALL)
    assert export_block is not None
    exported = set(re.findall(r"^\s*(\w+),", export_block.group(1), re.MULTILINE))
    assert set(ansys_saf_projects_dashboard.__all__) <= exported


def test_proptypes_enum_values_are_not_quoted_twice():
    # Without the fix of generate_components.py, the browser rejects valid values such as "list".
    proptypes = (Path(ansys_saf_projects_dashboard.__file__).parent / "proptypes.js").read_text(encoding="utf-8")
    assert "pt.oneOf(" in proptypes
    assert "\"'" not in proptypes
