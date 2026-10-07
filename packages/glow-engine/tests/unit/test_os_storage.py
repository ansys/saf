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

from typing import cast

from ansys.saf.glow._storage.os import OperatingSystemPath, OperatingSystemStorage
from ansys.saf.testing.platform_specific import linux_only, windows_only


@windows_only()
def test_operating_system_path_parses_uri_for_shared_directory_on_windows():
    p = OperatingSystemPath("\\\\xyz\\abc")
    uri = p.as_uri()
    pp = cast("OperatingSystemPath", OperatingSystemStorage().create_path_from_reference(uri))
    assert p.path == pp.path


@windows_only()
def test_operating_system_path_parses_uri_for_absolute_directory_on_windows():
    p = OperatingSystemPath("c:\\xyz\\abc")
    uri = p.as_uri()
    pp = cast("OperatingSystemPath", OperatingSystemStorage().create_path_from_reference(uri))
    assert p.path == pp.path


@linux_only()
def test_operating_system_path_parses_uri_on_linux():
    p = OperatingSystemPath("/xyz/abc")
    uri = p.as_uri()
    pp = cast("OperatingSystemPath", OperatingSystemStorage().create_path_from_reference(uri))
    assert p.path == pp.path
