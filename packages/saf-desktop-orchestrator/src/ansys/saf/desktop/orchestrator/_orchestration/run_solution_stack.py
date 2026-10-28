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

from __future__ import annotations

from collections.abc import MutableMapping  # noqa: TC003
from functools import partial
import importlib
import json
import logging
import logging.config
import os
from pathlib import Path  # noqa: TC003
import platform
import signal
import sys
import time
from typing import TYPE_CHECKING, Any
import uuid
import webbrowser

from dotenv import load_dotenv
import httpx2
import webview  # pyright: ignore[reportMissingTypeStubs]

from ansys.saf.desktop.orchestrator._orchestration.exceptions import (
    CantCreateProjectError,
    SameDisplayNameProjectException,
)
from ansys.saf.desktop.orchestrator._orchestration.pywebview_events import set_custom_pywebview_icon
from ansys.saf.desktop.orchestrator._orchestration.signal_fence import signal_fence
from ansys.saf.desktop.orchestrator._orchestration.solution_ui_framework import SolutionUIFramework
from ansys.saf.desktop.orchestrator._utilities.splash_screen import SplashScreen

if TYPE_CHECKING:
    from ansys.saf.desktop.orchestrator._config.schema import Settings
    from ansys.saf.desktop.orchestrator._orchestration.launcher import Launcher

logger = logging.getLogger(__name__)


LOGGING_DEFAULT_CONFIG = """
{
    "version": 1,
    "disable_existing_loggers": false,
    "formatters": {"saf": {"format": "%(levelname)s - %(message)s"}},
    "handlers": {
        "stream": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "saf"
        },
        "file": {
            "class": "logging.FileHandler",
            "formatter": "saf",
            "filename": "%FILEPATH%",
            "mode": "w"
        }
    },
    "root": {"level": "WARNING", "handlers": ["stream", "file"]},
    "loggers": {
        "ansys.saf.desktop": {
            "level": "DEBUG",
            "handlers": ["stream", "file"],
            "propagate": false
        }
    }
}"""
NOT_LAUNCHED = "not launched"


def _create_project(http_client: httpx2.Client, project_display_name: str) -> str:
    try:
        r = http_client.post("/projects", json={"display_name": project_display_name})
        r.raise_for_status()
    except Exception as ex:
        raise CantCreateProjectError(f"Project `{project_display_name}` could not be created.") from ex
    return r.json()["name"]


def _get_or_create_project(http_client: httpx2.Client, project_display_name: str) -> str:
    try:
        r = http_client.get("/projects", params={"filter": f'display_name = "{project_display_name}"'})
        r.raise_for_status()
    except Exception as ex:
        raise CantCreateProjectError("Failed to get projects from GLOW API server.") from ex

    matching_projects = [elem for elem in r.json()["projects"] if elem["display_name"] == project_display_name]
    if len(matching_projects) > 1:
        # Since display_name is not a unique project attribute in GLOW, raise exception
        # if we find more than 1 matching project and we can't resolve the petition.
        raise SameDisplayNameProjectException(f"Multiple projects found with display name {project_display_name}.")
    elif len(matching_projects) == 1:
        project_name = matching_projects[0]["name"]
        return project_name

    return _create_project(http_client, project_display_name)


def _launch_services(
    launcher: Launcher,
    with_pim: bool,
    with_ui: bool,
    with_portal: bool,
    splash_screen: SplashScreen,
    additional_services_spec_file: Path | None,
    log_to_files: bool = False,
) -> tuple[str, str, str, str, str, dict[str, str]]:
    # here we are ensuring that launcher is not Ctrl-C interrupted to that it is in a
    # known state when launcher.stop is executed

    with signal_fence(signal.SIGINT):
        add_services_urls: dict[str, str] = {}
        if additional_services_spec_file:
            logger.info("Starting additional services...")
            splash_screen.update_status("Starting additional services...")
            services = launcher.start_additional_services(additional_services_spec_file)
            for service_name, service_info in services.items():
                add_services_urls[service_name] = service_info.address

        if not log_to_files:
            logger.info("Starting OTEL Dashboard...")
            splash_screen.update_status("Starting OTEL Dashboard...")
            launcher.start_otel()
            otel_url = launcher.get_service_info("OTEL").address
        else:
            otel_url = NOT_LAUNCHED

        pim_url = NOT_LAUNCHED
        if with_pim:
            logger.info("Starting PIM Light Server...")
            splash_screen.update_status("Starting PIM Light Server...")
            launcher.start_pim()
            pim_url = launcher.get_service_info("PIM").address

        logger.info("Starting Solution API...")
        splash_screen.update_status("Starting Solution API...")
        launcher.start_solution_api()
        solution_api_url = launcher.get_service_info("API").address

        solution_ui_url = NOT_LAUNCHED
        if with_ui:
            logger.info("Starting Solution UI...")
            splash_screen.update_status("Starting Solution UI...")
            launcher.start_solution_ui()
            solution_ui_url = launcher.get_service_info("UI").address

        portal_url = NOT_LAUNCHED
        if with_portal and not launcher.use_projects_dashboard:
            logger.info("Starting SAF Portal...")
            splash_screen.update_status("Starting SAF Portal...")
            launcher.start_portal()
            portal_url = launcher.get_service_info("PORTAL").address

        launcher.wait_for_healthy()
        splash_screen.update_status("All services are up and running.")

    return solution_api_url, solution_ui_url, portal_url, pim_url, otel_url, add_services_urls


def _append_loopback_addresses_to_no_proxy_env_vars(env: MutableMapping[str, str]) -> None:
    """Ensure NO_PROXY and no_proxy contain localhost loopback addresses (localhost, 127.0.0.1, ::1)."""
    for no_proxy_env_var in ["NO_PROXY", "no_proxy"]:
        no_proxy = env.get(no_proxy_env_var, "")
        entries = [entry.strip() for entry in no_proxy.split(",") if entry.strip()]
        if "localhost" not in entries:
            entries.append("localhost")
        if "127.0.0.1" not in entries:
            entries.append("127.0.0.1")
        if "::1" not in entries:
            entries.append("::1")
        env[no_proxy_env_var] = ",".join(entries)


def run_solution_stack(
    solution_main_module_name: str,
    portal: bool = False,
    no_ui: bool = False,
    browser: bool = False,
    streamlit_ui: bool = False,
    input_project_display_name: str | None = None,
    env_file: Path | None = None,
    enable_automatic_project_migration: bool = False,
    log_to_files: bool = False,
    pre_load: bool = False,
) -> None:
    splash_screen = SplashScreen(solution_main_module_name)
    if not pre_load and not no_ui and platform.system() == "Windows":
        # The splash screen is shown regardless of UI module availability (unless --no-ui is set).
        # We skip pre-checking the UI module to avoid importing GLOW and incurring startup delay.
        splash_screen.start_splash()

    try:
        _run_solution_stack_inner(
            solution_main_module_name,
            env_file,
            log_to_files,
            streamlit_ui,
            no_ui,
            portal,
            browser,
            input_project_display_name,
            enable_automatic_project_migration,
            pre_load,
            splash_screen,
        )
    finally:
        splash_screen.stop_splash()


def _run_solution_stack_inner(  # noqa: C901
    solution_main_module_name: str,
    env_file: Path | None,
    log_to_files: bool,
    streamlit_ui: bool,
    no_ui: bool,
    portal: bool,
    browser: bool,
    input_project_display_name: str | None,
    enable_automatic_project_migration: bool,
    pre_load: bool,
    splash_screen: SplashScreen,
) -> None:
    # These imports are run here because they take a significant amount of time, which would delay the splash screen
    # if they were imported at a module level.
    from ansys.saf.desktop.orchestrator._config.schema import GLOW_PRODUCT_INSTANCE_SYSTEM, Settings
    from ansys.saf.desktop.orchestrator._orchestration.launcher import Launcher
    from ansys.saf.desktop.orchestrator._orchestration.streamlit_launcher import StreamlitLauncher
    from ansys.saf.glow.cli import run_analysis

    analysis_result = run_analysis(solution_main_module_name=solution_main_module_name)
    if not analysis_result.valid:
        raise RuntimeError(f"{analysis_result.error}\n{analysis_result.stack_trace}")

    if env_file:
        load_dotenv(dotenv_path=env_file.resolve())
    _append_loopback_addresses_to_no_proxy_env_vars(os.environ)

    fallback_required = not log_to_files and importlib.util.find_spec("ansys.saf.aspire") is None  # type: ignore
    if fallback_required:
        log_to_files = True

    settings_args: dict[str, Any] = {"saf_desktop_solution_name": analysis_result.solution_name}
    if log_to_files:
        # To pass CLI option to Settings and validate it
        settings_args["saf_desktop_log_to_files"] = True
    orchestrator_settings = Settings(**settings_args)

    logfile = orchestrator_settings.computed_solution_appdata_directory / "orchestrator.log"
    logfile.parent.mkdir(exist_ok=True, parents=True)
    config = LOGGING_DEFAULT_CONFIG.replace("%FILEPATH%", logfile.as_posix())
    logging.config.dictConfig(json.loads(config))
    logger.info(f"Extended logging available at {logfile}")

    # delay messages until we have the logger configured, which requires Settings to be initialized
    if env_file:
        logger.info(f"Environment variables loaded from {env_file.resolve()}")
    if fallback_required:
        logger.warning(
            "ansys.saf.aspire module not found, falling back to logging to files. "
            "If you want to use OTEL dashboard, make sure ansys-saf-aspire is installed.",
        )
    if splash_screen.is_active:
        logger.debug("Splash screen started.")
        logger.debug(f"Using splash image at {splash_screen.splash_png_path}")

    with_pim = analysis_result.uses_shared_product_instances and os.environ.get(GLOW_PRODUCT_INSTANCE_SYSTEM) != "HPS"
    ui_framework, with_ui = _get_solution_ui_framework(streamlit_ui, bool(analysis_result.ui_module), no_ui)
    if not with_ui and (portal or browser):
        raise ValueError("Portal and/or Browser cannot be enabled if the solution UI is disabled.")

    if portal and input_project_display_name:
        raise ValueError("A project display name cannot be specified when portal is enabled.")

    launcher_type = Launcher if ui_framework != SolutionUIFramework.streamlit else StreamlitLauncher
    launcher = launcher_type(
        orchestrator_settings,
        solution_main_module_name,
        analysis_result.solution_module,
        with_pim,
        with_ui,
        ui_framework,
        portal,
        env_file,
        enable_automatic_project_migration,
        log_to_files=orchestrator_settings.saf_desktop_log_to_files,
    )

    if launcher.use_projects_dashboard:
        logger.debug(
            "Projects Dashboard detected (ansys_saf_projects_dashboard installed); SAF Portal will not be started.",
        )

    try:
        solution_api_url, solution_ui_url, portal_url, pim_url, otel_url, add_services_urls = _launch_services(
            launcher,
            with_pim,
            with_ui,
            portal,
            splash_screen,
            orchestrator_settings.saf_definition_path,
            orchestrator_settings.saf_desktop_log_to_files,
        )

        with httpx2.Client() as http_client:
            response = http_client.get(f"{solution_api_url}/schema")
        solution_display_name = response.json()["properties"]["display_name"]["default"]

        ui_url = ""
        if portal:
            project_info = "no project created or selected"
            ui_url = (
                f"{solution_ui_url}{launcher.projects_dashboard_path}"
                if launcher.use_projects_dashboard
                else portal_url
            )
        else:
            with httpx2.Client(base_url=solution_api_url) as http_client:
                if input_project_display_name is None:
                    project_display_name = f"my-project-{str(uuid.uuid4())[:5]}"
                    project_name = _create_project(http_client, project_display_name)
                else:
                    project_display_name = input_project_display_name
                    project_name = _get_or_create_project(http_client, project_display_name)
            project_info = f"\n- display name: {project_display_name}\n- name: {project_name}"
            if solution_ui_url != NOT_LAUNCHED:
                ui_url = solution_ui_url = launcher.get_project(project_name)

        logger.info(f"Solution: {solution_display_name}")
        logger.info(f"Project: {project_info}")
        logger.info(f"Solution API: {solution_api_url}/docs")
        logger.info(f"Solution UI: {solution_ui_url}")
        if launcher.use_projects_dashboard:
            logger.info(f"Projects Dashboard: {solution_ui_url}{launcher.projects_dashboard_path}")
        logger.info(f"OTEL Dashboard: {otel_url}")
        logger.info(f"SAF Portal: {portal_url}")
        logger.info(f"PIM Light Server: {pim_url}")
        logger.info(f"Additional services:{' ' + NOT_LAUNCHED if not add_services_urls else ''}")
        for add_service_name, add_service_url in add_services_urls.items():
            logger.info(f"- {add_service_name}: {add_service_url}")
        sys.stdout.flush()

        _display_ui(
            browser=browser,
            pre_load=pre_load,
            orchestrator_settings=orchestrator_settings,
            with_ui=with_ui,
            solution_display_name=solution_display_name,
            ui_url=ui_url,
            solution_main_module_name=solution_main_module_name,
            splash_screen=splash_screen,
        )
    except Exception as ex:
        logger.exception(ex)
        raise
    finally:
        logger.info("Shutting down services...")
        # launcher.stop signals this process to shutdown
        # so block Ctrl-C here too so that shutdown can run without interruption
        with signal_fence(signal.SIGINT):
            launcher.stop()


def _display_ui(
    browser: bool,
    pre_load: bool,
    orchestrator_settings: Settings,
    with_ui: bool,
    solution_display_name: str,
    ui_url: str,
    solution_main_module_name: str,
    splash_screen: SplashScreen,
) -> None:
    needs_webview = with_ui and not browser and platform.system() == "Windows"

    if needs_webview:
        webview.settings["ALLOW_DOWNLOADS"] = True
        window = webview.create_window(  # pyright: ignore[reportUnknownMemberType]
            solution_display_name,
            ui_url,
            text_select=True,
            min_size=(1200, 800),
            confirm_close=True,
        )
        if window:
            window.events.before_show += partial(set_custom_pywebview_icon, window, solution_main_module_name)

    if not pre_load:
        splash_screen.stop_splash()
        if needs_webview:
            logger.info("Starting webview...")
            webview.start()  # automatically blocks until window is closed
            logger.info("Ending webview...")
        elif with_ui and (browser or platform.system() != "Windows"):
            logger.info(f"Opening browser at {ui_url}...")
            webbrowser.open(ui_url)
            _run_forever(orchestrator_settings)
        else:
            _run_forever(orchestrator_settings)


def _get_solution_ui_framework(streamlit_ui: bool, ui_module: bool, no_ui: bool) -> tuple[SolutionUIFramework, bool]:
    with_ui = ui_module and not no_ui
    if streamlit_ui:
        if not no_ui:
            with_ui = True
        return SolutionUIFramework.streamlit, with_ui
    elif with_ui:
        return SolutionUIFramework.dash, with_ui
    else:
        return SolutionUIFramework.no_ui, with_ui


def _run_forever(settings: Settings) -> None:
    print("Press Ctrl+C to exit...")
    while not settings.saf_desktop_test_env:
        time.sleep(0.5)
