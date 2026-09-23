# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

import azdo_feed_fetch_version

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


class _Response:
    def __init__(self, package_data: dict[str, object]) -> None:
        self._package_data = package_data
        self.raise_for_status_called = False

    def json(self) -> dict[str, object]:
        return self._package_data

    def raise_for_status(self) -> None:
        self.raise_for_status_called = True


def test_main_writes_latest_stable_version_to_github_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output_path = tmp_path / "github-output"
    response = _Response(
        {
            "value": [
                {
                    "name": "example-package",
                    "versions": [
                        {"version": "1.1.0rc1"},
                        {"version": "1.0.0"},
                        {"version": "1.1.0"},
                        {"version": "2.0.0", "isDeleted": True},
                    ],
                },
            ],
        },
    )

    monkeypatch.setattr(
        azdo_feed_fetch_version,
        "parse_args",
        lambda: argparse.Namespace(package_names=["example-package"]),
    )
    monkeypatch.setattr(azdo_feed_fetch_version.requests, "get", lambda *args, **kwargs: response)
    monkeypatch.setenv("AZURE_DEVOPS_ORG", "example-org")
    monkeypatch.setenv("AZURE_DEVOPS_FEED", "example-feed")
    monkeypatch.setenv("AZURE_DEVOPS_PAT", "token")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))

    azdo_feed_fetch_version.main()

    assert response.raise_for_status_called
    assert output_path.read_text(encoding="utf-8") == "example_package_version=1.1.0\n"
