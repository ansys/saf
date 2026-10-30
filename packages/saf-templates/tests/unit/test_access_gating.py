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


def _mentions(node: ast.AST, name: str) -> bool:
    return any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(node))


@pytest.mark.parametrize("step", PRIMARY_BUTTONS)
def test_project_access_banner_is_an_optional_import(step: str):
    """Pages must still import with a dash-super-components or GLOW release that has no access banner."""
    tree = ast.parse(_page_source(step))

    # no unconditional import of the banner at module level
    for node in tree.body:
        assert not (isinstance(node, ast.ImportFrom) and node.module == "ansys.solutions.dash_super_components"), (
            "ProjectAccessBanner must be imported in a try/except ImportError"
        )
    guarded = [
        node
        for node in tree.body
        if isinstance(node, ast.Try)
        and any(
            isinstance(child, ast.ImportFrom) and child.module == "ansys.solutions.dash_super_components"
            for child in ast.walk(node)
        )
    ]
    assert len(guarded) == 1
    assert any(
        isinstance(handler.type, ast.Name) and handler.type.id == "ImportError" for handler in guarded[0].handlers
    ), "the import must fall back when it raises ImportError"

    # module-level code may use the banner only through the availability flag
    for node in tree.body:
        if node is guarded[0] or not _mentions(node, "ProjectAccessBanner"):
            continue
        is_flag = isinstance(node, ast.Assign) and _mentions(node, "ACCESS_CONTROL_AVAILABLE")
        is_banner_helper = isinstance(node, ast.FunctionDef) and node.name == "_access_banner"
        is_guarded_block = (
            isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "ACCESS_CONTROL_AVAILABLE"
        )
        assert is_flag or is_banner_helper or is_guarded_block, (
            f"line {node.lineno}: ProjectAccessBanner is used outside the availability checks"
        )


@pytest.mark.parametrize("step", PRIMARY_BUTTONS)
def test_page_falls_back_to_no_banner_and_write_access_when_unavailable(step: str):
    tree = ast.parse(_page_source(step))
    helpers = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in ("_can_write", "_access_banner")
    ]
    assert {helper.name for helper in helpers} == {"_can_write", "_access_banner"}

    class FailingDashClient:
        @staticmethod
        def get_project_access(project_id: str):
            raise AssertionError("the access API must not be called when it is unavailable")

    namespace = {"ACCESS_CONTROL_AVAILABLE": False, "DashClient": FailingDashClient, "ProjectAccessBanner": None}
    exec(compile(ast.Module(body=helpers, type_ignores=[]), "<template>", "exec"), namespace)

    assert namespace["_can_write"]("project-id") is True
    assert namespace["_access_banner"]("project-id") == []


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
