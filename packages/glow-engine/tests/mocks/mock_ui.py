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

# this module is a mockup of a Dash UI module that would be provided by a solution

from collections.abc import Callable
from typing import Any


class MockFlaskServer:
    def before_request(self, func: Callable[[], Any]) -> Callable[[], Any]:
        return func

    def get(self, rule: str, **options: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return lambda func: func

    def post(self, rule: str, **options: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return lambda func: func


class MockUI:
    def __init__(self) -> None:
        self.server = MockFlaskServer()
        self.index_string = """<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="UTF-8">
        {%metas%}
        <title>Custom Title - {%title%}</title>
        {%css%}
        <style>body { background: white; }</style>
    </head>
    <body class="custom-class">
        <header>Custom Header</header>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
            <p>Custom Footer</p>
        </footer>
    </body>
</html>"""

    def run(self, host: str, port: int, debug: bool) -> None:
        self.host = host
        self.port = port
        self.debug = debug


app = MockUI()
