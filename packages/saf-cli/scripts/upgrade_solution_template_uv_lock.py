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

import argparse
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile

from dotenv import load_dotenv
import tomlkit

from ansys.saf.cli._config.const import UI_FRAMEWORKS

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Upgrade uv.lock files for solution templates",
    )
    parser.add_argument(
        "-p",
        "--packages",
        type=str,
        default="",
        help=(
            "Comma-separated list of packages to explicitly update (e.g., 'package1,package2'). "
            "Use it for packages that weren't modified in the pyproject.toml."
        ),
    )
    args = parser.parse_args()
    packages_to_update = [pkg.strip() for pkg in str(args.packages).split(",") if pkg.strip()]

    saf_cli_src_dir = Path(__file__).parent.parent / "src" / "ansys" / "saf" / "cli"
    assert saf_cli_src_dir.is_dir()

    pyproject_file = (
        saf_cli_src_dir
        / "_solutions"
        / "templates"
        / "solution"
        / "{{cookiecutter.__solution_name}}"
        / "pyproject.toml"
    )
    if not pyproject_file.is_file():
        raise FileNotFoundError(f"Solution template manifest not found: {pyproject_file}")

    if platform.system() == "Windows":
        saf_exec = Path.cwd() / ".venv" / "Scripts" / "saf.exe"
        if not saf_exec.is_file():
            saf_exec = Path.cwd() / ".venv" / "Scripts" / "saf.cmd"
    else:
        saf_exec = Path.cwd() / ".venv" / "bin" / "saf"
    if not saf_exec.is_file():
        raise FileNotFoundError(f"SAF CLI executable not found: {saf_exec}")

    uv_exec = shutil.which("uv")
    if uv_exec is None:
        raise RuntimeError("uv must be installed and available on PATH")

    uv_lock_dest_dirs: dict[str, str] = {
        "dash": "dash",
        "none": "no_ui",
    }

    for ui_framework in UI_FRAMEWORKS:
        print(f"Processing UI framework: {ui_framework}")

        uv_lock_dest = (
            saf_cli_src_dir
            / "_solutions"
            / "templates"
            / "solution"
            / "{{cookiecutter.__solution_name}}"
            / "lock_files"
            / uv_lock_dest_dirs[ui_framework]
            / "uv.lock"
        )
        if not uv_lock_dest.is_file():
            raise FileNotFoundError(f"Template lockfile not found: {uv_lock_dest}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            solution_name = f"solution-{ui_framework}"
            print(f"Creating new solution {solution_name} at {tmp_dir}...")
            subprocess.run(
                [
                    str(saf_exec),
                    "new",
                    "--solution-name",
                    solution_name,
                    "--solution-display-name",
                    "temp",
                    "--ui-framework",
                    ui_framework,
                    "--namespace",
                    "my_temp",
                ],
                cwd=tmp_dir,
                check=True,
            )
            solution_root_dir = Path(tmp_dir) / solution_name
            if not solution_root_dir.is_dir():
                raise FileNotFoundError(f"Generated solution not found: {solution_root_dir}")

            # Load credentials used by private package indexes before resolving dependencies.
            load_dotenv(solution_root_dir / ".env")

            uv_lock_command = [uv_exec, "lock"]
            uv_lock_command.extend(arg for package in packages_to_update for arg in ("--upgrade-package", package))
            print("Upgrading uv.lock...")
            subprocess.run(uv_lock_command, cwd=solution_root_dir, check=True)
            subprocess.run([uv_exec, "lock", "--check"], cwd=solution_root_dir, check=True)

            print(f"Copying uv.lock to destination {uv_lock_dest}...")
            solution_uv_lock = solution_root_dir / "uv.lock"
            if not solution_uv_lock.is_file():
                raise FileNotFoundError(f"Generated lockfile not found: {solution_uv_lock}")
            lock = tomlkit.parse(solution_uv_lock.read_text(encoding="utf-8"))
            solution_packages = [package for package in lock["package"] if package["source"] == {"editable": "."}]
            if len(solution_packages) != 1:
                raise ValueError("Expected exactly one editable solution package in the generated lockfile")
            solution_packages[0]["name"] = "{{ cookiecutter.__pkg_name }}"
            solution_packages[0]["version"] = "{{ cookiecutter.__version }}"
            uv_lock_dest.write_text(tomlkit.dumps(lock), encoding="utf-8", newline="\n")
