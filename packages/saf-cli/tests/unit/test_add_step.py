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

from pathlib import Path
import re
from typing import Any
from unittest.mock import call

from cookiecutter.exceptions import FailedHookException  # pyright: ignore[reportMissingTypeStubs]
from packaging.specifiers import SpecifierSet
import pytest
from pytest_mock import MockerFixture
import tomlkit

from ansys.saf.cli._solutions.add_step import (
    WRONG_DASH_STRUCTURE_ERROR_MSG,
    add_step_to_solution,
    check_template_cli_compatibility,
    step_name_exists,
)
from ansys.saf.cli._solutions.backend_detection import SolutionBackend
from ansys.saf.cli._solutions.dependencies import DependencyManager
from ansys.saf.cli._solutions.plugins import SafTemplate
from ansys.saf.cli._utilities.backup import BackupManager
from ansys.saf.cli._utilities.conversion import namespace_to_path, to_module_name


@pytest.mark.usefixtures("tmp_path_as_working_dir")
@pytest.mark.parametrize("solution_name", ["solution_without_ui"], indirect=True)
@pytest.mark.parametrize("solution_namespace", [None, "ansys.solutions", "myorg.apps"], indirect=True)
def test_add_step_without_ui(
    root_solution_dir: Path,
    solution_dir: Path,
    solution_name: str,
    solution_namespace: str,
    default_saf_step_template: SafTemplate,
):
    """Test adding a step to a solution without UI."""
    add_step_to_solution(
        solution_name,
        root_solution_dir,
        solution_name,
        "test_step",
        "none",
        default_saf_step_template,
    )

    solution_definition_path = solution_dir / "solution" / "definition.py"
    assert solution_definition_path.is_file()

    solution_definition_content = solution_definition_path.read_text(encoding="utf-8")
    assert (
        f"from {solution_namespace}.{solution_name}.solution.test_step import TestStep" in solution_definition_content
    )
    assert "    test_step: TestStep" in solution_definition_content

    step_path = solution_dir / "solution" / "test_step.py"
    assert step_path.is_file()

    step_content = step_path.read_text(encoding="utf-8")
    assert "Backend of the test_step step." in step_content
    assert "class TestStep(StepModel):" in step_content

    test_page_path = solution_dir / "ui" / "pages" / "test_page.py"
    assert not test_page_path.is_file()


@pytest.mark.usefixtures("tmp_path_as_working_dir")
@pytest.mark.parametrize("solution_name", ["solution_without_ui"], indirect=True)
def test_add_step_with_ui_to_solution_without_ui(
    root_solution_dir: Path,
    solution_name: str,
    default_saf_step_template: SafTemplate,
):
    """Test adding a UI step to a solution without UI raises an exception."""
    error_msg = (
        "The step you are creating is using a different framework than the one you used to create the solution with."
    )
    with pytest.raises(RuntimeError, match=error_msg):
        add_step_to_solution(
            solution_name,
            root_solution_dir,
            solution_name,
            "test_step",
            "dash",
            default_saf_step_template,
        )


@pytest.mark.usefixtures("tmp_path_as_working_dir")
@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
def test_add_step_without_ui_to_solution_with_ui(
    root_solution_dir: Path,
    solution_name: str,
    solution_namespace: str,
    solution_dir: Path,
    default_saf_step_template: SafTemplate,
):
    """Test adding a No-UI step to a solution with UI adds only the step file."""
    add_step_to_solution(
        solution_name,
        root_solution_dir,
        solution_name,
        "test_step",
        "none",
        default_saf_step_template,
    )
    solution_definition_path = solution_dir / "solution" / "definition.py"
    assert solution_definition_path.is_file()

    solution_definition_content = solution_definition_path.read_text(encoding="utf-8")
    assert (
        f"from {solution_namespace}.{solution_name}.solution.test_step import TestStep" in solution_definition_content
    )
    assert "    test_step: TestStep" in solution_definition_content

    step_path = solution_dir / "solution" / "test_step.py"
    assert step_path.is_file()

    step_content = step_path.read_text(encoding="utf-8")
    assert "Backend of the test_step step." in step_content
    assert "class TestStep(StepModel):" in step_content

    test_page_path = solution_dir / "ui" / "pages" / "test_page.py"
    assert not test_page_path.is_file()


@pytest.mark.usefixtures("tmp_path_as_working_dir")
@pytest.mark.parametrize(
    "solution_name",
    ["solution_without_ui", "solution_with_dash_ui"],
    indirect=True,
)
def test_add_duplicated_step(
    root_solution_dir: Path,
    solution_name: str,
    solution_namespace: str,
    solution_ui_framework: str,
    default_saf_step_template: SafTemplate,
):
    """Test adding a step to a solution with the same name as an existing step raises an exception."""
    step_file = (
        root_solution_dir / "src" / namespace_to_path(solution_namespace) / solution_name / "solution" / "test_step.py"
    )
    ui_page_file = (
        root_solution_dir
        / "src"
        / namespace_to_path(solution_namespace)
        / solution_name
        / "ui"
        / "pages"
        / "test_page.py"
    )
    assert not step_file.is_file()
    assert not ui_page_file.is_file()

    add_step_to_solution(
        solution_name,
        root_solution_dir,
        solution_name,
        "test_step",
        solution_ui_framework,
        default_saf_step_template,
    )

    assert step_file.is_file()
    step_file.write_text("MOCK CONTENT")
    if solution_name != "solution_without_ui":
        assert ui_page_file.is_file()
        ui_page_file.write_text("MOCK CONTENT")

    with pytest.raises(FailedHookException):
        add_step_to_solution(
            solution_name,
            root_solution_dir,
            solution_name,
            "test_step",
            solution_ui_framework,
            default_saf_step_template,
        )

    # existing files are not overwritten
    assert "MOCK CONTENT" in step_file.read_text()
    if solution_name != "solution_without_ui":
        assert "MOCK CONTENT" in ui_page_file.read_text()


@pytest.mark.usefixtures("tmp_path_as_working_dir")
@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.parametrize("solution_namespace", [None, "ansys.solutions", "myorg.apps"], indirect=True)
def test_add_duplicated_step_partial_overwrite(
    root_solution_dir: Path,
    solution_name: str,
    solution_namespace: str,
    solution_ui_framework: str,
    default_saf_step_template: SafTemplate,
):
    """Test adding a step to a solution that overwrites only some of the existing files raises an exception."""
    step_file = (
        root_solution_dir / "src" / namespace_to_path(solution_namespace) / solution_name / "solution" / "test_step.py"
    )
    ui_page_file = (
        root_solution_dir
        / "src"
        / namespace_to_path(solution_namespace)
        / solution_name
        / "ui"
        / "pages"
        / "test_page.py"
    )
    assert not step_file.is_file()
    assert not ui_page_file.is_file()

    add_step_to_solution(
        solution_name,
        root_solution_dir,
        solution_name,
        "test_step",
        solution_ui_framework,
        default_saf_step_template,
    )

    step_file.unlink()  # so it would not be overwritten
    assert ui_page_file.is_file()
    ui_page_file.write_text("MOCK CONTENT")

    with pytest.raises(FailedHookException):
        add_step_to_solution(
            solution_name,
            root_solution_dir,
            solution_name,
            "test_step",
            solution_ui_framework,
            default_saf_step_template,
        )

    # existing files are not overwritten
    assert not step_file.is_file()
    assert "MOCK CONTENT" in ui_page_file.read_text()


@pytest.mark.usefixtures("tmp_path_as_working_dir")
@pytest.mark.parametrize(
    "solution_name",
    [
        "solution_with_dash_ui",
    ],
    indirect=True,
)
def test_add_step_with_ui(
    root_solution_dir: Path,
    solution_dir: Path,
    solution_name: str,
    solution_ui_framework: str,
    default_saf_step_template: SafTemplate,
):
    """Test adding a step to a solution with Dash UI."""
    main_page_path = solution_dir / "ui" / "pages" / "page.py"
    main_page_before = main_page_path.read_text(encoding="utf-8")

    add_step_to_solution(
        solution_name,
        root_solution_dir,
        solution_name,
        "test_step",
        solution_ui_framework,
        default_saf_step_template,
    )

    ui_page_path = solution_dir / "ui" / "pages" / "test_page.py"
    assert ui_page_path.is_file()
    ui_page_content = ui_page_path.read_text(encoding="utf-8")
    assert (
        'dash.register_page(__name__, name="Test Step", path_template="/projects/<project_id>/test-step"'
        in ui_page_content
    )
    assert "def layout(project: SolutionWithDashUiSolution):" in ui_page_content
    assert "step = project.steps.test_step" in ui_page_content

    # SAF CLI does not explicitly modify the page.py. Depends on the post-gen hooks of the step template
    main_page_after = main_page_path.read_text(encoding="utf-8")
    assert main_page_after == main_page_before


@pytest.mark.usefixtures("tmp_path_as_working_dir")
@pytest.mark.parametrize(
    "solution_name",
    [
        "solution_with_dash_ui",
    ],
    indirect=True,
)
def test_add_step_with_ui_older_nav_tree_pattern(
    root_solution_dir: Path,
    solution_dir: Path,
    solution_name: str,
    solution_ui_framework: str,
    default_saf_step_template: SafTemplate,
):
    """Test adding a Dash step fails for solutions that do not use multi-page Dash structure."""
    app_path = solution_dir / "ui" / "app.py"
    app_path.write_text(app_path.read_text(encoding="utf-8").replace("use_pages=True,", ""), encoding="utf-8")

    with pytest.raises(RuntimeError, match=re.escape(WRONG_DASH_STRUCTURE_ERROR_MSG)):
        add_step_to_solution(
            solution_name,
            root_solution_dir,
            solution_name,
            "test_step",
            solution_ui_framework,
            default_saf_step_template,
        )


@pytest.mark.usefixtures("tmp_path_as_working_dir")
@pytest.mark.parametrize(
    "solution_name",
    [
        "solution_without_ui",
        "solution_with_dash_ui",
    ],
    indirect=True,
)
@pytest.mark.parametrize("solution_namespace", [None, "ansys.solutions", "myorg.apps"], indirect=True)
def test_add_multiple_steps(
    root_solution_dir: Path,
    solution_dir: Path,
    solution_name: str,
    solution_namespace: str,
    solution_ui_framework: str,
    default_saf_step_template: SafTemplate,
):
    """Test adding multiple steps to a solution."""
    main_page_path = solution_dir / "ui" / "pages" / "page.py"
    main_page_before = main_page_path.read_text(encoding="utf-8") if solution_ui_framework != "none" else ""

    add_step_to_solution(
        solution_name,
        root_solution_dir,
        solution_name,
        "test_step",
        solution_ui_framework,
        default_saf_step_template,
    )
    add_step_to_solution(
        solution_name,
        root_solution_dir,
        solution_name,
        "another_step",
        solution_ui_framework,
        default_saf_step_template,
    )

    solution_definition_path = solution_dir / "solution" / "definition.py"
    assert solution_definition_path.is_file()

    solution_definition_content = solution_definition_path.read_text(encoding="utf-8")
    assert (
        f"from {solution_namespace}.{solution_name}.solution.test_step import TestStep" in solution_definition_content
    )
    assert (
        f"from {solution_namespace}.{solution_name}.solution.another_step import AnotherStep"
        in solution_definition_content
    )
    assert "    test_step: TestStep" in solution_definition_content
    assert "    another_step: AnotherStep" in solution_definition_content

    step_path = solution_dir / "solution" / "test_step.py"
    assert step_path.is_file()

    another_step_path = solution_dir / "solution" / "another_step.py"
    assert another_step_path.is_file()

    if solution_ui_framework != "none":
        ui_page_path = solution_dir / "ui" / "pages" / "test_page.py"
        assert ui_page_path.is_file()
        another_page_path = solution_dir / "ui" / "pages" / "another_page.py"
        assert another_page_path.is_file()
        main_page_after = main_page_path.read_text(encoding="utf-8")
        assert main_page_after == main_page_before


@pytest.mark.usefixtures("tmp_path_as_working_dir")
@pytest.mark.parametrize(
    "solution_name",
    [
        "solution_without_ui",
    ],
    indirect=True,
)
def test_add_step_without_definition(
    root_solution_dir: Path,
    solution_dir: Path,
    solution_name: str,
    default_saf_step_template: SafTemplate,
):
    """Test adding a step to a solution without a definition file."""
    definition_path = solution_dir / "solution" / "definition.py"
    definition_path.unlink()

    with pytest.raises(Exception, match=re.escape(f"Solution definition not found in {definition_path}.")):
        add_step_to_solution(
            solution_name,
            root_solution_dir,
            solution_name,
            "test_step",
            "none",
            default_saf_step_template,
        )


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
def test_check_template_cli_compatibility_missing_pyproject_no_template_saf_cli_compat_range(
    root_solution_dir: Path,
    default_saf_step_template_without_saf_cli_compat_range: SafTemplate,
    capsys: pytest.CaptureFixture[str],
) -> None:
    check_template_cli_compatibility(root_solution_dir, default_saf_step_template_without_saf_cli_compat_range)

    captured = capsys.readouterr()
    assert "Warning" not in captured.out


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
def test_check_template_cli_compatibility_missing_pyproject_with_template_saf_cli_compat_range(
    root_solution_dir: Path,
    default_saf_step_template: SafTemplate,
    capsys: pytest.CaptureFixture[str],
) -> None:
    default_saf_step_template.saf_cli_compatibility_range = SpecifierSet(">=1.0.0")

    check_template_cli_compatibility(root_solution_dir, default_saf_step_template)

    captured = capsys.readouterr()

    expected_warning = (
        f"Warning: Template '{default_saf_step_template.name}' declares the saf-cli compatibility constraint "
        f"'{default_saf_step_template.saf_cli_compatibility_range}', but the solution does not declare a valid "
        f"saf-cli version in pyproject.toml. The step might not work as expected."
    )
    assert expected_warning in captured.out


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.usefixtures("root_solution_dir_with_pyproject_and_lock")
def test_check_template_cli_compatibility_no_cli_version_no_template_saf_cli_compat_range(
    root_solution_dir: Path,
    default_saf_step_template_without_saf_cli_compat_range: SafTemplate,
    capsys: pytest.CaptureFixture[str],
) -> None:
    check_template_cli_compatibility(root_solution_dir, default_saf_step_template_without_saf_cli_compat_range)

    captured = capsys.readouterr()
    assert "Warning" not in captured.out


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.usefixtures("root_solution_dir_with_pyproject_and_lock")
def test_check_template_cli_compatibility_no_cli_version_with_template_saf_cli_compat_range(
    root_solution_dir_with_pyproject_and_lock: Path,
    default_saf_step_template: SafTemplate,
    capsys: pytest.CaptureFixture[str],
) -> None:
    default_saf_step_template.saf_cli_compatibility_range = SpecifierSet(">=1.0.0")

    check_template_cli_compatibility(root_solution_dir_with_pyproject_and_lock, default_saf_step_template)

    captured = capsys.readouterr()

    expected_warning = (
        f"Warning: Template '{default_saf_step_template.name}' declares the saf-cli compatibility constraint "
        f"'{default_saf_step_template.saf_cli_compatibility_range}', but the solution does not declare a valid "
        f"saf-cli version in pyproject.toml. The step might not work as expected."
    )
    assert expected_warning in captured.out


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.parametrize("root_solution_dir_with_pyproject_and_lock", [{"version": "invalid_version"}], indirect=True)
def test_check_template_cli_compatibility_invalid_cli_version_no_template_saf_cli_compat_range(
    root_solution_dir_with_pyproject_and_lock: Path,
    solution_name: str,
    default_saf_step_template_without_saf_cli_compat_range: SafTemplate,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pyproject_path = root_solution_dir_with_pyproject_and_lock / "pyproject.toml"
    saf_cli_version = (
        tomlkit.loads(
            pyproject_path.read_bytes(),
        )
        .unwrap()
        .get("saf-cli-version", {})
        .get("saf-cli-version")
    )
    assert saf_cli_version == "invalid_version"

    check_template_cli_compatibility(
        root_solution_dir_with_pyproject_and_lock,
        default_saf_step_template_without_saf_cli_compat_range,
    )

    captured = capsys.readouterr()
    assert "Warning" not in captured.out


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.parametrize("root_solution_dir_with_pyproject_and_lock", [{"version": "invalid_version"}], indirect=True)
def test_check_template_cli_compatibility_invalid_cli_version_with_template_saf_cli_compat_range(
    root_solution_dir_with_pyproject_and_lock: Path,
    solution_name: str,
    default_saf_step_template: SafTemplate,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pyproject_path = root_solution_dir_with_pyproject_and_lock / "pyproject.toml"
    saf_cli_version = (
        tomlkit.loads(
            pyproject_path.read_bytes(),
        )
        .unwrap()
        .get("saf-cli-version", {})
        .get("saf-cli-version")
    )
    assert saf_cli_version == "invalid_version"

    default_saf_step_template.saf_cli_compatibility_range = SpecifierSet(">=1.0.0")

    check_template_cli_compatibility(root_solution_dir_with_pyproject_and_lock, default_saf_step_template)

    captured = capsys.readouterr()

    expected_warning = (
        f"Warning: Template '{default_saf_step_template.name}' declares the saf-cli compatibility constraint "
        f"'{default_saf_step_template.saf_cli_compatibility_range}', but the solution does not declare a valid "
        f"saf-cli version in pyproject.toml. The step might not work as expected."
    )
    assert expected_warning in captured.out


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.parametrize("root_solution_dir_with_pyproject_and_lock", [{"version": "2.0.0"}], indirect=True)
def test_check_template_cli_compatibility_included_cli_version_but_no_template_saf_cli_compat_range(
    root_solution_dir_with_pyproject_and_lock: Path,
    solution_name: str,
    default_saf_step_template_without_saf_cli_compat_range: SafTemplate,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pyproject_path = root_solution_dir_with_pyproject_and_lock / "pyproject.toml"
    saf_cli_version = (
        tomlkit.loads(
            pyproject_path.read_bytes(),
        )
        .unwrap()
        .get("saf-cli-version", {})
        .get("saf-cli-version")
    )
    assert saf_cli_version == "2.0.0"

    check_template_cli_compatibility(
        root_solution_dir_with_pyproject_and_lock,
        default_saf_step_template_without_saf_cli_compat_range,
    )

    captured = capsys.readouterr()
    assert "Warning" not in captured.out


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.parametrize("root_solution_dir_with_pyproject_and_lock", [{"version": "2.0.0"}], indirect=True)
def test_check_template_cli_compatibility_version_mismatch(
    root_solution_dir_with_pyproject_and_lock: Path,
    solution_name: str,
    default_saf_step_template: SafTemplate,
) -> None:
    default_saf_step_template.saf_cli_compatibility_range = SpecifierSet("<=1.0.0")

    pyproject_path = root_solution_dir_with_pyproject_and_lock / "pyproject.toml"
    saf_cli_version = (
        tomlkit.loads(
            pyproject_path.read_bytes(),
        )
        .unwrap()
        .get("saf-cli-version", {})
        .get("saf-cli-version")
    )
    assert saf_cli_version == "2.0.0"

    expected_error = (
        f"Template '{default_saf_step_template.name}' requires a saf-cli version in the range "
        f"'{default_saf_step_template.saf_cli_compatibility_range}', "
        f"but the solution's saf-cli version is {saf_cli_version}."
    )
    with pytest.raises(ValueError, match=expected_error):
        check_template_cli_compatibility(root_solution_dir_with_pyproject_and_lock, default_saf_step_template)


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.parametrize("root_solution_dir_with_pyproject_and_lock", [{"version": "2.0.0"}], indirect=True)
def test_check_template_cli_compatibility_version_match(
    root_solution_dir_with_pyproject_and_lock: Path,
    solution_name: str,
    default_saf_step_template: SafTemplate,
    capsys: pytest.CaptureFixture[str],
) -> None:
    default_saf_step_template.saf_cli_compatibility_range = SpecifierSet(">=1.0.0")

    pyproject_path = root_solution_dir_with_pyproject_and_lock / "pyproject.toml"
    saf_cli_version = (
        tomlkit.loads(
            pyproject_path.read_bytes(),
        )
        .unwrap()
        .get("saf-cli-version", {})
        .get("saf-cli-version")
    )
    assert saf_cli_version == "2.0.0"

    check_template_cli_compatibility(root_solution_dir_with_pyproject_and_lock, default_saf_step_template)

    captured = capsys.readouterr()
    assert "Warning" not in captured.out


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
def test_step_name_exists_no_solution_definition(
    root_solution_dir: Path,
    solution_dir: Path,
    solution_name: str,
) -> None:
    definition_path = solution_dir / "solution" / "definition.py"
    definition_path.unlink()

    expected_error = re.escape(f"Solution definition not found in expected location: {definition_path}")
    with pytest.raises(FileNotFoundError, match=expected_error):
        step_name_exists(root_solution_dir, solution_name, "first_step")


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
def test_step_name_exists_when_step_in_definition(
    root_solution_dir: Path,
    solution_name: str,
) -> None:
    assert step_name_exists(root_solution_dir, solution_name, "first_step")


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
def test_step_name_exists_when_step_not_in_definition(
    root_solution_dir: Path,
    solution_name: str,
) -> None:
    assert not step_name_exists(root_solution_dir, solution_name, "fake_step")


@pytest.mark.usefixtures("tmp_path_as_working_dir")
@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.parametrize("solution_namespace", [None, "ansys.solutions", "myorg.apps"], indirect=True)
def test_add_step_rollback_on_definition_failure(
    root_solution_dir: Path,
    solution_dir: Path,
    solution_name: str,
    solution_namespace: str,
    solution_ui_framework: str,
    default_saf_step_template: SafTemplate,
    mocker: MockerFixture,
):
    if solution_ui_framework != "dash":
        pytest.skip("test only applies to dash UI solutions")

    page_path = solution_dir / "ui" / "pages" / "page.py"
    definition_path = solution_dir / "solution" / "definition.py"
    snapshot_before = BackupManager(
        root_solution_dir,
        solution_name,
        solution_namespace,
    )._snapshot_directory_paths()  # pyright: ignore[reportPrivateUsage]
    original_page = page_path.read_text()
    original_definition = definition_path.read_text()
    step_name = "test_step"
    step_module_name = to_module_name(step_name, "step")
    mocker.patch(
        "ansys.saf.cli._solutions.add_step._add_step_to_definition",
        side_effect=RuntimeError("simulated failure"),
    )
    with (
        pytest.raises(RuntimeError, match="simulated failure"),
        BackupManager(
            root_solution_dir,
            solution_name,
            solution_namespace,
        ),
    ):
        add_step_to_solution(
            solution_name,
            root_solution_dir,
            solution_name,
            step_name,
            solution_ui_framework,
            default_saf_step_template,
        )
    assert page_path.read_text() == original_page
    assert definition_path.read_text() == original_definition
    assert not (solution_dir / "solution" / f"{step_module_name}.py").exists()
    assert (
        BackupManager(root_solution_dir, solution_name, solution_namespace)._snapshot_directory_paths()  # pyright: ignore[reportPrivateUsage]
        == snapshot_before
    )  # pyright: ignore[reportPrivateUsage]
    poetry_lock = root_solution_dir / "poetry.lock"
    assert not poetry_lock.exists()


@pytest.mark.usefixtures("tmp_path_as_working_dir")
@pytest.mark.parametrize(
    ("solution_name", "ui_type", "step_name", "dependencies", "failure_patch_target", "error_message", "backend"),
    [
        pytest.param(
            "solution_without_ui",
            "none",
            "dep_step",
            {"requests": "^2.0"},
            None,
            None,
            SolutionBackend.POETRY,
            id="poetry_dependencies_success",
        ),
        pytest.param(
            "solution_without_ui",
            "none",
            "fail_step",
            {"requests": "^2.0"},
            "ansys.saf.cli._solutions.dependencies.DependencyManager.update_solution_dependencies",
            "dependency failure",
            SolutionBackend.POETRY,
            id="poetry_dependency_failure_rollback",
        ),
        pytest.param(
            "solution_without_ui",
            "none",
            "cc_fail",
            None,
            "ansys.saf.cli._solutions.add_step.cookiecutter",
            "cookiecutter failure",
            SolutionBackend.POETRY,
            id="poetry_cookiecutter_failure_rollback_and_propagation",
        ),
        pytest.param(
            "solution_with_dash_ui",
            "dash",
            "ui_fail",
            None,
            "ansys.saf.cli._solutions.add_step._validate_multi_page_dash_solution",
            "ui failure",
            SolutionBackend.POETRY,
            id="poetry_ui_update_failure_rollback",
        ),
        pytest.param(
            "solution_without_ui",
            "none",
            "dep_step",
            {"requests": ">=2.0"},
            None,
            None,
            SolutionBackend.UV,
            id="uv_dependencies_success",
        ),
        pytest.param(
            "solution_without_ui",
            "none",
            "fail_step",
            {"requests": ">=2.0"},
            "ansys.saf.cli._solutions.dependencies.DependencyManager.update_solution_dependencies",
            "dependency failure",
            SolutionBackend.UV,
            id="uv_dependency_failure_rollback",
        ),
    ],
    indirect=["solution_name"],
)
@pytest.mark.parametrize("solution_namespace", [None, "ansys.solutions", "myorg.apps"], indirect=True)
def test_add_step_workflow_success_and_rollback(
    root_solution_dir: Path,
    solution_dir: Path,
    solution_name: str,
    solution_namespace: str,
    ui_type: str,
    step_name: str,
    dependencies: dict[str, str] | None,
    failure_patch_target: str | None,
    error_message: str | None,
    default_saf_step_template: SafTemplate,
    mocker: MockerFixture,
    backend: SolutionBackend,
):
    """Validate success and rollback workflows for add-step in a single parameterized test."""

    mock_which = None
    if dependencies is not None:
        default_saf_step_template.dependencies = dependencies
        mock_backend = mocker.patch("ansys.saf.cli._solutions.add_step.parse_solution_backend")
        mock_backend.return_value.backend = backend
        mock_get_exec = mocker.patch(
            "ansys.saf.cli._solutions.add_step.get_exec_from_solution_venv",
            return_value=Path("fake"),
        )
        if backend is SolutionBackend.UV:
            mock_which = mocker.patch(
                "ansys.saf.cli._solutions.add_step.shutil.which",
                return_value=str(Path("fake_uv")),
            )
        mock_env = mocker.patch(
            "ansys.saf.cli._solutions.add_step.create_solution_environment",
            return_value={},
        )
        # Create a minimal pyproject.toml so DependencyManager.__init__ doesn't raise
        pyproject_path = root_solution_dir / "pyproject.toml"
        if not pyproject_path.is_file():
            pyproject_path.touch()
    else:
        mock_get_exec = None
        mock_env = None

    if failure_patch_target is None and dependencies is not None:
        mock_update = mocker.patch(
            "ansys.saf.cli._solutions.dependencies.DependencyManager.update_solution_dependencies",
            return_value=None,
        )
    elif failure_patch_target is not None:
        mock_update = mocker.patch(failure_patch_target, side_effect=RuntimeError(error_message))
    else:
        mock_update = None

    step_file = solution_dir / "solution" / f"{to_module_name(step_name, 'step')}.py"
    snapshot_before = BackupManager(
        root_solution_dir,
        solution_name,
        solution_namespace,
    )._snapshot_directory_paths()  # pyright: ignore[reportPrivateUsage]

    if error_message is None:
        add_step_to_solution(
            solution_name,
            root_solution_dir,
            solution_name,
            step_name,
            ui_type,
            default_saf_step_template,
        )

        assert step_file.exists()
        assert mock_get_exec is not None
        assert mock_env is not None
        assert mock_update is not None
        if backend is SolutionBackend.POETRY:
            mock_get_exec.assert_called_once()
        mock_env.assert_called_once()
        mock_update.assert_called_once()
    else:
        with (
            pytest.raises(RuntimeError, match=error_message),
            BackupManager(root_solution_dir, solution_name, solution_namespace),
        ):
            add_step_to_solution(
                solution_name,
                root_solution_dir,
                solution_name,
                step_name,
                ui_type,
                default_saf_step_template,
            )

        assert (
            BackupManager(root_solution_dir, solution_name, solution_namespace)._snapshot_directory_paths()  # pyright: ignore[reportPrivateUsage]
            == snapshot_before
        )  # pyright: ignore[reportPrivateUsage]

    if backend is SolutionBackend.UV:
        assert mock_get_exec is not None
        assert mock_which is not None
        assert mock_update is not None
        mock_get_exec.assert_not_called()
        mock_which.assert_called_once_with("uv")
        mock_update.assert_called_once_with(Path("fake_uv"), {})


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
def test_update_solution_dependencies_with_no_pyproject_fails(
    root_solution_dir: Path,
    default_saf_step_template: SafTemplate,
):
    with pytest.raises(
        FileNotFoundError,
        match=re.escape(f"pyproject.toml not found in solution root directory '{root_solution_dir}'"),
    ):
        DependencyManager(
            saf_template=default_saf_step_template,
            solution_root_dir=root_solution_dir,
        )


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
def test_update_solution_dependencies_with_no_main_dependencies_fails(
    root_solution_dir_with_pyproject_and_lock: Path,
    solution_name: str,
    default_saf_step_template: SafTemplate,
):
    dependency_manager = DependencyManager(
        saf_template=default_saf_step_template,
        solution_root_dir=root_solution_dir_with_pyproject_and_lock,
    )
    with pytest.raises(
        ValueError,
        match=re.escape(
            f"No main dependencies found in pyproject.toml at "
            f"'{root_solution_dir_with_pyproject_and_lock / 'pyproject.toml'}'.",
        ),
    ):
        dependency_manager.update_solution_dependencies(Path("fake_executable"), {})


@pytest.mark.usefixtures("install_custom_template_plugin_with_main_dep")
@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.parametrize("custom_saf_step_template", ["test_custom_templates_with_main_dep"], indirect=True)
@pytest.mark.parametrize(
    ("root_solution_dir_with_pyproject_and_lock", "template_dependencies", "backend"),
    [
        pytest.param({"main_dependencies": True}, None, SolutionBackend.POETRY, id="poetry"),
        pytest.param(
            {"backend": "uv", "main_dependencies": True},
            {"main": {"humanize": ">=4.15.0,<5.0.0"}},
            SolutionBackend.UV,
            id="uv",
        ),
    ],
    indirect=["root_solution_dir_with_pyproject_and_lock"],
)
def test_update_solution_dependencies_with_main_non_conflicting_dependency(
    root_solution_dir_with_pyproject_and_lock: Path,
    custom_saf_step_template: SafTemplate,
    mocker: MockerFixture,
    template_dependencies: dict[str, Any] | None,
    backend: SolutionBackend,
):
    if template_dependencies is not None:
        custom_saf_step_template.dependencies = template_dependencies
    dependency_manager = DependencyManager(
        saf_template=custom_saf_step_template,
        solution_root_dir=root_solution_dir_with_pyproject_and_lock,
    )
    mock_subprocess = mocker.patch("ansys.saf.cli._solutions.dependencies.subprocess.run")

    solution_env = {"VIRTUAL_ENV": "unrelated_environment", "UV_PROJECT_ENVIRONMENT": "unrelated_environment"}
    dependency_manager.update_solution_dependencies(
        Path("fake_executable"),
        solution_env if backend is SolutionBackend.UV else {},
    )

    assert mock_subprocess.call_count == 2

    pyproject_content = tomlkit.loads((root_solution_dir_with_pyproject_and_lock / "pyproject.toml").read_bytes())
    if backend is SolutionBackend.POETRY:
        assert "humanize" in pyproject_content["tool"]["poetry"]["dependencies"]  # type: ignore
        assert pyproject_content["tool"]["poetry"]["dependencies"]["humanize"] == "^4.15.0"  # type: ignore
    else:
        uv_content = pyproject_content.unwrap()
        assert uv_content["project"]["dependencies"] == ["ansys-saf-sdk==0.2.0", "humanize >=4.15.0,<5.0.0"]
        assert uv_content["dependency-groups"] == {}
        assert "poetry" not in uv_content["tool"]
        expected_env = {"UV_PROJECT_ENVIRONMENT": str((root_solution_dir_with_pyproject_and_lock / ".venv").resolve())}
        mock_subprocess.assert_has_calls(
            [
                call(
                    ["fake_executable", "lock", "--no-python-downloads"],
                    env=expected_env,
                    cwd=root_solution_dir_with_pyproject_and_lock,
                    check=True,
                ),
                call(
                    [
                        "fake_executable",
                        "sync",
                        "--locked",
                        "--no-default-groups",
                        "--inexact",
                        "--no-python-downloads",
                    ],
                    env=expected_env,
                    cwd=root_solution_dir_with_pyproject_and_lock,
                    check=True,
                ),
            ],
        )
        assert solution_env == {
            "VIRTUAL_ENV": "unrelated_environment",
            "UV_PROJECT_ENVIRONMENT": "unrelated_environment",
        }


@pytest.mark.usefixtures("install_custom_template_plugin_with_ui_dep")
@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.parametrize("custom_saf_step_template", ["test_custom_templates_with_ui_dep"], indirect=True)
@pytest.mark.parametrize(
    ("root_solution_dir_with_pyproject_and_lock", "template_dependencies", "backend"),
    [
        pytest.param(
            {"main_dependencies": True, "ui_dependencies": True},
            None,
            SolutionBackend.POETRY,
            id="poetry_existing_group",
        ),
        pytest.param({"main_dependencies": True}, None, SolutionBackend.POETRY, id="poetry_new_group"),
        pytest.param(
            {"backend": "uv", "main_dependencies": True, "ui_dependencies": True},
            {"ui": {"streamlit": ">=1.58.0,<2.0.0"}},
            SolutionBackend.UV,
            id="uv_existing_group",
        ),
        pytest.param(
            {"backend": "uv", "main_dependencies": True},
            {"ui": {"streamlit": ">=1.58.0,<2.0.0"}},
            SolutionBackend.UV,
            id="uv_new_group",
        ),
    ],
    indirect=["root_solution_dir_with_pyproject_and_lock"],
)
def test_update_solution_dependencies_with_ui_non_conflicting_dependency(
    root_solution_dir_with_pyproject_and_lock: Path,
    custom_saf_step_template: SafTemplate,
    mocker: MockerFixture,
    template_dependencies: dict[str, Any] | None,
    backend: SolutionBackend,
):
    if template_dependencies is not None:
        custom_saf_step_template.dependencies = template_dependencies
    original_content = tomlkit.loads(
        (root_solution_dir_with_pyproject_and_lock / "pyproject.toml").read_bytes(),
    ).unwrap()
    dependency_manager = DependencyManager(
        saf_template=custom_saf_step_template,
        solution_root_dir=root_solution_dir_with_pyproject_and_lock,
    )
    mock_subprocess = mocker.patch("ansys.saf.cli._solutions.dependencies.subprocess.run")

    dependency_manager.update_solution_dependencies(Path("fake_executable"), {})

    assert mock_subprocess.call_count == 2

    pyproject_content = tomlkit.loads((root_solution_dir_with_pyproject_and_lock / "pyproject.toml").read_bytes())
    if backend is SolutionBackend.POETRY:
        assert "streamlit" in pyproject_content["tool"]["poetry"]["group"]["ui"]["dependencies"]  # type: ignore
        assert pyproject_content["tool"]["poetry"]["group"]["ui"]["dependencies"]["streamlit"] == "^1.58.0"  # type: ignore
    else:
        uv_content = pyproject_content.unwrap()
        existing_ui = original_content.get("dependency-groups", {}).get("ui", [])
        assert uv_content["project"]["dependencies"] == ["ansys-saf-sdk==0.2.0"]
        assert uv_content["dependency-groups"]["ui"] == [*existing_ui, "streamlit >=1.58.0,<2.0.0"]
        assert "poetry" not in uv_content["tool"]
        assert mock_subprocess.call_args_list[0].args[0] == ["fake_executable", "lock", "--no-python-downloads"]
        assert mock_subprocess.call_args_list[1].args[0] == [
            "fake_executable",
            "sync",
            "--locked",
            "--no-default-groups",
            "--inexact",
            "--no-python-downloads",
            "--group",
            "ui",
        ]


@pytest.mark.usefixtures("install_custom_template_plugin_with_glow_and_ui_deps")
@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.parametrize("custom_saf_step_template", ["test_custom_templates_with_glow_and_ui_deps"], indirect=True)
@pytest.mark.parametrize(
    ("root_solution_dir_with_pyproject_and_lock", "template_dependencies", "backend"),
    [
        pytest.param(
            {"main_dependencies": True, "ui_dependencies": True},
            None,
            SolutionBackend.POETRY,
            id="poetry_existing_group",
        ),
        pytest.param({"main_dependencies": True}, None, SolutionBackend.POETRY, id="poetry_new_group"),
        pytest.param(
            {"backend": "uv", "main_dependencies": True, "ui_dependencies": True},
            {
                "main": {
                    "ansys-saf-sdk": {
                        "version": ">=0.2.0,<0.3.0",
                        "allow-prereleases": True,
                        "extras": ["core-hps"],
                    },
                },
                "ui": {"streamlit": ">=1.58.0,<2.0.0"},
            },
            SolutionBackend.UV,
            id="uv_existing_group",
        ),
        pytest.param(
            {"backend": "uv", "main_dependencies": True},
            {
                "main": {
                    "ansys-saf-sdk": {
                        "version": ">=0.2.0,<0.3.0",
                        "allow-prereleases": True,
                        "extras": ["core-hps"],
                    },
                },
                "ui": {"streamlit": ">=1.58.0,<2.0.0"},
            },
            SolutionBackend.UV,
            id="uv_new_group",
        ),
    ],
    indirect=["root_solution_dir_with_pyproject_and_lock"],
)
def test_update_solution_dependencies_with_conflicting_dependencies(
    root_solution_dir_with_pyproject_and_lock: Path,
    custom_saf_step_template: SafTemplate,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
    template_dependencies: dict[str, Any] | None,
    backend: SolutionBackend,
):
    if template_dependencies is not None:
        custom_saf_step_template.dependencies = template_dependencies
    original_content = tomlkit.loads(
        (root_solution_dir_with_pyproject_and_lock / "pyproject.toml").read_bytes(),
    ).unwrap()
    dependency_manager = DependencyManager(
        saf_template=custom_saf_step_template,
        solution_root_dir=root_solution_dir_with_pyproject_and_lock,
    )
    mock_subprocess = mocker.patch("ansys.saf.cli._solutions.dependencies.subprocess.run")

    dependency_manager.update_solution_dependencies(Path("fake_executable"), {})

    mock_subprocess.assert_not_called()

    pyproject_content = tomlkit.loads((root_solution_dir_with_pyproject_and_lock / "pyproject.toml").read_bytes())
    if backend is SolutionBackend.POETRY:
        assert "streamlit" in pyproject_content["tool"]["poetry"]["group"]["ui"]["dependencies"]  # type: ignore
        assert pyproject_content["tool"]["poetry"]["group"]["ui"]["dependencies"]["streamlit"] == "^1.58.0"  # type: ignore
    else:
        uv_content = pyproject_content.unwrap()
        existing_ui = original_content.get("dependency-groups", {}).get("ui", [])
        assert uv_content["project"]["dependencies"] == ["ansys-saf-sdk==0.2.0"]
        assert uv_content["dependency-groups"]["ui"] == [*existing_ui, "streamlit >=1.58.0,<2.0.0"]
        assert uv_content["tool"]["uv"] == {}
        assert "poetry" not in uv_content["tool"]

    # Check that the warning in dependencies.py is printed to stdout
    captured = capsys.readouterr()
    pyproject_path = root_solution_dir_with_pyproject_and_lock / "pyproject.toml"
    if backend is SolutionBackend.POETRY:
        expected_warning = (
            f"WARNING: the step template 'second-step' has some dependencies in common with the solution's "
            f"pyproject.toml at {pyproject_path}. Review the solution's pyproject.toml and manually update it if "
            f"necessary, to ensure that it is compatible with the step template's dependencies.\n\n"
            f"Step specification of the common dependencies:\n"
            f"  - ansys-saf-sdk (main): {{'version': '^0.2.0', 'allow-prereleases': True, "
            f"'extras': ['core-hps']}}\n\n"
            f"After reviewing the dependencies, please run:\n"
            f'  - saf execute solution_with_dash_ui "poetry lock"\n'
            f'  - saf execute solution_with_dash_ui "poetry install --with ui"\n'
        )
    else:
        expected_warning = (
            f"WARNING: the step template 'second-step' has some dependencies in common with the solution's "
            f"pyproject.toml at {pyproject_path}. Review the solution's pyproject.toml and manually update it if "
            f"necessary, to ensure that it is compatible with the step template's dependencies.\n\n"
            f"Step specification of the common dependencies:\n"
            f"  - ansys-saf-sdk (main): {{'version': '>=0.2.0,<0.3.0', 'allow-prereleases': True, "
            f"'extras': ['core-hps']}}\n\n"
            f"After reviewing the dependencies, please run:\n"
            f'  - saf execute solution_with_dash_ui "uv lock --no-python-downloads"\n'
            f'  - saf execute solution_with_dash_ui "uv sync --locked --no-default-groups --inexact '
            f'--no-python-downloads --group ui"\n'
        )
    assert expected_warning in captured.out


@pytest.mark.usefixtures("install_custom_template_plugin_with_glow_in_different_group")
@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.parametrize(
    "custom_saf_step_template",
    ["test_custom_templates_with_glow_in_different_group"],
    indirect=True,
)
@pytest.mark.parametrize(
    ("root_solution_dir_with_pyproject_and_lock", "template_dependencies", "backend"),
    [
        pytest.param({"main_dependencies": True}, None, SolutionBackend.POETRY, id="poetry"),
        pytest.param(
            {"backend": "uv", "main_dependencies": True},
            {
                "another_group": {
                    "ansys-saf-sdk": {
                        "version": ">=0.2.0,<0.3.0",
                        "allow-prereleases": True,
                        "extras": ["core-hps"],
                    },
                },
                "ui": {"streamlit": ">=1.58.0,<2.0.0"},
            },
            SolutionBackend.UV,
            id="uv",
        ),
    ],
    indirect=["root_solution_dir_with_pyproject_and_lock"],
)
def test_update_solution_dependencies_with_conflicting_dependency_in_different_group(
    root_solution_dir_with_pyproject_and_lock: Path,
    custom_saf_step_template: SafTemplate,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
    template_dependencies: dict[str, Any] | None,
    backend: SolutionBackend,
):
    if template_dependencies is not None:
        custom_saf_step_template.dependencies = template_dependencies
    dependency_manager = DependencyManager(
        saf_template=custom_saf_step_template,
        solution_root_dir=root_solution_dir_with_pyproject_and_lock,
    )
    mock_subprocess = mocker.patch("ansys.saf.cli._solutions.dependencies.subprocess.run")

    dependency_manager.update_solution_dependencies(Path("fake_executable"), {})

    mock_subprocess.assert_not_called()

    pyproject_content = tomlkit.loads((root_solution_dir_with_pyproject_and_lock / "pyproject.toml").read_bytes())
    if backend is SolutionBackend.POETRY:
        assert "another_group" in pyproject_content["tool"]["poetry"]["group"]  # type: ignore
        assert not pyproject_content["tool"]["poetry"]["group"]["another_group"]["dependencies"]  # type: ignore
        assert "streamlit" in pyproject_content["tool"]["poetry"]["group"]["ui"]["dependencies"]  # type: ignore
        assert pyproject_content["tool"]["poetry"]["group"]["ui"]["dependencies"]["streamlit"] == "^1.58.0"  # type: ignore
    else:
        uv_content = pyproject_content.unwrap()
        assert uv_content["project"]["dependencies"] == ["ansys-saf-sdk==0.2.0"]
        assert uv_content["dependency-groups"] == {"another_group": [], "ui": ["streamlit >=1.58.0,<2.0.0"]}
        assert uv_content["tool"]["uv"] == {}
        assert "poetry" not in uv_content["tool"]

    # Check that the warning in dependencies.py is printed to stdout
    captured = capsys.readouterr()
    pyproject_path = root_solution_dir_with_pyproject_and_lock / "pyproject.toml"
    if backend is SolutionBackend.POETRY:
        expected_warning = (
            f"WARNING: the step template 'second-step' has some dependencies in common with the solution's "
            f"pyproject.toml at {pyproject_path}. Review the solution's pyproject.toml and manually update it if "
            f"necessary, to ensure that it is compatible with the step template's dependencies.\n\n"
            f"Step specification of the common dependencies:\n"
            f"  - ansys-saf-sdk (another_group group): {{'version': '^0.2.0', 'allow-prereleases': True, "
            f"'extras': ['core-hps']}}\n\n"
            f"After reviewing the dependencies, please run:\n"
            f'  - saf execute solution_with_dash_ui "poetry lock"\n'
            f'  - saf execute solution_with_dash_ui "poetry install --with another_group,ui"\n'
        )
    else:
        expected_warning = (
            f"WARNING: the step template 'second-step' has some dependencies in common with the solution's "
            f"pyproject.toml at {pyproject_path}. Review the solution's pyproject.toml and manually update it if "
            f"necessary, to ensure that it is compatible with the step template's dependencies.\n\n"
            f"Step specification of the common dependencies:\n"
            f"  - ansys-saf-sdk (another_group group): {{'version': '>=0.2.0,<0.3.0', 'allow-prereleases': True, "
            f"'extras': ['core-hps']}}\n\n"
            f"After reviewing the dependencies, please run:\n"
            f'  - saf execute solution_with_dash_ui "uv lock --no-python-downloads"\n'
            f'  - saf execute solution_with_dash_ui "uv sync --locked --no-default-groups --inexact '
            f'--no-python-downloads --group another_group --group ui"\n'
        )
    assert expected_warning in captured.out


@pytest.mark.parametrize("solution_name", ["solution_with_dash_ui"], indirect=True)
@pytest.mark.parametrize("root_solution_dir_with_pyproject_and_lock", [{"backend": "uv"}], indirect=True)
@pytest.mark.parametrize(
    ("specification", "expected_requirement", "expected_prereleases"),
    [
        pytest.param(">=2.0,<3.0", "requests >=2.0,<3.0", {}, id="version_string"),
        pytest.param(
            {
                "version": ">=2.0,<3.0",
                "extras": ["socks"],
                "markers": "python_version >= '3.12'",
                "allow-prereleases": True,
            },
            "requests[socks] >=2.0,<3.0; python_version >= '3.12'",
            {"requests": "allow"},
            id="extras_markers_prereleases_allowed",
        ),
        pytest.param(
            {"version": ">=2.0,<3.0", "allow-prereleases": False},
            "requests >=2.0,<3.0",
            {"requests": "disallow"},
            id="prereleases_disallowed",
        ),
    ],
)
def test_update_solution_dependencies_with_uv_requirement_options(
    root_solution_dir_with_pyproject_and_lock: Path,
    default_saf_step_template: SafTemplate,
    mocker: MockerFixture,
    specification: str | dict[str, Any],
    expected_requirement: str,
    expected_prereleases: dict[str, str],
):
    """Write UV requirement options without changing the SAF template declaration."""
    default_saf_step_template.dependencies = {"main": {"requests": specification}}
    dependency_manager = DependencyManager(
        saf_template=default_saf_step_template,
        solution_root_dir=root_solution_dir_with_pyproject_and_lock,
    )
    mock_subprocess = mocker.patch("ansys.saf.cli._solutions.dependencies.subprocess.run")

    dependency_manager.update_solution_dependencies(Path("fake_executable"), {})

    pyproject_content = tomlkit.loads(
        (root_solution_dir_with_pyproject_and_lock / "pyproject.toml").read_bytes(),
    ).unwrap()
    assert pyproject_content["project"]["dependencies"] == [expected_requirement]
    assert pyproject_content["tool"]["uv"].get("prerelease-package", {}) == expected_prereleases
    assert "poetry" not in pyproject_content["tool"]
    assert default_saf_step_template.dependencies == {"main": {"requests": specification}}
    assert mock_subprocess.call_count == 2
