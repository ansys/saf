# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
"""Real dependency-backend checks without SDK servers or browser services."""

from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile

from click.testing import CliRunner
from packaging.specifiers import SpecifierSet
import pytest
import tomlkit

from ansys.saf.cli._cli.main import saf
from ansys.saf.cli._solutions import environment
from ansys.saf.cli._utilities.conversion import namespace_to_path
from ansys.saf.cli._utilities.solution_modules import get_exec_from_solution_venv
from tests.conftest import prepare_poetry_solution


@pytest.fixture
def uv_executable() -> str:
    executable = shutil.which("uv")
    if executable is None:
        pytest.fail("UV must be installed to run dependency-backend integration tests.")
    return executable


def _new_solution(runner: CliRunner, ui: str, namespace: str) -> Path:
    result = runner.invoke(
        saf,
        [
            "new", "--solution-name", "backend_solution", "--solution-display-name", "Backend Solution",
            "--ui-framework", ui, "--namespace", namespace,
        ],
    )
    assert result.exit_code == 0, result.output
    return Path.cwd() / "backend_solution"


@pytest.mark.usefixtures("mock_appdata", "tmp_path_as_working_dir")
@pytest.mark.parametrize("ui", ["dash", "none"])
@pytest.mark.parametrize("namespace", ["saf.solutions", "mycompany.apps"])
def test_generated_uv_lockfile_is_current(ui: str, namespace: str, uv_executable: str):
    root = _new_solution(CliRunner(), ui, namespace)
    lock = root / "uv.lock"
    original = lock.read_bytes()

    subprocess.run(
        [uv_executable, "lock", "--check", "--offline", "--no-python-downloads", "--project", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert lock.read_bytes() == original
    assert not (root / "poetry.lock").exists()


@pytest.mark.usefixtures("mock_appdata", "tmp_path_as_working_dir", "install_custom_template_plugin")
@pytest.mark.parametrize(
    ("backend", "version", "ui", "namespace"),
    [
        pytest.param("uv", None, "dash", "saf.solutions", id="uv-dash"),
        pytest.param("uv", None, "none", "mycompany.apps", id="uv-no-ui-custom-namespace"),
        pytest.param("poetry", "1.7.1", "none", "saf.solutions", id="poetry-1.7"),
        pytest.param("poetry", "2.1.0", "dash", "mycompany.apps", id="poetry-2.1"),
        pytest.param("poetry-pep621", None, "none", "saf.solutions", id="poetry-pep621-default"),
        pytest.param("poetry-pep621", "2.1.0", "dash", "mycompany.apps", id="poetry-pep621-pinned"),
    ],
)
def test_real_backend_install_and_add_step(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    uv_executable: str,
    install_custom_template_plugin: Path,
    backend: str,
    version: str | None,
    ui: str,
    namespace: str,
):
    """Keep backend execution real while excluding the full SDK dependency tree."""
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
    monkeypatch.setattr(environment, "_install_dotnet_linux_dependencies", lambda: None)
    template_metadata = install_custom_template_plugin / "templates.toml"
    template_metadata.write_text(
        template_metadata.read_text()
        + '\n[templates.group-dependency-step]\nlocation = "steps/second_step"\n'
        'type = "step"\ndescription = "Group dependency regression"\n'
        '[templates.group-dependency-step.dependencies.regression]\n'
        'colorama = {version = "^0.4.6", allow-prereleases = true}\n',
    )
    runner = CliRunner()
    root = _new_solution(runner, ui, namespace)
    module_dir = root / "src" / namespace_to_path(namespace) / "backend_solution"
    (module_dir / "main.py").write_text('"""Minimal entry point for backend installation checks."""\n')
    pyproject = root / "pyproject.toml"
    configuration = tomlkit.loads(pyproject.read_bytes()).unwrap()
    configuration["project"]["dependencies"] = []
    configuration["dependency-groups"] = {"ui": []} if ui == "dash" else {}
    pyproject.write_text(tomlkit.dumps(configuration))
    (root / "uv.lock").unlink()
    if backend == "poetry":
        assert version is not None
        prepare_poetry_solution(root, version)
    elif backend == "poetry-pep621":
        configuration["tool"].pop("uv")
        configuration["tool"].pop("setuptools")
        configuration["tool"]["poetry"] = {
            "packages": [{"include": namespace.split(".")[0], "from": "src"}],
        }
        configuration.pop("dependency-groups")
        configuration["build-system"] = {
            "requires": ["poetry-core>=2"],
            "build-backend": "poetry.core.masonry.api",
        }
        if version is not None:
            configuration["build-system-requirements"] = {"build-system-version": version}
        pyproject.write_text(tomlkit.dumps(configuration))

    result = runner.invoke(saf, ["install", str(root)])
    assert result.exit_code == 0, result.output
    python = get_exec_from_solution_venv(root, "python")
    if backend != "uv":
        poetry = get_exec_from_solution_venv(root, "poetry")
        installed_version = subprocess.check_output([str(poetry), "--version"], text=True)
        assert f"(version {version or '2.5.1'})" in installed_version

    for step, template in (
        ("calculator_regression", "calculator-step"),
        ("dependency_regression", "several-deps-step"),
        ("group_regression", "group-dependency-step"),
    ):
        result = runner.invoke(
            saf,
            ["add-step", str(root), "--step-name", step, "--ui-framework", ui, "--template", template],
        )
        assert result.exit_code == 0, result.output
        assert (module_dir / "solution" / f"{step}_step.py").is_file()
        if ui == "dash":
            assert (module_dir / "ui" / "pages" / f"{step}_page.py").is_file()

    for name, constraint in (("humanize", ">=4.15.0,<5"), ("msgpack", ">=1.0,<2"), ("colorama", ">=0.4.6,<0.5")):
        installed = subprocess.check_output(
            [str(python), "-c", f"from importlib.metadata import version; print(version({name!r}))"],
            text=True,
        ).strip()
        assert SpecifierSet(constraint).contains(installed)
    lockfile = root / ("uv.lock" if backend == "uv" else "poetry.lock")
    assert lockfile.is_file()
    assert not (root / ("poetry.lock" if backend == "uv" else "uv.lock")).exists()

    if backend == "uv":
        result = runner.invoke(saf, ["execute", str(root), "uv lock --check --offline"])
        assert result.exit_code == 0, result.output
        output = tmp_path / "wheelhouse"
        subprocess.run(
            [uv_executable, "build", "--wheel", "--project", str(root), "--out-dir", str(output)],
            check=True,
            capture_output=True,
            text=True,
        )
        wheels = list(output.glob("*.whl"))
        assert len(wheels) == 1
        with ZipFile(wheels[0]) as wheel:
            module_path = f"{namespace_to_path(namespace)}/backend_solution"
            assert f"{module_path}/main.py" in wheel.namelist()
            assert f"{module_path}/solution/dependency_regression_step.py" in wheel.namelist()
        consumer = tmp_path / "wheel-consumer"
        subprocess.run(
            [uv_executable, "venv", "--python", sys.executable, "--no-python-downloads", str(consumer / ".venv")],
            check=True,
            capture_output=True,
            text=True,
        )
        wheel_python = get_exec_from_solution_venv(consumer, "python")
        subprocess.run(
            [uv_executable, "pip", "install", "--python", str(wheel_python), "--no-deps", str(wheels[0])],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [str(wheel_python), "-c", f"import {namespace}.backend_solution.main"],
            cwd=consumer,
            check=True,
            capture_output=True,
            text=True,
        )
