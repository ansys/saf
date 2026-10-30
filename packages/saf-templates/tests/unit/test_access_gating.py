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

"""The step templates must not re-enable their primary button for a user without the project write lock.

The page templates are cookiecutter files that cannot run as they are, so these tests render the placeholders with
dummy values, parse the result, and check the source of the callbacks.
"""

import ast
from pathlib import Path
import re

import pytest

import ansys.saf.templates as templates

STEPS_DIR = Path(templates.__file__).parent / "steps"
PAGE_GLOB = "**/ui/pages/*cookiecutter.__ui_page_file_name*.py"

# step template -> id suffix of its primary action button
PRIMARY_BUTTONS = {
    "calculator": "-calculate",
    "hps_job_submission/hps_simple_job": "-simple-hps-calculate",
    "hps_job_submission/hps_parametric_study": "-parametric-study-calculate",
    "instance_management/geometry": "-launch-geometry-button",
}


def _page_source(step: str) -> str:
    (page,) = (STEPS_DIR / step).glob(PAGE_GLOB)
    source = page.read_text(encoding="utf-8")
    return re.sub(
        r"\{\{\s*cookiecutter\.(\w+)\s*\}\}",
        lambda match: "Solution" if "class" in match.group(1) else "my_step",
        source,
    )


def _callbacks_writing_disabled(source: str, button_suffix: str) -> dict[str, ast.FunctionDef]:
    """Return the callbacks (by name) that have the ``disabled`` property of the primary button as an output."""
    callbacks: dict[str, ast.FunctionDef] = {}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            decorator_source = ast.get_source_segment(source, decorator) or ""
            outputs = re.findall(r'Output\("my_step' + re.escape(button_suffix) + r'", "disabled"', decorator_source)
            if outputs:
                callbacks[node.name] = node
    return callbacks


def _calls_can_write(function: ast.FunctionDef) -> bool:
    return any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_can_write"
        for node in ast.walk(function)
    )


# Callbacks that only ever disable the primary button (on a click), so they cannot re-enable it
ONLY_DISABLE_THE_BUTTON = {"sync_controls_on_clicks"}


@pytest.mark.parametrize("step", PRIMARY_BUTTONS)
def test_every_callback_writing_the_primary_button_checks_write_access(step: str):
    source = _page_source(step)
    callbacks = _callbacks_writing_disabled(source, PRIMARY_BUTTONS[step])

    assert any(name.startswith("toggle_") for name in callbacks), "the banner-driven toggle callback is missing"
    ungated = [
        name
        for name, function in callbacks.items()
        if name not in ONLY_DISABLE_THE_BUTTON and not _calls_can_write(function)
    ]
    assert not ungated, f"{ungated} can re-enable the primary button of a user without write access"
