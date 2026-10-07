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

"""Grid generation functions for airfoil geometry."""

import numpy as np

from .airfoil import airfoil_surface


def generate_grid(Nxi, Neta, thickness_max, camber_max, camber_pos, chord_length):
    """Generate initial grid around airfoil."""
    # Outer boundary radius
    outer_radius = 5.0

    # Initialize X[i, j] and Y[i, j]
    X = np.zeros((Nxi, Neta))
    Y = np.zeros((Nxi, Neta))

    # Generate grid points on airfoil surface
    Nxc = (Nxi - 1) // 2 + 1
    xc = np.linspace(0, chord_length, Nxc)
    xU_s, yU_s = airfoil_surface(xc, thickness_max, +1, camber_max, camber_pos, chord_length)
    xL_s, yL_s = airfoil_surface(xc, thickness_max, -1, camber_max, camber_pos, chord_length)

    # Set x_{i, j=0} and y_{i, j=0}
    X[:Nxc, 0] = xL_s[::-1]
    X[Nxc:, 0] = xU_s[1:]

    Y[:Nxc, 0] = yL_s[::-1]
    Y[Nxc:, 0] = yU_s[1:]

    # Generate grid points on circular outer boundary
    dr = 2.0 * np.pi / (Nxi - 1)
    theta = -np.array([i * dr for i in range(Nxi)])
    X[:, -1] = 0.5 * chord_length + outer_radius * np.cos(theta)
    Y[:, -1] = outer_radius * np.sin(theta)

    # Linear interpolation of interior grid points
    for i in range(Nxi):
        X[i, 1:-1] = np.linspace(X[i, 0], X[i, -1], Neta)[1:-1]
        Y[i, 1:-1] = np.linspace(Y[i, 0], Y[i, -1], Neta)[1:-1]
    return X, Y


def solve_a_b_c(x, y):
    """Solve a, b, c coefficients for elliptic grid generation.

    input:
        x: the x coordinate of x_{i=i-1~i+1, j=j-1~j+1}, at least 3x3 array
        y: the y coordinate of y_{i=i-1~i+1, j=j-1~j+1}, at least 3x3 array
    output:
        a, b, c: at least 1x1 float
    """
    a = 0.25 * (((x[1:-1, 2:] - x[1:-1, :-2]) ** 2) + ((y[1:-1, 2:] - y[1:-1, :-2]) ** 2))
    b = 0.25 * (
        (x[2:, 1:-1] - x[:-2, 1:-1]) * (x[1:-1, 2:] - x[1:-1, :-2])
        + (y[2:, 1:-1] - y[:-2, 1:-1]) * (y[1:-1, 2:] - y[1:-1, :-2])
    )
    c = 0.25 * (((x[2:, 1:-1] - x[:-2, 1:-1]) ** 2) + ((y[2:, 1:-1] - y[:-2, 1:-1]) ** 2))
    return a, b, c


def solve_equation(a, b, c, U):
    """Solve elliptic grid equation for one iteration.

    input:
        a, b, c: as described in the content
        U: the result of the last iteration
    output:
        return the result of current iteration
    """
    return (
        0.5
        * (
            a * (U[2:, 1:-1] + U[:-2, 1:-1])
            + c * (U[1:-1, 2:] + U[1:-1, :-2])
            - b * 0.5 * (U[2:, 2:] - U[2:, :-2] + U[:-2, :-2] - U[:-2, 2:])
        )
        / (a + c)
    )


def solve_elliptic_grid(x, y):
    """Solve elliptic grid generation equations iteratively."""
    # --- Iterate until smooth ---
    iters = 0
    while True:

        # count the number of iterations
        iters += 1

        # backup the last result
        xn = x.copy()
        yn = y.copy()

        # solve periodic BC first
        tempx = np.append([x[-2, :].copy()], x[0:2, :].copy(), 0)
        tempy = np.append([y[-2, :].copy()], y[0:2, :].copy(), 0)
        a, b, c = solve_a_b_c(tempx, tempy)
        x[0, 1:-1] = solve_equation(a, b, c, tempx)
        y[0, 1:-1] = solve_equation(a, b, c, tempy)

        x[-1, 1:-1] = x[0, 1:-1].copy()
        y[-1, 1:-1] = y[0, 1:-1].copy()

        # solve interior
        a, b, c = solve_a_b_c(x, y)
        x[1:-1, 1:-1] = solve_equation(a, b, c, x)
        y[1:-1, 1:-1] = solve_equation(a, b, c, y)

        # calculate difference between current and the last result
        errx = np.abs(x - xn)
        erry = np.abs(y - yn)

        # adjudge whether the iteration should stop
        if (errx.max() <= 1e-6) and (erry.max() <= 1e-6):
            break
    return x, y
