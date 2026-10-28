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

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "ansys-saf-cli",
#     "poetry==2.5.1",
#     "python-dotenv>=1.0.0,<2",
# ]
#
# [tool.uv.sources]
# ansys-saf-cli = { path = ".." }
# ///

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from dotenv import load_dotenv

from ansys.saf.cli._config.const import UI_FRAMEWORKS

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Upgrade poetry.lock files for solution templates",
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
    assert pyproject_file.is_file()
    saf_command = [
        sys.executable,
        "-c",
        "from ansys.saf.cli._cli.main import entry_point; entry_point()",
    ]

    starting_working_directory = Path.cwd()

    poetry_lock_dest_dirs: dict[str, str] = {
        "dash": "dash",
        "awc-dash": "awc",
        "none": "no_ui",
    }

    for ui_framework in UI_FRAMEWORKS:
        print(f"Processing UI framework: {ui_framework}")

        poetry_lock_dest = (
            saf_cli_src_dir
            / "_solutions"
            / "templates"
            / "solution"
            / "{{cookiecutter.__solution_name}}"
            / "lock_files"
            / poetry_lock_dest_dirs[ui_framework]
            / "poetry.lock"
        )
        assert poetry_lock_dest.is_file()

        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                os.chdir(tmp_dir)

                solution_name = f"solution-{ui_framework}"
                print(f"Creating new solution {solution_name} at {tmp_dir}...")
                subprocess.check_output(
                    [
                        *saf_command,
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
                )
                solution_root_dir = Path(tmp_dir) / solution_name
                assert solution_root_dir.is_dir()
                os.chdir(solution_root_dir)

                # load required poetry credentials for auth
                print(f"Loading .env file from {solution_root_dir / '.env'}...")
                load_dotenv(solution_root_dir / ".env")

                print("Upgrading poetry.lock....")
                poetry_command = [sys.executable, "-m", "poetry"]
                subprocess.check_output([*poetry_command, "lock"])

                # Update specific packages if provided
                if packages_to_update:
                    print(f"Updating packages: {packages_to_update}")
                    try:
                        subprocess.check_output([*poetry_command, "update", "--lock", *packages_to_update])
                    except subprocess.CalledProcessError as e:
                        print(f"Failed to update packages {packages_to_update}:\n{e.output.decode()}")
                        raise e
                print(f"Copying poetry.lock to destination {poetry_lock_dest}...")
                solution_poetry_lock = solution_root_dir / "poetry.lock"
                assert solution_poetry_lock.is_file()
                shutil.copyfile(solution_poetry_lock, poetry_lock_dest)
            except Exception as e:
                print(e)
                sys.exit(1)
            finally:
                os.chdir(starting_working_directory)
