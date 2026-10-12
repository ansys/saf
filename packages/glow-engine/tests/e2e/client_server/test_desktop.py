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

import asyncio
import contextlib
from pathlib import Path
from typing import Any

import httpx2
import pytest
from tenacity import TryAgain, retry, stop_after_attempt, wait_fixed

from ansys.saf.glow.solution import MethodState, MethodStatus
from ansys.saf.testing.solution.end_to_end import GlowBaseProcess, ProjectFixture
from tests.mocks.solutions.desktop import DesktopSolution

pytestmark = pytest.mark.parametrize("solution_type", [DesktopSolution], indirect=True)


@pytest.fixture(autouse=True)
def cleanup_glow_running_methods(session_glow: GlowBaseProcess[DesktopSolution]) -> None:
    # Let's make sure that all these tests start with a clean GLOW API server without running methods registered.
    session_glow.restart()


async def launch_transaction(async_client: httpx2.AsyncClient, url: str, signal_file: Path):
    response = await async_client.post(url, json={"signal_file": signal_file.as_posix()})
    response.raise_for_status()


@retry(
    stop=stop_after_attempt(100),
    wait=wait_fixed(0.3),
)
async def wait_for_transactions_to_be_in_status(
    async_client: httpx2.AsyncClient,
    method_urls: list[str],
    status: str,
) -> bool:
    for method_url in method_urls:
        response = await async_client.get(method_url)
        response.raise_for_status()
        if response.json()["status"] != status:
            raise TryAgain
    return True


@pytest.mark.parametrize("long_running", [False, True])
async def test_running_methods_are_set_to_failed(
    tmp_path: Path,
    long_running: bool,
    session_glow: GlowBaseProcess[DesktopSolution],
    function_project: ProjectFixture[DesktopSolution],
):
    """Test that running transactions are set to Failed when desktop:exit is called."""
    step = function_project.project.steps.desktop_step

    method_name = "infinity_lr" if long_running else "infinity"
    method_name_with_dashes = method_name.replace("_", "-")
    assert step.get_method_state(method_name).status == MethodStatus.RunRequired

    signal_file = tmp_path / "signal.txt"
    signal_file.touch()

    async with httpx2.AsyncClient() as async_client:
        url = (
            f"{session_glow.base_api_url}/{function_project.project_name}/steps/desktop-step:{method_name_with_dashes}"
        )
        task = asyncio.create_task(launch_transaction(async_client, url, signal_file))
        await wait_for_transactions_to_be_in_status(async_client, [url], "running")

        response = await async_client.post(f"{session_glow.base_api_url}/desktop:exit")
        response.raise_for_status()
        with contextlib.suppress(Exception):
            # closing tasks
            task.result()
    method_state = step.get_method_state(method_name)
    assert method_state.status == MethodStatus.Failed
    assert method_state.exception_message == "The project was closed before the method completed."

    # At the end of every test, signal the running transactions (long running and sync) that they should stop.
    # Leaving them running and trying to restart glow in the future doesn't work properly on Linux, where we send
    # SIGTERM signals (GlowDesktopInstance.stop()) and uvicorn politely waits for tasks to finish. Sending SIGTERM
    # is still the right thing to do, though, so resources such as ports are properly freed.
    signal_file.write_text("stop")
    await asyncio.sleep(0.5)  # give them time to read the file and stop


async def test_all_running_methods_are_set_to_failed(tmp_path: Path, session_glow: GlowBaseProcess[DesktopSolution]):
    """Test that all running transactions active in the server, of any type and any project, are set to Failed when
    desktop:exit is called."""
    signal_file = tmp_path / "signal.txt"
    signal_file.touch()

    async with httpx2.AsyncClient() as async_client:
        response = await async_client.post(f"{session_glow.base_api_url}/projects", json={"display_name": "project1"})
        project1_name = response.json()["name"]
        response = await async_client.post(f"{session_glow.base_api_url}/projects", json={"display_name": "project2"})
        project2_name = response.json()["name"]

        method_urls = [
            f"{session_glow.base_api_url}/{project1_name}/steps/desktop-step:infinity-lr",
            f"{session_glow.base_api_url}/{project2_name}/steps/desktop-step:infinity-lr",
            f"{session_glow.base_api_url}/{project2_name}/steps/desktop-step:infinity",
            f"{session_glow.base_api_url}/{project1_name}/steps/desktop-step:infinity",
        ]
        tasklist: list[asyncio.Task[Any]] = []
        for method_url in method_urls:
            await asyncio.sleep(0.1)  # transactions fail to launch sometimes if we don't wait between them
            task = asyncio.create_task(launch_transaction(async_client, method_url, signal_file))
            tasklist.append(task)
        await wait_for_transactions_to_be_in_status(async_client, method_urls, "running")

        response = await async_client.post(f"{session_glow.base_api_url}/desktop:exit")
        response.raise_for_status()
        for method_url in method_urls:
            response = await async_client.get(method_url)
            response.raise_for_status()
            assert response.json()["exception_message"] == "The project was closed before the method completed."
        with contextlib.suppress(Exception):
            # closing tasks
            [task.result() for task in tasklist]

    signal_file.write_text("stop")
    await asyncio.sleep(0.5)  # give them time to read the file and stop


async def test_running_methods_are_cleared_after_exit(
    tmp_path: Path,
    session_glow: GlowBaseProcess[DesktopSolution],
    function_project: ProjectFixture[DesktopSolution],
):
    """Test that running_methods is cleared after desktop:exit is called. A second request does nothing."""
    step = function_project.project.steps.desktop_step

    method_name = "infinity_lr"
    method_name_with_dashes = method_name.replace("_", "-")
    assert step.get_method_state(method_name).status == MethodStatus.RunRequired

    signal_file = tmp_path / "signal.txt"
    signal_file.touch()

    async with httpx2.AsyncClient() as async_client:
        url = (
            f"{session_glow.base_api_url}/{function_project.project_name}/steps/desktop-step:{method_name_with_dashes}"
        )
        response = await async_client.post(url, json={"signal_file": signal_file.as_posix()})
        response.raise_for_status()
        await wait_for_transactions_to_be_in_status(async_client, [url], "running")

        response = await async_client.post(f"{session_glow.base_api_url}/desktop:exit")
        response.raise_for_status()
        assert step.get_method_state(method_name).status == MethodStatus.Failed

        response = await async_client.patch(
            url,
            json=MethodState(status=MethodStatus.RunRequired, exception_message=None).model_dump(),
        )
        response.raise_for_status()

        response = await async_client.post(f"{session_glow.base_api_url}/desktop:exit")
        response.raise_for_status()
    method_state = step.get_method_state(method_name)
    assert method_state.status == MethodStatus.RunRequired
    assert not method_state.exception_message

    signal_file.write_text("stop")
    await asyncio.sleep(0.5)  # give them time to read the file and stop


async def test_running_methods_are_isolated_by_project(tmp_path: Path, session_glow: GlowBaseProcess[DesktopSolution]):
    """Test that running_methods of one project are not affect by ones from other projects."""
    signal_file = tmp_path / "signal.txt"
    signal_file.touch()

    async with httpx2.AsyncClient() as async_client:
        # Given: two projects
        response = await async_client.post(f"{session_glow.base_api_url}/projects", json={"display_name": "project1"})
        project1_name = response.json()["name"]
        response = await async_client.post(f"{session_glow.base_api_url}/projects", json={"display_name": "project2"})
        project2_name = response.json()["name"]

        # Launch the same longrunning transaction in both, but one of them will end shortly after.
        # Do it in the following way:
        # - Start #1
        # - Start #2
        # - Finish #2
        # leave #1 running.
        project1_method_url = f"{session_glow.base_api_url}/{project1_name}/steps/desktop-step:infinity-lr"
        project2_method_url = f"{session_glow.base_api_url}/{project2_name}/steps/desktop-step:infinity-lr"
        response = await async_client.patch(
            f"{session_glow.base_api_url}/{project2_name}/steps/desktop-step",
            json={"sleep_time": 1},
        )
        response.raise_for_status()
        await async_client.post(project1_method_url, json={"signal_file": signal_file.as_posix()})
        await wait_for_transactions_to_be_in_status(async_client, [project1_method_url], "running")
        await async_client.post(project2_method_url, json={"signal_file": signal_file.as_posix()})
        await wait_for_transactions_to_be_in_status(async_client, [project2_method_url], "completed")

        # Call /desktop:exit and #1 should be set to failed, but #2 should remain completed.
        response = await async_client.post(f"{session_glow.base_api_url}/desktop:exit")
        response.raise_for_status()
        response = await async_client.get(project1_method_url)
        response.raise_for_status()
        assert response.json()["status"] == "failed"
        assert response.json()["exception_message"] == "The project was closed before the method completed."
        response = await async_client.get(project2_method_url)
        response.raise_for_status()
        assert response.json()["status"] == "completed"
        assert not response.json()["exception_message"]

    signal_file.write_text("stop")
    await asyncio.sleep(0.5)  # give them time to read the file and stop
