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

import logging
import os
from unittest import mock

import pytest

from ansys.saf.glow.cli._cli_entry_point import run_ui
import tests.mocks.mock_ui
import tests.mocks.solutions.minimal_solution


@pytest.mark.parametrize(("debug", "ui_debug"), [(False, False), (False, True), (True, False), (True, True)])
def test_ui_server_debug_port(monkeypatch: pytest.MonkeyPatch, debug: bool, ui_debug: bool):
    # GIVEN - an environment with a UI debug port env var set and envars set or unset for debug and ui debug
    port = 12345
    monkeypatch.setenv("GLOW_DEBUG_UI_PORT", str(port))
    if debug:
        monkeypatch.setenv("GLOW_DEBUG", "True")
    if ui_debug:
        monkeypatch.setenv("GLOW_UI_PYTHON_DEBUGGING", "True")

    with (
        mock.patch.dict(os.environ, os.environ.copy()),
        mock.patch.object(
            logging.Logger,
            "info",
        ) as logging_info_mock,
        mock.patch("debugpy.listen") as debugpy_listen_mock,
    ):
        # calling run_ui is going to set env vars, mock os.environ to leave it clean
        # WHEN - invoking the UI
        run_ui("127.0.0.1", 50000, tests.mocks.solutions.minimal_solution, tests.mocks.mock_ui, "", "")  # pyright: ignore[reportAttributeAccessIssue]

        # THEN - the Dash/Flask UI features are enabled as expected
        #        (python debugging is not compatible with the debug features)
        assert tests.mocks.mock_ui.app.debug == (debug and not ui_debug)  # pyright: ignore[reportAttributeAccessIssue]

        if ui_debug:
            # THEN - if the ui debug is enabled debugpy.listen is called with the correct port
            assert debugpy_listen_mock.called
            assert debugpy_listen_mock.call_args_list[0][0][0] == port
            logging_args = [logging_arg[0][0] for logging_arg in logging_info_mock.call_args_list]
            # AND - if the ui debug is enabled the correct port is logged
            ui_debug_log = [
                logging_arg
                for logging_arg in logging_args
                if logging_arg.startswith("#### UI server listening for debug on port:")
            ]
            assert len(ui_debug_log) == 1
            debugpy_port_from_log = int(
                ui_debug_log[0].split("#### UI server listening for debug on port:")[1].split(" ####")[0],
            )
            assert debugpy_port_from_log == port
        else:
            # THEN - if the ui debug is not enabled debugpy.listen is not called
            assert debugpy_listen_mock.assert_not_called
            # AND - if the ui debug is not enabled no port info is logged
            for call in logging_info_mock.call_args_list:
                assert not call[0][0].startswith("#### UI server listening for debug on port:")
