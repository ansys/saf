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

"""Headless "run" tests for example apps.

Each ``example_*.py`` file under ``examples/`` (including ``examples/gallery_apps/``
and ``examples/user_guide/``) is automatically discovered via the
``pytest_generate_tests`` hook in ``conftest.py``.

Run tests verify that:

* The Dash application server starts without raising an exception.
* The ``/_dash-layout`` endpoint returns HTTP 200, confirming the app is
  healthy and its layout can be serialised.

The tests do **not** open a browser, interact with the UI, or assert anything
about the rendered HTML — that level of testing is left to dedicated end-to-end
tests.  Callback errors are also not checked here: they are only triggered when
the UI is loaded and interacted with, which is outside the scope of these
headless tests.

Implementation note
-------------------
``app.run()`` starts a blocking Werkzeug server and cannot be stopped from
another thread, so we use ``werkzeug.serving.make_server`` instead.  This
gives us a handle whose ``shutdown()`` method can be called from the test
thread after the assertions, keeping each test self-contained.
"""

from pathlib import Path
import threading
import time
from typing import cast

import pytest
import requests
from werkzeug.serving import make_server

from tests.examples.conftest import load_example_module


@pytest.mark.run
def test_example_serves_layout(example_path: Path) -> None:
    """Start the example app and verify it serves the layout endpoint.

    The test:

    1. Imports the example module (reusing the cached module if already loaded
       by a prior smoke test).
    2. Starts the Dash Flask server on an OS-assigned ephemeral port in a
       daemon background thread via ``werkzeug.serving.make_server``.
    3. Polls ``/_dash-layout`` until the server is ready (max 15 s).
    4. Asserts that ``/_dash-layout`` returns HTTP 200.
    5. Shuts the server down cleanly.
    """
    module = load_example_module(example_path)

    if not hasattr(module, "app"):
        pytest.fail(f"{example_path.name} does not define a top-level ``app`` variable.")

    # Pass port=0 so the OS assigns a free port atomically.
    flask_server = make_server("127.0.0.1", 0, module.app.server)
    host, port = cast("tuple[str, int]", flask_server.server_address)
    server_thread = threading.Thread(target=flask_server.serve_forever, daemon=True)
    server_thread.start()

    layout_url = f"http://{host}:{port}/_dash-layout"

    try:
        # Poll until the server is accepting connections (max 15 s).
        deadline = time.monotonic() + 15
        last_exc: Exception | None = None
        resp: requests.Response | None = None
        while time.monotonic() < deadline:
            try:
                resp = requests.get(layout_url, timeout=2)
                break
            except requests.exceptions.ConnectionError as exc:
                last_exc = exc
                time.sleep(0.25)
        else:
            raise TimeoutError(f"{example_path.name}: server did not become ready within 15 s. Last error: {last_exc}")

        assert resp is not None
        assert resp.status_code == 200, f"{example_path.name}: ``/_dash-layout`` returned HTTP {resp.status_code}."

    finally:
        flask_server.shutdown()
        server_thread.join(timeout=5)
