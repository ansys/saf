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

from collections.abc import Callable
from pathlib import Path
import platform
import shutil

from packaging.utils import canonicalize_name
import pytest
import tomlkit

from ansys.saf.cli._config.const import DEFAULT_SOLUTION_NAME, DEFAULT_SOLUTION_NAMESPACE
from ansys.saf.cli._solutions.backend_detection import SolutionBackend, parse_solution_backend
from ansys.saf.cli._utilities.conversion import namespace_to_pkg_name
from tests.e2e.conftest import InstallSolution, ListSolutions, NewSolution, is_solution_registered
from tests.e2e.saf_process import SAFProcess
from tests.outcome_checks import verify_installation

InstallWithNetrcSet = Callable[[str | None, int], SAFProcess]


@pytest.fixture(params=[SolutionBackend.POETRY, SolutionBackend.UV], ids=["poetry", "uv"])
def installation_backend(request: pytest.FixtureRequest) -> SolutionBackend:
    return SolutionBackend(request.param)


@pytest.fixture
def new_solution(
    new_solution: NewSolution,
    installation_backend: SolutionBackend,
    tmp_path: Path,
) -> NewSolution:
    def _new_solution(
        args: list[str] | None = None,
        cwd: Path | None = None,
        input_str: str = "",
        expected_return_code: int = 0,
    ) -> SAFProcess:
        cwd = cwd or tmp_path
        process = new_solution(args, cwd, input_str, expected_return_code)
        solution_path = cwd / DEFAULT_SOLUTION_NAME
        assert parse_solution_backend(solution_path).backend is SolutionBackend.POETRY
        if installation_backend is SolutionBackend.UV:
            _prepare_uv_solution(solution_path)
        return process

    return _new_solution


def _prepare_uv_solution(solution_path: Path) -> None:
    # Reuse the scaffold's source and locked direct dependencies without changing the production template.
    pyproject_path = solution_path / "pyproject.toml"
    configuration = tomlkit.loads(pyproject_path.read_bytes()).unwrap()
    poetry = configuration["tool"]["poetry"]
    lock_path = solution_path / "poetry.lock"
    lock = tomlkit.loads(lock_path.read_bytes()).unwrap()

    def requirements(dependencies: dict) -> list[str]:
        result = []
        for name, dependency in dependencies.items():
            if name == "python":
                continue
            versions = {
                package["version"]
                for package in lock["package"]
                if canonicalize_name(package["name"]) == canonicalize_name(name)
            }
            assert len(versions) == 1, f"Expected one locked version for {name}, got {versions}"
            extras = dependency.get("extras", []) if isinstance(dependency, dict) else []
            extras_spec = f"[{','.join(extras)}]" if extras else ""
            result.append(f"{name}{extras_spec}=={versions.pop()}")
        return result

    configuration["project"] = {
        "name": poetry["name"],
        "version": poetry["version"],
        "requires-python": poetry["dependencies"]["python"],
        "dependencies": requirements(poetry["dependencies"]),
    }
    configuration["dependency-groups"] = {
        name: requirements(group["dependencies"]) for name, group in poetry["group"].items()
    }
    configuration["build-system"] = {
        "requires": ["setuptools>=67.0"],
        "build-backend": "setuptools.build_meta",
    }
    del configuration["tool"]["poetry"]
    del configuration["build-system-requirements"]
    # A configured default group must not override SAF's explicit group selection.
    configuration["tool"]["uv"] = {"default-groups": ["tests"]}
    pyproject_path.write_text(tomlkit.dumps(configuration), encoding="utf-8")
    lock_path.unlink()


@pytest.fixture(params=[True, False])
def install_with_netrc_set(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    new_solution: NewSolution,
    install_solution: InstallSolution,
) -> InstallWithNetrcSet:
    use_home_dir = request.param

    def _install_with_netrc_set(
        netrc_content: str | None,
        expected_return_code: int = 0,
    ):
        solution_path = tmp_path / DEFAULT_SOLUTION_NAME

        if use_home_dir:
            home_dir = tmp_path / "home"
            home_dir.mkdir()

            if platform.system() == "Linux":
                home_envar = "HOME"
                netrc_file_name = ".netrc"
            else:
                home_envar = "USERPROFILE"
                netrc_file_name = "_netrc"

            monkeypatch.setenv(home_envar, str(home_dir))
            netrc_path = home_dir / netrc_file_name
        else:
            netrc_path = tmp_path / "netrc_file"
            monkeypatch.setenv("NETRC", str(netrc_path))

        if netrc_content is not None:
            netrc_path.write_text(netrc_content)
        new_solution(input_str="\n\n\n\n", cwd=tmp_path)

        p = install_solution([DEFAULT_SOLUTION_NAME], expected_return_code=expected_return_code)
        if expected_return_code == 0:
            verify_installation(solution_path)

        return p

    return _install_with_netrc_set


PtyProcess = None  # type: ignore
if platform.system() == "Windows":
    pass  # type: ignore[import]


@pytest.mark.parametrize("solution_param_type", [None, "relative", "absolute", "solution_name"])
def test_saf_install(
    tmp_path: Path,
    database_path: Path,
    solution_param_type: str,
    new_solution: NewSolution,
    list_solutions: ListSolutions,
    install_solution: InstallSolution,
    installation_backend: SolutionBackend,
):
    """
    Test ``saf install`` with the default option values and all the possible solution argument types: an empty string,
    a relative path, an absolute path, and a solution name.
    """
    solution_path = tmp_path / DEFAULT_SOLUTION_NAME

    new_solution(input_str="\n\n\n\n", cwd=tmp_path)

    if solution_param_type != "solution_name":
        database_path.unlink()
        assert not is_solution_registered(list_solutions(), solution_path)

    if solution_param_type == "solution_name":
        p = install_solution([DEFAULT_SOLUTION_NAME])
    elif solution_param_type == "relative":
        p = install_solution([f"./{solution_path.name}"], tmp_path)
    elif solution_param_type == "absolute":
        p = install_solution([solution_path.absolute().as_posix()])
    elif not solution_param_type:
        p = install_solution([""], solution_path)
    else:
        raise ValueError(f"Invalid solution_param_type: {solution_param_type}")

    assert p.find_msg_in_output(f"Environment variables loaded from {(solution_path / '.env').resolve()}")
    assert p.find_msg_in_output(f"Dependency management system         : {installation_backend.value}")
    if installation_backend is SolutionBackend.POETRY:
        expected_package_install_msg = (
            "Installing the current project: "
            f"{namespace_to_pkg_name(DEFAULT_SOLUTION_NAMESPACE)}-"
            f"{DEFAULT_SOLUTION_NAME.replace('_', '-')} (0.0.0)"
        )
        assert p.find_msg_in_output(expected_package_install_msg)
        assert p.find_msg_in_output("Poetry-based solutions are deprecated")
    assert p.find_msg_in_output("Preload solution package")

    verify_installation(solution_path)

    assert is_solution_registered(list_solutions(), solution_path)


@pytest.mark.parametrize("dependency_groups", [None, "desktop", "style,build,ui", "all"])
def test_saf_install_with_dependencies(
    tmp_path: Path,
    new_solution: NewSolution,
    install_solution: InstallSolution,
    dependency_groups: str | None,
):
    """
    Test ``saf install`` with dependency groups.
    """
    solution_path = tmp_path / DEFAULT_SOLUTION_NAME
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)

    p = install_solution([DEFAULT_SOLUTION_NAME] + (["-d", dependency_groups] if dependency_groups else []))

    all_dependency_groups = ["build", "desktop", "doc", "style", "tests", "ui"]
    selected_dependency_groups = (
        all_dependency_groups
        if dependency_groups == "all"
        else dependency_groups.split(",")
        if dependency_groups
        else ["desktop", "ui", "doc", "build"]
    )
    skipped_dependency_groups = [
        dependency_group
        for dependency_group in all_dependency_groups
        if dependency_group not in selected_dependency_groups
    ]
    skip_preload = "ui" not in selected_dependency_groups
    verify_installation(
        solution_path,
        installed_groups=selected_dependency_groups,
        not_installed_groups=skipped_dependency_groups,
        check_poetry_cache=True,
        skip_preload=skip_preload,
    )
    if skip_preload:
        assert p.find_msg_in_output("Skipped: UI is not in the selected dependency groups.")


@pytest.mark.parametrize("clear_option", ["-f", "-F"])
def test_saf_install_with_clear_workspace(
    tmp_path: Path,
    new_solution: NewSolution,
    install_solution: InstallSolution,
    clear_option: str,
    installation_backend: SolutionBackend,
):
    """
    Test ``saf install`` with soft and hard workspace clear.
    """
    solution_path = tmp_path / DEFAULT_SOLUTION_NAME
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)

    # Create a solution virtual environment and install some dependencies
    install_solution([DEFAULT_SOLUTION_NAME, "-d", "doc"])

    # Check the environment and the selected backend's installation artifacts.
    verify_installation(
        solution_path,
        installed_groups=["doc"],
        not_installed_groups=["style"],
        check_poetry_cache=True,
        skip_preload=True,
    )

    venv = solution_path / ".venv"
    lock_file = solution_path / f"{installation_backend.value}.lock"
    backend_directories = (
        [solution_path / ".poetry" / ".venv", solution_path / ".poetry" / ".cache"]
        if installation_backend is SolutionBackend.POETRY
        else []
    )

    venv_ctime = venv.stat().st_ctime  # pyright: ignore[reportDeprecated]
    backend_directory_ctimes = [path.stat().st_ctime for path in backend_directories]  # pyright: ignore[reportDeprecated]
    # Windows can preserve creation times when a file is deleted and recreated.
    lock_mtime = lock_file.stat().st_mtime_ns

    # Call saf install again with the -f or -F flag
    install_solution([DEFAULT_SOLUTION_NAME, clear_option, "-d", "style"])

    # The previous environment structure is deleted and a new one is created
    verify_installation(
        solution_path,
        installed_groups=["style"],
        not_installed_groups=["doc"],
        check_poetry_cache=True,
        skip_preload=True,
    )

    assert venv_ctime != venv.stat().st_ctime  # pyright: ignore[reportDeprecated]
    for path, previous_ctime in zip(backend_directories, backend_directory_ctimes, strict=True):
        assert previous_ctime != path.stat().st_ctime  # pyright: ignore[reportDeprecated]
    if clear_option == "-F":
        assert lock_mtime != lock_file.stat().st_mtime_ns
    else:
        assert lock_mtime == lock_file.stat().st_mtime_ns


def test_saf_install_with_custom_env_file(tmp_path: Path, new_solution: NewSolution, install_solution: InstallSolution):
    """
    Test ``saf install`` with a custom environment file.
    """

    solution_path = tmp_path / DEFAULT_SOLUTION_NAME
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)

    env_file = solution_path / ".custom_env"
    shutil.move(solution_path / ".env", env_file)

    p = install_solution([DEFAULT_SOLUTION_NAME, "--env-file", str(env_file)])
    assert p.find_msg_in_output(f"Environment variables loaded from {env_file.resolve()}")

    verify_installation(solution_path)


def test_install_invalid_solution(tmp_path: Path, new_solution: NewSolution, install_solution: InstallSolution):
    """
    Test installing an existing solution that is invalid raises an error.
    """
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)
    shutil.rmtree(tmp_path / DEFAULT_SOLUTION_NAME)

    p = install_solution([DEFAULT_SOLUTION_NAME], cwd=tmp_path, expected_return_code=1)
    assert p.find_msg_in_output(f"NotADirectoryError: Solution not found at {str(tmp_path / DEFAULT_SOLUTION_NAME)}")


def test_install_multiple_solutions_same_name_invalid_solution(
    tmp_path: Path,
    new_solution: NewSolution,
    install_solution: InstallSolution,
):
    """
    Test installing an existing solution that has the same name as other that is invalid.
    """
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)
    (tmp_path / "another_solution").mkdir()
    new_solution(input_str="\n\n\n\n", cwd=(tmp_path / "another_solution"))
    shutil.rmtree(tmp_path / "another_solution")

    install_solution([DEFAULT_SOLUTION_NAME])
    verify_installation(tmp_path / DEFAULT_SOLUTION_NAME)


def test_install_multiple_solutions_same_name(
    tmp_path: Path,
    new_solution: NewSolution,
    install_solution: InstallSolution,
):
    """
    Test installing an existing solution that has the same name as other raises an error.
    """
    new_solution(input_str="\n\n\n\n", cwd=tmp_path)
    (tmp_path / "another_solution").mkdir()
    new_solution(input_str="\n\n\n\n", cwd=(tmp_path / "another_solution"))

    p = install_solution([DEFAULT_SOLUTION_NAME], expected_return_code=1)

    assert p.find_msg_in_output(f"ValueError: Multiple solutions found with the name {DEFAULT_SOLUTION_NAME}.")
    assert p.find_msg_in_output(str(tmp_path / DEFAULT_SOLUTION_NAME))
    assert p.find_msg_in_output(str(tmp_path / "another_solution" / DEFAULT_SOLUTION_NAME))
    assert p.find_msg_in_output("Hint: You can specify the correct one by using the full path")
