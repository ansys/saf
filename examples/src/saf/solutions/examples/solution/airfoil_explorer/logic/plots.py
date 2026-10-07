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

"""Plotting functions for airfoil geometry, grid, and streamlines."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import griddata

if TYPE_CHECKING:
    from plotly.graph_objects import Figure


def interpolate_stream_field(
    x: np.ndarray, y: np.ndarray, stream: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Interpolate stream function values onto a rectilinear grid for contour plots."""
    pts = np.column_stack([x.ravel(), y.ravel()])
    vals = stream.ravel()
    xi = np.linspace(-2, 3, 300)
    yi = np.linspace(-1.5, 1.5, 300)
    xi_mesh, yi_mesh = np.meshgrid(xi, yi)
    zi = griddata(pts, vals, (xi_mesh, yi_mesh), method="cubic")
    return xi, yi, zi


def plot_airfoil(
    x_u: np.ndarray,
    y_u: np.ndarray,
    x_l: np.ndarray,
    y_l: np.ndarray,
    minimal: bool = False,
    include_png: bool = False,
) -> Figure | tuple[Figure, Figure]:
    """Plot airfoil geometry using Plotly and return figure object.

    Args:
        x_u, y_u: Upper surface coordinates
        x_l, y_l: Lower surface coordinates
        minimal: If True, create a clean plot without axes/titles (for PNG export)
        include_png: If True, return tuple of (full_figure, minimal_figure) for both JSON and PNG

    Returns:
        Figure object (default), or tuple of (full_figure, minimal_figure) if include_png=True
    """

    def _create_figure(is_minimal: bool):
        """Create figure with given minimal setting."""
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_u, y=y_u, mode="lines", line={"color": "black", "width": 3}, name="Upper Surface"))
        fig.add_trace(go.Scatter(x=x_l, y=y_l, mode="lines", line={"color": "black", "width": 3}, name="Lower Surface"))

        y_all = np.concatenate([y_u, y_l])
        x_range_zoom = [-0.1, 1.1]
        y_range_zoom = [float(y_all.min()) - 0.1, float(y_all.max()) + 0.1]

        if is_minimal:
            # Clean layout for PNG export - no axes, titles, or margins
            fig.update_layout(
                showlegend=False,
                xaxis=dict(visible=False, range=x_range_zoom),
                yaxis=dict(visible=False, range=y_range_zoom, scaleanchor="x", scaleratio=1),
                margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor="white",
                plot_bgcolor="white",
                height=450,
                width=800,
            )
        else:
            # Full interactive layout with axes and titles
            fig.update_layout(
                title="Airfoil Geometry",
                xaxis_title="x",
                yaxis_title="y",
                plot_bgcolor="white",
                paper_bgcolor="white",
                showlegend=False,
                height=450,
                width=800,
            )
            fig.update_xaxes(range=x_range_zoom)
            fig.update_yaxes(range=y_range_zoom, scaleanchor="x", scaleratio=1)

        return fig

    if include_png:
        # Return both full and minimal figures
        return _create_figure(False), _create_figure(True)
    else:
        # Return single figure based on minimal flag
        return _create_figure(minimal)


def plot_grid(
    nxi: int,
    neta: int,
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    minimal: bool = False,
    include_png: bool = False,
) -> Figure | tuple[Figure, Figure]:
    """Plot grid lines around the airfoil using Plotly and return figure object.

    Args:
        nxi, neta: Grid dimensions
        grid_x, grid_y: Grid coordinates
        minimal: If True, create a clean plot without axes/titles (for PNG export)
        include_png: If True, return tuple of (full_figure, minimal_figure) for both JSON and PNG

    Returns:
        Figure object (default), or tuple of (full_figure, minimal_figure) if include_png=True
    """

    def _create_figure(is_minimal: bool):
        """Create figure with given minimal setting."""
        fig = go.Figure()

        # ξ (circumferential)
        for i in range(nxi):
            fig.add_trace(
                go.Scatter(
                    x=grid_x[i, :], y=grid_y[i, :], mode="lines", line={"color": "black", "width": 1}, showlegend=False
                )
            )

        # η (radial)
        for j in range(neta):
            fig.add_trace(
                go.Scatter(
                    x=grid_x[:, j], y=grid_y[:, j], mode="lines", line={"color": "black", "width": 1}, showlegend=False
                )
            )

        if is_minimal:
            # Clean layout for PNG export
            fig.update_layout(
                showlegend=False,
                xaxis=dict(visible=False, range=[-0.2, 1.2]),
                yaxis=dict(visible=False, range=[-0.3, 0.3], scaleanchor="x", scaleratio=1),
                margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor="white",
                plot_bgcolor="white",
                height=700,
                width=700,
            )
        else:
            # Full interactive layout
            fig.update_layout(
                title="Grid",
                xaxis_title="x",
                yaxis_title="y",
                plot_bgcolor="white",
                paper_bgcolor="white",
                height=700,
                width=700,
            )
            fig.update_xaxes(range=[-0.2, 1.2])
            fig.update_yaxes(range=[-0.3, 0.3], scaleanchor="x", scaleratio=1)

        return fig

    if include_png:
        return _create_figure(False), _create_figure(True)
    else:
        return _create_figure(minimal)


def plot_streamlines(
    x: np.ndarray,
    y: np.ndarray,
    stream: np.ndarray,
    minimal: bool = False,
    include_png: bool = False,
) -> Figure | tuple[Figure, Figure]:
    """Plot streamlines using Plotly contour on an interpolated rectilinear grid and return figure object.

    Args:
        x, y: Grid coordinates
        stream: Stream function values
        minimal: If True, create a clean plot without axes/titles (for PNG export)
        include_png: If True, return tuple of (full_figure, minimal_figure) for both JSON and PNG

    Returns:
        Figure object (default), or tuple of (full_figure, minimal_figure) if include_png=True
    """
    xi, yi, zi = interpolate_stream_field(x, y, stream)

    def _create_figure(is_minimal: bool):
        """Create figure with given minimal setting."""
        fig = go.Figure(
            go.Contour(
                x=xi,
                y=yi,
                z=zi,
                colorscale="Viridis",
                ncontours=50,
                contours=dict(showlabels=False),
                line=dict(width=0.5),
                colorbar=dict(title="Stream Function ψ") if not is_minimal else None,
                showscale=not is_minimal,
            )
        )

        fig.add_trace(
            go.Scatter(
                x=np.append(x[:, 0], x[0, 0]),
                y=np.append(y[:, 0], y[0, 0]),
                fill="toself",
                fillcolor="white",
                line=dict(color="black", width=1),
                name="Airfoil",
            )
        )

        if is_minimal:
            # Clean layout for PNG export
            fig.update_layout(
                showlegend=False,
                xaxis=dict(visible=False, range=[-2, 3]),
                yaxis=dict(visible=False, range=[-1.5, 1.5], scaleanchor="x", scaleratio=1),
                margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor="white",
                plot_bgcolor="white",
                height=600,
                width=900,
            )
        else:
            # Full interactive layout
            fig.update_layout(
                title="Potential Flow over Airfoil",
                plot_bgcolor="white",
                paper_bgcolor="white",
                height=600,
                width=900,
                showlegend=False,
            )
            fig.update_xaxes(range=[-2, 3])
            fig.update_yaxes(range=[-1.5, 1.5], scaleanchor="x", scaleratio=1)

        return fig

    if include_png:
        return _create_figure(False), _create_figure(True)
    else:
        return _create_figure(minimal)
