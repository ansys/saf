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

from pathlib import Path
import sys
from zipfile import ZipFile

import pytest

from ansys.saf.desktop.installer._package.manage_dependencies import download_module


def _create_wheel(wheel_path: Path, package_name: str, version: str) -> None:
    dist_info = f"{package_name.replace('-', '_')}-{version}.dist-info"
    with ZipFile(wheel_path, "w") as wheel:
        wheel.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.1\nName: {package_name}\nVersion: {version}\n",
        )
        wheel.writestr(
            f"{dist_info}/WHEEL",
            "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        wheel.writestr(f"{dist_info}/RECORD", "")


def test_download_module_matches_exact_version(tmp_path: Path):
    module_name = "ansys-saf-glow-engine"
    version = "1.30.0"
    mock_index_package_path = tmp_path / "simple" / module_name
    mock_index_package_path.mkdir(parents=True)
    module_wheel = mock_index_package_path / "ansys_saf_glow_engine-1.30.0-py3-none-any.whl"
    sp_module_wheel = mock_index_package_path / "ansys_saf_glow_engine-1.30.0+sp01-py3-none-any.whl"
    _create_wheel(module_wheel, module_name, version)
    _create_wheel(sp_module_wheel, module_name, "1.30.0+sp01")
    (mock_index_package_path / "index.html").write_text(
        f'<a href="{module_wheel.name}">{module_wheel.name}</a>\n'
        f'<a href="{sp_module_wheel.name}">{sp_module_wheel.name}</a>\n',
    )

    download_path = tmp_path / "download"
    download_path.mkdir()
    module_path = download_path / module_wheel.name
    sp_module_path = download_path / sp_module_wheel.name

    download_module(
        module_name,
        version,
        (tmp_path / "simple").as_uri(),
        download_path,
        Path(sys.executable),
    )

    assert module_path.is_file()
    assert not sp_module_path.is_file()


def test_download_module_does_not_log_url_containing_pat(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ansys.saf.desktop.installer._package.manage_dependencies as manage_dependencies

    monkeypatch.setattr(manage_dependencies.subprocess, "check_output", lambda *args, **kwargs: "")
    secret_url = "https://ghp_secret@example.com/simple?token=secret"
    sensitive_destination = tmp_path / "private-download-directory"

    download_module(
        "example-package",
        "1.2.3",
        secret_url,
        sensitive_destination,
        Path(sys.executable),
    )

    assert "Downloading example-package===1.2.3 to " in caplog.text
    assert secret_url not in caplog.text
    assert "ghp_secret" not in caplog.text
    assert "token=secret" not in caplog.text
    assert f"to {sensitive_destination}." in caplog.text


def test_download_module_does_not_log_url_without_pat(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ansys.saf.desktop.installer._package.manage_dependencies as manage_dependencies

    monkeypatch.setattr(manage_dependencies.subprocess, "check_output", lambda *args, **kwargs: "")
    public_url = "https://example.com/simple"
    destination = tmp_path / "download"

    download_module(
        "example-package",
        "1.2.3",
        public_url,
        destination,
        Path(sys.executable),
    )

    assert f"Downloading example-package===1.2.3 to {destination}." in caplog.text
    assert public_url not in caplog.text
