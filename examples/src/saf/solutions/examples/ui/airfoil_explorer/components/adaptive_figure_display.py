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

"""Reusable component for hybrid JSON/PNG figure display."""

from __future__ import annotations

from typing import Literal

from dash_extensions.enrich import dcc, html
import dash_mantine_components as dmc


def AdaptiveFigureDisplay(
    id: str,
    json_figure: dict | None = None,
    image_url: str | None = None,
    mode: Literal["interactive", "fast", "auto"] = "auto",
    show_toggle: bool = True,
    style: dict | None = None,
) -> html.Div:
    """Create a hybrid figure display that can switch between interactive JSON and fast PNG.

    Args:
        id: Base ID for the component. Inner components will use suffixes.
        json_figure: Plotly figure dictionary for interactive mode.
        image_url: URL to the PNG image for fast mode.
        mode: Initial mode ("interactive", "fast", or "auto").
              "auto" defaults to fast if PNG available, else interactive.
        show_toggle: Whether to show the toggle switch.
        style: Optional style dict for the container.

    Components & IDs:
        - Container: {id}
        - Graph: {id}-graph
        - Image: {id}-image
        - Toggle: {id}-toggle
        - Mode Store: {id}-mode-store

    Usage:
        The parent page should register a callback to handle toggle switching:

        @callback(
            Output(f"{id}-graph", "style"),
            Output(f"{id}-image", "style"),
            Input(f"{id}-toggle", "checked"),
        )
        def toggle_view(is_interactive):
            if is_interactive:
                return {"display": "block", "width": "100%"}, {"display": "none"}
            return {"display": "none"}, {"display": "block", "width": "100%"}
    """
    graph_id = f"{id}-graph"
    image_id = f"{id}-image"
    toggle_id = f"{id}-toggle"

    # Determine initial visibility
    if mode == "auto":
        # Prefer fast mode (PNG) when image is available, fall back to interactive (JSON)
        is_interactive = not bool(image_url)
    else:
        is_interactive = mode == "interactive"

    graph_style = {"display": "block" if is_interactive else "none", "width": "100%", "height": "auto"}
    image_style = {"display": "none" if is_interactive else "block", "width": "100%", "height": "auto"}

    return html.Div(
        id=id,
        style=style or {"width": "100%"},
        children=[
            dmc.Group(
                justify="flex-end",
                mb="xs",
                style={"display": "flex" if show_toggle else "none"},
                children=[
                    dmc.Switch(
                        id=toggle_id,
                        label="Interactive View",
                        onLabel="ON",
                        offLabel="OFF",
                        checked=is_interactive,
                        size="sm",
                    )
                ],
            ),
            dcc.Graph(
                id=graph_id,
                figure=json_figure or {},
                config={"displayModeBar": False},
                style=graph_style,
            ),
            html.Img(
                id=image_id,
                src=image_url or "",
                style=image_style,
            ),
        ],
    )
