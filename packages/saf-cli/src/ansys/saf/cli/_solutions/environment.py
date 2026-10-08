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

from contextlib import contextmanager
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
from typing import Any
from urllib.parse import urlparse

import click
from dotenv import load_dotenv
from packaging.markers import Marker
import requests
from requests.auth import HTTPBasicAuth
import tomlkit

from ansys.saf.cli._config.const import (
    WORKSPACE_CLEAR_OPTIONS,
)
from ansys.saf.cli._utilities.solution_modules import get_exec_from_solution_venv


class InstallError(Exception):
    """Custom exception for install errors.
    Errors of this type are not internal issues with
    the saf install command but are instead issues
    relating to the user's environment or input.
    """


# Path definition ---------------------------------------------------------------------------------------------------


# leave as relative paths, they are resolved after setup_environment changes the working dir to the solution_root_dir
PYPROJECT_FILE = Path("pyproject.toml")
VENV_DIR = Path(".venv")
POETRY_LOCK_FILE = Path("poetry.lock")
POETRY_VENV_DIR = Path(".poetry") / ".venv"
POETRY_CACHE_DIR = Path(".poetry") / ".cache"
POETRY_PYTHON_EXEC = (
    POETRY_VENV_DIR / "Scripts" / "python.exe" if platform.system() == "Windows" else POETRY_VENV_DIR / "bin" / "python"
)
POETRY_POETRY_EXEC = (
    POETRY_VENV_DIR / "Scripts" / "poetry.exe" if platform.system() == "Windows" else POETRY_VENV_DIR / "bin" / "poetry"
)
PYTHON_EXEC = VENV_DIR / "Scripts" / "python.exe" if platform.system() == "Windows" else VENV_DIR / "bin" / "python"
POETRY_EXEC = VENV_DIR / "Scripts" / "poetry.exe" if platform.system() == "Windows" else VENV_DIR / "bin" / "poetry"


# Console prints ----------------------------------------------------------------------------------------------------


def _print_main_header(text: str, max_length: int = 100) -> None:
    """Display main header."""
    for _ in range(max_length):
        print("=", end="")
    print()
    print(text)
    for _ in range(max_length):
        print("=", end="")
    print()
    print()


def _print_section_header(text: str, max_length: int = 100) -> None:
    """Display a section header in the console."""
    section_header = ""
    if len(text) < max_length:
        section_header = text + " "
        for _ in range(len(text), max_length):
            section_header += "-"
    else:
        section_header = text
    print(section_header)
    print()


def _print_input_value(input_str: str, value: str, separator: str = ":", separator_position: int = 60) -> None:
    """Print input value in console."""
    if len(input_str) < separator_position:
        text = input_str
        for _ in range(len(text), separator_position):
            text += " "
        text += separator + " " + value
    else:
        text = input_str + " " + separator + " " + value
    print(text)


def _print_inputs_summary(
    dependency_groups: list[str],
    build_system_version: str,
    optional_dependency_groups: list[str],
) -> None:
    """Display a summary of the inputs."""
    print(f"OS                                   : {platform.system()}")
    print(f"Python version                       : {_get_python_version()}")
    print("Virtual environment name             : .venv")
    for dependency_group in optional_dependency_groups:
        _print_input_value(
            f"{dependency_group} dependencies",
            "yes" if dependency_group in dependency_groups else "no",
            separator=":",
            separator_position=37,
        )
    print("Dependency management system         : poetry")
    print(f"Dependency management system version : {build_system_version}")
    print()


# Checks ------------------------------------------------------------------------------------------------------------


def _check_python_version(configuration: dict[str, Any]) -> None:  # noqa: C901
    """Check if current Python is consistent with the python specifications from the build system."""
    # Initialize lower/upper versions
    lower_version, upper_version, lower_bound_symbol, upper_bound_symbol = None, None, None, None
    lower_specification, upper_specification, single_specification = None, None, None
    # Read Python version constraint
    if (
        "tool" not in configuration
        or "poetry" not in configuration["tool"]
        or "dependencies" not in configuration["tool"]["poetry"]
        or "python" not in configuration["tool"]["poetry"]["dependencies"]
    ):
        raise RuntimeError("Python dependency not specified in pyproject.")
    python_compatibility = configuration["tool"]["poetry"]["dependencies"]["python"].replace(" ", "")
    # Split lower/upper version constraint
    if "," in python_compatibility:
        lower_specification, upper_specification = (
            python_compatibility.split(",")[0],
            python_compatibility.split(",")[1],
        )
    elif python_compatibility.startswith(">"):
        lower_specification, upper_specification = python_compatibility, None
    elif python_compatibility.startswith("<"):
        lower_specification, upper_specification = None, python_compatibility
    else:
        single_specification = python_compatibility

    if single_specification:
        version = _get_version_from_python_specification(single_specification)
        sign = _get_sign_from_python_specification(single_specification)
        if sign != "==":
            raise Exception("Unable to interpret python version specification.")
        marker = Marker(f"python_full_version {sign} '{version}'")
        if not marker.evaluate():
            raise Exception(f"Python version must be equal to {version}.")
        return
    error_message = ""
    lower_marker: Marker | None = None
    upper_marker: Marker | None = None
    if lower_specification:
        lower_version = _get_version_from_python_specification(lower_specification)
        lower_bound_symbol = _get_sign_from_python_specification(lower_specification)
        lower_marker = Marker(f"python_full_version {lower_bound_symbol} '{lower_version}'")
        error_message += (
            f"Python version must be {lower_bound_symbol} {lower_version}. " if not lower_marker.evaluate() else ""
        )
    if upper_specification:
        upper_version = _get_version_from_python_specification(upper_specification)
        upper_bound_symbol = _get_sign_from_python_specification(upper_specification)
        upper_marker = Marker(f"python_full_version {upper_bound_symbol} '{upper_version}'")
        error_message += (
            f"Python version must be {upper_bound_symbol} {upper_version}." if not upper_marker.evaluate() else ""
        )
    if error_message:
        raise Exception(error_message)


def _check_virtual_environment_exists() -> bool:
    """Check if an install exists already."""
    return VENV_DIR.is_dir()


def set_user_level_environment_variable(variable_name: str, value: str) -> None:
    """Set environment variable at the user level for persistence."""
    os.environ[variable_name] = value

    variable_name_formatted = click.style(variable_name, fg="cyan", bold=True)

    if platform.system() == "Windows":
        try:
            subprocess.run(
                ["setx", variable_name, value],  # noqa: S607
                check=True,
                capture_output=True,
                text=True,
            )
            click.echo(
                f"Environment variable {variable_name_formatted} set permanently for the current Windows user",
            )
        except subprocess.CalledProcessError:
            click.echo(f"Warning: Could not set permanent environment variable {variable_name_formatted}")
    else:
        home_dir = Path.home()
        profile_files = [
            home_dir / ".bash_profile",
            home_dir / ".bashrc",
            home_dir / ".profile",
        ]

        export_line = f'export {variable_name}="{value}"\n'

        for profile_file in profile_files:
            if profile_file.exists():
                try:
                    content = profile_file.read_text()
                    if f"export {variable_name}=" not in content:
                        with profile_file.open("a") as f:
                            f.write(export_line)
                        click.echo(f"Environment variable {variable_name_formatted} added to {profile_file}")
                        break
                except OSError:
                    continue
        else:
            try:
                bashrc = home_dir / ".bashrc"
                with bashrc.open("a") as f:
                    f.write(export_line)
                click.echo(f"Created {bashrc} and added {variable_name_formatted}")
            except OSError:
                click.echo(f"Warning: Could not set permanent environment variable {variable_name_formatted}")


def _prompt_for_credentials(source: dict[str, Any], is_first_attempt: bool) -> tuple[str, str]:
    """Interactively prompt user for PyPI credentials."""
    source_name = source["name"]
    source_url = source.get("url", "")

    if is_first_attempt:
        click.echo(f"\nMissing credentials for private PyPI source: {click.style(source_name, fg='cyan', bold=True)}")
        click.echo(f"URL: {source_url}")

    click.echo()

    username = click.prompt(
        f"Enter username for {click.style(source_name, fg='cyan', bold=True)}",
        type=str,
        show_default=False,
    ).strip()

    password = click.prompt(
        f"Enter password/token for {click.style(source_name, fg='cyan', bold=True)}",
        type=str,
        hide_input=True,
        show_default=False,
    ).strip()

    return username, password


def _get_netrc_path():
    netrc_raw_path = os.getenv("NETRC")
    if netrc_raw_path is None:
        netrc_file_name = "_netrc" if platform.system() == "Windows" else ".netrc"
        netrc_path = Path.home() / netrc_file_name
    else:
        netrc_path = Path(netrc_raw_path)
    return netrc_path


def _get_credentials_from_netrc(source: dict[str, Any]) -> tuple[Path, str, str, str] | None:
    hostname = _get_parsed_url_from_source(source).hostname

    if hostname is None:
        return None

    netrc_path = _get_netrc_path()

    if not netrc_path.is_file():
        return None

    try:
        with netrc_path.open("r") as netrc_file:
            netrc_content = netrc_file.read()

        machine_pattern = re.compile(
            r"default\s+login\s+(\S+)\s+password\s+(\S+)",
            re.IGNORECASE,
        )
        match = machine_pattern.search(netrc_content)

        if match:
            raise InstallError(
                "The netrc file contains the 'default' keyword which is not supported by pypi. "
                f"The netrc file is located at: {netrc_path}",
            )

        machine_pattern = re.compile(
            rf"machine\s+{re.escape(hostname)}\s+login\s+(\S+)\s+password\s+(\S+)",
            re.IGNORECASE,
        )
        match = machine_pattern.search(netrc_content)

        if match:
            netrc_username, netrc_password = match.groups()
            return netrc_path, hostname, netrc_username, netrc_password

    except InstallError:
        raise
    except Exception as e:
        click.secho(f"Warning: Could not read .netrc file at {netrc_path}: {e}", err=True, fg="yellow")

    return None


def _check_credentials_consistent_with_netrc(source: dict[str, Any], username: str, password: str) -> bool:
    """Check for consistency between provided credentials and .netrc file."""

    credentials = _get_credentials_from_netrc(source)

    if credentials is None:
        return True  # No .netrc entry to compare against

    netrc_path, hostname, netrc_username, netrc_password = credentials
    if netrc_username != username or netrc_password != password:
        raise InstallError(
            f"Error: Credentials in poetry environment variables for {hostname} do not match those in {netrc_path}.",
        )

    return True


def validate_credentials(
    source: dict[str, Any],
    username: str,
    password: str,
    certificate: str | None = None,
    verify: bool = True,
) -> bool:
    """
    Validate the provided username and password against the remote PyPI server specified in the source.

    Args:
        source (dict[str, Any]): The source dictionary containing the PyPI server URL.
        username (str): The username to authenticate with.
        password (str): The password to authenticate with.

    Returns:
        bool: True if credentials are valid, False if unauthorized. Exits on other errors.
    """
    url = str(source["url"])

    try:
        response = requests.get(
            url + "/JUNK",
            auth=HTTPBasicAuth(username, password),
            timeout=(10, 10),
            verify=certificate if verify else False,
        )
    except requests.exceptions.SSLError as e:
        raise InstallError(
            f"SSL certificate validation failed for {_get_source_name_formatted(source)}. "
            "Please check the provided certificate.",
        ) from e
    except requests.RequestException as e:
        raise InstallError(f"Unable to reach {_get_source_name_formatted(source)} on {url}") from e

    if response.status_code == 401:
        return False
    elif response.status_code in (200, 404):
        return True

    raise InstallError(
        f"Unexpected response from {_get_source_name_formatted(source)}, Code is {response.status_code}",
    )


def _get_parsed_url_from_source(source: dict[str, Any]):
    parsed_url = urlparse(str(source["url"]))
    return parsed_url


def _can_use_credentials_from_environment_variables_or_netrc(
    source: dict[str, Any],
    username_var: str,
    password_var: str,
    certificate_var: str,
) -> bool:
    username = os.environ.get(username_var)
    password = os.environ.get(password_var)
    certificate, certificate_verification_disabled = _read_certificate_from_environment_variable(certificate_var)

    if username and password:
        _check_credentials_consistent_with_netrc(source, username, password)

        click.echo(f"Validating credentials for {_get_source_name_formatted(source)}...")
        if validate_credentials(
            source,
            username,
            password,
            certificate=certificate,
            verify=not certificate_verification_disabled,
        ):
            click.secho(f"Credentials for {source['name']} are valid.", fg="green")
            return True
        else:
            click.secho(f"Invalid credentials for {source['name']}", err=True, fg="red")
    else:
        credentials = _get_credentials_from_netrc(source)
        if credentials is not None:
            netrc_path, _, username, password = credentials
            source_name_formatted = _get_source_name_formatted(source)
            if validate_credentials(
                source,
                username,
                password,
                certificate=certificate,
                verify=not certificate_verification_disabled,
            ):
                click.secho(f"Using credentials from {netrc_path} for {source_name_formatted}.", fg="green")
                return True
            else:
                raise InstallError(
                    f"Unable to access private PyPI source {source_name_formatted}. "
                    "Poetry credential environment variables are not set "
                    f"and invalid credentials appear in {netrc_path}",
                )

    return False


def _check_private_sources(configuration: dict[str, Any]) -> None:
    """Check and interactively manage private PyPI credentials."""
    private_sources = configuration["tool"]["poetry"].get("source", [])
    credentials_updated, certificate_updated = False, False

    for source in private_sources:
        if source["name"].lower() == "pypi":
            source["url"] = "https://pypi.org/simple"

        click.secho(
            f"Checking access to {_get_source_name_formatted(source)}...",
        )

        source_name_slug = source["name"].upper().replace("-", "_")
        certificate_var = f"POETRY_CERTIFICATES_{source_name_slug}_CERT"

        certificate_updated = _prompt_validate_and_set_certificates(source, certificate_var) or certificate_updated

        if source["name"].lower() == "pypi":
            click.echo()
            continue

        username_var = f"POETRY_HTTP_BASIC_{source_name_slug}_USERNAME"
        password_var = f"POETRY_HTTP_BASIC_{source_name_slug}_PASSWORD"

        if not _can_use_credentials_from_environment_variables_or_netrc(
            source,
            username_var,
            password_var,
            certificate_var,
        ):
            credentials_updated = (
                _prompt_validate_and_set_credentials(source, username_var, password_var, certificate_var)
                or credentials_updated
            )

        click.echo()

    if credentials_updated or certificate_updated:
        click.echo()
        click.secho(
            "IMPORTANT: Environment variables have been updated.\n"
            "Please restart your terminal/IDE for the changes to take effect:\n"
            "   - If using VS Code: Close ALL instances and restart VS Code\n"
            "   - If using Command Prompt/PowerShell: Close and reopen your terminal\n"
            "   - If using Linux/macOS terminal: Start a new terminal session or run 'source ~/.bashrc'\n"
            "Then run the install command again to continue with the setup.",
            fg="yellow",
            bold=True,
        )
        sys.exit(0)


def _prompt_validate_and_set_credentials(
    source: dict[str, Any],
    username_var: str,
    password_var: str,
    certificate_var: str,
):
    attempt = 0
    credentials_updated = False

    certificate, certificate_verification_disabled = _read_certificate_from_environment_variable(certificate_var)

    while True:
        try:
            attempt += 1
            new_username, new_password = _prompt_for_credentials(source, bool(attempt))
            click.echo("Validating credentials...")
            if validate_credentials(
                source,
                new_username,
                new_password,
                certificate=certificate,
                verify=not certificate_verification_disabled,
            ):
                set_user_level_environment_variable(username_var, new_username)
                set_user_level_environment_variable(password_var, new_password)
                credentials_updated = True

                click.secho(f"Successfully configured credentials for {source['name']}", fg="green")
                break
            else:
                click.secho(
                    "Invalid credentials. Please check your username and password/token and try again.",
                    err=True,
                    fg="red",
                )
        except click.Abort as e:
            raise InstallError(
                f"\nSetup cancelled. Install will fail without valid credentials for {source['name']}",
            ) from e
        except KeyboardInterrupt as e:
            raise InstallError(
                f"\nSetup interrupted. Install will fail without valid credentials for {source['name']}",
            ) from e

    return credentials_updated


def _prompt_validate_and_set_certificates(source: dict[str, Any], certificate_var: str):
    """Prompt, validate and set SSL certificate for a given source."""
    certificate, certificate_verification_disabled = _read_certificate_from_environment_variable(certificate_var)

    if certificate_verification_disabled:
        click.secho(
            f"SSL certificate verification is currently disabled for {_get_source_name_formatted(source)}. "
            "Note that this is not recommended as it can pose security risks.",
            fg="yellow",
        )
        return False
    elif not is_valid_certificate(source, certificate):
        click.secho(
            f"An SSL certificate is required to access the {_get_source_name_formatted(source)} source. "
            "This is likely because you are in a corporate network with SSL interception "
            "or because the source uses a self-signed certificate.",
        )
    else:
        return False

    while True:
        try:
            new_certificate = _prompt_for_certificate(source)
            set_user_level_environment_variable(certificate_var, new_certificate)
            certificate = new_certificate
        except click.Abort as e:
            raise InstallError(
                f"\nSetup cancelled. Install will fail without a valid SSL certificate for {source['name']}",
            ) from e
        except KeyboardInterrupt as e:
            raise InstallError(
                f"\nSetup interrupted. Install will fail without a valid SSL certificate for {source['name']}",
            ) from e

        if not is_valid_certificate(source, certificate):
            click.secho(
                "Invalid certificate. Please check the provided certificate and try again.",
                err=True,
                fg="red",
            )
        else:
            break

    click.secho(f"Successfully configured certificate for {source['name']}", fg="green")
    return True


def _prompt_for_certificate(source: dict[str, Any]):
    """Interactively prompt user for PyPI certificate."""
    source_name = source["name"]

    while True:
        certificate = click.prompt(
            f"Enter the path to a valid SSL certificate for {click.style(source_name, fg='cyan', bold=True)}",
            type=str,
            show_default=False,
        ).strip()
        if Path(certificate).is_file():
            break
        else:
            click.secho("Invalid file path. Please enter a valid path to the SSL certificate.", err=True, fg="red")

    return certificate


def is_valid_certificate(source: dict[str, Any], certificate: str | None) -> bool:
    """
    Validate the provided SSL certificate against the remote PyPI server specified in the source.

    Args:
        source (dict[str, Any]): The source dictionary containing the PyPI server URL.
        certificate_path (str | None): The path to the SSL certificate to validate.

    Returns:
        bool: True if certificate is valid, False otherwise.
    """
    url = str(source["url"])

    try:
        requests.get(
            url + "/JUNK",
            verify=certificate or True,
            timeout=(10, 10),
        )
        return True
    except (requests.exceptions.SSLError, requests.RequestException):
        return False


def _get_source_name_formatted(source: dict[str, Any]):
    return click.style(source["name"], fg="cyan", bold=True)


def _read_certificate_from_environment_variable(certificate_var: str) -> tuple[str | None, bool]:
    """Read certificate path from environment variable and check if certificate verification is disabled."""
    certificate = os.environ.get(certificate_var)

    if certificate:  # noqa: SIM102
        if certificate.lower() == "false":
            return None, True

    return certificate, False


# General-purpose ---------------------------------------------------------------------------------------------------


def _read_integers_from_string(string: str) -> list[str]:
    """Scan a string and extract integers. The regex matches any digit character (0-9)."""
    return re.findall(r"\d+", string)


def _get_python_version() -> str:
    """Get Python version."""
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _set_pip_command(
    package_name: str,
    package_version: str = "*",
    method: str = "install",
    pypi_url: str = "https://pypi.org/simple",
    private_pypi_token_name: str = "",
    no_deps: bool = False,
    python_executable: str = sys.executable,
) -> list[str]:
    """Make pip command."""
    package_name += f"=={package_version}" if package_version != "*" else ""
    command = [python_executable, "-m", "pip", method, package_name]
    # Add part related to private PyPI source
    if pypi_url != "https://pypi.org/simple":
        # Check if token is available
        if not private_pypi_token_name:
            raise Exception(f"No token specified for private PyPI server {pypi_url}.")
        # Check if the environment variable associated to the private PyPI token exists
        if (private_pypi_token := os.getenv(private_pypi_token_name)) is None:
            raise Exception(f"Environment variable {private_pypi_token_name} does not exist.")
        # Split absolute URL
        parsed_url = urlparse(pypi_url)
        # Update command line
        command += ["-i", f"{parsed_url.scheme}://PAT:{private_pypi_token}@{parsed_url.netloc + parsed_url.path}"]
    # Add no-deps option
    if no_deps:
        command += ["--no-deps"]

    return command


def _get_python_package(
    package_name: str,
    package_version: str = "*",
    method: str = "install",
    pypi_url: str = "https://pypi.org/simple",
    private_pypi_token_name: str = "",
    no_deps: bool = False,
    python_executable: str = sys.executable,
) -> None:
    """
    Install or download a python package using PIP.

    Parameters
    ----------
    package_name: str
        Name of the package
    package_version : str
        Version of the package.
    method : str
        Get method: ``download`` or ``install``
    pypi_url : str
        URL of the PyPI server.
    private_pypi_token_name : str
        Name of the environment variable holding the token to access to the PyPI.
    python_executable : str
        Path to the Python executable.

    Returns
    -------
    None
    """
    # Set pip command
    command = _set_pip_command(
        package_name=package_name,
        package_version=package_version,
        method=method,
        pypi_url=pypi_url,
        private_pypi_token_name=private_pypi_token_name,
        no_deps=no_deps,
        python_executable=python_executable,
    )
    # Run pip command
    process = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        print(process.stdout)
        print(process.stderr)
        raise Exception("Command failed with error.")


def _create_virtual_environment(
    virtual_environment_exists: bool,
    workspace_clear: str | None,
    venv: str = VENV_DIR.name,
) -> None:
    """Create a virtual environment."""
    print("Create virtual environment")
    if virtual_environment_exists and not workspace_clear:
        print("Skipped\n")
        return

    if platform.system() == "Linux":
        subprocess.run([sys.executable, "-m", "pip", "install", "virtualenv"], check=True)
    subprocess.run([sys.executable, "-m", "venv", venv], check=True)
    print()


@contextmanager
def _exit_virtual_environment():
    # this is necessary to trick poetry into thinking it is not in a virtual environment. Otherwise, even if we execute
    # the poetry in the solution's venv with the CWD where the solution's pyproject.toml is located,
    # it will install the packages in the caller's venv (saf-cli)
    venv_path = os.environ.pop("VIRTUAL_ENV", None)
    yield
    if venv_path is not None:
        os.environ["VIRTUAL_ENV"] = venv_path


@contextmanager
def _switch_cwd(solution_root_dir: Path):
    working_directory = Path.cwd()
    try:
        os.chdir(solution_root_dir)
        yield
    finally:
        os.chdir(working_directory)


# Dependency Management System (Build System) -----------------------------------------------------------------------


def _get_version_from_python_specification(specification: str) -> str:
    """Read the version."""
    return ".".join(_read_integers_from_string(specification))


def _get_sign_from_python_specification(specification: str) -> str:
    """Read the mathematical symbol expressing a constraint on the version."""
    first_part = specification.split(".")[0]
    sign = "".join([i for i in first_part if not i.isdigit()])
    if sign == "":
        sign = "=="
    return sign


def _check_poetry_plugin_export_is_required(build_system_version: str, python_interpreter: str) -> bool:
    if int(build_system_version[0]) < 2:
        return False
    result = subprocess.run(
        [python_interpreter, "-m", "pip", "show", "poetry-plugin-export"],
        capture_output=True,
        text=True,
    )
    return result.returncode != 0


def _install_build_system(
    virtual_environment_exists: bool,
    workspace_clear: str | None,
    build_system_version: str,
) -> None:
    """Install build system."""
    print("Install dependency management system.")
    if virtual_environment_exists and not workspace_clear:
        print("Skipped\n")
        return

    # We create a separate virtual environment for poetry, as it's recommended in its documentation:
    # `Poetry should always be installed in a dedicated virtual environment to isolate it from the rest of your system.`
    # See: https://python-poetry.org/docs/#installation
    print()
    _create_virtual_environment(
        virtual_environment_exists,
        workspace_clear,
        venv=POETRY_VENV_DIR.as_posix(),
    )
    _get_python_package(
        "poetry",
        build_system_version,
        method="install",
        python_executable=POETRY_PYTHON_EXEC.absolute().as_posix(),
    )
    # poetry-plugin-export is currently included as a required plugin in the pyproject.toml of the solution.
    # However, if saf install is run in an old solution, we need to make sure the plugin is installed when
    # using poetry >=2.
    if _check_poetry_plugin_export_is_required(build_system_version, POETRY_PYTHON_EXEC.absolute().as_posix()):
        _get_python_package(
            "poetry-plugin-export>=1.8",
            method="install",
            python_executable=POETRY_PYTHON_EXEC.absolute().as_posix(),
        )
    if not POETRY_POETRY_EXEC.is_file():
        raise RuntimeError(f"Poetry executable not found at {POETRY_POETRY_EXEC}.")
    if int(build_system_version[0]) < 2:
        print("Downgrade virtualenv in the poetry virtual environment.")
        _get_python_package(
            "virtualenv",
            "20.30.0",  # virtualenv >= 20.31.0 is incompatible with poetry < 2
            method="install",
            python_executable=POETRY_PYTHON_EXEC.absolute().as_posix(),
        )
    # Create a file symbolic link from the virtual environment (.venv) that the build system (poetry) manages
    # to the build system executable (poetry.exe) in the poetry virtual environment (.poetry/.venv). This
    # ensures that the correct poetry is accessible when the managed virtual environment is activated

    if platform.system() == "Windows":
        subprocess.run(
            [  # noqa: S607
                "powershell",
                "-Command",
                "New-Item",
                "-ItemType",
                "HardLink",
                "-Path",
                f"'{POETRY_EXEC.absolute().as_posix()}'",
                "-Target",
                f"'{POETRY_POETRY_EXEC.absolute().as_posix()}'",
            ],
            check=True,
        )
    elif platform.system() == "Linux":
        subprocess.run(
            [  # noqa: S607
                "ln",
                "-sf",
                POETRY_POETRY_EXEC.absolute().as_posix(),
                POETRY_EXEC.absolute().as_posix(),
            ],
            check=True,
        )
    print()


def _configure_build_system(
    virtual_environment_exists: bool,
    workspace_clear: str | None,
) -> None:
    """Configure the build system to enable connection to private sources."""
    print("Configure dependency management system.")
    if virtual_environment_exists and not workspace_clear:
        print("Skipped\n")
        return

    _configure_poetry()
    print()


def _configure_poetry() -> None:
    """Configure Poetry."""
    subprocess.run(
        [
            POETRY_EXEC.absolute().as_posix(),
            "config",
            "cache-dir",
            POETRY_CACHE_DIR.absolute().as_posix(),
            "--local",
        ],
        check=True,
    )


# Specifics ---------------------------------------------------------------------------------------------------------


def _clear_workspace(workspace_clear: str | None) -> None:
    """Remove residual items form previous installation (like venv directory, lock file ...)."""
    if not workspace_clear:
        print("Skip workspace clear")
        print()
        return

    if VENV_DIR.is_dir():
        print("Delete existing virtual environment '.venv'")
        shutil.rmtree(VENV_DIR)
    if POETRY_VENV_DIR.is_dir():
        print("Delete existing poetry virtual environment")
        shutil.rmtree(POETRY_VENV_DIR)
    if POETRY_CACHE_DIR.is_dir():
        print("Delete existing poetry cache")
        shutil.rmtree(POETRY_CACHE_DIR)
    if workspace_clear == "hard":
        if POETRY_LOCK_FILE.is_file():
            print("Delete existing poetry lock file")
            POETRY_LOCK_FILE.unlink()
    else:
        print("Skip deleting poetry lock file")
    print()


def _resolve_dependency_groups(
    dependency_groups: list[str] | None,
    optional_dependency_groups: list[str],
) -> list[str]:
    if not dependency_groups:
        default_dependency_groups = [
            dependency_group
            for dependency_group in ["desktop", "ui", "doc", "build"]
            if dependency_group in optional_dependency_groups
        ]
        return default_dependency_groups
    if "all" in dependency_groups:
        return optional_dependency_groups
    for dependency_group in dependency_groups:
        if dependency_group not in optional_dependency_groups:
            raise ValueError(f"Invalid dependency group: {dependency_group}")
    return dependency_groups


def _run_poetry_install(args: list[str]) -> None:
    with _exit_virtual_environment():
        try:
            subprocess.run(
                [POETRY_POETRY_EXEC.absolute().as_posix()] + args,
                check=True,
                text=True,
                stderr=subprocess.PIPE,
            )

        except subprocess.CalledProcessError as e:
            if "Authorization error" in e.stderr or "401 Client Error:" in e.stderr:
                raise Exception(
                    "Poetry install failed due to authorization issues with a private PyPI source. "
                    "Please verify each username and password/token for private PyPI sources. ",
                ) from e
            else:
                raise Exception(
                    f"Poetry install failed with an unexpected error. {e.stderr}",
                ) from e


def _get_optional_dependency_groups(configuration: dict[str, Any]) -> list[str]:
    optional_dependency_groups = []
    if "group" in configuration["tool"]["poetry"]:
        optional_dependency_groups = list(configuration["tool"]["poetry"]["group"])
    return optional_dependency_groups


def _install_dependencies(dependency_groups: list[str]) -> None:
    """Install optional requirements (doc, tests, build or style)."""
    # Install standard optional dependency groups
    print(f"Install the following dependency groups: {', '.join(dependency_groups)}")
    dependency_groups_str = ",".join(dependency_groups)
    poetry_cmd = ["install"] + (["--with", dependency_groups_str] if dependency_groups_str else [])
    _run_poetry_install(poetry_cmd)
    print()


def _install_dotnet_linux_dependencies():
    """Install .NET for Linux."""
    print("Install dotnet dependencies")
    if platform.system() != "Linux":
        print("Skipped\n")
        return

    # ruff: disable[S602, S607]
    subprocess.run(
        """
        set -xe \
        && wget https://dot.net/v1/dotnet-install.sh \
        && chmod +x dotnet-install.sh \
        && ./dotnet-install.sh --install-dir /home/$USER/.dotnet --version 8.0.8 --runtime aspnetcore \
        && grep -qxF "DOTNET_ROOT=/home/$USER/.dotnet" /home/$USER/.bash_profile \
        || echo DOTNET_ROOT=/home/$USER/.dotnet >> /home/$USER/.bash_profile \
        && grep -qxF "PATH=\\$PATH:/home/$USER/.dotnet" /home/$USER/.bash_profile \
        || echo "PATH=\\$PATH:/home/$USER/.dotnet" >> /home/$USER/.bash_profile \
        && echo "\nsource /home/$USER/.bash_profile" >> ./.venv/bin/activate \
        && rm dotnet-install.sh
        """,
        check=True,
        shell=True,
    )
    # ruff: enable[S602, S607]
    print()


def _preload_solution_main_module(
    solution_python_exec: Path,
    solution_main_module_name: str,
    selected_dependency_groups: list[str],
    optional_dependency_groups: list[str],
) -> None:
    """Import the main module of the solution to speed up first saf run call."""
    print("Preload solution package")
    if "ui" in optional_dependency_groups and "ui" not in selected_dependency_groups:
        print("Skipped: UI is not in the selected dependency groups.\n")
        return
    try:
        subprocess.run(
            [solution_python_exec.absolute().as_posix(), "-c", f"import {solution_main_module_name}"],
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Importing the solution's main module failed: {e.stderr}") from e
    print()


def setup_environment(
    solution_root_dir: Path,
    solution_main_module_name: str,
    dependency_groups: list[str] | None = None,
    workspace_clear: str | None = None,
    env_file: Path | None = None,
) -> None:
    """Sequence of operations leading to the complete Python ecosystem."""
    if workspace_clear is not None and workspace_clear not in WORKSPACE_CLEAR_OPTIONS:
        raise ValueError(f"Invalid workspace clear option: {workspace_clear}")

    start_time = time.time()

    # Initialize setup ------------------------------------------------------------------------------------------------

    with _switch_cwd(solution_root_dir):
        configuration = tomlkit.loads(PYPROJECT_FILE.read_bytes()).unwrap()

        if env_file is not None:
            print(f"Environment variables loaded from {env_file.resolve()}")
            load_dotenv(env_file)

        _check_private_sources(configuration)

        _check_python_version(configuration)

        virtual_environment_exists = _check_virtual_environment_exists()

        optional_dependency_groups = _get_optional_dependency_groups(configuration)
        selected_dependency_groups = _resolve_dependency_groups(dependency_groups, optional_dependency_groups)

        build_system_version = configuration.get("build-system-requirements", {}).get("build-system-version", None)
        if not build_system_version:
            raise RuntimeError("No build system version found in the configuration file.")

        _print_main_header("Setup Environment")

        _print_inputs_summary(
            selected_dependency_groups,
            build_system_version,
            optional_dependency_groups,
        )

        # Clear workspace ----------------------------------------------------------------------------------------------

        _print_section_header("Clear workspace", max_length=100)

        _clear_workspace(workspace_clear)

        # Setup virtual environment ------------------------------------------------------------------------------------

        _print_section_header("Setup virtual environment", max_length=100)

        _create_virtual_environment(virtual_environment_exists, workspace_clear)

        # Setup dependency management system ---------------------------------------------------------------------------

        _print_section_header("Setup dependency management system", max_length=100)

        _install_build_system(
            virtual_environment_exists,
            workspace_clear,
            build_system_version,
        )

        _configure_build_system(
            virtual_environment_exists,
            workspace_clear,
        )

        # Install dependencies -----------------------------------------------------------------------------------------

        _print_section_header("Install dependencies", max_length=100)

        _install_dependencies(selected_dependency_groups)

        _install_dotnet_linux_dependencies()

        # Preload installed solution package so that the first execution with saf run is faster.
        solution_python_exec = get_exec_from_solution_venv(solution_root_dir, "python")
        _preload_solution_main_module(
            solution_python_exec,
            solution_main_module_name,
            selected_dependency_groups,
            optional_dependency_groups,
        )

        # Finish -------------------------------------------------------------------------------------------------------

        _print_section_header("Summary", max_length=100)

        elapsed_time = (time.time() - start_time) / 60

        print("You are all set!")
        print(f"Execution time: {elapsed_time:.1f} minutes.")
