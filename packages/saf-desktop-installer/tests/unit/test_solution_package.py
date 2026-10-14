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

import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
from typing import Any
from unittest.mock import patch

import pytest
import pytest_mock
import toml

from ansys.saf.desktop.installer._package import manage_dependencies
from ansys.saf.desktop.installer._package.config import InstallerConfig
from ansys.saf.desktop.installer._package.manage_dependencies import add_wheels, copy_files, delete_encrypted_files
from ansys.saf.desktop.installer._package.solution import (
    SolutionInfo,
    create_solution_metadata,
    get_solution_module_dotted_path,
    get_solution_module_name,
    get_solution_namespace_info,
    get_solution_package_dir,
)
from ansys.saf.desktop.installer._package.solution_package import (
    _restore_third_party,  # pyright: ignore[reportPrivateUsage]
    _zip_third_party,  # pyright: ignore[reportPrivateUsage]
    build_executable_installer,
    setup_solution_folder,
)
from tests.conftest import CUSTOM_PACKAGE_FOR_TEST_2_WHEEL_NAMES


def test_merge_group_dependencies_adds_extras_to_main_dependency():
    dependencies: dict[str, Any] = {
        "example-package": {"version": "^1.0", "extras": ["main-extra"], "python": ">=3.11"},
    }
    poetry: dict[str, Any] = {
        "group": {
            "desktop": {"dependencies": {"example_package": {"version": "^2.0", "extras": ["desktop-extra"]}}},
            "ui": {"dependencies": {"example-package": {"extras": ["ui-extra", "main-extra"]}}},
            "doc": {"dependencies": {"example-package": {"extras": ["doc-extra"]}}},
        },
    }

    manage_dependencies.merge_group_dependencies(["desktop", "ui", "doc"], poetry, dependencies)

    assert dependencies == {
        "example-package": {
            "version": "^1.0",
            "extras": ["main-extra", "desktop-extra", "ui-extra", "doc-extra"],
            "python": ">=3.11",
        },
    }


def test_merge_group_dependencies_adds_extras_to_string_main_dependency():
    dependencies: dict[str, Any] = {"example-package": "^1.0"}
    poetry: dict[str, Any] = {
        "group": {"desktop": {"dependencies": {"example_package": {"extras": ["desktop-extra"]}}}},
    }

    manage_dependencies.merge_group_dependencies(["desktop"], poetry, dependencies)

    assert dependencies == {"example-package": {"version": "^1.0", "extras": ["desktop-extra"]}}


def test_relativize_lock_path_dependencies(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    definitions_folder = tmp_path / "definitions" / "my_solution"
    definitions_folder.mkdir(parents=True)
    inside = (definitions_folder / "dep-1.0.0-py3-none-any.whl").as_posix()
    nested = (definitions_folder / "sub" / "nested-1.0.0-py3-none-any.whl").as_posix()
    outside = (tmp_path / "elsewhere" / "other-1.0.0-py3-none-any.whl").as_posix()
    multi_a = (definitions_folder / "multi-1.0.0-cp312-cp312-win_amd64.whl").as_posix()
    multi_b = (definitions_folder / "multi-1.0.0-cp312-cp312-manylinux_2_17_x86_64.whl").as_posix()
    lock_content = f"""[[package]]
name = "my-solution"
version = "0.1.0"

[package.dependencies]
dep = {{path = "{inside}"}}
nested = {{path = "{nested}"}}
other = {{path = "{outside}"}}
relative = {{path = "relative-1.0.0-py3-none-any.whl"}}
multi = [
    {{path = "{multi_a}", markers = "sys_platform == \\"win32\\""}},
    {{path = "{multi_b}", markers = "sys_platform == \\"linux\\""}},
]

[package.source]
type = "file"
url = "my_solution-0.1.0-py3-none-any.whl"
"""
    poetry_lock = definitions_folder / "poetry.lock"
    poetry_lock.write_text(lock_content, encoding="utf-8")

    manage_dependencies.relativize_lock_path_dependencies(definitions_folder)

    dependencies = toml.loads(poetry_lock.read_text(encoding="utf-8"))["package"][0]["dependencies"]
    assert dependencies["dep"] == {"path": "dep-1.0.0-py3-none-any.whl"}
    assert dependencies["nested"] == {"path": "sub/nested-1.0.0-py3-none-any.whl"}
    assert dependencies["other"] == {"path": outside}
    assert dependencies["relative"] == {"path": "relative-1.0.0-py3-none-any.whl"}
    assert [constraint["path"] for constraint in dependencies["multi"]] == [
        "multi-1.0.0-cp312-cp312-win_amd64.whl",
        "multi-1.0.0-cp312-cp312-manylinux_2_17_x86_64.whl",
    ]
    assert 'url = "my_solution-0.1.0-py3-none-any.whl"' in poetry_lock.read_text(encoding="utf-8")
    assert "other-1.0.0-py3-none-any.whl" in caplog.text


def test_add_poetry_project_relativizes_lock_path_dependencies(tmp_path: Path) -> None:
    solution_root_dir = tmp_path / "solution"
    solution_root_dir.mkdir()
    pyproject = solution_root_dir / "pyproject.toml"
    pyproject.write_text(
        '[tool.poetry]\nname = "my-solution"\n\n[tool.poetry.dependencies]\npython = ">=3.11,<3.13"\n',
        encoding="utf-8",
    )
    definitions_folder = tmp_path / "definitions"
    definitions_folder.mkdir()
    with (
        patch("ansys.saf.desktop.installer._package.manage_dependencies.subprocess.check_output"),
        patch(
            "ansys.saf.desktop.installer._package.manage_dependencies.relativize_lock_path_dependencies",
        ) as mock_relativize,
    ):
        manage_dependencies.add_poetry_project(Path("python"), pyproject, definitions_folder, "3.12")
    mock_relativize.assert_called_once_with(definitions_folder)


@pytest.fixture
def mock_installer_config(solution_root_dir: Path) -> InstallerConfig:
    return InstallerConfig(
        encryption_file=solution_root_dir / "obfuscate.txt",
        pyproject_location=solution_root_dir / "pyproject.toml",
        python_version="3.11.10",
    )


@pytest.fixture
def mock_subprocess_calls(  # noqa: C901
    mocker: pytest_mock.MockFixture,
    solution_root_dir: Path,
) -> pytest_mock.MockType:
    expected_doc_html = solution_root_dir / "doc" / "build" / "html" / "index.html"
    expected_exec = (
        solution_root_dir / "dist" / ("test-installer.exe" if platform.system() == "Windows" else "test-installer")
    )
    python_dir = solution_root_dir / "dist" / "solution" / "third_party" / "python"
    linux_expected_python_exec = python_dir / "bin" / "python3"
    windows_source_expected_python_exec = python_dir / "python.exe"
    windows_nuget_expected_python_exec = python_dir / "tools" / "python.exe"

    def _mock_subprocess_run(args: list[str], **kwargs: dict[str, Any]):  # type: ignore
        if args == ["sphinx-build", "doc/source", "doc/build/html", "--color", "-vW", "-bhtml"]:
            if not (solution_root_dir / "doc").is_dir():
                raise subprocess.CalledProcessError(1, args, "mock error when building doc", "")
            if any((solution_root_dir / "doc").iterdir()):
                expected_doc_html.parent.mkdir(parents=True, exist_ok=True)
                expected_doc_html.write_text("mock_documentation")
        elif args == ["poetry", "version", "--no-interaction"]:
            return subprocess.CompletedProcess(args, 0, "ansys-solutions-my-solution-dash 0.1", "")
        elif args[-4:] == ["-m", "pip", "--disable-pip-version-check", "--version"]:
            return subprocess.CompletedProcess(args, 0, "pip 22.3.1 from mock_directory", "")
        elif args == ["poetry", "build", "--no-interaction"]:
            expected_tmp_wheel = (
                Path(kwargs["cwd"])  # type: ignore
                / "dist"
                / "ansys_solutions_my_solution_dash-0.1.dev0-py3-none-any.whl"
            )
            expected_tmp_wheel.parent.mkdir(parents=True, exist_ok=True)
            expected_tmp_wheel.touch()
            return subprocess.CompletedProcess(args, 0, f"Built {expected_tmp_wheel.name}", "")
        elif "pyinstaller" in str(args[0]):
            expected_exec.parent.mkdir(parents=True, exist_ok=True)
            expected_exec.touch()
        elif args == ["make", "install"]:
            linux_expected_python_exec.parent.mkdir(parents=True)
            linux_expected_python_exec.touch()
        elif args == ["cmd", "/c", "PCBuild\\build.bat", "-e"]:
            windows_source_expected_python_exec.touch()
            windows_nuget_expected_python_exec.parent.mkdir(parents=True)
            windows_nuget_expected_python_exec.touch()

        return subprocess.CompletedProcess(args, 0, b"", b"")  # type: ignore

    subprocess_run_mock = mocker.patch("subprocess.run")
    subprocess_run_mock.side_effect = _mock_subprocess_run

    return subprocess_run_mock


@pytest.mark.usefixtures("mock_subprocess_calls", "mock_solution_display_name")
def test_package_missing_obfuscate_txt(solution_root_dir: Path, mock_installer_config: InstallerConfig):
    assert not (solution_root_dir / "obfuscate.txt").is_file()
    mock_installer_config.encrypt = True
    with pytest.raises(
        FileNotFoundError,
        match=re.escape(f"Could not find file {solution_root_dir / 'obfuscate.txt'}. Make sure the file exists."),
    ):
        setup_solution_folder(SolutionInfo(solution_root_dir), mock_installer_config)


@pytest.fixture
def mock_encrypted_files(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    source_file1 = tmp_path / "src" / "ansys" / "solutions" / "my_solution" / "factor.txt"
    source_file2 = tmp_path / "src" / "ansys" / "solutions" / "my_solution" / "data.json"
    encrypted_file1 = tmp_path / "src" / "ansys" / "solutions" / "my_solution" / "factor.txt.encrypted"
    encrypted_file2 = tmp_path / "src" / "ansys" / "solutions" / "my_solution" / "data.json.encrypted"

    source_file1.parent.mkdir(parents=True, exist_ok=True)
    source_file1.write_text("original content 1")
    source_file2.write_text("original content 2")
    encrypted_file1.write_text("encrypted content 1")
    encrypted_file2.write_text("encrypted content 2")

    return source_file1, source_file2, encrypted_file1, encrypted_file2


def test_delete_encrypted_files_removes_encrypted_artifacts(
    tmp_path: Path,
    mock_encrypted_files: tuple[Path, Path, Path, Path],
):
    """Verify that delete_encrypted_files removes .encrypted counterparts from solution root."""
    source_file1, source_file2, encrypted_file1, encrypted_file2 = mock_encrypted_files

    encryption_manifest = tmp_path / "encrypt_manifest.txt"
    encryption_manifest.write_text(
        "src/ansys/solutions/my_solution/factor.txt\nsrc/ansys/solutions/my_solution/data.json\n",
    )

    assert encrypted_file1.read_text() == "encrypted content 1"
    assert encrypted_file2.read_text() == "encrypted content 2"

    delete_encrypted_files(tmp_path, encryption_manifest)

    assert not encrypted_file1.exists()
    assert not encrypted_file2.exists()
    assert source_file1.read_text() == "original content 1"
    assert source_file2.read_text() == "original content 2"


def test_delete_encrypted_files_is_idempotent(tmp_path: Path, mock_encrypted_files: tuple[Path, Path, Path, Path]):
    """Verify that delete_encrypted_files safely handles missing encrypted files."""
    source_file, _, encrypted_file, _ = mock_encrypted_files

    encryption_manifest = tmp_path / "encrypt_manifest.txt"
    encryption_manifest.write_text("src/ansys/solutions/my_solution/factor.txt")

    delete_encrypted_files(tmp_path, encryption_manifest)

    assert not encrypted_file.exists()
    assert source_file.read_text() == "original content 1"

    # No encrypted file exists, but cleanup should not fail
    delete_encrypted_files(tmp_path, encryption_manifest)

    # Original file should remain untouched
    assert not encrypted_file.exists()
    assert source_file.read_text() == "original content 1"


def test_delete_encrypted_files_raises_error_on_missing_manifest(tmp_path: Path):
    """Verify that delete_encrypted_files raises exception when manifest file is missing."""
    nonexistent_file = tmp_path / "nonexistent_manifest.txt"
    with pytest.raises(
        FileNotFoundError,
        match=re.escape(f"Could not find file {nonexistent_file}. Make sure the file exists."),
    ):
        delete_encrypted_files(tmp_path, nonexistent_file)


@pytest.mark.parametrize(
    "files_file_content",
    [
        "%s\n%s\n",
        "  %s  \n  %s  \n",
        "\n%s\n\n%s\n\n",
        "   \n%s\n\t\n%s\n  \t  \n",
    ],
    ids=["basic", "leading_trailing_spaces", "empty_lines", "whitespace_only_lines"],
)
def test_delete_encrypted_files_ignores_empty_lines(
    tmp_path: Path,
    files_file_content: str,
    mock_encrypted_files: tuple[Path, Path, Path, Path],
):
    """Verify that delete_encrypted_files skips empty lines in the manifest."""
    source_file1, source_file2, encrypted_file1, encrypted_file2 = mock_encrypted_files

    encryption_manifest = tmp_path / "encrypt_manifest.txt"
    encryption_manifest.write_text(
        files_file_content
        % ("src/ansys/solutions/my_solution/factor.txt", "src/ansys/solutions/my_solution/data.json"),
    )

    delete_encrypted_files(tmp_path, encryption_manifest)

    assert not encrypted_file1.exists()
    assert not encrypted_file2.exists()
    assert source_file1.read_text() == "original content 1"
    assert source_file2.read_text() == "original content 2"


def test_delete_encrypted_files_handles_backslash_paths(
    tmp_path: Path,
    mock_encrypted_files: tuple[Path, Path, Path, Path],
):
    """Verify that delete_encrypted_files handles manifest entries with backslashes."""
    source_file, _, encrypted_file, _ = mock_encrypted_files

    encryption_manifest = tmp_path / "encrypt_manifest.txt"
    encryption_manifest.write_text(".\\src\\ansys\\solutions\\my_solution\\factor.txt\n")

    assert encrypted_file.read_text() == "encrypted content 1"

    delete_encrypted_files(tmp_path, encryption_manifest)

    assert not encrypted_file.exists()
    assert source_file.read_text() == "original content 1"


def test_get_solution_package_dir_from_glow_solution_definition(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
):
    monkeypatch.setenv(
        "GLOW_SOLUTION_DEFINITION",
        "synopsys.platform.solutions.my_solution_dash.solution.definition",
    )

    expected_solution_package_dir = (
        solution_root_dir / "src" / "synopsys" / "platform" / "solutions" / "my_solution_dash"
    )
    expected_solution_package_dir.mkdir(parents=True, exist_ok=True)

    solution_package_dir = get_solution_package_dir(solution_root_dir, "my_solution_dash")

    assert solution_package_dir == expected_solution_package_dir


@pytest.mark.parametrize(
    ("solution_root_dir", "module_name", "expected_namespace_path"),
    [
        ("my-solution-dash", "my_solution_dash", "ansys/solutions"),
        ("synopsys-custom-ns-solution", "custom_ns_solution", "synopsys"),
    ],
    indirect=["solution_root_dir"],
)
def test_get_solution_package_dir_falls_back_to_org_directory_under_src(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
    module_name: str,
    expected_namespace_path: str,
):
    monkeypatch.delenv("GLOW_SOLUTION_DEFINITION", raising=False)

    solution_package_dir = get_solution_package_dir(solution_root_dir, module_name)

    assert solution_package_dir == solution_root_dir / "src" / expected_namespace_path / module_name


def test_get_solution_module_name_from_glow_solution_definition(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
):
    monkeypatch.setenv(
        "GLOW_SOLUTION_DEFINITION",
        "synopsys.solutions.my_solution_dash.solution.definition",
    )

    solution_module_name = get_solution_module_name(solution_root_dir)

    assert solution_module_name == "my_solution_dash"


def test_get_solution_module_name_falls_back_to_org_directory_under_src(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
):
    monkeypatch.delenv("GLOW_SOLUTION_DEFINITION", raising=False)

    solution_module_name = get_solution_module_name(solution_root_dir)

    assert solution_module_name == "my_solution_dash"


def test_get_solution_module_dotted_path_from_glow_solution_definition(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
):
    monkeypatch.setenv(
        "GLOW_SOLUTION_DEFINITION",
        "synopsys.platform.solutions.my_solution_dash.solution.definition",
    )

    solution_module_dotted_path = get_solution_module_dotted_path(solution_root_dir, "my_solution_dash")

    assert solution_module_dotted_path == "synopsys.platform.solutions.my_solution_dash"


def test_get_solution_module_dotted_path_falls_back_to_org_directory_under_src(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
):
    monkeypatch.delenv("GLOW_SOLUTION_DEFINITION", raising=False)

    solution_module_dotted_path = get_solution_module_dotted_path(solution_root_dir, "my_solution_dash")

    assert solution_module_dotted_path == "ansys.solutions.my_solution_dash"


def test_get_solution_module_name_from_synopsys_namespace(tmp_path: Path) -> None:
    """Namespace resolution via filesystem scan returns the correct module for a single-segment custom namespace."""
    solution_root_dir = tmp_path / "synopsys-custom-ns-solution"
    pkg_dir = solution_root_dir / "src" / "synopsys" / "custom_ns_solution" / "solution"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "definition.py").write_text("# stub")

    module_name = get_solution_module_name(solution_root_dir)

    assert module_name == "custom_ns_solution"


def test_get_solution_module_dotted_path_from_synopsys_namespace(tmp_path: Path) -> None:
    """Dotted path is built from the single-segment synopsys namespace root."""
    solution_root_dir = tmp_path / "synopsys-custom-ns-solution"
    pkg_dir = solution_root_dir / "src" / "synopsys" / "custom_ns_solution" / "solution"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "definition.py").write_text("# stub")

    dotted_path = get_solution_module_dotted_path(solution_root_dir, "custom_ns_solution")

    assert dotted_path == "synopsys.custom_ns_solution"


def test_get_solution_package_dir_from_synopsys_namespace(tmp_path: Path) -> None:
    """Package dir resolves to src/synopsys/custom_ns_solution for the custom namespace mock."""
    solution_root_dir = tmp_path / "synopsys-custom-ns-solution"
    expected_pkg_dir = solution_root_dir / "src" / "synopsys" / "custom_ns_solution"
    (expected_pkg_dir / "solution").mkdir(parents=True)
    (expected_pkg_dir / "solution" / "definition.py").write_text("# stub")

    package_dir = get_solution_package_dir(solution_root_dir, "custom_ns_solution")

    assert package_dir == expected_pkg_dir


def test_get_solution_module_name_from_glow_solution_definition_synopsys(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
) -> None:
    """GLOW_SOLUTION_DEFINITION with synopsys single-segment namespace yields correct module name."""
    monkeypatch.setenv(
        "GLOW_SOLUTION_DEFINITION",
        "synopsys.custom_ns_solution.solution.definition",
    )

    module_name = get_solution_module_name(solution_root_dir)

    assert module_name == "custom_ns_solution"


def test_get_solution_module_dotted_path_from_glow_solution_definition_synopsys(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
) -> None:
    """GLOW_SOLUTION_DEFINITION with synopsys single-segment namespace yields correct dotted path."""
    monkeypatch.setenv(
        "GLOW_SOLUTION_DEFINITION",
        "synopsys.custom_ns_solution.solution.definition",
    )

    dotted_path = get_solution_module_dotted_path(solution_root_dir, "custom_ns_solution")

    assert dotted_path == "synopsys.custom_ns_solution"


def test_get_solution_package_dir_from_glow_solution_definition_synopsys(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
) -> None:
    """GLOW_SOLUTION_DEFINITION with synopsys single-segment namespace yields correct package dir."""
    monkeypatch.setenv(
        "GLOW_SOLUTION_DEFINITION",
        "synopsys.custom_ns_solution.solution.definition",
    )

    expected_package_dir = solution_root_dir / "src" / "synopsys" / "custom_ns_solution"
    expected_package_dir.mkdir(parents=True, exist_ok=True)

    package_dir = get_solution_package_dir(solution_root_dir, "custom_ns_solution")

    assert package_dir == expected_package_dir


def test_get_solution_package_dir_raises_if_env_resolved_path_does_not_exist(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
) -> None:
    monkeypatch.setenv(
        "GLOW_SOLUTION_DEFINITION",
        "synopsys.custom_ns_solution.solution.definition",
    )

    expected_package_dir = solution_root_dir / "src" / "synopsys" / "custom_ns_solution"

    with pytest.raises(
        FileNotFoundError,
        match=re.escape(
            f"Solution package directory does not exist: {expected_package_dir}",
        ),
    ):
        get_solution_package_dir(solution_root_dir, "custom_ns_solution")


def test_get_solution_namespace_info_raises_on_invalid_glow_solution_definition(
    monkeypatch: pytest.MonkeyPatch,
    solution_root_dir: Path,
) -> None:
    """get_solution_namespace_info raises ValueError when GLOW_SOLUTION_DEFINITION has invalid format."""

    # Missing ".solution.definition" suffix
    monkeypatch.setenv("GLOW_SOLUTION_DEFINITION", "synopsys.custom_ns_solution")

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Invalid GLOW_SOLUTION_DEFINITION value: 'synopsys.custom_ns_solution'. "
            "Expected format: '<namespace_root>.<module>.solution.definition'.",
        ),
    ):
        get_solution_namespace_info(solution_root_dir)


def test_get_solution_namespace_info_raises_when_no_solution_found(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """get_solution_namespace_info raises FileNotFoundError when no solution/definition.py exists."""

    solution_root_dir = tmp_path / "empty-solution"
    solution_root_dir.mkdir()
    (solution_root_dir / "src").mkdir()

    monkeypatch.delenv("GLOW_SOLUTION_DEFINITION", raising=False)

    with pytest.raises(
        FileNotFoundError,
        match=re.escape(f"Could not find solution module under {solution_root_dir / 'src'}."),
    ):
        get_solution_namespace_info(solution_root_dir)


def test_get_solution_namespace_info_raises_when_multiple_solutions_found(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """get_solution_namespace_info raises ValueError when autodiscovery finds multiple solutions."""

    solution_root_dir = tmp_path / "multi-solution"
    first_solution_dir = solution_root_dir / "src" / "ansys" / "solutions" / "first_solution" / "solution"
    second_solution_dir = solution_root_dir / "src" / "synopsys" / "second_solution" / "solution"
    first_solution_dir.mkdir(parents=True)
    second_solution_dir.mkdir(parents=True)
    (first_solution_dir / "definition.py").write_text("# test")
    (second_solution_dir / "definition.py").write_text("# test")

    monkeypatch.delenv("GLOW_SOLUTION_DEFINITION", raising=False)

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Multiple solution packages were found under "
            f"{solution_root_dir / 'src'}: ['ansys.solutions.first_solution', 'synopsys.second_solution']. "
            "Set GLOW_SOLUTION_DEFINITION to the target solution.",
        ),
    ):
        get_solution_namespace_info(solution_root_dir)


@pytest.mark.parametrize("solution_root_dir", ["synopsys-custom-ns-solution"], indirect=True)
def test_create_solution_metadata_with_synopsys_namespace(
    solution_root_dir: Path,
    mock_installer_config: InstallerConfig,
) -> None:
    """create_solution_metadata writes synopsys namespace fields to solution-metadata.json."""

    (solution_root_dir / "dist" / "solution").mkdir(parents=True, exist_ok=True)
    solution_info = SolutionInfo(solution_root_dir)

    with (
        patch(
            "ansys.saf.desktop.installer._package.solution.get_solution_display_name",
            return_value="Custom NS Solution",
        ),
        patch(
            "ansys.saf.desktop.installer._package.solution.get_solution_version",
            return_value="0.1.dev0",
        ),
    ):
        create_solution_metadata(solution_info, mock_installer_config)

    metadata_path = solution_root_dir / "dist" / "solution" / "solution-metadata.json"
    assert metadata_path.is_file()
    metadata = json.loads(metadata_path.read_text())
    assert metadata["solution-module-name"] == "custom_ns_solution"
    assert metadata["solution-main-module"] == "synopsys.custom_ns_solution.main"
    assert metadata["solution-name"] == "synopsys-custom-ns-solution"
    assert metadata["solution-display-name"] == "Custom NS Solution"
    assert metadata["solution-version"] == "0.1.dev0"


@pytest.mark.usefixtures("mock_subprocess_calls", "mock_solution_display_name")
def test_package_with_no_readme_key_in_pyproject(solution_root_dir: Path, mock_installer_config: InstallerConfig):
    solution_info = SolutionInfo(solution_root_dir)

    pyproject_content = toml.load(mock_installer_config.pyproject_location)
    pyproject_content.setdefault("tool", {}).setdefault("poetry", {}).pop("readme", None)
    with Path.open(mock_installer_config.pyproject_location, "w") as f:
        toml.dump(pyproject_content, f)

    with pytest.raises(
        ValueError,
        match=re.escape(f"No readme file specified in {mock_installer_config.pyproject_location}."),
    ):
        setup_solution_folder(solution_info, mock_installer_config)


@pytest.mark.parametrize(
    "readme_value",
    [["README.md", "README.str"], {"file": "README.md", "content-type": "text/markdown"}],
)
@pytest.mark.usefixtures("mock_subprocess_calls", "mock_solution_display_name")
def test_package_with_readme_key_is_not_str(
    readme_value: dict[str, str] | list[str],
    solution_root_dir: Path,
    mock_installer_config: InstallerConfig,
):
    solution_info = SolutionInfo(solution_root_dir)

    pyproject_content = toml.load(mock_installer_config.pyproject_location)
    pyproject_content.setdefault("tool", {}).setdefault("poetry", {})["readme"] = readme_value

    with Path.open(mock_installer_config.pyproject_location, "w") as f:
        toml.dump(pyproject_content, f)

    expected_warning_msg = f"The readme field in {mock_installer_config.pyproject_location} is not a string."
    with pytest.raises(
        TypeError,
        match=re.escape(expected_warning_msg),
    ):
        setup_solution_folder(solution_info, mock_installer_config)


@pytest.mark.usefixtures("mock_subprocess_calls", "mock_solution_display_name")
def test_package_with_missing_readme_file(
    solution_root_dir: Path,
    mock_installer_config: InstallerConfig,
):
    solution_info = SolutionInfo(solution_root_dir)

    pyproject_content = toml.load(mock_installer_config.pyproject_location)
    readme_value = "README.md"
    pyproject_content.setdefault("tool", {}).setdefault("poetry", {})["readme"] = readme_value

    with Path.open(mock_installer_config.pyproject_location, "w") as f:
        toml.dump(pyproject_content, f)

    # Remove the README.md file to simulate the missing file scenario
    readme_path = solution_root_dir / readme_value
    readme_path.unlink(missing_ok=True)
    with pytest.raises(
        FileNotFoundError,
        match=re.escape(
            f"The readme file {readme_path} does not exist.",
        ),
    ):
        setup_solution_folder(solution_info, mock_installer_config)


@pytest.mark.usefixtures("mock_subprocess_calls", "mock_solution_display_name")
def test_package_with_readme_random_format(
    solution_root_dir: Path,
    mock_installer_config: InstallerConfig,
):
    solution_info = SolutionInfo(solution_root_dir)
    solution_package_name = "ansys-solutions-my-solution-dash"
    solution_info._solution_package_name = solution_package_name  # pyright: ignore[reportPrivateUsage]
    solution_version = "0.1.dev0"
    solution_info._solution_version = solution_version  # pyright: ignore[reportPrivateUsage]

    pyproject_content = toml.load(mock_installer_config.pyproject_location)
    readme_value = "READMEfast.py"
    pyproject_content.setdefault("tool", {}).setdefault("poetry", {})["readme"] = readme_value

    with Path.open(mock_installer_config.pyproject_location, "w") as f:
        toml.dump(pyproject_content, f)

    # Create a README.md file with random content
    (solution_root_dir / readme_value).touch(exist_ok=True)

    with patch("ansys.saf.desktop.installer._package.manage_dependencies.modify_solution_wheel_metadata"):
        setup_solution_folder(solution_info, mock_installer_config)


@pytest.mark.parametrize("poetry_version", ["1.8.4", "2.3.2"], ids=["poetry_below_2", "poetry_2_or_higher"])
@pytest.mark.usefixtures("mock_subprocess_calls", "mock_solution_display_name")
def test_package_with_mock_solution(
    mock_installer_config: InstallerConfig,
    solution_root_dir: Path,
    poetry_version: str,
):
    solution_info = SolutionInfo(solution_root_dir)
    pyproject_path = solution_root_dir / "pyproject.toml"
    pyproject_path.write_text(
        pyproject_path.read_text().replace(
            'build-system-version = "2.3.2"',
            f'build-system-version = "{poetry_version}"',
            1,
        ),
    )
    with patch("ansys.saf.desktop.installer._package.manage_dependencies.modify_solution_wheel_metadata"):
        setup_solution_folder(solution_info, mock_installer_config)
    build_executable_installer(
        solution_folder=solution_info.solution_root_dir / "dist" / "solution",
        output_folder=solution_info.solution_root_dir / "dist",
        solution_display_name=solution_info.solution_display_name,
    )

    # documentation is built
    expected_doc_html = solution_root_dir / "doc" / "build" / "html" / "index.html"
    assert expected_doc_html.is_file()

    # documentation is copied to src/
    assert (
        solution_root_dir / "src" / "ansys" / "solutions" / "my_solution_dash" / "html-doc" / "index.html"
    ).read_text() == "mock_documentation"

    # solution wheel is generated
    expected_wheel = solution_root_dir / "dist" / "ansys_solutions_my_solution_dash-0.1.dev0-py3-none-any.whl"
    assert expected_wheel.is_file()

    # pyinstaller-based executable is generated
    expected_exec = (
        solution_root_dir / "dist" / ("test-installer.exe" if platform.system() == "Windows" else "test-installer")
    )
    assert expected_exec.is_file()

    # metadata, version and desktop_deployment scripts are generated
    solution_location = solution_root_dir / "dist" / "solution"
    assert (solution_location / "solution-metadata.json").is_file()
    assert (solution_location / "version.txt").is_file()
    assert (solution_location / "solution_desktop_deployment.py").is_file()

    # python binary is downloaded
    python_dir = solution_location / "third_party" / "python"
    assert next(python_dir.glob(f"**/{'python.exe' if platform.system() == 'Windows' else 'python3'}")).is_file()

    # local pyproject.toml wheels are copied to the definitions directory
    expected_wheel_dir = solution_root_dir / "dist" / "solution" / "definitions" / "my_solution_dash"
    current_platform = platform.system()
    expected_wheel_name = CUSTOM_PACKAGE_FOR_TEST_2_WHEEL_NAMES.get(current_platform)
    assert expected_wheel_name is not None, f"Unsupported platform: {current_platform}"
    assert (expected_wheel_dir / expected_wheel_name).is_file()
    dist_pyproject = expected_wheel_dir / "pyproject.toml"
    # And wheel paths are updated in the dist pyproject.toml
    assert "build_assets" not in dist_pyproject.read_text()

    # pip and poetry requirement files are generated with the correct content
    expected_tools_dir = solution_root_dir / "dist" / "solution" / "definitions" / "my_solution_dash" / "tools"
    pip_requirements = expected_tools_dir / "pip_requirements.txt"
    poetry_requirements = expected_tools_dir / "poetry_requirements.txt"
    assert pip_requirements.is_file()
    assert "pip==" in pip_requirements.read_text()
    assert poetry_requirements.is_file()
    pyproject = toml.load(solution_root_dir / "pyproject.toml")
    poetry_version = pyproject["build-system-requirements"]["build-system-version"]
    poetry_requirements_content = poetry_requirements.read_text()
    assert f"poetry=={poetry_version}" in poetry_requirements_content
    if poetry_version == "2.3.2":
        assert "poetry-plugin-export>=1.8" in poetry_requirements_content
    else:
        assert "poetry-plugin-export" not in poetry_requirements_content


@pytest.mark.parametrize("error_type", ["failure_to_build", "no_output"])
@pytest.mark.usefixtures("mock_subprocess_calls", "mock_solution_display_name")
def test_package_without_documentation(
    error_type: str,
    mock_installer_config: InstallerConfig,
    solution_root_dir: Path,
    mocker: pytest_mock.MockerFixture,
):
    solution_info = SolutionInfo(solution_root_dir)

    expected_doc_html = solution_root_dir / "doc" / "build" / "html"
    solution_html_doc = solution_root_dir / "src" / "ansys" / "solutions" / "my_solution_dash" / "html-doc"

    if error_type == "failure_to_build":
        shutil.rmtree(solution_root_dir / "doc")
        expected_warning_msg = (
            "Failed to build documentation: mock error when building doc\n"
            f"Fix the errors or manually copy the documentation to {solution_html_doc}."
        )
    elif error_type == "no_output":
        shutil.rmtree(solution_root_dir / "doc" / "source")
        expected_warning_msg = f"Documentation built directory {expected_doc_html} does not exist. Skipping..."
    else:
        pytest.fail(f"Invalid parameter value {error_type=}")

    mock_log_warning = mocker.patch("logging.Logger.warning")

    solution_display_name = "Fake Solution Display Name"
    with patch("ansys.saf.desktop.installer._package.manage_dependencies.modify_solution_wheel_metadata"):
        setup_solution_folder(solution_info, mock_installer_config)
    build_executable_installer(
        solution_folder=solution_root_dir / "dist" / "solution",
        output_folder=solution_root_dir / "dist",
        solution_display_name=solution_display_name,
    )

    # documentation build proc didn't generate any html output
    assert not expected_doc_html.is_dir()

    # documentation is not copied to src/
    assert not solution_html_doc.is_dir()

    # Expected msg is shown to user
    assert mock_log_warning.call_count == 2
    assert mock_log_warning.call_args_list[0][0][0] == expected_warning_msg

    # Rest of files are successfully generated
    solution_dist_dir = solution_root_dir / "dist"
    assert (solution_dist_dir / "ansys_solutions_my_solution_dash-0.1.dev0-py3-none-any.whl").is_file()
    assert (
        solution_dist_dir / ("test-installer.exe" if platform.system() == "Windows" else "test-installer")
    ).is_file()
    assert (solution_dist_dir / "solution" / "solution-metadata.json").is_file()
    assert (solution_dist_dir / "solution" / "version.txt").is_file()
    assert (solution_dist_dir / "solution" / "solution_desktop_deployment.py").is_file()
    python_dir = solution_dist_dir / "solution" / "third_party" / "python"
    assert next(python_dir.glob(f"**/{'python.exe' if platform.system() == 'Windows' else 'python3'}")).is_file()


@pytest.fixture
def mock_encrypt_solution(mocker: pytest_mock.MockerFixture) -> None:
    # Mock encrypt_solution to simulate the encryption process without requiring translation-utilities:
    # delete original files and create encrypted versions

    def _mock_encrypt_solution(encryption_file: Path, root: Path, encryption_key: str | None = None):
        for line in encryption_file.read_text().splitlines():
            file_path_str = line.strip().replace("\\", "/")
            if not file_path_str:
                continue
            original = root / file_path_str
            if original.is_file():
                encrypted = original.with_suffix(original.suffix + ".encrypted")
                encrypted.write_text(original.read_text() + " [encrypted]")
                original.unlink()

    mocker.patch(
        "ansys.saf.desktop.installer._package.manage_dependencies.encrypt_solution",
        side_effect=_mock_encrypt_solution,
    )


@pytest.mark.usefixtures("mock_subprocess_calls", "mock_solution_display_name", "mock_encrypt_solution")
def test_encryption_workflow_when_adding_wheels(
    solution_root_dir: Path,
    mock_installer_config: InstallerConfig,
    mocker: pytest_mock.MockerFixture,
):
    """Verify that encrypted files are cleaned from solution root after encryption build."""
    # Mock the build_wheel and download functions to avoid wheel file processing
    mocker.patch.object(manage_dependencies, "build_wheel_using_poetry")
    mocker.patch.object(manage_dependencies, "get_packages_with_wheel_url_deps", return_value=[])
    mocker.patch.object(manage_dependencies, "download_internal_dependencies")
    copy_files_spy = mocker.spy(manage_dependencies, "copy_files")
    delete_encrypted_files_spy = mocker.spy(manage_dependencies, "delete_encrypted_files")

    # Setup: Create encryption manifest with a file to encrypt
    solution_module_name = "my_solution_dash"
    file_to_encrypt = (
        solution_root_dir / "src" / "ansys" / "solutions" / solution_module_name / "method_assets" / "factor.txt"
    )
    file_to_encrypt.parent.mkdir(parents=True, exist_ok=True)
    file_to_encrypt.write_text("original content")
    encryption_manifest = solution_root_dir / "encrypt_manifest.txt"
    encryption_manifest.write_text(f"src/ansys/solutions/{solution_module_name}/method_assets/factor.txt\n")

    # Execute: call add_wheels with encryption enabled
    mock_installer_config.encrypt = True
    mock_installer_config.encryption_file = encryption_manifest

    definitions_folder = solution_root_dir / "dist" / "solution" / "definitions" / solution_module_name
    definitions_folder.mkdir(parents=True, exist_ok=True)

    venv_python_exec = solution_root_dir / ".venv" / "Scripts" / "python.exe"
    venv_python_exec.parent.mkdir(parents=True, exist_ok=True)
    venv_python_exec.touch()

    add_wheels(
        definitions_folder,
        venv_python_exec,
        solution_root_dir,
        solution_module_name,
        "Test Solution",
        mock_installer_config,
        "3.11.14",
    )

    # Assert: Original file is restored, encrypted file is cleaned up
    encrypted_file = file_to_encrypt.with_suffix(".txt.encrypted")
    assert not encrypted_file.exists()
    assert file_to_encrypt.read_text() == "original content"
    assert copy_files_spy.call_count == 2
    assert delete_encrypted_files_spy.call_count == 1


@pytest.mark.usefixtures("mock_subprocess_calls", "mock_solution_display_name", "mock_encrypt_solution")
def test_encryption_workflow_when_adding_wheels_executes_finally_on_error(
    solution_root_dir: Path,
    mock_installer_config: InstallerConfig,
    mocker: pytest_mock.MockerFixture,
):
    """Verify finally restores and cleans files when wheel build fails after encryption."""
    mocker.patch.object(
        manage_dependencies,
        "build_wheel_using_poetry",
        side_effect=RuntimeError("mock wheel build failure"),
    )
    copy_files_spy = mocker.spy(manage_dependencies, "copy_files")
    delete_encrypted_files_spy = mocker.spy(manage_dependencies, "delete_encrypted_files")

    # Setup: Create encryption manifest with a file to encrypt
    solution_module_name = "my_solution_dash"
    file_to_encrypt = (
        solution_root_dir / "src" / "ansys" / "solutions" / solution_module_name / "method_assets" / "factor.txt"
    )

    file_to_encrypt.parent.mkdir(parents=True, exist_ok=True)
    file_to_encrypt.write_text("original content")
    encryption_manifest = solution_root_dir / "encrypt_manifest.txt"
    encryption_manifest.write_text(f"src/ansys/solutions/{solution_module_name}/method_assets/factor.txt\n")

    # Execute: call add_wheels with encryption enabled
    mock_installer_config.encrypt = True
    mock_installer_config.encryption_file = encryption_manifest

    definitions_folder = solution_root_dir / "dist" / "solution" / "definitions" / solution_module_name
    definitions_folder.mkdir(parents=True, exist_ok=True)

    venv_python_exec = solution_root_dir / ".venv" / "Scripts" / "python.exe"
    venv_python_exec.parent.mkdir(parents=True, exist_ok=True)
    venv_python_exec.touch()

    with pytest.raises(RuntimeError, match="mock wheel build failure"):
        add_wheels(
            definitions_folder,
            venv_python_exec,
            solution_root_dir,
            solution_module_name,
            "Test Solution",
            mock_installer_config,
            "3.11.14",
        )

    # Assert: Original file is restored, encrypted file is cleaned up
    encrypted_file = file_to_encrypt.with_suffix(".txt.encrypted")
    assert not encrypted_file.exists()
    assert file_to_encrypt.read_text() == "original content"
    assert copy_files_spy.call_count == 2
    assert delete_encrypted_files_spy.call_count == 1


@pytest.fixture
def copy_files_setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create source files and directories for copy_files tests."""
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    files_file_path = tmp_path / "files_to_encrypt.txt"
    source_dir.mkdir()
    target_dir.mkdir()
    (source_dir / "file1.txt").write_text("content1")
    (source_dir / "sub").mkdir()
    (source_dir / "sub" / "file2.txt").write_text("content2")
    return source_dir, target_dir, files_file_path


@pytest.mark.parametrize(
    "files_file_content",
    [
        "file1.txt\nsub/file2.txt\n",
        "  file1.txt  \n  sub/file2.txt  \n",
        "\nfile1.txt\n\nsub/file2.txt\n\n",
        "   \nfile1.txt\n\t\nsub/file2.txt\n  \t  \n",
        "file1.txt\nsub\\file2.txt\n",
    ],
    ids=["basic", "leading_trailing_spaces", "empty_lines", "whitespace_only_lines", "backslash_paths"],
)
def test_copy_files(copy_files_setup: tuple[Path, Path, Path], files_file_content: str):
    source_dir, target_dir, files_file_path = copy_files_setup
    files_file_path.write_text(files_file_content)

    copy_files(source_dir, target_dir, files_file_path)

    # Act: files are copied to target directory with same relative paths,
    # and original content is preserved
    assert (target_dir / "file1.txt").read_text() == "content1"
    assert (target_dir / "sub" / "file2.txt").read_text() == "content2"
    assert (source_dir / "file1.txt").read_text() == "content1"
    assert (source_dir / "sub" / "file2.txt").read_text() == "content2"


def test_copy_files_missing_manifest(copy_files_setup: tuple[Path, Path, Path]):
    source_dir, target_dir, files_file_path = copy_files_setup
    with pytest.raises(FileNotFoundError, match="Could not find file"):
        copy_files(source_dir, target_dir, files_file_path)


def test_copy_files_missing_source_file(copy_files_setup: tuple[Path, Path, Path]):
    source_dir, target_dir, files_file_path = copy_files_setup
    files_file_path.write_text("nonexistent.txt\n")
    with pytest.raises(FileNotFoundError, match="source File"):
        copy_files(source_dir, target_dir, files_file_path)


@pytest.fixture
def third_party_folder(tmp_path: Path) -> Path:
    tp = tmp_path / "third_party"
    (tp / "python").mkdir(parents=True)
    (tp / "python" / "libssl-3.dll").write_bytes(b"\x4d\x5a" + b"\x00" * 10)
    (tp / "python" / "python.exe").write_bytes(b"\x4d\x5a" + b"\x00" * 10)
    (tp / "data.txt").write_text("payload")
    return tmp_path


@pytest.mark.parametrize(
    ("platform_system", "has_third_party", "should_zip"),
    [
        ("Windows", True, True),
        ("Windows", False, False),
        ("Linux", True, False),
    ],
    ids=["windows_zips", "windows_missing_dir", "linux_noop"],
)
def test_zip_third_party(
    third_party_folder: Path,
    mocker: pytest_mock.MockerFixture,
    platform_system: str,
    has_third_party: bool,
    should_zip: bool,
) -> None:
    """Test _zip_third_party across platforms and file existence scenarios."""
    mocker.patch("ansys.saf.desktop.installer._package.solution_package.platform.system", return_value=platform_system)

    if not has_third_party:
        import shutil as _shutil

        _shutil.rmtree(third_party_folder / "third_party")

    result = _zip_third_party(third_party_folder)

    if should_zip:
        assert result is not None
        assert result == third_party_folder / "third_party.zip"
        assert result.is_file()
        assert not (third_party_folder / "third_party").exists()
        # Verify ZIP contains all files
        import zipfile as _zipfile

        with _zipfile.ZipFile(result) as zf:
            names = set(zf.namelist())
            assert {"python/libssl-3.dll", "python/python.exe", "data.txt"}.issubset(names)
            # Verify no third_party/ prefix in entries
            for name in names:
                assert not name.startswith("third_party/"), f"ZIP entry has unexpected prefix: {name}"
    else:
        assert result is None
        if has_third_party:
            assert (third_party_folder / "third_party").is_dir()


@pytest.mark.parametrize(
    "zip_exists",
    [
        True,
        False,
        None,
    ],
    ids=["valid_zip", "missing_zip", "none_zip_path"],
)
def test_restore_third_party(
    third_party_folder: Path,
    zip_exists: bool | None,
) -> None:
    """Test _restore_third_party with various ZIP existence scenarios."""
    expected_extracted = bool(zip_exists) and platform.system() == "Windows"

    if zip_exists is True:
        zip_path = _zip_third_party(third_party_folder)
        if platform.system() == "Windows":
            assert zip_path is not None
    elif zip_exists is False:
        zip_path = third_party_folder / "third_party.zip"
    else:  # None
        zip_path = None

    _restore_third_party(third_party_folder, zip_path)

    third_party = third_party_folder / "third_party"
    if expected_extracted:
        assert (third_party / "python" / "libssl-3.dll").is_file()
        assert (third_party / "python" / "python.exe").is_file()
        assert (third_party / "data.txt").read_text() == "payload"
        assert not (third_party_folder / "third_party.zip").is_file()
    else:
        # no-op: pre-existing third_party directory is unchanged
        assert (third_party / "data.txt").read_text() == "payload"
        assert not (third_party_folder / "third_party.zip").is_file()
