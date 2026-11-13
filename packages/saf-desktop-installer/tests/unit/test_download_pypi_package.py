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
import subprocess
import sys
from zipfile import ZipFile

import pytest
import pytest_mock

from ansys.saf.desktop.installer._common.utils import modify_solution_wheel_metadata
from ansys.saf.desktop.installer._package import manage_dependencies
from ansys.saf.desktop.installer._package.manage_dependencies import download_pypi_package_with_pip


def _create_wheel(wheel_path: Path, package_name: str, version: str) -> None:
    dist_info = f"{package_name.replace('-', '_')}-{version}.dist-info"
    with ZipFile(wheel_path, "w") as wheel:
        wheel.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.1\nName: {package_name}\nVersion: {version}\n",
        )
        wheel.writestr(
            f"{dist_info}/WHEEL",
            "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        wheel.writestr(f"{dist_info}/RECORD", "")


def test_download_pypi_package_with_pip_matches_exact_version(tmp_path: Path):
    module_name = "ansys-saf-glow-engine"
    version = "1.30.0"
    mock_index_package_path = tmp_path / "simple" / module_name
    mock_index_package_path.mkdir(parents=True)
    module_wheel = mock_index_package_path / "ansys_saf_glow_engine-1.30.0-py3-none-any.whl"
    sp_module_wheel = mock_index_package_path / "ansys_saf_glow_engine-1.30.0+sp01-py3-none-any.whl"
    _create_wheel(module_wheel, module_name, version)
    _create_wheel(sp_module_wheel, module_name, "1.30.0+sp01")
    (mock_index_package_path / "index.html").write_text(
        f'<a href="{module_wheel.name}">{module_wheel.name}</a>\n'
        f'<a href="{sp_module_wheel.name}">{sp_module_wheel.name}</a>\n',
    )

    download_path = tmp_path / "download"
    download_path.mkdir()
    module_path = download_path / module_wheel.name
    sp_module_path = download_path / sp_module_wheel.name

    download_pypi_package_with_pip(
        module_name,
        version,
        (tmp_path / "simple").as_uri(),
        download_path,
        Path(sys.executable),
    )

    assert module_path.is_file()
    assert not sp_module_path.is_file()


def test_download_pypi_package_with_pip_does_not_log_url_containing_pat(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ansys.saf.desktop.installer._package.manage_dependencies as manage_dependencies

    monkeypatch.setattr(manage_dependencies.subprocess, "check_output", lambda *args, **kwargs: "")
    caplog.set_level("INFO", logger=manage_dependencies.logger.name)
    secret_url = "https://ghp_secret@example.com/simple?token=secret"
    sensitive_destination = tmp_path / "private-download-directory"

    download_pypi_package_with_pip(
        "example-package",
        "1.2.3",
        secret_url,
        sensitive_destination,
        Path(sys.executable),
    )

    assert "Downloading example-package===1.2.3 to " in caplog.text
    assert secret_url not in caplog.text
    assert "ghp_secret" not in caplog.text
    assert "token=secret" not in caplog.text
    assert f"to {sensitive_destination}." in caplog.text


def test_download_pypi_package_with_pip_does_not_log_url_without_pat(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ansys.saf.desktop.installer._package.manage_dependencies as manage_dependencies

    monkeypatch.setattr(manage_dependencies.subprocess, "check_output", lambda *args, **kwargs: "")
    caplog.set_level("INFO", logger=manage_dependencies.logger.name)
    public_url = "https://example.com/simple"
    destination = tmp_path / "download"

    download_pypi_package_with_pip(
        "example-package",
        "1.2.3",
        public_url,
        destination,
        Path(sys.executable),
    )

    assert f"Downloading example-package===1.2.3 to {destination}." in caplog.text
    assert public_url not in caplog.text


@pytest.mark.parametrize(
    ("token", "expected_url"),
    [
        (None, "https://github.com/org/repo.git"),
        ("test/token", "https://test%2Ftoken@github.com/org/repo.git"),
    ],
)
@pytest.mark.parametrize("resolved_reference", [None, "abcdef123456"])
def test_download_poetry_git_source_uses_direct_requirement(
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
    caplog: pytest.LogCaptureFixture,
    token: str | None,
    expected_url: str,
    resolved_reference: str | None,
) -> None:
    source = {"type": "git", "url": "https://github.com/org/repo.git", "reference": "main"}
    if resolved_reference is not None:
        source["resolved_reference"] = resolved_reference
    package = {"name": "example-package", "version": "1.2.3", "source": source}
    python = tmp_path / "python"
    download = mocker.patch.object(manage_dependencies.subprocess, "check_output")
    caplog.set_level("INFO", logger=manage_dependencies.logger.name)

    manage_dependencies._download_poetry_git_source(  # pyright: ignore[reportPrivateUsage]
        package,
        tmp_path,
        python,
        token,
    )

    revision = resolved_reference or "main"
    download.assert_called_once_with(
        [
            python,
            "-m",
            "pip",
            "wheel",
            "--disable-pip-version-check",
            "--no-deps",
            "--wheel-dir",
            tmp_path,
            f"example-package @ git+{expected_url}@{revision}",
        ],
        text=True,
    )
    assert "https://" not in caplog.text
    assert "test/token" not in caplog.text
    assert "test%2Ftoken" not in caplog.text


def test_download_poetry_git_source_propagates_download_failure(
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
) -> None:
    package = {
        "name": "example-package",
        "version": "1.2.3",
        "source": {"type": "git", "url": "https://github.com/org/repo.git", "reference": "main"},
    }
    error = subprocess.CalledProcessError(1, ["pip", "download"])
    mocker.patch.object(manage_dependencies.subprocess, "check_output", side_effect=error)

    with pytest.raises(subprocess.CalledProcessError) as failure:
        manage_dependencies._download_poetry_git_source(  # pyright: ignore[reportPrivateUsage]
            package,
            tmp_path,
            tmp_path / "python",
        )

    assert failure.value is error


@pytest.mark.parametrize("url", ["https://github.com/org/repo.git", "https://github.com/org/repo"])
def test_stage_poetry_locked_dependencies_recognizes_git_source(
    tmp_path: Path,
    mocker: pytest_mock.MockerFixture,
    url: str,
) -> None:
    lock = tmp_path / "poetry.lock"
    lock.write_text(
        '[[package]]\nname = "example-package"\nversion = "1.2.3"\n'
        f'[package.source]\ntype = "git"\nurl = "{url}"\nreference = "main"\n',
        encoding="utf-8",
    )
    download = mocker.patch.object(manage_dependencies, "_download_poetry_git_source")
    python = tmp_path / "python"

    manage_dependencies._stage_poetry_locked_dependencies(  # pyright: ignore[reportPrivateUsage]
        lock,
        tmp_path,
        python,
    )

    download.assert_called_once_with(
        {
            "name": "example-package",
            "version": "1.2.3",
            "source": {"type": "git", "url": url, "reference": "main"},
        },
        tmp_path,
        python,
        None,
    )


def test_download_poetry_git_source_downloads_locked_commit_without_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise pip and Git locally without network access or build dependency downloads."""
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["setuptools"]\nbuild-backend = "setuptools.build_meta"\n',
        encoding="utf-8",
    )
    (repository / "setup.py").write_text(
        "from setuptools import setup\n"
        'setup(name="example-git-dependency", version="1.2.3", py_modules=["example_git_dependency"])\n',
        encoding="utf-8",
    )
    module = repository / "example_git_dependency.py"
    module.write_text('value = "locked"\n', encoding="utf-8")
    for command in (
        ["git", "init", "--quiet"],
        ["git", "add", "."],
        [
            "git",
            "-c",
            "user.name=Installer Test",
            "-c",
            "user.email=installer-test@example.com",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "Create locked dependency",
        ],
    ):
        subprocess.run(command, cwd=repository, check=True, capture_output=True, text=True)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()
    module.write_text('value = "newer"\n', encoding="utf-8")
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Installer Test",
            "-c",
            "user.email=installer-test@example.com",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-am",
            "Change dependency",
        ],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    monkeypatch.setenv("PIP_NO_BUILD_ISOLATION", "0")
    monkeypatch.setenv("PIP_NO_INDEX", "1")
    monkeypatch.setenv("PIP_NO_INPUT", "1")
    destination = tmp_path / "download"
    destination.mkdir()
    package = {
        "name": "example-git-dependency",
        "version": "1.2.3",
        "source": {
            "type": "git",
            "url": repository.as_uri(),
            "reference": "HEAD",
            "resolved_reference": revision,
        },
    }

    manage_dependencies._download_poetry_git_source(  # pyright: ignore[reportPrivateUsage]
        package,
        destination,
        Path(sys.executable),
    )

    archives = list(destination.glob("*.whl"))
    assert len(archives) == 1
    with ZipFile(archives[0]) as archive:
        module_path = next(name for name in archive.namelist() if name == "example_git_dependency.py")
        assert archive.read(module_path).decode("utf-8").splitlines() == ['value = "locked"']


@pytest.mark.parametrize("staged", [False, True])
def test_solution_wheel_references_staged_git_dependency(tmp_path: Path, staged: bool) -> None:
    wheel = tmp_path / "example_solution-0.1.0-py3-none-any.whl"
    dependency = tmp_path / "example_git_dependency-1.2.3-py3-none-any.whl"
    requirement = (
        'example-git-dependency[extra] @ git+https://github.com/org/repo.git@abcdef ; python_version >= "3.11"'
    )
    with ZipFile(wheel, "w") as archive:
        archive.writestr(
            "example_solution-0.1.0.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: example-solution\nVersion: 0.1.0\nRequires-Dist: {requirement}\n",
        )
    if staged:
        _create_wheel(dependency, "example-git-dependency", "1.2.3")

    modify_solution_wheel_metadata(tmp_path, "example-solution", "0.1.0")

    with ZipFile(wheel) as archive:
        metadata = archive.read("example_solution-0.1.0.dist-info/METADATA").decode("utf-8")
    if staged:
        assert f'example-git-dependency[extra] @ {dependency.as_uri()} ; python_version >= "3.11"' in metadata
        assert "git+https://" not in metadata
    else:
        assert requirement in metadata
