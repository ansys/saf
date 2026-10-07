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

"""Matplotlib-based PNG export for report and UI static figure display."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from saf.solutions.examples.solution.airfoil_explorer.logic.plots import interpolate_stream_field

_png_dpi = 100
_color_white = "white"
_color_black = "black"


def _save_figure(fig: plt.Figure, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=_png_dpi, facecolor=_color_white, edgecolor=_color_white)
    plt.close(fig)


def _minimal_axes(ax: plt.Axes, xlim: tuple[float, float], ylim: tuple[float, float]) -> None:
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")


def save_airfoil_png(
    path: str | Path,
    x_u: np.ndarray,
    y_u: np.ndarray,
    x_l: np.ndarray,
    y_l: np.ndarray,
) -> None:
    """Write a minimal airfoil geometry PNG (matches plot_airfoil minimal layout)."""
    y_all = np.concatenate([y_u, y_l])
    x_range = (-0.1, 1.1)
    y_range = (float(y_all.min()) - 0.1, float(y_all.max()) + 0.1)

    fig, ax = plt.subplots(figsize=(8.0, 4.5), dpi=_png_dpi)
    fig.patch.set_facecolor(_color_white)
    ax.plot(x_u, y_u, color=_color_black, linewidth=2.0)
    ax.plot(x_l, y_l, color=_color_black, linewidth=2.0)
    _minimal_axes(ax, x_range, y_range)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    _save_figure(fig, path)


def save_mesh_png(path: str | Path, nxi: int, neta: int, x: np.ndarray, y: np.ndarray) -> None:
    """Write a minimal mesh PNG (matches plot_grid minimal layout)."""
    fig, ax = plt.subplots(figsize=(7.0, 7.0), dpi=_png_dpi)
    fig.patch.set_facecolor(_color_white)

    for i in range(nxi):
        ax.plot(x[i, :], y[i, :], color=_color_black, linewidth=0.8)
    for j in range(neta):
        ax.plot(x[:, j], y[:, j], color=_color_black, linewidth=0.8)

    _minimal_axes(ax, (-0.2, 1.2), (-0.3, 0.3))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    _save_figure(fig, path)


def save_streamlines_png(path: str | Path, x: np.ndarray, y: np.ndarray, stream: np.ndarray) -> None:
    """Write a minimal streamline PNG (matches plot_streamlines minimal layout)."""
    xi, yi, zi = interpolate_stream_field(x, y, stream)
    foil_x = np.append(x[:, 0], x[0, 0])
    foil_y = np.append(y[:, 0], y[0, 0])

    fig, ax = plt.subplots(figsize=(9.0, 6.0), dpi=_png_dpi)
    fig.patch.set_facecolor(_color_white)
    ax.contourf(xi, yi, zi, levels=50, cmap="viridis")
    ax.fill(foil_x, foil_y, facecolor=_color_white, edgecolor=_color_black, linewidth=1.0)
    _minimal_axes(ax, (-2, 3), (-1.5, 1.5))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    _save_figure(fig, path)
