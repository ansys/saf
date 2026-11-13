# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
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

import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from threading import Thread
import tomllib
from zipfile import ZipFile

import pytest
import toml

from ansys.saf.desktop.installer.__main__ import package_solution
from ansys.saf.desktop.installer._package import manage_dependencies
from ansys.saf.desktop.installer._package.backend_detection import SolutionBackend
from ansys.saf.desktop.installer._package.config import InstallerConfig
from ansys.saf.desktop.installer._package.manage_dependencies import build_and_stage_solution_packages
from ansys.saf.desktop.installer._package.solution import SolutionInfo
from ansys.saf.desktop.installer.solution_desktop_deployment import installation

PRIVATE_PACKAGE = "saf-uv-e2e-private-package"
PRIVATE_PACKAGE_WHEEL = "saf_uv_e2e_private_package-0.1.0-py3-none-any.whl"
PRIVATE_INDEX_USERNAME = "e2e-user"
PRIVATE_INDEX_PASSWORD = "e2e-password"


def test_uv_offline_lock_uses_staged_transitive_wheels(tmp_path: Path) -> None:
    """Resolve and install transitives without an index or unsupported-platform packages."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("UV is required for the portable lock integration test.")
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    packages = []
    for name, dependency in (
        ("portable-parent", "portable-child==1.0"),
        ("portable-child", "unavailable-jsfetch ; sys_platform == 'emscripten'"),
    ):
        distribution = f"{name.replace('-', '_')}-1.0"
        with ZipFile(wheelhouse / f"{distribution}-py3-none-any.whl", "w") as wheel:
            wheel.writestr(
                f"{distribution}.dist-info/METADATA",
                f"Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\nRequires-Dist: {dependency}\n",
            )
            wheel.writestr(
                f"{distribution}.dist-info/WHEEL",
                "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
            )
            wheel.writestr(f"{distribution}.dist-info/RECORD", "")
        packages.append({"name": name, "version": "1.0", "source": {"registry": "https://pypi.org/simple"}})
    project = {
        "project": {
            "name": "portable-test",
            "version": "1.0",
            "requires-python": ">=3.11",
            "dependencies": ["portable-parent==1.0"],
        },
        "tool": {
            "uv": {
                "package": False,
                "no-index": True,
                "find-links": ["wheelhouse"],
                "environments": [
                    f"sys_platform == '{sys.platform}' and "
                    f"python_version == '{sys.version_info.major}.{sys.version_info.minor}'",
                ],
            }
        },
    }
    manage_dependencies._rewrite_uv_local_sources(  # pyright: ignore[reportPrivateUsage]
        project,
        tmp_path,
        packages,
        wheelhouse,
        include_public_registry_packages=True,
    )
    (tmp_path / "pyproject.toml").write_text(toml.dumps(project), encoding="utf-8")
    for action in ("lock", "sync"):
        command = [
            uv,
            "--cache-dir",
            str(tmp_path / "empty-cache"),
            action,
            "--offline",
            "--no-index",
            "--python",
            sys.executable,
        ]
        if action == "sync":
            command.extend(["--locked", "--find-links", str(wheelhouse)])
        subprocess.run(command, cwd=tmp_path, check=True, capture_output=True, text=True)
    lock = tomllib.loads((tmp_path / "uv.lock").read_text(encoding="utf-8"))
    assert {package["name"] for package in lock["package"]} == {
        "portable-test",
        "portable-parent",
        "portable-child",
    }
    assert all(package["source"] in ({"virtual": "."}, {"registry": "wheelhouse"}) for package in lock["package"])


def _create_private_package_wheel(wheel_path: Path) -> None:
    distribution = "saf_uv_e2e_private_package-0.1.0.dist-info"
    files = {
        f"{PRIVATE_PACKAGE.replace('-', '_')}/__init__.py": b"value = True\n",
        f"{distribution}/METADATA": (f"Metadata-Version: 2.1\nName: {PRIVATE_PACKAGE}\nVersion: 0.1.0\n\n").encode(),
        f"{distribution}/WHEEL": (
            b"Wheel-Version: 1.0\nGenerator: saf-e2e\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
        ),
    }
    record_rows = []
    for path, content in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
        record_rows.append(f"{path},sha256={digest},{len(content)}")
    record_rows.append(f"{distribution}/RECORD,,")
    files[f"{distribution}/RECORD"] = ("\n".join(record_rows) + "\n").encode()
    with ZipFile(wheel_path, "w") as wheel:
        for path, content in files.items():
            wheel.writestr(path, content)


def _create_private_index(wheel_path: Path) -> type[BaseHTTPRequestHandler]:
    expected_auth = (
        "Basic "
        + base64.b64encode(
            f"{PRIVATE_INDEX_USERNAME}:{PRIVATE_INDEX_PASSWORD}".encode(),
        ).decode()
    )

    class PrivateIndexHandler(BaseHTTPRequestHandler):
        def do_HEAD(self) -> None:
            if self.headers.get("Authorization") != expected_auth:
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="UV e2e test index"')
                self.end_headers()
                return

            if self.path == f"/packages/{PRIVATE_PACKAGE_WHEEL}":
                self.send_response(200)
                self.send_header("Content-Length", str(wheel_path.stat().st_size))
                self.end_headers()
                return

            self.send_error(404)

        def do_GET(self) -> None:
            if self.headers.get("Authorization") != expected_auth:
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="UV e2e test index"')
                self.end_headers()
                return

            if self.path == f"/simple/{PRIVATE_PACKAGE}/":
                body = f'<a href="/packages/{PRIVATE_PACKAGE_WHEEL}">{PRIVATE_PACKAGE_WHEEL}</a>'.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if self.path == f"/packages/{PRIVATE_PACKAGE_WHEEL}":
                body = wheel_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            self.send_error(404)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    return PrivateIndexHandler


def _create_uv_solution(solution_root: Path) -> tuple[Path, str, str]:
    fixture_dir = Path(__file__).parent.parent / "mocks" / "my-solution-dash" / "build_assets"
    if platform.system() == "Windows":
        dependency_wheel_name = "custom_package_for_test_2-0.0.1-py3-none-win_amd64.whl"
    elif platform.system() == "Linux":
        dependency_wheel_name = (
            "custom_package_for_test_2-0.0.1-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl"
        )
    else:
        pytest.skip("The local dependency wheel fixture is available only on Windows and Linux.")

    assets = solution_root / "build_assets"
    assets.mkdir(parents=True)
    shutil.copy2(fixture_dir / dependency_wheel_name, assets / dependency_wheel_name)
    dependency_wheel = (assets / dependency_wheel_name).resolve().as_uri()
    git_dependency = solution_root / "git_dependency"
    git_package = git_dependency / "src" / "git_e2e_dependency"
    git_package.mkdir(parents=True)
    (git_dependency / "pyproject.toml").write_text(
        "[build-system]\n"
        'requires = ["setuptools>=61"]\n'
        'build-backend = "setuptools.build_meta"\n\n'
        "[project]\n"
        'name = "git-e2e-dependency"\n'
        'version = "0.1.0"\n\n'
        "[tool.setuptools.packages.find]\n"
        'where = ["src"]\n',
        encoding="utf-8",
    )
    (git_package / "__init__.py").write_text("value = True\n", encoding="utf-8")
    for command in (
        ["git", "init", "--quiet"],
        ["git", "config", "user.email", "uv-e2e@example.com"],
        ["git", "config", "user.name", "UV E2E Test"],
        ["git", "add", "."],
        ["git", "commit", "--quiet", "-m", "Create test dependency"],
    ):
        subprocess.run(command, cwd=git_dependency, check=True, capture_output=True, text=True)
    git_dependency_url = git_dependency.resolve().as_uri()
    (solution_root / "pyproject.toml").write_text(
        "[build-system]\n"
        'requires = ["setuptools>=61"]\n'
        'build-backend = "setuptools.build_meta"\n\n'
        "[project]\n"
        'name = "ansys-solutions-uv-migration-test"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.11"\n\n'
        "[tool.setuptools.packages.find]\n"
        'where = ["src"]\n'
        'include = ["ansys*"]\n\n'
        "[tool.uv]\n"
        "package = true\n\n",
        encoding="utf-8",
    )
    return solution_root / "pyproject.toml", dependency_wheel, git_dependency_url


def _add_uv_dependencies_to_project(
    pyproject_path: Path,
    dependency_wheel: str,
    git_dependency_url: str,
    private_index_url: str,
) -> None:
    pyproject_path.write_text(
        pyproject_path.read_text(encoding="utf-8") + "[[tool.uv.index]]\n"
        'name = "internal"\n'
        f'url = "{private_index_url}"\n\n'
        "[dependency-groups]\n"
        "desktop = [\n"
        f'    "custom-package-for-test-2 @ {dependency_wheel}",\n'
        f'    "git-e2e-dependency @ git+{git_dependency_url}",\n'
        f'    "{PRIVATE_PACKAGE}==0.1.0",\n'
        '    "idna==3.10",\n'
        "]\n",
        encoding="utf-8",
    )


def _create_solution_source(solution_root: Path) -> None:
    solution_package = solution_root / "src" / "ansys" / "solutions" / "uv_migration"
    (solution_package / "solution").mkdir(parents=True)
    for package_dir in (
        solution_root / "src" / "ansys",
        solution_root / "src" / "ansys" / "solutions",
        solution_package,
        solution_package / "solution",
    ):
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (solution_package / "main.py").write_text(
        "import custom_package_for_test_2\n\n"
        "import git_e2e_dependency\n\n"
        f"import {PRIVATE_PACKAGE.replace('-', '_')}\n\n"
        "import idna\n\n"
        "def dependency_is_importable() -> bool:\n"
        f"    return custom_package_for_test_2 is not None and git_e2e_dependency.value and "
        f"{PRIVATE_PACKAGE.replace('-', '_')}.value and idna.__version__ == '3.10'\n",
        encoding="utf-8",
    )
    (solution_package / "solution" / "definition.py").write_text("", encoding="utf-8")


def test_uv_solution_builds_and_installs_online_and_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Build the installer and install a UV solution through both offline runtime paths."""
    uv_executable = shutil.which("uv")
    assert uv_executable is not None, "UV must be installed to run this end-to-end test."
    assert shutil.which("git") is not None, "Git must be installed to run this end-to-end test."

    monkeypatch.setenv("UV_NO_BUILD_ISOLATION", "1")
    monkeypatch.setenv("UV_PYTHON", sys.executable)
    monkeypatch.setenv("UV_INDEX_INTERNAL_USERNAME", PRIVATE_INDEX_USERNAME)
    monkeypatch.setenv("UV_INDEX_INTERNAL_PASSWORD", PRIVATE_INDEX_PASSWORD)
    monkeypatch.setattr(
        "ansys.saf.desktop.installer._package.solution.get_solution_display_name",
        lambda _module: "UV Migration Test",
    )
    monkeypatch.setattr(
        "ansys.saf.desktop.installer._package.solution_package.download_embeddable_python",
        lambda _folder, _config: (
            Path(sys.executable),
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        ),
    )

    def use_host_python(definitions_dir: Path, _python: Path, _backend: SolutionBackend) -> tuple[Path, Path]:
        virtual_environment = definitions_dir / ".venv"
        virtual_environment.mkdir()
        return virtual_environment, Path(sys.executable)

    monkeypatch.setattr(
        "ansys.saf.desktop.installer._package.solution_package.create_venv_in_definitions_folder",
        use_host_python,
    )

    solution_root = tmp_path / "uv-migration-solution"
    solution_root.mkdir()
    pyproject_path, dependency_wheel, git_dependency_url = _create_uv_solution(solution_root)
    _create_solution_source(solution_root)

    private_wheel = solution_root / PRIVATE_PACKAGE_WHEEL
    _create_private_package_wheel(private_wheel)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _create_private_index(private_wheel))
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    private_index_url = f"http://127.0.0.1:{server.server_port}/simple"
    online_definitions_dir = tmp_path / "online-payload" / "definitions" / "uv_migration"
    try:
        _add_uv_dependencies_to_project(
            pyproject_path,
            dependency_wheel,
            git_dependency_url,
            private_index_url,
        )
        subprocess.run(
            [uv_executable, "lock", "--python", sys.executable],
            cwd=solution_root,
            check=True,
            capture_output=True,
            text=True,
        )

        package_solution(
            SolutionInfo(solution_root),
            InstallerConfig(
                exclude_python=True,
                offline_package=True,
                pyproject_location=pyproject_path,
            ),
        )
        online_definitions_dir.mkdir(parents=True)
        build_and_stage_solution_packages(
            online_definitions_dir,
            Path(sys.executable),
            solution_root,
            "uv_migration",
            "UV Migration Test",
            InstallerConfig(pyproject_location=pyproject_path),
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            backend=SolutionBackend.UV,
        )
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join()

    definitions_dir = solution_root / "dist" / "solution" / "definitions" / "uv_migration"
    assert (definitions_dir / "uv.lock").is_file()
    assert (definitions_dir / "uv-requirements.txt").is_file()
    assert list((definitions_dir / "wheelhouse").glob("custom_package_for_test_2-*.whl"))
    assert list((definitions_dir / "wheelhouse").glob("git_e2e_dependency-*.whl"))
    assert list((definitions_dir / "wheelhouse").glob("saf_uv_e2e_private_package-*.whl"))
    assert list((definitions_dir / "wheelhouse").glob("idna-3.10-*.whl"))
    assert not list((online_definitions_dir / "wheelhouse").glob("idna-3.10-*.whl"))
    installer_name = "uv-migration-test-installer"
    if platform.system() == "Windows":
        installer_name += ".exe"
    installer_path = solution_root / "dist" / installer_name
    assert installer_path.is_file()
    subprocess.run([installer_path, "--help"], check=True, capture_output=True, text=True)

    metadata_file = solution_root / "dist" / "solution" / "solution-metadata.json"
    package_metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    for payload_dir, offline_package in ((definitions_dir, True), (online_definitions_dir, False)):
        for use_pip in (False, True):
            installation_dir = tmp_path / f"{'offline' if offline_package else 'online'}-{'pip' if use_pip else 'uv'}"
            installed_definitions = installation_dir / "definitions" / "uv_migration"
            shutil.copytree(payload_dir, installed_definitions)
            package_metadata["offline-package"] = "True" if offline_package else "False"

            with monkeypatch.context() as environment:
                environment.setenv("PIP_CACHE_DIR", str(installation_dir / "pip-cache"))
                environment.setenv("UV_CACHE_DIR", str(installation_dir / "uv-cache"))
                if offline_package:
                    environment.setenv("UV_OFFLINE", "1")
                else:
                    environment.delenv("UV_OFFLINE", raising=False)
                installation(installation_dir, package_metadata, Path(sys.executable), use_pip=use_pip)

            python_executable = (
                installed_definitions / ".venv" / "Scripts" / "python.exe"
                if platform.system() == "Windows"
                else installed_definitions / ".venv" / "bin" / "python"
            )
            subprocess.run(
                [
                    str(python_executable),
                    "-c",
                    "from ansys.solutions.uv_migration.main import dependency_is_importable; "
                    "assert dependency_is_importable()",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
