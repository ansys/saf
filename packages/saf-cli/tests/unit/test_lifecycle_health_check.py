# SPDX-FileCopyrightText: Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0

import pytest

from tests.e2e import conftest as e2e_conftest


def test_dashboard_lifecycle_checks_dashboard_route(monkeypatch: pytest.MonkeyPatch) -> None:
    checked_urls: list[str] = []
    monkeypatch.setattr(e2e_conftest, "_check_service_health", checked_urls.append)
    monkeypatch.setattr(e2e_conftest, "_get_a_project_identifier", lambda _port: "project-id")

    project_ui_url = e2e_conftest.check_solution_launched_correctly(
        "5001",
        "5002",
        "5003",
        use_projects_dashboard=True,
    )

    assert checked_urls == [
        "http://127.0.0.1:5001/docs",
        "http://127.0.0.1:5002/projects",
        "http://127.0.0.1:5002/projects/project-id",
    ]
    assert project_ui_url == "http://127.0.0.1:5002/projects/project-id"


def test_standalone_portal_health_check_remains_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    checked_urls: list[str] = []
    monkeypatch.setattr(e2e_conftest, "_check_service_health", checked_urls.append)
    monkeypatch.setattr(e2e_conftest, "_get_a_project_identifier", lambda _port: "project-id")

    project_ui_url = e2e_conftest.check_solution_launched_correctly("5001", "5002", "5003")

    assert checked_urls == [
        "http://127.0.0.1:5003",
        "http://127.0.0.1:5001/docs",
        "http://127.0.0.1:5002/projects/project-id",
    ]
    assert project_ui_url == "http://127.0.0.1:5002/projects/project-id"
