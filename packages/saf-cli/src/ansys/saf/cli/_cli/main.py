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

from gettext import ngettext
import importlib.metadata
import keyword
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import traceback
import webbrowser

import click
from dotenv import dotenv_values, load_dotenv

from ansys.saf.cli._config.const import (
    DEFAULT_SOLUTION_DISPLAY_NAME,
    DEFAULT_SOLUTION_NAME,
    DEFAULT_SOLUTION_NAMESPACE,
    DEFAULT_STEP_NAME,
    DEFAULT_TEMPLATE_NAME,
    DEFAULT_UI_FRAMEWORK,
    GLOW_API_PORT,
    GLOW_DEBUG,
    GLOW_LOGGING_LEVEL,
    GLOW_SOLUTION_DEFINITION,
    GLOW_UI_DEBUG,
    GLOW_UI_MODULE,
    GLOW_UI_PORT,
    PORTAL_UI_PORT,
    SAF_CLI_EXTERNAL_URL,
    SAF_DESKTOP_LOG_TO_FILES,
    UI_FRAMEWORKS,
)
from ansys.saf.cli._database.manager import SolutionDatabaseManager
from ansys.saf.cli._database.models import SolutionRegistry
from ansys.saf.cli._solutions.add_step import (
    add_step_to_solution,
    check_template_cli_compatibility,
    step_name_exists,
)
from ansys.saf.cli._solutions.environment import InstallError, setup_environment
from ansys.saf.cli._solutions.plugins import list_available_templates, resolve_template
from ansys.saf.cli._solutions.scaffolding import create_solution
from ansys.saf.cli._utilities.archiver import archive_solution
from ansys.saf.cli._utilities.backup import BackupManager
from ansys.saf.cli._utilities.solution_modules import (
    create_solution_environment,
    find_solution_display_name,
    find_solution_root_dir,
    get_exec_from_solution_venv,
    get_main_module,
    get_solution_venv_bin_dir,
    resolve_solution_main_file,
)

LIST_UI_FRAMEWORKS = "\n- ".join(UI_FRAMEWORKS)
UI_PROMPT = f"""What is the UI framework of the Solution?\n- {LIST_UI_FRAMEWORKS}\nChoose UI framework"""


def _validate_namespace_root(_ctx: click.Context, _param: click.Parameter, value: str) -> str:
    """Validate namespace root parameter for Click callback."""

    value = value.strip()
    if not value:
        raise click.BadParameter("Namespace cannot be empty or just whitespace.")

    if value.startswith(".") or value.endswith("."):
        raise click.BadParameter("Namespace must not start or end with a dot.")

    if ".." in value:
        raise click.BadParameter("Namespace must not contain empty segments (for example: a..b).")

    segment_pattern = re.compile(r"^[a-z_][a-z0-9_]*$")
    for segment in value.split("."):
        if segment != segment.lower():
            raise click.BadParameter(f"Namespace segment '{segment}' must be lowercase.")
        if keyword.iskeyword(segment):
            raise click.BadParameter(f"Namespace segment '{segment}' is a Python keyword and is not allowed.")
        if segment and segment[0].isdigit():
            raise click.BadParameter(f"Namespace segment '{segment}' must start with a letter or underscore.")
        if not segment_pattern.fullmatch(segment):
            raise click.BadParameter(
                f"Namespace segment '{segment}' can contain only lowercase letters, numbers, and underscores.",
            )

    return value


def _set_env_var_if_not_none(name: str, value: int | bool | str | None = None, env: dict[str, str] | None = None):
    environment = env or os.environ
    if value is not None:
        environment[name] = str(value)


def _resolve_input_solution(solution: str) -> tuple[SolutionRegistry, str]:
    db_manager = SolutionDatabaseManager()
    solution_root_dir = find_solution_root_dir(db_manager, solution)
    solution_main_file = resolve_solution_main_file(solution_root_dir)
    main_module = get_main_module(solution_main_file)
    if stored_solution := db_manager.get_solution_by_root_dir(solution_root_dir):
        return stored_solution, main_module
    else:
        solution_display_name = find_solution_display_name(solution_main_file) or solution_root_dir.name
        new_solution = SolutionRegistry(
            name=solution_root_dir.name,
            root_dir=solution_root_dir,
            display_name=solution_display_name,
        )
        db_manager.store_solution(new_solution)
        return new_solution, main_module


def _resolve_effective_env_file(solution_root_dir: Path, env_file: Path | None) -> Path | None:
    default_env_file = solution_root_dir / ".env"
    return env_file or (default_env_file if default_env_file.is_file() else None)


def _get_solution_runtime_modules(main_module: str) -> tuple[str, str]:
    solution_module_root = main_module.removesuffix(".main")
    return f"{solution_module_root}.solution.definition", f"{solution_module_root}.ui.app"


def _set_solution_runtime_env_vars(solution_env: dict[str, str], main_module: str, env_file: Path | None):
    """Set GLOW_SOLUTION_DEFINITION and GLOW_UI_MODULE environment variables.

    For backward compatibility with existing solutions that may not define these values in .env,
    derive defaults from the resolved main module. Allows explicit overrides from environment or .env.
    """
    solution_definition_default, ui_module_default = _get_solution_runtime_modules(main_module)
    env_file_values: dict[str, str] = {}
    if env_file and env_file.is_file():
        env_file_values = {k: str(v) for k, v in dotenv_values(env_file).items() if v is not None}

    solution_definition = (
        solution_env.get(GLOW_SOLUTION_DEFINITION)
        or env_file_values.get(GLOW_SOLUTION_DEFINITION)
        or solution_definition_default
    )
    ui_module = solution_env.get(GLOW_UI_MODULE) or env_file_values.get(GLOW_UI_MODULE) or ui_module_default

    solution_env[GLOW_SOLUTION_DEFINITION] = solution_definition
    solution_env[GLOW_UI_MODULE] = ui_module


def _get_executable_absolute_path(executable: str, solution_root_dir: Path) -> Path:
    solution_venv_bin_dir = get_solution_venv_bin_dir(solution_root_dir)
    # We could not find a way to force binaries such as python or pip to resolve to the solution's environment,
    # so we force it by prepending the solution's environment bin directory.
    if (solution_venv_bin_dir / executable).is_file():
        return solution_venv_bin_dir / executable
    elif (solution_venv_bin_dir / f"{executable}.exe").is_file():
        return solution_venv_bin_dir / f"{executable}.exe"
    elif executable == "uv":
        # fallback to user/system-level UV, which is the common installation method for UV, and not per-project.
        uv_exec = shutil.which("uv")
        if uv_exec is not None:
            return Path(uv_exec)
    raise FileNotFoundError(f"Executable '{executable}' not found in solution '{solution_root_dir.name}'.")


def _generic_exception_handler(e: Exception):
    click.secho(f"Error: {e}\n{traceback.format_exc()}", err=True, fg="red")
    sys.exit(1)


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Display the SAF-CLI version.")
@click.pass_context
def saf(ctx: click.Context, version: bool):
    """Utility script for solutions."""
    try:
        if version:
            click.secho(importlib.metadata.version("ansys-saf-cli"), fg="cyan")
            sys.exit(0)
        elif ctx.invoked_subcommand is None:
            click.secho(ctx.get_help())
            sys.exit(0)
    except Exception as e:
        _generic_exception_handler(e)


# By default, click first prompts for all options, and then validates the arguments. This causes an issue where an user
# may do something like "saf <command> extra-invalid-argument" and only after providing all the prompted inputs, they
# receive an error about the invalid argument. To avoid this, we create a custom Command class that first checks for
# extra arguments before prompting for inputs.
class CommandWithPromptsNoArgs(click.Command):
    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        original_args = list(args)
        # The following code snippet is copied from click.Command.parse_args
        parser = self.make_parser(ctx)
        _, args, _ = parser.parse_args(args=args)
        if args and not ctx.allow_extra_args and not ctx.resilient_parsing:
            ctx.fail(
                ngettext(
                    "Got unexpected extra argument ({args})",
                    "Got unexpected extra arguments ({args})",
                    len(args),
                ).format(args=" ".join(map(str, args))),
            )
        return super().parse_args(ctx, original_args)


@saf.command(short_help="Create a new solution", cls=CommandWithPromptsNoArgs)
@click.option(
    "--solution-name",
    prompt="What is the solution name?",
    default=DEFAULT_SOLUTION_NAME,
    help="The name of the solution to be created.",
    type=str,
)
@click.option(
    "--solution-display-name",
    prompt="What is the solution display name?",
    default=DEFAULT_SOLUTION_DISPLAY_NAME,
    help="Name of the solution in the user interface.",
    type=str,
)
@click.option(
    "--ui-framework",
    type=click.Choice(UI_FRAMEWORKS),
    prompt=UI_PROMPT,
    show_choices=False,
    default=DEFAULT_UI_FRAMEWORK,
    help="Type of solution UI.",
)
@click.option(
    "--namespace",
    default=DEFAULT_SOLUTION_NAMESPACE,
    prompt="What is the solution namespace? (e.g. myorg.apps)",
    help=(
        "Provide a dot-separated namespace using lowercase letters, numbers, or underscores. "
        "Example: my_namespace.project"
    ),
    type=str,
    callback=_validate_namespace_root,
)
def new(solution_name: str, solution_display_name: str, ui_framework: str, namespace: str):
    """Create a new Solution in the current working directory."""
    solution_created: bool = False
    solution_root_dir: Path | None = None
    try:
        # solution_name will be used for the name of the python project directory (solution_root_dir).
        # SolutionRegistry contains validation for solution_name to check that the resulting path is valid.
        # In the same way, when registering a solution based on its solution_root_dir path, we extract the solution name
        # from the directory name.
        solution_root_dir = Path.cwd() / solution_name
        if solution_root_dir.exists():
            raise FileExistsError(f"A file or directory already exists at {solution_root_dir}")

        # create model before creating the solution to validate inputs
        solution = SolutionRegistry(name=solution_name, root_dir=solution_root_dir, display_name=solution_display_name)

        # Let's load the db before creating the solution, so that we fail fast in case something is wrong with it.
        db_manager = SolutionDatabaseManager()
        create_solution(solution_name, solution_display_name, ui_framework, namespace)
        solution_created = True
        db_manager.store_solution(solution)
    except Exception as e:
        if solution_root_dir and solution_root_dir.is_dir() and solution_created:
            shutil.rmtree(solution_root_dir)
        _generic_exception_handler(e)


@saf.command(short_help="Create the virtual environment and install the dependencies of a solution")
@click.argument("solution", type=str, default="")
@click.option(
    "-d",
    "--dependencies",
    type=str,
    help=(
        "List of dependency groups to install separated by comas. Example: tests,doc,style. [default: desktop,ui,doc]"
    ),
)
@click.option(
    "-F",
    "--force-clear-all",
    is_flag=True,
    default=False,
    help="Clean-up the workspace. Delete .venv and the project's lockfile. " \
    "For Poetry, also delete .poetry/.venv and .poetry/.cache.",
)
@click.option(
    "-f",
    "--force-clear",
    is_flag=True,
    default=False,
    help="Clean-up the workspace. Delete .venv but keep the lockfile. " \
    "For Poetry, also delete .poetry/.venv and .poetry/.cache.",
)
@click.option(
    "--env-file",
    type=click.Path(exists=True, file_okay=True, path_type=Path),
    help="Load environment variables from this file. [default: .env in the solution root directory]",
)
def install(
    solution: str,
    dependencies: str | None,
    force_clear_all: bool,
    force_clear: bool,
    env_file: Path | None,
):
    """Create the virtual environment and install the dependencies of a solution

    SOLUTION: The name of a registered Solution, or the path to a solution directory (relative or absolute).
    When specifying a path, it must point to the root dir of the solution, which contains the src directory. If left
    empty, the current working directory is assumed to be the root dir of a solution. When using a path or left empty,
    if the resolved directory is a valid solution directory, the solution is registered in the database.
    """
    try:
        stored_solution, main_module = _resolve_input_solution(solution)
        dependency_groups = dependencies.split(",") if dependencies else None
        workspace_clear = "hard" if force_clear_all else "soft" if force_clear else None
        default_env_file = stored_solution.root_dir / ".env"
        env_file = env_file or (default_env_file if default_env_file.is_file() else None)
        setup_environment(
            solution_root_dir=stored_solution.root_dir,
            solution_main_module_name=main_module,
            dependency_groups=dependency_groups,
            workspace_clear=workspace_clear,
            env_file=env_file,
        )
    except InstallError as ie:
        click.secho(str(ie), err=True, fg="red")
        sys.exit(1)
    except Exception as e:
        _generic_exception_handler(e)


@saf.command(short_help="List stored solutions")
def solutions():
    """List all the Solutions stored in the database. Solutions marked as invalid are not shown."""
    try:
        db_manager = SolutionDatabaseManager()
        solutions_by_name = db_manager.get_solutions_grouped_by_name()
        if not solutions_by_name:
            click.secho("No solutions found.", fg="yellow")
            return
        for solution_name, solutions in solutions_by_name.items():
            click.secho(f"{solution_name}", fg="cyan", bold=True)
            for solution in solutions:
                click.secho(f"    Root directory: {solution.root_dir}", fg="green")
                click.secho(f"    Display Name: {solution.display_name}", fg="green")
                click.secho()
    except Exception as e:
        _generic_exception_handler(e)


@saf.command(short_help="List installed templates")
@click.option("--steps", is_flag=True, help="List only steps.")
@click.option("--solutions", is_flag=True, help="List only solutions.")
@click.option("--verbose", is_flag=True, help="Enable verbose output.")
def templates(steps: bool, solutions: bool, verbose: bool):
    """List all the templates installed in the system."""
    try:
        if steps and solutions:
            raise click.UsageError("Cannot use both --steps and --solutions flags together.")
        list_available_templates(steps_only=steps, solutions_only=solutions, verbose=verbose)
    except Exception as e:
        _generic_exception_handler(e)


@saf.command(short_help="Run a solution from source code.")
@click.argument("solution", type=str, default="")
@click.option(
    "--portal",
    is_flag=True,
    default=False,
    help="Run the solution with Portal. If set, the portal UI will open instead of the solution UI.",
)
@click.option("--no-ui", is_flag=True, default=False, help="Run the solution without the UI server.")
@click.option(
    "--browser",
    is_flag=True,
    default=False,
    help="Run the solution without webview, opening the UI in the browser.",
)
@click.option("--streamlit-ui", is_flag=True, default=False, help="Run the solution with Streamlit UI framework.")
@click.option(
    "--loglevel",
    envvar=GLOW_LOGGING_LEVEL,
    default=None,
    type=str,
    help="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL.",
)
@click.option("--debug", envvar=GLOW_DEBUG, is_flag=True, default=False, help="Run the solution in debug mode.")
@click.option(
    "--ui-debugger",
    envvar=GLOW_UI_DEBUG,
    is_flag=True,
    default=False,
    help="Enable debugpy.listen in UI process and disable Dash/Flask debug functionality.",
)
@click.option(
    "--portal-ui-port",
    envvar=PORTAL_UI_PORT,
    type=int,
    help="The port on which the portal is running. [default: random]",
)
@click.option(
    "--solution-api-port",
    envvar=GLOW_API_PORT,
    type=int,
    help="The port on which the solution api is running. [default: random]",
)
@click.option(
    "--solution-ui-port",
    envvar=GLOW_UI_PORT,
    type=int,
    help="The port on which the solution ui is running. [default: random]",
)
@click.option(
    "--project",
    default=None,
    type=str,
    help="Display name of the project to open or create. This option cannot be used if Portal is running.",
)
@click.option(
    "--env-file",
    type=click.Path(exists=True, file_okay=True, path_type=Path),
    help="Load environment variables from this file. [default: .env in the solution root directory]",
)
@click.option(
    "--no-automatic-project-migration",
    is_flag=True,
    default=False,
    help="Disable automatic schema migration for old projects.",
)
@click.option(
    "--log-to-files",
    envvar=SAF_DESKTOP_LOG_TO_FILES,
    is_flag=True,
    default=False,
    help="Log to files and disable OTEL dashboard.",
)
def run(
    solution: str,
    portal: bool,
    no_ui: bool,
    browser: bool,
    streamlit_ui: bool,
    loglevel: str | None,
    debug: bool,
    ui_debugger: bool,
    portal_ui_port: int | None,
    solution_api_port: int | None,
    solution_ui_port: int | None,
    project: str | None,
    env_file: Path | None,
    no_automatic_project_migration: bool,
    log_to_files: bool,
):
    """Run a Solution.

    SOLUTION: The name of a registered Solution, or the path to a solution directory (relative or absolute).
    When specifying a path, it must point to the root dir of the solution, which contains the src directory. If left
    empty, the current working directory is assumed to be the root dir of a solution. When using a path or left empty,
    if the resolved directory is a valid solution directory, the solution is registered in the database.
    """
    try:
        stored_solution, main_module = _resolve_input_solution(solution)
        env_file = _resolve_effective_env_file(stored_solution.root_dir, env_file)

        solution_env = create_solution_environment(stored_solution.root_dir)
        _set_solution_runtime_env_vars(solution_env, main_module, env_file)
        _set_env_var_if_not_none(GLOW_LOGGING_LEVEL, loglevel, solution_env)
        if debug:  # don't overwrite env var if user has not set the flag explicitly, bool variables are always not None
            _set_env_var_if_not_none(GLOW_DEBUG, debug, solution_env)
        if ui_debugger:
            _set_env_var_if_not_none(GLOW_UI_DEBUG, ui_debugger, solution_env)
        _set_env_var_if_not_none(PORTAL_UI_PORT, portal_ui_port, solution_env)
        _set_env_var_if_not_none(GLOW_API_PORT, solution_api_port, solution_env)
        _set_env_var_if_not_none(GLOW_UI_PORT, solution_ui_port, solution_env)

        executable = get_exec_from_solution_venv(stored_solution.root_dir, "python")
        cmd: list[str] = [
            executable.as_posix(),
            "-m",
            "ansys.saf.desktop.orchestrator",
            "--solution-main-module-name",
            f"{main_module}",
        ]
        cmd += ["--no-ui"] if no_ui else []
        cmd += ["--portal"] if portal else []
        cmd += ["--browser"] if browser else []
        cmd += ["--streamlit-ui"] if streamlit_ui else []
        cmd += ["--project-display-name", project] if project else []
        cmd += ["--env-file", env_file.resolve().as_posix()] if env_file else []
        cmd += ["--no-automatic-project-migration"] if no_automatic_project_migration else []
        cmd += ["--log-to-files"] if log_to_files else []
        subprocess.run(cmd, env=solution_env, cwd=stored_solution.root_dir, check=True)
    except Exception as e:
        _generic_exception_handler(e)


@saf.command(short_help="Execute a command using the solution's python environment")
@click.argument("solution", type=str, default="")
@click.argument("command", type=str, default="", required=True)
@click.option(
    "--cwd",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory in which the command will be executed. [default: solution root directory]",
)
@click.option(
    "--env-file",
    type=click.Path(exists=True, file_okay=True, path_type=Path),
    help="Load environment variables from this file. [default: .env in the solution root directory]",
)
def execute(solution: str, command: str, cwd: Path | None, env_file: Path | None = None):
    try:
        # If a single argument is passed it is interpreted as the command and it will be executed in the
        # current working directory's solution, if any.
        if not command:
            command = solution
            solution = ""

        stored_solution, main_module = _resolve_input_solution(solution)

        cmd = shlex.split(command)
        executable = cmd[0]
        executable_abs_path = _get_executable_absolute_path(executable, stored_solution.root_dir)

        cwd = cwd or stored_solution.root_dir

        env_file = _resolve_effective_env_file(stored_solution.root_dir, env_file)
        if env_file and env_file.is_file():
            click.secho(f"Environment variables loaded from {env_file.resolve()}")
            load_dotenv(env_file)
        solution_env = create_solution_environment(stored_solution.root_dir)
        _set_solution_runtime_env_vars(solution_env, main_module=main_module, env_file=env_file)

        subprocess.run([executable_abs_path.as_posix()] + cmd[1:], cwd=cwd, env=solution_env, check=True)
    except Exception as e:
        _generic_exception_handler(e)


@saf.command(short_help="Archive a solution's source code.")
@click.argument("solution", type=str, default="")
@click.option(
    "--filename",
    default=None,
    type=str,
    help="The name of the archive file to create. If not provided, the solution name is used.",
)
@click.option(
    "--path",
    default=None,
    type=str,
    help="The path to a directory where to save the solution. If not provided, the current parent directory is used.",
)
@click.option(
    "--extension",
    default=None,
    type=str,
    help="The extension of the archive file to create. If not provided, .saf will be used.",
)
def archive(
    solution: str,
    filename: str | None,
    path: Path | None,
    extension: str | None,
):
    """Create a .saf archive from the given solution.

    SOLUTION: The name of a registered Solution, or the path to a solution directory (relative or absolute).
    When specifying a path, it must point to the root dir of the solution, which contains the src directory. If left
    empty, the current working directory is assumed to be the root dir of a solution. When using a path or left empty,
    if the resolved directory is a valid solution directory, the solution is registered in the database.
    """
    try:
        stored_solution, _ = _resolve_input_solution(solution)

        archive_solution(
            solution_root_dir=stored_solution.root_dir,
            archive_name=filename or stored_solution.name,
            archive_path=Path(path) if path else None,
            archive_extension=extension,
        )
    except Exception as e:
        _generic_exception_handler(e)


@saf.command(short_help="Open SAF documentation in a web browser.")
def doc():
    """Opens SAF documentation in a web browser."""
    try:
        webbrowser.open(SAF_CLI_EXTERNAL_URL)
    except Exception as e:
        _generic_exception_handler(e)


@saf.command(short_help="Package the solution for distribution.")
@click.argument("solution", type=str, default="")
@click.option(
    "--display-console-window",
    is_flag=True,
    default=False,
    help="Display the console window when running the solution.",
)
@click.option("--encrypt", is_flag=True, default=False, help="Encrypt the solution code before packaging.")
@click.option(
    "--encryption-file",
    help="The file containing the list of files to encrypt.",
    default="",
)
@click.option("--encryption-key", help="The encryption key to use for obfuscation.", default="")
@click.option(
    "--no-executable",
    is_flag=True,
    default=False,
    help="Do not create an executable installer for the solution.",
)
@click.option(
    "--executable-as-dir",
    is_flag=True,
    default=False,
    help=(
        "Bundle the executable in a directory containing all the supporting files. "
        "This is mandatory if the executable file size exceeds the pyinstaller limit of 4GB."
    ),
)
@click.option("--obfuscate", is_flag=True, default=False, help="Obfuscate the solution code before packaging.")
@click.option(
    "--offline-package",
    is_flag=True,
    default=False,
    help="Create a package that installs without internet access.",
)
@click.option(
    "--exclude-python",
    is_flag=True,
    default=False,
    help="Do not ship the Python interpreter with the packaged solution.",
)
@click.option(
    "--python-version",
    help="The version of Python to use for the solution.",
    default="",
)
@click.option(
    "--force-python-from-source",
    is_flag=True,
    default=False,
    help="Force building Python from source instead of downloading it from NuGet packages (Windows only).",
)
@click.option(
    "--solution-entry-point",
    help=(
        "The main solution entry point to start the solution. "
        "Module should be a dotted import ('ansys.solutions.mysoln.main'). "
        "If not provided, the solution will be run with the default entry point."
    ),
    default="",
)
@click.option("--github-token", help="Personal Access Token for downloading dependencies from GitHub.", default="")
@click.option("--solution-ui-framework", help="The UI framework used in the solution.", default="")
@click.option("--no-glow", is_flag=True, default=False, help="Add this flag if the solution does not use SAF/GLOW.")
@click.option(
    "--env-file",
    type=click.Path(exists=True, file_okay=True, path_type=Path),
    help="Load environment variables from this file. [default: .env in the solution root directory]",
)
def build(
    solution: str,
    display_console_window: bool,
    encrypt: bool,
    encryption_file: str,
    encryption_key: str,
    no_executable: bool,
    executable_as_dir: bool,
    obfuscate: bool,
    offline_package: bool,
    exclude_python: bool,
    python_version: str,
    force_python_from_source: bool,
    solution_entry_point: str,
    github_token: str,
    solution_ui_framework: str,
    no_glow: bool,
    env_file: Path | None = None,
):
    """Package the solution for distribution.

    This command will package the solution into a single executable file for distribution. The solution is
    packaged as a standalone executable that can be run on any machine without needing to install Python or any
    dependencies. The solution is packaged with all its dependencies and the Python interpreter.

    The solution is packaged using PyInstaller. The packaged solution is saved in the dist directory of the solution.

    SOLUTION: The name of a registered Solution, or the path to a solution directory (relative or absolute).
    When specifying a path, it must point to the root dir of the solution, which contains the src directory. If left
    empty, the current working directory is assumed to be the root dir of a solution. When using a path or left empty,
    if the resolved directory is a valid solution directory, the solution is registered in the database.
    """
    try:
        stored_solution, main_module = _resolve_input_solution(solution)
        env_file = _resolve_effective_env_file(stored_solution.root_dir, env_file)

        executable = get_exec_from_solution_venv(stored_solution.root_dir, "python")
        cmd: list[str] = [
            executable.as_posix(),
            "-m",
            "ansys.saf.desktop.installer",
        ]
        cmd += ["--display-console-window"] if display_console_window else []
        cmd += ["--encrypt"] if encrypt else []
        cmd += ["--encryption-file", encryption_file] if encryption_file else []
        cmd += ["--encryption-key", encryption_key] if encryption_key else []
        cmd += ["--no-executable"] if no_executable else []
        cmd += ["--executable-as-dir"] if executable_as_dir else []
        cmd += ["--obfuscate"] if obfuscate else []
        cmd += ["--offline-package"] if offline_package else []
        cmd += ["--exclude-python"] if exclude_python else []
        cmd += ["--python-version", python_version] if python_version else []
        cmd += ["--force-python-from-source"] if force_python_from_source else []
        cmd += ["--solution-entry-point", solution_entry_point] if solution_entry_point else []
        cmd += ["--github-token", github_token] if github_token else []
        cmd += ["--solution-ui-framework", solution_ui_framework] if solution_ui_framework else []
        cmd += ["--no-glow"] if no_glow else []
        cmd += ["--env-file", env_file.resolve().as_posix()] if env_file else []

        solution_env = create_solution_environment(stored_solution.root_dir)
        _set_solution_runtime_env_vars(solution_env, main_module, env_file)
        subprocess.run(cmd, cwd=stored_solution.root_dir, env=solution_env, check=True)
    except Exception as e:
        _generic_exception_handler(e)


@saf.command(short_help="Add a new step to the solution, with or without associated UI.")
@click.argument("solution", type=str, default="")
@click.option(
    "--step-name",
    prompt="What is the Step name?",
    default=DEFAULT_STEP_NAME,
    help="The name of the step to add to the solution. It is assumed that the step name is provided in snake_case.",
    type=str,
)
@click.option(
    "--ui-framework",
    type=click.Choice(UI_FRAMEWORKS),
    prompt=UI_PROMPT,
    show_choices=False,
    default=DEFAULT_UI_FRAMEWORK,
    help="Type of solution UI.",
)
@click.option(
    "--template",
    prompt="What is the Step template name?",
    default=DEFAULT_TEMPLATE_NAME,
    help="The name of the step template to be used.",
    type=str,
)
def add_step(
    solution: str,
    step_name: str,
    ui_framework: str,
    template: str,
):
    """Add a new step to the solution, with or without associated UI.

    SOLUTION: The name of a registered Solution, or the path to a solution directory (relative or absolute).
    When specifying a path, it must point to the root dir of the solution, which contains the src directory. If left
    empty, the current working directory is assumed to be the root dir of a solution. When using a path or left empty,
    if the resolved directory is a valid solution directory, the solution is registered in the database.
    """
    try:
        stored_solution, solution_main_module = _resolve_input_solution(solution)
        # expected format: <namespace>.<solution_name>.main
        # e.g., saf.solutions.my_solution.main or org.apps.my_solution.main
        solution_package_name = solution_main_module.split(".")[-2]
        namespace_root = ".".join(solution_main_module.split(".")[:-2])
        saf_step_template = resolve_template(template)
        if saf_step_template.type != "step":
            raise ValueError(f"Template '{template}' is of type '{saf_step_template.type}', expected 'step'")

        ctx = click.get_current_context()
        step_name_source = ctx.get_parameter_source("step_name")

        if step_name_source == click.core.ParameterSource.PROMPT:
            while step_name_exists(stored_solution.root_dir, solution_package_name, step_name):
                click.secho(
                    f"A step with name '{step_name}' already exists in solution '{stored_solution.name}'.",
                    fg="yellow",
                )
                step_name = click.prompt("Please enter a different Step name", default=DEFAULT_STEP_NAME)
        elif step_name_exists(stored_solution.root_dir, solution_package_name, step_name):
            raise ValueError(f"Step name '{step_name}' is already taken in solution '{stored_solution.name}'.")

        check_template_cli_compatibility(stored_solution.root_dir, saf_step_template)

        with BackupManager(stored_solution.root_dir, solution_package_name, namespace_root):
            add_step_to_solution(
                stored_solution.name,
                stored_solution.root_dir,
                solution_package_name,
                step_name,
                ui_framework,
                saf_step_template,
            )
    except Exception as e:
        _generic_exception_handler(e)


def entry_point():
    saf(obj={})
