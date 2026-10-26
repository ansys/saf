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

"""Smoke tests for example apps.

Each ``example_*.py`` file under ``examples/`` (including ``examples/gallery_apps/``
and ``examples/user_guide/``) is automatically discovered via the
``pytest_generate_tests`` hook in ``conftest.py``.

Smoke tests verify:

* The module can be imported without raising an exception.
* The module exposes an ``app`` attribute with a valid Dash layout.
* The ``app`` is a :class:`~dash_extensions.enrich.DashProxy` instance, not
  a plain :class:`~dash.Dash` instance (required for the pattern-matching
  callbacks used by the Super Components for Dash library).
"""

from pathlib import Path

from dash_extensions.enrich import DashProxy
import pytest

from tests.examples.conftest import load_example_module


@pytest.mark.smoke
def test_example_imports_without_error(example_path: Path) -> None:
    """Verify that the example module can be imported without raising an exception."""
    # Will raise if the import itself fails.
    load_example_module(example_path)


@pytest.mark.smoke
def test_example_has_valid_layout(example_path: Path) -> None:
    """Verify that the example module defines an ``app`` with a non-None layout."""
    module = load_example_module(example_path)

    assert hasattr(module, "app"), f"{example_path.name} does not define a top-level ``app`` variable."
    assert module.app.layout is not None, f"{example_path.name}: ``app.layout`` must not be ``None``."


@pytest.mark.smoke
def test_example_uses_dash_proxy(example_path: Path) -> None:
    """Verify that the example uses ``DashProxy``, not a plain ``dash.Dash`` instance.

    Super Components for Dash use pattern-matching callbacks that are only
    available through ``dash_extensions.enrich.DashProxy``.  Using a plain
    ``dash.Dash`` instance will cause those callbacks to be silently ignored.
    """
    module = load_example_module(example_path)

    assert hasattr(module, "app"), f"{example_path.name} does not define a top-level ``app`` variable."
    assert isinstance(module.app, DashProxy), (
        f"{example_path.name}: ``app`` must be a ``DashProxy`` instance, "
        f"got {type(module.app).__name__!r}. "
        "Use ``from dash_extensions.enrich import DashProxy`` and replace "
        "``app = dash.Dash(...)`` with ``app = DashProxy(...)``."
    )
